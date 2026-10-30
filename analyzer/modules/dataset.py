"""
SPAD Analyzer — Jeu de données chargé : ce qui s'y ajoute sans le modifier

Le fichier chargé (Excel nettoyé) n'est jamais réécrit par les analyses. Ce qui s'y rattache est
rangé à côté, dans des fichiers « sidecar » nommés d'après lui :

  <fichier>.labels.json    libellés des questions et des modalités (XLSForm ou structure Kobo)
  <fichier>.derived.json   variables calculées, ex. la classe d'une classification
  <fichier>.excluded.json  lignes écartées de l'analyse (page « Validation des données »)

Les numéros de ligne sont ceux du fichier complet (1 = première soumission) : des soumissions
ajoutées à la fin par la synchronisation Kobo ne les déplacent pas.

Ce module sert aussi à lire le jeu « comme un analyste » : modalités sous leur vrai nom, questions à
choix multiples éclatées en une colonne par choix, et variables typées d'après l'affixe PHAKTS
(une date, un identifiant ou un texte libre n'est pas une variable à tabuler).
"""
import json
import os
import re
import threading

import pandas as pd

from modules import choice_labels
from modules.data_loader import get_var_types
from modules.phakts_codes import affix_of, alignment_key, stem_of

_CACHE = {}
_LOCK = threading.Lock()
_CACHE_MAX = 2
_CACHE_BYTES = 100 * 1024 * 1024        # un jeu plus lourd n'est pas gardé en mémoire (relu à chaque demande)


# ─── Lecture du fichier ──────────────────────────────────────────────────────

def read_frame(path):
    """Fichier chargé, lu une fois par version (chemin + date de modification) tant qu'il reste raisonnable en mémoire ;
    une copie est renvoyée, jamais l'exemplaire partagé."""
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return None
    with _LOCK:
        df = _CACHE.get(key)
    if df is None:
        df = pd.read_excel(path)
        if df.memory_usage(deep=True).sum() <= _CACHE_BYTES:
            with _LOCK:
                for old in [k for k in _CACHE if k[0] == path]:
                    _CACHE.pop(old, None)
                while len(_CACHE) >= _CACHE_MAX:
                    _CACHE.pop(next(iter(_CACHE)))
                _CACHE[key] = df
            return df.copy()
        return df
    return df.copy()


# ─── Fichiers sidecar ────────────────────────────────────────────────────────

def sidecar(path, kind):
    return f'{path}.{kind}.json'


def _read_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


# ─── Variables dérivées ──────────────────────────────────────────────────────

def derived_names(path):
    return list(_read_json(sidecar(path, 'derived'), {}))


def save_derived(path, name, values_by_position, n_rows):
    """Enregistre la variable `name` : {position (0 = première ligne): valeur}. Les lignes absentes
    (non classées : valeurs manquantes) restent vides."""
    data = _read_json(sidecar(path, 'derived'), {})
    column = [None] * int(n_rows)
    for pos, value in values_by_position.items():
        if 0 <= int(pos) < len(column):
            column[int(pos)] = value
    data[name] = column
    _write_json(sidecar(path, 'derived'), data)


def delete_derived(path, name):
    data = _read_json(sidecar(path, 'derived'), {})
    if name in data:
        data.pop(name)
        _write_json(sidecar(path, 'derived'), data)
        return True
    return False


def attach_derived(df, path):
    data = _read_json(sidecar(path, 'derived'), {})
    if not data:
        return df
    out = df.copy()
    for name, values in data.items():
        column = list(values)[:len(out)]
        column += [None] * (len(out) - len(column))          # soumissions arrivées depuis (synchronisation)
        out[name] = column
    return out


# ─── Lignes écartées de l'analyse ────────────────────────────────────────────

def excluded_rows(path):
    data = _read_json(sidecar(path, 'excluded'), {})
    return sorted({int(x) for x in data.get('rows', [])})


def excluded_info(path):
    return _read_json(sidecar(path, 'excluded'), {})


def set_excluded(path, rows, note=''):
    rows = sorted({int(r) for r in rows if int(r) >= 1})
    if rows:
        _write_json(sidecar(path, 'excluded'), {'rows': rows, 'note': note})
    else:
        clear_excluded(path)
    return rows


