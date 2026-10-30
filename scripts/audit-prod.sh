#!/usr/bin/env bash
#
# Audit de la production : vérifie, sans rien modifier, que ce qui est dans
# le dépôt tourne réellement sur le VPS — version déployée, services,
# dépendances, fonctionnalités du Studio et de l'Analyzer, sauvegardes.
# À lancer après chaque ./scripts/deploy-lws.sh.
#
# Usage : ./scripts/audit-prod.sh
set -uo pipefail

SSH_KEY="$HOME/.ssh/spad_lws_vps"
VPS_HOST="root@185.98.137.200"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_HEAD=$(git -C "$REPO_DIR" rev-parse --short HEAD)
FAIL=0

echo "── Dépôt local ──"
git -C "$REPO_DIR" fetch -q origin main 2>/dev/null
if [ "$(git -C "$REPO_DIR" rev-parse HEAD)" = "$(git -C "$REPO_DIR" rev-parse origin/main)" ]; then
  echo "  ✓ main ($LOCAL_HEAD) est poussé sur GitHub"
else
  echo "  ✗ main ($LOCAL_HEAD) diffère de origin/main : pousser avant de déployer"; FAIL=$((FAIL + 1))
fi

REMOTE_OUT=$(ssh -i "$SSH_KEY" -o BatchMode=yes -o ConnectTimeout=10 "$VPS_HOST" "bash -s -- $LOCAL_HEAD" <<'REMOTE'
REPO=/var/www/spad-analyzer
EXPECTED=$1
ok() { echo "  ✓ $1"; }
ko() { echo "  ✗ $1"; }
check() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else ko "$1"; fi; }

echo "── Version déployée ──"
HEAD=$(git -C $REPO rev-parse --short HEAD)
if [ "$HEAD" = "$EXPECTED" ]; then ok "le serveur est sur $HEAD, comme le dépôt"; else ko "le serveur est sur $HEAD, le dépôt sur $EXPECTED : lancer ./scripts/deploy-lws.sh"; fi
check "aucun fichier de code modifié à la main sur le serveur" "[ -z \"\$(git -C $REPO status --porcelain --untracked-files=no)\" ]"

echo "── Services ──"
for u in spad-analyzer.service phakts-studio.service spad-kobo-refresh.timer spad-backup.timer; do
  check "$u actif" "systemctl is-active --quiet $u"
done
ERRS=$(journalctl -u spad-analyzer -u phakts-studio --since "-60min" -p err --no-pager -q 2>/dev/null | wc -l)
if [ "$ERRS" -eq 0 ]; then ok "aucune erreur dans les journaux depuis 1 h"; else ko "$ERRS ligne(s) d'erreur dans les journaux depuis 1 h (journalctl -u spad-analyzer -u phakts-studio -p err)"; fi

