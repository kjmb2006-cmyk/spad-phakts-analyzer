#!/usr/bin/env python3
"""
Test script — repli propre de l'assistance IA (Phase C) quand ANTHROPIC_API_KEY
n'est pas configurée.

Contexte : modules/ai_form_assist.py doit dégrader proprement (aucun appel
réseau, aucune exception) en l'absence de clé API — le bouton « Suggérer avec
l'IA » dans Suivi multi-formulaires doit alors rester masqué et la détection
par préfixe (Phase B) doit continuer de fonctionner seule. Vérifie :
  - available() renvoie False sans clé, sans lever d'exception
  - suggest_for_kobo_form() renvoie {'available': False, 'error': None} sans
    tenter le moindre appel réseau (le client anthropic n'est jamais construit)
  - /suivi n'affiche pas le bouton IA (ai_available=False côté template)
  - /suivi/ai_suggest renvoie available=False au lieu de planter
"""
import os

# Isole ce process de toute clé héritée de l'environnement ambiant, pour que
# le test reste valide même si ANTHROPIC_API_KEY est exportée dans le shell
# appelant (ex. session manuelle de test avec la vraie clé).
os.environ.pop('ANTHROPIC_API_KEY', None)

print("=" * 70)
print("TEST — Repli propre de l'assistance IA sans ANTHROPIC_API_KEY")
print("=" * 70)

from modules import ai_form_assist as ai  # noqa: E402

assert os.environ.get('ANTHROPIC_API_KEY') is None
assert ai.available() is False
print("OK — available() est False sans clé API")

result = ai.suggest_for_kobo_form("5_PNLTA_SPAD_Fiche_Femmes_Enceintes")
assert result == {'available': False, 'error': None}, result
print("OK — suggest_for_kobo_form() renvoie un repli propre, sans appel réseau")

assert ai._client is None and ai._client_checked is True
print("OK — aucun client anthropic construit (pas de tentative d'appel réseau)")

print()
print("=" * 70)
print("TESTS UNITAIRES PASSÉS — vérification des routes Flask")
print("=" * 70)

import app as app_module  # noqa: E402
from app import app  # noqa: E402
from modules import kobo_track  # noqa: E402

# app.py fait `from modules.kobo_connector import list_assets` (nom lié
# directement dans son propre espace de noms) — patcher kobo_connector.list_assets
# n'aurait donc aucun effet ici ; il faut patcher app.list_assets lui-même
# pour simuler un compte Kobo avec un formulaire non encore suivi.
def _fake_list_assets(token, instance=None, custom_instance=None):
    return {"success": True, "assets": [{"uid": "u_ai_test", "name": "Nouveau_Formulaire_Atypique", "submission_count": 3, "deployed": True}], "total": 1}
app_module.list_assets = _fake_list_assets

app.config['TESTING'] = True
client = app.test_client()

with client.session_transaction() as sess:
    sess['kobo_token'] = 'fake'

r = client.get('/suivi')
assert r.status_code == 200
html = r.get_data(as_text=True)
# Le nom de classe 'btn-ai-suggest' apparaît toujours dans le <script> de la
# page (querySelectorAll côté JS, ligne fixe) — seule la présence de la
# balise <button> elle-même (gardée par {% if ai_available %}) doit varier.
assert 'btn btn-sm btn-outline-info btn-ai-suggest' not in html, \
    "le bouton IA ne doit pas apparaître sans clé API"
print("OK — /suivi masque le bouton « Suggérer avec l'IA » sans clé API")

r = client.post('/suivi/ai_suggest', data={'name': '5_PNLTA_SPAD_Fiche_Femmes_Enceintes'})
assert r.status_code == 200
data = r.get_json()
assert data == {'available': False, 'error': None}, data
print("OK — /suivi/ai_suggest renvoie available=False sans clé API (pas de 500)")

r = client.post('/suivi/ai_suggest', data={})
assert r.status_code == 400
print("OK — /suivi/ai_suggest refuse une requête sans nom de formulaire (400)")

print()
print("=" * 70)
print("TEST — le bouton apparaît bien quand une clé API est configurée")
print("=" * 70)

# Clé factice : on ne veut vérifier ici que le fléchage serveur->template
# (ai_available), pas la pertinence d'un vrai appel réseau — donc on force
# la reconstruction du client sans clé réelle ni appel à messages.create().
os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-test-fake-key-for-gating-check'
ai._client_checked = False
ai._client = None
try:
    assert ai.available() is True, "le package anthropic doit permettre de construire un client avec n'importe quelle clé syntaxiquement valide"
    r = client.get('/suivi')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'btn btn-sm btn-outline-info btn-ai-suggest' in html, \
        "le bouton IA doit apparaître quand une clé API est configurée"
    print("OK — /suivi affiche le bouton « Suggérer avec l'IA » quand la clé est présente")
finally:
    os.environ.pop('ANTHROPIC_API_KEY', None)
    ai._client_checked = False
    ai._client = None

print()
print("=" * 70)
print("TOUS LES TESTS DE REPLI IA SONT PASSÉS")
print("=" * 70)
