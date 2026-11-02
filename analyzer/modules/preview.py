"""
SPAD Analyzer — Aperçu navigable des données

Une page de lignes à la demande (recherche, tri, filtres par colonne, choix des colonnes, pagination) et la fiche d'une
soumission (réponses classées par section, avec les anomalies relevées à la validation). Le numéro de ligne est celui de la
validation : 1 = première soumission du jeu.
"""
import math
import threading

import numpy as np
import pandas as pd

from modules import dataset

PER_PAGE_CHOICES = (10, 25, 50, 100, 200)
DEFAULT_COLUMNS = 10
CELL_MAX = 160
_HAYSTACKS = {}
_HAY_MAX = 3
_LOCK = threading.Lock()


def cell_text(value):
    """Texte d'une cellule : vide pour un manquant, entiers sans « .0 », décimales à la française, dates lisibles."""
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.strftime('%d/%m/%Y %H:%M') if (value.hour or value.minute) else value.strftime('%d/%m/%Y')
    if isinstance(value, (float, np.floating)):
        return str(int(value)) if float(value).is_integer() else f'{float(value):.6g}'.replace('.', ',')
    if isinstance(value, (bool, np.bool_)):
        return 'oui' if value else 'non'
    return str(value).strip()


def _as_text(series):
    """Série en texte minuscule, sans manquants, pour chercher."""
    return series.astype('string').fillna('').str.lower()


def _haystack(df, key):
    """Pour chaque ligne, tout son texte mis bout à bout : une recherche devient une seule passe. Gardé par jeu (`key`)."""
    if key is not None:
        with _LOCK:
            hay = _HAYSTACKS.get(key)
        if hay is not None and len(hay) == len(df):
            return hay
    hay = pd.Series([''] * len(df), index=df.index, dtype='string')
    for col in df.columns:
        hay = hay + '\x1f' + _as_text(df[col])
    if key is not None:
        with _LOCK:
            while len(_HAYSTACKS) >= _HAY_MAX:
                _HAYSTACKS.pop(next(iter(_HAYSTACKS)))
            _HAYSTACKS[key] = hay
    return hay


def _sort_key(series):
    """Tri numérique quand la colonne l'est (au moins 80 % de valeurs numériques), sinon alphabétique."""
    filled = series.notna().sum()
    num = pd.to_numeric(series, errors='coerce')
    if filled and num.notna().sum() >= 0.8 * filled:
        return num
    return _as_text(series).where(series.notna())


def default_columns(df, types=None, limit=DEFAULT_COLUMNS):
    """Colonnes montrées d'emblée : les premières qui portent une réponse (ni technique, ni vide)."""
    types = types or {}
    keep = [c for c in df.columns if types.get(c) != 'technique' and df[c].notna().any()]
    return (keep or list(df.columns))[:limit]


def column_catalog(df, labels=None, types=None):
    """Toutes les colonnes, pour le sélecteur : nom, libellé lisible, type, section."""
    labels, types = labels or {}, types or {}
    return [{'name': c, 'label': labels.get(c) or dataset.readable(c), 'type': types.get(c, ''), 'section': dataset.section_of(c)}
            for c in df.columns]


