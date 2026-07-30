#!/usr/bin/env python3
"""
Test script — calcul de complétude (modules/completeness.py).

Simule des soumissions Kobo réalistes (codes établissements/districts réels
du référentiel) pour valider tout le pipeline de rattachement et d'agrégation,
en l'absence de vraies données Kobo disponibles pour ce test.
"""
import random
import pandas as pd
from modules import reference_data as rd
from modules import completeness as cp

print("=" * 70)
print("TEST — Calcul de complétude (modules/completeness.py)")
print("=" * 70)

ref = rd.load()
random.seed(42)
etabs = list(ref['etablissements'].keys())

# --- F5 : simuler un taux de complétude connu et vérifiable -----------------
# 3 premiers établissements à 0 (jamais soumis), les autres à exactement
# leur cible (15) sauf le 4e volontairement en excès (30 = 200%).
rows = []
for i, code in enumerate(etabs):
    if i < 3:
        n = 0
    elif i == 3:
        n = 30
    else:
        n = 15
    rows.extend([{'Etablissement_Sanitaire__X': code} for _ in range(n)])
df_f5 = pd.DataFrame(rows)
print(f"F5 simulé : {len(df_f5)} soumissions ({len(etabs)} établissements)")

result = cp.etablissement_completeness(ref, 'F5', df_f5)
assert len(result) == 120
by_code = {r['etablissement_code']: r for r in result}

for i, code in enumerate(etabs[:3]):
    assert by_code[code]['recu'] == 0
    assert by_code[code]['statut'] == 'zero'
assert by_code[etabs[3]]['recu'] == 30
assert by_code[etabs[3]]['statut'] == 'verifier'   # 200% -> excès / doublons potentiels
assert by_code[etabs[3]]['taux'] == 200.0
for code in etabs[4:]:
    assert by_code[code]['recu'] == 15
    assert by_code[code]['statut'] == 'cible'
    assert by_code[code]['taux'] == 100.0
print("OK — F5 : statuts zero/en_cours/cible/verifier corrects par établissement")

# --- F5 : colonne préfixée par un groupe Kobo (cas group/field) ------------
df_f5_grouped = df_f5.rename(columns={'Etablissement_Sanitaire__X': 'ENTETE_STANDARD/Etablissement_Sanitaire__X'})
result2 = cp.etablissement_completeness(ref, 'F5', df_f5_grouped)
assert result2 == result
print("OK — rattachement robuste aussi avec un préfixe de groupe Kobo (group/champ)")

# --- Vue nationale F5 --------------------------------------------------------
nat = cp.national_summary(ref, {'F5': df_f5})
assert nat['F5']['cible'] == 1800
recu_attendu = 0*3 + 30 + 15*116
assert nat['F5']['recu'] == recu_attendu, (nat['F5']['recu'], recu_attendu)
print(f"OK — vue nationale F5 : {nat['F5']['recu']} / {nat['F5']['cible']} "
      f"({nat['F5']['taux']} %)")

# Formulaire non chargé -> statut 'inconnu', ne doit pas planter
assert nat['F6']['statut'] == 'inconnu'
assert nat['F6']['cible'] == rd.national_targets(ref)['F6']
print("OK — formulaire non chargé géré proprement (statut 'inconnu', pas d'exception)")

# --- F01 (district) ----------------------------------------------------------
rows_f01 = [{'F01_01a__X': d} for d in list(ref['districts'].keys())[:10]]  # 10/12 districts soumis
df_f01 = pd.DataFrame(rows_f01)
res_f01 = cp.district_completeness(ref, 'F01', df_f01)
assert len(res_f01) == 12
zeros = [r for r in res_f01 if r['recu'] == 0]
assert len(zeros) == 2
print(f"OK — F01 (district) : {12-len(zeros)}/12 districts couverts, {len(zeros)} à 0 correctement détectés")

# --- F07 (district, cible = plancher décès SIG) ------------------------------
one_district = next(iter(ref['districts'].keys()))
cible_f07 = rd.target_for(ref, 'F07', district_code=one_district)
rows_f07 = [{'RDM_NOT02__X': one_district} for _ in range(cible_f07 + 5)]  # dépasse largement la cible
df_f07 = pd.DataFrame(rows_f07)
res_f07 = cp.district_completeness(ref, 'F07', df_f07)
row = next(r for r in res_f07 if r['district_code'] == one_district)
assert row['statut'] == 'cible', row  # dépasser un plancher reste "cible atteinte", jamais "à vérifier"
print(f"OK — F07 : dépasser le plancher ({row['recu']} > {row['cible']}) reste 'cible atteinte' (pas 'à vérifier')")

# --- Anomalies ----------------------------------------------------------------
zero_f5 = cp.anomalies_zero(ref, 'F5', df_f5)
assert len(zero_f5) == 3
excess_f5 = cp.anomalies_excess(ref, 'F5', df_f5)
assert len(excess_f5) == 1 and excess_f5[0]['etablissement_code'] == etabs[3]
print(f"OK — anomalies : {len(zero_f5)} établissement(s) à 0, {len(excess_f5)} en excès (≥200%)")

print()
print("=" * 70)
print("TOUS LES TESTS DE COMPLÉTUDE SONT PASSÉS")
print("=" * 70)
