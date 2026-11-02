#!/usr/bin/env python3
"""
Test script — diagnostic des données (modules/raw_analysis.py) : manquants réels ou structurels, score de qualité,
doublons, associations redondantes, recommandations, prévalence des « oui ».
"""
import re

import numpy as np
import pandas as pd

from modules import raw_analysis as ra

print("=" * 70)
print("TEST — diagnostic des données")
print("=" * 70)
checks = 0


def ok(cond, msg=''):
    global checks
    assert cond, msg
    checks += 1


rng = np.random.default_rng(3)
n = 200
region = rng.choice(['Nord', 'Sud', 'Est'], n)
district = np.array([r + '-' + str(rng.integers(1, 3)) for r in region])
fume = rng.choice(['oui', 'non'], n, p=[0.105, 0.895])
age = rng.integers(18, 70, n).astype(float)
df = pd.DataFrame({
    'GRP/Region__X': region,
    'GRP/District__X': district,
    'GRP/Profession__X': rng.choice(['sage_femme', 'infirmier', 'medecin'], n),
    'GRP/Fume__B': fume,
    'GRP/Age__1Y': age,
    'GRP/Poids__1Y': rng.normal(70, 10, n).round(1),
    'GRP/Taille__1Y': rng.normal(170, 8, n).round(1),
    'GRP/Grossesse__B': [np.nan] * n,
    'GRP/Autre_Precisez__Z': [np.nan] * n,
    'GRP/Commentaire__Z': rng.choice(['a', 'b', None], n),
})
# Grossesse : posée seulement aux femmes ; 0/1 pour les femmes, vide sinon (donc vide par construction)
sexe = rng.choice(['F', 'H'], n)
df['GRP/Sexe__X'] = sexe
df['GRP/Grossesse__B'] = np.where(sexe == 'F', rng.choice(['oui', 'non'], n), None)
df['GRP/Autre_Precisez__Z'] = np.where(rng.random(n) < 0.05, 'x', None)
types = {'GRP/Region__X': 'categorielle', 'GRP/District__X': 'categorielle', 'GRP/Profession__X': 'categorielle', 'GRP/Sexe__X': 'categorielle',
         'GRP/Fume__B': 'binaire', 'GRP/Age__1Y': 'continue', 'GRP/Poids__1Y': 'continue', 'GRP/Taille__1Y': 'continue',
         'GRP/Grossesse__B': 'binaire', 'GRP/Autre_Precisez__Z': 'texte_libre', 'GRP/Commentaire__Z': 'texte_libre'}
form = {'questions': [{'name': 'Grossesse__B', 'relevant': "${Sexe__X} = 'F'"}, {'name': 'Sexe__X', 'relevant': ''},
                      {'name': 'Fume__B', 'relevant': ''}]}

# ── Prévalence : la part des « oui », pas celle de la modalité la plus fréquente
summary = ra.descriptive_summary(df, types)
prev = next((r['prevalence'] for r in summary['binary'] if r['variable'] == 'GRP/Fume__B'), None)
ok(prev is not None and 5 < prev < 16, f'prévalence des « oui » ≈ 10 % (obtenu {prev})')
none = pd.DataFrame({'Q__B': ['non', 'non', 'autre'] * 10})
ok(ra.descriptive_summary(none, {'Q__B': 'binaire'})['binary'][0]['prevalence'] is None, 'pas de « oui » : pas de prévalence inventée')
print(f"OK — prévalence des « oui » : {prev} %")

# ── Manquants : réels ou structurels
with_form = ra.missing_profile(df, form, types)
no_form = ra.missing_profile(df, None, types)
preg = [r for r in with_form['rows'] if r['variable'] == 'GRP/Grossesse__B'][0]
ok(preg['n_applicable'] == int((sexe == 'F').sum()), 'la question ne s\'applique qu\'aux femmes')
ok(preg['n_missing_applicable'] == 0 and preg['verdict'] == 'structurel', f"grossesse : vide par construction ({preg['verdict']})")
raw_preg = [r for r in no_form['rows'] if r['variable'] == 'GRP/Grossesse__B'][0]
ok(raw_preg['pct_missing_applicable'] > 30, 'sans formulaire, le même vide compte comme un manque')
ok(with_form['real_missing_pct'] < no_form['real_missing_pct'], 'avec le formulaire, les manquants réels baissent')
other = [r for r in no_form['rows'] if r['variable'] == 'GRP/Autre_Precisez__Z'][0]
ok(other['assumed'] and other['pct_missing_applicable'] is None, 'champ « Autre, précisez » présumé structurel')
print(f"OK — manquants réels {with_form['real_missing_pct']} % avec formulaire, {no_form['real_missing_pct']} % sans")

# ── Cases d'une question à choix multiples : comptées une seule fois
multi = pd.DataFrame({'Q__X': ['a b', 'a', None, 'b', None] * 20,
                      'Q__X/a': [1, 1, np.nan, 0, np.nan] * 20, 'Q__X/b': [1, 0, np.nan, 1, np.nan] * 20,
                      'Q__X/c': [0, 0, np.nan, 0, np.nan] * 20, 'Outils__Z': [np.nan] * 100,
                      'Outils__Z/boite': [np.nan, np.nan, 1, 0, np.nan] * 20, 'Outils__Z/livret': [np.nan, np.nan, 1, 1, np.nan] * 20,
                      'Id__1Y': range(100)})