def clear_excluded(path):
    try:
        os.remove(sidecar(path, 'excluded'))
    except OSError:
        pass


def apply_exclusions(df, path):
    """Jeu sans les lignes écartées. L'index d'origine est conservé : index + 1 = numéro de ligne."""
    rows = excluded_rows(path)
    if not rows:
        return df
    return df.drop(index=[r - 1 for r in rows if 0 <= r - 1 < len(df)])


# ─── Libellés ────────────────────────────────────────────────────────────────

def load_labels(path):
    return choice_labels.load(sidecar(path, 'labels'))


def save_labels(path, labels):
    if choice_labels.is_empty(labels):
        return False
    choice_labels.save(sidecar(path, 'labels'), labels)
    return True


def clear_labels(path):
    for kind in ('labels', 'xlsform'):
        try:
            os.remove(sidecar(path, kind))
        except OSError:
            pass


def save_form(path, form):
    """Définition du formulaire (questions, sauts de logique, contraintes, listes de choix) : voir modules/xlsform_checks.py."""
    if form and form.get('questions'):
        _write_json(sidecar(path, 'xlsform'), form)
        return True
    return False


def load_form(path):
    return _read_json(sidecar(path, 'xlsform'), None)


def clear_form(path):
    try:
        os.remove(sidecar(path, 'xlsform'))
    except OSError:
        pass


def column_labels(columns, labels):
    """{colonne: texte de la question} pour les colonnes que le dictionnaire connaît. Une case d'un choix
    multiple (Question__X/option) reçoit « Question — option »."""
    vmap = choice_labels.variable_label_map(labels)
    if not vmap:
        return {}
    out = {}
    for col in columns:
        text = str(col)
        label = (vmap.get(alignment_key(text, keep_path=True)) or vmap.get(alignment_key(text))
                 or vmap.get(text) or vmap.get(text.split('/')[-1]))
        if label:
            out[col] = label
    return out


# ─── Questions à choix multiples ─────────────────────────────────────────────

_TOKEN = re.compile(r'^[A-Za-z0-9_\-\.]+$')
MAX_CHOICES = 40


def _looks_multiple(series):
    """Une question à choix multiples stockée en une colonne (« a b c ») se reconnaît à ses valeurs : des choix séparés par
    des espaces, dont la plupart apparaissent AUSSI seuls dans au moins une réponse. « Sage femme » ou « Classe 1 » ne passent
    pas : « Sage » ou « Classe » n'est jamais une réponse à lui seul. En cas de doute, la colonne reste telle quelle ;
    l'XLSForm joint lève le doute (voir `labels['multiple']`)."""
    values = series.dropna().head(1000).astype(str).str.strip()        # un échantillon suffit pour reconnaître la forme des valeurs
    values = values[values != '']
    if len(values) < 5:
        return False
    spaced = values.str.contains(r'\s', regex=True)
    if spaced.mean() < 0.3:
        return False
    tokens = values.str.split()
    if not all(_TOKEN.match(t) for toks in tokens.head(200) for t in toks):
        return False
    distinct = {t for toks in tokens for t in toks}
    if not 2 <= len(distinct) <= MAX_CHOICES or tokens.map(len).mean() <= 1.1:
        return False
    alone = set(values[~spaced])
    return len(alone) >= 2 and len(distinct & alone) >= 0.5 * len(distinct)


def _choice_names(column, labels):
    for name in (str(column), str(column).split('/')[-1], alignment_key(str(column)), alignment_key(str(column), keep_path=True)):
        if name in (labels.get('choices') or {}):
            return labels['choices'][name]
    return {}


