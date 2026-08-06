"""
SPAD Analyzer — Registre des formulaires suivis (SPAD officiels + ajoutés)

Généralise ce qui était figé en dur dans reference_data.py (FORM_CODES /
FORM_LABELS / FORM_NAME_HINT, règles de cible codées par formulaire) en un
registre persisté, modifiable depuis /admin/forms sans toucher au code —
répond à la demande : « l'application ne doit pas rester figée sur les 7
formulaires uniquement... possibilité que d'autres formulaires soient
ajoutés et aussi retirer les 7 formulaires de kobo ».

Les 7 formulaires SPAD officiels sont le jeu de données par défaut (seed),
recréé au premier lancement si le fichier n'existe pas encore — comportement
strictement identique à avant (voir reference_data.py) tant que rien n'est
modifié depuis l'écran admin.

Types de règle de cible pris en charge génériquement (aucun code à écrire
pour ajouter un formulaire qui suit l'un de ces motifs) :
  - fixed_per_etablissement(n)      : n par établissement (motif F5/F7/F8)
  - fixed_per_district(n)           : n par district (motif F01)
  - etab_field_positive(field)      : 1 par établissement où ref[field] > 0
                                       (motif F02 — sig_deces_maternels)
  - floor_sum_district_field(field) : somme de ref[field] sur les
                                       établissements du district, plancher
                                       (motif F07 — dépasser est normal)
  - by_etablissement_type           : cible = etab['f6_target'] (motif F6 —
                                       type CSR-D/CSR-DM/EPH/CSU — trop
                                       spécifique pour être généralisé plus)
"""
import os
import json
import copy

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_MODULE_DIR)
REGISTRY_PATH = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'forms_registry.local.json')

RULE_TYPES = (
    'fixed_per_etablissement',
    'fixed_per_district',
    'etab_field_positive',
    'floor_sum_district_field',
    'by_etablissement_type',
)

RULE_TYPE_LABELS = {
    'fixed_per_etablissement': 'Nombre fixe par établissement',
    'fixed_per_district': 'Nombre fixe par district',
    'etab_field_positive': "1 par établissement où un champ du référentiel est > 0",
    'floor_sum_district_field': "Somme d'un champ du référentiel par district (plancher)",
    'by_etablissement_type': "Selon le type d'établissement (réservé F6)",
}

_SEED = [
    {'code': 'F5', 'label': 'Tabac — Femmes enceintes/allaitantes', 'name_hint': '5_',
     'grain': 'etablissement', 'actor': 'enqueteur',
     'etab_field': 'Etablissement_Sanitaire__X', 'district_field': 'District_Sanitaire__X',
     'target_rule': {'type': 'fixed_per_etablissement', 'params': {'n': 15}}, 'active': True},
    {'code': 'F6', 'label': 'Tabac — Personnel de santé (CAP)', 'name_hint': '6_',
     'grain': 'etablissement', 'actor': 'enqueteur',
     'etab_field': 'Etablissement_Sanitaire__X', 'district_field': 'District_Sanitaire__X',
     'target_rule': {'type': 'by_etablissement_type', 'params': {}}, 'active': True},
    {'code': 'F7', 'label': 'Vaccination — Ménages', 'name_hint': '7_',
     'grain': 'etablissement', 'actor': 'enqueteur',
     'etab_field': 'Etablissement_Sanitaire__X', 'district_field': 'District_Sanitaire__X',
     'target_rule': {'type': 'fixed_per_etablissement', 'params': {'n': 15}}, 'active': True},
    {'code': 'F8', 'label': 'Vaccination — Établissement', 'name_hint': '8_',
     'grain': 'etablissement', 'actor': 'enqueteur',
     'etab_field': 'Etablissement_Sanitaire__X', 'district_field': 'District_Sanitaire__X',
     'target_rule': {'type': 'fixed_per_etablissement', 'params': {'n': 1}}, 'active': True},
    {'code': 'F01', 'label': 'RDM — Fiche district', 'name_hint': 'F01',
     'grain': 'district', 'actor': 'superviseur',
     'etab_field': None, 'district_field': 'F01_01a__X',
     'target_rule': {'type': 'fixed_per_district', 'params': {'n': 1}}, 'active': True},
    {'code': 'F02', 'label': 'RDM — Fiche établissement', 'name_hint': 'F02',
     'grain': 'etablissement', 'actor': 'superviseur',
     'etab_field': 'F02_01__E', 'district_field': 'F02_00_district__X',
     'target_rule': {'type': 'etab_field_positive', 'params': {'field': 'sig_deces_maternels'}}, 'active': True},
    {'code': 'F07', 'label': 'RDM — Grille de revue', 'name_hint': 'F07',
     'grain': 'district', 'actor': 'superviseur',
     'etab_field': 'RDM_NOT03__X', 'district_field': 'RDM_NOT02__X',
     'target_rule': {'type': 'floor_sum_district_field', 'params': {'field': 'sig_deces_maternels'}}, 'active': True},
]


