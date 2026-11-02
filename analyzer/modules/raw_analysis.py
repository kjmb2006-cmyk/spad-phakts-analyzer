"""
SPAD Analyzer — Diagnostic des données (page « Diagnostic des données », ex « Analyse brute »)

Ce module répond à une seule question : ces données sont-elles en état d'être analysées ?
  - manquants RÉELS ou STRUCTURELS : une réponse absente n'est un manque que si la question s'appliquait. Avec l'XLSForm joint,
    le saut de logique (« relevant ») de chaque question le dit ; sans lui, les champs « Autre, précisez » sont reconnus à leur nom ;
  - score de qualité fondé sur des mesures qui ont un sens : complétude réelle, validité (lignes sans erreur à la validation),
    unicité (soumissions en double), variables exploitables ;
  - anomalies, structure du jeu, associations entre variables (V de Cramér, Spearman) ;
  - recommandations d'analyse qui s'appuient sur ces associations.

Le détail variable par variable (tri à plat, IC, décomposition par groupe) est dans « Statistiques descriptives » ;
`descriptive_summary` reste là pour les rapports.
"""
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from modules import dataset, xlsform_expr

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

MISSING_MODERATE = 20          # % de manquants réels au-delà duquel on le signale
MISSING_HIGH = 50
MISSING_EMPTY = 90
POSITIVE_VALUES = {'1', 'oui', 'yes', 'true', 'vrai', 'o', 'y', 'ok', 'present', 'présent'}
_STRUCTURAL_NAME = re.compile(r'(^|[_/ ])(autre|autres|other|precis|precise|preciser|precisez|detail|details|commentaire|observation|'
                              r'remarque|note)([_/ ]|$)|^si[_ ]', re.IGNORECASE)
MAX_ASSOC_VARS = 30
REDUNDANT_V = 0.95            # lien quasi total : l'une des deux variables découle de l'autre (district dans région…)
MAX_ASSOC_ROWS = 5000
MAX_HEAT_ROWS = 400


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _types(df, types=None):
    return types if types is not None else dataset.analysis_var_types(df)


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors='coerce').dropna()


def _short(name, n=40):
    return dataset.readable(name, n)


def _fr(x, nd=1):
    return f'{x:.{nd}f}'.replace('.', ',')


def _option_parent(col):
    """Question à laquelle appartient une case de choix multiple (« Question__X/option » → « Question__X ») ; None sinon."""
    text = str(col)
    if '/' not in text:
        return None
    parent, option = text.rsplit('/', 1)
    from modules.phakts_codes import affix_of
    if not option:
        return None
    if affix_of(parent) in ('X', 'SRC'):
        return parent
    # question à cases dont le suffixe n'est pas « X » (…Lesquels__Z/option) : un nom de groupe n'a pas de suffixe « __ »
    return parent if '__' in parent.rsplit('/', 1)[-1] else None


def _present(series):
    return series.notna() & (series.astype(str).str.strip() != '')


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


def _normality(series: pd.Series):
    """(libellé, classe de badge, p, test) — un vrai test (Shapiro-Wilk, D'Agostino au-delà de 5 000), pas un jugement sur
    l'asymétrie seule ; l'asymétrie précise seulement le sens de l'écart."""
    n = len(series)
    if n < 8 or series.nunique() < 3:
        return 'Effectif trop faible pour juger', 'badge-warn', None, ''
    if n <= 5000:
        _, p = stats.shapiro(series)
        test = 'Shapiro-Wilk'
    else:
        _, p = stats.normaltest(series)
        test = "D'Agostino-Pearson"
    skew = float(series.skew())
    if p > 0.05:
        return 'Compatible avec une loi normale', 'badge-normal', float(p), test
    if skew > 1:
        return 'Non normale : asymétrie positive forte', 'badge-skew-right', float(p), test
    if skew < -1:
        return 'Non normale : asymétrie négative forte', 'badge-skew-left', float(p), test
    return 'Non normale', 'badge-skew-light', float(p), test


def _shannon_entropy(series: pd.Series) -> float:
    counts = series.value_counts(normalize=True)
    return round(-float((counts * np.log2(counts + 1e-10)).sum()), 3)


def _herfindahl(series: pd.Series) -> float:
    props = series.value_counts(normalize=True)
    return round(float((props ** 2).sum()), 3)


# ══════════════════════════════════════════════════════════════════════════════
# MANQUANTS : RÉELS OU STRUCTURELS
# ══════════════════════════════════════════════════════════════════════════════

def _form_columns(df):
    out = {}
    for col in df.columns:
        out.setdefault(str(col).split('/')[-1].split('!')[0], col)
    return out


