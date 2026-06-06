import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats
from scipy.stats import gaussian_kde


# ── Helpers ───────────────────────────────────────────────────────────────────

def _wilson_ci(k: int, n: int, z: float = 1.96):
    """Intervalle de confiance de Wilson à 95% pour une proportion."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return round(max(0.0, center - margin) * 100, 1), round(min(100.0, center + margin) * 100, 1)


def _normality_test(series: pd.Series):
    """Shapiro-Wilk (n≤5000) ou D'Agostino-Pearson. Retourne (stat, p, nom_test, normal)."""
    n = len(series)
    if n < 3:
        return None, None, "—", None
    try:
        if n <= 5000:
            stat, p = stats.shapiro(series)
            name = "Shapiro-Wilk"
        else:
            stat, p = stats.normaltest(series)
            name = "D'Agostino-Pearson"
        return round(float(stat), 4), round(float(p), 4), name, bool(p > 0.05)
    except Exception:
        return None, None, "—", None


def _outliers_iqr(series: pd.Series):
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    mask = (series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)
    return int(mask.sum()), float(q1 - 1.5 * iqr), float(q3 + 1.5 * iqr)


_LAYOUT = dict(
    plot_bgcolor='white', paper_bgcolor='white',
    font=dict(family='Inter, sans-serif', size=11),
)


# ── Tri à plat (variables catégorielles) ──────────────────────────────────────

