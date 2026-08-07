#!/usr/bin/env python3
"""
Test script — /collecte/sync/run journalise le bon formulaire en cas
d'échec, et le menu déroulant ne retombe pas silencieusement sur l'ancien
formulaire chargé.

Contexte (retour terrain) : sélectionner un formulaire B dans le menu
« Formulaire suivi » alors qu'un formulaire A était déjà chargé pour
analyse, puis cliquer « Lancer la synchronisation » sur un B qui échoue
(ex. non déployé sur Kobo) — la ligne d'erreur dans l'historique affichait
le nom de A (session['kobo_asset_name'], jamais mis à jour en cas d'échec)
au lieu de B (le formulaire réellement ciblé par la tentative), et le menu
déroulant revenait sur A au rechargement de la page, donnant l'impression
que la sélection de B avait été ignorée alors que l'appel Kobo avait bien
ciblé B.

Vérifie que :
  - une synchronisation échouée journalise le nom du formulaire RÉELLEMENT
    ciblé (B), pas l'ancien formulaire chargé (A)
  - le menu déroulant de /collecte/sync affiche B (le dernier choisi) après
    l'échec, pas A
  - une synchronisation réussie continue de mettre à jour
    session['kobo_uid']/['kobo_asset_name'] comme avant (dataset d'analyse)
"""
import os
import sys
import tempfile
sys.path.insert(0, '.')
import app as app_module
from app import app

print("=" * 70)
print("TEST — /collecte/sync/run journalise le bon formulaire ciblé")
print("=" * 70)

def _fake_get_asset_info(token, uid, instance=None):
    names = {'uid_A': 'Formulaire A (déjà chargé)', 'uid_B': 'Formulaire B (non déployé)'}
    return {'success': True, 'uid': uid, 'name': names.get(uid, uid), 'submission_count': 0}

def _fake_kobo_load_data(token, uid, instance=None):
    if uid == 'uid_B':
        return {'success': False, 'error': "The specified asset has not been deployed"}
    return {'success': False, 'error': 'ne devrait pas être appelé pour ce test'}

def _fake_list_assets(token, instance=None):
    return {'success': True, 'assets': [
        {'uid': 'uid_A', 'name': 'Formulaire A (déjà chargé)', 'submission_count': 42},
        {'uid': 'uid_B', 'name': 'Formulaire B (non déployé)', 'submission_count': 0},
    ]}

app_module.get_asset_info = _fake_get_asset_info
app_module.kobo_load_data = _fake_kobo_load_data
app_module.list_assets = _fake_list_assets

client = app.test_client()
# collecte_state.json est un fichier partagé (chemin par défaut si
# session['collecte_state_path'] est absent) — on pointe explicitement vers
# un fichier temporaire pour ne jamais toucher l'état réel de production.
_tmp_state = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
_tmp_state.close()
os.remove(_tmp_state.name)  # append_sync_event() doit pouvoir créer le fichier lui-même

with client.session_transaction() as sess:
    sess['kobo_token'] = 'faux-token'
    sess['kobo_instance'] = 'https://kf.kobotoolbox.org'
    sess['collecte_state_path'] = _tmp_state.name
    # Simule un formulaire A déjà chargé pour analyse (comme après un
    # passage par « Analyse de données »)
    sess['kobo_uid'] = 'uid_A'
    sess['kobo_asset_name'] = 'Formulaire A (déjà chargé)'

# L'utilisateur choisit B (différent de A) dans le menu et lance la sync —
# B échoue (non déployé).
r = client.post('/collecte/sync/run', data={'uid': 'uid_B'}, follow_redirects=True)
assert r.status_code == 200
html = r.get_data(as_text=True)

# La ligne d'historique la plus récente doit porter le nom du formulaire
# réellement ciblé (B) — on isole le tableau "Historique des
# synchronisations" pour ne pas confondre avec "Formulaire A/B" qui
# apparaissent aussi comme options du menu déroulant, plus haut sur la page.
idx_hist = html.find('Historique des synchronisations')
assert idx_hist != -1, "section historique introuvable dans la page"
idx_end = html.find('</table>', idx_hist)
hist_html = html[idx_hist:idx_end if idx_end != -1 else idx_hist + 2000]
assert 'Formulaire B' in hist_html, "l'historique doit journaliser le formulaire réellement ciblé (B), pas A"
assert 'Formulaire A' not in hist_html, "le formulaire A (non ciblé par cette tentative) ne doit pas apparaître dans l'historique"
print("OK — l'échec journalise le nom du formulaire réellement ciblé (B), pas l'ancien (A)")

with client.session_transaction() as sess:
    assert sess.get('kobo_uid') == 'uid_A', "un échec ne doit pas changer le dataset chargé pour analyse"
    assert sess.get('collecte_sync_selected_uid') == 'uid_B', "la dernière sélection tentée doit être mémorisée"
print("OK — session['kobo_uid'] (dataset d'analyse) inchangé après un échec, mais la sélection B est mémorisée")

# Recharger la page : le menu déroulant doit montrer B (dernier choisi),
# pas A (silencieusement réaffiché comme si le choix avait été ignoré).
r = client.get('/collecte/sync')
html = r.get_data(as_text=True)
assert 'value="uid_B" selected' in html, "le menu doit montrer B, la dernière sélection tentée"
assert 'value="uid_A" selected' not in html, "le menu ne doit pas silencieusement retomber sur A"
print("OK — /collecte/sync (page rechargée) montre B (dernier choisi), pas A")

# Une synchronisation qui RÉUSSIT doit, elle, bien mettre à jour le dataset
# d'analyse (comportement inchangé) — reformule kobo_load_data pour que B
# réussisse cette fois.
def _fake_kobo_load_data_success(token, uid, instance=None):
    import pandas as pd
    return {'success': True, 'df': pd.DataFrame({'col1': [1, 2]}), 'n_obs': 2, 'n_vars': 1}
app_module.kobo_load_data = _fake_kobo_load_data_success

r = client.post('/collecte/sync/run', data={'uid': 'uid_B'}, follow_redirects=True)
assert r.status_code == 200
with client.session_transaction() as sess:
    assert sess.get('kobo_uid') == 'uid_B', "un succès doit bien mettre à jour le dataset d'analyse"
    assert sess.get('kobo_asset_name') == 'Formulaire B (non déployé)'
print("OK — une synchronisation réussie met bien à jour le dataset d'analyse (comportement inchangé)")

os.remove(_tmp_state.name)

print()
print("=" * 70)
print("TOUS LES TESTS DE /collecte/sync/run SONT PASSÉS")
print("=" * 70)