def query(df, columns=None, search='', filters=None, lines=None, sort=None, ascending=True, page=1, per_page=25,
          key=None, types=None):
    """Une page de lignes. `lines` : numéros de ligne à garder ; `filters` : {colonne: texte contenu} ; `key` : empreinte du jeu
    (garde le texte de recherche entre deux requêtes). Renvoie les lignes de la page et les totaux."""
    n = len(df)
    mask = np.ones(n, dtype=bool)
    if lines is not None:
        mask &= np.isin(np.arange(n) + 1, list(lines))
    term = str(search or '').strip().lower()
    if term:
        mask &= _haystack(df, key).str.contains(term, regex=False).fillna(False).to_numpy(dtype=bool)
    for col, text in (filters or {}).items():
        text = str(text or '').strip().lower()
        if col in df.columns and text:
            mask &= _as_text(df[col]).str.contains(text, regex=False).fillna(False).to_numpy(dtype=bool)
    pos = np.flatnonzero(mask)
    if sort in df.columns and len(pos):
        keys = _sort_key(df[sort]).iloc[pos].reset_index(drop=True)
        pos = pos[keys.sort_values(ascending=bool(ascending), na_position='last', kind='mergesort').index.to_numpy()]
    per_page = per_page if per_page in PER_PAGE_CHOICES else 25
    pages = max(1, math.ceil(len(pos) / per_page))
    page = min(max(int(page or 1), 1), pages)
    chunk = pos[(page - 1) * per_page: page * per_page]
    shown = [c for c in (columns or default_columns(df, types)) if c in df.columns]
    body = {c: df[c].iloc[chunk].tolist() for c in shown}
    rows = [{'line': int(p) + 1, 'cells': [_clip(cell_text(body[c][i])) for c in shown]} for i, p in enumerate(chunk)]
    return {'columns': shown, 'rows': rows, 'total': n, 'matched': int(len(pos)), 'page': page, 'pages': pages, 'per_page': per_page,
            'sort': sort if sort in df.columns else None, 'ascending': bool(ascending)}


def _clip(text):
    return text if len(text) <= CELL_MAX else text[:CELL_MAX - 1] + '…'


def full_view(df, columns=None, search='', filters=None, lines=None, sort=None, ascending=True, key=None, types=None):
    """Le même tri et les mêmes filtres que `query`, sans pagination : toutes les lignes retenues (export de la vue)."""
    first = query(df, columns, search, filters, lines, sort, ascending, 1, 200, key, types)
    out = [first['rows']]
    for page in range(2, first['pages'] + 1):
        out.append(query(df, columns, search, filters, lines, sort, ascending, page, 200, key, types)['rows'])
    return first['columns'], [row for chunk in out for row in chunk]


# ─── Fiche d'une soumission ──────────────────────────────────────────────────

def flags_by_line(result):
    """{numéro de ligne: [constats]} d'après le résultat de la validation. Un constat : gravité, catégorie, titre, détail, variables."""
    out = {}
    for check in (result or {}).get('checks', []):
        info = {k: check.get(k) for k in ('severite', 'categorie', 'titre', 'detail')}
        info['variables'] = list(check.get('variables') or [])
        for line in check.get('lignes', []):
            out.setdefault(int(line), []).append(info)
    return out


def row_severity(flags):
    """Pire gravité d'une ligne : « erreur », « a_verifier » (les constats statistiques n'en font pas partie), ou None."""
    kinds = {str(f['severite']).lower() for f in flags or [] if f.get('categorie') != 'Valeurs extrêmes'}
    return 'erreur' if 'erreur' in kinds else ('a_verifier' if 'a_verifier' in kinds else None)


def card(df, line, labels=None, flags=None, types=None, excluded=False):
    """Fiche de la soumission `line` : réponses par section (libellé, valeur), anomalies de la ligne, navigation."""
    n = len(df)
    if not 1 <= line <= n:
        return None
    labels, types = labels or {}, types or {}
    row = df.iloc[line - 1]
    line_flags = (flags or {}).get(line, [])
    flagged_columns = {}
    for f in line_flags:
        for v in f['variables']:
            flagged_columns.setdefault(v, []).append(f['titre'])
    sections, answered = {}, 0
    for col in df.columns:
        text = cell_text(row[col])
        answered += bool(text)
        sections.setdefault(dataset.section_of(col) or 'Général', []).append(
            {'column': col, 'label': labels.get(col) or dataset.readable(col), 'value': text, 'type': types.get(col, ''),
             'flags': flagged_columns.get(col, [])})
    flagged_lines = sorted((flags or {}).keys())
    before = [x for x in flagged_lines if x < line]
    after = [x for x in flagged_lines if x > line]
    return {'line': line, 'n': n, 'answered': answered, 'fields': len(df.columns), 'excluded': bool(excluded),
            'sections': [{'name': name, 'items': items} for name, items in sections.items()],
            'flags': line_flags, 'severity': row_severity(line_flags),
            'prev': line - 1 if line > 1 else None, 'next': line + 1 if line < n else None,
            'prev_flagged': before[-1] if before else None, 'next_flagged': after[0] if after else None}
