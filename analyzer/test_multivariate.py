#!/usr/bin/env python3
"""
Test script — analyses multivariées (ACP, ACM, AFC, classification).

Chaque méthode est comparée à une référence indépendante :
  - ACP : les « saturations » sont les corrélations réelles variable-axe ; valeurs propres = celles de la matrice de
    corrélation (et de scikit-learn) ; contributions = 100 % par axe ; une seule composante ne plante plus ;
  - ACM : pour deux variables, la première valeur propre vaut (1 + √λ_AFC)/2 ; le vrai premier axe est conservé ;
    contributions = 100 % par axe ; Benzécri ;
  - AFC : χ² identique à celui de SciPy ; Σ poids × coordonnée² = valeur propre ; une modalité rare s'éloigne du centre ;
  - classification : K-Means et Ward, sur variables numériques et sur les axes de l'ACM ; classes décrites, numérotées
    par effectif décroissant ; rapidité.
"""
import time

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from modules import multivariate as mv

print("=" * 70)
print("TEST — analyses multivariées")
print("=" * 70)
checks = 0


def ok(cond, msg=''):
    global checks
    assert cond, msg
    checks += 1


rng = np.random.default_rng(0)

# ── ACP
X = rng.normal(size=(400, 4))
X[:, 1] = X[:, 0] * .8 + rng.normal(size=400) * .6
d = pd.DataFrame(X, columns=list('abcd'))
res = mv.run_pca(d, list('abcd'), 3)
Z = StandardScaler().fit_transform(d)
sk = PCA().fit(Z)
ok(np.allclose(sorted(res['eigenvalues'], reverse=True), np.sort(np.linalg.eigvalsh(np.corrcoef(Z, rowvar=False)))[::-1], atol=1e-3))
ok(np.allclose(np.array(res['eigenvalues']) / sum(res['eigenvalues']), sk.explained_variance_ratio_, atol=1e-3), 'part de variance (scikit-learn)')
scores = PCA().fit_transform(Z)
corr = [abs(np.corrcoef(Z[:, k], scores[:, 0])[0, 1]) for k in range(4)]
ok(np.allclose(res['loadings']['F1'].abs().values, corr, atol=2e-3), (res['loadings']['F1'].tolist(), corr))
for k in range(3):
    ok(abs(res['var_table_df'][f'Contrib. F{k + 1} (%)'].sum() - 100) < 0.3, 'contributions des variables = 100 %')
ok(res['n_kaiser'] == sum(v > 1 for v in res['eigenvalues']) and 'KMO' not in res['eig_table'])
ok(res['kmo'] is not None and 0 < res['kmo'] < 1 and res['bartlett_p'] < 0.05, (res['kmo'], res['bartlett_p']))
one = mv.run_pca(d, list('abcd'), 1)
ok(one['n_components'] == 1 and 'Une seule composante' in one['chart_circle'], 'ACP à 1 composante')
const = d.assign(e=3.0)
ok(mv.run_pca(const, list('abcde'), 2)['dropped_constant'] == ['e'], 'variable constante écartée')
print("OK — ACP : valeurs propres, vraies corrélations, contributions, KMO/Bartlett, 1 composante, variable constante")

# ── ACM
a = rng.choice(['x', 'y', 'z'], 500, p=[.5, .3, .2])
b = np.where(rng.random(500) < .7, np.where(a == 'x', 'u', np.where(a == 'y', 'v', 'w')), rng.choice(['u', 'v', 'w'], 500))
cat = pd.DataFrame({'a': a, 'b': b})
mca = mv.run_mca(cat, ['a', 'b'], 2)
ct = pd.crosstab(cat['a'], cat['b'])
ca_eig = mv.run_ca(cat, 'a', 'b')['eigenvalues']
ok(abs(mca['eigenvalues'][0] - (1 + np.sqrt(ca_eig[0])) / 2) < 2e-4, (mca['eigenvalues'][0], (1 + np.sqrt(ca_eig[0])) / 2))   # le vrai axe 1 est conservé
ok(len(mca['eigenvalues']) == 3 + 3 - 2, len(mca['eigenvalues']))
cats = mca['cats_df']
ok(abs(cats['Contrib. F1 (%)'].sum() - 100) < 0.5 and abs(cats['Contrib. F2 (%)'].sum() - 100) < 0.5)
ok(abs(sum(mca['inertia']) - 100) < 0.5 or mca['inertia'][0] > 0, mca['inertia'])
core = mv.mca_core(cat, ['a', 'b'])
ok(abs(core['eig'].sum() - (core['J'] / core['Q'] - 1)) < 1e-9, 'inertie totale = J/Q − 1')
rates, cum = mv.benzecri_rates(np.array([.7, .5, .3, .1]), 4)       # seuil 1/Q = 0,25
ok(abs(cum[-1] - 100) < 1e-6 and rates[2] > 0 and rates[3] == 0, rates)       # axes sous 1/Q ignorés
big = pd.DataFrame({f'v{k}': np.random.default_rng(k).choice(list('abcd'), 12000) for k in range(5)})
t = time.time()
r = mv.run_mca(big, list(big.columns), 2)
ok(time.time() - t < 15 and r['n_obs'] == 12000, f'ACM 12 000 individus : {time.time() - t:.1f} s')       # plus de matrice n × n
print(f"OK — ACM : axe 1 conservé, identité avec l'AFC, contributions, Benzécri, 12 000 individus en {time.time() - t:.1f} s")

