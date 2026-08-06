#!/usr/bin/env python3
"""
Test script — comptes individuels Data + rôle Administrateur
(modules/accounts.py, modules/activity_log.py, app.py).

Contexte : le mot de passe Data partagé (ANALYZER_PASSWORD) est retiré —
chaque utilisateur Data a désormais son propre compte, créé par
auto-inscription (/register) mais inactif tant qu'un administrateur ne l'a
pas explicitement autorisé (/admin/users). Chaque action d'un compte Data
est journalisée (modules/activity_log.py), consultable par l'admin
(/admin/activity) — pour répondre à « toute modification ou toute
utilisation puisse être vue et notifiée à l'administrateur ».

Doit impérativement définir ANALYZER_PASSWORD_ADMIN / ANALYZER_PASSWORD_INVITE
AVANT d'importer app (lues une seule fois, au chargement du module). Crée un
utilisateur de test bien identifié et le supprime à la fin (ne pollue pas
data/reference/users.local.json).
"""
import os
os.environ['ANALYZER_PASSWORD_ADMIN'] = 'secret-admin'
os.environ['ANALYZER_PASSWORD_INVITE'] = 'secret-invite'

import sys
sys.path.insert(0, '.')
from app import app
from modules import accounts, activity_log

TEST_USER = '_test_user_accounts_py'
TEST_PASS = 'motdepasse123'

print("=" * 70)
print("TEST — Comptes Data individuels + rôle Administrateur")
print("=" * 70)

# Nettoyage défensif (si un run précédent a échoué avant la fin)
accounts.delete_user(TEST_USER)

client = app.test_client()

# --- Inscription publique, accessible sans connexion -------------------------
r = client.get('/register')
assert r.status_code == 200, r.status_code
r = client.post('/register', data={'password': TEST_PASS, 'confirm': 'different'})
assert 'correspondent' in r.get_data(as_text=True).lower()
r = client.post('/register', data={'username': TEST_USER, 'password': TEST_PASS, 'confirm': TEST_PASS})
assert r.status_code == 200 and 'attente' in r.get_data(as_text=True).lower()
print("OK — inscription publique crée un compte 'pending' (mots de passe différents rejetés)")

# Inscription en double refusée
r = client.post('/register', data={'username': TEST_USER, 'password': TEST_PASS, 'confirm': TEST_PASS})
assert 'déjà utilisé' in r.get_data(as_text=True).lower()
print("OK — identifiant déjà pris refusé à l'inscription")

# --- Connexion refusée tant que le compte est en attente ---------------------
r = client.post('/login', data={'access': 'data', 'username': TEST_USER, 'password': TEST_PASS})
assert r.status_code == 200 and 'attente' in r.get_data(as_text=True).lower()
with client.session_transaction() as sess:
    assert sess.get('authenticated') is None
print("OK — connexion refusée tant que le compte n'est pas autorisé")

# --- L'admin autorise le compte -----------------------------------------------
with client.session_transaction() as sess:
    sess.clear()
r = client.post('/login', data={'access': 'admin', 'password': 'secret-admin'}, follow_redirects=False)
assert r.status_code == 302
with client.session_transaction() as sess:
    assert sess.get('role') == 'admin', sess.get('role')

r = client.get('/admin/users')
assert r.status_code == 200 and TEST_USER in r.get_data(as_text=True)
r = client.post(f'/admin/users/{TEST_USER}/approve', follow_redirects=False)
assert r.status_code == 302
users = accounts.list_users()
assert next(u for u in users if u['username'] == TEST_USER)['status'] == accounts.STATUS_APPROVED
print("OK — l'admin voit le compte en attente et peut l'autoriser")

client.get('/logout')

# --- Connexion Data possible une fois autorisé, journalisée ------------------
with client.session_transaction() as sess:
    sess.clear()
r = client.post('/login', data={'access': 'data', 'username': TEST_USER, 'password': TEST_PASS}, follow_redirects=False)
assert r.status_code == 302, r.status_code
with client.session_transaction() as sess:
    assert sess.get('role') == 'data' and sess.get('username') == TEST_USER
r = client.get('/upload')
assert r.status_code == 200
print("OK — connexion Data acceptée une fois le compte autorisé")

events = activity_log.list_events(username=TEST_USER)
assert any(e['path'] == '/upload' for e in events), events
print(f"OK — les actions de {TEST_USER} apparaissent dans le journal d'activité ({len(events)} événement(s))")

client.get('/logout')

# --- L'admin bloque le compte : connexion refusée à nouveau ------------------
with client.session_transaction() as sess:
    sess.clear()
client.post('/login', data={'access': 'admin', 'password': 'secret-admin'})
client.post(f'/admin/users/{TEST_USER}/block')
users = accounts.list_users()
assert next(u for u in users if u['username'] == TEST_USER)['status'] == accounts.STATUS_BLOCKED
client.get('/logout')

with client.session_transaction() as sess:
    sess.clear()
r = client.post('/login', data={'access': 'data', 'username': TEST_USER, 'password': TEST_PASS})
assert r.status_code == 200 and 'bloqué' in r.get_data(as_text=True).lower()
print("OK — compte bloqué : connexion refusée avec message explicite")

# --- Journal et gestion des comptes réservés à l'admin ------------------------
with client.session_transaction() as sess:
    sess.clear()
r = client.get('/admin/users', follow_redirects=False)
assert r.status_code == 302 and '/login' in r.headers['Location']
print("OK — /admin/users inaccessible sans connexion")

# Nettoyage
accounts.delete_user(TEST_USER)
assert not any(u['username'] == TEST_USER for u in accounts.list_users())
print("OK — utilisateur de test supprimé (pas de pollution de users.local.json)")

print()
print("=" * 70)
print("TOUS LES TESTS DE COMPTES/ADMINISTRATION SONT PASSÉS")
print("=" * 70)
