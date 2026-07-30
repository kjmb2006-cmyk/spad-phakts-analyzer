"""
SPAD Analyzer — Référentiel organisationnel et cibles par formulaire

Sources (fournies par l'utilisateur, phase pilote 2026), stockées dans
data/reference/ :
  - org_unit.xlsx : référentiel région / district / établissement / enquêteur /
    superviseur — dérivé de « fichiers_org_unit_vf.xlsx » (liste "choices" du
    XLSForm, celle réellement proposée aux enquêteurs sur le terrain).
    ⚠️ Version EXPURGÉE des noms d'enquêteurs/superviseurs (remplacés par leur
    seul code, ex. D01ENQ1) avant tout commit — le dépôt GitHub est public et
    ces noms sont des données personnelles. Les établissements gardent leur
    nom complet (ce ne sont pas des données personnelles). Le fichier source
    original (avec noms) reste uniquement sur le poste local de l'utilisateur.
  - tirage_etablissements.xlsx : dérivé de
    « tirage_10_etsa_par_district_kd_vu.xlsx » — tirage au sort des 120
    établissements (méthodologie : 1 EPHR/EPHD + 4 CSU + 5 CSR par district,
    seed=20260713), avec le comptage SIG des décès maternels par
    établissement. Ne contient aucune donnée personnelle.

Règles de cible par formulaire — déduites empiriquement de l'observation de
spadapp-zeta.vercel.app (aucun document méthodologique séparé fourni) et
vérifiées ici par recoupement avec les totaux nationaux déjà observés :
  F5  (Tabac — Femmes)       : 15 par établissement, fixe   → total national 1800 (exact)
  F6  (Tabac — Personnel)    : 3 si EPH/CSU, 2 si CSR-DM, 1 si CSR-D
                                → total calculé 271 (≈ 273 observé — écart de
                                mémorisation probable, à confirmer)
  F7  (Vaccination Ménages)  : 15 par établissement, fixe   → total national 1800 (exact)
  F8  (Vaccination Étab.)    : 1 par établissement, fixe    → total national 120 (exact)
  F01 (RDM — District)       : 1 par district, fixe         → total national 12 (exact)
  F02 (RDM — Établissement)  : 1 par établissement, fixe    → total national 120
                                (le XLSForm F02 précise lui-même « une fiche
                                par établissement » — vérifié après une
                                première hypothèse erronée : ce n'est PAS le
                                nombre de décès SIG, comme le confirme
                                EPHR SAN-PEDRO — 43 décès SIG mais cible F02
                                observée = 1 sur spadapp-zeta.vercel.app)
  F07 (RDM — Grille)         : somme des décès maternels notifiés au SIG pour
                                les établissements du district — c'est un
                                plancher, le dépasser est normal → total
                                calculé 187 (≈ 188 observé)

Ces règles sont marquées « à confirmer » dans l'UI tant qu'aucun document
officiel ne les a validées explicitement — elles reproduisent fidèlement les
totaux déjà observés, mais restent une reconstruction, pas une source
primaire.
"""
import os
import re
import openpyxl

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_MODULE_DIR)
DEFAULT_ORG_UNIT_PATH = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'org_unit.xlsx')
DEFAULT_TIRAGE_PATH   = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'tirage_etablissements.xlsx')

FORM_CODES = ['F5', 'F6', 'F7', 'F8', 'F01', 'F02', 'F07']

FORM_LABELS = {
    'F5':  'Tabac — Femmes enceintes/allaitantes',
    'F6':  'Tabac — Personnel de santé (CAP)',
    'F7':  'Vaccination — Ménages',
    'F8':  'Vaccination — Établissement',
    'F01': 'RDM — Fiche district',
    'F02': 'RDM — Fiche établissement',
    'F07': 'RDM — Grille de revue',
}

_cache = {}  # (org_unit_path, tirage_path) -> référentiel chargé


def _norm_name(s):
    """Normalise un nom d'établissement (referentiel org_unit) pour le
    rapprochement avec le fichier de tirage : retire le suffixe type entre
    parenthèses (ex. « (CSU) », « (EPH (EPHR/EPHD)) ») ajouté par le
    référentiel, espaces multiples, casse. Ne s'applique qu'au nom du
    référentiel — le fichier de tirage n'a pas ce suffixe type (colonne
    séparée), donc pas besoin de la même opération côté tirage (voir
    _norm_tirage_name : un nom comme « EPHR PUBLIC de SAN-PEDRO (Nouveau) »
    a une parenthèse qui fait partie du nom réel, pas un suffixe type — la
    stripper aurait cassé le rapprochement)."""
    if not s:
        return ""
    s = re.sub(r'\s*\([^()]*(\([^()]*\))?[^()]*\)\s*$', '', s).strip()
    return re.sub(r'\s+', ' ', s).upper()


def _norm_tirage_name(s):
    """Normalise un nom d'établissement issu du fichier de tirage — pas de
    parenthèse à retirer ici (voir note dans _norm_name)."""
    if not s:
        return ""
    return re.sub(r'\s+', ' ', s.strip()).upper()


def _etab_type_and_f6_target(label):
    """Devine le type d'établissement à partir du libellé et la cible F6 associée."""
    upper = label.upper()
    if 'CSR-DM' in upper:
        return 'CSR-DM', 2
    if 'CSR-D' in upper or re.search(r'\bCSR\b', upper):
        return 'CSR-D', 1
    if 'EPH' in upper:
        return 'EPH', 3
    if 'CSU' in upper:
        return 'CSU', 3
    return '?', 1