def missing_profile(df, form=None, types=None) -> dict:
    """Pour chaque variable : manquants bruts, effectif auquel la question s'appliquait, manquants parmi eux (les vrais manques) et
    verdict. Une question dont le « relevant » est faux n'a pas à être répondue ; sans formulaire, un champ « Autre, précisez » est
    présumé structurel. Les variables techniques sont ignorées."""
    types = _types(df, types)
    cols = _form_columns(df)
    questions = {q['name']: q for q in (form or {}).get('questions', [])}
    index = pd.RangeIndex(len(df))
    positions = df.reset_index(drop=True)

    def resolve(name):
        c = cols.get(name)
        return positions[c] if c is not None else None

    rows, skipped = [], 0
    real_missing = applicable_total = 0
    seen_groups = {parent for parent in map(_option_parent, df.columns) if parent in df.columns}       # la colonne-question, quand elle existe, représente déjà ses cases
    for col in df.columns:
        if types.get(col) == 'technique':
            continue
        present = _present(df[col]).reset_index(drop=True)
        n_miss = int((~present).sum())
        q = questions.get(str(col).split('/')[-1].split('!')[0])
        applicable, reason, assumed = None, '', False
        if q and q.get('relevant'):
            try:
                applicable = xlsform_expr.evaluate(q['relevant'], resolve, index)
                reason = f"posée si {q['relevant']}"
            except xlsform_expr.Unsupported:
                skipped += 1
        if applicable is None and not (q and not q.get('relevant')) and _STRUCTURAL_NAME.search(str(col).split('/')[-1]) and n_miss / max(len(df), 1) > 0.3:
            assumed, reason = True, 'champ « Autre / précisez » : vide tant que le choix correspondant n\'est pas fait (présumé)'
        if applicable is None:
            applicable = pd.Series(True, index=index)
        n_app = int(applicable.sum())
        miss_app = int((applicable & ~present).sum())
        structural = int((~applicable & ~present).sum())
        pct_app = round(miss_app / n_app * 100, 1) if n_app and not assumed else None
        if assumed:
            verdict = 'structurel (présumé)'
        elif n_miss == 0:
            verdict = 'complet'
        elif miss_app == 0:
            verdict = 'structurel'
        elif pct_app is not None and pct_app >= MISSING_HIGH:
            verdict = 'manque élevé'
        elif pct_app is not None and pct_app >= MISSING_MODERATE:
            verdict = 'manque modéré'
        else:
            verdict = 'manque faible'
        parent = _option_parent(col)
        head = parent is None or parent not in seen_groups
        if parent:
            seen_groups.add(parent)
        if not assumed and head:
            real_missing += miss_app
            applicable_total += n_app
        rows.append({'variable': col, 'n_missing': n_miss, 'pct_missing': round(n_miss / len(df) * 100, 1) if len(df) else 0,
                     'n_applicable': n_app, 'n_missing_applicable': miss_app, 'pct_missing_applicable': pct_app,
                     'n_structural': structural, 'verdict': verdict, 'reason': reason, 'assumed': assumed,
                     'group': parent, 'group_head': head})
    real_pct = round(real_missing / applicable_total * 100, 1) if applicable_total else 0.0
    raw_total = sum(r['n_missing'] for r in rows)
    cells = len(df) * len(rows)
    return {'rows': rows, 'real_missing_pct': real_pct, 'raw_missing_pct': round(raw_total / cells * 100, 1) if cells else 0.0,
            'n_structural_vars': sum(1 for r in rows if r['verdict'].startswith('structurel')), 'unreadable_rules': skipped,
            'with_form': bool(questions)}


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSE DESCRIPTIVE (rapports)
# ══════════════════════════════════════════════════════════════════════════════

