"""
SPAD Analyzer — Analyse croisée

  tableau_croise_dynamique : tableau croisé façon Excel (lignes, colonnes, agrégation, pourcentages, filtres)
                             avec, pour un croisement de deux variables, le test d'association complet ;
  tableau_croise           : le même croisement, présentation du rapport ;
  croisement_choix_multiples : une question à choix multiples (une colonne 0/1 par choix) croisée avec une variable ;
  stratifier               : le croisement de deux variables refait dans chaque strate d'une 3ᵉ variable.

Le test d'association (`association`) donne : χ² de Pearson, p, V de Cramér, effectifs théoriques trop faibles
(part des cases < 5), test exact de Fisher et odds ratio pour un tableau 2 × 2, résidus standardisés AJUSTÉS (au-delà de
±1,96 une case s'écarte de l'indépendance) et les cases qui s'en écartent le plus.
"""
import numpy as np
import pandas as pd
import plotly.express as px
from scipy import stats

MIN_EXPECTED = 5
Z_95 = 1.96
MAX_HEATMAP_CELLS = 600           # au-delà, ni carte de chaleur ni barres : illisibles
MAX_TOP_CELLS = 5

_AGG_FUNCS = {
    'count':  ('Effectifs',     'size'),
    'sum':    ('Somme',         'sum'),
    'mean':   ('Moyenne',       'mean'),
    'median': ('Médiane',       'median'),
    'min':    ('Minimum',       'min'),
    'max':    ('Maximum',       'max'),
    'std':    ('Écart-type',    'std'),
    'nunique': ('Modalités uniques', 'nunique'),
}
_ADDITIVE = ('count', 'sum')      # seuls agrégats dont les pourcentages ont un sens


def _fr(x, nd=1):
    return '—' if x is None or (isinstance(x, float) and np.isnan(x)) else f'{x:.{nd}f}'.replace('.', ',')


def significance_label(p):
    if p < 0.001:
        return 'très hautement significative (p < 0,001)'
    if p < 0.01:
        return 'hautement significative (p < 0,01)'
    if p < 0.05:
        return 'significative (p < 0,05)'
    return 'non significative (p ≥ 0,05)'


def association_label(v):
    return 'très faible' if v < 0.1 else 'faible' if v < 0.3 else 'modérée' if v < 0.5 else 'forte'


# ─── Test d'association ──────────────────────────────────────────────────────

def association(ct: pd.DataFrame) -> dict:
    """Test d'association d'un tableau de contingence (effectifs). Renvoie None s'il n'a pas au moins 2 × 2
    modalités observées."""
    ct = ct.loc[ct.sum(axis=1) > 0, ct.sum(axis=0) > 0]
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return None
    obs = ct.values.astype(float)
    n = obs.sum()
    chi2, p, dof, expected = stats.chi2_contingency(obs, correction=False)
    cramer = float(np.sqrt(chi2 / (n * (min(obs.shape) - 1)))) if n else 0.0
    low = float((expected < MIN_EXPECTED).mean() * 100)
    rows, cols = obs.sum(axis=1), obs.sum(axis=0)
    adj = (obs - expected) / np.sqrt(expected * np.outer(1 - rows / n, 1 - cols / n))
    out = {
        'table': ct, 'n': int(n), 'chi2': round(float(chi2), 3), 'p_val': round(float(p), 4), 'dof': int(dof),
        'cramers_v': round(cramer, 3), 'sig_label': significance_label(p), 'assoc_label': association_label(cramer),
        'low_expected_pct': round(low, 1), 'min_expected': round(float(expected.min()), 2),
        'expected': pd.DataFrame(expected, index=ct.index, columns=ct.columns),
        'residuals': pd.DataFrame(adj, index=ct.index, columns=ct.columns),
        'fisher_p': None, 'odds_ratio': None, 'or_ci': None, 'warning': '',
    }
    if obs.shape == (2, 2):
        a, b, c, d = obs.ravel()
        out['fisher_p'] = round(float(stats.fisher_exact(obs)[1]), 4)
        if min(a, b, c, d) > 0:
            orr = a * d / (b * c)
            se = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
            out['odds_ratio'] = round(float(orr), 2)
            out['or_ci'] = (round(float(np.exp(np.log(orr) - Z_95 * se)), 2), round(float(np.exp(np.log(orr) + Z_95 * se)), 2))
    if low > 20 or expected.min() < 1:
        out['warning'] = (f"{_fr(low, 0)} % des cases ont un effectif théorique inférieur à {MIN_EXPECTED} : le χ² est peu fiable. "
                          + ("Se reporter au test exact de Fisher (tableau 2 × 2)." if obs.shape == (2, 2)
                             else "Regrouper des modalités rares ou s'appuyer sur la lecture descriptive."))
    out['top_cells'] = _top_cells(ct, out['expected'], out['residuals'], int(n))
    return out


