#!/usr/bin/env python3
"""
Test script — modules/collecte_monitor.py (« Suivi d'un formulaire »)

Contexte : ce fichier était écrit au format pytest (fonctions test_...())
alors que pytest n'est pas installé dans ce projet (absent de
requirements.txt et du venv) — exécuté via `python3 test_collecte_monitor.py`
(la convention utilisée par tous les autres tests de ce projet), aucune des
fonctions ne s'exécutait jamais : le script importait, définissait les
fonctions, puis quittait avec succès sans avoir rien vérifié. Converti au
format « script plat » (assertions au niveau module) comme le reste de la
suite.

Vérifie aussi le correctif du 20/08 : « Suivi d'un formulaire » affichait
des « Zone 1 », « Zone 2 », « Zone 3 » entièrement fictives (comptages
calculés par arithmétique arbitraire à partir du seul total, sans jamais
lire les données réelles) — alors que les vraies colonnes région/district/
établissement sont bien identifiées dans le formulaire chargé. Remplacé par
une répartition géographique réelle (voir real_geo_breakdown()).
"""
import tempfile
from pathlib import Path

import pandas as pd

from modules.collecte_monitor import (
    load_state,
    save_state,
    append_sync_event,
    build_dashboard_metrics,
    build_collecte_views,
    detect_geo_column,
    real_geo_breakdown,
)

print("=" * 70)
print("TEST — Suivi d'un formulaire (modules/collecte_monitor.py)")
print("=" * 70)

# --- append_sync_event() / build_dashboard_metrics() de base -----------------
with tempfile.TemporaryDirectory() as tmpdir:
    path = Path(tmpdir) / 'collecte_state.json'
    state = load_state(path)
    state = append_sync_event(state, path, form_name='Formulaire A', count=120, status='réussi', target=200)
    state = append_sync_event(state, path, form_name='Formulaire A', count=150, status='réussi', target=200)

    assert state['target'] == 200
    assert state['last_sync_count'] == 150
    assert len(state['history']) == 2

    metrics = build_dashboard_metrics(state, current_count=150)
    assert metrics['received'] == 150
    assert metrics['cible'] == 200
    assert metrics['taux'] == 75.0
    assert len(metrics['evolution']) == 2
    # Sans dataframe chargé (df=None), aucune zone fictive ne doit être
    # inventée.
    assert metrics['zones'] == []
    assert metrics['geo_column'] is None
print("OK — append_sync_event() / build_dashboard_metrics() : état et cumul corrects, aucune zone fictive sans données")

# --- save_state() / load_state() ---------------------------------------------
with tempfile.TemporaryDirectory() as tmpdir:
    path = Path(tmpdir) / 'collecte_state.json'
    save_state(path, {'target': 500, 'history': []})
    loaded = load_state(path)
    assert loaded['target'] == 500
    assert isinstance(loaded['history'], list)
print("OK — save_state()/load_state() persistent correctement sur disque")

# --- build_collecte_views() : teams/alerts/quality inchangés, zones vides ----
state = {
    'target': 200,
    'history': [{'form_name': 'Collecte F5', 'count': 80, 'status': 'réussi'}],
    'last_sync_at': '2026-08-04 10:00',
    'last_sync_count': 80,
    'last_sync_status': 'réussi',
    'last_form_name': 'Collecte F5',
}
payload = build_collecte_views(state, current_count=80, data_meta={'n_vars': 24, 'missing_pct': 8.5})
assert payload['geo_items'] == [] and payload['geo_column'] is None and payload['stratified_summary'] == []
assert payload['teams'][0]['name'] == 'Équipe terrain 1'
assert payload['alerts'][0]['type'] == 'Synchronisation réussie'
assert payload['quality_items'][0]['variable'] == 'Observations'
assert payload['interpretation']['risk_level'] in {'faible', 'moyen', 'élevé'}
assert 'recommandation' in payload['interpretation']
print("OK — build_collecte_views() sans dataframe : équipes/alertes/qualité corrects, tableaux géo vides (pas de zones fictives)")

payload2 = build_collecte_views(
    state, current_count=80, data_meta={'n_vars': 24, 'missing_pct': 8.5},
    sync_status={'active': True, 'has_pending': True, 'available_n_obs': 95},
)
assert payload2['sync_status']['active'] is True
assert payload2['sync_status']['has_pending'] is True
assert payload2['sync_status']['available_n_obs'] == 95
print("OK — build_collecte_views() relaie bien le statut de synchronisation automatique")

# --- Répartition géographique réelle (remplace les anciennes zones fictives) -
df = pd.DataFrame({
    'ENTETE_STANDARD/Region_Sanitaire__X': ['Nord'] * 3,
    'ENTETE_STANDARD/District_Sanitaire__X': ['Abengourou', 'Bondoukou', 'Abengourou'],
    'ENTETE_STANDARD/Etablissement_Sanitaire__X': ['CSU A', 'CSU B', 'CSU C'],
})
assert detect_geo_column(df) == 'ENTETE_STANDARD/District_Sanitaire__X'
print("OK — detect_geo_column() préfère district > région > établissement")

assert detect_geo_column(pd.DataFrame({'Region_Sanitaire__X': ['Nord', 'Sud']})) == 'Region_Sanitaire__X'
assert detect_geo_column(pd.DataFrame({'Sexe__X': ['Homme', 'Femme']})) is None
assert detect_geo_column(None) is None
assert detect_geo_column(pd.DataFrame()) is None
print("OK — detect_geo_column() se rabat sur région si pas de district, None si aucune colonne géo")

df_counts = pd.DataFrame({
    'ENTETE_STANDARD/District_Sanitaire__X': ['Abengourou'] * 3 + ['Bondoukou'] * 1 + [None],
})
items, col = real_geo_breakdown(df_counts, target=40)
assert col == 'ENTETE_STANDARD/District_Sanitaire__X'
names = {item['name']: item for item in items}
assert set(names) == {'Abengourou', 'Bondoukou'}, names
assert names['Abengourou']['received'] == 3 and names['Bondoukou']['received'] == 1
assert names['Abengourou']['target'] == 20 and names['Bondoukou']['target'] == 20
assert names['Abengourou']['rate'] == 15.0
assert names['Bondoukou']['status'] == 'À risque'
print("OK — real_geo_breakdown() renvoie les vrais noms de district et les vrais effectifs (cible répartie également)")

assert real_geo_breakdown(None, target=100) == ([], None)
assert real_geo_breakdown(pd.DataFrame({'Sexe__X': ['H', 'F']}), target=100) == ([], None)
items_empty, col_empty = real_geo_breakdown(pd.DataFrame({'District_Sanitaire__X': [None, None]}), target=100)
assert items_empty == [] and col_empty == 'District_Sanitaire__X'
print("OK — real_geo_breakdown() renvoie une liste vide (jamais de zones inventées) sans données exploitables")

df_metrics = pd.DataFrame({
    'ENTETE_STANDARD/District_Sanitaire__X': ['Odienné'] * 5 + ['Tiébissou'] * 2,
})
metrics_df = build_dashboard_metrics({'target': 70, 'history': [], 'last_sync_count': 7}, current_count=7, df=df_metrics)
assert metrics_df['geo_column'] == 'ENTETE_STANDARD/District_Sanitaire__X'
assert {z['name'] for z in metrics_df['zones']} == {'Odienné', 'Tiébissou'}
print("OK — build_dashboard_metrics() utilise bien le vrai dataframe quand il est fourni")

print()
print("=" * 70)
print("TOUS LES TESTS DE SUIVI D'UN FORMULAIRE SONT PASSÉS")
print("=" * 70)
