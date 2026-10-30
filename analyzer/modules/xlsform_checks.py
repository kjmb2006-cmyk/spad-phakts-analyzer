"""
SPAD Analyzer — Contrôles issus du formulaire (XLSForm)

Le formulaire dit ce que les données ont le droit de contenir. Joint au jeu de données, il permet de retrouver :

  - une réponse HORS LISTE : un choix qui n'existe pas dans la liste de la question ;
  - une réponse OBLIGATOIRE absente : question « required » posée (son saut de logique est vrai) mais restée vide ;
  - un SAUT DE LOGIQUE violé : question répondue alors que son « relevant » est faux (enquêteur qui a contourné le saut,
    ou réponse d'avant une modification) ;
  - une CONTRAINTE violée : valeur qui échoue au « constraint » de la question (âge hors bornes, date future…).

Les expressions XPath du formulaire sont évaluées par modules/xlsform_expr.py ; ce que ce module ne sait pas évaluer
est signalé en information, jamais deviné.

La définition du formulaire est conservée à côté des données (<fichier>.xlsform.json) : une structure légère
{questions: [{name, type, list_name, required, relevant, constraint, constraint_message}], choices: {liste: {nom: libellé}}}.
"""
import re

import pandas as pd

from modules import choice_labels, xlsform_expr
from modules.validation_rules import A_VERIFIER, ERREUR, INFO, _check

CATEGORIE = 'Formulaire (XLSForm)'
SELECT_KINDS = ('select_one', 'select_multiple')


def _truthy(value):
    return str(value).strip().lower() in ('yes', 'true', 'true()', '1', 'oui')


def _label_column(df):
    cols = [c for c in df.columns if str(c).strip().lower().startswith('label')]
    return cols[0] if cols else None


# ─── Lecture de la définition ────────────────────────────────────────────────

def parse_xlsform(path):
    """Définition du formulaire depuis un classeur XLSForm (feuilles survey et choices). Lève ValueError sinon."""
    try:
        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    except Exception as e:
        raise ValueError(f'Classeur illisible : {e}')
    names = {k.strip().lower(): v for k, v in sheets.items()}
    if 'survey' not in names:
        raise ValueError("Ce classeur n'est pas un XLSForm (feuille « survey » absente).")
    survey = names['survey']
    choices = names.get('choices', pd.DataFrame(columns=['list_name', 'name']))
    lcol = _label_column(choices)
    lists = {}
    for _, row in choices.iterrows():
        ln, name = choice_labels._text(row.get('list_name')), choice_labels._text(row.get('name'))
        if ln and name:
            lists.setdefault(ln, {})[name] = (choice_labels._text(row.get(lcol)) if lcol else '') or name
    questions = []
    for _, row in survey.iterrows():
        name = choice_labels._text(row.get('name'))
        kind, _, list_name = choice_labels._text(row.get('type')).partition(' ')
        if not name or kind in ('begin_group', 'end_group', 'begin_repeat', 'end_repeat', 'note', 'start', 'end', 'today',
                                'deviceid', 'calculate', 'username', 'phonenumber', 'subscriberid', 'simserial'):
            continue
        questions.append({'name': name, 'type': kind, 'list_name': list_name.split()[0] if list_name else '',
                          'required': _truthy(row.get('required')), 'relevant': choice_labels._text(row.get('relevant')),
                          'constraint': choice_labels._text(row.get('constraint')),
                          'constraint_message': next((choice_labels._text(row.get(c)) for c in survey.columns
                                                      if str(c).lower().startswith('constraint_message') and choice_labels._text(row.get(c))), '')})
    return {'questions': questions, 'choices': lists}


def from_structure(structure):
    """Définition depuis la structure d'un formulaire Kobo (kobo_connector.get_asset_structure)."""
    if not structure or not structure.get('success'):
        return None
    lists = {}
    for c in structure.get('choices', []):
        ln, name = choice_labels._text(c.get('list_name')), choice_labels._text(c.get('name'))
        if ln and name:
            lists.setdefault(ln, {})[name] = choice_labels._text(c.get('label')) or name
    questions = []
    for q in structure.get('survey', []):
        name = choice_labels._text(q.get('name'))
        kind, _, inline = choice_labels._text(q.get('type')).partition(' ')
        if not name:
            continue
        questions.append({'name': name, 'type': kind, 'list_name': q.get('list_name') or inline.strip(),
                          'required': bool(q.get('required')), 'relevant': choice_labels._text(q.get('relevant')),
                          'constraint': choice_labels._text(q.get('constraint')),
                          'constraint_message': choice_labels._text(q.get('constraint_message'))})
    return {'questions': questions, 'choices': lists} if questions else None


