"""
Analyse multi-enquête — fusion de plusieurs enquêtes en tenant compte de la
codification PHAKTS (DPF).

Principe : chaque colonne PHAKTS est de la forme
    Radical__Déterminant__Affixe!directive      (ex. Age__1Y!0<N<120)
La clé d'alignement est le code SANS sa directive (voir modules/phakts_codes.py) :
Age__1Y et Age__1Y!0<N<120 sont la même variable ; Age__1Y (années) et
Age__1M (mois) ne le sont pas, et le module le signale (multi_checks.py).
"""
import re
import os
import math
import pandas as pd
import numpy as np
import plotly.express as px
from scipy import stats

from modules.xlsform_dictionary import _xtype_key, GRILLE_XTYPE
from modules.phakts_codes import alignment_key, affix_of, is_coded


# ─── Extraction du code PHAKTS / clé d'alignement ────────────────────────────
def phakts_radical(col: str) -> str:
    """Clé d'alignement d'une colonne (nom historique : c'était le premier
    segment du code, qui confondait Allaitement__B et Allaitement__Duree__1W)."""
    if not col:
        return ''
    return alignment_key(str(col).strip(), keep_path=True)


def phakts_type(col: str) -> str:
    """Affixe PHAKTS (B, X, 1Y, …) ou ''."""
    return affix_of(col)


def is_phakts_coded(col: str) -> bool:
    return is_coded(col)


# Colonnes techniques jamais présentées comme variables : identifiant de soumission, identifiant du
# formulaire (_xform_id_string : une seule valeur, « aX28oe… »), géolocalisation brute, pièces jointes…
HIDDEN_COLUMNS = {'_uuid', '__survey__'}


def is_hidden_column(col) -> bool:
    c = str(col)
    return c in HIDDEN_COLUMNS or c.startswith('_') or c.startswith(('meta/', 'formhub/'))


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

    all_vars = sorted(v for v in set().union(*cols_by_survey.values()) if not is_hidden_column(v))
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
    return sorted(v for v in set.intersection(*sets) if not is_hidden_column(v)) if sets else []


# ─── Analyses sur le dataframe fusionné ──────────────────────────────────────
def _ordered(columns, order):
    """Enquêtes dans l'ordre demandé (date du Factum), les autres à la suite."""
    order = [n for n in (order or []) if n in set(columns)]
    return order + [c for c in columns if c not in order]


# ─── Graphique d'une variable catégorielle ───────────────────────────────────
CHART_MAX_MODALITES = 12       # au-delà, les plus fréquentes sont tracées et le reste est regroupé
CHART_HORIZONTAL_FROM = 7      # à partir de 7 modalités (ou de libellés longs), barres horizontales
CHART_LONG_LABEL = 22
CHART_LABEL_MAX = 42


def _short(label, n=CHART_LABEL_MAX):
    label = str(label)
    return label if len(label) <= n else label[:n - 1] + '…'


def _categorical_chart(ct: pd.DataFrame, pct: pd.DataFrame, variable: str):
    """Barres groupées par enquête. Une variable à 120 modalités aux noms longs (établissements)
    donnait des étiquettes verticales qui prenaient toute la place et effaçaient le graphique :
    on trace au plus 12 modalités (les plus fréquentes, la part du reste étant indiquée dans le titre), en
    barres horizontales dès que les libellés sont nombreux ou longs. Les tableaux, eux, restent complets."""
    surveys = list(ct.columns)
    n_mod = len(ct)
    note = ''
    plot = pct
    if n_mod > CHART_MAX_MODALITES:
        ranked = ct.sum(axis=1).sort_values(ascending=False).index[:CHART_MAX_MODALITES]
        plot = pct.loc[list(ranked)].copy()
        # Le reste n'est pas tracé : sa barre (souvent > 70 %) écraserait les autres. Sa part est dans le titre.
        rest = (100 - plot.sum(axis=0)).clip(lower=0).round(1)
        note = (f'{CHART_MAX_MODALITES} modalités les plus fréquentes sur {n_mod} ; les {n_mod - CHART_MAX_MODALITES} autres : '
                + ' · '.join(f'{v:.1f} %' for v in rest) + ' (voir les tableaux)')
    horizontal = len(plot) >= CHART_HORIZONTAL_FROM or any(len(str(i)) > CHART_LONG_LABEL for i in plot.index)

    long = plot.copy()
    long.index.name = 'Modalité'
    long = long.reset_index().melt(id_vars='Modalité', var_name='Enquête', value_name='%')
    shorts = {m: _short(m) for m in plot.index}
    if len(set(shorts.values())) < len(shorts):           # deux libellés tronqués identiques : on garde les complets
        shorts = {m: str(m) for m in plot.index}
    long['Affiché'] = long['Modalité'].map(shorts)
    labels = list(dict.fromkeys(shorts[m] for m in plot.index))
    common = dict(color='Enquête', barmode='group', hover_name='Modalité', hover_data={'Affiché': False},
                  category_orders={'Enquête': surveys, 'Affiché': labels},
                  title=f'Comparaison de {variable} entre enquêtes' + (f'<br><sup>{note}</sup>' if note else ''),
                  color_discrete_sequence=px.colors.qualitative.Set2, text_auto='.1f')
    if horizontal:
        fig = px.bar(long, y='Affiché', x='%', orientation='h', **common)
        fig.update_yaxes(autorange='reversed', automargin=True, title=None)
        height = int(min(1000, max(420, 130 + len(plot) * (14 + 16 * len(surveys)))))
    else:
        fig = px.bar(long, x='Affiché', y='%', **common)
        fig.update_xaxes(automargin=True, title=None)
        height = 420
    fig.update_layout(height=height, plot_bgcolor='white', paper_bgcolor='white',
                      font=dict(family='Inter, sans-serif'), margin=dict(t=90 if note else 60))
    return fig


