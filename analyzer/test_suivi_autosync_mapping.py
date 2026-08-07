#!/usr/bin/env python3
"""
Test script — la correspondance Complétude nationale se met à jour toute
seule quand un type est assigné à un formulaire dans Suivi multi-formulaires.

Contexte : jusqu'ici, ajouter un formulaire dans Suivi avec un type détecté
(préfixe ou IA) ne suffisait pas — il fallait ensuite aller le réassocier à
la main dans « Complétude nationale → Correspondance formulaire SPAD ↔
KoboToolbox », une étape redondante puisque Suivi connaît déjà l'association
(uid Kobo ↔ code SPAD). Vérifie que :
  - /suivi/add avec un form_type reconnu écrit directement dans
    form_mapping.py (plus besoin de « Enregistrer la correspondance »)
  - /suivi/add sans form_type (« Libre ») ne touche pas au mapping
  - /suivi/target (changer le type d'un formulaire déjà suivi) met aussi à
    jour le mapping
  - une correspondance déjà enregistrée pour un AUTRE code n'est jamais
    touchée par cette synchronisation (comportement additif, pas un reset)
"""
import os
os.environ['ANALYZER_PASSWORD_ADMIN'] = 'secret-admin-autosync'

import sys
sys.path.insert(0, '.')
from app import app
from modules import form_mapping
from modules import kobo_track

print("=" * 70)
print("TEST — Synchronisation automatique Suivi → correspondance Complétude")
print("=" * 70)

client = app.test_client()
client.post('/login', data={'password': 'secret-admin-autosync', 'access': 'admin'})
with client.session_transaction() as sess:
    sess['kobo_token'] = 'faux-token-test'
    sess['kobo_instance'] = 'kf.kobotoolbox.org'

_original_mapping = form_mapping.load()
_test_uids = ['uid_autosync_f5', 'uid_autosync_f6']
try:
    form_mapping.save({'F8': 'uid_f8_intact'})  # une correspondance existante, sans rapport

    # --- /suivi/add avec un type reconnu : doit écrire dans form_mapping ---
    r = client.post('/suivi/add', data={
        'uid': 'uid_autosync_f5', 'name': 'Formulaire test F5', 'form_type': 'F5',
    })
    assert r.get_json()['success'], r.get_json()
    mapping = form_mapping.load()
    assert mapping.get('F5') == 'uid_autosync_f5', mapping
    print("OK — /suivi/add avec form_type=F5 écrit automatiquement la correspondance")

    assert mapping.get('F8') == 'uid_f8_intact', "une correspondance existante sans rapport ne doit jamais être touchée"
    print("OK — une correspondance déjà enregistrée pour un autre code n'est pas affectée")

    # --- /suivi/add sans form_type (« Libre ») : ne doit rien écrire ---
    r = client.post('/suivi/add', data={'uid': 'uid_autosync_libre', 'name': 'Formulaire libre'})
    assert r.get_json()['success']
    mapping = form_mapping.load()
    assert 'F6' not in mapping or mapping.get('F6') != 'uid_autosync_libre'
    print("OK — ajouter un formulaire en type « Libre » ne touche pas la correspondance")

    # --- /suivi/target : changer le type d'un formulaire déjà suivi met aussi à jour le mapping ---
    r = client.post('/suivi/add', data={
        'uid': 'uid_autosync_f6', 'name': 'Formulaire test F6 (déposé sans type)',
    })
    assert r.get_json()['success']
    r = client.post('/suivi/target', data={'uid': 'uid_autosync_f6', 'form_type': 'F6'})
    assert r.get_json()['success'], r.get_json()
    mapping = form_mapping.load()
    assert mapping.get('F6') == 'uid_autosync_f6', mapping
    print("OK — /suivi/target (retyper un formulaire déjà suivi) met aussi à jour la correspondance")

finally:
    for uid in _test_uids + ['uid_autosync_libre']:
        kobo_track.remove(uid)
    form_mapping.save(_original_mapping)

print()
print("=" * 70)
print("TOUS LES TESTS DE SYNCHRONISATION SUIVI → COMPLÉTUDE SONT PASSÉS")
print("=" * 70)