# ─── Contrôles ───────────────────────────────────────────────────────────────

def _norm(value):
    s = str(value).strip().lower()
    return s[:-2] if re.fullmatch(r'-?\d+\.0', s) else s


def _column_index(df):
    """Nom de question → colonne du jeu (dernier segment du chemin de groupe)."""
    out = {}
    for col in df.columns:
        out.setdefault(str(col).split('/')[-1].split('!')[0], col)
    return out


def run_checks(df, form):
    """Contrôles du formulaire sur les données (valeurs d'origine). Renvoie des contrôles au format de
    validation_rules (ERREUR / A_VERIFIER / INFO)."""
    cols = _column_index(df)
    index = df.index
    positions = pd.RangeIndex(len(df))
    out, skipped = [], []

    def resolve(name):
        col = cols.get(name)
        return df[col].reset_index(drop=True) if col is not None else None

    for q in form.get('questions', []):
        col = cols.get(q['name'])
        if col is None:
            continue
        series = df[col].reset_index(drop=True)
        present = series.notna() & (series.astype(str).str.strip() != '')
        relevant = None
        if q['relevant']:
            try:
                relevant = xlsform_expr.evaluate(q['relevant'], resolve, positions)
            except xlsform_expr.Unsupported as e:
                skipped.append(f"saut de « {q['name']} » ({e})")
        title_var = f"{q['name']}"

        # 1. valeur hors liste
        allowed = form.get('choices', {}).get(q['list_name'])
        if q['type'] in SELECT_KINDS and allowed:
            ok_values = {_norm(k) for k in allowed} | {_norm(v) for v in allowed.values()}
            tokens = series.astype(str).where(present, '').map(lambda v: v.split() if q['type'] == 'select_multiple' else ([v.strip()] if v.strip() else []))
            if q['type'] == 'select_multiple':
                # des libellés de plusieurs mots ne se découpent pas : une valeur entière connue est acceptée telle quelle
                whole = series.astype(str).map(_norm).isin(ok_values)
                bad = present & ~whole & tokens.map(lambda toks: any(_norm(t) not in ok_values for t in toks))
            else:
                bad = present & ~series.astype(str).map(_norm).isin(ok_values)
            if bad.any():
                shown = sorted({str(v) for v in series[bad].head(200)})[:4]
                out.append(_check(CATEGORIE, f'Réponse hors de la liste de choix ({title_var})',
                                  f"Valeur(s) absente(s) de la liste « {q['list_name']} » : {', '.join(shown)}.", ERREUR, [col], bad.values))

        # 2. réponse obligatoire absente
        if q['required']:
            missing = ~present if relevant is None else (relevant & ~present)
            if missing.any():
                out.append(_check(CATEGORIE, f'Réponse obligatoire absente ({title_var})',
                                  "Question obligatoire restée vide alors que son saut de logique la rend applicable.", ERREUR, [col], missing.values))

        # 3. saut de logique violé
        if relevant is not None:
            answered_off = ~relevant & present
            if answered_off.any():
                out.append(_check(CATEGORIE, f'Question répondue alors qu\'elle devait être sautée ({title_var})',
                                  f"Condition d'affichage du formulaire : {q['relevant']}. Saut contourné, ou réponse antérieure à une "
                                  "modification du formulaire.", A_VERIFIER, [col], answered_off.values))

        # 4. contrainte violée
        if q['constraint']:
            try:
                satisfied = xlsform_expr.evaluate(q['constraint'], resolve, positions, self_value=series)
                broken = present & ~satisfied
                if broken.any():
                    out.append(_check(CATEGORIE, f'Contrainte du formulaire non respectée ({title_var})',
                                      (q['constraint_message'] + ' ' if q['constraint_message'] else '') + f"Contrainte : {q['constraint']}.",
                                      ERREUR, [col], broken.values))
            except xlsform_expr.Unsupported as e:
                skipped.append(f"contrainte de « {q['name']} » ({e})")

    if skipped:
        out.append(_check(CATEGORIE, f'{len(skipped)} contrôle(s) du formulaire non évalué(s)',
                          'Expressions que le contrôle ne sait pas lire : ' + '; '.join(skipped[:6]) + ('…' if len(skipped) > 6 else '') + '.',
                          INFO, []))
    return [c for c in out if c['lignes'] or c['severite'] == INFO]
