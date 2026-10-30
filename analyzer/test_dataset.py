#!/usr/bin/env python3
"""
Test script — jeu de données chargé : variables dérivées, lignes écartées, libellés, choix multiples, types.
"""
import os
import tempfile

import numpy as np
import pandas as pd

from modules import choice_labels, dataset

print("=" * 70)
print("TEST — jeu de données chargé (modules/dataset.py)")
print("=" * 70)
checks = 0


def ok(cond, msg=''):
    global checks
    assert cond, msg
    checks += 1


work = tempfile.mkdtemp()
path = os.path.join(work, 'data.xlsx')
rng = np.random.default_rng(0)
n = 120
df = pd.DataFrame({'Profession__X': rng.choice(['sage_femme', 'infirmier', 'medecin'], n),
                   'Age__1Y': rng.integers(20, 60, n),
                   'Date_Collecte__A': ['2026-01-01'] * n, 'Code_Enqueteur__E': rng.choice(['E1', 'E2'], n),
                   'Commentaire__Z': ['rien à signaler'] * n, 'start': ['2026-01-01T08:00:00'] * n})
df.to_excel(path, index=False)

# ── Lecture : un fichier lu une fois par version, copie rendue
a = dataset.read_frame(path)
a.loc[0, 'Age__1Y'] = 999
ok(dataset.read_frame(path).loc[0, 'Age__1Y'] != 999, 'la copie rendue ne contamine pas le cache')
print("OK — lecture en cache, copie isolée")

# ── Variables dérivées
dataset.save_derived(path, 'Classe_CAH', {0: 'Classe 1', 1: 'Classe 2', 5: 'Classe 1'}, n)
full = dataset.attach_derived(dataset.read_frame(path), path)
ok(list(full['Classe_CAH'].iloc[:3]) == ['Classe 1', 'Classe 2', None] or pd.isna(full['Classe_CAH'].iloc[2]), full['Classe_CAH'].iloc[:3].tolist())
ok(full['Classe_CAH'].notna().sum() == 3 and dataset.derived_names(path) == ['Classe_CAH'])
bigger = pd.concat([dataset.read_frame(path), dataset.read_frame(path).head(10)], ignore_index=True)       # 10 soumissions arrivées depuis
ok(len(dataset.attach_derived(bigger, path)) == n + 10 and dataset.attach_derived(bigger, path)['Classe_CAH'].notna().sum() == 3)
ok(dataset.delete_derived(path, 'Classe_CAH') and dataset.derived_names(path) == [])
print("OK — variables dérivées : enregistrement, jointure, soumissions ajoutées après coup, suppression")

# ── Lignes écartées : l'index d'origine est conservé (index + 1 = numéro de ligne)
dataset.set_excluded(path, [2, 5, 7], note='erreurs')
kept = dataset.apply_exclusions(dataset.read_frame(path), path)
ok(len(kept) == n - 3 and 1 not in kept.index and 4 not in kept.index and 6 not in kept.index, kept.index[:8].tolist())
ok(dataset.excluded_rows(path) == [2, 5, 7] and dataset.excluded_info(path)['note'] == 'erreurs')
dataset.clear_excluded(path)
ok(len(dataset.apply_exclusions(dataset.read_frame(path), path)) == n and dataset.excluded_rows(path) == [])
print("OK — lignes écartées : retirées, numéros d'origine conservés, rétablies")

# ── Choix multiples : une colonne « a b c » éclatée en une colonne 0/1 par choix
multi = pd.DataFrame({'Effets__X': ['cancer toux', 'cancer', 'toux', None, 'cancer toux asthme', 'asthme', 'toux', 'cancer', 'cancer asthme', 'toux'] * 3,
                      'Prof__X': ['sage femme', 'infirmier'] * 15, 'Classe': ['Classe 1', 'Classe 2', 'Classe 3'] * 10,
                      'Q__X': ['oui', 'non', 'ne sait pas'] * 10})
out = dataset.expand_multiple(multi)
ok('Effets__X/Cancer' in out.columns and 'Effets__X' not in out.columns, list(out.columns))
ok(out['Effets__X/Cancer'].iloc[0] == 1 and out['Effets__X/Asthme'].iloc[0] == 0 and pd.isna(out['Effets__X/Cancer'].iloc[3]))
ok(out['Effets__X/Cancer'].sum() == 15, out['Effets__X/Cancer'].sum())
for col in ('Prof__X', 'Classe', 'Q__X'):
    ok(col in out.columns, f'« {col} » ne doit pas être éclatée')            # « sage femme », « Classe 1 », « ne sait pas » : pas des choix cochés
