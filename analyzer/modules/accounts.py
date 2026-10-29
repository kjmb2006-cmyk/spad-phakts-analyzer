"""
SPAD Analyzer — Comptes individuels du rôle 'data'

Avant : un seul mot de passe partagé (ANALYZER_PASSWORD) pour tout le monde
côté Data — impossible de savoir qui a fait quoi (voir activity_log.py).
Maintenant : chaque utilisateur Data a son propre compte (identifiant + mot
de passe), créé par auto-inscription (/register) mais inactif tant qu'un
administrateur ne l'a pas explicitement autorisé — comme demandé : « il doit
y avoir un volet où les data doivent s'inscrire avec leur propre identifiant ».

Persisté côté serveur en SQLite (même base que modules/form_mapping.py —
voir DB_PATH), jamais commité (voir .gitignore : analyzer/data/reference/
*.local.json, *.db). La contrainte PRIMARY KEY sur username_key règle un
vrai risque qu'avait l'ancien stockage JSON : create_pending() faisait
load -> vérifie l'unicité -> save sans aucun verrou — deux inscriptions
concurrentes avec le même identifiant pouvaient toutes deux passer le test
avant l'écriture, la seconde écrasant silencieusement la première. Avec une
contrainte d'unicité en base, la seconde échoue proprement (IntegrityError)
au lieu d'écraser — l'unicité et l'écriture ne sont plus deux étapes
séparées mais une seule opération atomique.

username_key (clé de recherche, toujours en minuscules) est distinct de
username (valeur d'affichage, casse d'origine telle que saisie à
l'inscription) — reproduit le comportement JSON d'origine, où la clé du
dict était username.lower() mais le champ 'username' à l'intérieur gardait
la casse saisie (list_users() l'affichait ainsi).

Migration : au tout premier accès après mise à jour, si spad.db n'a pas
encore de comptes mais que l'ancien users.local.json existe, son contenu
est importé automatiquement. L'ancien fichier n'est jamais supprimé.
"""
import os
import re
import json
import sqlite3
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_MODULE_DIR)
DB_PATH = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'spad.db')
_LEGACY_JSON_PATH = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'users.local.json')

STATUS_PENDING = 'pending'
STATUS_APPROVED = 'approved'
STATUS_BLOCKED = 'blocked'

_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_.\-]{3,32}$')


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    # Attend plutôt que d'échouer immédiatement avec "database is locked" si
    # un autre process (scripts/kobo_completude_refresh.py, un autre thread
    # gunicorn) détient une écriture au même instant — rare mais possible
    # juste après un déploiement, voir migrate_to_sqlite.py.
    conn.execute('PRAGMA busy_timeout=30000')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        username_key  TEXT PRIMARY KEY,
        username      TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        status        TEXT NOT NULL,
        created_at    TEXT NOT NULL
    )''')
    _bootstrap_from_legacy_json(conn)
    return conn


def _bootstrap_from_legacy_json(conn):
    cur = conn.execute('SELECT COUNT(*) FROM users')
    if cur.fetchone()[0] > 0 or not os.path.exists(_LEGACY_JSON_PATH):
        return
    try:
        with open(_LEGACY_JSON_PATH, 'r', encoding='utf-8') as f:
            users = json.load(f)
    except Exception:
        return
    if not users:
        return
    rows = [(key, u['username'], u['password_hash'], u['status'], u['created_at'])
            for key, u in users.items()]
    with conn:
        conn.executemany(
            '''INSERT OR REPLACE INTO users (username_key, username, password_hash, status, created_at)
               VALUES (?, ?, ?, ?, ?)''',
            rows)


def valid_username(username):
    return bool(_USERNAME_RE.match(username or ''))


def create_pending(username, password):
    """Crée un compte Data en attente de validation. Renvoie (ok, erreur)."""
    username = (username or '').strip()
    if not valid_username(username):
        return False, "Identifiant invalide (3 à 32 caractères : lettres, chiffres, . _ -)."
    if not password or len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères."
    conn = _connect()
    try:
        with conn:
            conn.execute(
                '''INSERT INTO users (username_key, username, password_hash, status, created_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (username.lower(), username, generate_password_hash(password), STATUS_PENDING,
                 datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    except sqlite3.IntegrityError:
        # Contrainte PRIMARY KEY sur username_key : identifiant déjà pris —
        # y compris par une inscription concurrente qui vient de gagner la
        # course (voir docstring).
        return False, "Cet identifiant est déjà utilisé."
    finally:
        conn.close()
    return True, None


def verify_login(username, password):
    """Vérifie identifiant/mot de passe. Renvoie (statut, username_normalise) :
    statut est 'approved' (connexion autorisée), 'pending', 'blocked', ou
    None (identifiant ou mot de passe incorrect — même message que 'inconnu'
    pour ne pas révéler quels identifiants existent)."""
    conn = _connect()
    try:
        row = conn.execute(
            'SELECT username, password_hash, status FROM users WHERE username_key = ?',
            ((username or '').strip().lower(),)).fetchone()
    finally:
        conn.close()
    if not row or not check_password_hash(row[1], password or ''):
        return None, None
    return row[2], row[0]


def list_users():
    """Trié : en attente d'abord (ce qui demande une action de l'admin), puis
    approuvés, puis bloqués — chaque groupe par ordre alphabétique."""
    conn = _connect()
    try:
        rows = conn.execute('SELECT username, password_hash, status, created_at FROM users').fetchall()
    finally:
        conn.close()
    users = [{'username': u, 'password_hash': h, 'status': s, 'created_at': c} for u, h, s, c in rows]
    order = {STATUS_PENDING: 0, STATUS_APPROVED: 1, STATUS_BLOCKED: 2}
    users.sort(key=lambda u: (order.get(u['status'], 9), u['username'].lower()))
    return users


def set_status(username, status):
    if status not in (STATUS_PENDING, STATUS_APPROVED, STATUS_BLOCKED):
        return False
    key = (username or '').strip().lower()
    conn = _connect()
    try:
        with conn:
            cur = conn.execute('UPDATE users SET status = ? WHERE username_key = ?', (status, key))
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_user(username):
    key = (username or '').strip().lower()
    conn = _connect()
    try:
        with conn:
            cur = conn.execute('DELETE FROM users WHERE username_key = ?', (key,))
        return cur.rowcount > 0
    finally:
        conn.close()
