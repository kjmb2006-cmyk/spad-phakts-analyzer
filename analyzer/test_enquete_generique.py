#!/usr/bin/env python3
"""
Test script — moteur d'analyse générique (modules/xlsform_dictionary.py,
modules/enquete_analyse.py, extension de modules/projets.py).

Vérifie que la détection PHAKTS (xType/period) fonctionne sur un XLSForm
réellement codifié (F5 — Tabac/Nicotine Grossesse & Allaitement, SPAD 2026)
avec parité exacte sur les scores composites déjà validés manuellement, ET
que le repli sur la grille générique (type XLSForm brut) fonctionne sur un
formulaire totalement différent, sans aucun suffixe PHAKTS — condition
posée par l'utilisateur : « l'application... doit être adaptée à tout type
de questionnaire ou d'enquête ».
"""
import io
import numpy as np
import pandas as pd

from modules import xlsform_dictionary as xd
from modules import enquete_analyse as ea
from modules import reference_data as rd

print("=" * 70)
print("TEST 1 — Détection PHAKTS + parité avec l'analyse F5 validée manuellement")
print("=" * 70)

XLSFORM_F5 = (
    "/Users/mac/Desktop/Consultance 2026/Coordination/01-Projet SPAD OMS/SPAD 2026/"
    "Projet pilot SPAD/02-Tabac Validé/Questionnaire XLSForm_PHAKTS_Kobotoolbox_Tabac/"
    "5_Tabac_Nicotine_Grossesse_Allaitement_SPAD_v3_2_AUDITE.xlsx"
)
DATA_F5 = (
    "/Users/mac/Desktop/Consultance 2026/Coordination/01-Projet SPAD OMS/Codification PHAKS/"
    "SPAD-PHAKTS-Analyzer/output/donnees_F5_brutes.xlsx"
)

import os
if not (os.path.exists(XLSFORM_F5) and os.path.exists(DATA_F5)):
    print("SKIP — fichiers F5 (hors dépôt, données réelles locales) introuvables sur ce poste.")
else:
    dic = xd.parse_xlsform(XLSFORM_F5)
    assert len(dic) == 81, f"attendu 81 variables, trouvé {len(dic)}"
    assert (dic[dic['nom'] == 'Consommation_Tabac_Actuelle__B']['suffixe_phakts'] == 'B').all()
    assert (dic[dic['nom'] == 'Age__1Y']['suffixe_phakts'] == '1Y').all()
    n_qualite = (dic['note_qualite'] != '').sum()
    assert n_qualite == 2, f"attendu 2 points de qualité détectés (Depistage_Tabac_CP{{,o}}N), trouvé {n_qualite}"
    print(f"OK — dictionnaire F5 : {len(dic)} variables, suffixes PHAKTS détectés, "
          f"{n_qualite} points de qualité (suffixe vs cardinalité)")

    DOMAINE = {
        'Connaissance_Risques_Tabac__B': ('Connaissances', 'positif', 'oui'),
        'Connaissance_Danger_Grossesse__B': ('Connaissances', 'positif', 'oui'),
        'Consommation_Tabac_Actuelle__B': ('Pratiques', 'negatif', 'oui'),
        'Tentative_Arret_Grossesse__B': ('Pratiques', 'positif', 'oui'),
    }
    for nom, (domaine, sens, favorables) in DOMAINE.items():
        idx = dic.index[dic['nom'] == nom]
        dic.loc[idx, 'domaine'] = domaine
        dic.loc[idx, 'inclure_score_composite'] = True
        dic.loc[idx, 'sens_item'] = sens
        dic.loc[idx, 'valeurs_favorables'] = favorables

    data = pd.read_excel(DATA_F5)
    dic, manquantes, extra = ea.match_columns(dic, data)
    assert len(manquantes) == 5, f"attendu 5 variables non trouvées, trouvé {len(manquantes)}"

    scores, detail, ignores = ea.compute_composite_scores(dic, data)
    conn = scores['Score_Connaissances'].mean()
    prat = scores['Score_Pratiques'].mean()
    assert abs(conn - 72.4) < 0.5, f"Score_Connaissances attendu ~72.4%, trouvé {conn}"
    assert abs(prat - 99.4) < 0.5, f"Score_Pratiques attendu ~99.4%, trouvé {prat}"
    print(f"OK — scores composites : Connaissances={round(conn, 1)}%, Pratiques={round(prat, 1)}% "
          f"(parité avec l'analyse F5 dédiée validée manuellement)")

print()
print("=" * 70)
print("TEST 2 — Repli grille générique sur un formulaire SANS suffixe PHAKTS")
print("=" * 70)

survey = pd.DataFrame([
    {'type': 'select_one gender', 'name': 'sexe', 'label::English (en)': 'Sex'},
    {'type': 'integer', 'name': 'age', 'label::English (en)': 'Age'},
    {'type': 'select_multiple symptoms', 'name': 'symptoms', 'label::English (en)': 'Symptoms'},
    {'type': 'text', 'name': 'comment', 'label::English (en)': 'Comment'},
    {'type': 'date', 'name': 'visit_date', 'label::English (en)': 'Visit date'},
])
choices = pd.DataFrame([
    {'list_name': 'gender', 'name': 'm', 'label::English (en)': 'Male'},
    {'list_name': 'gender', 'name': 'f', 'label::English (en)': 'Female'},
    {'list_name': 'symptoms', 'name': 'fever', 'label::English (en)': 'Fever'},
    {'list_name': 'symptoms', 'name': 'cough', 'label::English (en)': 'Cough'},
])
tmp_xls = '/tmp/spad_test_generic_form.xlsx'
with pd.ExcelWriter(tmp_xls) as w:
    survey.to_excel(w, sheet_name='survey', index=False)
    choices.to_excel(w, sheet_name='choices', index=False)

