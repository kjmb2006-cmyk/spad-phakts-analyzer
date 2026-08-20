#!/usr/bin/env python3
"""
Test script — « Effacer les données » (/data/reset) ne doit purger que les
fichiers de LA session courante, jamais le cache de complétude partagé.

Contexte (revue de la mise à jour « SPAD AI Copilot ») : le commit
b148c1b avait ajouté une boucle qui supprimait TOUS les fichiers
completude_*.json du dossier UPLOAD_FOLDER partagé, quelle que soit la
session qui a cliqué « Effacer les données ». Avec plusieurs comptes Data
actifs simultanément (modules/accounts.py), un seul utilisateur cliquant
sur ce bouton effaçait le calcul de complétude de TOUT LE MONDE, y compris
celui du script d'actualisation automatique
(scripts/kobo_completude_refresh.py). Vérifie que /data/reset ne supprime
que le fichier de complétude de la session courante, et laisse intact un
fichier de complétude appartenant à une AUTRE session.
"""
import os
import sys
import json
sys.path.insert(0, '.')
from app import app

print("=" * 70)
print("TEST — /data/reset ne purge que le cache de la session courante")
print("=" * 70)

upload_folder = app.config['UPLOAD_FOLDER']
os.makedirs(upload_folder, exist_ok=True)

mine_path = os.path.join(upload_folder, 'completude_test_mine.json')
other_path = os.path.join(upload_folder, 'completude_test_other_session.json')
for p in (mine_path, other_path):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump({'national': {}}, f)

client = app.test_client()
with client.session_transaction() as sess:
    sess['completude_path'] = mine_path

try:
    r = client.get('/data/reset', follow_redirects=True)
    assert r.status_code == 200

    assert not os.path.exists(mine_path), "le fichier de complétude de LA session courante doit être supprimé"
    print("OK — le cache de complétude de la session qui a cliqué « Effacer » est bien supprimé")

    assert os.path.exists(other_path), \
        "RÉGRESSION : le cache de complétude d'une AUTRE session (ou du script d'actualisation) a été supprimé"
    print("OK — le cache de complétude d'une autre session reste intact (pas d'effet de bord partagé)")
finally:
    for p in (mine_path, other_path):
        if os.path.exists(p):
            os.remove(p)

print()
print("=" * 70)
print("TOUS LES TESTS DE PÉRIMÈTRE DE /data/reset SONT PASSÉS")
print("=" * 70)