def _top_cells(ct, expected, residuals, n):
    """Cases qui s'écartent le plus de l'indépendance (|résidu ajusté| > 1,96)."""
    rows_tot, cols_tot = ct.sum(axis=1), ct.sum(axis=0)
    cells = []
    for i in ct.index:
        for j in ct.columns:
            r = float(residuals.loc[i, j])
            if abs(r) > Z_95 and expected.loc[i, j] >= 1:
                cells.append({'row': str(i), 'col': str(j), 'n': int(ct.loc[i, j]), 'expected': round(float(expected.loc[i, j]), 1),
                              'residual': round(r, 2), 'row_share': round(100 * ct.loc[i, j] / rows_tot[i], 1),
                              'overall_share': round(100 * cols_tot[j] / n, 1), 'row_total': int(rows_tot[i])})
    cells.sort(key=lambda c: -abs(c['residual']))
    return cells[:MAX_TOP_CELLS]


def _residual_table(residuals: pd.DataFrame) -> str:
    def color(val):
        return ('background-color:#d4edda' if val > Z_95 else 'background-color:#f8d7da' if val < -Z_95 else '')
    return (residuals.round(2).style.map(color).format('{:.2f}')
            .set_table_attributes('class="table table-sm table-bordered text-center"').to_html())


# ─── Tableau croisé dynamique ────────────────────────────────────────────────

def _pivot(sub, rows, cols, value_var, agg, margins):
    label, func = _AGG_FUNCS[agg]
    if agg == 'count' or not value_var:
        data, values, aggfunc, fill = sub.assign(__n__=1), '__n__', 'sum', 0
    else:
        data, values, aggfunc = sub, value_var, func
        fill = 0 if agg in ('sum', 'nunique') else None          # une moyenne absente n'est pas 0 : la case reste vide
    pt = pd.pivot_table(data, index=rows, columns=cols or None, values=values, aggfunc=aggfunc, fill_value=fill,
                        margins=margins, margins_name='Total')
    if isinstance(pt, pd.Series):
        pt = pt.to_frame(name=label)
    if not cols:
        pt.columns = [label]
    return pt


def _percentages(pm: pd.DataFrame, pct_type: str):
    """Pourcentages calculés sur le tableau AVEC marges : la dernière ligne et la dernière colonne sont les totaux
    (la ligne « Total » donne la répartition des colonnes, la colonne « Total » vaut 100 % en pourcentage de ligne)."""
    has_total_col = pm.shape[1] > 1
    if pct_type == 'row':
        base = pm.iloc[:, -1] if has_total_col else pm.iloc[-1, 0]
        out = pm.div(base, axis=0) if has_total_col else pm / base
        label = '% ligne'
    elif pct_type == 'col':
        out, label = pm.div(pm.iloc[-1, :], axis=1), '% colonne'
    else:
        out, label = pm / pm.iloc[-1, -1], '% total'
    return out.mul(100).round(1), label


def _style(df, na_rep='—', decimals=None):
    fmt = (lambda x: f'{x:.{decimals}f}') if decimals is not None else (lambda x: f'{x:.1f}' if isinstance(x, float) and x != int(x) else (f'{int(x)}' if isinstance(x, float) else x))
    return df.to_html(classes='table table-sm table-bordered text-center', border=0, na_rep=na_rep, float_format=fmt)