def _save_raw(forms):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(forms, f, ensure_ascii=False, indent=2)


def _load_raw():
    if not os.path.exists(REGISTRY_PATH):
        _save_raw(copy.deepcopy(_SEED))
    try:
        with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return copy.deepcopy(_SEED)


def all_forms(include_inactive=True):
    forms = _load_raw()
    if not include_inactive:
        forms = [f for f in forms if f.get('active', True)]
    return forms


def active_codes():
    return [f['code'] for f in all_forms(include_inactive=False)]


def get(code):
    for f in _load_raw():
        if f['code'] == code:
            return f
    return None


def labels():
    return {f['code']: f['label'] for f in all_forms(include_inactive=False)}


def name_hints():
    return {f['code']: f['name_hint'] for f in all_forms(include_inactive=False) if f.get('name_hint')}


def set_active(code, active):
    forms = _load_raw()
    for f in forms:
        if f['code'] == code:
            f['active'] = bool(active)
            _save_raw(forms)
            return True
    return False


def add_form(code, label, name_hint, grain, actor, etab_field, district_field, target_rule):
    code = (code or '').strip()
    if not code:
        return False, "Code obligatoire."
    forms = _load_raw()
    if any(f['code'] == code for f in forms):
        return False, f"Le code « {code} » existe déjà."
    if grain not in ('etablissement', 'district'):
        return False, "Grain invalide (établissement ou district)."
    if actor not in ('enqueteur', 'superviseur'):
        return False, "Acteur invalide (enquêteur ou superviseur)."
    if not isinstance(target_rule, dict) or target_rule.get('type') not in RULE_TYPES:
        return False, "Type de règle de cible invalide."
    forms.append({
        'code': code, 'label': label or code, 'name_hint': name_hint or '',
        'grain': grain, 'actor': actor,
        'etab_field': etab_field or None, 'district_field': district_field or None,
        'target_rule': target_rule, 'active': True,
    })
    _save_raw(forms)
    return True, None


def delete_form(code):
    forms = _load_raw()
    remaining = [f for f in forms if f['code'] != code]
    if len(remaining) == len(forms):
        return False
    _save_raw(remaining)
    return True


# ─── Calcul de cible générique, par type de règle ──────────────────────────

def is_floor_rule(form):
    """Vrai si la cible de ce formulaire est un plancher (le dépasser est
    normal, jamais une anomalie « à vérifier ») — motif F07."""
    return form['target_rule']['type'] == 'floor_sum_district_field'


def target_for_etablissement(form, ref, etablissement_code):
    """Cible pour CE formulaire, pour UN établissement — None si sa règle
    n'est pas au grain établissement."""
    rule = form['target_rule']
    rtype = rule['type']
    etab = ref['etablissements'].get(etablissement_code)
    if rtype == 'fixed_per_etablissement':
        return rule['params']['n']
    if rtype == 'etab_field_positive':
        if etab is None:
            return 1
        return 1 if (etab.get(rule['params']['field']) or 0) > 0 else 0
    if rtype == 'by_etablissement_type':
        return etab['f6_target'] if etab else 1
    return None


def target_for_district(form, ref, district_code):
    """Cible pour CE formulaire, pour UN district — None si sa règle n'est
    pas au grain district."""
    rule = form['target_rule']
    rtype = rule['type']
    if rtype == 'fixed_per_district':
        return rule['params']['n']
    if rtype == 'floor_sum_district_field':
        field = rule['params']['field']
        return sum((e.get(field) or 0) for e in ref['etablissements'].values()
                    if e['district_code'] == district_code)
    return None


def national_target(form, ref):
    """Cible nationale agrégée pour CE formulaire."""
    rule = form['target_rule']
    rtype = rule['type']
    if rtype == 'fixed_per_etablissement':
        return rule['params']['n'] * len(ref['etablissements'])
    if rtype == 'fixed_per_district':
        return rule['params']['n'] * len(ref['districts'])
    if rtype == 'etab_field_positive':
        field = rule['params']['field']
        return sum(1 for e in ref['etablissements'].values() if (e.get(field) or 0) > 0)
    if rtype == 'floor_sum_district_field':
        field = rule['params']['field']
        return sum((e.get(field) or 0) for e in ref['etablissements'].values())
    if rtype == 'by_etablissement_type':
        return sum(e.get('f6_target', 0) for e in ref['etablissements'].values())
    return None
