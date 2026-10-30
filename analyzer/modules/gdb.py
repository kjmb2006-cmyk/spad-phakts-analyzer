"""
SPAD Analyzer — Base centrale (Golden Data Base allégée)

Le document « Concepts & Fonctionnalités » du SPAD prévoit une base où les
données de toutes les enquêtes sont conservées, identifiées par leur Factum,
et croisées selon les variables du DPF (le CUBE : géographie × variables ×
temps). Version allégée ici, dans spad.db :

  - gdb_enquetes  : une ligne par enquête versée (Factum, titre, source…)
  - gdb_valeurs   : une ligne par valeur (Factum, répondant, code, radical,
                    valeur) — le modèle « Survey_D » du document
  - gdb_variables : résumé par variable et par enquête, pour la vue CUBE et
                    la recherche sans parcourir toutes les valeurs

Le code PHAKTS sans sa directive aligne les enquêtes entre elles : Age__1Y
d'une enquête et Age__1Y!0<N<120 d'une autre sont la même variable, mais pas
Allaitement__B et Allaitement__Duree__1W, ni Age__1Y (années) et Age__1M
(mois). La colonne « radical » des tables contient cette clé d'alignement. Verser à nouveau une enquête (même Factum) remplace ses données.
Chaque valeur garde son Factum, son répondant et son code d'origine : on
remonte toujours à l'enquête source.
"""
import datetime
import json
import math
import re
import sqlite3
import unicodedata

import pandas as pd

from modules import factum as study_factum
from modules.phakts_codes import alignment_key
from modules.form_mapping import DB_PATH