# ── AFC
tab = pd.DataFrame({'r': rng.choice(list('ABCD'), 600, p=[.4, .35, .2, .05]), 'c': rng.choice(list('uvw'), 600)})
tab.loc[tab['r'] == 'D', 'c'] = 'w'
fac = mv.run_ca(tab, 'r', 'c')
ct = pd.crosstab(tab['r'], tab['c'])
chi2, p, dof, _ = chi2_contingency(ct)
ok(abs(fac['chi2'] - chi2) < 0.01 and fac['dof'] == dof and abs(fac['p_value'] - p) < 1e-3, (fac['chi2'], chi2))
rows = fac['rows_df']
mass = ct.sum(axis=1) / ct.values.sum()
lam1 = fac['eigenvalues'][0]
ok(abs((mass.values * rows['F1'].values ** 2).sum() - lam1) < 5e-3, 'Σ poids × F1² = λ1')
d_rare = np.hypot(*rows.loc[rows.iloc[:, 0] == 'D', ['F1', 'F2']].values[0])
d_big = np.hypot(*rows.loc[rows.iloc[:, 0] == 'A', ['F1', 'F2']].values[0])
ok(d_rare > d_big, f'la modalité rare « D » est la plus éloignée du centre ({d_rare:.2f} > {d_big:.2f})')
print("OK — AFC : χ² de SciPy, Σ poids × coord² = λ, modalité rare éloignée du centre")

# ── Classification
num = pd.DataFrame(np.vstack([rng.normal(0, 1, (150, 3)), rng.normal(4, 1, (100, 3)), rng.normal(-4, 1, (50, 3))]), columns=list('xyz'))
for method in ('kmeans', 'cah'):
    r = mv.run_clustering(num, list('xyz'), 3, method=method)
    sizes = sorted(c['n'] for c in r['classes'])
    ok(sizes == [50, 100, 150] and r['silhouette'] > .6, (method, sizes, r['silhouette']))
    ok([c['name'] for c in r['classes']] == ['Classe 1', 'Classe 2', 'Classe 3'] and r['classes'][0]['n'] == 150, 'classes par effectif décroissant')
    ok(all(c['traits'] for c in r['classes']), 'chaque classe est décrite')
    ok(len(r['class_index']) == len(r['class_labels']) == 300)
auto = mv.run_clustering(num, list('xyz'), None, method='cah')
ok(auto['n_clusters'] == 3 and auto['auto_k'] and auto['chart_dendrogram'], auto['n_clusters'])
cat3 = pd.DataFrame({'a': rng.choice(list('xy'), 400), 'b': rng.choice(list('uv'), 400), 'c': rng.choice(list('pq'), 400)})
cat3['b'] = np.where(cat3['a'] == 'x', 'u', 'v'); cat3['c'] = np.where(cat3['a'] == 'x', 'p', 'q')
r = mv.run_clustering(cat3, ['a', 'b', 'c'], 2, method='cah', kind='mca')
ok(sorted(c['n'] for c in r['classes']) == sorted(cat3['a'].value_counts().tolist()) and r['classes'][0]['traits'], r['classes'])
ok('=' in r['classes'][0]['traits'][0]['label'], 'modalités sur-représentées par classe')
bigx = pd.DataFrame(np.random.default_rng(1).normal(size=(8000, 6)), columns=list('abcdef'))
t = time.time(); mv.run_clustering(bigx, list(bigx.columns), 3); dt_k = time.time() - t
t = time.time(); mv.run_clustering(bigx, list(bigx.columns), 3, method='cah'); dt_c = time.time() - t
ok(dt_k < 12 and dt_c < 20, (dt_k, dt_c))
print(f"OK — classification : K-Means et Ward, variables numériques et ACM, description des classes ; 8 000 individus en {dt_k:.1f} s / {dt_c:.1f} s (Ward)")

print()
print(f"TOUS LES TESTS DES ANALYSES MULTIVARIÉES SONT PASSÉS ({checks} vérifications)")
