"""
SPAD Analyzer — Correspondance formulaires SPAD -> formulaires KoboToolbox

Persistée côté serveur (fichier), pas en session : cette correspondance doit
rester la même pour tout le monde (rôle 'data' comme 'invite'), et surtout
pour la tâche de fond d'actualisation automatique (voir
scripts/kobo_completude_refresh.py) qui tourne sans navigateur ni session.

Les formulaires Kobo changent au fil des cycles de collecte (nouveau projet
Kobo déployé pour une nouvelle vague) — ce fichier reste modifiable à tout
moment depuis l'écran « Complétude nationale », sans redéploiement.
"""
import os
import json

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_MODULE_DIR)
MAPPING_PATH = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'spad_form_mapping.local.json')


def load():
    if not os.path.exists(MAPPING_PATH):
        return {}
    try:
        with open(MAPPING_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save(mapping):
    os.makedirs(os.path.dirname(MAPPING_PATH), exist_ok=True)
    with open(MAPPING_PATH, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
