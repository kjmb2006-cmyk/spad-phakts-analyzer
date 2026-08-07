#!/usr/bin/env python3
"""
Test script — Complétude nationale n'affiche que les codes SPAD réellement
associés à un formulaire Kobo (form_mapping.py), pas tout le catalogue de
codes actifs du registre.

Contexte : les 7 formulaires SPAD (F5-F07) ne sont pas des colonnes figées
— une période de collecte donnée peut n'en utiliser aucun, un seul, ou en
introduire de nouveaux via le registre. Avant ce correctif, Complétude
nationale (et toutes ses sous-pages : régions, districts, enquêteurs,
superviseurs, anomalies, graphiques) affichait une carte/colonne pour
CHAQUE code actif du registre même si l'utilisateur n'avait sélectionné
qu'un seul formulaire dans Suivi — reproduit en observant 7 cartes à
« Non calculé » alors qu'un seul formulaire (non lié à F5-F07) était suivi.
Vérifie que :
  - _completude_scope() ne renvoie que les codes présents dans form_mapping
  - /completude n'affiche que les codes mappés dans « Correspondance » et
    « Complétude par formulaire »
  - un code actif mais jamais mappé (ex. les 7 historiques, sur un
    déploiement qui n'en suit aucun) n'apparaît nulle part
  - une fois mappé (via /suivi, qui alimente automatiquement le mapping),
    il redevient visible
"""
import os
os.environ['ANALYZER_PASSWORD_ADMIN'] = 'secret-admin-completude-scope'

import sys
sys.path.insert(0, '.')
from app import app, _completude_scope
from modules import form_mapping
from modules import kobo_track
from modules import reference_data as rd

print("=" * 70)
print("TEST — Complétude nationale limitée aux codes réellement mappés")
print("=" * 70)

_original_mapping = form_mapping.load()
try:
    form_mapping.save({})
    assert _completude_scope() == [], _completude_scope()
    print("OK — _completude_scope() est vide sans aucune correspondance enregistrée")

    form_mapping.save({'F5': 'uid_f5_test'})
    scope = _completude_scope()
    assert scope == ['F5'], scope
    print("OK — _completude_scope() ne renvoie que les codes mappés (F5 seul)")

    assert 'F6' not in _completude_scope(['F5', 'F6', 'F07'])
    print("OK — un sous-ensemble fourni (ex. cp.enqueteur_forms()) est aussi filtré aux codes mappés")

    client = app.test_client()
    client.post('/login', data={'password': 'secret-admin-completude-scope', 'access': 'admin'})
    kobo_track._trackers['_uid_scope_test'] = kobo_track._new_entry(
        '_uid_scope_test', '_Formulaire_Scope_Test', 100, 'inst', form_type='F5', target_source='detectee')
    try:
        r = client.get('/completude')
        html = r.get_data(as_text=True)
        assert r.status_code == 200
        assert 'F5 —' in html, "F5 (mappé) doit apparaître dans la correspondance"
        assert 'F6 —' not in html, "F6 (actif mais jamais mappé) ne doit apparaître nulle part"
        assert 'F07 —' not in html, "F07 (actif mais jamais mappé) ne doit apparaître nulle part"
        print("OK — /completude n'affiche que F5 (mappé), pas F6/F07 (actifs mais non mappés)")
    finally:
        kobo_track.remove('_uid_scope_test')

finally:
    form_mapping.save(_original_mapping)

print()
print("=" * 70)
print("TOUS LES TESTS DE PÉRIMÈTRE DE COMPLÉTUDE SONT PASSÉS")
print("=" * 70)
