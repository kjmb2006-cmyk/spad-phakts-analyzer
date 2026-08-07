"""
SPAD Analyzer — Journal d'activité des utilisateurs Data

Répond à la demande : « toute modification ou toute utilisation puisse être
vue et notifiée à l'administrateur ». Journalise chaque requête effectuée
par un utilisateur du rôle 'data' (identifiant, méthode, chemin) — jamais
le rôle 'invite' (lecture seule, rien à auditer) ni 'admin'.

Fichier .jsonl (une ligne JSON par événement, append-only) plutôt qu'un
JSON unique : écriture atomique par nature (un `write` par ligne, jamais de
réécriture complète du fichier), pas de risque de corruption si deux
requêtes journalisent au même instant.
"""
import os
import json
import datetime

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_MODULE_DIR)
LOG_PATH = os.path.join(_ANALYZER_DIR, 'data', 'activity_log.jsonl')

# Au-delà de ce nombre de lignes, les plus anciennes sont purgées au prochain
# enregistrement — évite une croissance illimitée sur un serveur qui tourne
# des mois (voir DEPLOIEMENT_RENDER.md, disque non persistant de toute façon
# sur le plan gratuit, mais utile aussi en usage desktop local prolongé).
MAX_EVENTS = 20000


def record(username, role, method, path):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    event = {
        'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'username': username,
        'role': role,
        'method': method,
        'path': path,
    }
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass  # journalisation best-effort — ne doit jamais casser la requête réelle


def list_events(limit=500, username=None):
    """Les `limit` événements les plus récents, plus récent en premier.
    Filtre optionnel par utilisateur (pour l'écran détail d'un compte)."""
    if not os.path.exists(LOG_PATH):
        return []
    events = []
    try:
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if username and e.get('username', '').lower() != username.lower():
                    continue
                events.append(e)
    except Exception:
        return []
    events.reverse()
    return events[:limit]


def clear():
    """Vide le journal — action volontaire de l'administrateur (ex. après
    une pollution du journal par du bruit non significatif, voir la
    correction dans app.py qui exclut désormais /suivi/status)."""
    try:
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)
    except Exception:
        pass


def _prune_if_needed():
    """Purge les événements les plus anciens si le fichier dépasse MAX_EVENTS
    lignes — appelé occasionnellement (pas à chaque écriture, trop coûteux)."""
    if not os.path.exists(LOG_PATH):
        return
    try:
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if len(lines) > MAX_EVENTS:
            with open(LOG_PATH, 'w', encoding='utf-8') as f:
                f.writelines(lines[-MAX_EVENTS:])
    except Exception:
        pass