MAX_CELLS = 3_000_000
RESPONDENT_COLUMNS = ('_uuid', 'meta/instanceID', '_id')
TECHNICAL = re.compile(r'^(_|meta/|formhub/)|^__version__$', re.I)


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute('PRAGMA busy_timeout=30000')
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS gdb_enquetes (
            factum       TEXT PRIMARY KEY,
            titre        TEXT,
            source       TEXT,
            source_ref   TEXT,
            n_repondants INTEGER,
            n_variables  INTEGER,
            versee_le    TEXT,
            versee_par   TEXT,
            labels       TEXT);
        CREATE TABLE IF NOT EXISTS gdb_valeurs (
            factum     TEXT NOT NULL,
            repondant  TEXT NOT NULL,
            code       TEXT NOT NULL,
            radical    TEXT NOT NULL,
            valeur     TEXT NOT NULL,
            valeur_num REAL);
        CREATE INDEX IF NOT EXISTS idx_gdb_valeurs_factum ON gdb_valeurs(factum);
        CREATE INDEX IF NOT EXISTS idx_gdb_valeurs_radical ON gdb_valeurs(radical);
        CREATE TABLE IF NOT EXISTS gdb_variables (
            factum     TEXT NOT NULL,
            code       TEXT NOT NULL,
            radical    TEXT NOT NULL,
            n_valeurs  INTEGER,
            n_num      INTEGER,
            PRIMARY KEY (factum, code));
    ''')
    if 'labels' not in {r[1] for r in conn.execute('PRAGMA table_info(gdb_enquetes)')}:
        conn.execute('ALTER TABLE gdb_enquetes ADD COLUMN labels TEXT')     # bases créées avant les libellés
    return conn


def radical_of(column):
    """Clé d'alignement d'une colonne (voir modules/phakts_codes.py)."""
    return alignment_key(column)


def _fold(text):
    return unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode().lower()


def _respondent_ids(df):
    for col in RESPONDENT_COLUMNS:
        if col in df.columns:
            ids = df[col].astype(str).str.strip()
            if df[col].notna().all() and ids.is_unique:
                return ids.tolist()
    return [f'L{i}' for i in range(1, len(df) + 1)]


def _text(value):
    if isinstance(value, (pd.Timestamp, datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _number(text):
    try:
        x = float(text.replace(',', '.'))
        return x if math.isfinite(x) else None
    except ValueError:
        return None


def deposer(df, fac, titre='', source='', source_ref='', user='', labels=None):
    """Verse un jeu de données dans la base centrale sous le Factum `fac`.
    `labels` : dictionnaire des libellés de modalités (modules/choice_labels.py),
    conservé avec l'enquête pour que la rouvrir affiche les vraies modalités.
    Renvoie (ok, message)."""
    parsed = study_factum.parse(fac)
    if not parsed['valid']:
        return False, 'Factum invalide : ' + ' '.join(parsed['errors'])
    fac = parsed['normalized']
    if df is None or df.empty:
        return False, 'Aucune donnée à verser.'
    if df.size > MAX_CELLS:
        return False, f'Jeu de données trop volumineux ({df.size:,} cellules, maximum {MAX_CELLS:,}).'.replace(',', ' ')

    respondents = _respondent_ids(df)
    columns = [c for c in df.columns
               if not TECHNICAL.match(str(c)) and not str(c).split('/')[-1].lower().startswith('factum')]
    rows, summary = [], []
    for col in columns:
        radical = radical_of(col)
        n = n_num = 0
        for rid, value in zip(respondents, df[col].tolist()):
            if value is None or (not isinstance(value, str) and pd.isna(value)):
                continue
            text = _text(value)
            if not text or text.lower() == 'nan':
                continue
            num = _number(text)
            rows.append((fac, rid, str(col), radical, text, num))
            n += 1
            n_num += num is not None
        if n:
            summary.append((fac, str(col), radical, n, n_num))

    conn = _connect()
    try:
        with conn:
            conn.execute('DELETE FROM gdb_valeurs WHERE factum = ?', (fac,))
            conn.execute('DELETE FROM gdb_variables WHERE factum = ?', (fac,))
            conn.executemany('INSERT INTO gdb_valeurs VALUES (?, ?, ?, ?, ?, ?)', rows)
            conn.executemany('INSERT INTO gdb_variables VALUES (?, ?, ?, ?, ?)', summary)
            conn.execute('INSERT OR REPLACE INTO gdb_enquetes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         (fac, titre or parsed['parts']['sujet_lisible'], source, source_ref, len(df),
                          len(summary), datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), user,
                          json.dumps(labels, ensure_ascii=False) if labels else None))
    finally:
        conn.close()
    return True, (f'{len(df)} répondant(s), {len(summary)} variable(s) et {len(rows)} valeur(s) '
                  f'versés dans la base centrale.')


def enquetes():
    """Enquêtes versées, de la plus récente (date de référence) à la plus ancienne."""
    conn = _connect()
    try:
        rows = conn.execute('SELECT factum, titre, source, source_ref, n_repondants, n_variables, '
                            "versee_le, versee_par, COALESCE(labels, '') != '' FROM gdb_enquetes").fetchall()
    finally:
        conn.close()
    keys = ('factum', 'titre', 'source', 'source_ref', 'n_repondants', 'n_variables', 'versee_le', 'versee_par',
            'has_labels')
    out = []
    for r in rows:
        e = dict(zip(keys, r))
        e['parts'] = study_factum.parse(e['factum'])['parts']
        out.append(e)
    return sorted(out, key=lambda e: (e['parts'].get('date', ''), e['factum']), reverse=True)


def labels_for(fac):
    """Dictionnaire de libellés conservé avec une enquête versée ({} s'il n'y en a pas)."""
    conn = _connect()
    try:
        row = conn.execute('SELECT labels FROM gdb_enquetes WHERE factum = ?', (fac,)).fetchone()
    finally:
        conn.close()
    try:
        return json.loads(row[0]) if row and row[0] else {}
    except ValueError:
        return {}


def dataframe(fac):
    """Reconstruit une enquête versée sous forme de tableau (une ligne par
    répondant, une colonne par code d'origine) — pour la rouvrir dans
    l'analyse multi-enquête sans recharger le fichier. Les colonnes
    entièrement numériques redeviennent numériques ; les valeurs manquantes
    (non versées) restent vides."""
    conn = _connect()
    try:
        rows = conn.execute('SELECT repondant, code, valeur, valeur_num FROM gdb_valeurs WHERE factum = ? '
                            'ORDER BY rowid', (fac,)).fetchall()
        variables = conn.execute('SELECT code, n_valeurs, n_num FROM gdb_variables WHERE factum = ? '
                                 'ORDER BY rowid', (fac,)).fetchall()
    finally:
        conn.close()
    if not rows:
        return None
    respondents = list(dict.fromkeys(r[0] for r in rows))
    numeric = {code for code, n, n_num in variables if n and n == n_num}
    data = {code: {} for code, _, _ in variables}
    for resp, code, text, num in rows:
        data[code][resp] = num if code in numeric else text
    return pd.DataFrame({c: pd.Series(v, dtype='float64' if c in numeric else 'object') for c, v in data.items()},
                        index=respondents)


def supprimer(fac):
    conn = _connect()
    try:
        with conn:
            n = conn.execute('DELETE FROM gdb_enquetes WHERE factum = ?', (fac,)).rowcount
            conn.execute('DELETE FROM gdb_valeurs WHERE factum = ?', (fac,))
            conn.execute('DELETE FROM gdb_variables WHERE factum = ?', (fac,))
        return n > 0
    finally:
        conn.close()


def cube(min_enquetes=2):
    """Vue CUBE : pour chaque radical présent dans au moins `min_enquetes`
    enquêtes, le nombre de valeurs par enquête. Renvoie (factums, lignes)."""
    conn = _connect()
    try:
        rows = conn.execute('SELECT radical, factum, SUM(n_valeurs) FROM gdb_variables '
                            'GROUP BY radical, factum').fetchall()
    finally:
        conn.close()
    by_radical = {}
    for radical, fac, n in rows:
        by_radical.setdefault(radical, {})[fac] = n
    factums = [e['factum'] for e in reversed(enquetes())]     # axe du temps : plus ancienne d'abord
    lignes = [{'radical': r, 'counts': counts, 'n_enquetes': len(counts)}
              for r, counts in by_radical.items() if len(counts) >= min_enquetes]
    lignes.sort(key=lambda l: (-l['n_enquetes'], _fold(l['radical'])))
    return factums, lignes


def rechercher(terme):
    """« Ces données existent-elles déjà ? » — variables dont le radical ou
    le code contient le terme (sans tenir compte des accents ni de la casse)."""
    needle = _fold(terme).strip()
    if not needle:
        return []
    conn = _connect()
    try:
        rows = conn.execute('SELECT radical, code, factum, n_valeurs FROM gdb_variables').fetchall()
    finally:
        conn.close()
    found = {}
    for radical, code, fac, n in rows:
        if needle in _fold(radical) or needle in _fold(code):
            entry = found.setdefault(radical, {'radical': radical, 'enquetes': {}, 'codes': set()})
            entry['enquetes'][fac] = entry['enquetes'].get(fac, 0) + n
            entry['codes'].add(code)
    out = []
    for entry in found.values():
        entry['codes'] = sorted(entry['codes'])
        entry['n_valeurs'] = sum(entry['enquetes'].values())
        out.append(entry)
    return sorted(out, key=lambda e: (-len(e['enquetes']), _fold(e['radical'])))


def serie(radical, top=8):
    """Une variable à travers les enquêtes, dans l'ordre chronologique des
    dates de référence : effectifs, puis moyenne/médiane (numérique) ou
    répartition des modalités (catégoriel)."""
    conn = _connect()
    try:
        rows = conn.execute('SELECT factum, valeur, valeur_num FROM gdb_valeurs WHERE radical = ?',
                            (radical,)).fetchall()
        codes = conn.execute('SELECT factum, code FROM gdb_variables WHERE radical = ?', (radical,)).fetchall()
    finally:
        conn.close()
    if not rows:
        return []
    meta = {e['factum']: e for e in enquetes()}
    df = pd.DataFrame(rows, columns=['factum', 'valeur', 'valeur_num'])
    out = []
    for fac, g in df.groupby('factum'):
        n = len(g)
        nums = g['valeur_num'].dropna()
        item = {'factum': fac, 'n': n, 'enquete': meta.get(fac, {}),
                'codes': sorted({c for f, c in codes if f == fac})}
        if len(nums) >= 0.9 * n:
            item.update(type='numerique', moyenne=round(float(nums.mean()), 2), mediane=round(float(nums.median()), 2),
                        minimum=round(float(nums.min()), 2), maximum=round(float(nums.max()), 2))
        else:
            counts = g['valeur'].value_counts()
            item.update(type='categoriel', modalites=[
                {'valeur': v, 'n': int(c), 'pct': round(100 * c / n, 1)} for v, c in counts.head(top).items()],
                autres=int(counts.iloc[top:].sum()))
        out.append(item)
    return sorted(out, key=lambda i: (i['enquete'].get('parts', {}).get('date', ''), i['factum']))


def valeurs(radical):
    """Toutes les valeurs d'une variable, avec leur origine (Factum, répondant,
    code) : la base de tout croisement entre enquêtes."""
    conn = _connect()
    try:
        rows = conn.execute('SELECT factum, repondant, code, valeur FROM gdb_valeurs WHERE radical = ? '
                            'ORDER BY factum, repondant', (radical,)).fetchall()
    finally:
        conn.close()
    return pd.DataFrame(rows, columns=['Factum', 'Répondant', 'Code', 'Valeur'])
