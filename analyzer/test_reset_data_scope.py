#!/usr/bin/env python3
"""
Test script — « Effacer les données » (/data/reset) ne doit purger que les
fichiers de données de LA session courante, jamais le cache de complétude.

Contexte (revue de la mise à jour « SPAD AI Copilot ») : le commit
b148c1b avait ajouté une boucle qui supprimait TOUS les fichiers
completude_*.json du dossier UPLOAD_FOLDER partagé, quelle que soit la
session qui a cliqué « Effacer les données ». Le cache de complétude est
aujourd'hui un fichier CANONIQUE partagé (modules/completude_cache.py), tenu
à jour pour tout le monde par le timer serveur
(scripts/kobo_completude_refresh.py) : un seul utilisateur cliquant sur ce
bouton ne doit jamais le faire disparaître. Vérifie que /data/reset supprime
bien les fichiers de la session (data_path, child_path) et laisse intacts le
cache canonique ainsi que tout fichier completude_*.json, y compris un
chemin hérité d'un ancien cookie de session (clé 'completude_path').

Le test travaille dans un dossier temporaire substitué à UPLOAD_FOLDER : il
n'efface ni n'écrase jamais le vrai cache du poste qui le lance.
"""
import os
import sys
import json
import shutil
import tempfile
sys.path.insert(0, '.')
from app import app
from modules import completude_cache

print("=" * 70)
print("TEST — /data/reset ne purge que les fichiers de la session courante")
print("=" * 70)

real_upload_folder = app.config['UPLOAD_FOLDER']
upload_folder = tempfile.mkdtemp(prefix='_test_reset_data_scope_')
app.config['UPLOAD_FOLDER'] = upload_folder

data_path = os.path.join(upload_folder, 'session_data.xlsx')
child_path = os.path.join(upload_folder, 'session_child.xlsx')
legacy_path = os.path.join(upload_folder, 'completude_legacy_session.json')      # ancien cookie
other_data_path = os.path.join(upload_folder, 'other_session_data.xlsx')         # autre session
for p in (data_path, child_path, other_data_path):
    with open(p, 'wb') as f:
        f.write(b'x')
with open(legacy_path, 'w', encoding='utf-8') as f:
    json.dump({'national': {}}, f)
completude_cache.save_cache({'national': {}}, upload_folder, '2026-01-01T00:00:00')
canonical_path = completude_cache.cache_path(upload_folder)
assert os.path.exists(canonical_path)

client = app.test_client()
with client.session_transaction() as sess:
    sess['data_path'] = data_path
    sess['child_path'] = child_path
    sess['completude_path'] = legacy_path

try:
    r = client.get('/data/reset', follow_redirects=True)
    assert r.status_code == 200

    assert not os.path.exists(data_path), "le fichier de données de LA session courante doit être supprimé"
    assert not os.path.exists(child_path), "le fichier enfant de LA session courante doit être supprimé"
    print("OK — les fichiers de données de la session qui a cliqué « Effacer » sont bien supprimés")

    assert os.path.exists(canonical_path), \
        "RÉGRESSION : le cache de complétude canonique (partagé, tenu à jour par le timer) a été supprimé"
    assert completude_cache.load_cache(upload_folder) is not None, "le cache canonique doit rester lisible"
    print("OK — le cache de complétude canonique reste intact (pas d'effet de bord partagé)")

    assert os.path.exists(legacy_path), \
        "RÉGRESSION : un fichier completude_*.json (chemin hérité d'un ancien cookie) a été supprimé"
    print("OK — un fichier de complétude référencé par un ancien cookie n'est pas supprimé")

    assert os.path.exists(other_data_path), \
        "RÉGRESSION : le fichier de données d'une AUTRE session a été supprimé"
    print("OK — les fichiers d'une autre session restent intacts")

    with client.session_transaction() as sess:
        assert not sess.get('data_path') and not sess.get('child_path'), "la session doit être vidée"
    print("OK — la session est vidée")
finally:
    app.config['UPLOAD_FOLDER'] = real_upload_folder
    shutil.rmtree(upload_folder, ignore_errors=True)

print()
print("=" * 70)
print("TOUS LES TESTS DE PÉRIMÈTRE DE /data/reset SONT PASSÉS")
print("=" * 70)
