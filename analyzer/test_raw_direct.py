#!/usr/bin/env python3
"""
Test direct de l'analyse brute en chargeant les données manuellement.
"""
import sys
sys.path.insert(0, '/Users/mac/Desktop/dossier\ sans\ titre/spad_analyzer')

import pandas as pd
from modules.raw_analysis import (
    systematic_analysis, 
    descriptive_summary,
    data_quality_gauge, 
    composition_chart,
    distributions_chart
)

# Charger les données de test
data_file = 'data/donnees_enquete_spad.xlsx'
print(f"📊 Chargement de {data_file}...")
df = pd.read_excel(data_file)
print(f"   ✓ {df.shape[0]} lignes × {df.shape[1]} colonnes\n")

# Test 1: Analyse systématique
print("[1] Analyse systématique...")
try:
    sys = systematic_analysis(df)
    print(f"    ✓ Quality: {sys['quality']['quality_score']}/100")
    print(f"    ✓ Profile: {sys['profile']['n_obs']} obs, {sys['profile']['n_vars']} vars")
    print(f"    ✓ Anomalies: {len(sys['anomalies'])} détectées")
    print(f"    ✓ Recommandations: {len(sys['recommendations'])}")
except Exception as e:
    print(f"    ✗ Erreur: {e}")
    import traceback; traceback.print_exc()

# Test 2: Analyse descriptive
print("\n[2] Analyse descriptive...")
try:
    desc = descriptive_summary(df)
    print(f"    ✓ Variables continues: {len(desc['continuous'])} traitées")
    print(f"    ✓ Variables catégorielles: {len(desc['categorical'])} traitées")
    print(f"    ✓ Variables binaires: {len(desc['binary'])} traitées")
    
    if desc['continuous']:
        var = desc['continuous'][0]
        print(f"    ✓ Exemple continue '{var['name']}': {len(var)} clés")
        if 'chart_hist' in var:
            print(f"      → Histogram JSON: {len(var['chart_hist'])} chars")
        if 'chart_box' in var:
            print(f"      → Box plot JSON: {len(var['chart_box'])} chars")
except Exception as e:
    print(f"    ✗ Erreur: {e}")
    import traceback; traceback.print_exc()

# Test 3: Graphiques
print("\n[3] Graphiques...")
try:
    gauge = data_quality_gauge(sys['quality'])
    print(f"    ✓ Quality gauge: {len(gauge) if gauge else 0} chars JSON")
except Exception as e:
    print(f"    ✗ Data quality gauge: {e}")

try:
    distrib = distributions_chart(df)
    print(f"    ✓ Distributions: {len(distrib) if distrib else 0} chars JSON")
except Exception as e:
    print(f"    ✗ Distributions chart: {e}")

try:
    compo = composition_chart(sys)
    print(f"    ✓ Composition: {len(compo) if compo else 0} chars JSON")
except Exception as e:
    print(f"    ✗ Composition chart: {e}")

print("\n✓ Tous les tests de l'analyse brute sont passés!")