def tris_a_plat(df: pd.DataFrame, variable: str) -> dict:
    """Tri à plat enrichi : tableau avec IC 95% Wilson, graphiques barres+cumulé et donut."""
    series = df[variable].dropna().astype(str).str.strip()

    # Remap 0/1 → Oui/Non
    try:
        num = pd.to_numeric(df[variable].dropna(), errors='raise')
        if set(num.unique()) <= {0, 1, 0.0, 1.0}:
            series = num.map({1: 'Oui', 1.0: 'Oui', 0: 'Non', 0.0: 'Non'}).astype(str)
    except Exception:
        pass

    n_total = len(df)
    n_valid = len(series)
    n_missing = n_total - n_valid
    counts = series.value_counts()
    n_cats = len(counts)

    # ── Garde : aucune valeur valide → renvoie un résultat « vide » sans planter ──
    if n_cats == 0 or n_valid == 0:
        return {
            'variable': variable,
            'n_total': int(n_total),
            'n_valid': 0,
            'missing': int(n_missing),
            'missing_pct': round(n_missing / n_total * 100, 1) if n_total else 0,
            'n_cats': 0,
            'mode_val': '—',
            'mode_pct': 0,
            'hhi': 0,
            'table_html': '<div class="alert alert-warning small mb-0">'
                          'Aucune valeur valide pour la variable <strong>' + str(variable) + '</strong>.</div>',
            'chart_bar': None,
            'chart_pie': None,
            'analyse_type': 'categorielle',
            'empty': True,
        }

    # Tableau des fréquences avec IC Wilson
    rows, cum = [], 0.0
    for modal, eff in counts.items():
        pct_v = round(eff / n_valid * 100, 1) if n_valid else 0
        pct_t = round(eff / n_total * 100, 1) if n_total else 0
        cum = round(cum + pct_v, 1)
        ci_lo, ci_hi = _wilson_ci(int(eff), n_valid)
        rows.append({
            'Modalité': modal,
            'Effectif (n)': int(eff),
            '% valides': pct_v,
            '% total': pct_t,
            'IC 95% bas': ci_lo,
            'IC 95% haut': ci_hi,
            'Fréq. cumulée (%)': min(cum, 100.0),
        })

    tbl = pd.DataFrame(rows)
    mode_val = counts.index[0] if n_cats else '—'
    mode_pct = round(counts.iloc[0] / n_valid * 100, 1) if n_valid else 0
    props = counts.values / n_valid if n_valid else np.zeros(1)
    hhi = round(float(np.sum(props ** 2)), 3)

    palette = px.colors.qualitative.Set2

    # ── Graphique 1 : barres (horizontal si >6 cat) + ligne cumulative ────────
    if n_cats > 6:
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=tbl['% valides'], y=tbl['Modalité'],
            orientation='h',
            marker=dict(
                color=tbl['% valides'],
                colorscale='Blues',
                colorbar=dict(title='%'),
            ),
            text=tbl['% valides'].map(lambda v: f'{v}%'),
            textposition='outside',
            error_x=dict(
                type='data',
                array=(tbl['IC 95% haut'] - tbl['% valides']).tolist(),
                arrayminus=(tbl['% valides'] - tbl['IC 95% bas']).tolist(),
                visible=True, color='#888', thickness=1.5,
            ),
            name='Fréquence',
        ))
        fig_bar.update_layout(
            **_LAYOUT,
            height=max(320, 38 * n_cats + 100),
            margin=dict(l=200, r=90, t=40, b=40),
            xaxis=dict(range=[0, 120], title='Fréquence (%)'),
            yaxis=dict(title='', autorange='reversed'),
            showlegend=False,
        )
    else:
        fig_bar = make_subplots(specs=[[{"secondary_y": True}]])
        colors = [palette[i % len(palette)] for i in range(n_cats)]
        fig_bar.add_trace(go.Bar(
            x=tbl['Modalité'], y=tbl['% valides'],
            name='Fréquence (%)',
            marker=dict(color=colors),
            text=tbl['% valides'].map(lambda v: f'{v}%'),
            textposition='outside',
            error_y=dict(
                type='data',
                array=(tbl['IC 95% haut'] - tbl['% valides']).tolist(),
                arrayminus=(tbl['% valides'] - tbl['IC 95% bas']).tolist(),
                visible=True, color='#666', thickness=1.5,
            ),
        ), secondary_y=False)
        fig_bar.add_trace(go.Scatter(
            x=tbl['Modalité'], y=tbl['Fréq. cumulée (%)'],
            name='Fréq. cumulée (%)',
            mode='lines+markers',
            line=dict(color='#e05c1a', width=2),
            marker=dict(size=7, symbol='circle'),
        ), secondary_y=True)
        fig_bar.update_layout(
            **_LAYOUT,
            height=370,
            margin=dict(t=40, b=60, l=50, r=50),
            legend=dict(orientation='h', y=-0.2, x=0.5, xanchor='center'),
            xaxis=dict(tickangle=-30 if n_cats > 3 else 0),
        )
        fig_bar.update_yaxes(title_text='Fréquence (%)', gridcolor='#f0f0f0', secondary_y=False)
        fig_bar.update_yaxes(title_text='Fréq. cumulée (%)', range=[0, 110], secondary_y=True)

    # ── Graphique 2 : donut avec annotation centrale ──────────────────────────
    fig_pie = go.Figure(go.Pie(
        labels=tbl['Modalité'],
        values=tbl['Effectif (n)'],
        hole=0.45,
        marker=dict(colors=palette[:n_cats]),
        texttemplate='<b>%{label}</b><br>%{percent:.1%}',
        textposition='inside',
        insidetextorientation='radial',
        hovertemplate='<b>%{label}</b><br>Effectif : %{value}<br>Part : %{percent}<extra></extra>',
    ))
    fig_pie.update_layout(
        **_LAYOUT,
        height=340,
        margin=dict(t=20, b=40, l=20, r=20),
        legend=dict(orientation='h', y=-0.12, x=0.5, xanchor='center'),
        annotations=[dict(
            text=f'<b>{n_valid}</b><br>obs.',
            x=0.5, y=0.5, font_size=14, showarrow=False,
        )],
    )

    return {
        'variable': variable,
        'n_total': n_total,
        'n_valid': n_valid,
        'missing': n_missing,
        'missing_pct': round(n_missing / n_total * 100, 1) if n_total else 0,
        'n_cats': n_cats,
        'mode_val': mode_val,
        'mode_pct': mode_pct,
        'hhi': hhi,
        'table_html': tbl.to_html(
            classes='table table-sm table-bordered table-hover align-middle text-center',
            border=0, index=False),
        'chart_bar': fig_bar.to_json(engine='json'),
        'chart_pie': fig_pie.to_json(engine='json'),
        'analyse_type': 'categorielle',
    }


# ── Statistiques pour variables continues ─────────────────────────────────────