echo "── Dépendances ──"
cd $REPO
for p in multer:2 express:4.22 mammoth:1.13; do
  name=${p%%:*}; want=${p#*:}
  have=$(node -p "require('$name/package.json').version" 2>/dev/null)
  if [[ "$have" == "$want"* ]]; then ok "$name $have"; else ko "$name $have (attendu $want.x)"; fi
done
check "pyreadstat installé (exports SPSS/Stata)" "analyzer/venv/bin/python3 -c 'import pyreadstat'"
WZ=$(analyzer/venv/bin/python3 -c 'from importlib.metadata import version; print(version("werkzeug"))' 2>/dev/null)
[ "$WZ" = "3.1.9" ] && ok "Werkzeug $WZ" || ko "Werkzeug $WZ (attendu 3.1.9)"

echo "── Sécurité ──"
for f in /etc/spad-analyzer.env /etc/phakts-studio.env; do
  check "$f lisible par root seul" "[ \"\$(stat -c %a $f)\" = 600 ]"
done
for k in SECRET_KEY ANALYZER_PASSWORD_ADMIN; do
  check "$k défini pour l'Analyzer" "grep -qE '^$k=.+' /etc/spad-analyzer.env"
done
check "sauvegardes lisibles par root seul" "[ -z \"\$(find /var/backups/spad -name 'spad-*.tar.gz' -perm /077)\" ]"

echo "── PHAKTS Studio ──"
TOKEN=$(grep -E '^API_TOKEN=' /etc/phakts-studio.env 2>/dev/null | cut -d= -f2- | tr -d "\"'")
AUTH=(-H "Authorization: Bearer $TOKEN")
S=http://127.0.0.1:8010
check "page servie = page du dépôt" "curl -sf '$S/PHAKTS%C2%B7STUDIO.html' | cmp -s - '$REPO/public/PHAKTS·STUDIO.html'"
check "noyau phakts-core.js servi = dépôt" "curl -sf $S/phakts-core.js | cmp -s - $REPO/public/phakts-core.js"
check "service worker à jour (les navigateurs rechargeront la page)" "curl -sf $S/service-worker.js | cmp -s - $REPO/public/service-worker.js"
XLS=$(curl -sf "${AUTH[@]}" -H 'Content-Type: application/json' $S/api/xlsform -d '{
  "formTitle": "Audit", "factum": "PGT14_OS2_RC2_2__CIV_MS__1C1_Audit__20251000__ES",
  "items": [
    {"libelle": "Sports pratiqués", "pf_question": "Sport__X!2*3Sport_", "pf_modalites": "Sport_=[Football|Basket|Tennis|Natation]"},
    {"libelle": "Position GPS", "pf_question": "Coordonnees_GPS__G!DMS", "pf_modalites": "GPS"},
    {"libelle": "Début", "pf_question": "Entretien__Debut__G!start", "pf_modalites": "Automatique"}]}')
echo "$XLS" | python3 -c '
import json, sys
x = json.load(sys.stdin); s = x["survey"]
def say(ok, msg): print(("  ✓ " if ok else "  ✗ ") + msg)
say(any(r.get("name") == "Factum__G" and r.get("type") == "calculate" for r in s), "XLSForm : Factum__G de l’étude dans chaque soumission")
say(any("count-selected(.) >= 2" in r.get("constraint", "") and "<= 3" in r.get("constraint", "") for r in s), "XLSForm : multiplicité N*M (2*3 = entre 2 et 3)")
say(any(r.get("type") == "geopoint" and "capture-accuracy=10" in r.get("parameters", "") for r in s), "XLSForm : précision GPS 10 m")
say(any(r.get("type") == "start" for r in s), "XLSForm : __G!start = métadonnée Kobo")
' 2>/dev/null || ko "XLSForm : réponse invalide de /api/xlsform"
CODE=$(curl -s -o /dev/null -w '%{http_code}' "${AUTH[@]}" -H 'Content-Type: application/json' -d '{}' $S/api/learned/review)
[ "$CODE" = 400 ] && ok "Comité DPF : /api/learned/review en service" || ko "Comité DPF : /api/learned/review répond $CODE"
curl -sf "${AUTH[@]}" $S/api/learned | python3 -c '
import json, sys
d = json.load(sys.stdin)["items"]
v, p, r = (sum(1 for i in d if i.get("statut") == s) for s in ("valide", "propose", "rejete"))
ok = v + p + r == len(d)
print(("  ✓ " if ok else "  ✗ ") + f"registre du Comité : {len(d)} codification(s) — {v} validée(s), {p} proposée(s), {r} rejetée(s)")
' 2>/dev/null || ko "registre du Comité illisible"

echo "── SPAD Analyzer ──"
sudo -u spadapp $REPO/analyzer/venv/bin/python3 - <<'PY' 2>/dev/null || ko "Analyzer : contrôle impossible"
import os, sys
os.chdir('/var/www/spad-analyzer/analyzer'); sys.path.insert(0, '.')
import app as m
c = m.app.test_client()
def say(ok, msg): print(("  ✓ " if ok else "  ✗ ") + msg)
hub = c.get('/analyse-donnees').get_data(as_text=True)
say('Validation des données' in hub, "menu : « Validation des données » visible sans données chargées")
say('Base centrale (GDB)' in hub, "menu : « Base centrale (GDB) »")
r = c.get('/qualite/validation')
say(r.status_code == 302 and r.location.endswith('/analyse-donnees'), "validation sans données → renvoi vers le chargement des données")
say('existent-elles déjà' in c.get('/gdb').get_data(as_text=True), "page Base centrale")
j = c.post('/api/factum', json={'factum': 'PGT14_OS2_RC2_2__CIV_MS__1C1_Etude_CAP_Personnel_Sante_PEC_Tabac__20250900__ES'}).get_json()
say(j and j.get('valid'), "vérification du Factum")
say(c.get('/data/export.sav').status_code == 302, "export SPSS en place (sans données : renvoi)")
from modules import gdb
say(True, f"base centrale : {len(gdb.enquetes())} enquête(s) versée(s)")
PY

echo "── Sauvegardes ──"
LAST=$(ls -t /var/backups/spad/spad-*.tar.gz 2>/dev/null | head -1)
if [ -n "$LAST" ]; then
  AGE=$(( ($(date +%s) - $(stat -c %Y "$LAST")) / 3600 ))
  [ "$AGE" -le 26 ] && ok "dernière sauvegarde il y a ${AGE} h ($(basename "$LAST"))" || ko "dernière sauvegarde il y a ${AGE} h : le minuteur ne tourne pas ?"
else
  ko "aucune sauvegarde dans /var/backups/spad"
fi
check "dernière exécution du minuteur réussie" "[ \"\$(systemctl show spad-backup.service -p Result --value)\" = success ]"
REMOTE
)
echo "$REMOTE_OUT"
FAIL=$((FAIL + $(grep -c '✗' <<< "$REMOTE_OUT")))

echo "── Accès publics ──"
ANALYZER=https://spad-analyzer.afriklearn-consulting.com
STUDIO=https://studio.spad-analyzer.afriklearn-consulting.com
for url in $ANALYZER/login $STUDIO/manifest.webmanifest; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$url")
  if [ "$code" = 200 ]; then echo "  ✓ $url → 200"; else echo "  ✗ $url → $code"; FAIL=$((FAIL + 1)); fi
done
# Sans session, les pages et API protégées doivent renvoyer vers la connexion
for url in $ANALYZER/gdb $ANALYZER/qualite/validation $STUDIO/api/learned; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$url")
  if [ "$code" = 302 ] || [ "$code" = 401 ]; then echo "  ✓ $url refusé sans connexion ($code)"; else echo "  ✗ $url accessible sans connexion ($code)"; FAIL=$((FAIL + 1)); fi
done

echo
if [ "$FAIL" -eq 0 ]; then echo "✅ Audit sans anomalie."; else echo "⚠️  $FAIL point(s) à corriger."; fi
exit "$FAIL"
