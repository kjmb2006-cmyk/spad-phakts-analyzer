"""
Analyse multi-enquête — fusion de plusieurs fichiers Excel
en tenant compte de la codification PHAKTS (DPF).

Principe : chaque colonne PHAKTS est de la forme
    Radical__TYPE!contrainte         (ex. Age__1Y!0<N<120)
On extrait le radical (avant le « __ ») pour aligner les variables
d'enquêtes différentes même si la contrainte ou les modalités diffèrent.
"""
import re
import os
import pandas as pd
import numpy as np
import plotly.express as px


# ─── Extraction du code PHAKTS / radical ─────────────────────────────────────
_PHAKTS_TYPE_RX = re.compile(
    r'^(?P<radical>.+?)__(?P<type>B|X|1Y|1M|1W|1D|1H|1U|1|2K|2T|2L|2S|2|Z|A|SRC)'
    r'(?P<rest>.*)$'
)


def phakts_radical(col: str) -> str:
    """Renvoie le radical PHAKTS d'une colonne, ou la colonne nettoyée."""
    if not col:
        return ''
    s = str(col).strip()
    m = _PHAKTS_TYPE_RX.match(s)
    if m:
        return m.group('radical')
    return s


def phakts_type(col: str) -> str:
    """Renvoie le type PHAKTS (B, X, 1Y, …) ou ''."""
    m = _PHAKTS_TYPE_RX.match(str(col or '').strip())
    return m.group('type') if m else ''


def is_phakts_coded(col: str) -> bool:
    return bool(_PHAKTS_TYPE_RX.match(str(col or '').strip()))


# ─── Fusion multi-enquêtes ───────────────────────────────────────────────────
def merge_surveys(surveys: dict, mode: str = 'phakts') -> pd.DataFrame:
    """
    Fusionne plusieurs enquêtes en un seul DataFrame.

    Args:
        surveys : { nom_enquête : DataFrame }
        mode    : 'phakts'    → aligne par radical PHAKTS (recommandé)
                  'exact'     → aligne par nom de colonne exact
                  'union'     → conserve toutes les colonnes (NaN où absent)

    Le DataFrame résultant contient une colonne `__survey__` indiquant
    l'enquête d'origine de chaque observation.
    """
    if not surveys:
        raise ValueError("Aucune enquête fournie.")

    if mode == 'phakts':
        # Pour chaque enquête, on renomme les colonnes PHAKTS par leur radical.
        renamed = {}
        for name, df in surveys.items():
            mapping = {c: phakts_radical(c) for c in df.columns}
            d2 = df.rename(columns=mapping).copy()
            # Si plusieurs colonnes mappent vers le même radical, on garde la 1ʳᵉ
            d2 = d2.loc[:, ~d2.columns.duplicated()]
            d2['__survey__'] = name
            renamed[name] = d2
        merged = pd.concat(renamed.values(), ignore_index=True, sort=False)
    elif mode == 'exact':
        # Union sur colonnes exactes (seules celles présentes dans toutes les enquêtes
        # sont mises côte à côte, les autres deviennent NaN)
        framed = []
        for name, df in surveys.items():
            d2 = df.copy()
            d2['__survey__'] = name
            framed.append(d2)
        merged = pd.concat(framed, ignore_index=True, sort=False)
    else:  # union
        framed = []
        for name, df in surveys.items():
            d2 = df.copy()
            d2['__survey__'] = name
            framed.append(d2)
        merged = pd.concat(framed, ignore_index=True, sort=False)

    return merged


def variable_coverage(surveys: dict, mode: str = 'phakts') -> pd.DataFrame:
    """
    Renvoie une matrice de couverture variable × enquête (1 = présent, 0 = absent).
    """
    if mode == 'phakts':
        cols_by_survey = {name: set(phakts_radical(c) for c in df.columns)
                           for name, df in surveys.items()}
    else:
        cols_by_survey = {name: set(df.columns) for name, df in surveys.items()}

    all_vars = sorted(set().union(*cols_by_survey.values()))
    matrix = pd.DataFrame(
        {name: [int(v in cols) for v in all_vars]
         for name, cols in cols_by_survey.items()},
        index=all_vars,
    )
    matrix['Total enquêtes'] = matrix.sum(axis=1)
    return matrix.sort_values('Total enquêtes', ascending=False)


def common_variables(surveys: dict, mode: str = 'phakts') -> list:
    """Variables présentes dans TOUTES les enquêtes."""
    if mode == 'phakts':
        sets = [set(phakts_radical(c) for c in df.columns) for df in surveys.values()]
    else:
        sets = [set(df.columns) for df in surveys.values()]
    return sorted(set.intersection(*sets)) if sets else []


# ─── Analyses sur le dataframe fusionné ──────────────────────────────────────
def compare_categorical_by_survey(merged: pd.DataFrame, variable: str) -> dict:
    """
    Compare la distribution d'une variable catégorielle entre enquêtes.
    """
    if variable not in merged.columns:
        raise ValueError(f"Variable {variable!r} absente du jeu fusionné.")
    sub = merged[['__survey__', variable]].dropna()
    if sub.empty:
        raise ValueError("Aucune observation disponible.")
    ct = pd.crosstab(sub[variable], sub['__survey__'])
    pct = ct.div(ct.sum(axis=0), axis=1).mul(100).round(1)

    fig = px.bar(
        pct.reset_index().melt(id_vars=variable, var_name='Enquête', value_name='%'),
        x=variable, y='%', color='Enquête', barmode='group',
        title=f'Comparaison de {variable} entre enquêtes',
        color_discrete_sequence=px.colors.qualitative.Set2,
        text_auto='.1f',
    )
    fig.update_layout(height=420, plot_bgcolor='white', paper_bgcolor='white',
                      font=dict(family='Inter, sans-serif'))

    return {
        'variable': variable,
        'count_html': ct.to_html(classes='table table-sm table-bordered text-center',
                                  border=0, na_rep='—'),
        'pct_html': pct.to_html(classes='table table-sm table-bordered text-center',
                                 border=0, na_rep='—',
                                 float_format=lambda x: f'{x:.1f}'),
        'chart': fig.to_json(),
        'n_total': int(ct.values.sum()),
    }


def compare_continuous_by_survey(merged: pd.DataFrame, variable: str) -> dict:
    """
    Compare une variable continue entre enquêtes (moyenne, médiane, écart-type).
    """
    if variable not in merged.columns:
        raise ValueError(f"Variable {variable!r} absente du jeu fusionné.")
    sub = merged[['__survey__', variable]].copy()
    sub[variable] = pd.to_numeric(sub[variable], errors='coerce')
    sub = sub.dropna()
    if sub.empty:
        raise ValueError("Aucune valeur numérique disponible.")

    summary = sub.groupby('__survey__')[variable].agg(['count', 'mean', 'median', 'std', 'min', 'max']).round(2)
    summary.columns = ['Effectif', 'Moyenne', 'Médiane', 'Écart-type', 'Min', 'Max']

    fig = px.box(sub, x='__survey__', y=variable,
                 title=f'Distribution de {variable} par enquête',
                 color='__survey__',
                 color_discrete_sequence=px.colors.qualitative.Set2)
    fig.update_layout(height=420, plot_bgcolor='white', paper_bgcolor='white',
                      showlegend=False, font=dict(family='Inter, sans-serif'))

    return {
        'variable': variable,
        'summary_html': summary.to_html(classes='table table-sm table-bordered text-center',
                                          border=0, na_rep='—'),
        'chart': fig.to_json(),
        'n_total': int(summary['Effectif'].sum()),
    }
