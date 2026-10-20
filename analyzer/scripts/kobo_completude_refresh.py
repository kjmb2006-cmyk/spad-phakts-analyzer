"""
SPAD Analyzer — Actualisation automatique de la Complétude nationale

Script autonome (hors requête Flask/session), lancé toutes les 2 minutes
par un timer systemd sur le serveur (spad-kobo-refresh.timer). Reproduit
le calcul de /completude/calculer via modules/completude_cache.py (même
fonction build_cache(), pour ne jamais diverger de la route Flask), à
partir d'un jeton KoboToolbox et d'une correspondance formulaires
configurés côté serveur (KOBO_API_TOKEN, modules/form_mapping.py) — pour
que toutes les vues de Complétude restent à jour sans qu'aucun utilisateur
(rôle Data ou Invité) n'ait à cliquer sur « Calculer ».

Usage : venv/bin/python scripts/kobo_completude_refresh.py
"""
import os
import sys
import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _ANALYZER_DIR)

from config import Config
from modules import reference_data as ref_data
from modules import tendance
from modules import form_mapping
from modules import completude_cache
from modules.kobo_connector import validate_token


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
    cache, errors, n_ok = completude_cache.build_cache(ref, token, instance, mapping)
    if cache is None:
        print("Échec sur tous les formulaires mappés, cache existant conservé : " + " · ".join(errors), file=sys.stderr)
        return 1

    tendance.add_snapshot(cache['national'])
    computed_at = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    completude_cache.save_cache(cache, Config.UPLOAD_FOLDER, computed_at)

    if errors:
        print(f"Complétude actualisée pour {n_ok}/{len(mapping)} formulaire(s) — erreurs : " + " · ".join(errors))
    else:
        print(f"Complétude actualisée pour {n_ok} formulaire(s).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
