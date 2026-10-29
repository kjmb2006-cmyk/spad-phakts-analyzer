"""
SPAD Analyzer — Registre des formulaires suivis (SPAD officiels + ajoutés)

Généralise ce qui était figé en dur dans reference_data.py (FORM_CODES /
FORM_LABELS / FORM_NAME_HINT, règles de cible codées par formulaire) en un
registre persisté, modifiable depuis /admin/forms sans toucher au code —
répond à la demande : « l'application ne doit pas rester figée sur les 7
formulaires uniquement... possibilité que d'autres formulaires soient
ajoutés et aussi retirer les 7 formulaires de kobo ».

Les 7 formulaires SPAD officiels sont le jeu de données par défaut (seed),
recréé au premier lancement si la base n'a pas encore d'enregistrement —
comportement strictement identique à avant (voir reference_data.py) tant
que rien n'est modifié depuis l'écran admin.

Persisté en SQLite (même base que modules/form_mapping.py et
modules/accounts.py — voir DB_PATH), pas en JSON : ce registre est relu à
CHAQUE appel (all_forms()/get(), aucun cache en mémoire — voir plus bas),
par exemple une fois par formulaire mappé à chaque calcul de Complétude
nationale. Un fichier JSON relu/réécrit en entier à chaque fois n'offrait
aucune atomicité ; SQLite (mode WAL) le fait nativement, sans dépendance
supplémentaire (sqlite3 est dans la bibliothèque standard).

Migration : au tout premier accès après mise à jour, si spad.db n'a pas
encore de formulaires mais que l'ancien forms_registry.local.json existe,
son contenu est importé automatiquement (sinon le seed des 7 formulaires
officiels, comme avant). L'ancien fichier n'est jamais supprimé.

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
  - fixed_national(n)               : cible nationale fixe, non multipliée
                                       par le référentiel (motif "roster" —
                                       voir grain 'enqueteur'/'superviseur'
                                       ci-dessous)
  - fixed_named_list(field, entries) : cible NOMMÉE par entité (pas par
                                       district) — motif "roster national"
                                       (grain 'roster_national' ci-dessous).
                                       entries est une liste de
                                       {label, match, n} ; 'match' est une
                                       liste de valeurs à comparer (insensible
                                       à la casse) au champ Kobo 'field' —
                                       une valeur préfixée "AUTRE:xxx" veut
                                       dire : field == 'AUTRE' ET le champ
                                       "<field>_Autre__Z" associé (convention
                                       PHAKTS pour le texte libre d'un
                                       "Autre, précisez") vaut xxx. Cas réel :
                                       l'UGP RAA Phase 1 compte DIS/OMS/INSP/
                                       ANSTAT par code Kobo, mais une 5e
                                       entité ("DPPS") n'a pas de code dédié
                                       — seulement saisie en texte libre.

Grains pris en charge : 'etablissement', 'district', 'enqueteur' /
'superviseur' ("roster" géographique — voir ci-dessous), et
'roster_national' ("roster nominatif", sans dimension géographique — motif
UGP/Programmes RAA Phase 1 : chaque entité nommée a son propre effectif
attendu, voir fixed_named_list ci-dessus et
modules/completeness.py::named_roster_detail()).

'enqueteur'/'superviseur' : un même Kobo UID peut porter PLUSIEURS codes
SPAD à la fois dans ce cas précis, un par rôle, chacun avec son propre
role_filter — cas réel : un formulaire d'avis rempli à la fois par les
superviseurs et les enquêteurs, où seul le champ "Fonction" distingue qui a
répondu. Pour ce grain, 'reçu' compte les valeurs DISTINCTES de
identity_field parmi les lignes où role_filter[field] == role_filter[value]
— jamais un décompte par établissement/district, qui n'aurait pas de sens
ici (une même personne répond une seule fois, pas une fois par
établissement). Voir modules/completeness.py::roster_completeness().

region_fallback_field : pour un acteur RÉGIONAL (motif DRS, RAA Phase 1)
dont le formulaire ne demande district_field qu'aux acteurs de niveau
district (skip logic XLSForm) — un champ texte libre compagnon capture
alors sa région de rattachement, résolue vers l'unique district de cette
région dans le référentiel. Voir modules/completeness.py::roster_by_district()."""
import os
import json
import copy
import sqlite3

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_MODULE_DIR)
DB_PATH = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'spad.db')
_LEGACY_JSON_PATH = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'forms_registry.local.json')

