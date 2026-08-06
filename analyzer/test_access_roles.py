#!/usr/bin/env python3
"""
Test script — accès à trois rôles (modules/app.py::require_login()).

Contexte : Admin (gestion des comptes Data + journal d'activité), Data
(compte individuel, accès complet), Invité (mot de passe partagé, lecture
seule restreinte au tableau de bord Complétude nationale / par district &
établissement / performances superviseurs & enquêteurs). Le mot de passe
Data partagé (ANALYZER_PASSWORD) est retiré — voir test_accounts.py pour le
parcours complet inscription -> validation admin -> connexion, journalisé
dans modules/activity_log.py. Ici on se concentre sur la séparation des
périmètres entre les 3 rôles.

Doit impérativement définir ANALYZER_PASSWORD_ADMIN / ANALYZER_PASSWORD_INVITE
AVANT d'importer app (lues une seule fois, au chargement du module).

Chaque formulaire de connexion (Admin / Data / Invité) poste un champ caché
'access' : le mot de passe/compte saisi doit correspondre à CE champ
précisément, sinon refusé — pas de mélange entre rôles.
"""
import os
os.environ['ANALYZER_PASSWORD_ADMIN'] = 'secret-admin'
os.environ['ANALYZER_PASSWORD_INVITE'] = 'secret-invite'

import sys
sys.path.insert(0, '.')
from app import app
from modules import accounts

TEST_USER = '_test_user_access_roles_py'
TEST_PASS = 'motdepasse123'

print("=" * 70)
print("TEST — Accès à trois rôles (Admin / Data / Invité)")
print("=" * 70)

accounts.delete_user(TEST_USER)  # nettoyage défensif
accounts.create_pending(TEST_USER, TEST_PASS)
accounts.set_status(TEST_USER, accounts.STATUS_APPROVED)

client = app.test_client()

# --- Sans session : redirection vers /login sur n'importe quelle page ------
r = client.get('/completude', follow_redirects=False)
assert r.status_code == 302 and '/login' in r.headers['Location'], r.headers.get('Location')
print("OK — sans connexion, redirection vers /login")

# --- Mauvais mot de passe ----------------------------------------------------
r = client.post('/login', data={'password': 'faux', 'access': 'admin'})
assert r.status_code == 200 and 'incorrect' in r.get_data(as_text=True).lower()
print("OK — mot de passe incorrect refusé avec message d'erreur")

# --- Mot de passe croisé : chaque champ n'accepte que son propre rôle -------
r = client.post('/login', data={'password': 'secret-invite', 'access': 'admin'})
assert r.status_code == 200 and 'incorrect' in r.get_data(as_text=True).lower()
r = client.post('/login', data={'password': 'secret-admin', 'access': 'invite'})
assert r.status_code == 200 and 'incorrect' in r.get_data(as_text=True).lower()
print("OK — mot de passe Invité sur le champ Admin (et inversement) refusé")

# --- Rôle Data : accès complet (comportement historique) --------------------
with client.session_transaction() as sess:
    sess.clear()
r = client.post('/login', data={'access': 'data', 'username': TEST_USER, 'password': TEST_PASS}, follow_redirects=False)
assert r.status_code == 302
with client.session_transaction() as sess:
    assert sess.get('role') == 'data', sess.get('role')
r = client.get('/upload')
assert r.status_code == 200, r.status_code
r = client.get('/')
assert r.status_code == 200, r.status_code
print("OK — rôle 'data' : accès complet inchangé (upload, accueil, etc.)")

# Data n'a pas accès aux pages d'administration
r = client.get('/admin/users', follow_redirects=False)
assert r.status_code == 302 and r.headers['Location'].endswith('/')
r = client.get('/admin/activity', follow_redirects=False)
assert r.status_code == 302 and r.headers['Location'].endswith('/')
print("OK — rôle 'data' : pages d'administration bloquées")

client.get('/logout')

# --- Rôle Admin : accès complet + administration -----------------------------
with client.session_transaction() as sess:
    sess.clear()
r = client.post('/login', data={'password': 'secret-admin', 'access': 'admin'}, follow_redirects=False)
assert r.status_code == 302
with client.session_transaction() as sess:
    assert sess.get('role') == 'admin', sess.get('role')
r = client.get('/upload')
assert r.status_code == 200
r = client.get('/admin/users')
assert r.status_code == 200
r = client.get('/admin/activity')
assert r.status_code == 200
print("OK — rôle 'admin' : accès complet + écrans d'administration")

client.get('/logout')

# --- Rôle Invité : whitelist stricte -----------------------------------------
with client.session_transaction() as sess:
    sess.clear()
r = client.post('/login', data={'password': 'secret-invite', 'access': 'invite'}, follow_redirects=False)
assert r.status_code == 302 and r.headers['Location'].endswith('/completude'), r.headers.get('Location')
with client.session_transaction() as sess:
    assert sess.get('role') == 'invite', sess.get('role')
print("OK — mot de passe Invité reconnu, redirection directe vers /completude")

allowed = ['/completude', '/completude/districts', '/completude/superviseurs', '/completude/enqueteurs']
for path in allowed:
    r = client.get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code} (devrait être accessible au rôle invité)"
print(f"OK — rôle 'invite' : les {len(allowed)} pages du tableau de bord sont accessibles (200, pas de redirection)")

blocked = [
    '/', '/upload', '/analyse-donnees', '/multi-survey', '/projets', '/suivi',
    '/completude/regions', '/completude/anomalies', '/completude/graphiques',
    '/completude/export.csv', '/completude/export.xlsx', '/completude/export.docx',
    '/kobo/connect', '/admin/users', '/admin/activity',
]
for path in blocked:
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 302 and r.headers['Location'].endswith('/completude'), \
        f"{path} -> {r.status_code} {r.headers.get('Location')} (devrait rediriger vers /completude)"
print(f"OK — rôle 'invite' : les {len(blocked)} pages hors périmètre redirigent proprement vers /completude")

# Actions de modification (mapping/calcul) bloquées même en POST
r = client.post('/completude/mapper', follow_redirects=False)
assert r.status_code == 302 and r.headers['Location'].endswith('/completude')
r = client.post('/completude/calculer', follow_redirects=False)
assert r.status_code == 302 and r.headers['Location'].endswith('/completude')
print("OK — rôle 'invite' : actions de correspondance/calcul bloquées (POST)")

client.get('/logout')
with client.session_transaction() as sess:
    assert sess.get('authenticated') is None and sess.get('role') is None
print("OK — /logout efface bien authentification et rôle")

accounts.delete_user(TEST_USER)

print()
print("=" * 70)
print("TOUS LES TESTS D'ACCÈS À TROIS RÔLES SONT PASSÉS")
print("=" * 70)
