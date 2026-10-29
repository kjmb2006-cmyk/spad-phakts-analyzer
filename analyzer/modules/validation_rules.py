"""
SPAD Analyzer — Règles de validation des données de collecte

Applique au jeu de données chargé les « Règles de Validation des Données de
Collecte » du SPAD (document Concepts & Fonctionnalités, §A) :
  - doublons : même identifiant de soumission, ou réponses identiques ;
  - cohérence des heures de l'appareil : fin avant début, entretien trop
    court ou resté ouvert, dates dans le futur ;
  - seuils : bornes PHAKTS écrites dans le nom de colonne (Age__1Y!0<N<120) ;
  - valeurs extrêmes (écart interquartile) et distributions anormales
    (asymétrie, aplatissement) — le contrôle « ensembliste » de pré-analyse ;
  - règles propres à une enquête, définies par l'utilisateur (A ≤ B, A > 0…),
    enregistrées dans spad.db (même base que modules/form_mapping.py).

Rien n'est corrigé automatiquement : chaque contrôle signale des lignes à
vérifier, exportables pour les équipes de terrain.
"""
import os
import re
import sqlite3
import datetime

import numpy as np
import pandas as pd

from modules.form_mapping import DB_PATH

ERREUR = 'erreur'
A_VERIFIER = 'a_verifier'
INFO = 'info'

MIN_INTERVIEW_MINUTES = 2
MAX_INTERVIEW_HOURS = 24
IQR_FACTOR = 3          # barrières « extrêmes » de Tukey : bien moins de faux positifs que 1,5
SKEW_LIMIT = 2
KURTOSIS_LIMIT = 7      # aplatissement en excès (0 pour une loi normale)
MIN_VALUES_FOR_STATS = 20
MIN_COLUMNS_FOR_IDENTICAL = 10   # en dessous, deux réponses identiques sont banales

# Colonnes techniques Kobo / ODK : ni des réponses, ni des variables d'analyse
_TECH_COLUMNS = {
    'start', 'end', 'today', 'deviceid', 'username', 'simserial', 'subscriberid',
    'phonenumber', 'audit', '_id', '_uuid', '_submission_time', '_index',
    'meta/instanceid', 'instanceid', 'meta/rootuuid', '__version__', 'formhub/uuid',
    '_validation_status', '_status', '_submitted_by', '_tags', '_notes',
    '_attachments', '_geolocation', 'key', 'submissiondate',
}
_SUBMISSION_ID_COLUMNS = ('_uuid', 'meta/instanceid', 'instanceid', '_id', 'key')
_RANGE_IN_NAME = re.compile(r'!(-?\d+(?:[.,]\d+)?)\s*(<=?)\s*[A-Za-z]\s*(<=?)\s*(-?\d+(?:[.,]\d+)?)\s*$')
_ISO_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}')
# Codes, identifiants, téléphones, coordonnées : numériques mais sans sens statistique
_ID_LIKE = re.compile(r'(^|[_/ .])(id|code|codes|numero|num|telephone|tel|latitude|longitude|lat|lon|gps|index)([_/ .]|$)', re.IGNORECASE)

OPERATEURS = {
    '<': lambda a, b: a < b,
    '<=': lambda a, b: a <= b,
    '>': lambda a, b: a > b,
    '>=': lambda a, b: a >= b,
    '=': lambda a, b: a == b,
    '!=': lambda a, b: a != b,
}
OPERATEUR_SYMBOLES = {'<': '<', '<=': '≤', '>': '>', '>=': '≥', '=': '=', '!=': '≠'}


def _check(categorie, titre, detail, severite, variables, mask=None):
    lignes = [int(i) + 1 for i in np.flatnonzero(np.asarray(mask, dtype=bool))] if mask is not None else []
    return {'categorie': categorie, 'titre': titre, 'detail': detail, 'severite': severite,
            'variables': list(variables), 'lignes': lignes}


def _as_datetime(series):
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors='coerce', utc=True)
    return pd.to_datetime(series.astype('string'), errors='coerce', utc=True, format='ISO8601')


def _mostly(mask_ok, non_null, share=0.8):
    return non_null > 0 and mask_ok.sum() / non_null >= share


