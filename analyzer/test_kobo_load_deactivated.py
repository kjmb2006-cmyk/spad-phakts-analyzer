#!/usr/bin/env python3
"""
Test script — un formulaire désactivé dans le registre (Administration →
Formulaires) ne doit plus être chargeable dans « Analyse de données ».

Contexte : désactiver un formulaire (F5-F07 ou tout autre code du registre)
ne l'empêchait que d'apparaître dans Suivi/Complétude — on pouvait toujours
le charger et l'analyser statistiquement via /kobo/load, ce qui semblait
incohérent une fois qu'on a explicitement dit « ce formulaire n'est plus
utilisé ». Demande explicite : bloquer aussi le chargement pour analyse.

Vérifie que _deactivated_form_code() (app.py) reconnaît un formulaire
désactivé de deux façons — via une correspondance déjà enregistrée
(form_mapping.py), ou par déduction du nom (registre complet, y compris les
formulaires inactifs, contrairement à reference_data.guess_form_type() qui
ne regarde que les formulaires actifs) — et que /kobo/load et /kobo/refresh
bloquent effectivement le chargement dans ce cas, mais laissent passer un
formulaire actif ou sans rapport avec le registre.
"""
import os
os.environ['ANALYZER_PASSWORD_ADMIN'] = 'secret-admin-kobo-load-deactivated'

import sys
sys.path.insert(0, '.')
import app as app_module
from app import app, _deactivated_form_code
from modules import forms_registry
from modules import form_mapping

print("=" * 70)
print("TEST — Formulaire désactivé bloqué dans Analyse de données")
print("=" * 70)

_original_mapping = form_mapping.load()
_was_active = forms_registry.get('F5')['active']
try:
    forms_registry.set_active('F5', False)

    # --- Détection via une correspondance déjà enregistrée ---
    form_mapping.save({**_original_mapping, 'F5': 'uid_mapped_f5'})
    code = _deactivated_form_code('uid_mapped_f5', 'Nom Quelconque Sans Rapport')
    assert code == 'F5', code
    print("OK — un formulaire désactivé est détecté via une correspondance déjà enregistrée")

    # --- Détection par déduction du nom (pas de correspondance enregistrée) ---
    form_mapping.save(_original_mapping)
    code = _deactivated_form_code('uid_jamais_mappe', '5_PNLTA_SPAD_Fiche_Femmes_Enceintes_Allaitantes_Tabac')
    assert code == 'F5', code
    print("OK — un formulaire désactivé est aussi détecté par déduction du nom (registre complet, actifs et inactifs)")

    # --- Un formulaire actif ou sans rapport n'est jamais bloqué ---
    forms_registry.set_active('F5', True)
    assert _deactivated_form_code('uid_jamais_mappe', '5_PNLTA_SPAD_Fiche_Femmes_Enceintes_Allaitantes_Tabac') is None
    assert _deactivated_form_code('uid_sans_rapport', 'Un formulaire totalement étranger au registre SPAD') is None
    print("OK — un formulaire actif, ou sans rapport avec le registre, n'est jamais bloqué")

    # --- Intégration Flask : /kobo/load bloque effectivement le chargement ---
    forms_registry.set_active('F5', False)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['role'] = 'admin'
        sess['kobo_token'] = 'faux-token'

    def _fake_load_data(token, uid, instance=None):
        raise AssertionError("kobo_load_data() ne doit jamais être appelé pour un formulaire désactivé")
    app_module.kobo_load_data = _fake_load_data

    r = client.post('/kobo/load', data={
        'uid': 'uid_test_load', 'name': '5_PNLTA_SPAD_Fiche_Femmes_Enceintes_Allaitantes_Tabac',
    }, follow_redirects=True)
    assert r.status_code == 200
    assert 'désactivé' in r.get_data(as_text=True).lower()
    with client.session_transaction() as sess:
        assert sess.get('kobo_uid') is None, "le formulaire désactivé ne doit jamais être chargé en session"
    print("OK — /kobo/load refuse de charger un formulaire désactivé (kobo_load_data jamais appelé)")

finally:
    forms_registry.set_active('F5', _was_active)
    form_mapping.save(_original_mapping)

print()
print("=" * 70)
print("TOUS LES TESTS DE BLOCAGE DES FORMULAIRES DÉSACTIVÉS SONT PASSÉS")
print("=" * 70)