mt = {c: ('categorielle' if c.startswith('Q__X') else 'binaire' if '/' in c else 'continue') for c in multi.columns}
mp = ra.missing_profile(multi, None, mt)
ok(not [r for r in mp['rows'] if r['group'] and r['group_head']], 'la colonne-question représente déjà ses cases')
alone = multi.drop(columns=['Q__X', 'Outils__Z'])                      # export sans colonne-question : une case sert de tête
mp = ra.missing_profile(alone, None, mt)
heads = [r for r in mp['rows'] if r['group'] and r['group_head']]
ok(sorted(r['group'] for r in heads) == ['Outils__Z', 'Q__X'], f"deux questions à cases, une tête chacune ({[r['variable'] for r in heads]})")
ok(ra._option_parent('A/B__Z/option') == 'A/B__Z' and ra._option_parent('A/Section_1/Q__X') is None, 'parent d\'une case reconnu, groupe ignoré')
for frame in (multi, alone):
    anoms = ra.systematic_analysis(frame, {c: mt[c] for c in frame.columns})['anomalies']
    named = [a['variable'] for a in anoms if a['type'].startswith('Taux de manquants') or a['type'] == 'Colonne presque vide']
    ok(len(named) == len(set(named)), f'une anomalie de manquants par question, pas une par case ({named})')
print("OK — choix multiples comptés une fois")

# ── Doublons
dup = pd.concat([df, df.iloc[:10]], ignore_index=True)
d = ra.duplicate_rows(dup, types)
ok(d['n'] == 10 and d['pct'] > 4, f"10 doublons exacts retrouvés ({d['n']})")
ok(ra.duplicate_rows(df, types)['n'] == 0, 'aucun doublon dans les données de base')
dup_id = df.copy(); dup_id['_uuid'] = [f'u{i}' for i in range(n)]; dup_id.loc[5, '_uuid'] = dup_id.loc[4, '_uuid']
ok(ra.duplicate_rows(dup_id, types)['by_id'] == 1, 'doublon repéré par l\'identifiant technique')
print("OK — doublons")

# ── Score de qualité : mesures vérifiables
q = ra.data_quality_score(df, types, with_form, None, ra.duplicate_rows(df, types))
names = [c['name'] for c in q['components']]
ok(names == ['Complétude réelle', 'Unicité', 'Variables exploitables'] and not q['with_validation'], 'trois mesures sans validation')
ok(sum(c['weight'] for c in q['components']) == 70, 'les poids se répartissent sur les mesures disponibles')
v = {'pct_sans_anomalie': 50.0, 'n_signalees': 100, 'n_erreurs': 12}
qv = ra.data_quality_score(df, types, with_form, v, ra.duplicate_rows(df, types))
ok([c['name'] for c in qv['components']][1] == 'Validité' and qv['with_validation'], 'la validité entre dans le score quand elle est faite')
ok(qv['quality_score'] < q['quality_score'], 'la moitié des lignes en défaut abaisse le score')
holes = df.copy(); holes.loc[:, 'GRP/Commentaire__Z'] = np.nan; holes['GRP/Region__X'] = 'Nord'
tt = dict(types)
qh = ra.data_quality_score(holes, tt, ra.missing_profile(holes, form, tt), None, ra.duplicate_rows(holes, tt))
ok(qh['quality_score'] <= q['quality_score'], 'une colonne constante ne relève pas le score')
ok(q['label'] in ('Bonne', 'Correcte', 'À améliorer', 'Faible'), 'libellé du score')
print(f"OK — score {q['quality_score']} ({q['label']}), avec 50 % de lignes en défaut : {qv['quality_score']}")

# ── Associations : lien total = redondant, non recommandé
assoc = ra.association_matrix(df, types)
pair = [p for p in assoc['pairs'] if {p['a'], p['b']} == {'GRP/Region__X', 'GRP/District__X'}]
ok(pair and pair[0]['v'] >= ra.REDUNDANT_V and pair[0]['redundant'], 'région × district : redondantes')
ok(all(not p['redundant'] for p in assoc['pairs'] if p['v'] < ra.REDUNDANT_V), 'les autres couples ne sont pas marqués redondants')
recs = ra.build_recommendations(types, assoc, None, with_form, {})
cross = [r for r in recs if r['module'] == 'crosstabs']
ok(not cross or set(cross[0]['variables']) != {'GRP/Region__X', 'GRP/District__X'}, 'on ne recommande pas de croiser un couple redondant')
ok(all(r['rank'] == i for i, r in enumerate(recs, start=1)), 'recommandations numérotées')
for r in recs:
    if r['form']:
        ok(isinstance(r['form'], dict), 'formulaire prérempli sous forme de dictionnaire')
print(f"OK — {len(recs)} recommandations, couple redondant écarté")

# ── Corrélations de Spearman sur variables continues
corr = ra.correlation_matrix(df, types)
ok(corr is not None, 'matrice de corrélation calculée')
pairs = ra.correlation_pairs(df, types)
ok(isinstance(pairs, list) and all('rho' in p for p in pairs), 'paires avec rho de Spearman')
print("OK — corrélations de Spearman")

# ── Analyse systématique complète : décimales françaises, sans erreur
full = ra.systematic_analysis(df, types, form, None, {})
ok({'quality', 'profile', 'anomalies', 'recommendations'} <= set(full) or 'quality' in full, 'structure de l\'analyse')
notes = ' '.join(a['note'] for a in full['anomalies'])
ok(not re.search(r'\d\.\d', notes), f'décimales à la française dans les notes : {notes[:200]}')
print("OK — analyse systématique")

print(f"\n{checks} vérifications réussies.")
