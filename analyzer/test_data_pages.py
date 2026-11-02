#!/usr/bin/env python3
"""
Test script — aperçu navigable, fiche d'une soumission, dictionnaire des variables, préparation des données, diagnostic.

Un jeu de données de formulaire Kobo et son XLSForm. Vérifie ce que voit l'utilisateur :
  - l'aperçu se lit page par page : recherche, tri, filtres de colonnes, colonnes choisies, export de la vue ;
  - la fiche d'une soumission montre ses réponses sous leur libellé et les anomalies relevées à la validation ;
  - un libellé ou un type corrigé reste avec le jeu et se retrouve dans les analyses et le questionnaire exporté ;
  - une variable créée (regroupement, classes, calcul, condition, partie de date) devient une variable des analyses ;
  - un filtre écarte des lignes sans toucher au fichier, et « Rétablir » les remet.
"""
import html as htmllib
import io
import json
import os
import re
import tempfile

import numpy as np
import pandas as pd

import app as m
from modules import dataset, preview

print("=" * 70)
print("TEST — aperçu, dictionnaire, préparation des données")
print("=" * 70)
checks = 0


def ok(cond, msg=''):
    global checks
    assert cond, msg
    checks += 1


rng = np.random.default_rng(5)
n = 120
prof = rng.choice(['sage_femme', 'infirmier', 'medecin'], n, p=[.45, .35, .2])
df = pd.DataFrame({
    '_uuid': [f'u{i}' for i in range(n)],
    'start': ['2026-03-01T09:00:00'] * n, 'end': ['2026-03-01T09:20:00'] * n,
    'Date_Collecte__A': pd.to_datetime(['2026-03-01'] * 60 + ['2026-04-15'] * 60),
    'ENTETE/Code_Enqueteur__E': rng.choice(['E1', 'E2', 'E3'], n),
    'ENTETE/District__X': rng.choice(['nord', 'sud', 'est'], n),
    'METIER/Profession__X': prof,
    'METIER/Sexe__X': rng.choice(['femme', 'homme'], n),
    'METIER/Age__1Y': rng.integers(22, 62, n),
    'METIER/Poids__1Y': rng.integers(50, 95, n),
    'METIER/Taille__1Y': rng.integers(150, 190, n),
    'METIER/Commentaire__Z': ['rien'] * n,
})
df.loc[3, 'METIER/Age__1Y'] = 250            # ligne 4 : âge hors du possible
df.loc[9, '_uuid'] = df.loc[8, '_uuid']      # ligne 10 : doublon de la ligne 9
work = tempfile.mkdtemp()
path = os.path.join(work, 'kobo.xlsx')
df.to_excel(path, index=False)
form_path = os.path.join(work, 'form.xlsx')
with pd.ExcelWriter(form_path) as w:
    pd.DataFrame({'type': ['select_one prof', 'select_one sx', 'integer'],
                  'name': ['Profession__X', 'Sexe__X', 'Age__1Y'],
                  'label': ['Profession du répondant', 'Sexe', 'Âge'],
                  'required': ['yes', 'yes', 'yes'], 'relevant': ['', '', ''],
                  'constraint': ['', '', '. <= 120'], 'constraint_message': ['', '', 'Âge entre 0 et 120.']}).to_excel(w, sheet_name='survey', index=False)
    pd.DataFrame({'list_name': ['prof'] * 3 + ['sx'] * 2, 'name': ['sage_femme', 'infirmier', 'medecin', 'femme', 'homme'],
                  'label': ['Sage-femme', 'Infirmier(ère)', 'Médecin', 'Femme', 'Homme']}).to_excel(w, sheet_name='choices', index=False)

# ── Module d'aperçu seul : recherche, tri, filtres, colonnes, pagination
shown = dataset.display_frame(df, dataset.load_labels(path))
page = preview.query(shown, per_page=25)
ok(page['total'] == n and page['matched'] == n and page['pages'] == 5 and len(page['rows']) == 25, page)
ok(page['rows'][0]['line'] == 1 and page['rows'][-1]['line'] == 25, 'numéros de ligne : 1 = première soumission')
ok(preview.query(shown, page=99, per_page=25)['page'] == 5, 'page demandée trop loin : ramenée à la dernière')
cols = ['METIER/Profession__X', 'METIER/Age__1Y']
sage = preview.query(shown, columns=cols, search='sage', per_page=200)
ok(sage['matched'] == int((prof == 'sage_femme').sum()) and all('Sage' in r['cells'][0] or 'sage' in r['cells'][0].lower() for r in sage['rows']),
   'la recherche porte sur toutes les colonnes (même masquées)')
