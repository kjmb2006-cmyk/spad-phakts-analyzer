#!/usr/bin/env python3
"""
Test script — persistance de « Suivi multi-formulaires » (modules/kobo_track.py)
à travers un redémarrage complet de l'application.

Contexte : jusqu'ici, _trackers/_threads n'existaient qu'en mémoire — chaque
redémarrage Python (nécessaire après toute modification du backend) vidait
silencieusement la liste des formulaires suivis. Conséquence concrète
observée : après redémarrage, le menu « Correspondance formulaire SPAD ↔
KoboToolbox » de Complétude nationale (qui ne propose que les formulaires
listés par kobo_track.list_tracked() depuis la Phase B) affichait
« — Non associé — » pour les 7 formulaires SPAD, alors que le fichier de
correspondance réel (data/reference/spad_form_mapping.local.json) contenait
toujours les bonnes associations — juste que leurs <option> avaient disparu
du menu. Vérifie que :
  - un formulaire ajouté au suivi survit à un redémarrage simulé (rechargement
    du module dans un process frais)
  - la cible, le type détecté et le dernier effectif connu sont conservés
  - resume() redémarre le sondage pour les formulaires restaurés, sans
    dupliquer un thread déjà actif (idempotent)
  - remove() efface bien l'entrée du fichier persisté (pas de réapparition
    fantôme après une suppression volontaire)
"""
import os
import json
import time
import subprocess
import sys

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACK_PATH = os.path.join(MODULE_DIR, 'data', 'reference', 'kobo_track.local.json')

print("=" * 70)
print("TEST — Persistance de Suivi multi-formulaires (modules/kobo_track.py)")
print("=" * 70)

# On isole ce test de tout état réel déjà présent sur disque (sauvegarde/
# restauration), comme test_mapping_validation.py le fait pour le mapping.
_had_existing = os.path.exists(TRACK_PATH)
_backup = None
if _had_existing:
    with open(TRACK_PATH, 'r', encoding='utf-8') as f:
        _backup = f.read()

try:
    from modules import kobo_track as kt

    kt.remove('uid_persist_test')  # nettoyage défensif si un run précédent a échoué

    kt._trackers['uid_persist_test'] = kt._new_entry(
        'uid_persist_test', 'Formulaire Persistance Test', 500, 'kf.kobotoolbox.org',
        form_type='F5', target_source='detectee')
    kt._trackers['uid_persist_test']['count'] = 342
    kt._save_persisted()
    assert os.path.exists(TRACK_PATH)
    print("OK — un formulaire suivi est bien écrit sur disque (kobo_track.local.json)")

    # ── Redémarrage simulé : un process Python frais, pas juste une réimportation
    # (sys.modules garderait l'état déjà en mémoire et ne testerait rien) ──
    check = subprocess.run(
        [sys.executable, '-c', (
            "import sys; sys.path.insert(0, %r)\n"
            "from modules import kobo_track as kt\n"
            "t = [e for e in kt.list_tracked() if e['uid'] == 'uid_persist_test']\n"
            "assert len(t) == 1, t\n"
            "e = t[0]\n"
            "assert e['target'] == 500, e\n"
            "assert e['form_type'] == 'F5', e\n"
            "assert e['count'] == 342, e\n"
            "assert 'uid_persist_test' not in kt._threads, 'aucun thread ne doit demarrer a l\\'import'\n"
            "print('sous-process OK')\n"
        ) % MODULE_DIR],
        capture_output=True, text=True, cwd=MODULE_DIR,
    )
    assert check.returncode == 0, f"stdout={check.stdout}\nstderr={check.stderr}"
    assert 'sous-process OK' in check.stdout
    print("OK — un process Python frais restaure le formulaire (cible, type, dernier effectif) sans démarrer de sondage")

    # ── resume() doit démarrer le sondage et être idempotent ──
    from modules import kobo_connector
    kobo_connector.get_asset_info = lambda token, uid, instance=None: {'success': False, 'error': 'faux test'}

    assert 'uid_persist_test' not in kt._threads
    kt.resume('faux-token', 'kf.kobotoolbox.org')
    assert 'uid_persist_test' in kt._threads
    first_thread = kt._threads['uid_persist_test'][0]
    print("OK — resume() démarre le sondage pour un formulaire restauré")

    kt.resume('faux-token', 'kf.kobotoolbox.org')
    assert kt._threads['uid_persist_test'][0] is first_thread, "resume() ne doit pas dupliquer un thread déjà actif"
    print("OK — resume() est idempotent")

    time.sleep(0.2)
    kt.remove('uid_persist_test')
    assert 'uid_persist_test' not in kt._load_persisted(), "remove() doit effacer l'entrée du fichier persisté"
    print("OK — remove() efface bien l'entrée persistée (pas de réapparition après redémarrage)")

finally:
    if _had_existing:
        with open(TRACK_PATH, 'w', encoding='utf-8') as f:
            f.write(_backup)
    elif os.path.exists(TRACK_PATH):
        os.remove(TRACK_PATH)

print()
print("=" * 70)
print("TOUS LES TESTS DE PERSISTANCE DE SUIVI MULTI-FORMULAIRES SONT PASSÉS")
print("=" * 70)
