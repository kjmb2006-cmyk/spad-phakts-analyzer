#!/usr/bin/env python3
"""
Test script — accès à deux rôles (modules/app.py::require_login()).

Contexte : demande d'un accès « Invité » en ligne, restreint à la lecture
seule du tableau de bord (Complétude nationale / par district & établissement
/ performances superviseurs & enquêteurs), sans export ni accès aux autres
modules — par opposition au rôle « Data » (accès complet, comportement
historique de l'app). Les deux rôles partagent le même champ de mot de passe
à l'écran de connexion ; c'est la valeur saisie qui détermine le rôle.

Doit impérativement définir ANALYZER_PASSWORD / ANALYZER_PASSWORD_INVITE
AVANT d'importer app (lus une seule fois, au chargement du module).

Depuis l'écran de connexion à deux champs distincts (Data / Invité), chaque
formulaire poste aussi un champ caché 'access' ('data' ou 'invite') : le
mot de passe saisi doit correspondre à CE champ précisément, sinon refusé
— même s'il correspond à l'autre rôle (évite la confusion : avant, saisir
le mot de passe Invité dans le champ Data donnait quand même accès).
"""
import os
os.environ['ANALYZER_PASSWORD'] = 'secret-data'
os.environ['ANALYZER_PASSWORD_INVITE'] = 'secret-invite'

import sys
sys.path.insert(0, '.')
from app import app

print("=" * 70)
print("TEST — Accès à deux rôles (Data / Invité)")
print("=" * 70)

client = app.test_client()

# --- Sans session : redirection vers /login sur n'importe quelle page ------
r = client.get('/completude', follow_redirects=False)
assert r.status_code == 302 and '/login' in r.headers['Location'], r.headers.get('Location')
print("OK — sans connexion, redirection vers /login")

# --- Mauvais mot de passe ----------------------------------------------------
r = client.post('/login', data={'password': 'faux', 'access': 'data'})
assert r.status_code == 200 and 'incorrect' in r.get_data(as_text=True).lower()
print("OK — mot de passe incorrect refusé avec message d'erreur")

# --- Mot de passe croisé : chaque champ n'accepte que son propre rôle -------
r = client.post('/login', data={'password': 'secret-invite', 'access': 'data'})
assert r.status_code == 200 and 'incorrect' in r.get_data(as_text=True).lower()
r = client.post('/login', data={'password': 'secret-data', 'access': 'invite'})
assert r.status_code == 200 and 'incorrect' in r.get_data(as_text=True).lower()
print("OK — mot de passe Invité sur le champ Data (et inversement) refusé")

# --- Rôle Data : accès complet (comportement historique) --------------------
with client.session_transaction() as sess:
    sess.clear()
r = client.post('/login', data={'password': 'secret-data', 'access': 'data'}, follow_redirects=False)
assert r.status_code == 302
with client.session_transaction() as sess:
    assert sess.get('role') == 'data', sess.get('role')
r = client.get('/upload')
assert r.status_code == 200, r.status_code
r = client.get('/')
assert r.status_code == 200, r.status_code
print("OK — rôle 'data' : accès complet inchangé (upload, accueil, etc.)")

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
    '/kobo/connect',
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

print()
print("=" * 70)
print("TOUS LES TESTS D'ACCÈS À DEUX RÔLES SONT PASSÉS")
print("=" * 70)
