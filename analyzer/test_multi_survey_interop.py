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

assert set(by_radical) == {'Age', 'Emploi', 'Niveau_Instruction'}, by_radical.keys()
print("OK — exactement les 3 indicateurs communs à >=2 enquêtes détectés (pas les autres)")

assert by_radical['Age']['n_surveys'] == 3 and by_radical['Age']['suffix'] == '1Y'
assert by_radical['Emploi']['n_surveys'] == 2 and by_radical['Emploi']['suffix'] == 'B'
assert by_radical['Niveau_Instruction']['n_surveys'] == 2 and by_radical['Niveau_Instruction']['suffix'] == 'X'
print("OK — xType et nombre d'enquêtes couvertes corrects pour chaque indicateur")

assert 'Poste_Occupe' not in by_radical, "texte libre (__Z) doit être exclu de l'analyse quantitative"
assert 'Consommation_Tabac' not in by_radical, "présent dans 1 seule enquête -> exclu (min_surveys=2)"
assert 'Zone' not in by_radical, "présent dans 1 seule enquête -> exclu (min_surveys=2)"
print("OK — texte libre et indicateurs mono-enquête correctement exclus")

results = ms.auto_analyze(surveys, mode='phakts', min_surveys=2)
by_var = {r['variable']: r for r in results}
assert set(by_var) == {'Age', 'Emploi', 'Niveau_Instruction'}
print(f"OK — auto_analyze() calcule bien les {len(results)} comparaisons automatiquement")

assert by_var['Age']['kind'] == 'continuous'
assert by_var['Age']['test']['test'] in ('ANOVA', 'Kruskal-Wallis')
assert by_var['Age']['test']['p_value'] < 0.05, "les plages d'âge diffèrent nettement entre enquêtes"
print(f"OK — Age : test {by_var['Age']['test']['test']}, p={by_var['Age']['test']['p_value']} (écart détecté, attendu)")

assert by_var['Emploi']['kind'] == 'categorical'
assert by_var['Emploi']['test']['test'] == 'χ² (indépendance)'
assert by_var['Emploi']['test']['p_value'] < 0.05, "60% vs 90% d'emploi doit être détecté comme significatif"
print(f"OK — Emploi : {by_var['Emploi']['test']['test']}, p={by_var['Emploi']['test']['p_value']} (écart détecté, attendu)")

assert by_var['Niveau_Instruction']['test']['p_value'] >= 0.05, "distribution identique -> pas d'écart significatif attendu"
print(f"OK — Niveau_Instruction : p={by_var['Niveau_Instruction']['test']['p_value']} "
      f"(pas d'écart, distribution identique — cohérent)")

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
assert 'Age' in html and 'Emploi' in html and 'Niveau_Instruction' in html
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