def _unique_names(mapping):
    """Noms d'affichage distincts : deux variables de même libellé ne doivent pas se confondre."""
    seen, out = {}, {}
    for col, name in mapping.items():
        name = str(name)
        seen[name] = seen.get(name, 0) + 1
        out[col] = name if seen[name] == 1 else f'{name} ({seen[name]})'
    return out


def tableau_croise_dynamique(df: pd.DataFrame, rows: list, cols: list, value_var: str = None, agg: str = 'count',
                              pct_type: str = 'none', filters: dict = None, layer: str = None, names: dict = None) -> dict:
    """
    Tableau croisé dynamique (style tableau croisé dynamique Excel).

    rows / cols : variables en ligne (≥ 1, hiérarchie de niveaux) et en colonne (peut être vide) ;
    value_var   : variable de valeur (None → comptage des observations) ; agg : count | sum | mean | median | min | max |
    std | nunique ; pct_type : none | row | col | total (comptages et sommes seulement) ;
    filters     : { var: [valeur autorisée, …] } appliqués avant le calcul ;
    layer       : 3ᵉ variable de stratification (croisement de deux variables en comptage) ;
    names       : {colonne: nom affiché} — libellé de la question ; les tableaux et graphiques portent ces noms, le résultat
                  garde les noms de colonnes d'origine (`rows`, `cols`).
    """
    rows = [r for r in (rows or []) if r in df.columns]
    cols = [c for c in (cols or []) if c in df.columns]
    if not rows:
        raise ValueError("Sélectionnez au moins une variable en LIGNE.")
    if agg not in _AGG_FUNCS:
        agg = 'count'
    agg_label = _AGG_FUNCS[agg][0]
    if agg != 'count' and not value_var:
        raise ValueError(f"L'agrégation « {agg_label} » demande une variable de valeur numérique.")

    sub = df.copy()
    for var, allowed in (filters or {}).items():
        if var in sub.columns and allowed:
            sub = sub[sub[var].astype(str).isin([str(a) for a in allowed])]
    keep = list(dict.fromkeys(rows + cols + ([value_var] if value_var and agg != 'count' else []) + ([layer] if layer and layer in df.columns else [])))
    sub = sub[keep].dropna(subset=rows + cols)
    if value_var and agg != 'count' and agg != 'nunique':
        sub[value_var] = pd.to_numeric(sub[value_var], errors='coerce')
        sub = sub.dropna(subset=[value_var])
    if sub.empty:
        raise ValueError("Aucune observation ne reste après application des filtres.")

    ren = _unique_names({c: (names or {}).get(c, c) for c in sub.columns})
    sub = sub.rename(columns=ren)
    rows_o, cols_o, layer_o, value_o = rows, cols, layer, value_var                  # noms d'origine, rendus tels quels
    rows, cols = [ren[r] for r in rows_o], [ren[c] for c in cols_o]
    value_var = ren.get(value_o) if value_o else None
    layer = ren.get(layer_o) if layer_o else None
    pivot = _pivot(sub, rows, cols, value_var, agg, margins=False)
    pivot_m = _pivot(sub, rows, cols, value_var, agg, margins=True)
    if pivot.size == 0:
        raise ValueError("Le tableau croisé produit est vide.")

    pct = pct_label = pct_note = None
    pct_html = None
    if pct_type and pct_type != 'none':
        if agg in _ADDITIVE:
            pct, pct_label = _percentages(pivot_m, pct_type)
            pct_html = _style(pct, decimals=1)
        else:
            pct_note = f"Les pourcentages n'ont de sens que pour un nombre ou une somme (agrégation choisie : {agg_label.lower()})."

    assoc = None
    if agg == 'count' and len(rows) == 1 and len(cols) == 1:
        assoc = association(pivot)

    chart_heat = chart_bar = None
    if len(rows) == 1 and len(cols) <= 1 and pivot.size <= MAX_HEATMAP_CELLS:
        data_for_chart = (pct.iloc[:-1, :-1] if (pct is not None and pct.shape[1] > 1) else pct.iloc[:-1] if pct is not None else pivot)
        title = f'Tableau croisé dynamique — {agg_label}' + (f' ({pct_label})' if pct_label else '')
        try:
            fig_heat = px.imshow(data_for_chart.astype(float), text_auto=True, color_continuous_scale='Blues', title=title, aspect='auto')
            fig_heat.update_layout(height=max(300, 60 * len(data_for_chart.index) + 100), font=dict(family='Inter, sans-serif'),
                                   margin=dict(t=60, b=60))
            chart_heat = fig_heat.to_json()
            melt = data_for_chart.astype(float).reset_index().melt(id_vars=rows, var_name='__col', value_name='Valeur')
            fig_bar = px.bar(melt, x=rows[0], y='Valeur', color='__col', barmode='group', title=title.replace('dynamique — ', ''),
                             color_discrete_sequence=px.colors.qualitative.Set2, text_auto='.1f')
            fig_bar.update_layout(height=380, plot_bgcolor='white', paper_bgcolor='white', font=dict(family='Inter, sans-serif'),
                                  legend_title_text='')
            fig_bar.update_yaxes(gridcolor='#f0f0f0')
            chart_bar = fig_bar.to_json()
        except Exception:
            chart_heat = chart_bar = None

    strata = None
    if layer and layer in sub.columns and layer not in rows + cols and agg == 'count' and len(rows) == 1 and len(cols) == 1:
        strata = stratifier(sub, rows[0], cols[0], layer)

    result = {
        'rows': rows_o, 'cols': cols_o, 'rows_display': rows, 'cols_display': cols, 'value_var': value_o, 'value_display': value_var,
        'agg': agg, 'agg_label': agg_label, 'pct_type': pct_type,
        'pct_label': pct_label or '', 'pct_note': pct_note, 'layer': layer_o if strata else None,
        'n': int(pivot_m.iloc[-1, -1]) if agg == 'count' else int(len(sub)),
        'pivot_html': _style(pivot_m, decimals=None if agg in ('count', 'sum', 'nunique') else 2),
        'pct_html': pct_html, 'chart_heat': chart_heat, 'chart_bar': chart_bar, 'strata': strata,
        'frames': {'Tableau': pivot_m, **({'Pourcentages': pct} if pct is not None else {})},
        'chi2': None, 'p_val': None, 'dof': None, 'cramers_v': None, 'sig_label': '', 'assoc_label': '',
        'low_expected_pct': None, 'warning': '', 'fisher_p': None, 'odds_ratio': None, 'or_ci': None, 'top_cells': [],
        'residuals_html': None,
    }
    if assoc:
        result.update({k: assoc[k] for k in ('chi2', 'p_val', 'dof', 'cramers_v', 'sig_label', 'assoc_label', 'low_expected_pct',
                                              'warning', 'fisher_p', 'odds_ratio', 'or_ci', 'top_cells', 'min_expected')})
        result['residuals_html'] = _residual_table(assoc['residuals'])
        result['frames']['Résidus ajustés'] = assoc['residuals'].round(2)
        result['frames']['Effectifs théoriques'] = assoc['expected'].round(1)
    return result