def compare_categorical_by_survey(merged: pd.DataFrame, variable: str, order=None) -> dict:
    """
    Compare la distribution d'une variable catégorielle entre enquêtes.
    """
    if variable not in merged.columns:
        raise ValueError(f"Variable {variable!r} absente du jeu fusionné.")
    sub = merged[['__survey__', variable]].dropna()
    if sub.empty:
        raise ValueError("Aucune observation disponible.")
    ct = pd.crosstab(sub[variable], sub['__survey__'])
    ct = ct[_ordered(list(ct.columns), order)]
    pct = ct.div(ct.sum(axis=0), axis=1).mul(100).round(1)
    ct.columns.name = pct.columns.name = 'Enquête'
    fig = _categorical_chart(ct, pct, variable)
    stats_by_survey = []
    for name in ct.columns:
        col = ct[name]
        top = col.idxmax()
        stats_by_survey.append({'name': name, 'n': int(col.sum()), 'top': str(top), 'top_pct': float(pct.loc[top, name])})

    return {
        'variable': variable,
        'count_html': ct.to_html(classes='table table-sm table-bordered text-center',
                                  border=0, na_rep='—'),
        'pct_html': pct.to_html(classes='table table-sm table-bordered text-center',
                                 border=0, na_rep='—',
                                 float_format=lambda x: f'{x:.1f}'),
        'chart': fig.to_json(),
        'n_total': int(ct.values.sum()),
        'stats': {'surveys': stats_by_survey, 'n_modalites': int(len(ct))},
    }


def compare_continuous_by_survey(merged: pd.DataFrame, variable: str, order=None) -> dict:
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
    summary = summary.loc[_ordered(list(summary.index), order)]
    summary.index.name = 'Enquête'

    fig = px.box(sub, x='__survey__', y=variable,
                 title=f'Distribution de {variable} par enquête',
                 labels={'__survey__': 'Enquête'},
                 category_orders={'__survey__': list(summary.index)},
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
        'stats': {'surveys': [{'name': name, 'n': int(row['Effectif']), 'mean': float(row['Moyenne']),
                               'median': float(row['Médiane']),
                               'std': None if pd.isna(row['Écart-type']) else float(row['Écart-type'])}
                              for name, row in summary.iterrows()]},
    }


# ─── Évolution entre enquêtes consécutives (ordre chronologique du Factum) ───
_Z95 = 1.959964


def _wilson(k, n, z=_Z95):
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def diff_proportions(k1, n1, k2, n2):
    """Écart de proportion p2 − p1, avec son IC à 95 % (méthode de Newcombe,
    fondée sur les IC de Wilson : fiable même pour des effectifs faibles ou
    des proportions proches de 0 et de 1) et le p d'un test z."""
    p1, p2 = k1 / n1, k2 / n2
    d = p2 - p1
    l1, u1 = _wilson(k1, n1)
    l2, u2 = _wilson(k2, n2)
    lo = d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    hi = d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    p = 1.0 if se == 0 else float(2 * stats.norm.sf(abs(d) / se))
    return d, lo, hi, p


def evolution_categorical(merged: pd.DataFrame, variable: str, order, top: int = 6) -> list:
    """Pour chaque couple d'enquêtes consécutives et chaque modalité (les `top`
    plus fréquentes) : proportions, écart en points de % et IC à 95 %."""
    sub = merged[['__survey__', variable]].dropna()
    present = [n for n in (order or []) if n in set(sub['__survey__'])]
    if len(present) < 2:
        return []
    ct = pd.crosstab(sub[variable], sub['__survey__'])
    totals = ct.sum()
    modalites = ct.sum(axis=1).sort_values(ascending=False).head(top).index
    rows = []
    for a, b in zip(present[:-1], present[1:]):
        n1, n2 = int(totals[a]), int(totals[b])
        if n1 < 2 or n2 < 2:
            continue
        for m in modalites:
            k1, k2 = int(ct.loc[m, a]), int(ct.loc[m, b])
            d, lo, hi, p = diff_proportions(k1, n1, k2, n2)
            rows.append({'de': a, 'vers': b, 'modalite': str(m),
                         'v1': round(100 * k1 / n1, 1), 'v2': round(100 * k2 / n2, 1),
                         'n1': n1, 'n2': n2, 'diff': round(100 * d, 1),
                         'ic_bas': round(100 * lo, 1), 'ic_haut': round(100 * hi, 1),
                         'p_value': round(p, 4), 'significatif': lo > 0 or hi < 0, 'unite': 'points de %'})
    return rows


