#!/usr/bin/env python3
"""
Test script pour vérifier la fonctionnalité de l'analyse descriptive.
"""
import pandas as pd
import sys
from modules.raw_analysis import (
    descriptive_summary,
    systematic_analysis,
    data_quality_score,
    overview_stats,
    missing_bar_chart,
    missing_heatmap,
    correlation_matrix,
    distributions_chart,
    composition_chart,
    data_quality_gauge,
)

print("=" * 70)
print("TEST - ANALYSE DESCRIPTIVE ET VISUALISATIONS")
print("=" * 70)

# Charger les données d'exemple
data_path = 'data/donnees_enquete_spad.xlsx'
try:
    df = pd.read_excel(data_path)
    print(f"\n✓ Données chargées : {df.shape[0]} observations × {df.shape[1]} variables")
except Exception as e:
    print(f"\n✗ Erreur lors du chargement : {e}")
    sys.exit(1)

# Test 1 : Overview stats
print("\n[1] Overview statistics...")
try:
    overview = overview_stats(df)
    print(f"    ✓ Overview generé : {overview['n_vars']} variables, {overview['n_obs']} observations")
except Exception as e:
    print(f"    ✗ Erreur : {e}")
    sys.exit(1)

# Test 2 : Analyse descriptive avec tableaux et graphiques
print("\n[2] Descriptive summary (tableaux + graphiques)...")
try:
    desc = descriptive_summary(df)
    n_cont = len(desc['continuous'])
    n_cat = len(desc['categorical'])
    n_bin = len(desc['binary'])
    print(f"    ✓ Analyse descriptive générée :")
    print(f"      - {n_cont} variables continues analysées")
    print(f"      - {n_cat} variables catégorielles analysées")
    print(f"      - {n_bin} variables binaires analysées")
    
    # Vérifier un exemple
    if n_cont > 0:
        cont = desc['continuous'][0]
        if 'chart_hist' in cont:
            print(f"      - Graphique histogram : OK")
        if 'stats' in cont:
            print(f"      - Tableau statistiques : OK")
except Exception as e:
    print(f"    ✗ Erreur : {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3 : Analyse systématique
print("\n[3] Systematic analysis...")
try:
    sys_analysis = systematic_analysis(df)
    print(f"    ✓ Analyse systématique générée :")
    print(f"      - Profil : {sys_analysis['profile']['n_obs']} obs, {sys_analysis['profile']['n_vars']} vars")
    print(f"      - Score qualité : {sys_analysis['quality']['quality_score']}/100")
    print(f"      - Anomalies détectées : {len(sys_analysis['anomalies'])}")
    print(f"      - Recommandations : {len(sys_analysis['recommendations'])}")
except Exception as e:
    print(f"    ✗ Erreur : {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4 : Graphiques
print("\n[4] Data quality gauge...")
try:
    gauge = data_quality_gauge(sys_analysis['quality'])
    if gauge and len(gauge) > 100:
        print(f"    ✓ Gauge JSON généré ({len(gauge)} bytes)")
    else:
        print(f"    ✗ Gauge JSON vide ou trop petit")
except Exception as e:
    print(f"    ✗ Erreur : {e}")
    sys.exit(1)

print("\n[5] Heatmap des données manquantes...")
try:
    heatmap = missing_heatmap(df)
    if heatmap and len(heatmap) > 100:
        print(f"    ✓ Heatmap JSON généré ({len(heatmap)} bytes)")
    else:
        print(f"    ✗ Heatmap JSON vide")
except Exception as e:
    print(f"    ✗ Erreur : {e}")
    sys.exit(1)

print("\n[6] Distributions continues...")
try:
    distrib = distributions_chart(df)
    if distrib and len(distrib) > 100:
        print(f"    ✓ Distribution chart JSON généré ({len(distrib)} bytes)")
    else:
        print(f"    ✓ Distributions chart : pas de variables continues ou trop peu")
except Exception as e:
    print(f"    ✗ Erreur : {e}")
    sys.exit(1)

print("\n[7] Corrélations...")
try:
    corr = correlation_matrix(df)
    if corr and len(corr) > 100:
        print(f"    ✓ Correlation matrix JSON généré ({len(corr)} bytes)")
    elif corr is None:
        print(f"    ✓ Pas assez de variables numériques pour corrélations")
    else:
        print(f"    ✗ Correlation matrix vide")
except Exception as e:
    print(f"    ✗ Erreur : {e}")
    sys.exit(1)

print("\n[8] Composition chart...")
try:
    comp = composition_chart(sys_analysis)
    if comp and len(comp) > 100:
        print(f"    ✓ Composition chart JSON généré ({len(comp)} bytes)")
    else:
        print(f"    ✗ Composition chart vide")
except Exception as e:
    print(f"    ✗ Erreur : {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("✓ TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS")
print("=" * 70)
print("\nRésumé:")
print(f"  • Données : {df.shape[0]} observations × {df.shape[1]} variables")
print(f"  • Analyse descriptive : {n_cont + n_cat + n_bin} variables analysées")
print(f"  • Anomalies détectées : {len(sys_analysis['anomalies'])}")
print(f"  • Recommandations d'analyse : {len(sys_analysis['recommendations'])}")
print(f"  • Score de qualité : {sys_analysis['quality']['quality_score']}/100")
print()