# ─── Stratification par une 3ᵉ variable ──────────────────────────────────────

def _mantel_haenszel(tables):
    """Odds ratio commun de Mantel-Haenszel (2 × 2 × K) : (estimation, IC 95 %, p du test CMH) ou None."""
    num = den = 0.0
    P = Q = R = 0.0
    sum_a = sum_e = sum_v = 0.0
    for t in tables:
        a, b, c, d = t.ravel().astype(float)
        n = a + b + c + d
        if n < 2:
            continue
        r_, s_ = a * d / n, b * c / n
        num += r_
        den += s_
        p_, q_ = (a + d) / n, (b + c) / n
        P += p_ * r_
        Q += p_ * s_ + q_ * r_
        R += q_ * s_
        sum_a += a
        sum_e += (a + b) * (a + c) / n
        sum_v += (a + b) * (c + d) * (a + c) * (b + d) / (n ** 2 * (n - 1))
    if den == 0 or num == 0 or sum_v == 0:
        return None
    orr = num / den
    var_log = P / (2 * num ** 2) + Q / (2 * num * den) + R / (2 * den ** 2)
    se = float(np.sqrt(var_log))
    chi = (abs(sum_a - sum_e) - 0.5) ** 2 / sum_v
    return (round(float(orr), 2), (round(float(np.exp(np.log(orr) - Z_95 * se)), 2), round(float(np.exp(np.log(orr) + Z_95 * se)), 2)),
            round(float(stats.chi2.sf(chi, 1)), 4))


