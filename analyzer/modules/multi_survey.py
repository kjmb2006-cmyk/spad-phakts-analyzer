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
from scipy import stats

from modules.xlsform_dictionary import _xtype_key, GRILLE_XTYPE


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


# ─── Interopérabilité — détection automatique des indicateurs communs ────────
#
# Une colonne codifiée PHAKTS porte déjà, dans son nom, l'information de
# type (xType — voir modules/xlsform_dictionary.py, même grammaire que le
# dictionnaire PHAKTS v2025.10.22-ext2) : pas besoin du XLSForm d'origine
# pour savoir comment traiter statistiquement une variable alignée entre
# plusieurs enquêtes, le nom suffit. C'est ce qui rend l'alignement DPF/
# PHAKTS déjà en place ci-dessus réellement exploitable automatiquement,
# plutôt que de se limiter à un simple regroupement de colonnes.

def detect_common_indicators(surveys: dict, mode: str = 'phakts', min_surveys: int = 2) -> list:
    """Identifie les radicaux PHAKTS présents dans au moins `min_surveys`
    enquêtes, avec le xType détecté et le traitement statistique recommandé
    (même grille que modules/xlsform_dictionary.py). Une colonne non
    codifiée PHAKTS (pas de suffixe __TYPE reconnu) n'entre pas dans la
    détection automatique — elle reste accessible en mode manuel."""
    if mode != 'phakts':
        return []  # la détection de type suppose l'alignement par radical

    occurrences = {}  # radical -> {survey_name: (colonne_originale, suffixe)}
    for survey_name, df in surveys.items():
        for col in df.columns:
            radical = phakts_radical(col)
            suffix = phakts_type(col)
            if not suffix:
                continue
            occurrences.setdefault(radical, {})[survey_name] = (col, suffix)

    indicators = []
    for radical, per_survey in occurrences.items():
        if len(per_survey) < min_surveys:
            continue
        suffixes = [s for _, s in per_survey.values()]
        suffix = max(set(suffixes), key=suffixes.count)  # majoritaire si divergence rare entre enquêtes
        xkey = _xtype_key(suffix, is_multi=False)
        if xkey not in ('B', 'C', 'X_one', 'X_multi', 'period', 'I'):
            continue  # A/Z/E/G : hors analyse quantitative automatique (voir GRILLE_XTYPE)
        indicators.append({
            'radical': radical, 'suffix': suffix, 'xkey': xkey,
            'n_surveys': len(per_survey),
            'surveys': sorted(per_survey.keys()),
            'traitement': GRILLE_XTYPE.get(xkey, "À déterminer manuellement"),
        })
    indicators.sort(key=lambda i: (-i['n_surveys'], i['radical']))
    return indicators


def _categorical_cross_survey_test(merged: pd.DataFrame, radical: str):
    """Test d'association entre l'enquête d'origine et la variable
    (χ² d'indépendance) — l'indicateur diffère-t-il significativement
    d'une enquête à l'autre ?"""
    sub = merged[['__survey__', radical]].dropna()
    if sub.empty:
        return None
    ct = pd.crosstab(sub[radical], sub['__survey__'])
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return None
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    return {'test': 'χ² (indépendance)', 'stat': round(float(chi2), 2),
            'p_value': round(float(p), 4), 'dof': int(dof), 'n': int(ct.values.sum())}


def _continuous_cross_survey_test(merged: pd.DataFrame, radical: str):
    """Compare la moyenne/médiane de la variable entre enquêtes — ANOVA si
    la distribution est normale dans chaque enquête, Kruskal-Wallis sinon."""
    sub = merged[['__survey__', radical]].copy()
    sub[radical] = pd.to_numeric(sub[radical], errors='coerce')
    sub = sub.dropna()
    groups = [g[radical].values for _, g in sub.groupby('__survey__') if len(g) >= 3]
    if len(groups) < 2:
        return None
    normal = all(len(g) < 5000 and stats.shapiro(g)[1] >= 0.05 for g in groups)
    if normal:
        stat, p = stats.f_oneway(*groups)
        test = 'ANOVA'
    else:
        stat, p = stats.kruskal(*groups)
        test = 'Kruskal-Wallis'
    return {'test': test, 'stat': round(float(stat), 2), 'p_value': round(float(p), 4),
            'n': int(sum(len(g) for g in groups))}


def auto_analyze(surveys: dict, mode: str = 'phakts', min_surveys: int = 2) -> list:
    """Analyse automatique complète : détecte les indicateurs communs puis
    calcule, pour chacun, la comparaison descriptive (déjà fournie par
    compare_categorical_by_survey / compare_continuous_by_survey) ET un
    test statistique d'écart entre enquêtes — l'utilisateur n'a besoin de
    choisir aucune variable au préalable."""
    indicators = detect_common_indicators(surveys, mode=mode, min_surveys=min_surveys)
    if not indicators:
        return []
    merged = merge_surveys(surveys, mode=mode)

    out = []
    for ind in indicators:
        radical = ind['radical']
        if radical not in merged.columns:
            continue
        try:
            if ind['xkey'] in ('B', 'C', 'X_one', 'X_multi'):
                r = compare_categorical_by_survey(merged, radical)
                r['test'] = _categorical_cross_survey_test(merged, radical)
                r['kind'] = 'categorical'
            else:  # 'period', 'I'
                r = compare_continuous_by_survey(merged, radical)
                r['test'] = _continuous_cross_survey_test(merged, radical)
                r['kind'] = 'continuous'
        except Exception as e:
            r = {'variable': radical, 'error': str(e), 'kind': ind['xkey']}
        r.update({k: v for k, v in ind.items() if k not in r})
        out.append(r)
    return out
