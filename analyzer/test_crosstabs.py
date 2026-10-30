#!/usr/bin/env python3
"""
Test script — analyse croisée.

Vérifie, contre des références indépendantes (SciPy, calcul direct) :
  - un croisement de moyennes a pour « Total » la vraie moyenne (et non la somme des moyennes), et une case sans
    observation reste vide au lieu d'afficher 0 ;
  - les pourcentages d'un croisement ont des totaux cohérents (ligne = 100 %, colonne « Total » = répartition) ;
  - le χ² de Pearson, le test exact de Fisher et l'odds ratio d'un 2 × 2 ; l'avertissement sur les effectifs théoriques
    faibles ; les résidus ajustés ;
  - la stratification (Mantel-Haenszel) et le croisement d'une question à choix multiples.
"""
import io

import numpy as np
import pandas as pd
from scipy import stats

from modules import crosstabs as ct

print("=" * 70)
print("TEST — analyse croisée")
print("=" * 70)
checks = 0


def ok(cond, msg=''):
    global checks
    assert cond, msg
    checks += 1


rng = np.random.default_rng(3)
n = 600
df = pd.DataFrame({'sexe': rng.choice(['F', 'H'], n), 'zone': rng.choice(['A', 'B', 'C'], n), 'age': rng.normal(40, 10, n).round(1)})
df.loc[df['zone'] == 'C', 'sexe'] = 'F'                                 # la combinaison (C, H) n'existe pas

# ── Moyennes : Total = vraie moyenne ; case vide ≠ 0
res = ct.tableau_croise_dynamique(df, ['sexe'], ['zone'], value_var='age', agg='mean')
piv = res['frames']['Tableau']
ok(abs(piv.loc['Total', 'Total'] - df['age'].mean()) < 1e-9, (piv.loc['Total', 'Total'], df['age'].mean()))
ok(abs(piv.loc['F', 'Total'] - df.loc[df['sexe'] == 'F', 'age'].mean()) < 1e-9)
ok(abs(piv.loc['Total', 'A'] - df.loc[df['zone'] == 'A', 'age'].mean()) < 1e-9)
ok(pd.isna(piv.loc['H', 'C']), 'une moyenne sans observation reste vide')
ok('—' in res['pivot_html'] and res['pct_html'] is None, 'case vide affichée « — »')
res = ct.tableau_croise_dynamique(df, ['sexe'], ['zone'], value_var='age', agg='mean', pct_type='row')
ok(res['pct_note'] and res['pct_html'] is None, 'pas de pourcentages sur une moyenne')
print("OK — moyennes : Total = vraie moyenne, case sans observation vide, pas de pourcentage sur une moyenne")

# ── Comptages et pourcentages
res = ct.tableau_croise_dynamique(df, ['sexe'], ['zone'], pct_type='row')
piv = res['frames']['Tableau']; pct = res['frames']['Pourcentages']
ok(piv.loc['Total', 'Total'] == n and res['n'] == n)
ok(all(abs(pct.loc[i, 'Total'] - 100) < 1e-9 for i in ['F', 'H']), 'chaque ligne = 100 %')
ok(abs(pct.loc['Total', 'A'] - piv.loc['Total', 'A'] / n * 100) < 0.06, 'ligne Total = répartition des colonnes')
colp = ct.tableau_croise_dynamique(df, ['sexe'], ['zone'], pct_type='col')['frames']['Pourcentages']
ok(all(abs(colp.loc['Total', c] - 100) < 1e-9 for c in ['A', 'B', 'C']))
multi = ct.tableau_croise_dynamique(df, ['sexe', 'zone'], [], pct_type='total')
ok(multi['n'] == n and abs(multi['frames']['Pourcentages'].iloc[-1, -1] - 100) < 1e-9)
hier = ct.tableau_croise_dynamique(df, ['zone'], ['sexe'], value_var='age', agg='nunique')
ok(hier['n'] == n)
filt = ct.tableau_croise_dynamique(df, ['sexe'], ['zone'], filters={'zone': ['A', 'B']})
ok(filt['n'] == int(df['zone'].isin(['A', 'B']).sum()))
print("OK — comptages : totaux, pourcentages ligne / colonne / total, hiérarchie, filtres")