def stratifier(df: pd.DataFrame, row_var: str, col_var: str, layer: str, max_strata: int = 12) -> dict:
    """Le croisement row × col refait dans chaque strate de `layer`, comparé au croisement brut. Pour des tableaux
    2 × 2 dans toutes les strates : odds ratio commun de Mantel-Haenszel — un écart avec l'odds ratio brut trahit
    un facteur de confusion."""
    sub = df[[row_var, col_var, layer]].dropna()
    levels = sub[layer].astype(str).value_counts()
    if len(levels) < 2:
        return None
    levels = levels.head(max_strata)
    crude = association(pd.crosstab(sub[row_var], sub[col_var]))
    blocks, tables = [], []
    for level in levels.index:
        part = sub[sub[layer].astype(str) == level]
        ct = pd.crosstab(part[row_var], part[col_var])
        a = association(ct)
        pct = ct.div(ct.sum(axis=1), axis=0).mul(100).round(1)
        blocks.append({'level': level, 'n': int(len(part)), 'counts_html': _style(ct), 'pct_html': _style(pct, decimals=1),
                       'chi2': a['chi2'] if a else None, 'p_val': a['p_val'] if a else None,
                       'cramers_v': a['cramers_v'] if a else None, 'odds_ratio': a['odds_ratio'] if a else None,
                       'warning': a['warning'] if a else 'Une seule modalité observée dans cette strate.'})
        if a and a['table'].shape == (2, 2):
            tables.append(a['table'].values)
    full_2x2 = len(tables) == len(levels) and len(tables) >= 2
    mh = _mantel_haenszel(tables) if full_2x2 else None
    return {'layer': layer, 'levels': blocks, 'n_levels_total': int(sub[layer].nunique()), 'shown': len(levels),
            'crude_v': crude['cramers_v'] if crude else None, 'crude_p': crude['p_val'] if crude else None,
            'crude_or': crude['odds_ratio'] if crude else None, 'mh': mh,
            'confounding': bool(mh and crude and crude['odds_ratio'] and abs(mh[0] - crude['odds_ratio']) / crude['odds_ratio'] > 0.2)}


# ─── Question à choix multiples × variable ───────────────────────────────────

def benjamini_hochberg(pvalues):
    p = np.array([1.0 if v is None else v for v in pvalues], dtype=float)
    n = len(p)
    if n == 0:
        return []
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return [round(float(x), 4) for x in out]


def _wilson(k, n):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + Z_95 ** 2 / n
    c = (p + Z_95 ** 2 / (2 * n)) / d
    m = Z_95 * np.sqrt(p * (1 - p) / n + Z_95 ** 2 / (4 * n ** 2)) / d
    return max(0.0, c - m) * 100, min(1.0, c + m) * 100


