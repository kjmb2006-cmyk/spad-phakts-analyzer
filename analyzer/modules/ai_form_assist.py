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


def suggest_multi_role(kobo_name, structure):
    """Analyse la STRUCTURE complète (survey + choices, voir
    kobo_connector.get_asset_structure()) d'un formulaire Kobo pour détecter
    s'il est rempli par PLUSIEURS catégories d'acteurs distinctes (motif
    « roster » — voir forms_registry.py, grain enquêteur/superviseur :
    un même formulaire porte alors plusieurs codes SPAD, un par rôle, via
    role_filter) — ce que suggest_for_kobo_form() ne couvre pas, limité à UN
    SEUL code.

    Ne propose JAMAIS de cible chiffrée : combien de DRS, de DDS, etc. sont
    attendus est un fait organisationnel (SOP du projet), pas quelque chose
    de déductible de la structure d'un formulaire — voir la note du bouton
    « Analyser la structure » dans templates/suivi.html. L'utilisateur reste
    seul décideur de la configuration finale dans /admin/forms.

    Renvoie toujours un dict, jamais None : {'available', 'error',
    'has_multi_role', 'role_field', 'roles' (liste de {'value','label'}),
    'district_field', 'identity_hint', 'rationale'}."""
    client = _get_client()
    if client is None:
        return {'available': False, 'error': None}

    survey = structure.get('survey', [])
    choices = structure.get('choices', [])

    # Ne garde que les champs select_one/select_multiple/text — les seuls
    # susceptibles d'être le champ de rôle, le champ district ou un champ
    # d'identité ; le reste (questions d'évaluation, notes...) n'apporte
    # rien à cette détection et gonflerait inutilement le prompt (un XLSForm
    # réel peut avoir plusieurs centaines de questions).
    relevant = [q for q in survey if q.get('type') in ('select_one', 'select_multiple', 'text')]
    choice_lists = {}
    for c in choices:
        ln = c.get('list_name')
        if ln:
            choice_lists.setdefault(ln, []).append(c.get('name'))

    prompt = (
        "Tu analyses la structure d'un formulaire KoboToolbox utilisé pour une enquête de santé publique (SPAD).\n\n"
        f"Nom du formulaire : {kobo_name!r}\n\n"
        f"Champs pertinents (type/nom/libellé/liste de choix associée) :\n{json.dumps(relevant, ensure_ascii=False)}\n\n"
        f"Valeurs de chaque liste de choix :\n{json.dumps(choice_lists, ensure_ascii=False)}\n\n"
        "Question : ce formulaire est-il rempli par PLUSIEURS catégories d'acteurs distinctes (ex. superviseur "
        "ET enquêteur, ou plusieurs profils d'intervenants), identifiables par un SEUL champ dont les valeurs "
        "correspondent chacune à un rôle ? Ou est-ce un formulaire à rôle unique (ou sans rôle du tout) ?\n\n"
        "Réponds UNIQUEMENT avec un objet JSON compact sur une seule ligne, sans texte autour et sans balise "
        "markdown, avec ces clés :\n"
        '- has_multi_role : booléen\n'
        '- role_field : nom EXACT du champ qui distingue les rôles, ou null\n'
        '- roles : liste d\'objets {"value": "...", "label": "..."} (value = valeur Kobo exacte, label = libellé '
        'lisible en français) — une entrée par rôle détecté, liste vide si has_multi_role est false\n'
        '- district_field : nom EXACT du champ qui identifie le district/la zone géographique du répondant, ou null\n'
        '- identity_hint : nom EXACT d\'un champ texte libre qui pourrait identifier individuellement le répondant '
        '(nom, téléphone...), ou null si aucun ne semble fiable\n'
        '- rationale : UNE phrase courte en français expliquant le raisonnement (moins de 30 mots)\n\n'
        "Ne propose JAMAIS de nombre ou de cible — ce n'est pas déductible de la structure du formulaire seule."
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(block.text for block in response.content if getattr(block, 'type', None) == 'text')
    except Exception as e:
        return {'available': True, 'error': f"Appel IA impossible : {e}"}

    parsed = _extract_json(raw)
    if not parsed:
        return {'available': True, 'error': "Réponse de l'IA illisible — réessayez."}

    roles = [r for r in (parsed.get('roles') or []) if isinstance(r, dict) and r.get('value')]

    return {
        'available': True,
        'error': None,
        'has_multi_role': bool(parsed.get('has_multi_role')) and bool(roles),
        'role_field': parsed.get('role_field'),
        'roles': roles,
        'district_field': parsed.get('district_field'),
        'identity_hint': parsed.get('identity_hint'),
        'rationale': parsed.get('rationale'),
    }
