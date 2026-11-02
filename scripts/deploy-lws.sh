#!/usr/bin/env bash
#
# Déploiement 1-clic sur le VPS LWS : pull GitHub, installe les dépendances
# si besoin, redémarre les deux services, puis vérifie par des tests de
# fumée que tout répond correctement avant de considérer le déploiement
# réussi. Sans le smoke test, un "1-clic" peut aussi casser la prod en un
# clic sans qu'on s'en aperçoive (cf. session du 2026-08-26/27).
#
# Usage : ./scripts/deploy-lws.sh
#
set -euo pipefail

SSH_KEY="$HOME/.ssh/spad_lws_vps"
VPS_HOST="root@185.98.137.200"
REPO_DIR="/var/www/spad-analyzer"
MAIN_URL="https://spad-analyzer.afriklearn-consulting.com/login"
STUDIO_URL="https://studio.spad-analyzer.afriklearn-consulting.com/manifest.webmanifest"

ssh_run() { ssh -i "$SSH_KEY" -o ConnectTimeout=10 "$VPS_HOST" "$@"; }

echo "── Vérification : des commits locaux ne sont-ils pas encore poussés ? ──"
LOCAL_AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "?")
if [ "$LOCAL_AHEAD" != "0" ] && [ "$LOCAL_AHEAD" != "?" ]; then
  echo "⚠️  $LOCAL_AHEAD commit(s) local(aux) non poussé(s) sur origin/main — le VPS déploiera l'état ACTUEL de GitHub, pas votre disque local."
  echo "    Faites 'git push' d'abord si vous vouliez inclure ces commits."
fi

echo
echo "── 1/4 · git pull sur le VPS ──"
PULL_OUTPUT=$(ssh_run "cd $REPO_DIR && git pull origin main")
echo "$PULL_OUTPUT"

# package.json / package-lock.json réécrits avec le contenu EXACT de HEAD après le pull : constaté
# le 03/11/2026, un ancien `npm install` (avant le passage à `npm ci` ci-dessous) avait laissé
# package-lock.json modifié sur le disque du serveur ; comme le pull qui a suivi ne touchait pas
# ce fichier, il restait un fast-forward "propre" sans corriger cette dérive — et `npm ci`, qui
# lit le fichier tel quel SUR LE DISQUE (pas ce que git a committé), réinstallait alors depuis ce
# lockfile dérivé, rechargeant le minimatch vulnérable. `git show HEAD:<chemin>` écrit le contenu
# committé sans rien "annuler" (jamais checkout/reset/clean) : seuls ces deux fichiers précis sont
# concernés, jamais les .local.json de données (ignorés par git, intacts).
ssh_run "cd $REPO_DIR && git show HEAD:package.json > package.json && git show HEAD:package-lock.json > package-lock.json"

if echo "$PULL_OUTPUT" | grep -q "Already up to date."; then
  echo "→ Rien de nouveau à déployer."
fi

echo
echo "── 2/4 · Dépendances (npm + pip, rapide si rien n'a changé) ──"
# npm ci, pas npm install : installation STRICTEMENT à partir du lockfile (celui qu'on vient de
# remettre à jour ci-dessus), jamais de résolution incrémentale qui le réécrirait. npm ci supprime
# et réinstalle node_modules à chaque fois : aussi rapide que npm install quand rien n'a changé,
# mais jamais de dérive silencieuse.
ssh_run "cd $REPO_DIR && npm ci --omit=dev 2>&1 | tail -5"
ssh_run "cd $REPO_DIR/analyzer && venv/bin/pip install -q -r requirements.txt"

echo
echo "── 3/4 · Redémarrage des services ──"
ssh_run "systemctl restart spad-analyzer.service phakts-studio.service"
sleep 3
NODE_STATE=$(ssh_run "systemctl is-active phakts-studio.service" || echo "inactive")
FLASK_STATE=$(ssh_run "systemctl is-active spad-analyzer.service" || echo "inactive")
echo "  phakts-studio.service : $NODE_STATE"
echo "  spad-analyzer.service : $FLASK_STATE"

if [ "$NODE_STATE" != "active" ] || [ "$FLASK_STATE" != "active" ]; then
  echo
  echo "❌ ÉCHEC : un service ne redémarre pas correctement. Journaux récents :"
  ssh_run "journalctl -u spad-analyzer.service -u phakts-studio.service -n 30 --no-pager"
  exit 1
fi

echo
echo "── 4/4 · Tests de fumée (public, via nginx) ──"
MAIN_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "$MAIN_URL")
STUDIO_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "$STUDIO_URL")
echo "  $MAIN_URL → $MAIN_STATUS"
echo "  $STUDIO_URL → $STUDIO_STATUS"

if [ "$MAIN_STATUS" != "200" ] || [ "$STUDIO_STATUS" != "200" ]; then
  echo
  echo "❌ ÉCHEC : au moins une URL publique ne répond pas correctement (attendu 200)."
  exit 1
fi

echo
echo "✅ Déploiement réussi et vérifié."
