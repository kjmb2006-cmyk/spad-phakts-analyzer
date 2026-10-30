"""
SPAD Analyzer — Libellés des modalités

Les données KoboToolbox ne contiennent pas les libellés des choix mais leurs
NOMS internes : « femme », « maladies_respiratoires », ou un identifiant
généré. C'est ce que l'on voit dans les exports « valeurs XML » (le « False »
du nom de fichier) et dans les données lues par l'API. Pour comparer des
enquêtes on veut lire « Femme », « Maladies respiratoires » — les vraies
modalités.

Un dictionnaire de libellés (« labels ») se construit à partir :
  - de la structure du formulaire Kobo (survey + choices), à l'import ;
  - d'un XLSForm joint à l'enquête (celui de PHAKTS Studio, ou l'export XLSForm
    de Kobo), quand les données viennent d'un fichier ;
  - de la base centrale, qui le conserve avec chaque enquête versée.

À défaut, la lecture reste possible : un nom lisible est reconstitué
(« faible_poids_naissance » → « Faible poids naissance ») et un identifiant de
formulaire Kobo connu est remplacé par le nom du formulaire. Seules les
valeurs AFFICHÉES changent : les calculs portent sur les mêmes données.

Format du dictionnaire (JSON) :
    {'questions': {nom de question: libellé},
     'choices':   {nom de question: {nom du choix: libellé}},
     'multiple':  [noms des questions à choix multiple]}
"""
import json
import os
import re

import pandas as pd

from modules.phakts_codes import affix_of, alignment_key

CHOICE_AFFIXES = ('X', 'SRC', 'B', 'C')
_SLUG = re.compile(r'^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$')
KOBO_UID = re.compile(r'^a[A-Za-z0-9]{21}$')


def empty():
    return {'questions': {}, 'choices': {}, 'multiple': []}


def is_empty(labels):
    return not labels or not (labels.get('choices') or labels.get('questions'))


# ─── Sources ─────────────────────────────────────────────────────────────────

def _text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    if isinstance(value, list):
        value = value[0] if value else ''
    return str(value).strip()


def from_kobo_structure(structure):
    """Depuis kobo_connector.get_asset_structure() : {'survey': […], 'choices': […]}."""
    labels = empty()
    if not structure or not structure.get('success'):
        return labels
    lists = {}
    for c in structure.get('choices', []):
        name = _text(c.get('name'))
        if name:
            lists.setdefault(c.get('list_name'), {})[name] = _text(c.get('label')) or name
    for q in structure.get('survey', []):
        name = _text(q.get('name'))
        if not name:
            continue
        if _text(q.get('label')):
            labels['questions'][name] = _text(q['label'])
        kind, _, inline_list = _text(q.get('type')).partition(' ')
        list_name = q.get('list_name') or inline_list.strip() or None
        if kind in ('select_one', 'select_multiple') and list_name in lists:
            labels['choices'][name] = lists[list_name]
            if kind == 'select_multiple':
                labels['multiple'].append(name)
    return labels


def from_xlsform(path):
    """Depuis un XLSForm (feuilles « survey » et « choices »). Lève ValueError
    si le classeur n'en est pas un."""
    try:
        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    except Exception as e:
        raise ValueError(f'Classeur illisible : {e}')
    names = {k.strip().lower(): v for k, v in sheets.items()}
    if 'survey' not in names:
        found = ', '.join(f'« {k.strip()} »' for k in list(sheets)[:6]) or 'aucune'
        raise ValueError("Ce classeur n'est pas un XLSForm : il lui faut une feuille « survey » (et « choices » s'il a des "
                         f"questions à choix). Feuilles trouvées : {found}. L'XLSForm est le fichier du FORMULAIRE "
                         "(celui de PHAKTS Studio, ou « Télécharger XLS » dans KoboToolbox), pas l'export des données.")
    survey = names['survey']
    # Un formulaire sans aucune question à choix n'a pas de feuille « choices » dans l'export de Kobo.
    choices = names.get('choices', pd.DataFrame(columns=['list_name', 'name']))

    def label_column(df):
        cols = [c for c in df.columns if str(c).strip().lower().startswith('label')]
        # « label::French (fr) » avant un éventuel « label::English (en) » : la première fait foi
        return cols[0] if cols else None

    labels = empty()
    lcol = label_column(choices)
    if 'list_name' not in choices.columns or 'name' not in choices.columns:
        raise ValueError("La feuille « choices » doit avoir les colonnes list_name et name.")
    lists = {}
    for _, row in choices.iterrows():
        ln, name = _text(row.get('list_name')), _text(row.get('name'))
        if ln and name:
            lists.setdefault(ln, {})[name] = (_text(row.get(lcol)) if lcol else '') or name
    qcol = label_column(survey)
    for _, row in survey.iterrows():
        name = _text(row.get('name'))
        kind, _, list_name = _text(row.get('type')).partition(' ')
        if not name:
            continue
        if qcol and _text(row.get(qcol)):
            labels['questions'][name] = _text(row.get(qcol))
        list_name = list_name.split()[0] if list_name else ''
        if kind in ('select_one', 'select_multiple') and list_name in lists:
            labels['choices'][name] = lists[list_name]
            if kind == 'select_multiple':
                labels['multiple'].append(name)
    if not labels['choices'] and not labels['questions']:
        raise ValueError('Aucune question ni aucun choix lisible dans cet XLSForm.')
    return labels


