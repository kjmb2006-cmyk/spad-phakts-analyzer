#!/usr/bin/env python3
"""
Test script — hygiène du journal d'activité (modules/activity_log.py,
app.py::log_data_activity()/require_login()).

Contexte (retour terrain) : le journal affichait des dizaines d'entrées
« ? » comme utilisateur, une toutes les 10 secondes sur /suivi/status —
noyant les vraies actions sous du bruit et défaisant l'objectif même du
journal (« qui a modifié la correspondance de formulaires »). Deux causes
combinées :
  1. une session 'data' sans identifiant (cookie antérieur aux comptes
     individuels, ou corrompu) était acceptée et journalisée sous '?' au
     lieu d'être invalidée ;
  2. /suivi/status est sondé automatiquement toutes les 10s par le JS de la
     page (setInterval), pas une action de l'utilisateur — journalisé quand
     même jusqu'ici.
Vérifie que :
  - une session 'data' sans username est déconnectée de force (pas de '?')
  - /suivi/status n'est jamais journalisé, même pour une session 'data'
    valide
  - une action réelle (POST /suivi/add) reste bien journalisée
  - /admin/activity/reset vide le journal, réservé au rôle admin
"""
import os
os.environ['ANALYZER_PASSWORD_ADMIN'] = 'secret-admin-activity-hygiene'

import sys
sys.path.insert(0, '.')
from app import app
from modules import accounts
from modules import activity_log
from modules import kobo_track

print("=" * 70)
print("TEST — Hygiène du journal d'activité")
print("=" * 70)

# Ce test vide le journal réel (/admin/activity/reset) — sauvegarde/
# restauration du fichier, comme les autres tests le font déjà pour
# form_mapping.py/forms_registry.py (jamais altérer un état réel de prod).
_had_log = os.path.exists(activity_log.LOG_PATH)
_log_backup = None
if _had_log:
    with open(activity_log.LOG_PATH, 'r', encoding='utf-8') as f:
        _log_backup = f.read()

TEST_USER = '_test_activity_hygiene'
TEST_PASS = 'motdepasse123'
accounts.delete_user(TEST_USER)
accounts.create_pending(TEST_USER, TEST_PASS)
accounts.set_status(TEST_USER, accounts.STATUS_APPROVED)

client = app.test_client()
try:
    # --- Session 'data' sans username : déconnexion forcée, pas de '?' ---
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['role'] = 'data'
        # username volontairement absent — simule un cookie antérieur aux
        # comptes individuels (ancien mot de passe Data partagé)
    r = client.get('/suivi/status', follow_redirects=False)
    assert r.status_code == 302 and '/login' in r.headers['Location'], r.headers.get('Location')
    with client.session_transaction() as sess:
        assert not sess.get('authenticated'), "la session invalide doit être entièrement effacée"
    print("OK — une session 'data' sans identifiant est déconnectée de force (pas de '?' journalisé)")

    # --- Connexion réelle : /suivi/status ne doit jamais être journalisé ---
    client.post('/login', data={'access': 'data', 'username': TEST_USER, 'password': TEST_PASS})
    n_avant = len(activity_log.list_events(username=TEST_USER))
    for _ in range(3):
        client.get('/suivi/status')
    n_apres_poll = len(activity_log.list_events(username=TEST_USER))
    assert n_apres_poll == n_avant, f"le sondage /suivi/status ne doit jamais être journalisé ({n_avant} -> {n_apres_poll})"
    print("OK — /suivi/status (sondage automatique JS) n'est jamais journalisé")

    # --- Une vraie action reste journalisée ---
    client.post('/suivi/target', data={'uid': 'uid-inexistant-test'})  # 400 attendu, mais la requête elle-même doit être journalisée
    n_apres_action = len(activity_log.list_events(username=TEST_USER))
    assert n_apres_action == n_avant + 1, f"une action réelle doit rester journalisée ({n_avant} -> {n_apres_action})"
    print("OK — une action réelle (POST /suivi/target) reste journalisée normalement")

    events = activity_log.list_events(username=TEST_USER)
    assert all(e['username'] == TEST_USER for e in events), "aucune entrée '?' ne doit apparaître pour une session valide"
    print("OK — toutes les entrées journalisées portent le vrai identifiant, jamais '?'")

finally:
    client.get('/logout')
    accounts.delete_user(TEST_USER)

try:
    # --- /admin/activity/reset vide le journal, réservé à l'admin ------------
    client2 = app.test_client()
    activity_log.record('quelquun', 'data', 'GET', '/completude')
    assert len(activity_log.list_events()) > 0

    r = client2.post('/admin/activity/reset', follow_redirects=False)
    assert r.status_code == 302 and '/login' in r.headers['Location'], "réservé à l'admin, refusé sans connexion"
    assert len(activity_log.list_events()) > 0, "le journal ne doit pas être vidé par un appel refusé"
    print("OK — /admin/activity/reset est réservé au rôle admin")

    client2.post('/login', data={'password': 'secret-admin-activity-hygiene', 'access': 'admin'})
    r = client2.post('/admin/activity/reset', follow_redirects=True)
    assert r.status_code == 200
    assert activity_log.list_events() == [], "le journal doit être vide après réinitialisation"
    print("OK — /admin/activity/reset vide bien le journal (rôle admin)")
finally:
    if _had_log:
        with open(activity_log.LOG_PATH, 'w', encoding='utf-8') as f:
            f.write(_log_backup)
    elif os.path.exists(activity_log.LOG_PATH):
        os.remove(activity_log.LOG_PATH)

print()
print("=" * 70)
print("TOUS LES TESTS D'HYGIÈNE DU JOURNAL D'ACTIVITÉ SONT PASSÉS")
print("=" * 70)