def statistiques_continues(df: pd.DataFrame, variable: str) -> dict:
    """Stats complètes : table, histogramme+KDE+normale, violin+boxplot."""
    raw = pd.to_numeric(df[variable], errors='coerce')
    series = raw.dropna()
    n_total = len(df)
    n_valid = int(len(series))
    n_missing = n_total - n_valid

    if n_valid == 0:
        return {'variable': variable, 'error': 'Aucune valeur numérique valide.', 'analyse_type': 'continue'}

    q1 = float(series.quantile(0.25))
    q3 = float(series.quantile(0.75))
    iqr = q3 - q1
    n_out, fence_low, fence_hi = _outliers_iqr(series)
    mean_v = float(series.mean())
    std_v = float(series.std())
    cv = round(std_v / mean_v * 100, 1) if mean_v != 0 else None
    stat_n, p_n, test_name, is_normal = _normality_test(series)

    stats_rows = [
        ('N valides', n_valid),
        ('Données manquantes', f'{n_missing} ({round(n_missing/n_total*100,1) if n_total else 0}%)'),
        ('Minimum', round(float(series.min()), 3)),
        ('Maximum', round(float(series.max()), 3)),
        ('Étendue', round(float(series.max() - series.min()), 3)),
        ('Moyenne', round(mean_v, 3)),
        ('Médiane', round(float(series.median()), 3)),
        ('Écart-type', round(std_v, 3)),
        ('Coeff. de variation (%)', cv),
        ('Q1 (25%)', round(q1, 3)),
        ('Q3 (75%)', round(q3, 3)),
        ('IQR', round(iqr, 3)),
        ('Asymétrie (skewness)', round(float(series.skew()), 3)),
        ('Aplatissement (kurtosis)', round(float(series.kurt()), 3)),
        (f'{test_name} — p-valeur', p_n),
        ('Valeurs aberrantes (IQR)', n_out),
    ]
    stats_df = pd.DataFrame(stats_rows, columns=['Statistique', 'Valeur'])

    # ── Graphique 1 : histogramme + KDE + normale théorique ──────────────────
    fig_hist = go.Figure()

    # Histogramme en densité
    fig_hist.add_trace(go.Histogram(
        x=series,
        nbinsx=min(30, series.nunique()),
        histnorm='probability density',
        name='Effectif',
        marker=dict(color='rgba(26,111,168,0.65)', line=dict(color='#1a6fa8', width=0.8)),
    ))

    # KDE
    if n_valid >= 3:
        kde_fn = gaussian_kde(series)
        x_kde = np.linspace(series.min(), series.max(), 250)
        fig_hist.add_trace(go.Scatter(
            x=x_kde, y=kde_fn(x_kde),
            mode='lines', name='KDE (densité)',
            line=dict(color='#e05c1a', width=2.5),
        ))

    # Courbe normale théorique
    x_norm = np.linspace(series.min(), series.max(), 250)
    y_norm = stats.norm.pdf(x_norm, mean_v, std_v)
    fig_hist.add_trace(go.Scatter(
        x=x_norm, y=y_norm,
        mode='lines', name='Normale théorique',
        line=dict(color='#198754', width=1.8, dash='dash'),
    ))

    # Lignes moyenne / médiane
    fig_hist.add_vline(x=mean_v, line=dict(color='#e05c1a', dash='dot', width=1.5),
                       annotation_text=f'Moy.={round(mean_v,2)}', annotation_position='top right')
    fig_hist.add_vline(x=float(series.median()), line=dict(color='#0d6efd', dash='dot', width=1.5),
                       annotation_text=f'Méd.={round(float(series.median()),2)}',
                       annotation_position='top left')

    fig_hist.update_layout(
        **_LAYOUT, height=400,
        bargap=0.04,
        xaxis_title=variable, yaxis_title='Densité',
        legend=dict(orientation='h', y=-0.18, x=0.5, xanchor='center'),
        margin=dict(t=40, b=70, l=50, r=30),
    )
    fig_hist.update_yaxes(gridcolor='#f0f0f0')

    # ── Graphique 2 : violin + boxplot intégré ────────────────────────────────
    fig_vio = go.Figure()
    fig_vio.add_trace(go.Violin(
        y=series,
        name=variable,
        box_visible=True,
        meanline_visible=True,
        fillcolor='rgba(26,111,168,0.18)',
        line_color='#1a6fa8',
        marker=dict(color='#1a6fa8', opacity=0.45, size=4),
        points='outliers',
        spanmode='hard',
    ))

    # Annotations des seuils aberrants
    if fence_low > series.min() or fence_hi < series.max():
        for fence, label, pos in [(fence_low, f'Seuil inf. ({round(fence_low,1)})', 'bottom right'),
                                   (fence_hi,  f'Seuil sup. ({round(fence_hi,1)})',  'top right')]:
            if series.min() <= fence <= series.max():
                fig_vio.add_hline(y=fence, line=dict(color='#dc3545', dash='dot', width=1),
                                  annotation_text=label, annotation_position=pos,
                                  annotation_font_color='#dc3545')

    fig_vio.update_layout(
        **_LAYOUT, height=400,
        yaxis_title=variable,
        showlegend=False,
        margin=dict(t=40, b=40, l=50, r=30),
    )
    fig_vio.update_yaxes(gridcolor='#f0f0f0')

    return {
        'variable': variable,
        'n_valid': n_valid,
        'n_missing': n_missing,
        'missing_pct': round(n_missing / n_total * 100, 1) if n_total else 0,
        'mean': round(mean_v, 2),
        'median': round(float(series.median()), 2),
        'std': round(std_v, 2),
        'cv': cv,
        'n_outliers': n_out,
        'normality_test': test_name,
        'normality_p': p_n,
        'is_normal': is_normal,
        'table_html': stats_df.to_html(
            classes='table table-sm table-bordered align-middle',
            border=0, index=False),
        'chart_hist': fig_hist.to_json(engine='json'),
        'chart_box': fig_vio.to_json(engine='json'),
        'analyse_type': 'continue',
    }