# ── χ², Fisher, avertissement, résidus
tab = pd.crosstab(df['sexe'], df['zone'])
chi2, p, dof, _ = stats.chi2_contingency(tab, correction=False)
a = ct.association(tab)
ok(abs(a['chi2'] - chi2) < 1e-2 and abs(a['p_val'] - p) < 1e-4 and a['dof'] == dof, (a['chi2'], chi2))
small = pd.DataFrame({'a': ['x'] * 3 + ['y'] * 3 + ['x'] * 2, 'b': ['u', 'v', 'u', 'v', 'u', 'v', 'u', 'v']})
a2 = ct.association(pd.crosstab(small['a'], small['b']))
ok(a2['warning'] and 'Fisher' in a2['warning'] and a2['fisher_p'] is not None, a2['warning'])
t22 = pd.DataFrame([[20, 10], [8, 30]], index=['x', 'y'], columns=['u', 'v'])
a3 = ct.association(t22)
ok(abs(a3['fisher_p'] - stats.fisher_exact(t22.values)[1]) < 1e-4 and abs(a3['odds_ratio'] - (20 * 30) / (10 * 8)) < 0.01, a3['odds_ratio'])
lo, hi = a3['or_ci']
ok(lo < a3['odds_ratio'] < hi)
ok(ct.association(pd.DataFrame({'u': [5, 5]}, index=['x', 'y'])) is None, 'tableau à 1 colonne : pas de test')
adj = a['residuals']
exp = a['expected']
manual = (tab - exp) / np.sqrt(exp * np.outer(1 - tab.sum(axis=1) / n, 1 - tab.sum(axis=0) / n))
ok(np.allclose(adj.values, manual.values), 'résidu ajusté = (O−E)/√(E(1−l)(1−c))')
ok(all(abs(c['residual']) > 1.96 for c in a['top_cells']))
rep = ct.tableau_croise(df, 'sexe', 'zone')
ok(rep['n'] == n and rep['ct_html'] and rep['residuals_html'] and rep['top_cells'])
print("OK — χ² de SciPy, Fisher et odds ratio, avertissement effectifs faibles, résidus ajustés, rapport")

# ── Stratification
m = 3000
sex = rng.choice(['F', 'H'], m)
site = rng.choice(['urbain', 'rural'], m, p=[.5, .5])
base = np.where(site == 'urbain', .6, .2)                            # le site influence le résultat…
treat = np.where(rng.random(m) < np.where(site == 'urbain', .7, .3), 'oui', 'non')       # … et l'exposition : confusion
out = np.where(rng.random(m) < base, 'guéri', 'non guéri')
d3 = pd.DataFrame({'traitement': treat, 'résultat': out, 'site': site})
res = ct.tableau_croise_dynamique(d3, ['traitement'], ['résultat'], layer='site')
st = res['strata']
ok(st and len(st['levels']) == 2 and st['mh'] and st['crude_or'], st)
ok(st['confounding'] and abs(np.log(st['mh'][0])) < abs(np.log(st['crude_or'])), (st['mh'], st['crude_or']))     # l'OR brut s'éloigne trop de 1
ok(0.6 < st['mh'][0] < 1.6, f"pas d'effet réel du traitement : OR commun proche de 1 ({st['mh'][0]})")
print("OK — stratification : odds ratio brut biaisé par le site, odds ratio de Mantel-Haenszel proche de 1")

# ── Choix multiples
q = 500
grp = pd.Series(rng.choice(['A', 'B'], q))
mc = pd.DataFrame({'Effets/Cancer': (rng.random(q) < np.where(grp == 'A', .7, .3)).astype(int),
                   'Effets/Toux': (rng.random(q) < .5).astype(int),
                   'Effets/Rien': (rng.random(q) < .1).astype(int), 'groupe': grp})
r = ct.croisement_choix_multiples(mc, ['Effets/Cancer', 'Effets/Toux', 'Effets/Rien'], 'groupe', 'Effets')
byname = {x['option']: x for x in r['rows']}
ok(byname['Cancer']['significant'] and not byname['Toux']['significant'], [(x['option'], x['p_val'], x['q_val']) for x in r['rows']])
ok(r['n_respondents'] == q and abs(byname['Toux']['pct_all'] - mc['Effets/Toux'].mean() * 100) < 0.06)
pa = float(r['frames']['% citant'].set_index('Choix').loc['Cancer', 'A'])
ok(abs(pa - mc.loc[grp == 'A', 'Effets/Cancer'].mean() * 100) < 0.06, pa)
ok(r['n_significant'] == 1 and r['chart_heat'])
unanswered = mc.copy(); unanswered.loc[:99, ['Effets/Cancer', 'Effets/Toux', 'Effets/Rien']] = np.nan
ok(ct.croisement_choix_multiples(unanswered, ['Effets/Cancer', 'Effets/Toux', 'Effets/Rien'], 'groupe')['n_respondents'] == q - 100, 'les non-répondants sont exclus')
print("OK — choix multiples × variable : parts par catégorie, tests corrigés entre choix, non-répondants exclus")

# ── Export Excel
xl = ct.export_workbook(dict(res, auto_comment='Lecture'))
sheets = pd.read_excel(io.BytesIO(xl), sheet_name=None)
ok('Synthèse' in sheets and 'Tableau' in sheets and 'Strates' in sheets, list(sheets))
print("OK — export Excel : synthèse, tableaux, strates")

print()
print(f"TOUS LES TESTS D'ANALYSE CROISÉE SONT PASSÉS ({checks} vérifications)")
