#!/usr/bin/env python3
"""
Test script — Post/Redirect/Get sur les pages d'analyse.

Contexte : « Statistiques descriptives », « Analyse croisée », « Analyses multivariées »,
« Rapport », l'import de fichier et la connexion Kobo répondaient à un formulaire en
affichant directement le résultat. L'historique du navigateur gardait alors un résultat
de POST : le bouton « Précédent » (ou « Retour ») affichait « Confirmer le nouvel envoi du
formulaire » et pouvait rejouer l'action. Vérifie que chaque page :
  - répond à un POST par une redirection vers elle-même (jamais par une page rendue) ;
  - retrouve les choix de l'utilisateur et affiche le résultat au rechargement qui suit ;
  - conserve ses messages (erreurs, avertissements) à travers la redirection.
"""
import io
import os
import tempfile

import numpy as np
import pandas as pd

import app as m

print("=" * 70)
print("TEST — Post/Redirect/Get sur les pages d'analyse")
print("=" * 70)

rng = np.random.default_rng(1)
n = 120
df = pd.DataFrame({
    'Sexe__X': rng.choice(['Femme', 'Homme'], n),
    'Fumeur__B': rng.choice(['OUI', 'NON'], n),
    'Age__1Y': rng.integers(18, 70, n),
    'Poids__2K': rng.normal(65, 9, n).round(1),
})
path = os.path.join(tempfile.mkdtemp(), 'prg.xlsx')
df.to_excel(path, index=False)

m.app.config['TESTING'] = True
checks = 0


def ok(cond, msg=''):
    global checks
    assert cond, msg
    checks += 1


def redirige_vers(resp, chemin):
    return resp.status_code == 302 and resp.location.split('?')[0].endswith(chemin)


with m.app.test_client() as c:
    with c.session_transaction() as sess:
        sess['data_path'] = path
        sess['data_meta'] = {'name': 'prg', 'n_obs': n, 'n_vars': 4}
        sess['original_filename'] = 'prg.xlsx'
        for k in ('descriptive_form', 'crosstabs_form', 'multivariate_form', 'report_form'):
            sess.pop(k, None)

    # ── Statistiques descriptives
    r = c.post('/descriptive', data={'cat_vars': ['Sexe__X'], 'num_vars': ['Age__1Y']})
    ok(redirige_vers(r, '/descriptive'), (r.status_code, r.location))
    page = c.get('/descriptive').get_data(as_text=True)
    with c.session_transaction() as sess:
        ok(sess['descriptive_form']['cat'] == ['Sexe__X'] and sess['descriptive_form']['num'] == ['Age__1Y'])
    ok('Sexe__X' in page and 'Age__1Y' in page)
    print("OK — /descriptive : POST → redirection, choix retrouvés au rechargement")

    # ── Analyse croisée dynamique
    r = c.post('/crosstabs', data={'rows': ['Sexe__X'], 'cols': ['Fumeur__B'], 'agg': 'count', 'pct_type': 'row'})
    ok(redirige_vers(r, '/crosstabs'), (r.status_code, r.location))
    page = c.get('/crosstabs').get_data(as_text=True)
    ok('Sexe__X' in page and 'Fumeur__B' in page and ('Khi' in page or 'χ' in page or 'Cramér' in page), "résultat du croisement absent")
    print("OK — /crosstabs : POST → redirection, tableau croisé calculé au rechargement")

    # ── Analyses multivariées
    r = c.post('/multivariate', data={'method': 'pca', 'variables': ['Age__1Y', 'Poids__2K'], 'n_components': '2', 'n_clusters': '3'})
    ok(redirige_vers(r, '/multivariate'), (r.status_code, r.location))
    page = c.get('/multivariate').get_data(as_text=True)
    ok('Valeurs propres' in page or 'valeurs propres' in page.lower() or 'Plotly' in page, "résultat de l'ACP absent")
    r = c.post('/multivariate', data={'method': 'pca', 'variables': ['Age__1Y'], 'n_components': '2', 'n_clusters': '3'})
    ok(redirige_vers(r, '/multivariate'))
    ok('Sélectionnez au moins 2 variables' in c.get('/multivariate').get_data(as_text=True), "avertissement perdu par la redirection")
    print("OK — /multivariate : POST → redirection ; l'avertissement « au moins 2 variables » survit")

    # ── Import d'un fichier : formats refusés
    r = c.post('/upload', data={'file': (io.BytesIO(b'a;b\n1;2'), 'donnees.txt')}, content_type='multipart/form-data')
    ok(redirige_vers(r, '/upload'), (r.status_code, r.location))
    ok('Format non support' in c.get('/upload').get_data(as_text=True))
    print("OK — /upload : fichier refusé → redirection, message conservé")

    # ── Connexion KoboToolbox refusée
    m.validate_token = lambda token, custom_instance=None: {'valid': False, 'error': 'Token invalide.'}
    r = c.post('/kobo/connect', data={'token': 'mauvais'})
    ok(redirige_vers(r, '/kobo/connect'), (r.status_code, r.location))
    ok('Connexion échouée' in c.get('/kobo/connect').get_data(as_text=True))
    print("OK — /kobo/connect : connexion refusée → redirection, message conservé")

    # ── Rapport : un échec de génération redirige et reprend les choix
    def boom(*a, **k):
        raise RuntimeError('échec simulé')
    m.generate_pdf_report = boom
    r = c.post('/report', data={'report_format': 'pdf', 'analyses': ['descriptive'], 'cat_vars': ['Sexe__X'],
                                'num_vars': ['Age__1Y'], 'crosstabs_row': 'Sexe__X', 'crosstabs_col': 'Fumeur__B'})
    ok(redirige_vers(r, '/report'), (r.status_code, r.location))
    page = c.get('/report').get_data(as_text=True)
    ok('Erreur génération rapport' in page and 'échec simulé' in page)
    with c.session_transaction() as sess:
        ok(sess['report_form'] == {'cat': ['Sexe__X'], 'num': ['Age__1Y'], 'bin': [], 'row': 'Sexe__X', 'col': 'Fumeur__B'}, sess.get('report_form'))
    ok('Fumeur__B' in page)
    print("OK — /report : échec de génération → redirection, message et choix conservés")

print()
print(f"TOUS LES TESTS POST/REDIRECT/GET SONT PASSÉS ({checks} vérifications)")
