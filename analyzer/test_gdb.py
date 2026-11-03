#!/usr/bin/env python3
"""
Test script — base centrale (modules/gdb.py) : 3e axe du CUBE (géographie).

Contexte : le document SPAD définit le CUBE comme géographie × variables ×
temps. cube() et serie() formalisaient déjà variable (radical) × temps
(factums triés par date de référence) ; la géographie n'avait pas de lecture
dédiée alors que la donnée existe déjà (une variable comme District__X est
versée comme n'importe quel radical). Vérifie que spatial_radicals() et
repartition_spatiale() lisent correctement cet axe SANS toucher au
comportement existant de deposer()/cube()/serie() (régression).

Nettoie toujours les enquêtes de test (factum sous juridiction XXX, qui
n'existe dans aucune vraie donnée) à la fin, succès ou échec.
"""
import numpy as np
import pandas as pd

from modules import gdb, factum as study_factum

print("=" * 70)
print("TEST — base centrale : 3e axe du CUBE (géographie × variable)")
print("=" * 70)
checks = 0


def ok(cond, msg=''):
    global checks
    assert cond, msg
    checks += 1


FAC1 = study_factum.build('TEST_GDB_SPATIAL', 'XXX_TEST', 1, 1, 'Test_Cube_Spatial', '20260101', 'Menage')
FAC2 = study_factum.build('TEST_GDB_SPATIAL', 'XXX_TEST', 1, 1, 'Test_Cube_Spatial', '20260601', 'Menage')
assert study_factum.parse(FAC1)['valid'] and study_factum.parse(FAC2)['valid']

try:
    rng = np.random.default_rng(7)
    n = 90
    districts = rng.choice(['District_A', 'District_B', 'District_C'], n)
    df1 = pd.DataFrame({
        '_uuid': [f'r{i}' for i in range(n)],
        'District_Sanitaire__X': districts,
        'Age__1Y': np.where(districts == 'District_A', rng.integers(20, 30, n), rng.integers(40, 50, n)),
        'Sexe__X': rng.choice(['F', 'H'], n),
    })
    ok1, msg1 = gdb.deposer(df1, FAC1, titre='Test spatial 1')
    ok(ok1, msg1)

    # Deuxième enquête (même structure, districts différents) : vérifie que la
    # ventilation spatiale agrège bien across enquêtes, comme serie() le fait pour le temps.
    districts2 = rng.choice(['District_A', 'District_D'], 40)
    df2 = pd.DataFrame({
        '_uuid': [f's{i}' for i in range(40)],
        'District_Sanitaire__X': districts2,
        'Age__1Y': rng.integers(20, 30, 40),
    })
    ok2, msg2 = gdb.deposer(df2, FAC2, titre='Test spatial 2')
    ok(ok2, msg2)

    # ── Régression : cube() et serie() se comportent comme avant ─────────────
    factums, lignes = gdb.cube(1)
    ok(FAC1 in factums and FAC2 in factums)
    radicaux = {l['radical'] for l in lignes}
    ok('Age__1Y' in radicaux and 'District_Sanitaire__X' in radicaux)
    serie_age = gdb.serie('Age__1Y')
    ok(len(serie_age) == 2 and all(i['type'] == 'numerique' for i in serie_age))
    print("OK — régression : cube() et serie() inchangés avec les nouvelles données versées")

    # ── spatial_radicals() : détection par mot-clé ────────────────────────────
    detectes = dict(gdb.spatial_radicals())
    ok('District_Sanitaire__X' in detectes, detectes)
    ok('Age__1Y' not in detectes and 'Sexe__X' not in detectes, detectes)
    ok(detectes['District_Sanitaire__X'] == n + 40, detectes)   # couverture = toutes les valeurs versées
    print("OK — spatial_radicals() : repère District_Sanitaire__X par mot-clé, pas les autres variables")

    # ── repartition_spatiale() : numérique (moyenne par lieu) ────────────────
    rep = gdb.repartition_spatiale('Age__1Y', 'District_Sanitaire__X')
    by_lieu = {r['lieu']: r for r in rep}
    attendu_a = df1.loc[df1['District_Sanitaire__X'] == 'District_A', 'Age__1Y'].tolist() \
        + df2.loc[df2['District_Sanitaire__X'] == 'District_A', 'Age__1Y'].tolist()
    ok(by_lieu['District_A']['n'] == len(attendu_a), (by_lieu['District_A']['n'], len(attendu_a)))
    ok(abs(by_lieu['District_A']['moyenne'] - float(np.mean(attendu_a))) < 0.01,   # moyenne arrondie à 2 décimales
       (by_lieu['District_A']['moyenne'], float(np.mean(attendu_a))))
    ok('District_D' in by_lieu and by_lieu['District_D']['n'] == int((districts2 == 'District_D').sum()))
    ok(by_lieu['District_A']['type'] == 'numerique')
    print("OK — repartition_spatiale() : moyenne par lieu agrégée sur les 2 enquêtes, exacte")

    # ── repartition_spatiale() : catégoriel (répartition des modalités) ──────
    rep_sexe = gdb.repartition_spatiale('Sexe__X', 'District_Sanitaire__X')
    ok(rep_sexe and all(r['type'] == 'categoriel' for r in rep_sexe))
    une_ligne = next(r for r in rep_sexe if r['lieu'] == 'District_A')
    total_pct = sum(m['pct'] for m in une_ligne['modalites'])
    ok(abs(total_pct - 100) < 1 or une_ligne['autres'], une_ligne)   # Sexe__X n'a que F/H, pas de "autres"
    print("OK — repartition_spatiale() : répartition des modalités par lieu (catégoriel)")

    # ── Cas limites ────────────────────────────────────────────────────────
    ok(gdb.repartition_spatiale('Age__1Y', 'Age__1Y') == [], 'même radical des deux côtés : rien')
    ok(gdb.repartition_spatiale('Inexistant__X', 'District_Sanitaire__X') == [], 'radical absent : rien')
    ok(gdb.repartition_spatiale('', 'District_Sanitaire__X') == [], 'radical vide : rien')
    print("OK — cas limites : radical identique, absent ou vide ne renvoient rien (jamais d'erreur)")

finally:
    gdb.supprimer(FAC1)
    gdb.supprimer(FAC2)
    factums_restants, _ = gdb.cube(1)
    assert FAC1 not in factums_restants and FAC2 not in factums_restants, \
        'les enquêtes de test doivent être retirées de la base centrale'

print()
print(f"TOUS LES TESTS DU 3e AXE DU CUBE SONT PASSÉS ({checks} vérifications)")
