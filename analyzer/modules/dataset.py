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

SIDECAR_KINDS = ('derived', 'excluded', 'labels', 'recipes', 'types', 'varlabels', 'xlsform')


def signature(path):
    """Empreinte du jeu : le fichier et tout ce qui change la façon de le lire (libellés, variables calculées, types, lignes écartées).
    Sert de clé aux caches de pages."""
    stamps = []
    for p in [path] + [f'{path}.{kind}.json' for kind in SIDECAR_KINDS]:
        try:
            stamps.append(os.path.getmtime(p))
        except OSError:
            stamps.append(0)
    return (path, tuple(stamps))


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
    """Joint au jeu les variables calculées : classes enregistrées (valeurs figées) puis recettes (recalculées à chaque lecture,
    donc appliquées aussi aux soumissions arrivées depuis)."""
    data = _read_json(sidecar(path, 'derived'), {})
    out = df
    if data:
        out = df.copy()
        for name, values in data.items():
            column = list(values)[:len(out)]
            column += [None] * (len(out) - len(column))          # soumissions arrivées depuis (synchronisation)
            out[name] = column
    return apply_recipes(out, path)[0]


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


def choice_names(column, labels):
    """{code: libellé} des choix d'une question (XLSForm joint), vide si inconnue."""
    return _choice_names(column, labels or choice_labels.empty())


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


def analysis_var_types(df, base=None, overrides=None):
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
    for col, forced in (overrides or {}).items():
        if col in types and forced in TYPE_CHOICES:
            types[col] = forced                                   # le choix de l'utilisateur l'emporte sur tout le reste
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


# ─── Types de variables corrigés par l'utilisateur ───────────────────────────

TYPE_CHOICES = {'categorielle': 'Catégorielle', 'continue': 'Continue', 'binaire': 'Binaire (0/1)', 'date': 'Date',
                'identifiant': 'Identifiant', 'texte_libre': 'Texte libre', 'technique': 'Technique (ignorée)'}


def type_overrides(path):
    return _read_json(sidecar(path, 'types'), {}) if path else {}


def _write_or_remove(path, kind, data):
    if data:
        _write_json(sidecar(path, kind), data)
    else:
        try:
            os.remove(sidecar(path, kind))
        except OSError:
            pass


def set_type_override(path, column, type_name):
    """Force le type d'une variable (None ou '' : retour au type détecté)."""
    data = _read_json(sidecar(path, 'types'), {})
    if type_name and type_name in TYPE_CHOICES:
        data[column] = type_name
    else:
        data.pop(column, None)
    _write_or_remove(path, 'types', data)


# ─── Libellés de variables saisis par l'utilisateur (conservés avec le jeu) ──

def user_labels(path):
    return _read_json(sidecar(path, 'varlabels'), {}) if path else {}


def set_user_label(path, column, label):
    data = _read_json(sidecar(path, 'varlabels'), {})
    label = (label or '').strip()
    if label:
        data[column] = label[:500]
    else:
        data.pop(column, None)
    _write_or_remove(path, 'varlabels', data)


# ─── Recettes : variables calculées à partir des autres ──────────────────────
#
# Une recette décrit comment calculer une variable ; elle est rejouée à chaque lecture du jeu. Genres :
#   mapping   : regrouper / recoder les valeurs d'une variable        {source, map: {valeur: groupe}, other: 'Autres' | None}
#   bins      : découper une variable numérique en classes            {source, edges: [bornes]}  ou {mode: 'quantiles', q}
#   formula   : calcul entre variables                                {expression: '${a} div (${b} * ${b})', decimals}
#   condition : oui / non selon une condition                         {expression: "${age} >= 18 and ${sexe} = 'femme'", yes, no}
#   date_part : année, mois, trimestre, semaine d'une date           {source, part}

RECIPE_KINDS = ('mapping', 'bins', 'formula', 'condition', 'date_part')
RECIPE_LABELS = {'mapping': 'Regroupement de modalités', 'bins': 'Classes', 'formula': 'Calcul', 'condition': 'Oui / non selon une condition',
                 'date_part': 'Partie de date'}
DATE_PARTS = {'annee': 'Année', 'mois': 'Mois', 'trimestre': 'Trimestre', 'semaine': 'Semaine', 'annee_mois': 'Année-mois'}
_NAME_OK = re.compile(r"^[A-Za-z0-9À-ÿ _\-\(\)\.']{1,60}$")


def recipes(path):
    return _read_json(sidecar(path, 'recipes'), []) if path else []


def add_recipe(path, recipe, existing_columns=()):
    """Enregistre une recette. Renvoie (ok, message). Le nom doit être neuf (ni colonne, ni variable calculée, ni recette)."""
    name = str(recipe.get('name') or '').strip()
    if recipe.get('kind') not in RECIPE_KINDS:
        return False, 'Genre de variable inconnu.'
    if not _NAME_OK.match(name):
        return False, "Nom invalide : 1 à 60 caractères (lettres, chiffres, espace, _ - ( ) . ' ; pas de « / »)."
    items = recipes(path)
    shorts = {str(c).split('/')[-1].split('!')[0] for c in existing_columns}          # « Age__1Y » désigne déjà « GRP/Age__1Y »
    taken = set(existing_columns) | shorts | {r['name'] for r in items} | set(derived_names(path))
    if name in taken:
        return False, f"Une variable « {name} » existe déjà : choisissez un autre nom."
    items.append(dict(recipe, name=name))
    _write_or_remove(path, 'recipes', items)
    return True, None


def delete_recipe(path, name):
    items = recipes(path)
    kept = [r for r in items if r['name'] != name]
    if len(kept) == len(items):
        return False
    _write_or_remove(path, 'recipes', kept)
    return True


