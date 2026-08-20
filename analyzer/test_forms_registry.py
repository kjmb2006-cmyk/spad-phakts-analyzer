#!/usr/bin/env python3
"""
Test script — registre de formulaires dynamique (modules/forms_registry.py)
et son intégration Suivi multi-formulaires ↔ Complétude nationale.

Contexte : l'app ne doit plus rester figée sur les 7 formulaires SPAD
historiques — ils doivent être activables/désactivables, et il doit être
possible d'en ajouter d'autres (menu « Type (détection auto.) » de Suivi,
menu de correspondance de Complétude) sans toucher au code. Vérifie que :
  - le registre, une fois seedé, reproduit EXACTEMENT les cibles nationales
    historiques (régression — voir aussi test_reference_data.py)
  - désactiver un formulaire le retire de rd.FORM_CODES / national_targets,
    le réactiver le restaure
  - ajouter un formulaire synthétique au registre le fait apparaître dans
    rd.FORM_CODES, avec une cible calculée correctement selon sa règle
  - un formulaire ajouté dans Suivi multi-formulaires devient sélectionnable
    dans le menu de correspondance de Complétude nationale (demande
    explicite : « les associations doivent apparaître en fonction des
    formulaires sélectionnés dans Suivi multi-formulaires »)
  - /admin/forms est réservé au rôle admin
"""
import os
os.environ['ANALYZER_PASSWORD_ADMIN'] = 'secret-admin'

import sys
sys.path.insert(0, '.')
from app import app
from modules import reference_data as rd
from modules import forms_registry
from modules import kobo_track
from modules import form_mapping

print("=" * 70)
print("TEST — Registre de formulaires dynamique + intégration Suivi/Complétude")
print("=" * 70)

# --- Régression : le registre reproduit les cibles historiques exactes -----
# Vérifie une INCLUSION (pas une égalité stricte) : sur un déploiement réel,
# le registre grandit légitimement au fil de la collecte (ex. un formulaire
# personnalisé ajouté depuis Administration → Formulaires) — le but ici est
# de garantir que les 7 formulaires historiques restent corrects, pas que le
# registre s'arrête à eux.
ref = rd.load()
nat = rd.national_targets(ref)
attendu = {'F5': 1800, 'F6': 271, 'F7': 1800, 'F8': 120, 'F01': 12, 'F02': 16, 'F07': 187}
for code, cible in attendu.items():
    assert nat.get(code) == cible, f"{code} : attendu {cible}, obtenu {nat.get(code)} — {nat}"
print("OK — cibles nationales identiques aux 7 formulaires historiques (aucune régression)")

# --- Désactivation / réactivation -------------------------------------------
assert 'F02' in rd.FORM_CODES
forms_registry.set_active('F02', False)
assert 'F02' not in rd.FORM_CODES
assert 'F02' not in rd.national_targets(ref)
forms_registry.set_active('F02', True)
assert 'F02' in rd.FORM_CODES
print("OK — désactiver un formulaire le retire de FORM_CODES/national_targets, réactiver le restaure")

# --- Ajout d'un formulaire synthétique --------------------------------------
TEST_CODE = '_TEST_F99'
forms_registry.delete_form(TEST_CODE)  # nettoyage défensif
ok, err = forms_registry.add_form(
    code=TEST_CODE, label='Formulaire test synthétique', name_hint='99_',
    grain='etablissement', actor='enqueteur',
    etab_field='Etablissement_Sanitaire__X', district_field='District_Sanitaire__X',
    target_rule={'type': 'fixed_per_etablissement', 'params': {'n': 2}},
)
assert ok, err
assert TEST_CODE in rd.FORM_CODES
assert rd.FORM_LABELS[TEST_CODE] == 'Formulaire test synthétique'
assert rd.national_targets(ref)[TEST_CODE] == 2 * len(ref['etablissements'])
print(f"OK — formulaire ajouté au registre : apparaît dans FORM_CODES, cible = 2 × {len(ref['etablissements'])} établissements")

# Code déjà existant refusé
ok2, err2 = forms_registry.add_form(
    code=TEST_CODE, label='doublon', name_hint='', grain='etablissement', actor='enqueteur',
    etab_field=None, district_field=None, target_rule={'type': 'fixed_per_etablissement', 'params': {'n': 1}},
)
assert not ok2 and 'existe déjà' in err2
print("OK — ajouter un code déjà existant est refusé")

forms_registry.delete_form(TEST_CODE)
assert TEST_CODE not in rd.FORM_CODES
print("OK — formulaire synthétique supprimé (registre nettoyé)")

print()
print("=" * 70)
print("TESTS D'INTÉGRATION — routes Flask")
print("=" * 70)

client = app.test_client()

# --- /admin/forms réservé au rôle admin (vérifié avant connexion) ----------
r = client.get('/admin/forms', follow_redirects=False)
assert r.status_code == 302 and '/login' in r.headers['Location']
print("OK — /admin/forms inaccessible sans connexion")

client.post('/login', data={'password': 'secret-admin', 'access': 'admin'})
r = client.get('/admin/forms')
assert r.status_code == 200 and 'F02' in r.get_data(as_text=True)
print("OK — /admin/forms accessible au rôle admin, liste bien les formulaires du registre")

# --- Un formulaire ajouté dans Suivi devient sélectionnable dans Complétude -
# Depuis la synchronisation automatique Suivi → Complétude (voir
# _sync_completude_mapping() dans app.py, appelée par /suivi/add et
# /suivi/target), Complétude nationale ne montre plus QUE les codes
# effectivement associés à un formulaire Kobo (form_mapping.py) — plus le
# catalogue complet des codes actifs du registre. Ce test manipule
# kobo_track directement (sans passer par la route), donc la synchronisation
# automatique ne se déclenche pas ici : on l'imite explicitement avec
# form_mapping.save() pour vérifier le même comportement observable.
kobo_track._trackers['_test_uid'] = kobo_track._new_entry(
    '_test_uid', '_Formulaire_Suivi_Test_Integration', 100, 'inst', form_type='F5', target_source='detectee')
kobo_track._trackers['_test_uid']['count'] = 7
_original_mapping_fr = form_mapping.load()
try:
    form_mapping.save({**_original_mapping_fr, 'F5': '_test_uid'})
    r = client.get('/completude')
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert '_Formulaire_Suivi_Test_Integration' in html, \
        "un formulaire suivi ET associé (via Suivi ou form_mapping) doit apparaître dans Complétude"
    print("OK — un formulaire ajouté dans Suivi et associé devient visible dans Complétude nationale")
finally:
    kobo_track.remove('_test_uid')
    form_mapping.save(_original_mapping_fr)

print()
print("=" * 70)
print("TOUS LES TESTS DE REGISTRE DE FORMULAIRES SONT PASSÉS")
print("=" * 70)
