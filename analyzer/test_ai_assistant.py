"""
Test de l'Assistant IA d'Analyse (modules/ai_assistant.py et routes Flask)
"""
import os
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

# 2. Test sans clé API (dégradation propre)
res_no_key = ai_assistant.ask_ai("Quel est l'âge moyen ?", df=df_sample, api_key='')
assert res_no_key['success'] is False, "Sans clé API, l'appel doit renvoyer success=False"
assert res_no_key.get('needs_key') is True, "needs_key doit être True"
print("OK — ask_ai() sans clé signale proprement needs_key=True sans crash")

# 3. Test route Flask /ai-assistant
with app.test_client() as client:
    # Test avec rôle Data
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['role'] = 'data'
    
    resp = client.get('/ai-assistant')
    assert resp.status_code == 200, f"Statut inattendu: {resp.status_code}"
    assert b'SPAD AI Copilot' in resp.data, "La page doit contenir le titre de l'assistant"
    print("OK — Route GET /ai-assistant répond 200 avec l'interface complète")

    # Test route API /api/ai/set-key
    resp_key = client.post('/api/ai/set-key', json={'api_key': 'sk-ant-test-key-12345'})
    assert resp_key.status_code == 200
    assert resp_key.get_json()['success'] is True
    print("OK — Route POST /api/ai/set-key enregistre la clé en session")

    # Test route API /api/ai/chat (message vide)
    resp_empty = client.post('/api/ai/chat', json={'message': ''})
    assert resp_empty.status_code == 400
    print("OK — Route POST /api/ai/chat valide les entrées vides")

print("======================================================================")
print("TOUS LES TESTS DE L'ASSISTANT IA SONT PASSÉS AVEC SUCCÈS !")
print("======================================================================")