ok(preview.query(shown, search='zzz-introuvable')['matched'] == 0, 'recherche sans résultat')
asc = preview.query(shown, columns=cols, sort='METIER/Age__1Y', per_page=200)
ages = [int(r['cells'][1]) for r in asc['rows']]
ok(ages == sorted(ages), 'tri numérique (pas alphabétique)')
desc = preview.query(shown, columns=cols, sort='METIER/Age__1Y', ascending=False, per_page=10)
ok(desc['rows'][0]['cells'][1] == '250', 'tri décroissant')
filt = preview.query(shown, columns=cols, filters={'METIER/Age__1Y': '25'}, per_page=200)
ok(0 < filt['matched'] < n and all('25' in r['cells'][1] for r in filt['rows']), 'filtre de colonne')
ok(preview.query(shown, lines={4, 10}, per_page=200)['matched'] == 2, 'filtre sur des numéros de ligne')
ok(preview.cell_text(float('nan')) == '' and preview.cell_text(3.0) == '3' and preview.cell_text(3.5) == '3,5' and preview.cell_text(None) == '',
   'cellules : vide, entier, décimale française')
cols_all, rows_all = preview.full_view(shown, columns=cols, search='sage')
ok(len(rows_all) == sage['matched'] and cols_all == cols, 'la vue exportée porte toutes les lignes retenues')
print("OK — aperçu : pagination, recherche, tri numérique, filtres, colonnes, vue exportée")

