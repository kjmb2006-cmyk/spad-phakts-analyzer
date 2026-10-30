#!/usr/bin/env python3
"""
Test script — interopérabilité PHAKTS et analyse automatique multi-enquête
(modules/multi_survey.py::detect_common_indicators()/auto_analyze(), route
/multi-survey en mode « Analyse automatique »).

Contexte : « Analyse multi-enquête (DPF/PHAKTS) » alignait déjà les
variables entre enquêtes par leur radical PHAKTS, mais l'analyse restait
manuelle (une variable choisie à la fois). Vérifie que :
  - les indicateurs communs à au moins 2 enquêtes sont détectés
    automatiquement, avec le xType et le traitement statistique corrects
  - les colonnes non codifiées PHAKTS, ou présentes dans une seule enquête,
    sont exclues de la détection
  - le test statistique de comparaison (χ² pour catégorielle, ANOVA/
    Kruskal-Wallis pour continue) est calculé pour chaque indicateur détecté
  - la route /multi-survey rend correctement les deux modes (automatique
    et manuel), et le commutateur bascule proprement entre les deux
"""
import numpy as np
import pandas as pd

from modules import multi_survey as ms

print("=" * 70)
print("TEST — Interopérabilité PHAKTS (modules/multi_survey.py)")
print("=" * 70)

rng = np.random.default_rng(0)
n1, n2, n3 = 200, 150, 100

survey_a = pd.DataFrame({
    'Age__1Y': rng.integers(18, 49, n1),
    'Emploi__B': rng.choice(['oui', 'non'], n1, p=[0.6, 0.4]),
    'Niveau_Instruction__X': rng.choice(['aucun', 'primaire', 'secondaire'], n1),
    'Consommation_Tabac__B': rng.choice(['oui', 'non'], n1, p=[0.15, 0.85]),
})
survey_b = pd.DataFrame({
    'Age__1Y': rng.integers(20, 60, n2),
    'Emploi__B': rng.choice(['oui', 'non'], n2, p=[0.9, 0.1]),
    'Niveau_Instruction__X': rng.choice(['aucun', 'primaire', 'secondaire'], n2),
    'Poste_Occupe__Z': rng.choice(['infirmier', 'medecin'], n2),
})
survey_c = pd.DataFrame({
    'Age__1Y': rng.integers(15, 70, n3),
    'Zone__X': rng.choice(['urbain', 'rural'], n3),
})
surveys = {'Tabac Femmes': survey_a, 'CAP Personnel': survey_b, 'Enquête C': survey_c}

indicators = ms.detect_common_indicators(surveys, mode='phakts', min_surveys=2)
by_radical = {i['radical']: i for i in indicators}

assert set(by_radical) == {'Age__1Y', 'Emploi__B', 'Niveau_Instruction__X'}, by_radical.keys()
print("OK — exactement les 3 indicateurs communs à >=2 enquêtes détectés (pas les autres)")

assert by_radical['Age__1Y']['n_surveys'] == 3 and by_radical['Age__1Y']['suffix'] == '1Y'
assert by_radical['Emploi__B']['n_surveys'] == 2 and by_radical['Emploi__B']['suffix'] == 'B'
assert by_radical['Niveau_Instruction__X']['n_surveys'] == 2 and by_radical['Niveau_Instruction__X']['suffix'] == 'X'
print("OK — xType et nombre d'enquêtes couvertes corrects pour chaque indicateur")

assert 'Poste_Occupe__Z' not in by_radical, "texte libre (__Z) doit être exclu de l'analyse quantitative"
assert 'Consommation_Tabac__B' not in by_radical, "présent dans 1 seule enquête -> exclu (min_surveys=2)"
assert 'Zone__X' not in by_radical, "présent dans 1 seule enquête -> exclu (min_surveys=2)"
print("OK — texte libre et indicateurs mono-enquête correctement exclus")

results = ms.auto_analyze(surveys, mode='phakts', min_surveys=2)
by_var = {r['variable']: r for r in results}
assert set(by_var) == {'Age__1Y', 'Emploi__B', 'Niveau_Instruction__X'}
print(f"OK — auto_analyze() calcule bien les {len(results)} comparaisons automatiquement")

assert by_var['Age__1Y']['kind'] == 'continuous'
assert by_var['Age__1Y']['test']['test'] in ('ANOVA', 'Kruskal-Wallis')
assert by_var['Age__1Y']['test']['p_value'] < 0.05, "les plages d'âge diffèrent nettement entre enquêtes"
print(f"OK — Age : test {by_var['Age__1Y']['test']['test']}, p={by_var['Age__1Y']['test']['p_value']} (écart détecté, attendu)")