def _date_columns(df):
    out = []
    for col in df.columns:
        if str(col).lower() in _TECH_COLUMNS:
            continue
        series = df[col].dropna()
        if series.empty:
            continue
        if pd.api.types.is_datetime64_any_dtype(series):
            out.append(col)
        elif series.dtype == object:
            sample = series.astype(str).head(200)
            if _mostly(sample.str.match(_ISO_DATE), len(sample)):
                out.append(col)
    return out


def _find_time_column(df, kind):
    """Colonne de début ou de fin d'entretien : métadonnée Kobo start/end, ou
    variable PHAKTS générée par Kobo (Entretien__Debut__G!start)."""
    words = {'start': ('debut', 'start'), 'end': ('fin', 'end')}[kind]
    for col in df.columns:
        if str(col).lower().split('/')[-1] == kind:
            return col
    for col in df.columns:
        parts = [p for p in re.split(r'[_/\s!]+', str(col).lower()) if p]
        if parts and 'g' in parts and any(w in parts for w in words):
            return col
    return None


def _duplicate_checks(df):
    out = []
    id_cols = [c for c in df.columns if str(c).lower() in _SUBMISSION_ID_COLUMNS]
    for col in id_cols:
        mask = df[col].notna() & df[col].duplicated(keep=False)
        if mask.any():
            out.append(_check('Doublons', f'Identifiant de soumission « {col} » en double',
                              'La même soumission semble importée plusieurs fois.', ERREUR, [col], mask))
    answers = [c for c in df.columns if str(c).lower() not in _TECH_COLUMNS and df[c].notna().any()]
    if len(answers) >= MIN_COLUMNS_FOR_IDENTICAL:
        values = df[answers].astype(str)
        mask = values.duplicated(keep=False)
        if mask.any():
            groups = values[mask].drop_duplicates().shape[0]
            out.append(_check('Doublons', 'Soumissions aux réponses identiques',
                              f'{groups} groupe(s) de soumissions identiques sur les {len(answers)} réponses : '
                              'saisie en double probable.', A_VERIFIER, [], mask))
    return out


def _time_checks(df):
    out = []
    start_col, end_col = _find_time_column(df, 'start'), _find_time_column(df, 'end')
    if start_col and end_col:
        start, end = _as_datetime(df[start_col]), _as_datetime(df[end_col])
        both = start.notna() & end.notna()
        minutes = (end - start).dt.total_seconds() / 60
        out.append(_check('Cohérence des heures', "Heure de fin antérieure à l'heure de début",
                          "Horloge de l'appareil déréglée : les médias de collecte doivent être synchronisés.",
                          ERREUR, [start_col, end_col], both & (end < start)))
        out.append(_check('Cohérence des heures', f'Entretien de moins de {MIN_INTERVIEW_MINUTES} minutes',
                          "Durée trop courte pour un entretien réel : questionnaire rempli sans l'enquêté ?",
                          A_VERIFIER, [start_col, end_col], both & (minutes >= 0) & (minutes < MIN_INTERVIEW_MINUTES)))
        out.append(_check('Cohérence des heures', f'Questionnaire resté ouvert plus de {MAX_INTERVIEW_HOURS} h',
                          'Questionnaire laissé ouvert, repris plus tard, ou horloge déréglée.',
                          A_VERIFIER, [start_col, end_col], both & (minutes > MAX_INTERVIEW_HOURS * 60)))
        if '_submission_time' in df.columns:
            sent = _as_datetime(df['_submission_time'])
            ahead = end.notna() & sent.notna() & (end > sent + pd.Timedelta(hours=1))
            out.append(_check('Cohérence des heures', "Fin d'entretien postérieure à l'envoi",
                              "Horloge de l'appareil en avance sur celle du serveur.",
                              A_VERIFIER, [end_col, '_submission_time'], ahead))
    limit = pd.Timestamp.now(tz='UTC') + pd.Timedelta(days=1)
    for col in _date_columns(df):
        dates = _as_datetime(df[col])
        out.append(_check('Cohérence des heures', f'Date dans le futur ({col})',
                          'Date postérieure au jour de contrôle : saisie ou horloge erronée.',
                          ERREUR, [col], dates.notna() & (dates > limit)))
    return [c for c in out if c['lignes']]


