"""
SPAD Analyzer — Correspondance formulaires SPAD -> formulaires KoboToolbox

Persistée côté serveur (SQLite), pas en session : cette correspondance doit
rester la même pour tout le monde (rôle 'data' comme 'invite'), et surtout
pour la tâche de fond d'actualisation automatique (voir
scripts/kobo_completude_refresh.py) qui tourne dans un AUTRE process, sans
navigateur ni session — un fichier partagé relu/réécrit en entier à chaque
appel (l'ancien json.load()/json.dump()) n'offrait aucune garantie contre
une lecture au milieu d'une écriture par ce second process. SQLite (mode
WAL) donne cette garantie pour le prix d'aucune dépendance supplémentaire
(sqlite3 est dans la bibliothèque standard).

Les formulaires Kobo changent au fil des cycles de collecte (nouveau projet
Kobo déployé pour une nouvelle vague) — cette correspondance reste modifiable
à tout moment depuis l'écran « Complétude nationale », sans redéploiement.

Migration : au tout premier accès après mise à jour, si spad.db n'a pas
encore de données mais que l'ancien spad_form_mapping.local.json existe,
son contenu est importé automatiquement — aucune étape manuelle. L'ancien
fichier n'est jamais supprimé (filet de sécurité pour revenir en arrière).
"""
import os
import json
import sqlite3

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_MODULE_DIR)
DB_PATH = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'spad.db')
_LEGACY_JSON_PATH = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'spad_form_mapping.local.json')


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    # Attend plutôt que d'échouer immédiatement avec "database is locked" si
    # un autre process (scripts/kobo_completude_refresh.py, un autre thread
    # gunicorn) détient une écriture au même instant.
    conn.execute('PRAGMA busy_timeout=30000')
    conn.execute('''CREATE TABLE IF NOT EXISTS form_mapping (
        code     TEXT PRIMARY KEY,
        kobo_uid TEXT NOT NULL
    )''')
    _bootstrap_from_legacy_json(conn)
    return conn


def _bootstrap_from_legacy_json(conn):
    cur = conn.execute('SELECT COUNT(*) FROM form_mapping')
    if cur.fetchone()[0] > 0 or not os.path.exists(_LEGACY_JSON_PATH):
        return
    try:
        with open(_LEGACY_JSON_PATH, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
    except Exception:
        return
    if not mapping:
        return
    with conn:
        conn.executemany('INSERT OR REPLACE INTO form_mapping (code, kobo_uid) VALUES (?, ?)',
                          list(mapping.items()))


def load():
    conn = _connect()
    try:
        rows = conn.execute('SELECT code, kobo_uid FROM form_mapping').fetchall()
        return {code: uid for code, uid in rows}
    finally:
        conn.close()


def save(mapping):
    conn = _connect()
    try:
        with conn:
            conn.execute('DELETE FROM form_mapping')
            conn.executemany('INSERT INTO form_mapping (code, kobo_uid) VALUES (?, ?)',
                              list(mapping.items()))
    finally:
        conn.close()
