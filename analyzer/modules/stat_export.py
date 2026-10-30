"""
SPAD Analyzer — Exports SPSS (.sav) et Stata (.dta)

Stratégie d'analyse prévue par le document « Concepts & Fonctionnalités » du
SPAD : les données sortent de la plateforme vers les logiciels de l'analyste,
avec leurs libellés.

  - Libellé de variable : libellé de la question Kobo s'il est connu, sinon
    celui saisi dans l'Analyzer, sinon le radical PHAKTS lisible.
  - Modalités : les variables catégorielles (choix Kobo, ou texte à peu de
    valeurs distinctes) sont recodées 1, 2, 3… avec une étiquette par code,
    dans l'ordre des choix du formulaire quand il est connu.
  - Noms : les directives PHAKTS (`!0<N<120`, `!1*Sport_`) et caractères
    interdits sont retirés ; au-delà de 32 caractères (limite Stata), le nom
    est raccourci selon la règle du Transcode (3 premières lettres de chaque
    particule). Le code PHAKTS complet reste dans le libellé.
"""
import os
import re
import tempfile
import unicodedata

import pandas as pd

MAX_CATEGORIES = 60          # au-delà, une variable texte reste du texte
LIMITS = {'sav': {'name': 64, 'label': 256, 'string': 32767},
          'dta': {'name': 32, 'label': 80, 'string': 2045}}


def _ascii(s):
    return unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()


def _short_name(code, max_len):
    """Nom de variable valide pour SPSS/Stata, dérivé du code PHAKTS."""
    base = _ascii(str(code).split('!', 1)[0]).replace('/', '_')
    base = re.sub(r'[^A-Za-z0-9_]', '_', base).strip('_') or 'v'
    if len(base) > max_len:
        parts = re.split(r'(_+)', base)
        base = ''.join(p if (p.startswith('_') or p.isdigit() or len(p) <= 3) else p[:3]
                       for p in parts)
    if not re.match(r'[A-Za-z]', base):
        base = 'v_' + base
    return base[:max_len]


def _unique_names(columns, max_len):
    names, used = {}, set()
    for col in columns:
        name = _short_name(col, max_len)
        candidate, i = name, 2
        while candidate.lower() in used:
            suffix = f'_{i}'
            candidate = name[:max_len - len(suffix)] + suffix
            i += 1
        used.add(candidate.lower())
        names[col] = candidate
    return names


def _phakts_label(code):
    base = str(code).split('__', 1)[0].split('/')[-1]
    return base.replace('_', ' ').strip()


def kobo_dictionary(structure):
    """{colonne: (libellé, [(valeur, libellé), …] ou None)} depuis la
    structure Kobo (get_asset_structure)."""
    if not structure or not structure.get('success'):
        return {}
    lists = {}
    for c in structure.get('choices', []):
        lists.setdefault(c.get('list_name'), []).append((str(c.get('name')), c.get('label') or str(c.get('name'))))
    out = {}
    for q in structure.get('survey', []):
        name = q.get('name')
        if not name:
            continue
        qtype = (q.get('type') or '').split()
        choices = lists.get(qtype[1]) if len(qtype) > 1 and qtype[0] == 'select_one' else None
        out[name] = (q.get('label') or '', choices)
    return out


def _date_like(series):
    sample = series.dropna().astype(str).head(50)
    return len(sample) > 0 and sample.str.match(r'^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2})?').mean() > 0.9


def prepare(df, fmt, kobo=None, user_labels=None):
    """Renvoie (df_converti, libellés, étiquettes de modalités, mesures)."""
    kobo = kobo or {}
    user_labels = user_labels or {}
    lim = LIMITS[fmt]
    names = _unique_names(df.columns, lim['name'])
    out = pd.DataFrame(index=df.index)
    labels, value_labels, measures = [], {}, {}

    for col in df.columns:
        name = names[col]
        s = df[col]
        kobo_label, choices = kobo.get(col, kobo.get(str(col).split('/')[-1], ('', None)))
        label = (kobo_label or user_labels.get(col, '') or _phakts_label(col)).strip()
        if name != col:
            label = f'{label} [{col}]'
        labels.append(label[:lim['label']])

        if pd.api.types.is_datetime64_any_dtype(s):
            out[name] = s.dt.tz_localize(None) if getattr(s.dt, 'tz', None) else s
            continue
        if pd.api.types.is_bool_dtype(s):
            out[name] = s.astype('float')
            continue
        if pd.api.types.is_numeric_dtype(s):
            out[name] = s
            measures[name] = 'scale'
            continue

        text = s.where(s.isna(), s.astype(str))
        if _date_like(text):
            parsed = pd.to_datetime(text, errors='coerce', utc=True).dt.tz_localize(None)
            if parsed.notna().sum() >= text.notna().sum() * 0.9:
                out[name] = parsed
                continue

        distinct = text.dropna().unique()
        if choices or (0 < len(distinct) <= MAX_CATEGORIES and len(distinct) < max(2, len(text.dropna()) * 0.5)):
            order = [v for v, _ in choices] if choices else []
            order += sorted(v for v in distinct if v not in order)
            texts = dict(choices or [])
            codes = {v: i for i, v in enumerate(order, start=1)}
            out[name] = text.map(codes).astype('float')
            value_labels[name] = {float(codes[v]): str(texts.get(v, v))[:120] for v in order}
            measures[name] = 'nominal'
        else:
            out[name] = text.fillna('').str.slice(0, lim['string'])
    return out, labels, value_labels, measures


def export(df, fmt, kobo=None, user_labels=None, note=''):
    """Fichier SPSS (fmt='sav') ou Stata (fmt='dta') en octets."""
    import pyreadstat
    data, labels, value_labels, measures = prepare(df, fmt, kobo, user_labels)
    fd, path = tempfile.mkstemp(suffix='.' + fmt)
    os.close(fd)
    try:
        if fmt == 'sav':
            pyreadstat.write_sav(data, path, column_labels=labels, variable_value_labels=value_labels,
                                 variable_measure=measures, note=note or None)
        else:
            pyreadstat.write_dta(data, path, column_labels=labels, variable_value_labels=value_labels,
                                 file_label=note[:80])
        with open(path, 'rb') as f:
            return f.read()
    finally:
        os.remove(path)
