#!/usr/bin/env python3
"""
Test script — contrôles issus du formulaire (XLSForm).

Un formulaire dit ce que les données ont le droit de contenir : liste de choix, question obligatoire, saut de logique
(relevant), contrainte. Vérifie l'évaluateur d'expressions et les contrôles qui s'en servent, sur un jeu où chaque
violation est connue.
"""
import os
import tempfile

import numpy as np
import pandas as pd

from modules import validation_rules as vr
from modules import xlsform_checks as xc
from modules import xlsform_expr as xe

print("=" * 70)
print("TEST — expressions et contrôles XLSForm")
print("=" * 70)
checks = 0


def ok(cond, msg=''):
    global checks
    assert cond, msg
    checks += 1


df = pd.DataFrame({'age': ['25', '17', '40', '', '130', '35'], 'sexe': ['femme', 'homme', 'femme', 'homme', 'femme', 'femme'],
                   'enceinte': ['oui', 'non', 'oui', None, None, 'non'], 'effets': ['toux cancer', 'toux', None, 'cancer asthme', 'toux', 'x']})
res = lambda name: df[name] if name in df.columns else None


def ev(expr, self_value=None):
    return xe.evaluate(expr, res, df.index, self_value=self_value).tolist()


# ── Expressions
ok(ev("${age} >= 18") == [True, False, True, False, True, True], 'comparaison numérique (vide : faux)')
ok(ev("${sexe} = 'femme' and ${age} < 100") == [True, False, True, False, False, True])
ok(ev("${sexe} = 'homme' or ${age} > 120") == [False, True, False, True, True, False])
ok(ev("not(${sexe} = 'femme')") == [False, True, False, True, False, False])
ok(ev("selected(${effets}, 'cancer')") == [True, False, False, True, False, False])
ok(ev("count-selected(${effets}) >= 2") == [True, False, False, True, False, False])
ok(ev(". >= 0 and . <= 120", self_value=df['age']) == [True, True, True, False, False, True])
ok(ev("${age} * 2 > 60") == [False, False, True, False, True, True])
ok(ev("${enceinte} != 'oui'") == [False, True, False, True, True, True])
ok(ev("string-length(${enceinte}) = 3") == [True, True, True, False, False, True])
ok(ev("regex(${sexe}, '^f')") == [True, False, True, False, True, True])
ok(ev("if(${age} > 30, 1, 0) = 1") == [False, False, True, False, True, True])
for bad in ("jr:choice-name(${sexe}, '${sexe}')", "${absente} = 1", "${age} <"):
    try:
        ev(bad)
        ok(False, f'devait refuser : {bad}')
    except xe.Unsupported:
        ok(True)
today = pd.DataFrame({'d': ['2020-01-01', '2999-01-01', None]})
ok(xe.evaluate('. <= today()', lambda n: today['d'], today.index, self_value=today['d']).tolist() == [True, False, False], 'date future')
print("OK — évaluateur : comparaisons, and/or/not, selected, count-selected, regex, if, today, et refus de l'inconnu")

# ── Lecture d'un XLSForm
form = {'questions': [
    {'name': 'age', 'type': 'integer', 'list_name': '', 'required': True, 'relevant': '', 'constraint': '. >= 0 and . <= 120', 'constraint_message': 'Âge entre 0 et 120.'},
    {'name': 'sexe', 'type': 'select_one', 'list_name': 'sx', 'required': True, 'relevant': '', 'constraint': '', 'constraint_message': ''},
    {'name': 'enceinte', 'type': 'select_one', 'list_name': 'yn', 'required': True, 'relevant': "${sexe} = 'femme' and ${age} >= 18", 'constraint': '', 'constraint_message': ''},
    {'name': 'effets', 'type': 'select_multiple', 'list_name': 'ef', 'required': False, 'relevant': '', 'constraint': '', 'constraint_message': ''},
    {'name': 'note', 'type': 'text', 'list_name': '', 'required': False, 'relevant': "jr:choice-name(${sexe}, '${sexe}') = 'x'", 'constraint': '', 'constraint_message': ''}],
    'choices': {'sx': {'femme': 'Femme', 'homme': 'Homme'}, 'yn': {'oui': 'Oui', 'non': 'Non'},
                'ef': {'toux': 'Toux', 'cancer': 'Cancer', 'asthme': 'Asthme'}}}
