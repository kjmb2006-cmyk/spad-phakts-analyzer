#!/usr/bin/env python3
"""
Test script — /completude/mapper ne doit jamais effacer une correspondance
déjà enregistrée pour un formulaire absent du formulaire HTML soumis.

Contexte : bug réel constaté en usage — la route reconstruisait le mapping
depuis un dict vide en ne parcourant que ref_data.FORM_CODES (les
formulaires *actifs* au moment de la requête). Si un formulaire est
temporairement désactivé dans le registre (modules/forms_registry.py,
Administration → Formulaires) au moment où « Enregistrer la correspondance »
est cliqué, son champ uid_<code> n'existe pas dans le formulaire HTML rendu
→ absent de request.form → la boucle passait dessus → sa correspondance
Kobo précédemment enregistrée disparaissait du fichier persisté sans que
personne ne l'ait demandé. Reproduit et corrigé : la route part maintenant
de form_mapping.load() (pas d'un dict vide) et ne touche que les codes
présents dans ref_data.FORM_CODES au moment de la requête.
"""
import os
os.environ['ANALYZER_PASSWORD_ADMIN'] = 'secret-admin-mapper-safety'

import sys
sys.path.insert(0, '.')
from app import app
from modules import form_mapping
from modules import forms_registry

print("=" * 70)
print("TEST — /completude/mapper préserve les correspondances des formulaires inactifs")
print("=" * 70)

client = app.test_client()
client.post('/login', data={'password': 'secret-admin-mapper-safety', 'access': 'admin'})

_original_mapping = form_mapping.load()
_was_active = {code: forms_registry.get(code)['active'] for code in ('F5', 'F02')}
try:
    # Mapping de départ : F5 et F02 sont tous deux associés à un formulaire Kobo.
    form_mapping.save({'F5': 'uid_f5_reel', 'F02': 'uid_f02_reel'})

    # F02 est désactivé — son champ uid_F02 n'apparaîtra plus dans le
    # formulaire HTML de /completude, donc pas dans la requête POST ci-dessous
    # (on simule exactement ce que le navigateur soumettrait : uniquement les
    # codes actuellement actifs).
    forms_registry.set_active('F02', False)

    r = client.post('/completude/mapper', data={'uid_F5': 'uid_f5_reel'})
    assert r.status_code == 302
    mapping_apres = form_mapping.load()

    assert mapping_apres.get('F02') == 'uid_f02_reel', (
        "RÉGRESSION : la correspondance de F02 (formulaire désactivé, absent du "
        f"formulaire soumis) a été effacée — mapping={mapping_apres}")
    print("OK — la correspondance d'un formulaire désactivé (absent du POST) est préservée")

    assert mapping_apres.get('F5') == 'uid_f5_reel'
    print("OK — la correspondance d'un formulaire actif et soumis reste correcte")

    # Un formulaire actif explicitement remis à « Non associé » (champ soumis
    # vide) doit, lui, bien être effacé — un désassociation volontaire doit
    # continuer de fonctionner.
    r = client.post('/completude/mapper', data={'uid_F5': ''})
    mapping_apres2 = form_mapping.load()
    assert 'F5' not in mapping_apres2, "une désassociation volontaire (champ vide soumis) doit être respectée"
    assert mapping_apres2.get('F02') == 'uid_f02_reel', "F02 doit toujours être préservé"
    print("OK — désassocier volontairement un formulaire actif fonctionne toujours")

finally:
    forms_registry.set_active('F02', _was_active['F02'])
    forms_registry.set_active('F5', _was_active['F5'])
    form_mapping.save(_original_mapping)

print()
print("=" * 70)
print("TOUS LES TESTS DE SÉCURITÉ DE /completude/mapper SONT PASSÉS")
print("=" * 70)