def evolution_continuous(merged: pd.DataFrame, variable: str, order) -> list:
    """Écart de moyenne entre enquêtes consécutives (Welch) avec IC à 95 %."""
    sub = merged[['__survey__', variable]].copy()
    sub[variable] = pd.to_numeric(sub[variable], errors='coerce')
    sub = sub.dropna()
    present = [n for n in (order or []) if n in set(sub['__survey__'])]
    rows = []
    for a, b in zip(present[:-1], present[1:]):
        x, y = sub[sub['__survey__'] == a][variable].values, sub[sub['__survey__'] == b][variable].values
        if len(x) < 2 or len(y) < 2:
            continue
        v1, v2 = x.var(ddof=1) / len(x), y.var(ddof=1) / len(y)
        d = float(y.mean() - x.mean())
        if v1 + v2 == 0:
            lo = hi = d
            p = 1.0 if d == 0 else 0.0
        else:
            se = math.sqrt(v1 + v2)
            df = (v1 + v2) ** 2 / ((v1 ** 2) / (len(x) - 1) + (v2 ** 2) / (len(y) - 1))
            tcrit = float(stats.t.ppf(0.975, df))
            lo, hi = d - tcrit * se, d + tcrit * se
            p = float(2 * stats.t.sf(abs(d) / se, df))
        rows.append({'de': a, 'vers': b, 'modalite': 'Moyenne', 'v1': round(float(x.mean()), 2),
                     'v2': round(float(y.mean()), 2), 'n1': len(x), 'n2': len(y), 'diff': round(d, 2),
                     'ic_bas': round(lo, 2), 'ic_haut': round(hi, 2), 'p_value': round(p, 4),
                     'significatif': lo > 0 or hi < 0, 'unite': 'unités de la variable'})
    return rows


def benjamini_hochberg(pvalues):
    """Valeurs q (taux de fausses découvertes) pour une liste de p ; None est
    conservé. Avec 40 indicateurs testés à 5 %, environ 2 paraissent
    « significatifs » par pur hasard : on juge donc sur q, pas sur p."""
    idx = [i for i, p in enumerate(pvalues) if p is not None]
    m = len(idx)
    q = [None] * len(pvalues)
    running = 1.0
    ranked = sorted(idx, key=lambda i: pvalues[i])
    for rank in range(m, 0, -1):
        i = ranked[rank - 1]
        running = min(running, pvalues[i] * m / rank)
        q[i] = round(float(running), 4)
    return q


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
    chi2, p, dof, expected = stats.chi2_contingency(ct)
    n = int(ct.values.sum())
    v = math.sqrt(chi2 / (n * (min(ct.shape) - 1))) if n else 0.0
    return {'test': 'χ² (indépendance)', 'stat': round(float(chi2), 2),
            'p_value': round(float(p), 4), 'dof': int(dof), 'n': n,
            'cramers_v': round(float(v), 3),                              # intensité de l'écart, indépendante de l'effectif
            'low_expected_pct': round(100 * float((expected < 5).mean()), 1)}  # % de cases à effectif théorique < 5


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


def cross_survey_test(merged: pd.DataFrame, variable: str, kind: str):
    """Test d'écart entre enquêtes pour une variable : 'categorical' (χ²) ou 'continuous'
    (ANOVA / Kruskal-Wallis). None si les données ne le permettent pas."""
    try:
        if kind == 'categorical':
            return _categorical_cross_survey_test(merged, variable)
        return _continuous_cross_survey_test(merged, variable)
    except Exception:
        return None


def apply_fdr(results: list) -> list:
    """Correction des tests multiples (Benjamini-Hochberg, FDR 5 %) sur l'ensemble des
    comparaisons d'une liste : ajoute q_value et significant_fdr à chaque test."""
    pvalues = [r['test']['p_value'] if r.get('test') else None for r in results]
    for r, q in zip(results, benjamini_hochberg(pvalues)):
        if r.get('test'):
            r['test']['q_value'] = q
            r['test']['significant_fdr'] = q < 0.05
    return results


def auto_analyze(surveys: dict, mode: str = 'phakts', min_surveys: int = 2, order=None) -> list:
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
                r = compare_categorical_by_survey(merged, radical, order)
                r['test'] = _categorical_cross_survey_test(merged, radical)
                r['evolution'] = evolution_categorical(merged, radical, order)
                r['kind'] = 'categorical'
            else:  # 'period', 'I'
                r = compare_continuous_by_survey(merged, radical, order)
                r['test'] = _continuous_cross_survey_test(merged, radical)
                r['evolution'] = evolution_continuous(merged, radical, order)
                r['kind'] = 'continuous'
        except Exception as e:
            r = {'variable': radical, 'error': str(e), 'kind': ind['xkey']}
        r.update({k: v for k, v in ind.items() if k not in r})
        out.append(r)

    # Correction des tests multiples (Benjamini-Hochberg, FDR 5 %) sur
    # l'ensemble des indicateurs testés.
    return apply_fdr(out)
