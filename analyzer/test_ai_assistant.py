"""
Test de l'Assistant IA d'Analyse (modules/ai_assistant.py et routes Flask)

Contexte (revue de la mise à jour « SPAD AI Copilot ») : la clé API
n'est plus lue ni écrite depuis la session utilisateur (voir
modules/ai_assistant.py::get_api_key()) — même convention que
modules/ai_form_assist.py, uniquement ANTHROPIC_API_KEY côté serveur. La
route /api/ai/set-key (qui stockait la clé en clair dans le cookie de
session) a été supprimée.
"""
import os
import sys
sys.path.insert(0, '.')
import pandas as pd
from app import app
from modules import ai_assistant

print("======================================================================")
print("TEST — Assistant IA d'Analyse (SPAD AI Copilot)")
print("======================================================================")

# 1. Test construction de contexte
df_sample = pd.DataFrame({
    'age': [25, 30, 45, 50, None],
    'district': ['Nord', 'Sud', 'Nord', 'Est', 'Sud'],
    'vaccine': ['Oui', 'Non', 'Oui', 'Oui', 'Non']
})

ctx = ai_assistant.build_data_context(df=df_sample)
assert '5 observations' in ctx, "Le nombre d'observations doit être dans le contexte"
assert '3 variables' in ctx, "Le nombre de variables doit être dans le contexte"
assert 'age' in ctx and 'district' in ctx, "Les noms de colonnes doivent figurer dans le contexte"
print("OK — build_data_context() génère un résumé statistique fidèle")

# 2. Test sans clé API (dégradation propre) — isolé de tout ANTHROPIC_API_KEY
# hérité de l'environnement ambiant, pour que ce test reste valide même si
# une clé réelle est exportée dans le shell appelant.
_had_anthropic_key = 'ANTHROPIC_API_KEY' in os.environ
_had_claude_key = 'CLAUDE_API_KEY' in os.environ
_backup_anthropic = os.environ.pop('ANTHROPIC_API_KEY', None)
_backup_claude = os.environ.pop('CLAUDE_API_KEY', None)
try:
    assert ai_assistant.is_available() is False
    res_no_key = ai_assistant.ask_ai("Quel est l'âge moyen ?", df=df_sample)
    assert res_no_key['success'] is False, "Sans clé API, l'appel doit renvoyer success=False"
    assert res_no_key.get('needs_key') is True, "needs_key doit être True"
    print("OK — ask_ai() sans clé (serveur) signale proprement needs_key=True sans crash")
finally:
    if _had_anthropic_key:
        os.environ['ANTHROPIC_API_KEY'] = _backup_anthropic
    if _had_claude_key:
        os.environ['CLAUDE_API_KEY'] = _backup_claude

# 3. get_api_key()/ask_ai() n'exposent plus aucun moyen de fournir une clé
# API depuis l'appelant (session ou requête) — uniquement le serveur.
import inspect
assert list(inspect.signature(ai_assistant.get_api_key).parameters) == [], \
    "get_api_key() ne doit accepter aucun paramètre — clé serveur uniquement"
assert 'api_key' not in inspect.signature(ai_assistant.ask_ai).parameters, \
    "ask_ai() ne doit plus accepter de clé API fournie par l'appelant"
print("OK — l'API du module n'expose plus aucun moyen de fournir une clé côté client")

# 4. Test route Flask /ai-assistant
with app.test_client() as client:
    # Test avec rôle Data
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['role'] = 'data'

    resp = client.get('/ai-assistant')
    assert resp.status_code == 200, f"Statut inattendu: {resp.status_code}"
    assert b'SPAD AI Copilot' in resp.data, "La page doit contenir le titre de l'assistant"
    print("OK — Route GET /ai-assistant répond 200 avec l'interface complète")

    # La route /api/ai/set-key a été supprimée (stockait la clé API en clair
    # dans le cookie de session, sans backend de session serveur configuré).
    resp_key = client.post('/api/ai/set-key', json={'api_key': 'sk-ant-test-key-12345'})
    assert resp_key.status_code == 404, "/api/ai/set-key doit avoir disparu (plus de clé côté client)"
    print("OK — Route POST /api/ai/set-key n'existe plus (404)")

    with client.session_transaction() as sess:
        assert 'anthropic_api_key' not in sess, "aucune clé API ne doit jamais transiter par la session"

    # Test route API /api/ai/chat (message vide)
    resp_empty = client.post('/api/ai/chat', json={'message': ''})
    assert resp_empty.status_code == 400
    print("OK — Route POST /api/ai/chat valide les entrées vides")

print("======================================================================")
print("TOUS LES TESTS DE L'ASSISTANT IA SONT PASSÉS AVEC SUCCÈS !")
print("======================================================================")
