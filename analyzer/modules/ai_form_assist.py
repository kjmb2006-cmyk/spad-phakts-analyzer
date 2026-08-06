"""
SPAD Analyzer — Assistance IA pour Suivi multi-formulaires

Complète la détection par préfixe (reference_data.guess_form_type(), basée
sur forms_registry.name_hints()) par une suggestion via l'API Claude quand
le nom d'un formulaire Kobo ne correspond à aucun préfixe connu du registre
— pour qu'un formulaire pas encore répertorié reçoive quand même une
proposition de type et de cible, que l'utilisateur valide ou corrige avant
d'enregistrer. JAMAIS d'enregistrement automatique : voir /suivi/ai_suggest
(app.py) et le bouton « Suggérer avec l'IA » (templates/suivi.html), qui ne
font que pré-remplir les champs du formulaire de suivi.

Nécessite ANTHROPIC_API_KEY (variable d'environnement — réutilise la même
clé que PHAKTS Studio côté Node, voir api/grammar.js). Absente par défaut :
available() renvoie False, aucun appel réseau, aucune exception — la
détection par préfixe (Phase B) continue de fonctionner seule.
"""
import os
import json

from modules import forms_registry

MODEL = os.environ.get('PHAKTS_MODEL', 'claude-sonnet-5')

_client = None
_client_checked = False


def available():
    """Vrai si une clé API est configurée ET le package anthropic installé —
    sans lever d'exception si l'un des deux manque (dégradation propre)."""
    return _get_client() is not None


def _get_client():
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    api_key = (os.environ.get('ANTHROPIC_API_KEY') or '').strip()
    if not api_key:
        return None
    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=api_key)
    except Exception:
        _client = None
    return _client


def _extract_json(text):
    """Le modèle est prié de ne renvoyer que du JSON, mais on reste tolérant
    à un texte entourant (ex. ```json ... ```) plutôt que de planter."""
    text = text.strip()
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


def suggest_for_kobo_form(kobo_name, sample_columns=None):
    """Propose un type de formulaire SPAD (parmi le registre actif, ou un
    nouveau formulaire) et une cible plausible, à partir du nom d'un
    formulaire Kobo — et, si disponibles, d'un échantillon de noms de
    colonnes (aide à distinguer deux formulaires au nom proche).

    Renvoie toujours un dict, jamais None : {'available': bool, 'error': str
    ou None, 'code': str ou None, 'confidence': 'haute'|'moyenne'|'faible' ou
    None, 'is_new': bool, 'suggested_label': str ou None, 'target': int ou
    None, 'rationale': str ou None} — 'available' à False (clé absente ou
    appel échoué) signifie : rien à afficher, retomber sur la détection par
    préfixe existante."""
    client = _get_client()
    if client is None:
        return {'available': False, 'error': None}

    known_forms = [
        {'code': f['code'], 'label': f['label'], 'name_hint': f.get('name_hint', '')}
        for f in forms_registry.all_forms(include_inactive=False)
    ]
    ref = None
    try:
        from modules import reference_data as rd
        ref = rd.load()
    except Exception:
        pass
    n_etab = len(ref['etablissements']) if ref else None
    n_district = len(ref['districts']) if ref else None

    prompt = (
        "Tu assistes le suivi de formulaires KoboToolbox pour une enquête de santé publique (SPAD).\n\n"
        f"Formulaires déjà connus du registre : {json.dumps(known_forms, ensure_ascii=False)}\n\n"
        f"Nom du formulaire Kobo à classer : {kobo_name!r}\n"
    )
    if sample_columns:
        prompt += f"Échantillon de noms de colonnes de ce formulaire : {json.dumps(sample_columns[:40], ensure_ascii=False)}\n"
    if n_etab and n_district:
        prompt += f"\nRéférentiel terrain : {n_etab} établissements, {n_district} districts.\n"
    prompt += (
        "\nRéponds UNIQUEMENT avec un objet JSON compact sur une seule ligne, sans texte autour "
        "et sans balise markdown, avec ces 6 clés :\n"
        '- code : string (un des codes connus ci-dessus) ou null\n'
        '- confidence : "haute", "moyenne" ou "faible"\n'
        '- is_new : booléen — true si aucun code connu ne convient et qu\'il s\'agit d\'un nouveau formulaire\n'
        '- suggested_label : string courte si is_new est true, sinon null\n'
        '- target : entier plausible de soumissions attendues pour ce formulaire sur tout le terrain '
        '(ex. un formulaire par établissement -> proche du nombre d\'établissements), ou null si incertain\n'
        '- rationale : UNE phrase courte en français expliquant le raisonnement\n'
        'Reste bref sur "rationale" (moins de 25 mots) pour que la réponse tienne dans le budget alloué.'
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(block.text for block in response.content if getattr(block, 'type', None) == 'text')
    except Exception as e:
        return {'available': True, 'error': f"Appel IA impossible : {e}"}

    parsed = _extract_json(raw)
    if not parsed:
        return {'available': True, 'error': "Réponse de l'IA illisible — réessayez ou saisissez manuellement."}

    code = parsed.get('code')
    if code and code not in {f['code'] for f in known_forms}:
        code = None  # l'IA ne doit proposer qu'un code existant, sinon on l'ignore plutôt que d'inventer

    return {
        'available': True,
        'error': None,
        'code': code,
        'confidence': parsed.get('confidence'),
        'is_new': bool(parsed.get('is_new')) and not code,
        'suggested_label': parsed.get('suggested_label'),
        'target': parsed.get('target') if isinstance(parsed.get('target'), int) else None,
        'rationale': parsed.get('rationale'),
    }