assert by_var['Emploi__B']['kind'] == 'categorical'
assert by_var['Emploi__B']['test']['test'] == 'χ² (indépendance)'
assert by_var['Emploi__B']['test']['p_value'] < 0.05, "60% vs 90% d'emploi doit être détecté comme significatif"
print(f"OK — Emploi : {by_var['Emploi__B']['test']['test']}, p={by_var['Emploi__B']['test']['p_value']} (écart détecté, attendu)")

assert by_var['Niveau_Instruction__X']['test']['p_value'] >= 0.05, "distribution identique -> pas d'écart significatif attendu"
print(f"OK — Niveau_Instruction : p={by_var['Niveau_Instruction__X']['test']['p_value']} "
      f"(pas d'écart, distribution identique — cohérent)")

# Alignement sur le code PHAKTS COMPLET : une même question en années (1Y) et en mois (1M)
# n'est PAS la même variable, et un triléen (__C) entre dans l'analyse comme un choix.
survey_m = pd.DataFrame({'Age__1M': rng.integers(200, 700, 80), 'Fumeur__C': rng.choice(['oui', 'non', 'nsp'], 80)})
survey_y = pd.DataFrame({'Age__1Y': rng.integers(18, 60, 80), 'Fumeur__C': rng.choice(['oui', 'non', 'nsp'], 80)})
mixed = ms.detect_common_indicators({'En mois': survey_m, 'En années': survey_y}, mode='phakts', min_surveys=2)
assert {i['radical'] for i in mixed} == {'Fumeur__C'}, "Age__1M et Age__1Y ne doivent pas être alignés ; Fumeur__C doit l'être"
print("OK — années ≠ mois (Age__1Y / Age__1M) ; triléen __C reconnu comme indicateur")

# Mode 'exact'/'union' : la détection auto suppose l'alignement par radical PHAKTS
assert ms.detect_common_indicators(surveys, mode='exact') == []
assert ms.detect_common_indicators(surveys, mode='union') == []
print("OK — détection automatique désactivée hors mode d'alignement PHAKTS (comportement voulu)")

print()
print("=" * 70)
print("TESTS UNITAIRES PASSÉS — vérification de la route /multi-survey")
print("=" * 70)

from app import app  # noqa: E402

app.config['TESTING'] = True
client = app.test_client()

with client.session_transaction() as sess:
    sess['multi_surveys'] = []
    sess.pop('ms_auto_mode', None)
    sess.pop('ms_compared_vars', None)

import io


def _upload(name, df):
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine='openpyxl')
    buf.seek(0)
    return client.post('/multi-survey', data={
        'action': 'upload', 'files': (buf, f'{name}.xlsx'),
    }, content_type='multipart/form-data', follow_redirects=True)


_upload('tabac_femmes', survey_a)
_upload('cap_personnel', survey_b)
r = _upload('enquete_c', survey_c)
assert r.status_code == 200
print("OK — 3 enquêtes importées via la route")

# Mode manuel (par défaut) : pas de section auto visible
html = r.get_data(as_text=True)
assert 'Analyse automatique' in html  # le commutateur est toujours visible
assert 'Interopérabilité PHAKTS' not in html
print("OK — mode manuel par défaut : pas de section automatique affichée")

# Active le mode automatique
r = client.post('/multi-survey', data={'action': 'toggle_auto', 'auto_mode': 'on'},
                 follow_redirects=True)
assert r.status_code == 200
html = r.get_data(as_text=True)
assert 'Interopérabilité PHAKTS' in html
assert 'indicateur(s) commun(s) détecté' in html
assert 'Age__1Y' in html and 'Emploi__B' in html and 'Niveau_Instruction__X' in html
print("OK — mode automatique activé : indicateurs détectés affichés sur la page")

with client.session_transaction() as sess:
    assert sess.get('ms_auto_mode') is True
print("OK — préférence auto_mode persistée en session")

# Désactive à nouveau
r = client.post('/multi-survey', data={'action': 'toggle_auto'}, follow_redirects=True)
html = r.get_data(as_text=True)
assert 'Interopérabilité PHAKTS' not in html
assert 'Variables à ajouter au panier' in html
print("OK — retour au mode manuel : sélection variable par variable réaffichée")

# Nettoyage
client.post('/multi-survey', data={'action': 'reset'})

print()
print("=" * 70)
print("TOUS LES TESTS D'INTEROPÉRABILITÉ MULTI-ENQUÊTE SONT PASSÉS")
print("=" * 70)