def _phakts_range_checks(df):
    out = []
    for col in df.columns:
        m = _RANGE_IN_NAME.search(str(col))
        if not m:
            continue
        lo, hi = float(m.group(1).replace(',', '.')), float(m.group(4).replace(',', '.'))
        # Comme le générateur XLSForm : une borne basse 0 reste inclusive (0 cas, âge 0 an)
        lo_ok = (lambda v: v >= lo) if (m.group(2) == '<=' or lo == 0) else (lambda v: v > lo)
        hi_ok = (lambda v: v <= hi) if m.group(3) == '<=' else (lambda v: v < hi)
        values = pd.to_numeric(df[col], errors='coerce')
        mask = values.notna() & ~(lo_ok(values) & hi_ok(values))
        if mask.any():
            out.append(_check('Seuils', f'Valeur hors de la plage PHAKTS ({col})',
                              f'Plage attendue : {m.group(1)} {m.group(2)} valeur {m.group(3)} {m.group(4)}.',
                              ERREUR, [col], mask))
    return out


def _numeric_columns(df):
    out = []
    for col in df.columns:
        if str(col).lower() in _TECH_COLUMNS or _ID_LIKE.search(str(col)):
            continue
        raw = df[col].dropna()
        if len(raw) < MIN_VALUES_FOR_STATS:
            continue
        values = pd.to_numeric(raw, errors='coerce')
        if _mostly(values.notna(), len(raw)) and values.nunique() > 15:
            out.append(col)
    return out


def _outlier_checks(df):
    out = []
    for col in _numeric_columns(df):
        values = pd.to_numeric(df[col], errors='coerce')
        q1, q3 = values.quantile(0.25), values.quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            lo, hi = q1 - IQR_FACTOR * iqr, q3 + IQR_FACTOR * iqr
            mask = values.notna() & ((values < lo) | (values > hi))
            if mask.any():
                out.append(_check('Valeurs extrêmes', f'Valeurs extrêmes ({col})',
                                  f'Hors de [{lo:.4g} ; {hi:.4g}] ({IQR_FACTOR} × écart interquartile) : '
                                  'erreur de saisie ou cas exceptionnel à confirmer.', A_VERIFIER, [col], mask))
        skew, kurt = values.skew(), values.kurt()
        if (pd.notna(skew) and abs(skew) > SKEW_LIMIT) or (pd.notna(kurt) and kurt > KURTOSIS_LIMIT):
            out.append(_check('Valeurs extrêmes', f'Distribution anormale ({col})',
                              f'Asymétrie {skew:.1f}, aplatissement {kurt:.1f} : distribution très éloignée '
                              'de la normale, à contrôler avant toute analyse.', A_VERIFIER, [col]))
    return out


def _comparable(left, right):
    """Convertit les deux côtés d'une règle en nombres, sinon en dates, sinon en
    texte. right est une Series (autre variable) ou une valeur constante."""
    right_is_series = isinstance(right, pd.Series)
    left_non_null = left.notna().sum()

    def series_or_const(conv, value):
        return conv(value) if right_is_series else conv(pd.Series([value] * len(left), index=left.index))

    nums_l = pd.to_numeric(left, errors='coerce')
    nums_r = series_or_const(lambda s: pd.to_numeric(s, errors='coerce'), right)
    if _mostly(nums_l.notna() & left.notna(), left_non_null) and nums_r.notna().any():
        return nums_l, nums_r, 'nombre'
    dates_l = _as_datetime(left)
    dates_r = series_or_const(_as_datetime, right)
    if _mostly(dates_l.notna() & left.notna(), left_non_null) and dates_r.notna().any():
        return dates_l, dates_r, 'date'
    text = lambda s: s.astype('string').str.strip().str.lower()
    return text(left), series_or_const(text, right), 'texte'


def evaluate_rule(df, rule):
    sym = OPERATEUR_SYMBOLES.get(rule['operateur'], rule['operateur'])
    titre = rule.get('libelle') or f"{rule['gauche']} {sym} {rule['droite']}"
    if rule['gauche'] not in df.columns or (rule['droite_est_variable'] and rule['droite'] not in df.columns):
        return _check("Règles de l'enquête", titre, 'Règle non appliquée : variable absente du jeu de données chargé.',
                      INFO, [rule['gauche']])
    right = df[rule['droite']] if rule['droite_est_variable'] else rule['droite']
    left, right, nature = _comparable(df[rule['gauche']], right)
    if nature == 'texte' and rule['operateur'] not in ('=', '!='):
        return _check("Règles de l'enquête", titre, 'Règle non appliquée : comparaison < ou > impossible sur du texte.',
                      INFO, [rule['gauche']])
    valid = left.notna() & right.notna()
    respected = OPERATEURS[rule['operateur']](left, right).fillna(False).astype(bool)
    variables = [rule['gauche']] + ([rule['droite']] if rule['droite_est_variable'] else [])
    compared = {'nombre': 'nombres comparés', 'date': 'dates comparées', 'texte': 'textes comparés'}[nature]
    return _check("Règles de l'enquête", titre, f'Règle non respectée ({compared}).',
                  ERREUR, variables, valid & ~respected)


