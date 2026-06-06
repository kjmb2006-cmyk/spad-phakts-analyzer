import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency
import plotly.express as px
import plotly.graph_objects as go


# ─── AGGREGATION HELPERS ─────────────────────────────────────────────────────
_AGG_FUNCS = {
    'count':  ('Effectifs',     'size'),
    'sum':    ('Somme',         'sum'),
    'mean':   ('Moyenne',       'mean'),
    'median': ('Médiane',       'median'),
    'min':    ('Minimum',       'min'),
    'max':    ('Maximum',       'max'),
    'std':    ('Écart-type',    'std'),
    'nunique':('Modalités uniques', 'nunique'),
}


def tableau_croise_dynamique(df: pd.DataFrame,
                              rows: list,
                              cols: list,
                              value_var: str = None,
                              agg: str = 'count',
                              pct_type: str = 'none',
                              filters: dict = None) -> dict:
    """
    Tableau croisé dynamique (style tableau croisé dynamique Excel).

    Args:
        df       : dataframe source
        rows     : liste de variables en ligne (≥ 1) — hiérarchie de niveaux
        cols     : liste de variables en colonne (peut être vide)
        value_var: variable de valeur (None → comptage des observations)
        agg      : 'count' | 'sum' | 'mean' | 'median' | 'min' | 'max' | 'std' | 'nunique'
        pct_type : 'none' | 'row' | 'col' | 'total'
        filters  : { var: [valeur_autorisée, …] } pour filtrer avant le pivot
    """
    rows = [r for r in (rows or []) if r in df.columns]
    cols = [c for c in (cols or []) if c in df.columns]
    if not rows:
        raise ValueError("Sélectionnez au moins une variable en LIGNE.")
    if agg not in _AGG_FUNCS:
        agg = 'count'
    agg_label, agg_func_name = _AGG_FUNCS[agg]

    # Filtres
    sub = df.copy()
    if filters:
        for var, allowed in filters.items():
            if var in sub.columns and allowed:
                sub = sub[sub[var].astype(str).isin([str(a) for a in allowed])]

    keep_cols = list(dict.fromkeys(rows + cols + ([value_var] if value_var else [])))
    sub = sub[keep_cols].dropna(subset=rows + cols)

    if value_var and agg != 'count':
        sub[value_var] = pd.to_numeric(sub[value_var], errors='coerce')
        sub = sub.dropna(subset=[value_var])

    if sub.empty:
        raise ValueError("Aucune observation ne reste après application des filtres.")

    # Pivot table
    pivot_kwargs = dict(index=rows, columns=cols if cols else None,
                        aggfunc=agg_func_name, fill_value=0)
    if agg == 'count':
        pivot = pd.pivot_table(sub, values=rows[0],
                                aggfunc='size', **{'index': rows,
                                                    'columns': cols if cols else None,
                                                    'fill_value': 0})
    else:
        pivot = pd.pivot_table(sub, values=value_var, **pivot_kwargs)

    if not isinstance(pivot, (pd.DataFrame, pd.Series)) or pivot.size == 0:
        raise ValueError("Le tableau croisé produit est vide.")
    if isinstance(pivot, pd.Series):
        pivot = pivot.to_frame(name=agg_label)

    # Pourcentages éventuels
    pct_label = ''
    if pct_type and pct_type != 'none':
        n_total = pivot.values.sum()
        if pct_type == 'row':
            pct = pivot.div(pivot.sum(axis=1), axis=0).mul(100).round(1)
            pct_label = '% ligne'
        elif pct_type == 'col':
            pct = pivot.div(pivot.sum(axis=0), axis=1).mul(100).round(1)
            pct_label = '% colonne'
        else:
            pct = pivot.div(n_total).mul(100).round(1) if n_total else pivot * 0
            pct_label = '% total'
    else:
        pct = None

    # χ² seulement si comptage 2D simple
    chi2 = p_val = dof = cramers_v = None
    sig_label = assoc_label = ''
    if agg == 'count' and len(rows) == 1 and len(cols) == 1:
        try:
            ct = pivot.copy()
            ct = ct.loc[(ct.sum(axis=1) > 0), (ct.sum(axis=0) > 0)]
            if ct.shape[0] >= 2 and ct.shape[1] >= 2:
                chi2v, p, ddl, _ = chi2_contingency(ct)
                n = int(ct.values.sum())
                cv = np.sqrt(chi2v / (n * (min(ct.shape) - 1))) if min(ct.shape) > 1 else 0
                chi2, p_val, dof, cramers_v = round(chi2v, 3), round(p, 4), int(ddl), round(cv, 3)
                if p < 0.001:    sig_label = 'très hautement significative (p < 0.001)'
                elif p < 0.01:   sig_label = 'hautement significative (p < 0.01)'
                elif p < 0.05:   sig_label = 'significative (p < 0.05)'
                else:            sig_label = 'non significative (p ≥ 0.05)'
                if cv < 0.1:    assoc_label = 'très faible'
                elif cv < 0.3:  assoc_label = 'faible à modérée'
                elif cv < 0.5:  assoc_label = 'modérée à forte'
                else:           assoc_label = 'forte'
        except Exception:
            pass

    # Heatmap (si 2D simple)
    chart_heat = None
    chart_bar = None
    if len(rows) == 1 and len(cols) <= 1:
        data_for_chart = pct if pct is not None else pivot
        try:
            fig_heat = px.imshow(
                data_for_chart, text_auto=True,
                color_continuous_scale='Blues',
                title=f'Tableau croisé dynamique — {agg_label}'
                      + (f' ({pct_label})' if pct_label else ''),
                aspect='auto',
            )
            fig_heat.update_layout(height=max(300, 60 * len(pivot.index) + 100),
                                    font=dict(family='Inter, sans-serif'),
                                    margin=dict(t=60, b=60))
            chart_heat = fig_heat.to_json()
        except Exception:
            pass
        try:
            df_melt = (data_for_chart.reset_index()
                                     .melt(id_vars=rows, var_name='__col',
                                            value_name='Valeur'))
            fig_bar = px.bar(df_melt, x=rows[0], y='Valeur',
                              color='__col' if '__col' in df_melt.columns else None,
                              barmode='group',
                              title=f'Comparaison — {agg_label}'
                                    + (f' ({pct_label})' if pct_label else ''),
                              color_discrete_sequence=px.colors.qualitative.Set2,
                              text_auto='.1f')
            fig_bar.update_layout(height=380, plot_bgcolor='white',
                                   paper_bgcolor='white',
                                   font=dict(family='Inter, sans-serif'))
            fig_bar.update_yaxes(gridcolor='#f0f0f0')
            chart_bar = fig_bar.to_json()
        except Exception:
            pass

    return {
        'rows': rows,
        'cols': cols,
        'value_var': value_var,
        'agg': agg,
        'agg_label': agg_label,
        'pct_type': pct_type,
        'pct_label': pct_label,
        'n': int(pivot.values.sum()) if agg == 'count' else int(len(sub)),
        'chi2': chi2,
        'p_val': p_val,
        'dof': dof,
        'cramers_v': cramers_v,
        'sig_label': sig_label,
        'assoc_label': assoc_label,
        'pivot_html': _style_pivot(pivot, agg_label),
        'pct_html': _style_pivot(pct, pct_label) if pct is not None else None,
        'chart_heat': chart_heat,
        'chart_bar': chart_bar,
    }