# ── Analyse groupe binaire (questions à choix multiples) ─────────────────────

def analyse_binaire_groupe(df: pd.DataFrame, variables: list,
                            label_1='Oui', label_0='Non') -> dict:
    """Taux de sélection par modalité avec IC Wilson et graphique à barres horizontales."""
    n_total = len(df)
    rows = []
    for var in variables:
        col = pd.to_numeric(df[var], errors='coerce').fillna(0)
        n_oui = int(col.sum())
        pct = round(n_oui / n_total * 100, 1) if n_total else 0
        ci_lo, ci_hi = _wilson_ci(n_oui, n_total)
        label = var.split('/')[-1].strip() if '/' in var else var
        rows.append({
            'Modalité': label,
            'Effectif': n_oui,
            '% sélection': pct,
            'IC 95% bas': ci_lo,
            'IC 95% haut': ci_hi,
        })

    tbl = pd.DataFrame(rows).sort_values('% sélection', ascending=True).reset_index(drop=True)

    # Couleur dégradée selon le rang
    n = len(tbl)
    colors = px.colors.sequential.Blues[max(1, len(px.colors.sequential.Blues) - n):]
    if len(colors) < n:
        colors = (colors * (n // len(colors) + 1))[:n]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=tbl['% sélection'], y=tbl['Modalité'],
        orientation='h',
        marker=dict(color=tbl['% sélection'], colorscale='Blues',
                    colorbar=dict(title='%', thickness=12)),
        text=tbl['% sélection'].map(lambda v: f'{v}%'),
        textposition='outside',
        error_x=dict(
            type='data',
            array=(tbl['IC 95% haut'] - tbl['% sélection']).tolist(),
            arrayminus=(tbl['% sélection'] - tbl['IC 95% bas']).tolist(),
            visible=True, color='#555', thickness=1.5,
        ),
        name='% sélection',
        hovertemplate='<b>%{y}</b><br>Effectif : %{customdata}<br>Taux : %{x}%<extra></extra>',
        customdata=tbl['Effectif'],
    ))

    # Ligne de référence (taux moyen)
    avg = round(tbl['% sélection'].mean(), 1)
    fig.add_vline(x=avg, line=dict(color='#e05c1a', dash='dash', width=1.5),
                  annotation_text=f'Moy. {avg}%', annotation_position='top')

    fig.update_layout(
        **_LAYOUT,
        height=max(320, 45 * len(variables) + 120),
        margin=dict(l=200, r=90, t=50, b=40),
        xaxis=dict(range=[0, 120], title='Taux de sélection (%)'),
        yaxis=dict(title=''),
        showlegend=False,
    )

    return {
        'variables': variables,
        'n_total': n_total,
        'n_vars': len(variables),
        'top_modal': tbl.iloc[-1]['Modalité'] if n else '—',
        'top_pct': tbl.iloc[-1]['% sélection'] if n else 0,
        'avg_pct': avg,
        'table_html': tbl.sort_values('% sélection', ascending=False).to_html(
            classes='table table-sm table-bordered table-hover align-middle text-center',
            border=0, index=False),
        'chart': fig.to_json(engine='json'),
        'analyse_type': 'binaire_groupe',
    }