# ─── Conservation ────────────────────────────────────────────────────────────

def save(path, labels):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(labels, f, ensure_ascii=False)
    os.replace(tmp, path)


def load(path):
    if not path or not os.path.exists(path):
        return empty()
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return empty()
    return {'questions': data.get('questions') or {}, 'choices': data.get('choices') or {},
            'multiple': data.get('multiple') or []}


def merge(dictionaries):
    """Réunit plusieurs dictionnaires ; le premier qui définit un libellé l'emporte."""
    out = empty()
    for d in dictionaries:
        for name, label in (d.get('questions') or {}).items():
            out['questions'].setdefault(name, label)
        for name, mapping in (d.get('choices') or {}).items():
            out['choices'].setdefault(name, {}).update({k: v for k, v in mapping.items()
                                                        if k not in out['choices'][name]})
        for name in d.get('multiple') or []:
            if name not in out['multiple']:
                out['multiple'].append(name)
    return out


# ─── Lecture des valeurs ─────────────────────────────────────────────────────

def prettify(token):
    """« faible_poids_naissance » → « Faible poids naissance ». Les valeurs qui
    ne sont pas des noms internes (majuscules, chiffres, ponctuation) restent telles quelles."""
    token = str(token)
    if _SLUG.match(token):
        return token.replace('_', ' ').capitalize()
    return token


def _candidates(column):
    column = str(column)
    seen = []
    for name in (column, column.split('/')[-1], alignment_key(column), alignment_key(column).split('/')[-1]):
        if name not in seen:
            seen.append(name)
    return seen


def _choice_mapping(column, labels):
    for name in _candidates(column):
        if name in labels['choices']:
            return labels['choices'][name], name in labels['multiple']
    return None, False


def relabel_frame(df, labels=None, uid_names=None, prettify_values=True):
    """Copie du tableau où les noms internes des modalités sont remplacés par
    leurs libellés. Ordre de résolution : libellé du formulaire, nom de
    formulaire Kobo connu (uid_names), sinon nom lisible reconstitué. Les
    colonnes numériques, les cases 0/1 d'un choix multiple et les colonnes
    qui ne sont pas des choix sont laissées intactes."""
    labels = labels or empty()
    uid_names = uid_names or {}
    out = None
    for col in df.columns:
        s = df[col]
        if s.dtype != object:
            continue
        mapping, multiple = _choice_mapping(col, labels)
        tail = str(col).split('/')[-1]
        is_option = '/' in str(col) and affix_of(str(col).rsplit('/', 1)[0]) in CHOICE_AFFIXES
        is_choice = mapping is not None or (not is_option and affix_of(col) in CHOICE_AFFIXES)
        has_uid = bool(uid_names) and s.isin(uid_names).any()
        if not (is_choice or has_uid):
            continue

        def one(token, _mapping=mapping):
            if _mapping and token in _mapping:
                return _mapping[token]
            if token in uid_names:
                return uid_names[token]
            return prettify(token) if (prettify_values and is_choice) else token

        table = {}
        for value in s.dropna().unique():
            if not isinstance(value, str):
                continue
            if multiple or (is_choice and ' ' in value.strip() and all(_SLUG.match(t) for t in value.split())):
                table[value] = ', '.join(one(t) for t in value.split())
            else:
                table[value] = one(value)
        if any(k != v for k, v in table.items()):
            if out is None:
                out = df.copy()
            out[col] = s.map(table).where(s.notna())
    return df if out is None else out


def variable_label_map(labels):
    """{clé d'alignement: libellé} — « Sexe du répondant », et pour une case de
    choix multiple « Effets connus — Cancer »."""
    out = {}
    for name, label in (labels.get('questions') or {}).items():
        out.setdefault(alignment_key(name, keep_path=True), label)
    for name in labels.get('multiple') or []:
        for choice, text in (labels['choices'].get(name) or {}).items():
            base = labels['questions'].get(name) or name
            out.setdefault(f'{alignment_key(name, keep_path=True)}/{choice}', f'{base} — {text}')
    return out