def descriptive_summary(df: pd.DataFrame, types=None) -> dict:
    var_types = _types(df, types)
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
        t_crit  = float(stats.t.ppf(0.975, n_valid - 1))                      # Student : IC juste pour de petits effectifs
        ci95_lo = round(mean_ - t_crit * sem_, 3)
        ci95_hi = round(mean_ + t_crit * sem_, 3)
        outliers = detect_outliers_iqr(df[var])
        norm_label, norm_badge, norm_p, norm_test = _normality(num)

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

        fig_hist = go.Figure()
        fig_hist.add_trace(go.Histogram(
            x=num, nbinsx=min(30, max(5, int(np.sqrt(n_valid)))),
            name='Effectif', marker_color=BLUE, opacity=0.75,
            histnorm='probability density',
        ))
        if std_ > 0:
            x_range = np.linspace(mn - std_, mx + std_, 200)
            kde_y   = (1 / (std_ * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_range - mean_) / std_) ** 2)
            fig_hist.add_trace(go.Scatter(
                x=x_range, y=kde_y, mode='lines',
                line=dict(color=ORANGE, width=2.5, dash='solid'),
                name='Loi normale de mêmes moyenne et écart-type',
            ))
        fig_hist.add_vline(x=mean_,  line=dict(color=RED,  width=1.5, dash='dash'), annotation_text='Moy', annotation_position='top right')
        fig_hist.add_vline(x=med_,   line=dict(color=TEAL, width=1.5, dash='dot'),  annotation_text='Méd', annotation_position='top left')
        fig_hist.update_layout(
            **LAYOUT,
            title=f'Distribution — <b>{_short(var)}</b>',
            xaxis_title=_short(var), yaxis_title='Densité',
            height=300, showlegend=True,
            legend=dict(orientation='h', y=-0.25, x=0),
        )

        fig_box = make_subplots(rows=1, cols=2, subplot_titles=['Boîte à moustaches', 'Violin'])
        fig_box.add_trace(go.Box(
            y=num, name=_short(var), marker_color=TEAL,
            boxmean='sd', boxpoints='outliers', jitter=0.3,
            line=dict(color=NAVY, width=1.5),
        ), row=1, col=1)
        fig_box.add_trace(go.Violin(
            y=num, name=_short(var), fillcolor='rgba(23,165,137,0.25)',
            line_color=TEAL, meanline_visible=True,
            box_visible=True, points=False,
        ), row=1, col=2)
        fig_box.update_layout(
            **LAYOUT,
            height=300, showlegend=False,
            title=f'Dispersion — <b>{_short(var)}</b>',
        )

        results['continuous'].append({
            'var':        var,
            'stats':      stats_dict,
            'outliers':   outliers,
            'norm_label': norm_label,
            'norm_badge': norm_badge,
            'norm_p':     norm_p,
            'norm_test':  norm_test,
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
            title=f'Distribution — <b>{_short(var)}</b>',
            xaxis=dict(title='Fréquence (%)', range=[0, max(pct) * 1.2]),
            yaxis=dict(autorange='reversed'),
            height=max(280, 32 * top_n + 80),
        )

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
            title=f'Répartition — <b>{_short(var)}</b>',
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

        text = series.astype(str).str.strip()
        text = text.map(lambda v: v[:-2] if re.fullmatch(r'-?\d+\.0', v) else v)
        counts = text.value_counts()
        display = {v: ('Oui (1)' if v == '1' else 'Non (0)' if v == '0' else v) for v in counts.index}
        positive = next((v for v in counts.index if v.lower() in POSITIVE_VALUES), None)       # la prévalence est celle du « oui »

        pct = (counts.values / n_valid * 100).round(1)
        freq_df = pd.DataFrame({
            'Modalité':      [display[v] for v in counts.index],
            'Effectif':      counts.values,
            'Fréquence (%)': pct,
        })
        prevalence = round(float(counts[positive] / n_valid * 100), 1) if positive is not None else None

        fig_bar = go.Figure()
        for v, eff, p in zip(counts.index, counts.values, pct):
            fig_bar.add_trace(go.Bar(
                x=[display[v]], y=[p],
                text=[f'{p}%'],
                textposition='outside',
                marker_color=TEAL if v == positive else '#BFC9CA',
                name=display[v],
            ))
        fig_bar.update_layout(
            **LAYOUT,
            title=f'Proportion — <b>{_short(var)}</b>',
            yaxis=dict(title='Fréquence (%)', range=[0, 115]),
            height=280, showlegend=False,
            barmode='group',
        )

        fig_gauge = None
        if prevalence is not None:
            fig_gauge = go.Figure(go.Indicator(
                mode='gauge+number',
                value=prevalence,
                number={'suffix': '%', 'font': {'size': 28, 'color': NAVY}},
                gauge={
                    'axis': {'range': [0, 100], 'ticksuffix': '%'},
                    'bar': {'color': TEAL},
                    'steps': [
                        {'range': [0,  25],  'color': '#FDFEFE'},
                        {'range': [25, 75],  'color': '#EBF5FB'},
                        {'range': [75, 100], 'color': '#D6EAF8'},
                    ],
                    'threshold': {'line': {'color': NAVY, 'width': 3}, 'thickness': 0.8, 'value': 50},
                },
                title={'text': f'Prévalence — {display[positive]}', 'font': {'size': 13}},
            ))
            fig_gauge.update_layout(height=220, margin=dict(l=30, r=30, t=60, b=20), font=FONT, paper_bgcolor='white')

        results['binary'].append({
            'variable':  var,
            'n_missing': n_miss,
            'pct_missing': round(n_miss / len(df[var]) * 100, 1),
            'n_valid':   n_valid,
            'table':     freq_df.to_html(classes='table table-sm table-hover mb-0', border=0, index=False),
            'chart':     fig_bar.to_json(engine='json'),
            'chart_gauge': fig_gauge.to_json(engine='json') if fig_gauge is not None else None,
            'prevalence': prevalence,
            'label_pos':  display[positive] if positive is not None else '—',
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# VUE D'ENSEMBLE
# ══════════════════════════════════════════════════════════════════════════════

def overview_stats(df: pd.DataFrame, types=None) -> dict:
    var_types = _types(df, types)
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
        if typ in ('categorielle', 'binaire', 'identifiant'):
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


def variable_profile(df, shown, types, labels=None, profile=None):
    """Une ligne par variable pour la table du diagnostic : type, effectif, manquants (réels), modalités ou moyenne, alertes.
    `shown` : le même jeu avec les modalités sous leur libellé (pour afficher le mode)."""
    labels = labels or {}
    by_var = {r['variable']: r for r in (profile or {}).get('rows', [])}
    out = []
    for col in df.columns:
        typ = types.get(col, '?')
        if typ == 'technique':
            continue
        s, sh = df[col], shown[col]
        miss = by_var.get(col, {})
        row = {'variable': col, 'label': labels.get(col) or _short(col, 60), 'type': typ, 'n_valid': int(_present(s).sum()),
               'pct_missing': miss.get('pct_missing', round(float(s.isna().mean() * 100), 1)),
               'pct_real': miss.get('pct_missing_applicable'), 'verdict': miss.get('verdict', ''), 'summary': '', 'alerts': []}
        if typ in ('categorielle', 'binaire', 'identifiant'):
            counts = sh.dropna().astype(str).value_counts()
            row['distinct'] = int(len(counts))
            if len(counts):
                row['summary'] = f"« {counts.index[0]} » {counts.iloc[0] / counts.sum() * 100:.0f} %".replace('.', ',')
                if len(counts) == 1:
                    row['alerts'].append('une seule modalité')
                elif counts.iloc[0] / counts.sum() > 0.95 and typ != 'identifiant':
                    row['alerts'].append('déséquilibre extrême')
                if (counts == 1).sum() > max(5, len(df) / 3) and typ == 'categorielle':
                    row['alerts'].append('modalités uniques nombreuses')
        elif typ == 'continue':
            num = _safe_num(s)
            if len(num):
                row['distinct'] = int(num.nunique())
                row['summary'] = f"{num.mean():.1f} ± {num.std():.1f} (méd. {num.median():.1f})".replace('.', ',')
                if num.std() == 0:
                    row['alerts'].append('variance nulle')
                out_ = detect_outliers_iqr(s)
                if out_['pct'] > 10:
                    row['alerts'].append(f"{out_['pct']} % de valeurs aberrantes".replace('.', ','))
        elif typ == 'date':
            dates = pd.to_datetime(s, errors='coerce').dropna()
            if len(dates):
                row['summary'] = f"{dates.min():%d/%m/%Y} → {dates.max():%d/%m/%Y}"
        else:
            row['distinct'] = int(s.nunique())
        if row['verdict'] in ('manque élevé',):
            row['alerts'].append('manquants élevés')
        if row['pct_missing'] >= MISSING_EMPTY and not row['verdict'].startswith('structurel'):
            row['alerts'].append('presque vide')
        out.append(row)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# QUALITÉ & SCORE
# ══════════════════════════════════════════════════════════════════════════════

def duplicate_rows(df, types=None) -> dict:
    """Soumissions en double : même identifiant technique, ou mêmes réponses sur toutes les variables analytiques."""
    types = _types(df, types)
    analytic = [c for c, t in types.items() if t not in ('technique',) and c in df.columns and df[c].notna().any()]
    n = len(df)
    by_answers = 0
    if len(analytic) >= 8 and n:
        by_answers = int(df[analytic].astype(str).duplicated(keep='first').sum())
    by_id = 0
    for col in ('_uuid', 'meta/instanceID', 'instanceID'):
        if col in df.columns:
            by_id = max(by_id, int(df[col].dropna().duplicated(keep='first').sum()))
    total = max(by_answers, by_id)
    return {'n': total, 'by_answers': by_answers, 'by_id': by_id, 'pct': round(total / n * 100, 1) if n else 0.0}


def data_quality_score(df: pd.DataFrame, types=None, profile=None, validation=None, dupes=None) -> dict:
    """Score sur 100, de quatre mesures que chacun peut vérifier :
       complétude RÉELLE (40) · validité : lignes sans défaut de collecte à la validation (30) · unicité (15) · variables exploitables (15).
       Une mesure indisponible (pas de validation faite) est écartée et les poids se répartissent sur les autres."""
    n_obs, n_vars = len(df), len(df.columns)
    types = _types(df, types)
    profile = profile or missing_profile(df, None, types)
    dupes = dupes or duplicate_rows(df, types)
    counts = {t: 0 for t in ['categorielle', 'continue', 'binaire', 'date', 'texte_libre', 'identifiant', 'technique']}
    for t in types.values():
        counts[t] = counts.get(t, 0) + 1

    analytic = [r for r in profile['rows'] if types.get(r['variable']) in ('categorielle', 'continue', 'binaire', 'date')]
    usable = 0
    for r in analytic:
        col = df[r['variable']]
        constant = col.dropna().nunique() <= 1
        empty = (r['pct_missing_applicable'] or 0) > MISSING_EMPTY
        usable += 0 if (constant or empty) else 1
    usable_pct = round(usable / len(analytic) * 100, 1) if analytic else 100.0

    components = [
        {'name': 'Complétude réelle', 'value': round(100 - profile['real_missing_pct'], 1), 'weight': 40,
         'detail': f"{_fr(profile['real_missing_pct'])} % de réponses manquantes parmi les questions applicables"
                   + (f" ({profile['n_structural_vars']} variable(s) vides par construction écartées)" if profile['n_structural_vars'] else '')},
        {'name': 'Unicité', 'value': round(100 - dupes['pct'], 1), 'weight': 15,
         'detail': f"{dupes['n']} soumission(s) en double sur {n_obs}"},
        {'name': 'Variables exploitables', 'value': usable_pct, 'weight': 15,
         'detail': f"{usable} variable(s) sur {len(analytic)} ni constantes ni quasi vides"},
    ]
    if validation is not None:
        components.insert(1, {'name': 'Validité', 'value': validation['pct_sans_anomalie'], 'weight': 30,
                              'detail': f"{validation['n_signalees']} ligne(s) signalée(s) à la validation, {validation['n_erreurs']} contrôle(s) en erreur"})
    total_weight = sum(c['weight'] for c in components)
    score = round(sum(c['value'] * c['weight'] for c in components) / total_weight)
    label = 'Bonne' if score >= 85 else 'Correcte' if score >= 70 else 'À améliorer' if score >= 50 else 'Faible'
    return {
        'quality_score': score, 'label': label, 'components': components,
        'completeness': round(100 - profile['real_missing_pct'], 1),
        'diversity': counts, 'missing_pct': profile['real_missing_pct'], 'raw_missing_pct': profile['raw_missing_pct'],
        'n_obs': n_obs, 'n_vars': n_vars, 'with_validation': validation is not None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ASSOCIATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _cramers_v_corrected(ct):
    """V de Cramér corrigé du biais (Bergsma) — le V brut est gonflé quand les effectifs sont faibles."""
    obs = ct.values.astype(float)
    n = obs.sum()
    if n < 3 or min(obs.shape) < 2:
        return None, None
    chi2, p, _, _ = stats.chi2_contingency(obs, correction=False)
    phi2 = chi2 / n
    r, k = obs.shape
    phi2c = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    rc, kc = r - (r - 1) ** 2 / (n - 1), k - (k - 1) ** 2 / (n - 1)
    denom = min(kc - 1, rc - 1)
    return (float(np.sqrt(phi2c / denom)) if denom > 0 else 0.0), float(p)


def association_matrix(df: pd.DataFrame, types=None, labels=None, max_vars=MAX_ASSOC_VARS):
    """Associations entre variables catégorielles (V de Cramér corrigé) : carte de chaleur et couples les plus liés, p corrigés
    des tests multiples (Benjamini-Hochberg). None s'il y a moins de deux variables utilisables."""
    from modules.crosstabs import benjamini_hochberg
    types = _types(df, types)
    labels = labels or {}
    sample = df.sample(MAX_ASSOC_ROWS, random_state=1) if len(df) > MAX_ASSOC_ROWS else df
    cands = []
    for col, t in types.items():
        if t != 'categorielle' or col not in sample.columns:
            continue
        s = sample[col].dropna().astype(str)
        if len(s) >= 0.3 * len(sample) and 2 <= s.nunique() <= 15:
            cands.append((len(s), col))
    cols = [c for _, c in sorted(cands, key=lambda x: -x[0])[:max_vars]]
    if len(cols) < 2:
        return None
    names = {c: labels.get(c) or _short(c, 34) for c in cols}
    matrix = pd.DataFrame(np.nan, index=cols, columns=cols)
    pairs = []
    for i, a in enumerate(cols):
        matrix.loc[a, a] = 1.0
        for b in cols[i + 1:]:
            sub = sample[[a, b]].dropna().astype(str)
            if len(sub) < 10:
                continue
            ct = pd.crosstab(sub[a], sub[b])
            if ct.shape[0] < 2 or ct.shape[1] < 2:
                continue
            v, p = _cramers_v_corrected(ct)
            if v is None:
                continue
            matrix.loc[a, b] = matrix.loc[b, a] = v
            pairs.append({'a': a, 'b': b, 'v': round(v, 3), 'p': p, 'n': int(len(sub)), 'redundant': v >= REDUNDANT_V})
    if not pairs:
        return None
    for pair, q in zip(pairs, benjamini_hochberg([p['p'] for p in pairs])):
        pair['q'] = q
    pairs.sort(key=lambda x: -x['v'])
    for pair in pairs:
        pair['label_a'], pair['label_b'] = names[pair['a']], names[pair['b']]
    shown = matrix.rename(index=names, columns=names)
    fig = go.Figure(go.Heatmap(z=shown.values, x=shown.columns.tolist(), y=shown.index.tolist(), colorscale='Blues', zmin=0, zmax=1,
                               hovertemplate='%{y} × %{x}<br>V de Cramér = %{z:.2f}<extra></extra>', colorbar=dict(title='V')))
    fig.update_layout(**{**LAYOUT, 'margin': dict(l=210, r=20, t=60, b=210)}, title='Associations entre variables catégorielles (V de Cramér corrigé)',
                      height=max(420, 22 * len(cols) + 300))
    fig.update_xaxes(tickangle=-60)
    fig.update_yaxes(autorange='reversed')
    return {'chart': fig.to_json(engine='json'), 'pairs': pairs[:15], 'n_vars': len(cols), 'n_pairs': len(pairs),
            'sampled': len(df) > MAX_ASSOC_ROWS}


def correlation_pairs(df: pd.DataFrame, types=None, labels=None):
    """Corrélations de Spearman (robustes aux valeurs extrêmes et aux distributions asymétriques) entre variables CONTINUES,
    avec leur p corrigé. Une variable catégorielle codée en nombres n'en est pas une."""
    from modules.crosstabs import benjamini_hochberg
    types = _types(df, types)
    labels = labels or {}
    cols = [c for c, t in types.items() if t == 'continue' and c in df.columns]
    cols = [c for c in cols if _safe_num(df[c]).nunique() > 3][:25]
    pairs = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            sub = pd.DataFrame({'a': pd.to_numeric(df[a], errors='coerce'), 'b': pd.to_numeric(df[b], errors='coerce')}).dropna()
            if len(sub) < 10 or sub['a'].nunique() < 3 or sub['b'].nunique() < 3:
                continue
            rho, p = stats.spearmanr(sub['a'], sub['b'])
            pairs.append({'a': a, 'b': b, 'rho': round(float(rho), 3), 'p': float(p), 'n': int(len(sub)),
                          'label_a': labels.get(a) or _short(a, 34), 'label_b': labels.get(b) or _short(b, 34)})
    for pair, q in zip(pairs, benjamini_hochberg([p['p'] for p in pairs])):
        pair['q'] = q
    return sorted(pairs, key=lambda x: -abs(x['rho']))


def correlation_matrix(df: pd.DataFrame, types=None):
    """Carte des corrélations de Spearman entre variables continues (JSON Plotly), ou None s'il y en a moins de deux."""
    types = _types(df, types)
    cols = [c for c, t in types.items() if t == 'continue' and c in df.columns and _safe_num(df[c]).nunique() > 3][:25]
    if len(cols) < 2:
        return None
    num_df = df[cols].apply(pd.to_numeric, errors='coerce')
    corr = num_df.corr(method='spearman').round(2)
    names = {c: _short(c, 30) for c in cols}
    corr = corr.rename(index=names, columns=names)
    n = len(corr.columns)
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    corr_masked = corr.copy()
    corr_masked[mask] = np.nan
    text_matrix = corr_masked.map(lambda v: f'{v:.2f}' if not pd.isna(v) else '').values
    fig = go.Figure(go.Heatmap(
        z=corr_masked.values, x=corr.columns.tolist(), y=corr.columns.tolist(),
        colorscale='RdBu_r', zmin=-1, zmax=1, text=text_matrix, texttemplate='%{text}',
        textfont=dict(size=max(8, 12 - n // 4)),
        hovertemplate='%{y} × %{x}<br>rho = %{z:.3f}<extra></extra>',
        colorbar=dict(title='ρ de Spearman', tickvals=[-1, -0.5, 0, 0.5, 1]),
    ))
    fig.update_layout(**{**LAYOUT, 'margin': dict(l=120, r=20, t=70, b=120)},
                      title='Corrélations de Spearman entre variables continues', height=max(400, 40 * n + 120))
    fig.update_xaxes(tickangle=-45, side='bottom')
    return fig.to_json(engine='json')


# ══════════════════════════════════════════════════════════════════════════════
# SYNTHÈSE, ANOMALIES, RECOMMANDATIONS
# ══════════════════════════════════════════════════════════════════════════════

def build_recommendations(types, assoc=None, pairs=None, profile=None, labels=None):
    """Analyses à lancer ensuite, chacune avec le formulaire déjà rempli : les variables viennent des constats ci-dessus."""
    labels = labels or {}
    recs = []
    cat = [c for c, t in types.items() if t == 'categorielle']
    cont = [c for c, t in types.items() if t == 'continue']
    useful = [p for p in (assoc or {}).get('pairs', []) if not p['redundant']]
    if useful:
        top = useful[0]
        if top['v'] >= 0.2 and top['q'] < 0.05:
            recs.append({'type': 'Croiser les deux variables les plus liées', 'module': 'crosstabs', 'variables': [top['a'], top['b']],
                         'rationale': f"« {top['label_a']} » et « {top['label_b']} » sont associées (V de Cramér = {top['v']:.2f}, "
                                      f"{top['n']} observations) : le croisement détaille dans quel sens.".replace('.', ','),
                         'form': {'kind': 'pivot', 'rows': [top['a']], 'cols': [top['b']], 'agg': 'count', 'pct_type': 'row'}})
    if len(cat) >= 3:
        pick = [r['variable'] for r in sorted((r for r in (profile or {}).get('rows', []) if r['variable'] in cat and r['pct_missing'] < 20),
                                              key=lambda r: r['pct_missing'])][:6] or cat[:6]
        recs.append({'type': 'Explorer la structure des réponses (ACM)', 'module': 'multivariate', 'variables': pick,
                     'rationale': f"{len(cat)} variables catégorielles : l'ACM les résume en quelques axes et la classification en dégage des profils.",
                     'form': {'method': 'mca', 'variables': pick, 'n_components': 2}})
    if len(cont) >= 3:
        recs.append({'type': 'Résumer les variables continues (ACP)', 'module': 'multivariate', 'variables': cont[:8],
                     'rationale': f'{len(cont)} variables continues : réduisez-les à quelques axes.',
                     'form': {'method': 'pca', 'variables': cont[:8], 'n_components': 2}})
    if pairs and abs(pairs[0]['rho']) >= 0.3 and pairs[0]['q'] < 0.05:
        p = pairs[0]
        recs.append({'type': 'Étudier la corrélation la plus forte', 'module': 'crosstabs', 'variables': [p['a'], p['b']],
                     'rationale': f"« {p['label_a']} » et « {p['label_b']} » : rho de Spearman = {p['rho']:.2f}.".replace('.', ','), 'form': None})
    if profile and profile['rows']:
        weak = [r['variable'] for r in profile['rows'] if r['verdict'] == 'manque élevé'][:4]
        if weak:
            recs.append({'type': 'Traiter les manquants élevés avant analyse', 'module': 'descriptive', 'variables': weak,
                         'rationale': f"{len(weak)} variable(s) ont plus de {MISSING_HIGH} % de réponses manquantes parmi celles qui devaient répondre : "
                                      "les résultats ne porteront que sur une partie des enquêtés.", 'form': None})
    for rank, rec in enumerate(recs, start=1):
        rec['rank'] = rank
    return recs


def systematic_analysis(df: pd.DataFrame, types=None, form=None, validation=None, labels=None) -> dict:
    var_types  = _types(df, types)
    n_obs, n_vars = len(df), len(df.columns)

    cat_vars  = [c for c, t in var_types.items() if t == 'categorielle']
    num_vars  = [c for c, t in var_types.items() if t == 'continue']
    bin_vars  = [c for c, t in var_types.items() if t == 'binaire']
    date_vars = [c for c, t in var_types.items() if t == 'date']
    text_vars = [c for c, t in var_types.items() if t == 'texte_libre']
    id_vars   = [c for c, t in var_types.items() if t == 'identifiant']

    profile = missing_profile(df, form, var_types)
    by_var = {r['variable']: r for r in profile['rows']}
    miss_by_var = df.isnull().sum().sort_values(ascending=False)
    vars_with_miss = miss_by_var[miss_by_var > 0]
    complete_vars = int((df.isnull().sum() == 0).sum())

    cont_stats = {}
    for var in num_vars:
        num = _safe_num(df[var])
        if len(num) > 0:
            cont_stats[var] = {'mean': round(float(num.mean()), 3), 'median': round(float(num.median()), 3), 'std': round(float(num.std()), 3),
                               'min': round(float(num.min()), 3), 'max': round(float(num.max()), 3), 'skew': round(float(num.skew()), 3),
                               'outliers': detect_outliers_iqr(df[var])}

    cat_card = {}
    for var in cat_vars:
        card = df[var].nunique()
        mode = df[var].mode()
        cat_card[var] = {'n_categories': card, 'dominant': str(mode.iloc[0]) if len(mode) else '—',
                         'dominant_pct': round((df[var] == mode.iloc[0]).sum() / len(df[var]) * 100, 1) if len(mode) > 0 else 0}

    anomalies = []
    for var in num_vars:
        num = _safe_num(df[var])
        if len(num) < 2:
            continue
        if float(num.std()) < 0.001:
            anomalies.append({'type': 'Variance nulle', 'variable': var, 'severity': 'élevé',
                              'note': "La variable ne contient qu'une seule valeur : inutilisable."})
        out = detect_outliers_iqr(df[var])
        if out['pct'] > 10:
            anomalies.append({'type': 'Valeurs aberrantes nombreuses', 'variable': var, 'severity': 'modéré',
                              'note': f"{out['count']} valeurs aberrantes ({_fr(out['pct'])} %) hors de [{_fr(out['lower'])} ; {_fr(out['upper'])}]."})
        sk = float(num.skew())
        if abs(sk) > 2:
            anomalies.append({'type': 'Forte asymétrie', 'variable': var, 'severity': 'faible',
                              'note': f"Asymétrie de {_fr(sk, 2)} : distribution très éloignée de la normale ; préférer la médiane."})

    for var in cat_vars + bin_vars:
        if df[var].dropna().nunique() == 1 and len(df[var].dropna()):
            anomalies.append({'type': 'Variance nulle', 'variable': var, 'severity': 'modéré',
                              'note': "Une seule modalité observée : la variable ne distingue personne."})

    for col, r in by_var.items():
        pct_app = r['pct_missing_applicable']
        if r['assumed'] or r['verdict'] in ('complet', 'structurel') or pct_app is None or not r['group_head']:
            continue
        basis = (f"{r['n_applicable']} personne(s) à qui la question s'appliquait"
                 if r['n_applicable'] < n_obs else 'ensemble des soumissions')
        what = r['group'] or col
        if pct_app > MISSING_EMPTY:
            anomalies.append({'type': 'Colonne presque vide', 'variable': what, 'severity': 'élevé',
                              'note': f"{_fr(pct_app)} % de réponses manquantes ({basis})."})
        elif pct_app > MISSING_HIGH:
            anomalies.append({'type': 'Taux de manquants élevé', 'variable': what, 'severity': 'modéré',
                              'note': f"{_fr(pct_app)} % de réponses manquantes ({basis})."})

    for var in bin_vars:
        counts = df[var].value_counts()
        if len(counts) >= 2:
            pct_dom = max(counts) / counts.sum() * 100
            if pct_dom > 95:
                anomalies.append({'type': 'Déséquilibre extrême', 'variable': var, 'severity': 'modéré',
                                  'note': f"{pct_dom:.1f} % d'une seule modalité : variable peu discriminante.".replace('.', ',')})

    for var in cat_vars:
        counts = df[var].value_counts()
        rare = (counts == 1).sum()
        if rare > n_obs / 3:
            anomalies.append({'type': 'Modalités trop rares', 'variable': var, 'severity': 'faible',
                              'note': f"{rare} modalités avec une seule observation : regroupement conseillé."})

    dupes = duplicate_rows(df, var_types)
    if dupes['n']:
        anomalies.append({'type': 'Soumissions en double', 'variable': '(ensemble du jeu)', 'severity': 'élevé' if dupes['pct'] > 2 else 'modéré',
                          'note': f"{dupes['n']} soumission(s) en double ({_fr(dupes['pct'])} %) : " +
                                  ("même identifiant technique." if dupes['by_id'] >= dupes['by_answers'] else "mêmes réponses sur toutes les variables.")})

    assoc = association_matrix(df, var_types, labels)
    pairs = correlation_pairs(df, var_types, labels)
    quality = data_quality_score(df, var_types, profile, validation, dupes)

    return {
        'profile': {
            'n_obs': n_obs, 'n_vars': n_vars, 'n_continuous': len(num_vars), 'n_categorical': len(cat_vars), 'n_binary': len(bin_vars),
            'n_date': len(date_vars), 'n_text': len(text_vars), 'n_identifier': len(id_vars),
            'complete_vars': complete_vars, 'vars_with_missing': int((df.isnull().sum() > 0).sum()),
        },
        'missing': {
            'total_cells': n_obs * n_vars, 'missing_count': int(df.isnull().sum().sum()),
            'missing_pct': profile['raw_missing_pct'], 'real_missing_pct': profile['real_missing_pct'],
            'vars_with_missing': vars_with_miss.to_dict(), 'complete_variables': complete_vars, 'rows': profile['rows'],
            'with_form': profile['with_form'], 'n_structural_vars': profile['n_structural_vars'], 'unreadable_rules': profile['unreadable_rules'],
        },
        'continuous_stats':   cont_stats,
        'categorical_stats':  cat_card,
        'anomalies':          anomalies,
        'duplicates':         dupes,
        'association':        assoc,
        'correlations':       pairs,
        'recommendations':    build_recommendations(var_types, assoc, pairs, profile, labels),
        'quality':            quality,
    }


# ══════════════════════════════════════════════════════════════════════════════
# GRAPHIQUES GLOBAUX
# ══════════════════════════════════════════════════════════════════════════════

def data_quality_gauge(quality_dict: dict) -> str:
    score = quality_dict.get('quality_score', 0)
    bar_color = TEAL if score >= 75 else ORANGE if score >= 50 else RED
    parts = ' · '.join(f"{c['name']} {c['weight']} %" for c in quality_dict.get('components', []))
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
                {'range': [75, 100], 'color': '#D5F5E3'},
            ],
            'threshold': {'line': {'color': NAVY, 'width': 3}, 'thickness': 0.85, 'value': 70},
        },
        title={'text': f'Score de qualité des données<br><span style="font-size:.7rem;color:{GREY}">{parts}</span>',
               'font': {'size': 13}},
    ))
    fig.update_layout(height=300, font=FONT, paper_bgcolor='white', margin=dict(l=30, r=30, t=90, b=20))
    return fig.to_json(engine='json')


def composition_chart(analysis_dict: dict) -> str:
    diversity = analysis_dict.get('quality', {}).get('diversity', {})
    if not diversity:
        return None
    labels, values, colors_list = [], [], []
    CMAP = {'continue': BLUE, 'categorielle': ORANGE, 'binaire': TEAL, 'date': PURPLE, 'texte_libre': GREY,
            'identifiant': '#5D6D7E', 'technique': '#D5D8DC'}
    LMAP = {'continue': 'Continue', 'categorielle': 'Catégorielle', 'binaire': 'Binaire', 'date': 'Date', 'texte_libre': 'Texte libre',
            'identifiant': 'Identifiant', 'technique': 'Technique'}
    for typ, count in diversity.items():
        if count > 0:
            labels.append(f'{LMAP.get(typ, typ)} ({count})')
            values.append(count)
            colors_list.append(CMAP.get(typ, GREY))
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors_list, line=dict(color='white', width=3)),
        hole=0.45, textinfo='label+percent', textfont=dict(size=11), pull=[0.03] * len(labels),
    ))
    fig.update_layout(title='Composition des variables par type', height=300, font=FONT, paper_bgcolor='white',
                      showlegend=False, margin=dict(l=20, r=20, t=50, b=20))
    return fig.to_json(engine='json')