def expand_multiple(df, labels=None):
    """Remplace chaque question à choix multiples stockée dans UNE colonne (« a b c ») par une colonne 0/1 par
    choix, nommée « Question/Choix » : le groupe est alors reconnu comme tel (tri à plat des choix, croisements).
    Une question est reconnue par l'XLSForm ou, à défaut, par la forme de ses valeurs."""
    labels = labels or choice_labels.empty()
    known = set(labels.get('multiple') or [])
    out = df
    for col in list(df.columns):
        s = df[col]
        if s.dtype != object or '/' in str(col).rsplit('/', 1)[-1]:
            continue
        declared = any(n in known for n in (str(col), str(col).split('/')[-1], alignment_key(str(col))))
        if not (declared or _looks_multiple(s)):
            continue
        names = _choice_names(col, labels)
        text = s.fillna('').astype(str)
        tokens = sorted({t for v in text for t in v.split()})
        if not 1 < len(tokens) <= MAX_CHOICES:
            continue
        if out is df:
            out = df.copy()
        position = list(out.columns).index(col)
        answered = s.notna() & (text.str.strip() != '')
        new = {}
        for t in tokens:
            flag = text.map(lambda v, _t=t: 1 if _t in v.split() else 0).where(answered)
            new[f'{col}/{names.get(t) or choice_labels.prettify(t)}'] = flag
        out = out.drop(columns=[col])
        for i, (name, series) in enumerate(new.items()):
            out.insert(position + i, name, series)
    return out


def rename_option_columns(df, labels=None):
    """Les cases d'une question à choix multiples déjà éclatée par Kobo (« Question__X/maladies_respiratoires ») prennent le
    libellé du choix (XLSForm) ou, à défaut, leur nom mis en forme (« Maladies respiratoires »). Rien n'est renommé en cas de
    doublon : deux choix ne doivent jamais se confondre."""
    labels = labels or choice_labels.empty()
    mapping = {}
    for col in df.columns:
        text = str(col)
        if '/' not in text:
            continue
        parent, option = text.rsplit('/', 1)
        names = _choice_names(parent, labels)
        if option in names:
            new = names[option]
        elif affix_of(parent) in ('X', 'SRC') and re.fullmatch(r'[a-z0-9_]+', option):
            new = choice_labels.prettify(option)
        else:
            continue
        mapping[col] = f'{parent}/{new}'
    if not mapping or len(set(mapping.values()) | (set(df.columns) - set(mapping))) != len(df.columns):
        return df
    return df.rename(columns=mapping)


def display_frame(df, labels=None, uid_names=None):
    """Jeu tel que l'analyste le lit : choix multiples éclatés, modalités sous leur vrai nom."""
    labels = labels or choice_labels.empty()
    out = rename_option_columns(expand_multiple(df, labels), labels)
    return choice_labels.relabel_frame(out, labels, uid_names or {})


# ─── Types de variables d'après l'affixe PHAKTS ──────────────────────────────

ID_AFFIXES = ('E',)
TEXT_AFFIXES = ('Z',)
TECHNICAL_AFFIXES = ('G', 'P')
_TECHNICAL_COLUMNS = {'_id', '_uuid', 'start', 'end', 'today', 'deviceid', '_index', '_submission_time'}


def analysis_var_types(df, base=None):
    """get_var_types() corrigé par le code PHAKTS : date (A), identifiant (E), texte libre (Z), variable
    technique (G, P) — ce ne sont pas des variables à tabuler. Les types 'identifiant' restent proposés pour
    les croisements (par enquêteur, par établissement)."""
    types = dict(base if base is not None else get_var_types(df))
    for col in df.columns:
        if str(col).lower() in _TECHNICAL_COLUMNS or str(col).split('/')[-1].lower() in _TECHNICAL_COLUMNS:
            types[col] = 'technique'
            continue
        affix = affix_of(col)
        if affix == 'A':
            types[col] = 'date'
        elif affix in ID_AFFIXES:
            types[col] = 'identifiant'
        elif affix in TEXT_AFFIXES:
            types[col] = 'texte_libre'
        elif affix in TECHNICAL_AFFIXES:
            types[col] = 'technique'
    return types


def readable(name, limit=None):
    """Nom lisible d'une variable sans libellé : dernier segment du chemin, sans affixe PHAKTS ni directive
    (« METIER/Section_1/Anciennete_Fonction__1Y!0<N<60 » → « Anciennete Fonction »)."""
    last = str(name).split('/')[-1].split('!')[0]
    text = stem_of(last).replace('__', ' · ').replace('_', ' ').strip() or last
    return text if not limit or len(text) <= limit else text[:limit - 1] + '…'


def section_of(column):
    """Section (groupe Kobo) d'une colonne : « METIER_ETUDE/Section_1/Age__1Y » → « METIER_ETUDE/Section_1 »."""
    parts = str(column).split('/')
    return '/'.join(parts[:-1]) if len(parts) > 1 else ''