df['note'] = 'x'                                       # la question « note » existe dans les données : son saut est illisible → signalé
found = {c['titre'].split(' (')[0] + ' / ' + c['variables'][0] if c['variables'] else c['titre']: c for c in xc.run_checks(df, form)}
by = lambda titre, var: next(c for c in xc.run_checks(df, form) if c['titre'].startswith(titre) and var in c['variables'])
ok(by('Réponse hors de la liste', 'effets')['lignes'] == [6], by('Réponse hors de la liste', 'effets')['lignes'])                  # « x » n'est pas un choix
ok(by('Réponse obligatoire absente', 'age')['lignes'] == [4], 'âge obligatoire vide à la ligne 4')
ok(by('Réponse obligatoire absente', 'enceinte')['lignes'] == [5], by('Réponse obligatoire absente', 'enceinte')['lignes'])      # ligne 5 : femme de 130 ans, question applicable, restée vide
ok(by('Contrainte', 'age')['lignes'] == [5] and 'Âge entre 0 et 120.' in by('Contrainte', 'age')['detail'], by('Contrainte', 'age')['lignes'])
skip = by('Question répondue', 'enceinte')
ok(skip['lignes'] == [2] and skip['severite'] == vr.A_VERIFIER, skip['lignes'])      # ligne 2 : un homme de 17 ans a répondu « non » à une question réservée aux femmes majeures
info = [c for c in xc.run_checks(df, form) if c['severite'] == vr.INFO]
ok(info and 'non évalué' in info[0]['titre'] and 'note' in info[0]['detail'], info)
print("OK — contrôles : hors liste, obligatoire absent, contrainte, saut violé, expression inconnue signalée")

# ── Chaîne complète : XLSForm .xlsx → définition → contrôles
work = tempfile.mkdtemp()
path = os.path.join(work, 'form.xlsx')
with pd.ExcelWriter(path) as writer:
    pd.DataFrame({'type': ['integer', 'select_one sx', 'begin_group', 'select_multiple ef', 'end_group'], 'name': ['age', 'sexe', 'g', 'effets', 'g'],
                  'label': ['Âge', 'Sexe', 'Groupe', 'Effets', ''], 'required': ['yes', 'true', '', '', ''],
                  'relevant': ['', '', '', "${age} >= 18", ''], 'constraint': ['. <= 120', '', '', '', ''],
                  'constraint_message': ['Trop âgé', '', '', '', '']}).to_excel(writer, sheet_name='survey', index=False)
    pd.DataFrame({'list_name': ['sx', 'sx', 'ef', 'ef'], 'name': ['femme', 'homme', 'toux', 'cancer'],
                  'label': ['Femme', 'Homme', 'Toux', 'Cancer']}).to_excel(writer, sheet_name='choices', index=False)
parsed = xc.parse_xlsform(path)
ok([q['name'] for q in parsed['questions']] == ['age', 'sexe', 'effets'], [q['name'] for q in parsed['questions']])
ok(parsed['questions'][0]['required'] and parsed['questions'][2]['relevant'] == '${age} >= 18' and parsed['choices']['sx']['femme'] == 'Femme')
data = pd.DataFrame({'GRP/age': ['25', '130', '17'], 'sexe': ['femme', 'inconnu', 'homme'], 'GRP/effets': ['toux', 'toux', 'cancer']})
run = {c['titre']: c['lignes'] for c in xc.run_checks(data, parsed)}
ok(run['Contrainte du formulaire non respectée (age)'] == [2] and run['Réponse hors de la liste de choix (sexe)'] == [2], run)
ok(run["Question répondue alors qu'elle devait être sautée (effets)"] == [3], run)                      # 17 ans : « effets » n'aurait pas dû être posée
try:
    xc.parse_xlsform(os.path.join(work, 'data.xlsx')) if pd.DataFrame({'a': [1]}).to_excel(os.path.join(work, 'data.xlsx'), index=False) is None else None
    ok(False)
except ValueError as e:
    ok('XLSForm' in str(e))
struct = {'success': True, 'survey': [{'type': 'select_one sx', 'name': 'sexe', 'required': True, 'relevant': '', 'constraint': ''}],
          'choices': [{'list_name': 'sx', 'name': 'femme', 'label': 'Femme'}]}
ok(xc.from_structure(struct)['questions'][0]['required'] and xc.from_structure({'success': False}) is None)
print("OK — du classeur XLSForm (colonnes sous un chemin de groupe) aux contrôles ; structure Kobo acceptée")

print()
print(f"TOUS LES TESTS DES CONTRÔLES XLSFORM SONT PASSÉS ({checks} vérifications)")