def distributions_chart(df: pd.DataFrame, types=None) -> str:
    var_types = _types(df, types)
    num_vars  = [c for c, t in var_types.items() if t == 'continue']
    if not num_vars:
        return None
    num_vars_d = num_vars[:6]
    n_plots    = len(num_vars_d)
    n_cols     = 2
    n_rows     = (n_plots + 1) // n_cols
    fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=[f'<b>{_short(v, 36)}</b>' for v in num_vars_d])
    for i, var in enumerate(num_vars_d):
        r, c = (i // n_cols) + 1, (i % n_cols) + 1
        num  = _safe_num(df[var])
        if len(num) < 2:
            continue
        fig.add_trace(go.Histogram(x=num, nbinsx=min(25, max(5, int(np.sqrt(len(num))))), name=var,
                                   marker_color=BLUE, opacity=0.75, showlegend=False), row=r, col=c)
        fig.add_vline(x=float(num.mean()), line=dict(color=RED, width=1.5, dash='dash'), row=r, col=c)
    fig.update_layout(title_text=f'Distributions des variables continues ({n_plots}/{len(num_vars)})', height=max(350, 260 * n_rows),
                      plot_bgcolor='white', paper_bgcolor='white', font=FONT, showlegend=False, margin=dict(t=70, b=40, l=40, r=20))
    for ax in fig.layout:
        if ax.startswith('xaxis') or ax.startswith('yaxis'):
            fig.layout[ax].update(showgrid=True, gridcolor='#F0F0F0')
    return fig.to_json(engine='json')


def missing_bar_chart(df: pd.DataFrame, profile=None):
    """Manquants par variable. Avec le profil : manquants RÉELS (parmi ceux qui devaient répondre) ; les variables vides par
    construction n'y figurent pas."""
    if profile:
        rows = [r for r in profile['rows'] if r['pct_missing_applicable'] and not r['assumed'] and r.get('group_head', True)]
        miss_pct = pd.DataFrame({'Variable': [_short(r.get('group') or r['variable'], 44) for r in rows],
                                 '% manquant': [r['pct_missing_applicable'] for r in rows]})
        title = 'Réponses manquantes parmi les personnes concernées (par variable)'
    else:
        miss_pct = (df.isnull().mean() * 100).round(1).reset_index()
        miss_pct.columns = ['Variable', '% manquant']
        title = 'Taux de données manquantes par variable'
    miss_pct = miss_pct[miss_pct['% manquant'] > 0].sort_values('% manquant', ascending=False).head(40).sort_values('% manquant', ascending=True)
    if miss_pct.empty:
        return None
    miss_pct['Couleur'] = miss_pct['% manquant'].apply(lambda x: RED if x > MISSING_HIGH else ORANGE if x > MISSING_MODERATE else BLUE)
    fig = go.Figure(go.Bar(x=miss_pct['% manquant'], y=miss_pct['Variable'], orientation='h',
                           text=[f'{v}%' for v in miss_pct['% manquant']], textposition='outside',
                           marker=dict(color=miss_pct['Couleur'])))
    fig.update_layout(**{**LAYOUT, 'margin': dict(l=230, r=80, t=60, b=40)}, title=title,
                      xaxis=dict(title='% manquant', range=[0, 115]), height=max(300, 28 * len(miss_pct) + 100))
    return fig.to_json(engine='json')


def missing_heatmap(df: pd.DataFrame):
    sample = df if len(df) <= MAX_HEAT_ROWS else df.iloc[np.linspace(0, len(df) - 1, MAX_HEAT_ROWS).astype(int)]
    miss = sample.isnull().astype(int)
    if miss.shape[1] > 40:
        top_cols = df.isnull().sum().sort_values(ascending=False).head(40).index.tolist()
        miss = miss[top_cols]
    miss = miss.rename(columns={c: _short(c, 40) for c in miss.columns})
    fig = px.imshow(miss.T, color_continuous_scale=['#EBF5FB', RED],
                    labels=dict(x='Observation', y='Variable', color='Manquant'), aspect='auto')
    fig.update_coloraxes(showscale=True, colorbar=dict(title='Manquant', tickvals=[0, 1], ticktext=['Présent', 'Absent']))
    fig.update_layout(**{**LAYOUT, 'margin': dict(l=230, r=60, t=70, b=40)},
                      title='Carte des données manquantes (rouge = absent)' + (f' — {MAX_HEAT_ROWS} lignes réparties sur le jeu' if len(df) > MAX_HEAT_ROWS else ''),
                      height=max(300, 20 * len(miss.columns) + 120))
    fig.update_xaxes(showticklabels=False)
    return fig.to_json(engine='json')
