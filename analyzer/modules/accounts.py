"""
SPAD Analyzer — Comptes individuels du rôle 'data'

Avant : un seul mot de passe partagé (ANALYZER_PASSWORD) pour tout le monde
côté Data — impossible de savoir qui a fait quoi (voir activity_log.py).
Maintenant : chaque utilisateur Data a son propre compte (identifiant + mot
de passe), créé par auto-inscription (/register) mais inactif tant qu'un
administrateur ne l'a pas explicitement autorisé — comme demandé : « il doit
y avoir un volet où les data doivent s'inscrire avec leur propre identifiant ».

Persisté côté serveur en JSON (même idiome que modules/form_mapping.py et
modules/projets.py — pas de base de données), jamais commité (voir
.gitignore : analyzer/data/reference/*.local.json).
"""
import os
import re
import json
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_MODULE_DIR)
USERS_PATH = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'users.local.json')

STATUS_PENDING = 'pending'
STATUS_APPROVED = 'approved'
STATUS_BLOCKED = 'blocked'

_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_.\-]{3,32}$')


def _load():
    if not os.path.exists(USERS_PATH):
        return {}
    try:
        with open(USERS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save(users):
    os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
    with open(USERS_PATH, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def valid_username(username):
    return bool(_USERNAME_RE.match(username or ''))


def create_pending(username, password):
    """Crée un compte Data en attente de validation. Renvoie (ok, erreur)."""
    username = (username or '').strip()
    if not valid_username(username):
        return False, "Identifiant invalide (3 à 32 caractères : lettres, chiffres, . _ -)."
    if not password or len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères."
    users = _load()
    key = username.lower()
    if key in users:
        return False, "Cet identifiant est déjà utilisé."
    users[key] = {
        'username': username,
        'password_hash': generate_password_hash(password),
        'status': STATUS_PENDING,
        'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    _save(users)
    return True, None


def verify_login(username, password):
    """Vérifie identifiant/mot de passe. Renvoie (statut, username_normalise) :
    statut est 'approved' (connexion autorisée), 'pending', 'blocked', ou
    None (identifiant ou mot de passe incorrect — même message que 'inconnu'
    pour ne pas révéler quels identifiants existent)."""
    users = _load()
    entry = users.get((username or '').strip().lower())
    if not entry or not check_password_hash(entry['password_hash'], password or ''):
        return None, None
    return entry['status'], entry['username']


def list_users():
    """Trié : en attente d'abord (ce qui demande une action de l'admin), puis
    approuvés, puis bloqués — chaque groupe par ordre alphabétique."""
    order = {STATUS_PENDING: 0, STATUS_APPROVED: 1, STATUS_BLOCKED: 2}
    users = list(_load().values())
    users.sort(key=lambda u: (order.get(u['status'], 9), u['username'].lower()))
    return users


def set_status(username, status):
    if status not in (STATUS_PENDING, STATUS_APPROVED, STATUS_BLOCKED):
        return False
    users = _load()
    key = (username or '').strip().lower()
    if key not in users:
        return False
    users[key]['status'] = status
    _save(users)
    return True


def delete_user(username):
    users = _load()
    key = (username or '').strip().lower()
    if key not in users:
        return False
    del users[key]
    _save(users)
    return True