_SEVERITY_ORDER = {ERREUR: 0, A_VERIFIER: 1, INFO: 2}


def run_validation(df, rules=()):
    checks = (_duplicate_checks(df) + _time_checks(df) + _phakts_range_checks(df)
              + _outlier_checks(df) + [evaluate_rule(df, r) for r in rules])
    checks.sort(key=lambda c: (_SEVERITY_ORDER[c['severite']], c['categorie'], -len(c['lignes'])))
    flagged = {line for c in checks for line in c['lignes']}
    n = len(df)
    return {
        'n_lignes': n,
        'n_signalees': len(flagged),
        'pct_sans_anomalie': round(100 * (n - len(flagged)) / n, 1) if n else 100.0,
        'n_erreurs': sum(1 for c in checks if c['severite'] == ERREUR and c['lignes']),
        'n_a_verifier': sum(1 for c in checks if c['severite'] == A_VERIFIER),
        'checks': checks,
    }


def flagged_rows(df, result):
    """Lignes signalées, avec leur numéro et la liste de leurs anomalies — à
    transmettre aux équipes de terrain pour vérification."""
    reasons = {}
    for c in result['checks']:
        for line in c['lignes']:
            reasons.setdefault(line, []).append(c['titre'])
    if not reasons:
        return df.head(0)
    lines = sorted(reasons)
    out = df.iloc[[line - 1 for line in lines]].copy()
    out.insert(0, 'Anomalies', [' ; '.join(reasons[line]) for line in lines])
    out.insert(0, 'N° ligne', lines)
    return out


# ── Règles propres à une enquête (stockées dans spad.db) ──────────────────────

def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    conn.execute('''CREATE TABLE IF NOT EXISTS validation_rules (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        survey_key          TEXT NOT NULL,
        gauche              TEXT NOT NULL,
        operateur           TEXT NOT NULL,
        droite              TEXT NOT NULL,
        droite_est_variable INTEGER NOT NULL,
        libelle             TEXT,
        created_by          TEXT,
        created_at          TEXT NOT NULL
    )''')
    return conn


def list_rules(survey_key):
    conn = _connect()
    try:
        rows = conn.execute(
            '''SELECT id, gauche, operateur, droite, droite_est_variable, libelle, created_by, created_at
               FROM validation_rules WHERE survey_key = ? ORDER BY id''', (survey_key,)).fetchall()
    finally:
        conn.close()
    keys = ('id', 'gauche', 'operateur', 'droite', 'droite_est_variable', 'libelle', 'created_by', 'created_at')
    return [dict(zip(keys, row), droite_est_variable=bool(row[4])) for row in rows]


def add_rule(survey_key, gauche, operateur, droite, droite_est_variable, libelle='', created_by=''):
    """Renvoie (ok, erreur)."""
    gauche, droite = (gauche or '').strip(), (droite or '').strip()
    if not survey_key:
        return False, "Aucune enquête chargée."
    if not gauche or not droite:
        return False, "Variable et valeur de comparaison requises."
    if operateur not in OPERATEURS:
        return False, "Opérateur invalide."
    conn = _connect()
    try:
        with conn:
            conn.execute(
                '''INSERT INTO validation_rules
                   (survey_key, gauche, operateur, droite, droite_est_variable, libelle, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (survey_key, gauche[:200], operateur, droite[:200], 1 if droite_est_variable else 0,
                 (libelle or '').strip()[:200], (created_by or '')[:100],
                 datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    finally:
        conn.close()
    return True, None


def delete_rule(rule_id, survey_key):
    conn = _connect()
    try:
        with conn:
            cur = conn.execute('DELETE FROM validation_rules WHERE id = ? AND survey_key = ?', (rule_id, survey_key))
        return cur.rowcount > 0
    finally:
        conn.close()