m.app.config['TESTING'] = True
with m.app.test_client() as c:
    with c.session_transaction() as sess:
        sess['data_path'] = path
        sess['data_meta'] = {'name': 'kobo', 'n_obs': n, 'n_vars': df.shape[1]}
        sess['original_filename'] = 'kobo.xlsx'
    with open(form_path, 'rb') as f:
        c.post('/data/labels', data={'xlsform': (f, 'form.xlsx')}, content_type='multipart/form-data')

    # ── Page et JSON de l'aperçu
    html = c.get('/data/preview').get_data(as_text=True)
    ok('id="grid-table"' in html and 'Dictionnaire des variables' in html, 'page d\'aperçu')
    d = c.get('/data/rows?per_page=10').get_json()
    ok(d['matched'] == n and len(d['rows']) == 10 and d['pages'] == 12, d['pages'])
    ok(all('label' in col for col in d['columns']), 'colonnes avec leur libellé')
    d = c.get('/data/rows', query_string={'cols': json.dumps(['METIER/Profession__X']), 'q': 'sage-femme'}).get_json()
    ok(d['matched'] == int((prof == 'sage_femme').sum()) and d['rows'][0]['cells'][0] == 'Sage-femme', 'les modalités s\'affichent sous leur vrai nom')
    ok(c.get('/data/rows?sort=METIER/Age__1Y&dir=desc&per_page=5').get_json()['rows'][0]['line'] == 4, 'tri par âge décroissant : la ligne 4 en tête')
    csv_text = c.get('/data/rows.csv', query_string={'cols': json.dumps(['METIER/Profession__X', 'METIER/Age__1Y']), 'q': 'sage-femme'}).get_data(as_text=True)
    ok(csv_text.splitlines()[0].lstrip('﻿') == 'N° ligne,METIER/Profession__X,METIER/Age__1Y' and len(csv_text.splitlines()) == 1 + int((prof == 'sage_femme').sum()), 'export de la vue')
    print("OK — pages JSON : recherche, tri, colonnes, libellés des modalités, export CSV de la vue")

    # ── Lignes signalées par la validation
    flagged = c.get('/data/rows?flagged=1&per_page=200').get_json()
    lines = {r['line'] for r in flagged['rows']}
    ok({4, 9, 10} & lines, f'lignes signalées : {sorted(lines)[:10]}')
    ok(all(r['severity'] for r in flagged['rows']), 'chaque ligne signalée porte sa gravité')
    ok(c.get('/data/rows?flagged=erreur&per_page=200').get_json()['matched'] <= flagged['matched'], 'les erreurs sont un sous-ensemble')

    # ── Fiche d'une soumission
    card = c.get('/data/row/4').get_json()
    ok(card['line'] == 4 and card['prev'] == 3 and card['next'] == 5 and card['n'] == n, card['line'])
    items = {i['column']: i for s in card['sections'] for i in s['items']}
    ok(items['METIER/Age__1Y']['value'] == '250' and items['METIER/Age__1Y']['label'] == 'Âge', 'réponse sous le libellé de la question')
    ok(items['METIER/Profession__X']['value'] in ('Sage-femme', 'Infirmier(ère)', 'Médecin'), 'modalité sous son vrai nom')
    ok(any('250' in f['detail'] or 'Âge' in f['titre'] or '120' in f['detail'] for f in card['flags']) or card['flags'], 'anomalies de la ligne')
    ok(card['severity'] in ('erreur', 'a_verifier'), card['severity'])
    ok(card['next_flagged'] is not None or card['prev_flagged'] is not None, 'navigation de ligne signalée en ligne signalée')
    ok(c.get('/data/row/0').status_code == 404 and c.get(f'/data/row/{n + 1}').status_code == 404, 'ligne inexistante')
    ok(c.get('/data/preview?ligne=4').status_code == 200, 'lien direct vers une fiche')
    val_html = c.get('/qualite/validation').get_data(as_text=True)
    ok('/data/preview?ligne=' in val_html, 'la validation renvoie vers les fiches')
    print("OK — fiche : libellés, valeurs, anomalies, navigation ; la validation y renvoie")

    # ── Écarter une ligne depuis sa fiche
    r = c.post('/data/row/4/exclude', json={'action': 'exclude'}).get_json()
    ok(r['excluded'] and dataset.excluded_rows(path) == [4], r)
    ok(c.get('/data/row/4').get_json()['excluded'] and c.get('/data/rows?per_page=5').get_json()['rows'][3]['excluded'], 'ligne marquée écartée')
    ok(len(dataset.apply_exclusions(dataset.read_frame(path), path)) == n - 1, 'écartée de l\'analyse')
    r = c.post('/data/row/4/exclude', json={'action': 'restore'}).get_json()
    ok(not r['excluded'] and dataset.excluded_rows(path) == [], 'rétablie')
    print("OK — une ligne s'écarte et se rétablit depuis sa fiche")

    # ── Dictionnaire : libellé et type conservés
    r = c.post('/api/var-label', json={'variable': 'METIER/Poids__1Y', 'label': 'Poids en kg (déclaré)'}).get_json()
    ok(r['ok'] and dataset.user_labels(path)['METIER/Poids__1Y'] == 'Poids en kg (déclaré)', 'libellé conservé avec le jeu')
    html = c.get('/data/preview').get_data(as_text=True)
    ok('Poids en kg (déclaré)' in html and 'utilisateur' in html and 'Profession du répondant' in html, 'libellés : utilisateur et XLSForm')
    ok('obligatoire' in html and 'contrainte' in html, 'règles du formulaire dans le dictionnaire')
    ok('Poids en kg (déclaré)' in c.get('/crosstabs').get_data(as_text=True) or 'Poids en kg (déclaré)' in c.get('/descriptive').get_data(as_text=True)
       or 'Poids en kg (déclaré)' in c.get('/multivariate').get_data(as_text=True), 'libellé repris par les analyses')
    x = pd.read_excel(io.BytesIO(c.get('/data/var-types.xlsx').data), sheet_name='Questionnaire')
    row = x[x['Variable (code)'] == 'METIER/Age__1Y'].iloc[0]
    ok(row['Obligatoire'] == 'oui' and '120' in str(row['Contrainte']) and row['Source du libellé'] == 'XLSForm' and row['Question / Libellé'] == 'Âge', row.to_dict())
    ok(x[x['Variable (code)'] == 'METIER/Poids__1Y'].iloc[0]['Question / Libellé'] == 'Poids en kg (déclaré)', 'libellé saisi dans le questionnaire exporté')
    prof_row = x[x['Variable (code)'] == 'METIER/Profession__X'].iloc[0]
    ok('Sage-femme' in str(prof_row['Modalités attendues']), 'modalités sous leur libellé dans le questionnaire')
    ok(c.get('/data/var-types.csv').get_data(as_text=True).splitlines()[0].startswith('N°,Section'), 'questionnaire CSV')
    c.post('/api/var-label', json={'variable': 'METIER/Poids__1Y', 'label': ''})
    ok('METIER/Poids__1Y' not in dataset.user_labels(path), 'un libellé vide revient à l\'origine')
    r = c.post('/api/var-type', json={'variable': 'METIER/Age__1Y', 'type': 'categorielle'}).get_json()
    ok(r['ok'] and dataset.type_overrides(path) == {'METIER/Age__1Y': 'categorielle'}, 'type corrigé conservé')
    ok(m._var_types(dataset.read_frame(path))['METIER/Age__1Y'] == 'categorielle', 'le type choisi l\'emporte dans les analyses')
    ok(c.post('/api/var-type', json={'variable': 'METIER/Age__1Y', 'type': 'inconnu'}).status_code == 400, 'type inconnu refusé')
    c.post('/api/var-type', json={'variable': 'METIER/Age__1Y', 'type': ''})
    ok(dataset.type_overrides(path) == {}, 'retour au type détecté')
    print("OK — dictionnaire : libellés et types conservés, règles du formulaire et libellés dans le questionnaire")

    # ── Préparer les données
    html = c.get('/data/preparer').get_data(as_text=True)
    ok('Créer une variable' in html and 'Filtrer les lignes' in html and 'Sage-femme' in html, 'page de préparation')
    prof_values = ['sage_femme', 'infirmier', 'medecin']
    mapping = {'kind': 'mapping', 'name': 'Profession regroupée', 'source': 'METIER/Profession__X', 'map_value': prof_values,
               'map_group': ['Sages-femmes', 'Autres soignants', 'Autres soignants'], 'other': ''}
    pv = c.post('/data/preparer/apercu', data=mapping).get_json()
    ok(pv['ok'] and dict(pv['counts']) == {'Sages-femmes': int((prof == 'sage_femme').sum()), 'Autres soignants': int((prof != 'sage_femme').sum())}, pv)
    ok(c.post('/data/preparer/ajouter', data=mapping).status_code == 302, 'regroupement créé')
    bins = {'kind': 'bins', 'name': 'Classe d\'âge', 'source': 'METIER/Age__1Y', 'mode': 'edges', 'edges': '30 40 50'}
    ok(c.post('/data/preparer/ajouter', data=bins).status_code == 302, 'classes créées')
    ok(c.post('/data/preparer/ajouter', data={'kind': 'bins', 'name': 'Âge en quartiles', 'source': 'METIER/Age__1Y', 'mode': 'quantiles', 'q': '4'}).status_code == 302, 'quantiles créés')
    imc = {'kind': 'formula', 'name': 'IMC', 'expression': '${Poids__1Y} div (${Taille__1Y} div 100 * ${Taille__1Y} div 100)', 'decimals': '1'}
    pv = c.post('/data/preparer/apercu', data=imc).get_json()
    ok(pv['ok'] and pv['kind'] == 'numeric' and 10 < pv['median'] < 40, pv)
    ok(c.post('/data/preparer/ajouter', data=imc).status_code == 302, 'calcul créé')
    cond = {'kind': 'condition', 'name': 'Adulte de plus de 40 ans', 'expression': '${Age__1Y} > 40', 'yes': 'Plus de 40 ans', 'no': '40 ans ou moins'}
    ok(c.post('/data/preparer/ajouter', data=cond).status_code == 302, 'condition créée')
    ok(c.post('/data/preparer/ajouter', data={'kind': 'date_part', 'name': 'Mois de collecte', 'source': 'Date_Collecte__A', 'part': 'mois'}).status_code == 302, 'partie de date créée')
    names = [r['name'] for r in dataset.recipes(path)]
    ok(names == ['Profession regroupée', 'Classe d\'âge', 'Âge en quartiles', 'IMC', 'Adulte de plus de 40 ans', 'Mois de collecte'], names)
    frame = dataset.attach_derived(dataset.read_frame(path), path)
    ok(set(frame['Profession regroupée'].dropna()) == {'Sages-femmes', 'Autres soignants'}, 'regroupement calculé')
    ok(frame.loc[3, 'Classe d\'âge'] == '≥ 50' and set(frame['Classe d\'âge'].dropna()) <= {'< 30', '30–39', '40–49', '≥ 50'}, frame['Classe d\'âge'].unique())
    ok(frame['IMC'].dropna().between(10, 60).all(), 'IMC calculé')
    ok(set(frame['Mois de collecte'].dropna()) == {3, 4}, 'mois de la collecte')
    # une nouvelle soumission est classée à son tour (la recette se rejoue à chaque lecture)
    more = pd.concat([dataset.read_frame(path), dataset.read_frame(path).iloc[[0]].assign(**{'METIER/Age__1Y': 33})], ignore_index=True)
    ok(dataset.attach_derived(more, path)['Classe d\'âge'].iloc[-1] == '30–39', 'nouvelle soumission classée')
    print("OK — variables créées : regroupement, classes, quartiles, calcul, condition, mois ; recalculées pour les nouvelles soumissions")

    # ── Les variables créées servent partout
    for url, needle in (('/descriptive', 'Profession regroupée'), ('/crosstabs', 'Classe d\'âge'), ('/multivariate', 'Profession regroupée')):
        ok(needle in htmllib.unescape(c.get(url).get_data(as_text=True)), f'{needle} proposée dans {url}')
    html = c.get('/data/preparer').get_data(as_text=True)
    ok('Variables créées' in html and 'IMC' in html and 'Sages-femmes' in html, 'liste des variables créées avec leur répartition')
    print("OK — les variables créées sont proposées dans les statistiques, les croisements et les analyses multivariées")

    # ── Refus : nom pris, expression illisible, variable absente
    html = c.post('/data/preparer/ajouter', data=cond, follow_redirects=True).get_data(as_text=True)
    ok('existe déjà' in html, 'nom déjà pris')
    html = c.post('/data/preparer/ajouter', data={'kind': 'formula', 'name': 'Faux', 'expression': '${inconnue} * 2'}, follow_redirects=True).get_data(as_text=True)
    ok('absente des données' in html and 'Faux' not in [r['name'] for r in dataset.recipes(path)], 'expression sur une variable absente refusée avant enregistrement')
    ok(not c.post('/data/preparer/apercu', data={'kind': 'bins', 'name': 'X', 'source': 'METIER/Age__1Y', 'mode': 'edges', 'edges': 'abc'}).get_json()['ok'], 'bornes illisibles')
    ok(not c.post('/data/preparer/apercu', data={'kind': 'condition', 'name': 'X', 'expression': 'foo(${Age__1Y})'}).get_json()['ok'], 'fonction non gérée signalée')
    print("OK — refus clairs : nom pris, variable absente, bornes illisibles, fonction non gérée")

    # ── Filtre : garder / écarter, réversible
    ok(c.post('/data/preparer/apercu', data={'kind': 'filter', 'expression': "${Profession__X} = 'sage_femme'"}).get_json()['matching'] == int((prof == 'sage_femme').sum()), 'effectif du filtre')
    c.post('/data/preparer/filtrer', data={'expression': "${Profession__X} = 'sage_femme'", 'mode': 'garder'})
    ok(len(dataset.excluded_rows(path)) == int((prof != 'sage_femme').sum()), 'ne garder que les sages-femmes')
    ok(len(dataset.apply_exclusions(dataset.read_frame(path), path)) == int((prof == 'sage_femme').sum()), 'jeu filtré')
    c.post('/data/preparer/filtrer', data={'expression': "${Profession__X} = 'inexistante'", 'mode': 'garder'})
    ok(len(dataset.excluded_rows(path)) == int((prof != 'sage_femme').sum()), 'un filtre qui viderait le jeu n\'est pas appliqué')
    c.post('/data/exclusions/clear')
    ok(dataset.excluded_rows(path) == [], 'rétabli')
    c.post('/data/preparer/filtrer', data={'expression': "${Sexe__X} = 'homme'", 'mode': 'ecarter'})
    ok(len(dataset.excluded_rows(path)) > 0, 'écarter')
    c.post('/data/exclusions/clear')
    print("OK — filtre : ne garder que / écarter, jamais un jeu vide, réversible")

    # ── Suppression
    c.post('/data/preparer/supprimer', data={'name': 'IMC'})
    ok('IMC' not in [r['name'] for r in dataset.recipes(path)], 'variable supprimée')

    # ── Diagnostic : la page se charge avec le formulaire joint
    html = c.get('/data/raw').get_data(as_text=True)
    ok(c.get('/data/raw').status_code == 200 and 'Diagnostic des données' in html and 'Par où continuer' in html, 'diagnostic')
    ok('Diagnostic des données' in c.get('/analyse-donnees').get_data(as_text=True) and 'Préparer les données' in c.get('/analyse-donnees').get_data(as_text=True), 'hub et menu')

    # ── Rapports : la section porte le nom de la page et dit la même chose qu'elle
    from docx import Document
    from flask import session as flask_session
    from openpyxl import load_workbook
    from modules import raw_analysis
    report_page = c.get('/report').get_data(as_text=True)
    ok('Diagnostic des données' in report_page and 'Analyse brute' not in report_page, 'page Rapport : la section porte le nom de la page')
    reports_dir = m.app.config['REPORTS_FOLDER']
    m.app.config['REPORTS_FOLDER'] = work                      # les rapports du test ne vont pas dans le vrai dossier
    try:
        report_form = {'analyses': ['raw'], 'report_title': 'T', 'report_author': 'A'}
        word = c.post('/report', data={**report_form, 'report_format': 'word'})
        xls = c.post('/report', data={**report_form, 'report_format': 'excel'})
        pdf = c.post('/report', data={**report_form, 'report_format': 'pdf'})
    finally:
        m.app.config['REPORTS_FOLDER'] = reports_dir
    ok(word.status_code == 200 and xls.status_code == 200 and pdf.status_code == 200, 'les trois rapports se génèrent')
    ok(pdf.data[:5] == b'%PDF-' and len(pdf.data) > 5000, 'PDF valide')

    with m.app.test_request_context():
        flask_session['data_path'] = path
        flask_session['original_filename'] = 'kobo.xlsx'
        inputs = m._diagnostic_inputs()
    ok(inputs and {'df', 'types', 'labels', 'form', 'validation'} <= set(inputs) and inputs['form'], 'entrées du diagnostic partagées (formulaire joint)')
    page_quality = raw_analysis.systematic_analysis(inputs['df'], inputs['types'], inputs['form'], inputs['validation'], inputs['labels'])['quality']

    doc = Document(io.BytesIO(word.data))
    paragraphs = [p.text for p in doc.paragraphs]
    ok('1. Diagnostic des données' in paragraphs and not any('brute' in t.lower() for t in paragraphs), 'Word : section « Diagnostic des données », plus d\'« Analyse brute »')
    ok(not any(t.startswith('Erreur') for t in paragraphs), f'Word : aucune erreur interceptée dans la section ({[t for t in paragraphs if t.startswith("Erreur")]})')
    cells = [[cell.text for cell in row.cells] for t in doc.tables for row in t.rows]
    word_scores = {r[0]: r[1] for r in cells if len(r) == 3 and r[0] in {c_['name'] for c_ in page_quality['components']}}
    ok(word_scores == {c_['name']: f"{c_['value']:.1f}".replace('.', ',') for c_ in page_quality['components']},
       f'Word : les mesures du score sont celles de la page ({word_scores})')
    ok(any('Manquants bruts' in t and 'Manquants réels' in t for t in paragraphs), 'Word : manquants bruts et réels')

    wb = load_workbook(io.BytesIO(xls.data))
    ok(all(not name.startswith('Brute') for name in wb.sheetnames) and 'Diagnostic-Qualité' in wb.sheetnames and 'Diagnostic-Manquantes' in wb.sheetnames, wb.sheetnames)
    ok('Diagnostic-Erreur' not in wb.sheetnames, 'Excel : aucune erreur interceptée dans la section')
    print("OK — rapports PDF, Word et Excel : « Diagnostic des données », mêmes mesures que la page")

print()
print(f"TOUS LES TESTS DES PAGES DE DONNÉES SONT PASSÉS ({checks} vérifications)")