labels = {'questions': {}, 'choices': {'Effets__X': {'cancer': 'Cancer du poumon', 'toux': 'Toux chronique', 'asthme': 'Asthme'}}, 'multiple': ['Effets__X']}
shown = dataset.expand_multiple(multi, labels)
ok('Effets__X/Cancer du poumon' in shown.columns and 'Effets__X/Toux chronique' in shown.columns, list(shown.columns))
declared = pd.DataFrame({'M__X': ['a', 'b', 'a', 'b', 'a']})
ok('M__X' in dataset.expand_multiple(declared).columns)                          # une seule valeur par ligne : rien à éclater
print("OK — choix multiples : éclatés avec leurs libellés ; « Sage femme », « Classe 1 », « Ne sait pas » non confondus")

# ── Libellés et vue « analyste »
labels = {'questions': {'Profession__X': 'Profession du répondant'},
          'choices': {'Profession__X': {'sage_femme': 'Sage-femme', 'infirmier': 'Infirmier(ère)', 'medecin': 'Médecin'}}, 'multiple': []}
ok(dataset.save_labels(path, labels) and dataset.load_labels(path)['choices']['Profession__X']['medecin'] == 'Médecin')
view = dataset.display_frame(dataset.read_frame(path), dataset.load_labels(path))
ok(set(view['Profession__X']) <= {'Sage-femme', 'Infirmier(ère)', 'Médecin'}, set(view['Profession__X']))
bare = dataset.display_frame(dataset.read_frame(path), None)
ok(set(bare['Profession__X']) <= {'Sage femme', 'Infirmier', 'Medecin'}, set(bare['Profession__X']))           # sans XLSForm : nom reconstitué
cl = dataset.column_labels(['METIER/Section_1/Profession__X', 'Age__1Y'], dataset.load_labels(path))
ok(cl == {'METIER/Section_1/Profession__X': 'Profession du répondant'}, cl)
dataset.clear_labels(path)
ok(dataset.column_labels(['Profession__X'], dataset.load_labels(path)) == {})
print("OK — libellés : vrais noms avec l'XLSForm, noms reconstitués sans, question retrouvée malgré le chemin de groupe")

# ── Cases d'un choix multiple déjà éclatées par Kobo
native = pd.DataFrame({'G/Effets__X/maladies_respiratoires': [1, 0, 1], 'G/Effets__X/cancer': [0, 1, 1], 'G/Autre/ne_pas_toucher': [1, 1, 0], 'Age__1Y': [30, 40, 50]})
pretty = dataset.rename_option_columns(native)
ok('G/Effets__X/Maladies respiratoires' in pretty.columns and 'G/Effets__X/Cancer' in pretty.columns, list(pretty.columns))
ok('G/Autre/ne_pas_toucher' in pretty.columns and 'Age__1Y' in pretty.columns, 'seules les options d\'une question à choix sont renommées')
named = dataset.rename_option_columns(native, {'questions': {}, 'choices': {'Effets__X': {'maladies_respiratoires': 'Maladies respiratoires', 'cancer': 'Cancer du poumon'}}, 'multiple': ['Effets__X']})
ok('G/Effets__X/Cancer du poumon' in named.columns, list(named.columns))
clash = dataset.rename_option_columns(native, {'questions': {}, 'choices': {'Effets__X': {'maladies_respiratoires': 'Pareil', 'cancer': 'Pareil'}}, 'multiple': []})
ok('G/Effets__X/cancer' in clash.columns, 'deux choix au même libellé : rien n\'est renommé')
print("OK — cases de choix multiples déjà éclatées : libellé du choix, ou nom mis en forme, sans confusion possible")

# ── Types d'après l'affixe PHAKTS
types = dataset.analysis_var_types(dataset.read_frame(path))
ok(types['Date_Collecte__A'] == 'date' and types['Code_Enqueteur__E'] == 'identifiant' and types['Commentaire__Z'] == 'texte_libre', types)
ok(types['start'] == 'technique' and types['Profession__X'] == 'categorielle' and types['Age__1Y'] == 'continue', types)
ok(dataset.section_of('METIER_ETUDE/Section_1/Age__1Y') == 'METIER_ETUDE/Section_1' and dataset.section_of('Age__1Y') == '')
print("OK — types : date, identifiant, texte libre et variables techniques écartés des tris à plat")

print()
print(f"TOUS LES TESTS DU JEU DE DONNÉES SONT PASSÉS ({checks} vérifications)")
