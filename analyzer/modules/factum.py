"""
SPAD Analyzer — Factum : identifiant universel d'une Étude

Syntaxe (rapport final SPAD-CIV, octobre 2025, et Factums du DPF-genesis) :

    <entête>__<juridiction>__<n>C<m>_<sujet>__<AAAAMMJJ>__<domaine>

    PGT14_OS2_RC2_2__CIV_MS__1C1_Etude_CAP_Personnel_Sante_PEC_Tabac__20250900__ES

  - entête      : programme / objectif stratégique / résultat (PGT14_OS2_RC2_2)
  - juridiction : pays (code ISO à 3 lettres) et institution (CIV_MS)
  - nCm         : collecte n sur m (1C1 = collecte unique, 2C2 = 2e de 2)
  - sujet       : objet de l'étude, mots séparés par « _ »
  - date        : date de référence AAAAMMJJ, JJ = 00 si le jour n'est pas fixé
  - domaine     : domaine de définition (ES = établissement de santé, Menage…)

La même règle existe côté PHAKTS Studio (public/phakts-core.js, parseFactum) :
les deux doivent rester alignées.

Le Factum de chaque enquête chargée dans l'Analyzer est enregistré dans
spad.db (table survey_factums), rattaché à la même clé que les règles de
validation (formulaire Kobo ou fichier importé).
"""
import datetime
import re
import sqlite3
import unicodedata

from modules.form_mapping import DB_PATH

_PART = r'[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*'
FACTUM_RE = re.compile(
    rf'^(?P<entete>{_PART})__(?P<juridiction>{_PART})__(?P<n>\d+)C(?P<m>\d+)_'
    rf'(?P<sujet>{_PART}?)(?P<sep>__|_)(?P<date>\d{{8}})__(?P<domaine>{_PART})$')

DOMAINES = {'ES': 'Établissement de santé', 'ESP': 'Établissement scolaire / public',
            'Menage': 'Ménage', 'Communaute': 'Communauté'}

EXEMPLE = 'PGT14_OS2_RC2_2__CIV_MS__1C1_Etude_CAP_Personnel_Sante_PEC_Tabac__20250900__ES'


def normalize_part(text):
    """Une composante sans accent, espace ni séparateur double."""
    s = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^A-Za-z0-9]+', '_', s)
    return s.strip('_')


def normalize_date(text):
    """'2025-09' → '20250900', '2025-09-15' → '20250915', '20250900' inchangé."""
    s = re.sub(r'\D', '', str(text or ''))
    if len(s) == 6:
        s += '00'
    return s


def _count(x):
    digits = re.sub(r'\D', '', str(x or ''))
    return int(digits) if digits else 1


def build(entete, juridiction, n, m, sujet, date, domaine):
    return (f'{normalize_part(entete)}__{normalize_part(juridiction)}__{_count(n)}C{_count(m)}_'
            f'{normalize_part(sujet)}__{normalize_date(date)}__{normalize_part(domaine)}')


def parse(factum):
    """{'valid', 'errors', 'warnings', 'parts', 'normalized'} — un Factum
    invalide a au moins une erreur ; les avertissements n'empêchent rien."""
    s = str(factum or '').strip()
    res = {'valid': False, 'errors': [], 'warnings': [], 'parts': {}, 'normalized': s}
    if not s:
        res['errors'].append('Factum vide.')
        return res
    bad = sorted(set(re.sub(r'[A-Za-z0-9_]', '', s)))
    if bad:
        res['errors'].append('Caractères interdits : ' + ' '.join(repr(c) for c in bad)
                             + ' (lettres sans accent, chiffres et « _ » uniquement).')
        return res
    m = FACTUM_RE.match(s)
    if not m:
        res['errors'].append('Structure attendue : Entête__Juridiction__nCm_Sujet__AAAAMMJJ__Domaine '
                             f'(exemple : {EXEMPLE}).')
        return res
    p = m.groupdict()
    n, total, date = int(p['n']), int(p['m']), p['date']
    if n < 1 or total < 1 or n > total:
        res['errors'].append(f'Collecte « {n}C{total} » : n doit être compris entre 1 et m.')
    year, month, day = int(date[:4]), int(date[4:6]), int(date[6:])
    if not (1900 <= year <= 2100) or not (1 <= month <= 12) or not (0 <= day <= 31):
        res['errors'].append(f'Date de référence « {date} » invalide (AAAAMMJJ, JJ = 00 si le jour n\'est pas fixé).')
    elif day:
        try:
            datetime.date(year, month, day)
        except ValueError:
            res['errors'].append(f'Date de référence « {date} » inexistante.')
    if not p['sujet']:
        res['errors'].append('Sujet de l\'étude manquant.')
    if p['sep'] == '_':
        res['warnings'].append('Séparateur « __ » attendu avant la date, comme dans le DPF.')
    if not re.match(r'^[A-Z]{3}(_|$)', p['juridiction']):
        res['warnings'].append(f'Juridiction « {p["juridiction"]} » : le pays devrait être un code à 3 lettres majuscules (CIV, COG…).')
    if not re.match(r'^PGT\d+_OS\d+_RC\d+', p['entete']):
        res['warnings'].append(f'Entête « {p["entete"]} » inhabituel (forme attendue : PGT14_OS2_RC2_2).')
    res['parts'] = {
        'entete': p['entete'], 'juridiction': p['juridiction'], 'collecte': n, 'collectes': total,
        'sujet': p['sujet'], 'date': date, 'domaine': p['domaine'],
        'date_lisible': f'{date[6:]}/{date[4:6]}/{date[:4]}' if day else f'{date[4:6]}/{date[:4]}',
        'domaine_lisible': DOMAINES.get(p['domaine'], p['domaine']),
        'sujet_lisible': p['sujet'].replace('_', ' '),
    }
    res['normalized'] = f"{p['entete']}__{p['juridiction']}__{n}C{total}_{p['sujet']}__{date}__{p['domaine']}"
    res['valid'] = not res['errors']
    return res


# ─── Factum de l'enquête chargée ───────────────────────────────────────────

def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute('PRAGMA busy_timeout=30000')
    conn.execute('''CREATE TABLE IF NOT EXISTS survey_factums (
        survey_key TEXT PRIMARY KEY,
        factum     TEXT NOT NULL,
        updated_by TEXT,
        updated_at TEXT NOT NULL)''')
    return conn


def get_for_survey(survey_key):
    conn = _connect()
    try:
        row = conn.execute('SELECT factum FROM survey_factums WHERE survey_key = ?', (survey_key,)).fetchone()
        return row[0] if row else ''
    finally:
        conn.close()


def set_for_survey(survey_key, factum, user=''):
    """Enregistre un Factum valide (forme normalisée). Renvoie le résultat de parse()."""
    res = parse(factum)
    if res['valid']:
        conn = _connect()
        try:
            with conn:
                conn.execute('INSERT OR REPLACE INTO survey_factums VALUES (?, ?, ?, ?)',
                             (survey_key, res['normalized'], user,
                              datetime.datetime.now().strftime('%Y-%m-%d %H:%M')))
        finally:
            conn.close()
    return res


def from_dataframe(df):
    """Factum porté par les données elles-mêmes (champ Factum__G du XLSForm
    généré par PHAKTS Studio), s'il est unique et valide."""
    if df is None:
        return ''
    for col in df.columns:
        if str(col).split('/')[-1].lower().startswith('factum'):
            values = df[col].dropna().astype(str).str.strip().unique()
            if len(values) == 1 and parse(values[0])['valid']:
                return parse(values[0])['normalized']
    return ''