dic2 = xd.parse_xlsform(tmp_xls)
os.remove(tmp_xls)
assert (dic2['suffixe_phakts'] == '').all(), "un formulaire sans __B/__X ne doit détecter aucun suffixe PHAKTS"
assert dic2.set_index('nom').loc['sexe', 'traitement_statistique_recommande'].startswith('Fréquences')
assert dic2.set_index('nom').loc['age', 'traitement_statistique_recommande'].startswith('Moyenne')
assert dic2.set_index('nom').loc['comment', 'traitement_statistique_recommande'].startswith("Exclu")
print("OK — grille générique (type XLSForm brut) appliquée correctement en l'absence de suffixes PHAKTS")

print()
print("=" * 70)
print("TEST 3 — Flux applicatif complet (route Flask) sur ce même formulaire non-PHAKTS")
print("=" * 70)

rng = np.random.default_rng(1)
n = 60
fake_data = pd.DataFrame({
    'sexe': rng.choice(['m', 'f'], n),
    'age': rng.integers(5, 15, n),
    'symptoms': [' '.join(rng.choice(['fever', 'cough'], rng.integers(1, 2), replace=False)) for _ in range(n)],
    'comment': [''] * n,
    'visit_date': ['2026-01-01'] * n,
})

from modules import kobo_connector

def fake_list_assets(token, instance=None, custom_instance=None):
    return {"success": True, "assets": [{"uid": "uidTest", "name": "Test générique",
                                          "asset_type": "survey", "submission_count": n, "deployed": True}],
            "total": 1, "instance": "https://kf.kobotoolbox.org"}

def fake_load_data(token, uid, instance=None, limit=30000):
    return {"success": True, "df": fake_data, "n_obs": n, "n_vars": fake_data.shape[1],
            "pages": 1, "instance": instance}

kobo_connector.list_assets = fake_list_assets
kobo_connector.load_data = fake_load_data

from app import app
app.config['TESTING'] = True
client = app.test_client()
with client.session_transaction() as sess:
    sess['kobo_token'] = 'fake-token'
    sess['kobo_instance'] = 'https://kf.kobotoolbox.org'

ref_df = pd.DataFrame([{'code': 'm', 'cible': 30}, {'code': 'f', 'cible': 30}])
ref_buf = io.BytesIO()
ref_df.to_excel(ref_buf, index=False)
ref_buf.seek(0)

r = client.post('/projets/creer', data={
    'nom': 'Test unitaire générique', 'champ_unite': 'sexe',
    'kobo_uid': 'uidTest', 'kobo_name': 'Test générique',
    'reference': (ref_buf, 'reference.xlsx'),
}, content_type='multipart/form-data', follow_redirects=True)
assert r.status_code == 200

from modules import projets as proj
pid = proj.list_projets()[-1]['id']

with open(tmp_xls if os.path.exists(tmp_xls) else '/dev/null', 'rb') as f:
    pass  # tmp_xls déjà supprimé — on régénère juste pour l'upload
with pd.ExcelWriter(tmp_xls) as w:
    survey.to_excel(w, sheet_name='survey', index=False)
    choices.to_excel(w, sheet_name='choices', index=False)
with open(tmp_xls, 'rb') as f:
    xls_bytes = f.read()
os.remove(tmp_xls)

r = client.post(f'/projets/{pid}/xlsform', data={'xlsform': (io.BytesIO(xls_bytes), 'form.xlsx')},
                 content_type='multipart/form-data', follow_redirects=True)
assert r.status_code == 200
print("OK — route upload XLSForm")

r = client.get(f'/projets/{pid}/dictionnaire')
assert r.status_code == 200 and 'sexe' in r.get_data(as_text=True)
print("OK — route dictionnaire (affichage)")

dic3 = proj.load_dictionnaire(pid)
form_data = {f'role_{nom}': dic3.loc[dic3['nom'] == nom, 'role'].iloc[0] for nom in dic3['nom']}
r = client.post(f'/projets/{pid}/dictionnaire/save', data=form_data, follow_redirects=True)
assert r.status_code == 200
print("OK — route dictionnaire (sauvegarde)")

r = client.post(f'/projets/{pid}/calculer', follow_redirects=True)
assert r.status_code == 200
print("OK — route complétude par groupe")

r = client.post(f'/projets/{pid}/analyser', follow_redirects=True)
assert r.status_code == 200
print("OK — route analyser")

r = client.get(f'/projets/{pid}/rapport.docx')
assert r.status_code == 200 and 'wordprocessingml' in r.mimetype and len(r.data) > 3000
print(f"OK — route rapport.docx ({len(r.data)} octets)")

proj.delete_projet(pid)

print()
print("=" * 70)
print("TOUS LES TESTS DU MOTEUR D'ANALYSE GÉNÉRIQUE SONT PASSÉS")
print("=" * 70)
