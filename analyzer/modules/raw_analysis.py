"""
SPAD Analyzer — Analyse brute complète
Analyse descriptive de niveau expert : stats, graphiques, qualité, anomalies.
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from modules.data_loader import get_var_types

# ── Palette SPAD ──────────────────────────────────────────────────────────────
NAVY   = '#1A5276'
TEAL   = '#17A589'
ORANGE = '#E67E22'
RED    = '#C0392B'
PURPLE = '#7D3C98'
GREY   = '#85929E'
LIGHT  = '#F8F9FA'
BLUE   = '#2E86C1'

FONT   = dict(family='Inter, sans-serif', size=11)
LAYOUT = dict(plot_bgcolor='white', paper_bgcolor='white', font=FONT,
              margin=dict(l=50, r=30, t=50, b=40))


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors='coerce').dropna()


def detect_outliers_iqr(series: pd.Series) -> dict:
    num = _safe_num(series)
    if len(num) < 4:
        return {'has_outliers': False, 'count': 0, 'pct': 0, 'lower': None, 'upper': None}
    Q1, Q3 = num.quantile(0.25), num.quantile(0.75)
    IQR    = Q3 - Q1
    lo, hi = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
    out    = num[(num < lo) | (num > hi)]
    return {
        'has_outliers': len(out) > 0,
        'count': int(len(out)),
        'pct': round(len(out) / len(num) * 100, 1),
        'lower': round(float(lo), 3),
        'upper': round(float(hi), 3),
        'extreme_low':  round(float(out[out < lo].min()), 3) if any(out < lo) else None,
        'extreme_high': round(float(out[out > hi].max()), 3) if any(out > hi) else None,
    }


def _normality_label(skew: float, kurt: float) -> tuple[str, str]:
    """Retourne (label, badge_class) pour la distribution."""
    if abs(skew) <= 0.5 and abs(kurt) <= 1.0:
        return 'Normale', 'badge-normal'
    elif skew > 1.0:
        return 'Asymétrie positive forte', 'badge-skew-right'
    elif skew < -1.0:
        return 'Asymétrie négative forte', 'badge-skew-left'
    elif abs(skew) <= 1.0:
        return 'Légèrement asymétrique', 'badge-skew-light'
    else:
        return 'Distribution non normale', 'badge-warn'


def _shannon_entropy(series: pd.Series) -> float:
    counts = series.value_counts(normalize=True)
    return round(-float((counts * np.log2(counts + 1e-10)).sum()), 3)


def _herfindahl(series: pd.Series) -> float:
    props = series.value_counts(normalize=True)
    return round(float((props ** 2).sum()), 3)


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSE DESCRIPTIVE COMPLÈTE
# ══════════════════════════════════════════════════════════════════════════════

def descriptive_summary(df: pd.DataFrame) -> dict:
    var_types = get_var_types(df)
    cat_vars  = [c for c, t in var_types.items() if t == 'categorielle']
    num_vars  = [c for c, t in var_types.items() if t == 'continue']
    bin_vars  = [c for c, t in var_types.items() if t == 'binaire']

    results = {'continuous': [], 'categorical': [], 'binary': []}

    # ── VARIABLES CONTINUES ────────────────────────────────────────────────
    for var in num_vars:
        num = _safe_num(df[var])
        if len(num) < 2:
            continue

        n_total = len(df[var])
        n_valid = int(len(num))
        n_miss  = n_total - n_valid
        mean_   = float(num.mean())
        med_    = float(num.median())
        std_    = float(num.std())
        mn, mx  = float(num.min()), float(num.max())
        q1, q3  = float(num.quantile(0.25)), float(num.quantile(0.75))
        skew_   = float(num.skew())
        kurt_   = float(num.kurtosis())
        cv_     = round(std_ / mean_ * 100, 1) if mean_ != 0 else None
        sem_    = float(num.sem())
        ci95_lo = round(mean_ - 1.96 * sem_, 3)
        ci95_hi = round(mean_ + 1.96 * sem_, 3)
        outliers = detect_outliers_iqr(df[var])
        norm_label, norm_badge = _normality_label(skew_, kurt_)

        stats_dict = {
            'Variable':      var,
            'N valides':     n_valid,
            'Manquantes':    n_miss,
            '% manq.':       round(n_miss / n_total * 100, 1) if n_total > 0 else 0,
            'Moyenne':       round(mean_, 3),
            'Médiane':       round(med_, 3),
            'Écart-type':    round(std_, 3),
            'CV (%)':        cv_,
            'Min':           round(mn, 3),
            'Q1':            round(q1, 3),
            'Q3':            round(q3, 3),
            'Max':           round(mx, 3),
            'IQR':           round(q3 - q1, 3),
            'Asymétrie':     round(skew_, 3),
            'Aplatissement': round(kurt_, 3),
            'IC 95% (bas)':  ci95_lo,
            'IC 95% (haut)': ci95_hi,
        }

        # Histogramme + courbe normale théorique
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Histogram(
            x=num, nbinsx=min(30, max(5, int(np.sqrt(n_valid)))),
            name='Effectif', marker_color=BLUE, opacity=0.75,
            histnorm='probability density',
        ))
        # Courbe KDE approximée par gaussienne théorique
        x_range = np.linspace(mn - std_, mx + std_, 200)
        kde_y   = (1 / (std_ * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_range - mean_) / std_) ** 2)
        fig_hist.add_trace(go.Scatter(
            x=x_range, y=kde_y, mode='lines',
            line=dict(color=ORANGE, width=2.5, dash='solid'),
            name='Loi normale théorique',
        ))
        fig_hist.add_vline(x=mean_,  line=dict(color=RED,  width=1.5, dash='dash'), annotation_text='Moy', annotation_position='top right')
        fig_hist.add_vline(x=med_,   line=dict(color=TEAL, width=1.5, dash='dot'),  annotation_text='Méd', annotation_position='top left')
        fig_hist.update_layout(
            **LAYOUT,
            title=f'Distribution — <b>{var}</b>',
            xaxis_title=var, yaxis_title='Densité',
            height=300, showlegend=True,
            legend=dict(orientation='h', y=-0.25, x=0),
        )

        # Box plot + violin
        fig_box = make_subplots(rows=1, cols=2, subplot_titles=['Boîte à moustaches', 'Violin'])
        fig_box.add_trace(go.Box(
            y=num, name=var, marker_color=TEAL,
            boxmean='sd', boxpoints='outliers', jitter=0.3,
            line=dict(color=NAVY, width=1.5),
        ), row=1, col=1)
        fig_box.add_trace(go.Violin(
            y=num, name=var, fillcolor=f'rgba(23,165,137,0.25)',
            line_color=TEAL, meanline_visible=True,
            box_visible=True, points=False,
        ), row=1, col=2)
        fig_box.update_layout(
            **LAYOUT,
            height=300, showlegend=False,
            title=f'Dispersion — <b>{var}</b>',
        )

        results['continuous'].append({
            'var':        var,
            'stats':      stats_dict,
            'outliers':   outliers,
            'norm_label': norm_label,
            'norm_badge': norm_badge,
            'cv':         cv_,
            'ci95':       (ci95_lo, ci95_hi),
            'chart_hist': fig_hist.to_json(engine='json'),
            'chart_box':  fig_box.to_json(engine='json'),
        })

    # ── VARIABLES CATÉGORIELLES ────────────────────────────────────────────
    for var in cat_vars:
        series = df[var].dropna()
        if len(series) == 0:
            continue
        n_valid  = len(series)
        n_miss   = len(df[var]) - n_valid
        counts   = series.value_counts()
        n_cats   = len(counts)
        top_n    = min(15, n_cats)
        top      = counts.head(top_n)

        pct      = (top.values / n_valid * 100).round(1)
        cum_pct  = pct.cumsum().round(1)

        entropy_ = _shannon_entropy(series)
        herf_    = _herfindahl(series)
        max_ent  = round(np.log2(n_cats), 3) if n_cats > 1 else 1.0
        norm_ent = round(entropy_ / max_ent, 3) if max_ent > 0 else 1.0

        dominant_cat = str(counts.index[0])
        dominant_pct = round(counts.iloc[0] / n_valid * 100, 1)

        freq_df = pd.DataFrame({
            'Modalité':       top.index.astype(str),
            'Effectif':       top.values,
            'Fréquence (%)':  pct,
            'Fréq. cum. (%)': cum_pct,
        })

        colors = px.colors.qualitative.Bold[:top_n]

        # Bar chart horizontal
        fig_bar = go.Figure(go.Bar(
            x=pct, y=top.index.astype(str).tolist(),
            orientation='h',
            text=[f'{p}%' for p in pct],
            textposition='outside',
            marker=dict(
                color=pct,
                colorscale=[[0, '#AED6F1'], [1, NAVY]],
                showscale=False,
            ),
        ))
        fig_bar.update_layout(
            **LAYOUT,
            title=f'Distribution — <b>{var}</b>',
            xaxis=dict(title='Fréquence (%)', range=[0, max(pct) * 1.2]),
            yaxis=dict(autorange='reversed'),
            height=max(280, 32 * top_n + 80),
        )

        # Donut
        fig_pie = go.Figure(go.Pie(
            labels=top.index.astype(str).tolist(),
            values=top.values.tolist(),
            hole=0.42,
            marker=dict(colors=colors, line=dict(color='white', width=2)),
            textinfo='percent+label',
            textfont=dict(size=10),
        ))
        fig_pie.update_layout(
            **LAYOUT,
            title=f'Répartition — <b>{var}</b>',
            height=300,
            showlegend=n_cats <= 8,
            legend=dict(orientation='h', y=-0.15, x=0),
        )

        results['categorical'].append({
            'variable':      var,
            'n_categories':  n_cats,
            'n_missing':     n_miss,
            'pct_missing':   round(n_miss / len(df[var]) * 100, 1) if len(df[var]) > 0 else 0,
            'n_valid':       n_valid,
            'dominant':      dominant_cat,
            'dominant_pct':  dominant_pct,
            'entropy':       entropy_,
            'norm_entropy':  norm_ent,
            'herfindahl':    herf_,
            'top_shown':     top_n,
            'table':         freq_df.to_html(
                                 classes='table table-sm table-hover mb-0',
                                 border=0, index=False),
            'chart_bar':     fig_bar.to_json(engine='json'),
            'chart_pie':     fig_pie.to_json(engine='json'),
        })

    # ── VARIABLES BINAIRES ────────────────────────────────────────────────
    for var in bin_vars:
        series  = df[var].dropna()
        n_valid = len(series)
        n_miss  = len(df[var]) - n_valid
        if n_valid == 0:
            continue

        counts = series.value_counts()
        # Remapper 1/0 en Oui/Non si numérique
        try:
            num_v = pd.to_numeric(series, errors='coerce').dropna()
            if set(num_v.unique()).issubset({0, 1, 0.0, 1.0}):
                counts.index = counts.index.map(
                    {1: 'Oui (1)', 1.0: 'Oui (1)', 0: 'Non (0)', 0.0: 'Non (0)'})
        except Exception:
            pass

        pct    = (counts.values / n_valid * 100).round(1)
        pct_1  = float(pct[0])  # dominant
        pct_0  = 100 - pct_1

        freq_df = pd.DataFrame({
            'Modalité':      counts.index.astype(str),
            'Effectif':      counts.values,
            'Fréquence (%)': pct,
        })

        color_map = {}
        for lbl in counts.index.astype(str):
            if 'Oui' in lbl or lbl in ('1', '1.0', 'True', 'yes', 'oui'):
                color_map[lbl] = TEAL
            else:
                color_map[lbl] = '#E8E8E8'

        # Bar chart
        fig_bar = go.Figure()
        for lbl, eff, p in zip(counts.index.astype(str), counts.values, pct):
            fig_bar.add_trace(go.Bar(
                x=[lbl], y=[p],
                text=[f'{p}%'],
                textposition='outside',
                marker_color=color_map.get(lbl, GREY),
                name=lbl,
            ))
        fig_bar.update_layout(
            **LAYOUT,
            title=f'Proportion — <b>{var}</b>',
            yaxis=dict(title='Fréquence (%)', range=[0, 115]),
            height=280, showlegend=False,
            barmode='group',
        )

        # Gauge de prévalence
        fig_gauge = go.Figure(go.Indicator(
            mode='gauge+number',
            value=pct_1,
            number={'suffix': '%', 'font': {'size': 28, 'color': NAVY}},
            gauge={
                'axis': {'range': [0, 100], 'ticksuffix': '%'},
                'bar': {'color': TEAL},
                'steps': [
                    {'range': [0,  25],  'color': '#FDFEFE'},
                    {'range': [25, 75],  'color': '#EBF5FB'},
                    {'range': [75, 100], 'color': '#D6EAF8'},
                ],
                'threshold': {'line': {'color': NAVY, 'width': 3},
                              'thickness': 0.8, 'value': 50},
            },
            title={'text': f'Prévalence — {counts.index.astype(str)[0]}',
                   'font': {'size': 13}},
        ))
        fig_gauge.update_layout(height=220, margin=dict(l=30, r=30, t=60, b=20),
                                font=FONT, paper_bgcolor='white')

        results['binary'].append({
            'variable':  var,
            'n_missing': n_miss,
            'pct_missing': round(n_miss / len(df[var]) * 100, 1),
            'n_valid':   n_valid,
            'table':     freq_df.to_html(
                             classes='table table-sm table-hover mb-0',
                             border=0, index=False),
            'chart':     fig_bar.to_json(engine='json'),
            'chart_gauge': fig_gauge.to_json(engine='json'),
            'prevalence': pct_1,
            'label_pos':  str(counts.index.astype(str)[0]),
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# VUE D'ENSEMBLE
# ══════════════════════════════════════════════════════════════════════════════

def overview_stats(df: pd.DataFrame) -> dict:
    var_types = get_var_types(df)
    rows = []
    for col in df.columns:
        s      = df[col]
        n_miss = int(s.isnull().sum())
        pct_m  = round(n_miss / len(s) * 100, 1) if len(s) > 0 else 0
        typ    = var_types.get(col, '?')
        row    = {
            'Variable':     col,
            'Type':         typ,
            'N valides':    int(s.notna().sum()),
            'Manquantes':   n_miss,
            '% manq.':      pct_m,
            'Modalités / Min': '',
            'Mode / Max':   '',
        }
        if typ in ('categorielle', 'binaire'):
            row['Modalités / Min'] = int(s.nunique())
            mode = s.mode()
            row['Mode / Max'] = str(mode.iloc[0]) if len(mode) else '—'
        elif typ == 'continue':
            num = _safe_num(s)
            if len(num):
                row['Modalités / Min'] = round(float(num.min()), 2)
                row['Mode / Max']      = round(float(num.max()), 2)
        rows.append(row)

    ov_df = pd.DataFrame(rows)
    return {
        'table_html': ov_df.to_html(
            classes='table table-sm table-hover mb-0',
            border=0, index=False),
        'n_vars': len(df.columns),
        'n_obs':  len(df),
        'complete_vars': int((df.isnull().sum() == 0).sum()),
        'vars_with_missing': int((df.isnull().sum() > 0).sum()),
    }


# ══════════════════════════════════════════════════════════════════════════════
# QUALITÉ & SCORE
# ══════════════════════════════════════════════════════════════════════════════

def data_quality_score(df: pd.DataFrame) -> dict:
    n_obs, n_vars = len(df), len(df.columns)
    total_cells   = n_obs * n_vars
    missing_total = int(df.isnull().sum().sum())
    missing_pct   = round(missing_total / total_cells * 100, 1) if total_cells > 0 else 0

    var_types = get_var_types(df)
    counts    = {t: 0 for t in ['categorielle', 'continue', 'binaire', 'date', 'texte_libre']}
    for t in var_types.values():
        counts[t] = counts.get(t, 0) + 1

    # Scores partiels
    completeness  = max(0, 100 - missing_pct)
    n_types_used  = len([c for c in counts.values() if c > 0])
    diversity_sc  = min(100, n_types_used / 4 * 100)
    size_sc       = min(100, n_obs / 200 * 100)
    quality_score = round(completeness * 0.60 + diversity_sc * 0.25 + size_sc * 0.15)

    return {
        'quality_score': quality_score,
        'completeness':  round(completeness, 1),
        'diversity':     counts,
        'missing_pct':   missing_pct,
        'n_obs':         n_obs,
        'n_vars':        n_vars,
    }


def systematic_analysis(df: pd.DataFrame) -> dict:
    var_types  = get_var_types(df)
    n_obs, n_vars = len(df), len(df.columns)

    cat_vars  = [c for c, t in var_types.items() if t == 'categorielle']
    num_vars  = [c for c, t in var_types.items() if t == 'continue']
    bin_vars  = [c for c, t in var_types.items() if t == 'binaire']
    date_vars = [c for c, t in var_types.items() if t == 'date']
    text_vars = [c for c, t in var_types.items() if t == 'texte_libre']

    miss_by_var     = df.isnull().sum().sort_values(ascending=False)
    vars_with_miss  = miss_by_var[miss_by_var > 0]
    complete_vars   = int((df.isnull().sum() == 0).sum())

    # Stats continues résumées
    cont_stats = {}
    for var in num_vars:
        num = _safe_num(df[var])
        if len(num) > 0:
            out = detect_outliers_iqr(df[var])
            cont_stats[var] = {
                'mean':    round(float(num.mean()), 3),
                'median':  round(float(num.median()), 3),
                'std':     round(float(num.std()), 3),
                'min':     round(float(num.min()), 3),
                'max':     round(float(num.max()), 3),
                'skew':    round(float(num.skew()), 3),
                'outliers': out,
            }

    # Cardinality catégorielles
    cat_card = {}
    for var in cat_vars:
        card = df[var].nunique()
        mode = df[var].mode()
        cat_card[var] = {
            'n_categories':  card,
            'dominant':      str(mode.iloc[0]) if len(mode) else '—',
            'dominant_pct':  round((df[var] == mode.iloc[0]).sum() / len(df[var]) * 100, 1)
                             if len(mode) > 0 else 0,
        }

    # ── Anomalies ─────────────────────────────────────────────────────────
    anomalies = []

    for var in num_vars:
        num = _safe_num(df[var])
        if len(num) < 2:
            continue
        # Variance nulle
        if float(num.std()) < 0.001:
            anomalies.append({'type': 'Variance nulle', 'variable': var, 'severity': 'élevé',
                               'note': "La variable ne contient qu'une seule valeur - inutilisable."})
        # Outliers importants
        out = detect_outliers_iqr(df[var])
        if out['pct'] > 10:
            anomalies.append({'type': 'Outliers nombreux', 'variable': var, 'severity': 'modéré',
                               'note': f"{out['count']} valeurs aberrantes ({out['pct']}%) hors [{out['lower']}, {out['upper']}]."})
        # Forte asymétrie
        sk = float(num.skew())
        if abs(sk) > 2:
            anomalies.append({'type': 'Forte asymétrie', 'variable': var, 'severity': 'faible',
                               'note': f"Asymetrie = {sk:.2f} - distribution tres eloignee de la normale."})

    for col in df.columns:
        pct_m = df[col].isnull().sum() / len(df) * 100
        if pct_m > 90:
            anomalies.append({'type': 'Colonne presque vide', 'variable': col, 'severity': 'élevé',
                               'note': f'{pct_m:.1f}% de valeurs manquantes.'})
        elif pct_m > 50:
            anomalies.append({'type': 'Taux de manquants élevé', 'variable': col, 'severity': 'modéré',
                               'note': f'{pct_m:.1f}% de valeurs manquantes.'})

    for var in bin_vars:
        counts = df[var].value_counts()
        if len(counts) >= 2:
            pct_dom = max(counts) / len(df) * 100
            if pct_dom > 95:
                anomalies.append({'type': 'Déséquilibre extrême', 'variable': var, 'severity': 'modéré',
                                   'note': f"{pct_dom:.1f}% d'une seule modalite - peu discriminante."})

    for var in cat_vars:
        counts = df[var].value_counts()
        rare   = (counts == 1).sum()
        if rare > n_obs / 3:
            anomalies.append({'type': 'Catégories trop rares', 'variable': var, 'severity': 'faible',
                               'note': f"{rare} categories avec une seule observation - regroupement conseille."})

    # ── Recommandations ───────────────────────────────────────────────────
    recs = []
    if len(num_vars) >= 2:
        recs.append({'rank': 1, 'type': 'Corrélations', 'rationale':
            f'Vous avez {len(num_vars)} variables continues. Explorez leurs relations linéaires.',
            'variables': num_vars[:6], 'module': 'multivariate'})
    if len(cat_vars) >= 1 and len(num_vars) >= 1:
        recs.append({'rank': 2, 'type': 'Tableaux croisés', 'rationale':
            f'Croisez vos {len(cat_vars)} variables catégorielles avec les variables numériques.',
            'variables': cat_vars[:4], 'module': 'crosstabs'})
    if len(num_vars) >= 3:
        recs.append({'rank': 3, 'type': 'ACP (Analyse en Composantes Principales)', 'rationale':
            f'Réduisez la dimensionnalité de vos {len(num_vars)} variables continues.',
            'variables': num_vars[:6], 'module': 'multivariate'})
    if len(cat_vars) >= 2:
        recs.append({'rank': 4, 'type': 'ACM (Correspondances Multiples)', 'rationale':
            f'Explorez la structure des {len(cat_vars)} variables catégorielles.',
            'variables': cat_vars[:6], 'module': 'multivariate'})
    if len(num_vars) >= 2 or len(bin_vars) >= 2:
        recs.append({'rank': 5, 'type': 'Classification (K-Means)', 'rationale':
            'Segmentez votre population en groupes homogènes pour cibler les interventions.',
            'variables': (num_vars + bin_vars)[:6], 'module': 'multivariate'})

    quality = data_quality_score(df)

    return {
        'profile': {
            'n_obs':           n_obs,
            'n_vars':          n_vars,
            'n_continuous':    len(num_vars),
            'n_categorical':   len(cat_vars),
            'n_binary':        len(bin_vars),
            'n_date':          len(date_vars),
            'n_text':          len(text_vars),
            'complete_vars':   complete_vars,
            'vars_with_missing': int((df.isnull().sum() > 0).sum()),
        },
        'missing': {
            'total_cells':      n_obs * n_vars,
            'missing_count':    int(df.isnull().sum().sum()),
            'missing_pct':      round(df.isnull().sum().sum() / (n_obs * n_vars) * 100, 1),
            'vars_with_missing': vars_with_miss.to_dict(),
            'complete_variables': complete_vars,
        },
        'continuous_stats':   cont_stats,
        'categorical_stats':  cat_card,
        'anomalies':          anomalies,
        'recommendations':    sorted(recs, key=lambda x: x['rank']),
        'quality':            quality,
    }


# ══════════════════════════════════════════════════════════════════════════════
# GRAPHIQUES GLOBAUX
# ══════════════════════════════════════════════════════════════════════════════

def data_quality_gauge(quality_dict: dict) -> str:
    score = quality_dict.get('quality_score', 0)
    if score >= 75:
        bar_color = TEAL
    elif score >= 50:
        bar_color = ORANGE
    else:
        bar_color = RED

    fig = go.Figure(go.Indicator(
        mode='gauge+number',
        value=score,
        number={'font': {'size': 42, 'color': bar_color}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': GREY},
            'bar':  {'color': bar_color, 'thickness': 0.28},
            'bgcolor': 'white',
            'borderwidth': 0,
            'steps': [
                {'range': [0,  50], 'color': '#FADBD8'},
                {'range': [50, 75], 'color': '#FDEBD0'},
                {'range': [75, 100],'color': '#D5F5E3'},
            ],
            'threshold': {'line': {'color': NAVY, 'width': 3},
                          'thickness': 0.85, 'value': 70},
        },
        title={'text': f'Score de qualité des données<br><span style="font-size:.78rem;color:{GREY}">Complétude 60% · Diversité 25% · Taille 15%</span>',
               'font': {'size': 13}},
    ))
    fig.update_layout(height=300, font=FONT, paper_bgcolor='white',
                      margin=dict(l=30, r=30, t=80, b=20))
    return fig.to_json(engine='json')


def composition_chart(analysis_dict: dict) -> str:
    diversity = analysis_dict.get('quality', {}).get('diversity', {})
    if not diversity:
        return None

    labels, values, colors_list = [], [], []
    CMAP = {'continue': BLUE, 'categorielle': ORANGE, 'binaire': TEAL,
            'date': PURPLE, 'texte_libre': GREY}
    LMAP = {'continue': 'Continue', 'categorielle': 'Catégorielle',
            'binaire': 'Binaire', 'date': 'Date', 'texte_libre': 'Texte libre'}

    for typ, count in diversity.items():
        if count > 0:
            labels.append(f'{LMAP.get(typ, typ)} ({count})')
            values.append(count)
            colors_list.append(CMAP.get(typ, GREY))

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors_list, line=dict(color='white', width=3)),
        hole=0.45,
        textinfo='label+percent',
        textfont=dict(size=11),
        pull=[0.03] * len(labels),
    ))
    fig.update_layout(
        title='Composition des variables par type',
        height=300, font=FONT, paper_bgcolor='white',
        showlegend=False,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig.to_json(engine='json')


def distributions_chart(df: pd.DataFrame) -> str:
    var_types = get_var_types(df)
    num_vars  = [c for c, t in var_types.items() if t == 'continue']
    if not num_vars:
        return None

    num_vars_d = num_vars[:6]
    n_plots    = len(num_vars_d)
    n_cols     = 2
    n_rows     = (n_plots + 1) // n_cols

    fig = make_subplots(rows=n_rows, cols=n_cols,
                        subplot_titles=[f'<b>{v}</b>' for v in num_vars_d])

    for i, var in enumerate(num_vars_d):
        r, c = (i // n_cols) + 1, (i % n_cols) + 1
        num  = _safe_num(df[var])
        if len(num) < 2:
            continue
        fig.add_trace(go.Histogram(
            x=num, nbinsx=min(25, max(5, int(np.sqrt(len(num))))),
            name=var, marker_color=BLUE, opacity=0.75, showlegend=False,
        ), row=r, col=c)
        # Ligne de moyenne
        fig.add_vline(x=float(num.mean()), line=dict(color=RED, width=1.5, dash='dash'),
                      row=r, col=c)

    fig.update_layout(
        title_text=f'Distributions des variables continues ({n_plots}/{len(num_vars)})',
        height=max(350, 260 * n_rows),
        plot_bgcolor='white', paper_bgcolor='white', font=FONT,
        showlegend=False, margin=dict(t=70, b=40, l=40, r=20),
    )
    for ax in fig.layout:
        if ax.startswith('xaxis') or ax.startswith('yaxis'):
            fig.layout[ax].update(showgrid=True, gridcolor='#F0F0F0')
    return fig.to_json(engine='json')


def missing_bar_chart(df: pd.DataFrame):
    miss_pct = (df.isnull().mean() * 100).round(1).reset_index()
    miss_pct.columns = ['Variable', '% manquant']
    miss_pct = miss_pct[miss_pct['% manquant'] > 0].sort_values('% manquant', ascending=True)
    if miss_pct.empty:
        return None

    miss_pct['Couleur'] = miss_pct['% manquant'].apply(
        lambda x: RED if x > 50 else ORANGE if x > 20 else BLUE)

    fig = go.Figure(go.Bar(
        x=miss_pct['% manquant'],
        y=miss_pct['Variable'],
        orientation='h',
        text=[f'{v}%' for v in miss_pct['% manquant']],
        textposition='outside',
        marker=dict(color=miss_pct['Couleur']),
    ))
    layout = {**LAYOUT, 'margin': dict(l=200, r=80, t=60, b=40)}
    fig.update_layout(
        **layout,
        title='Taux de données manquantes par variable',
        xaxis=dict(title='% manquant', range=[0, 115]),
        height=max(300, 28 * len(miss_pct) + 100),
    )
    return fig.to_json(engine='json')


def missing_heatmap(df: pd.DataFrame):
    miss = df.isnull().astype(int)
    if miss.shape[1] > 40:
        top_cols = df.isnull().sum().sort_values(ascending=False).head(40).index.tolist()
        miss = miss[top_cols]

    fig = px.imshow(
        miss.T,
        color_continuous_scale=['#EBF5FB', RED],
        labels=dict(x='Observation', y='Variable', color='Manquant'),
        aspect='auto',
    )
    fig.update_coloraxes(showscale=True,
                         colorbar=dict(title='Manquant', tickvals=[0, 1],
                                       ticktext=['Présent', 'Absent']))
    layout = {**LAYOUT, 'margin': dict(l=200, r=60, t=70, b=40)}
    fig.update_layout(
        **layout,
        title='Carte des données manquantes (rouge = absent)',
        height=max(300, 20 * len(miss.columns) + 120),
    )
    fig.update_xaxes(showticklabels=False)
    return fig.to_json(engine='json')


def correlation_matrix(df: pd.DataFrame):
    num_df = df.select_dtypes(include='number')
    if num_df.shape[1] < 2:
        return None

    corr = num_df.corr(method='pearson').round(2)
    n    = len(corr.columns)

    # Masque triangle supérieur
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    corr_masked = corr.copy()
    corr_masked[mask] = np.nan

    text_matrix = corr_masked.map(
        lambda v: f'{v:.2f}' if not pd.isna(v) else '').values

    fig = go.Figure(go.Heatmap(
        z=corr_masked.values,
        x=corr.columns.tolist(),
        y=corr.columns.tolist(),
        colorscale='RdBu_r',
        zmin=-1, zmax=1,
        text=text_matrix,
        texttemplate='%{text}',
        textfont=dict(size=max(8, 12 - n // 4)),
        hovertemplate='%{y} × %{x}<br>r = %{z:.3f}<extra></extra>',
        colorbar=dict(title='r de Pearson', tickvals=[-1, -0.5, 0, 0.5, 1]),
    ))
    layout = {**LAYOUT, 'margin': dict(l=120, r=20, t=70, b=120)}
    fig.update_layout(
        **layout,
        title='Matrice de correlations (Pearson) - triangle inferieur',
        height=max(400, 40 * n + 120),
    )
    fig.update_xaxes(tickangle=-45, side='bottom')
    return fig.to_json(engine='json')
