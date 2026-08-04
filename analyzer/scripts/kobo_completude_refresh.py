"""
SPAD Analyzer — Actualisation automatique de la Complétude nationale

Script autonome (hors requête Flask/session), lancé périodiquement par un
timer systemd sur le serveur. Reproduit le calcul de /completude/calculer,
mais à partir d'un jeton KoboToolbox et d'une correspondance formulaires
configurés côté serveur (KOBO_API_TOKEN, modules/form_mapping.py) — pour que
la page Complétude nationale reste à jour sans qu'aucun utilisateur (rôle
Data ou Invité) n'ait à se connecter à KoboToolbox.

Écrit toujours dans le même fichier (completude_autorefresh.json) plutôt
qu'un nom horodaté à chaque exécution : évite d'accumuler des fichiers sur
le serveur, et _load_completude_cache() (app.py) prend de toute façon
automatiquement le plus récent des completude_*.json, qu'il vienne de ce
script ou d'un calcul manuel.

Usage : venv/bin/python scripts/kobo_completude_refresh.py
"""
import os
import sys
import json

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _ANALYZER_DIR)

from config import Config
from modules import reference_data as ref_data
from modules import completeness as cp
from modules import tendance
from modules import form_mapping
from modules.kobo_connector import validate_token, load_data as kobo_load_data

CACHE_FILENAME = 'completude_autorefresh.json'


def main():
    token = (os.environ.get('KOBO_API_TOKEN') or '').strip()
    if not token:
        print("KOBO_API_TOKEN non défini — rien à faire.")
        return 0

    instance_env = (os.environ.get('KOBO_INSTANCE') or '').strip() or None
    v = validate_token(token, custom_instance=instance_env)
    if not v.get('valid'):
        print(f"Jeton KoboToolbox invalide : {v.get('error', 'inconnu')}", file=sys.stderr)
        return 1
    instance = instance_env or v.get('instance')

    mapping = form_mapping.load()
    if not mapping:
        print("Aucune correspondance formulaire SPAD -> KoboToolbox configurée — rien à faire.")
        return 0

    ref = ref_data.load()
    form_dataframes = {}
    errors = []
    for code, uid in mapping.items():
        res = kobo_load_data(token, uid, instance=instance)
        if res.get('success'):
            form_dataframes[code] = res['df']
        else:
            errors.append(f"{code} : {res.get('error', 'erreur inconnue')}")

    if not form_dataframes:
        print("Échec sur tous les formulaires mappés, cache existant conservé : " + " · ".join(errors), file=sys.stderr)
        return 1

    national = cp.national_summary(ref, form_dataframes)
    cache = {
        'national':         national,
        'district':         cp.district_table(ref, form_dataframes),
        'region':           cp.region_table(ref, form_dataframes),
        'etablissement':    cp.etablissement_table(ref, form_dataframes),
        'enqueteur':        cp.enqueteur_table(ref, form_dataframes),
        'superviseur':      cp.superviseur_table(ref, form_dataframes),
        'anomalies_zero':   cp.all_anomalies_zero(ref, form_dataframes),
        'anomalies_excess': cp.all_anomalies_excess(ref, form_dataframes),
        'export':           cp.export_rows(ref, form_dataframes),
    }
    tendance.add_snapshot(national)

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    save_path = os.path.join(Config.UPLOAD_FOLDER, CACHE_FILENAME)
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)

    if errors:
        print(f"Complétude actualisée pour {len(form_dataframes)}/{len(mapping)} formulaire(s) — erreurs : " + " · ".join(errors))
    else:
        print(f"Complétude actualisée pour {len(form_dataframes)} formulaire(s).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