def _norm_value(v):
    s = str(v).strip()
    return s[:-2] if re.fullmatch(r'-?\d+\.0', s) else s


def _resolver(frame):
    """Nom de question → colonne : nom exact, sinon dernier segment du chemin de groupe (sans directive)."""
    short = {}
    for col in frame.columns:
        short.setdefault(str(col).split('/')[-1].split('!')[0], col)

    def resolve(name):
        if name in frame.columns:
            return frame[name]
        col = short.get(name)
        return frame[col] if col is not None else None
    return resolve


def _bin_labels(edges):
    nums = [float(e) for e in edges]
    whole = all(n == int(n) for n in nums)
    fmt = (lambda x: str(int(x))) if whole else (lambda x: str(x).replace('.', ','))
    labels = [f'< {fmt(nums[0])}']
    for lo, hi in zip(nums, nums[1:]):
        if whole:
            labels.append(f'{fmt(lo)}–{fmt(hi - 1)}' if hi - lo > 1 else fmt(lo))
        else:
            labels.append(f'{fmt(lo)} à < {fmt(hi)}')
    labels.append(f'≥ {fmt(nums[-1])}')
    return labels


QUANTILE_NAMES = {3: ['Tiers inférieur', 'Tiers central', 'Tiers supérieur'],
                  4: ['Q1 (plus bas)', 'Q2', 'Q3', 'Q4 (plus haut)'],
                  5: ['Quintile 1 (plus bas)', 'Quintile 2', 'Quintile 3', 'Quintile 4', 'Quintile 5 (plus haut)']}


def compute_recipe(frame, recipe):
    """Colonne calculée (Series alignée sur `frame`). Lève ValueError avec un message lisible."""
    from modules import xlsform_expr
    kind = recipe['kind']
    resolve = _resolver(frame)
    index = frame.index

    def source():
        col = resolve(recipe.get('source', ''))
        if col is None:
            raise ValueError(f"variable « {recipe.get('source')} » absente des données")
        return col

    try:
        if kind == 'mapping':
            s = source()
            mapping = {_norm_value(k): v for k, v in (recipe.get('map') or {}).items()}
            other = recipe.get('other')
            out = s.map(lambda v: None if pd.isna(v) else mapping.get(_norm_value(v), other if other else str(v)))
            return out.where(s.notna())
        if kind == 'bins':
            num = pd.to_numeric(source(), errors='coerce')
            if recipe.get('mode') == 'quantiles':
                q = int(recipe.get('q') or 4)
                return pd.qcut(num, q, labels=QUANTILE_NAMES.get(q), duplicates='drop').astype(object).where(num.notna())
            edges = sorted(float(e) for e in recipe.get('edges') or [])
            if not edges:
                raise ValueError('aucune borne')
            cuts = pd.cut(num, bins=[-float('inf')] + edges + [float('inf')], right=False, labels=_bin_labels(edges))
            return cuts.astype(object).where(num.notna())
        if kind == 'formula':
            value = pd.to_numeric(xlsform_expr.evaluate_value(recipe['expression'], resolve, index), errors='coerce')
            value = value.replace([float('inf'), float('-inf')], float('nan'))
            return value.round(int(recipe['decimals'])) if recipe.get('decimals') not in (None, '') else value
        if kind == 'condition':
            ok = xlsform_expr.evaluate(recipe['expression'], resolve, index)
            return ok.map({True: recipe.get('yes') or 'Oui', False: recipe.get('no') or 'Non'})
        if kind == 'date_part':
            dates = pd.to_datetime(source(), errors='coerce', utc=True)
            part = recipe.get('part', 'annee')
            if part == 'annee':
                return dates.dt.year.astype('Int64').astype(object).where(dates.notna())
            if part == 'mois':
                return dates.dt.month.astype('Int64').astype(object).where(dates.notna())
            if part == 'trimestre':
                return ('T' + dates.dt.quarter.astype('Int64').astype(str)).where(dates.notna())
            if part == 'semaine':
                return dates.dt.isocalendar().week.astype('Int64').astype(object).where(dates.notna())
            if part == 'annee_mois':
                return dates.dt.strftime('%Y-%m').where(dates.notna())
            raise ValueError(f'partie de date inconnue : {part}')
    except xlsform_expr.Unsupported as e:
        raise ValueError(str(e))
    raise ValueError(f'genre de variable inconnu : {kind}')


def apply_recipes(df, path):
    """(jeu avec les variables calculées, {nom: erreur}). Une recette en erreur n'ajoute pas de colonne et est signalée."""
    items = recipes(path)
    if not items:
        return df, {}
    out, errors = df.copy(), {}
    for r in items:
        try:
            out[r['name']] = compute_recipe(out, r)
        except (ValueError, KeyError, TypeError) as e:
            errors[r['name']] = str(e)
    return out, errors


def value_options(series, labels=None, column=None, limit=200):
    """[(valeur brute, libellé, effectif)] des valeurs d'une variable, les plus fréquentes d'abord : pour proposer à l'utilisateur
    des modalités lisibles tout en gardant la valeur d'origine dans la recette."""
    labels = labels or choice_labels.empty()
    names = _choice_names(column, labels) if column is not None else {}
    out = []
    for value, n in series.dropna().astype(str).str.strip().value_counts().head(limit).items():
        out.append((value, names.get(value) or choice_labels.prettify(value), int(n)))
    return out


def lines_matching(df, expression):
    """Numéros de ligne (1 = première soumission) où la condition est vraie. Lève ValueError si l'expression est illisible."""
    from modules import xlsform_expr
    try:
        mask = xlsform_expr.evaluate(expression, _resolver(df), df.index)
    except xlsform_expr.Unsupported as e:
        raise ValueError(str(e))
    return [int(i) + 1 for i in df.index[mask.values]]