def croisement_choix_multiples(df: pd.DataFrame, option_cols: list, var: str, group_label: str = '', var_name: str = None) -> dict:
    """Question à choix multiples (une colonne 0/1 par choix) × variable catégorielle. Pour chaque choix : part des
    répondants de chaque catégorie qui le citent, test d'association (χ², ou Fisher en 2 × 2 de petits effectifs),
    corrigé des tests multiples entre choix (Benjamini-Hochberg)."""
    option_cols = [c for c in option_cols if c in df.columns]
    if not option_cols or var not in df.columns:
        raise ValueError("Choisissez une question à choix multiples et une variable de croisement.")
    flags = df[option_cols].apply(pd.to_numeric, errors='coerce')
    answered = flags.notna().any(axis=1)
    base = df.loc[answered & df[var].notna(), [var]].copy()
    base[var] = base[var].astype(str)
    flags = flags.loc[base.index].fillna(0)
    cats = base[var].value_counts()
    cats = cats[cats > 0]
    if len(cats) < 2:
        raise ValueError(f"« {var} » n'a qu'une modalité parmi les répondants de cette question : rien à croiser.")
    n_by_cat = cats
    n_total = int(len(base))
    rows, table_pct, table_n = [], {}, {}
    for col in option_cols:
        label = str(col).rsplit('/', 1)[-1]
        sel = flags[col] == 1
        counts = base.loc[sel, var].value_counts().reindex(cats.index).fillna(0).astype(int)
        ct = pd.DataFrame({'cité': counts, 'non cité': n_by_cat - counts}).T
        a = association(ct)
        total_cited = int(sel.sum())
        lo, hi = _wilson(total_cited, n_total)
        p = None
        if a:
            p = a['fisher_p'] if (ct.shape == (2, 2) and a['low_expected_pct'] > 20 and a['fisher_p'] is not None) else a['p_val']
        rows.append({'option': label, 'n_cited': total_cited, 'pct_all': round(100 * total_cited / n_total, 1),
                     'ci': (round(lo, 1), round(hi, 1)), 'p_val': p, 'cramers_v': a['cramers_v'] if a else None,
                     'warning': bool(a and a['warning'])})
        table_n[label] = counts
        table_pct[label] = (counts / n_by_cat * 100).round(1)
    qs = benjamini_hochberg([r['p_val'] for r in rows])
    for r, q in zip(rows, qs):
        r['q_val'] = q if r['p_val'] is not None else None
        r['significant'] = bool(r['q_val'] is not None and r['q_val'] < 0.05)
    pct_df = pd.DataFrame(table_pct).T
    pct_df['Ensemble'] = [r['pct_all'] for r in rows]
    n_df = pd.DataFrame(table_n).T
    n_df['Ensemble'] = [r['n_cited'] for r in rows]
    pct_df.index.name = n_df.index.name = 'Choix'
    shown_var = var_name or str(var).rsplit('/', 1)[-1]
    pct_df.columns.name = n_df.columns.name = shown_var
    summary = pd.DataFrame({'Choix': [r['option'] for r in rows], 'Cité par (n)': [r['n_cited'] for r in rows],
                            '% des répondants': [r['pct_all'] for r in rows],
                            'IC 95 % bas': [r['ci'][0] for r in rows], 'IC 95 % haut': [r['ci'][1] for r in rows],
                            'V de Cramér': [r['cramers_v'] for r in rows], 'p': [r['p_val'] for r in rows],
                            'q (corrigé)': [r['q_val'] for r in rows],
                            'Écart net': ['oui' if r['significant'] else '' for r in rows]})
    heat = px.imshow(pct_df.drop(columns='Ensemble').astype(float), text_auto='.0f', color_continuous_scale='Blues', aspect='auto',
                     labels=dict(color='% citant'), title=f'Part des répondants citant chaque choix, selon « {shown_var} »')
    heat.update_layout(height=max(320, 42 * len(rows) + 140), font=dict(family='Inter, sans-serif'), margin=dict(t=60, b=40))
    return {
        'group': group_label, 'var': var, 'n_respondents': n_total, 'n_options': len(rows), 'categories': [str(c) for c in cats.index],
        'category_sizes': {str(k): int(v) for k, v in cats.items()}, 'rows': rows,
        'n_significant': sum(1 for r in rows if r['significant']),
        'pct_html': _style(pct_df, decimals=1), 'n_html': _style(n_df), 'summary_html': _style(summary, decimals=3),
        'chart_heat': heat.to_json(), 'frames': {'% citant': pct_df.reset_index(), 'Effectifs': n_df.reset_index(), 'Tests': summary},
    }


# ─── Présentation du rapport ─────────────────────────────────────────────────

