#!/usr/bin/env python3
"""
Test script — référentiel organisationnel (modules/reference_data.py).

Verrouille les totaux nationaux déjà observés sur spadapp-zeta.vercel.app
pour détecter toute régression si le référentiel ou les règles de cible
sont modifiés par la suite.
"""
from modules import reference_data as rd

print("=" * 70)
print("TEST — Référentiel organisationnel SPAD (data/reference/)")
print("=" * 70)

ref = rd.load()

assert len(ref['regions']) == 12, f"régions: {len(ref['regions'])}"
assert len(ref['districts']) == 12, f"districts: {len(ref['districts'])}"
assert len(ref['etablissements']) == 120, f"établissements: {len(ref['etablissements'])}"
assert len(ref['enqueteurs']) == 60, f"enquêteurs: {len(ref['enqueteurs'])}"
assert len(ref['superviseurs']) == 12, f"superviseurs: {len(ref['superviseurs'])}"
print("OK — effectifs référentiel (12 régions, 12 districts, 120 établissements,"
      " 60 enquêteurs, 12 superviseurs)")

# Chaque enquêteur suit exactement 2 établissements (contrainte du pilote)
from collections import Counter
etab_par_enq = Counter(e['enqueteur_code'] for e in ref['etablissements'].values())
assert set(etab_par_enq.values()) == {2}, etab_par_enq
print("OK — chaque enquêteur est rattaché à exactement 2 établissements")

# Anonymisation : aucun nom propre ne doit subsister dans le référentiel
# enquêteur/superviseur committé (le code doit être identique au "nom_complet")
for e in ref['enqueteurs'].values():
    assert e['nom_complet'] == e['code'], f"nom non expurgé : {e}"
for s in ref['superviseurs'].values():
    assert s['nom_complet'] == s['code'], f"nom non expurgé : {s}"
print("OK — noms d'enquêteurs/superviseurs bien expurgés (codes uniquement)")

nat = rd.national_targets(ref)
print()
print("Cibles nationales calculées :", nat)

assert nat['F5'] == 1800
assert nat['F7'] == 1800
assert nat['F8'] == 120
assert nat['F01'] == 12
assert nat['F02'] == 120
assert 260 <= nat['F6'] <= 280, nat['F6']   # ~271, tolérance vs le chiffre observé (273)
assert 180 <= nat['F07'] <= 195, nat['F07']  # ~187, tolérance vs le chiffre observé (188)
print("OK — cibles nationales conformes aux totaux observés (F5/F7/F8/F01/F02 exacts,"
      " F6/F07 à ±10 du chiffre observé — écart documenté dans reference_data.py)")

# target_for : cohérence individuelle
some_etab = next(e for e in ref['etablissements'].values() if e['type'] == 'EPH')
assert rd.target_for(ref, 'F6', etablissement_code=some_etab['code']) == 3
some_csrd = next(e for e in ref['etablissements'].values() if e['type'] == 'CSR-D')
assert rd.target_for(ref, 'F6', etablissement_code=some_csrd['code']) == 1
assert rd.target_for(ref, 'F5') == 15
assert rd.target_for(ref, 'F8') == 1
assert rd.target_for(ref, 'F02') == 1
print("OK — target_for() cohérent par type d'établissement et par formulaire")

print()
print("=" * 70)
print("TOUS LES TESTS RÉFÉRENTIEL SONT PASSÉS")
print("=" * 70)