def _style_pivot(df, label):
    if df is None:
        return None
    out = df.copy()
    try:
        out.loc['Total', :] = out.sum(axis=0)
        out.loc[:, 'Total'] = out.sum(axis=1)
    except Exception:
        pass
    return out.to_html(classes='table table-sm table-bordered text-center',
                       border=0, na_rep='—', float_format=lambda x: f'{x:.1f}' if isinstance(x, float) else x)


def tableau_croise(df: pd.DataFrame, row_var: str, col_var: str,
                   pct_type: str = 'row') -> dict:
    sub = df[[row_var, col_var]].dropna()

    # Contingency table (counts)
    ct = pd.crosstab(sub[row_var], sub[col_var])

    # Chi-square test
    chi2, p_val, dof, expected = chi2_contingency(ct)
    n = ct.values.sum()
    cramers_v = np.sqrt(chi2 / (n * (min(ct.shape) - 1))) if min(ct.shape) > 1 else 0

    # Percentage tables
    if pct_type == 'row':
        ct_pct = ct.div(ct.sum(axis=1), axis=0).mul(100).round(1)
        pct_label = '% ligne'
    elif pct_type == 'col':
        ct_pct = ct.div(ct.sum(axis=0), axis=1).mul(100).round(1)
        pct_label = '% colonne'
    else:
        ct_pct = ct.div(n).mul(100).round(1)
        pct_label = '% total'

    # Residuals (standardized)
    expected_df = pd.DataFrame(expected, index=ct.index, columns=ct.columns)
    residuals = ((ct - expected_df) / np.sqrt(expected_df)).round(2)

    # Heatmap chart
    fig_heat = px.imshow(
        ct_pct,
        text_auto=True,
        color_continuous_scale='Blues',
        title=f'Tableau croisé : {row_var} × {col_var} ({pct_label})',
        labels=dict(x=col_var, y=row_var, color=pct_label),
        aspect='auto',
    )
    fig_heat.update_layout(height=max(300, 60 * len(ct.index) + 100),
                            font=dict(family='Inter, sans-serif'),
                            margin=dict(t=60, b=60))

    # Grouped bar chart
    ct_reset = ct_pct.reset_index().melt(id_vars=row_var,
                                          var_name=col_var, value_name='Pourcentage')
    fig_bar = px.bar(
        ct_reset, x=row_var, y='Pourcentage', color=col_var,
        barmode='group',
        title=f'Comparaison des profils ({pct_label})',
        color_discrete_sequence=px.colors.qualitative.Set2,
        text_auto='.1f',
    )
    fig_bar.update_layout(height=380, plot_bgcolor='white', paper_bgcolor='white',
                           font=dict(family='Inter, sans-serif'))
    fig_bar.update_yaxes(gridcolor='#f0f0f0')

    # Interpretation
    if p_val < 0.001:
        sig = 'très hautement significative (p < 0.001)'
    elif p_val < 0.01:
        sig = 'hautement significative (p < 0.01)'
    elif p_val < 0.05:
        sig = 'significative (p < 0.05)'
    else:
        sig = 'non significative (p ≥ 0.05)'

    if cramers_v < 0.1:
        assoc = 'très faible'
    elif cramers_v < 0.3:
        assoc = 'faible à modérée'
    elif cramers_v < 0.5:
        assoc = 'modérée à forte'
    else:
        assoc = 'forte'

    return {
        'row_var': row_var,
        'col_var': col_var,
        'pct_type': pct_type,
        'pct_label': pct_label,
        'n': int(n),
        'chi2': round(chi2, 3),
        'p_val': round(p_val, 4),
        'dof': int(dof),
        'cramers_v': round(cramers_v, 3),
        'sig_label': sig,
        'assoc_label': assoc,
        'ct_html': _style_table(ct, 'Effectifs'),
        'ct_pct_html': _style_table(ct_pct, pct_label),
        'residuals_html': _style_residuals(residuals),
        'chart_heat': fig_heat.to_json(),
        'chart_bar': fig_bar.to_json(),
    }


def _style_table(df: pd.DataFrame, label: str) -> str:
    total_row = df.sum(axis=1).rename('Total')
    total_col = df.sum(axis=0).rename('Total')
    df_out = df.copy()
    df_out['Total'] = total_row
    total_col['Total'] = int(df.values.sum()) if label == 'Effectifs' else None
    df_out.loc['Total'] = total_col
    return df_out.to_html(classes='table table-sm table-bordered text-center',
                          border=0, na_rep='—')


def _style_residuals(df: pd.DataFrame) -> str:
    def color_cell(val):
        try:
            v = float(val)
            if v > 2:
                return 'background-color:#d4edda'
            elif v < -2:
                return 'background-color:#f8d7da'
            return ''
        except:
            return ''
    return (df.style.map(color_cell)
              .format('{:.2f}')
              .set_table_attributes('class="table table-sm table-bordered text-center"')
              .to_html())