def tableau_croise(df: pd.DataFrame, row_var: str, col_var: str, pct_type: str = 'row') -> dict:
    """Croisement de deux variables (effectifs, pourcentages, résidus, test) : présentation du rapport."""
    sub = df[[row_var, col_var]].dropna()
    ct = pd.crosstab(sub[row_var], sub[col_var])
    a = association(ct)
    if a is None:
        raise ValueError("Le croisement demande deux variables ayant chacune au moins 2 modalités observées.")
    if pct_type == 'row':
        pct, pct_label = ct.div(ct.sum(axis=1), axis=0).mul(100).round(1), '% ligne'
    elif pct_type == 'col':
        pct, pct_label = ct.div(ct.sum(axis=0), axis=1).mul(100).round(1), '% colonne'
    else:
        pct, pct_label = ct.div(ct.values.sum()).mul(100).round(1), '% total'
    fig_heat = px.imshow(pct, text_auto=True, color_continuous_scale='Blues', title=f'Tableau croisé : {row_var} × {col_var} ({pct_label})',
                         labels=dict(x=col_var, y=row_var, color=pct_label), aspect='auto')
    fig_heat.update_layout(height=max(300, 60 * len(ct.index) + 100), font=dict(family='Inter, sans-serif'), margin=dict(t=60, b=60))
    melt = pct.reset_index().melt(id_vars=row_var, var_name=col_var, value_name='Pourcentage')
    fig_bar = px.bar(melt, x=row_var, y='Pourcentage', color=col_var, barmode='group', title=f'Comparaison des profils ({pct_label})',
                     color_discrete_sequence=px.colors.qualitative.Set2, text_auto='.1f')
    fig_bar.update_layout(height=380, plot_bgcolor='white', paper_bgcolor='white', font=dict(family='Inter, sans-serif'))
    fig_bar.update_yaxes(gridcolor='#f0f0f0')
    return {
        'row_var': row_var, 'col_var': col_var, 'pct_type': pct_type, 'pct_label': pct_label, 'n': a['n'],
        'chi2': a['chi2'], 'p_val': a['p_val'], 'dof': a['dof'], 'cramers_v': a['cramers_v'], 'sig_label': a['sig_label'],
        'assoc_label': a['assoc_label'], 'low_expected_pct': a['low_expected_pct'], 'warning': a['warning'],
        'fisher_p': a['fisher_p'], 'odds_ratio': a['odds_ratio'], 'or_ci': a['or_ci'], 'top_cells': a['top_cells'],
        'ct_html': _style_table(ct, 'Effectifs'), 'ct_pct_html': _style_table(pct, pct_label),
        'residuals_html': _residual_table(a['residuals']),
        'chart_heat': fig_heat.to_json(), 'chart_bar': fig_bar.to_json(),
    }


def _style_table(df: pd.DataFrame, label: str) -> str:
    out = df.copy()
    if label == 'Effectifs':
        out['Total'] = df.sum(axis=1)
        out.loc['Total'] = out.sum(axis=0)
    return out.to_html(classes='table table-sm table-bordered text-center', border=0, na_rep='—')


# ─── Export Excel ────────────────────────────────────────────────────────────

def export_workbook(result: dict) -> bytes:
    """Classeur Excel d'un résultat (une feuille par tableau brut du résultat)."""
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        info = [('Indicateur', 'Valeur')]
        for key, label in (('n', 'Observations'), ('chi2', 'χ² de Pearson'), ('dof', 'ddl'), ('p_val', 'p'), ('cramers_v', 'V de Cramér'),
                           ('fisher_p', 'p exact de Fisher (2 × 2)'), ('odds_ratio', 'Odds ratio'), ('low_expected_pct', '% de cases à effectif théorique < 5')):
            if result.get(key) is not None:
                info.append((label, result[key]))
        if result.get('warning'):
            info.append(('Avertissement', result['warning']))
        if result.get('auto_comment'):
            info.append(('Lecture automatique', result['auto_comment']))
        pd.DataFrame(info[1:], columns=info[0]).to_excel(writer, sheet_name='Synthèse', index=False)
        for name, frame in (result.get('frames') or {}).items():
            frame.to_excel(writer, sheet_name=name[:31], index=not isinstance(frame.index, pd.RangeIndex))
        strata = result.get('strata')
        if strata:
            pd.DataFrame([{'Strate': b['level'], 'n': b['n'], 'χ²': b['chi2'], 'p': b['p_val'], 'V de Cramér': b['cramers_v'],
                           'Odds ratio': b['odds_ratio']} for b in strata['levels']]).to_excel(writer, sheet_name='Strates', index=False)
    return buf.getvalue()