def _load_org_unit(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb['choices_etab']
    rows = list(ws.iter_rows(min_row=2, values_only=True))

    regions = {}      # code -> {code, nom}
    districts = {}     # code -> {code, nom, region_code}
    etablissements = {}  # code -> {...}
    enqueteurs = {}     # code -> {...}
    superviseurs = {}   # code -> {...}

    for r in rows:
        if not r or not r[0]:
            continue
        list_name, name, label = r[0], r[1], r[2]
        code_id   = r[3] if len(r) > 3 else None
        region_c  = r[4] if len(r) > 4 else None
        district_c = r[5] if len(r) > 5 else None
        enq_c     = r[6] if len(r) > 6 else None

        if list_name == 'Admin_Region_Sanitaire_':
            regions[name] = {'code': name, 'nom': label}

        elif list_name == 'Admin_District_Sanitaire_':
            districts[name] = {'code': name, 'nom': label, 'district_id': code_id, 'region_code': region_c}

        elif list_name == 'Admin_Etablissement_Sante_':
            etype, f6_target = _etab_type_and_f6_target(label)
            etablissements[name] = {
                'code': name,
                'nom_complet': label,
                'nom_normalise': _norm_name(label),
                'etab_id': code_id,
                'region_code': region_c,
                'district_code': district_c,
                'enqueteur_code': enq_c,
                'type': etype,
                'f6_target': f6_target,
                'sig_deces_maternels': 0,  # complété par _apply_tirage_targets
            }

        elif list_name == 'Admin_Enqueteur_':
            enqueteurs[name] = {'code': name, 'nom_complet': label, 'enq_id': code_id,
                                 'region_code': region_c, 'district_code': district_c}

        elif list_name == 'Admin_Superviseur_':
            superviseurs[name] = {'code': name, 'nom_complet': label, 'sup_id': code_id,
                                   'region_code': region_c, 'district_code': district_c}

    return {
        'regions': regions, 'districts': districts, 'etablissements': etablissements,
        'enqueteurs': enqueteurs, 'superviseurs': superviseurs,
    }


def _apply_tirage_targets(ref, tirage_path):
    """Complète le référentiel avec la cible F02 (décès maternels SIG) par
    établissement, en rapprochant les noms entre les deux fichiers sources."""
    wb = openpyxl.load_workbook(tirage_path, read_only=True, data_only=True)
    by_norm_name = {e['nom_normalise']: e for e in ref['etablissements'].values()}

    unmatched = []
    for sheet in wb.sheetnames:
        if not sheet.startswith('Tirage_'):
            continue
        ws = wb[sheet]
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        for r in rows:
            if not r or not r[2]:
                continue
            etsa_name = r[2].strip()
            sig_deces = r[4] if len(r) > 4 and r[4] else 0
            key = _norm_tirage_name(etsa_name)
            if key in by_norm_name:
                by_norm_name[key]['sig_deces_maternels'] = int(sig_deces or 0)
            else:
                unmatched.append((etsa_name, sig_deces))

    ref['tirage_unmatched'] = unmatched
    return ref


def load(org_unit_path=None, tirage_path=None, use_cache=True):
    """Charge (et met en cache) le référentiel complet à partir des fichiers Excel fournis
    (par défaut : data/reference/org_unit.xlsx et data/reference/tirage_etablissements.xlsx)."""
    org_unit_path = org_unit_path or DEFAULT_ORG_UNIT_PATH
    tirage_path = tirage_path if tirage_path is not None else DEFAULT_TIRAGE_PATH
    cache_key = (org_unit_path, tirage_path)
    if use_cache and cache_key in _cache:
        return _cache[cache_key]

    ref = _load_org_unit(org_unit_path)
    if tirage_path:
        _apply_tirage_targets(ref, tirage_path)

    _cache[cache_key] = ref
    return ref


def clear_cache():
    _cache.clear()


def target_for(ref, form_code, etablissement_code=None, district_code=None):
    """Cible attendue pour un formulaire donné, au niveau établissement ou district."""
    if form_code in ('F5', 'F7'):
        return 15
    if form_code == 'F8':
        return 1
    if form_code == 'F01':
        return 1  # par district
    if form_code == 'F02':
        return 1  # par établissement — voir note méthodologique en tête de module
    if form_code == 'F6':
        etab = ref['etablissements'].get(etablissement_code)
        return etab['f6_target'] if etab else 1
    if form_code == 'F07':
        # somme des décès maternels SIG des établissements du district — plancher
        total = sum(e['sig_deces_maternels'] for e in ref['etablissements'].values()
                    if e['district_code'] == district_code)
        return total
    return None


def national_targets(ref):
    """Cibles nationales agrégées par formulaire — pour la vue nationale."""
    n_etab = len(ref['etablissements'])
    n_district = len(ref['districts'])
    sig_total = sum(e['sig_deces_maternels'] for e in ref['etablissements'].values())
    f6_total = sum(e['f6_target'] for e in ref['etablissements'].values())
    return {
        'F5':  15 * n_etab,
        'F6':  f6_total,
        'F7':  15 * n_etab,
        'F8':  1 * n_etab,
        'F01': 1 * n_district,
        'F02': 1 * n_etab,
        'F07': sig_total,  # plancher — dépasser cette valeur est normal
    }