RULE_TYPES = (
    'fixed_per_etablissement',
    'fixed_per_district',
    'etab_field_positive',
    'floor_sum_district_field',
    'by_etablissement_type',
    'fixed_national',
    'fixed_named_list',
)

GRAINS = ('etablissement', 'district', 'enqueteur', 'superviseur', 'roster_national')

RULE_TYPE_LABELS = {
    'fixed_per_etablissement': 'Nombre fixe par établissement',
    'fixed_per_district': 'Nombre fixe par district',
    'fixed_national': 'Nombre fixe national (roster)',
    'fixed_named_list': 'Liste nominative à cibles variables (roster national)',
    'etab_field_positive': "1 par établissement où un champ du référentiel est > 0",
    'floor_sum_district_field': "Somme d'un champ du référentiel par district (plancher)",
    'by_etablissement_type': "Selon le type d'établissement (réservé F6)",
}

# Colonnes JSON (forme variable selon le type de règle / nullable) à part des
# colonnes scalaires — voir _row_to_dict()/_dict_to_row().
_JSON_FIELDS = ('target_rule', 'role_filter')
_SCALAR_FIELDS = ('code', 'label', 'name_hint', 'grain', 'actor',
                   'etab_field', 'district_field', 'identity_field', 'region_fallback_field')

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


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    # Attend plutôt que d'échouer immédiatement avec "database is locked" si
    # un autre process (scripts/kobo_completude_refresh.py, un autre thread
    # gunicorn) détient une écriture au même instant.
    conn.execute('PRAGMA busy_timeout=30000')
    conn.execute('''CREATE TABLE IF NOT EXISTS forms (
        code                  TEXT PRIMARY KEY,
        label                 TEXT,
        name_hint             TEXT,
        grain                 TEXT,
        actor                 TEXT,
        etab_field            TEXT,
        district_field        TEXT,
        target_rule           TEXT,
        active                INTEGER NOT NULL DEFAULT 1,
        role_filter           TEXT,
        identity_field        TEXT,
        region_fallback_field TEXT
    )''')
    _bootstrap(conn)
    return conn


def _bootstrap(conn):
    """Si la table est vide : importe l'ancien forms_registry.local.json s'il
    existe, sinon réinstalle le seed des 7 formulaires officiels — même
    comportement qu'avant (recréation depuis _SEED au premier lancement).

    INSERT OR IGNORE (pas le _INSERT_SQL ordinaire d'add_form(), qui doit
    lever une erreur sur un doublon) : au tout premier déploiement après
    migration, ce bootstrap peut s'exécuter depuis deux process à la fois
    (ce worker gunicorn fraîchement redémarré ET, dans la même fenêtre,
    scripts/kobo_completude_refresh.py relancé par le timer systemd) — les
    deux verraient la table vide et tenteraient le même seed ; ignorer un
    doublon plutôt que planter dessus le rend inoffensif. Le script
    scripts/migrate_to_sqlite.py, lancé à la main avant le redémarrage des
    services, est le vrai filet de sécurité qui évite ce scénario en
    production — ceci n'est qu'une seconde ligne de défense."""
    cur = conn.execute('SELECT COUNT(*) FROM forms')
    if cur.fetchone()[0] > 0:
        return
    source = None
    if os.path.exists(_LEGACY_JSON_PATH):
        try:
            with open(_LEGACY_JSON_PATH, 'r', encoding='utf-8') as f:
                source = json.load(f)
        except Exception:
            source = None
    if not source:
        source = copy.deepcopy(_SEED)
    with conn:
        for form in source:
            conn.execute(_BOOTSTRAP_INSERT_SQL, _dict_to_row(form))


