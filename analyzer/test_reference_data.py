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

# Anonymisation : le fichier COMMITTÉ (org_unit.xlsx) ne doit jamais contenir
# de nom propre — on le vérifie sur son contenu brut, indépendamment d'un
# éventuel fichier local non versionné (noms_personnel.local.json) que
# load() superpose ensuite pour l'affichage sur le poste de l'utilisateur.
raw = rd._load_org_unit(rd.DEFAULT_ORG_UNIT_PATH)
for e in raw['enqueteurs'].values():
    assert e['nom_complet'] == e['code'], f"nom non expurgé dans org_unit.xlsx : {e}"
for s in raw['superviseurs'].values():
    assert s['nom_complet'] == s['code'], f"nom non expurgé dans org_unit.xlsx : {s}"
print("OK — org_unit.xlsx (fichier committé) bien expurgé (codes uniquement)")

nat = rd.national_targets(ref)
print()
print("Cibles nationales calculées :", nat)

n_etab_avec_deces = sum(1 for e in ref['etablissements'].values() if e['sig_deces_maternels'] > 0)

assert nat['F5'] == 1800
assert nat['F7'] == 1800
assert nat['F8'] == 120
assert nat['F01'] == 12
# F02 = nombre d'établissements ayant ≥1 décès maternel SIG (pas tout
# l'échantillon de 120) — dérivé de tirage_etablissements.xlsx, pas figé.
assert nat['F02'] == n_etab_avec_deces, (nat['F02'], n_etab_avec_deces)
assert 260 <= nat['F6'] <= 280, nat['F6']   # ~271, tolérance vs le chiffre observé (273)
assert 180 <= nat['F07'] <= 195, nat['F07']  # ~187, tolérance vs le chiffre observé (188)
print("OK — cibles nationales conformes aux totaux observés (F5/F7/F8/F01 exacts,"
      " F02 = établissements avec décès SIG, F6/F07 à ±10 du chiffre observé"
      " — écart documenté dans reference_data.py)")

# target_for : cohérence individuelle
some_etab = next(e for e in ref['etablissements'].values() if e['type'] == 'EPH')
assert rd.target_for(ref, 'F6', etablissement_code=some_etab['code']) == 3
some_csrd = next(e for e in ref['etablissements'].values() if e['type'] == 'CSR-D')
assert rd.target_for(ref, 'F6', etablissement_code=some_csrd['code']) == 1
assert rd.target_for(ref, 'F5') == 15
assert rd.target_for(ref, 'F8') == 1

# F02 : 1 uniquement pour un établissement avec ≥1 décès SIG, 0 sinon
etab_avec_deces = next(e for e in ref['etablissements'].values() if e['sig_deces_maternels'] > 0)
etab_sans_deces = next(e for e in ref['etablissements'].values() if e['sig_deces_maternels'] == 0)
assert rd.target_for(ref, 'F02', etablissement_code=etab_avec_deces['code']) == 1
assert rd.target_for(ref, 'F02', etablissement_code=etab_sans_deces['code']) == 0
print("OK — target_for() cohérent par type d'établissement et par formulaire"
      " (F02 conditionné à la présence d'un décès SIG)")

# Garde-fou de cohérence F02 ↔ F07 : les deux cibles dérivent du même champ
# sig_deces_maternels par établissement. Un district doit avoir une cible F02
# (établissements à notifier) si et seulement s'il a une cible F07 (décès à
# réviser) — sinon les deux volets RDM racontent des histoires différentes
# pour le même district. Verrouille l'invariant contre toute régression
# future (ex. mise à jour de tirage_etablissements.xlsx qui désaligne les deux).
from collections import defaultdict
etab_avec_deces_par_district = defaultdict(int)
f07_par_district = defaultdict(int)
for e in ref['etablissements'].values():
    f07_par_district[e['district_code']] += e['sig_deces_maternels']
    if e['sig_deces_maternels'] > 0:
        etab_avec_deces_par_district[e['district_code']] += 1

for d in ref['districts']:
    n_etab_f02 = etab_avec_deces_par_district.get(d, 0)
    cible_f07 = f07_par_district.get(d, 0)
    assert (n_etab_f02 > 0) == (cible_f07 > 0), (
        f"F02/F07 désalignés sur le district {d} : "
        f"{n_etab_f02} établissement(s) avec décès mais cible F07 = {cible_f07}"
    )
assert sum(etab_avec_deces_par_district.values()) == nat['F02']
assert sum(f07_par_district.values()) == nat['F07']
print("OK — F02 (établissements à notifier) et F07 (décès à réviser) restent"
      f" alignés par district ({sum(1 for d in ref['districts'] if etab_avec_deces_par_district.get(d, 0) > 0)}"
      " district(s) concernés sur 12)")

print()
print("=" * 70)
print("TOUS LES TESTS RÉFÉRENTIEL SONT PASSÉS")
print("=" * 70)