_BOOTSTRAP_INSERT_SQL = '''INSERT OR IGNORE INTO forms
    (code, label, name_hint, grain, actor, etab_field, district_field,
     target_rule, active, role_filter, identity_field, region_fallback_field)
    VALUES (:code, :label, :name_hint, :grain, :actor, :etab_field, :district_field,
            :target_rule, :active, :role_filter, :identity_field, :region_fallback_field)'''

_INSERT_SQL = '''INSERT INTO forms
    (code, label, name_hint, grain, actor, etab_field, district_field,
     target_rule, active, role_filter, identity_field, region_fallback_field)
    VALUES (:code, :label, :name_hint, :grain, :actor, :etab_field, :district_field,
            :target_rule, :active, :role_filter, :identity_field, :region_fallback_field)'''


def _dict_to_row(form):
    row = {k: form.get(k) for k in _SCALAR_FIELDS}
    row['active'] = 1 if form.get('active', True) else 0
    for k in _JSON_FIELDS:
        v = form.get(k)
        row[k] = json.dumps(v, ensure_ascii=False) if v is not None else None
    return row


def _row_to_dict(row):
    """row : sqlite3.Row (voir _connect(), row_factory réglé juste avant
    chaque SELECT qui en a besoin)."""
    form = {k: row[k] for k in _SCALAR_FIELDS}
    form['active'] = bool(row['active'])
    for k in _JSON_FIELDS:
        raw = row[k]
        form[k] = json.loads(raw) if raw is not None else None
    return form


def _load_raw():
    conn = _connect()
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM forms ORDER BY rowid').fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def all_forms(include_inactive=True):
    forms = _load_raw()
    if not include_inactive:
        forms = [f for f in forms if f.get('active', True)]
    return forms


def active_codes():
    return [f['code'] for f in all_forms(include_inactive=False)]


def get(code):
    conn = _connect()
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM forms WHERE code = ?', (code,)).fetchone()
    finally:
        conn.close()
    return _row_to_dict(row) if row else None


def labels():
    return {f['code']: f['label'] for f in all_forms(include_inactive=False)}


def name_hints():
    return {f['code']: f['name_hint'] for f in all_forms(include_inactive=False) if f.get('name_hint')}


def set_active(code, active):
    conn = _connect()
    try:
        with conn:
            cur = conn.execute('UPDATE forms SET active = ? WHERE code = ?', (1 if active else 0, code))
        return cur.rowcount > 0
    finally:
        conn.close()


def add_form(code, label, name_hint, grain, actor, etab_field, district_field, target_rule,
             role_filter=None, identity_field=None, region_fallback_field=None):
    code = (code or '').strip()
    if not code:
        return False, "Code obligatoire."
    if grain not in GRAINS:
        return False, "Grain invalide (établissement, district, enquêteur ou superviseur)."
    if actor not in ('enqueteur', 'superviseur'):
        return False, "Acteur invalide (enquêteur ou superviseur)."
    if not isinstance(target_rule, dict) or target_rule.get('type') not in RULE_TYPES:
        return False, "Type de règle de cible invalide."
    form = {
        'code': code, 'label': label or code, 'name_hint': name_hint or '',
        'grain': grain, 'actor': actor,
        'etab_field': etab_field or None, 'district_field': district_field or None,
        'target_rule': target_rule, 'active': True,
        'role_filter': role_filter or None, 'identity_field': identity_field or None,
        'region_fallback_field': region_fallback_field or None,
    }
    conn = _connect()
    try:
        with conn:
            conn.execute(_INSERT_SQL, _dict_to_row(form))
    except sqlite3.IntegrityError:
        return False, f"Le code « {code} » existe déjà."
    finally:
        conn.close()
    return True, None


def delete_form(code):
    conn = _connect()
    try:
        with conn:
            cur = conn.execute('DELETE FROM forms WHERE code = ?', (code,))
        return cur.rowcount > 0
    finally:
        conn.close()


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
    if rtype == 'fixed_national':
        return rule['params']['n']
    if rtype == 'fixed_named_list':
        return sum(e['n'] for e in rule['params']['entries'])
    return None
