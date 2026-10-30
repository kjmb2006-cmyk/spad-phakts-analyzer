"""
SPAD Analyzer — Analyses multivariées (ACP, ACM, AFC, classification)

Chaque méthode renvoie des tableaux HTML et des graphiques (JSON Plotly), mais aussi les
tableaux bruts (`tables`) pour l'export Excel et, pour la classification, l'appartenance de
chaque individu (`class_index`, `class_labels`) afin de l'enregistrer comme variable.

Conventions (celles de l'analyse des données à la française) :
  - ACP sur variables centrées-réduites ; « saturations » = corrélations variable-axe
    (vecteur propre × racine de la valeur propre), contributions et cos² ;
  - ACM = AFC du tableau disjonctif complet ; valeurs propres brutes et taux modifiés de
    Benzécri (les inerties brutes sous-estiment l'information portée par les premiers axes) ;
  - AFC : coordonnées principales (les modalités rares s'éloignent du centre) ;
  - classification : K-Means ou classification hiérarchique (Ward), sur variables numériques
    ou, pour des variables catégorielles, sur les axes de l'ACM. Les classes sont décrites par
    leurs valeurs-tests.
"""
import warnings

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats
from scipy.cluster import hierarchy
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')

PLOT_MAX_POINTS = 3000          # individus tracés (échantillon au-delà)
SIL_SAMPLE = 2000               # silhouette calculée sur un échantillon (sinon O(n²))
CAH_MAX = 3000                  # Ward exact jusqu'ici ; au-delà, sur un échantillon puis affectation
MODALITIES_SHOWN = 40           # modalités nommées sur le plan de l'ACM
MAX_TABLE_ROWS = 60
MAX_RADAR_VARS = 12
PALETTE = px.colors.qualitative.Set2
BLUE, ORANGE, GREEN = '#1a6fa8', '#e05c1a', '#198754'
RNG_SEED = 42


# ─── Choix automatique de variables ──────────────────────────────────────────

def select_viable_variables(df: pd.DataFrame, candidates: list, min_rows: int = 10,
                             min_vars: int = 2, numeric: bool = True) -> list:
    """Choisit un sous-ensemble de `candidates` utilisable pour une ACP/ACM
    sans intervention de l'utilisateur : PCA/MCA font un dropna() conjoint
    sur toutes les variables sélectionnées, donc combiner des variables
    mutuellement exclusives par logique de saut (ex. « âge calculé » vs
    « âge saisi », remplies l'une XOR l'autre selon une réponse en amont)
    peut faire tomber le nombre de lignes conjointement renseignées à zéro,
    même si chaque variable prise séparément est bien remplie.

    Ajoute les variables une à une, des plus complètes aux moins complètes,
    en écartant celles qui feraient chuter le nombre de lignes exploitables
    sous `min_rows` — un choix par défaut robuste plutôt qu'un simple "tout
    sélectionner" qui échoue silencieusement sur ce genre de formulaire."""
    candidates = [v for v in candidates if v in df.columns]
    if len(candidates) < min_vars:
        return candidates

    def _n_complete(vars_):
        sub = df[vars_]
        if numeric:
            sub = sub.apply(pd.to_numeric, errors='coerce')
        return sub.dropna().shape[0]

    ordered = sorted(candidates, key=lambda v: df[v].notna().sum(), reverse=True)
    chosen = [ordered[0]]
    for v in ordered[1:]:
        trial = chosen + [v]
        if _n_complete(trial) >= min_rows:
            chosen = trial
    return chosen if len(chosen) >= min_vars else ordered[:min_vars]


# ─── Utilitaires ─────────────────────────────────────────────────────────────

def _html(df, index=True):
    return df.to_html(classes='table table-sm table-bordered text-center', border=0, index=index, na_rep='—')


def _short(name, n=28):
    from modules.dataset import readable
    return readable(name, n)


def _layout(fig, height=420, **extra):
    fig.update_layout(height=height, plot_bgcolor='white', paper_bgcolor='white',
                      font=dict(family='Inter, sans-serif'), **extra)
    return fig


def _empty_fig(message):
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(size=13, color='#6c757d'))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _layout(fig, 220)


def _json(fig):
    return fig.to_json(engine='json')


def _prepare_numeric_df(df: pd.DataFrame, variables: list):
    """Sous-tableau numérique complet. Les variables constantes (variance nulle) n'apportent
    rien et font échouer la corrélation : elles sont écartées et signalées."""
    sub = df[variables].copy()
    for var in variables:
        sub[var] = pd.to_numeric(sub[var], errors='coerce')
    sub = sub.dropna()
    if sub.shape[0] < 3:
        raise ValueError('Les variables sélectionnées contiennent trop de valeurs manquantes ou pas assez de lignes valides.')
    constant = [c for c in sub.columns if sub[c].std(ddof=1) == 0 or pd.isna(sub[c].std(ddof=1))]
    if constant:
        sub = sub.drop(columns=constant)
    if sub.shape[1] < 2:
        raise ValueError('Sélectionnez au moins deux variables numériques non constantes pour cette analyse.')
    return sub, constant


def _line_numbers(index):
    """Numéros de ligne (1 = première soumission) d'un index positionnel du jeu de données."""
    return [int(i) + 1 for i in index]


def _sample_positions(n, limit=PLOT_MAX_POINTS):
    if n <= limit:
        return np.arange(n)
    return np.sort(np.random.default_rng(RNG_SEED).choice(n, limit, replace=False))


# ─── ACP ─────────────────────────────────────────────────────────────────────

def _kmo_bartlett(R, n):
    """Adéquation des données à une ACP : indice KMO et test de sphéricité de Bartlett."""
    out = {'kmo': None, 'bartlett_p': None}
    p = R.shape[0]
    try:
        det = np.linalg.det(R)
        if det > 0:
            chi2 = -(n - 1 - (2 * p + 5) / 6) * np.log(det)
            out['bartlett_p'] = float(stats.chi2.sf(chi2, p * (p - 1) / 2))
        inv = np.linalg.inv(R)
        d = np.sqrt(np.outer(np.diag(inv), np.diag(inv)))
        partial = -inv / d
        off = ~np.eye(p, dtype=bool)
        r2, q2 = (R[off] ** 2).sum(), (partial[off] ** 2).sum()
        out['kmo'] = float(r2 / (r2 + q2)) if (r2 + q2) else None
    except np.linalg.LinAlgError:
        pass
    return out


def _kmo_label(kmo):
    if kmo is None:
        return ''
    return ('inadéquat' if kmo < 0.5 else 'médiocre' if kmo < 0.6 else 'moyen' if kmo < 0.7
            else 'bon' if kmo < 0.8 else 'très bon' if kmo < 0.9 else 'excellent')


def run_pca(df: pd.DataFrame, variables: list, n_components: int = 2) -> dict:
    sub, constant = _prepare_numeric_df(df, variables)
    variables = list(sub.columns)
    n, p = sub.shape
    Z = ((sub - sub.mean()) / sub.std(ddof=1)).values
    R = np.corrcoef(Z, rowvar=False)
    eigval, eigvec = np.linalg.eigh(R)
    order = np.argsort(eigval)[::-1]
    eigval, eigvec = np.clip(eigval[order], 0, None), eigvec[:, order]
    flip = np.where(eigvec.sum(axis=0) < 0, -1.0, 1.0)         # signe stable : saturations plutôt positives
    eigvec = eigvec * flip
    n_comp = max(1, min(int(n_components), p))

    explained = eigval / p * 100
    cumulative = np.cumsum(explained)
    load = eigvec * np.sqrt(eigval)                              # corrélation variable-axe
    ctr_var = np.divide(load ** 2, eigval, out=np.zeros_like(load), where=eigval > 1e-12) * 100
    scores_all = Z @ eigvec                                      # n × p
    scores = scores_all[:, :n_comp]
    ctr_ind = np.divide(scores_all ** 2, (n - 1) * eigval, out=np.zeros_like(scores_all), where=eigval > 1e-12) * 100
    d2 = (scores_all ** 2).sum(axis=1)
    cos_ind = np.divide(scores_all ** 2, d2[:, None], out=np.zeros_like(scores_all), where=d2[:, None] > 0)

    n_kaiser = int((eigval > 1 + 1e-9).sum())
    n_80 = int(np.searchsorted(cumulative, 80) + 1)
    n_suggested = max(2, min(n_kaiser, p)) if n_kaiser else 2
    adequacy = _kmo_bartlett(R, n)

    axes = [f'F{i + 1}' for i in range(p)]
    eig_df = pd.DataFrame({
        'Composante': axes[:p], 'Valeur propre': eigval.round(3),
        'Variance expliquée (%)': explained.round(2), 'Variance cumulée (%)': cumulative.round(2),
        'Kaiser (λ > 1)': ['oui' if v > 1 + 1e-9 else '' for v in eigval]}).head(max(n_comp, min(p, 8)))

    var_cols = {}
    for k in range(n_comp):
        var_cols[f'Corr. F{k + 1}'] = load[:, k].round(3)
        var_cols[f'Contrib. F{k + 1} (%)'] = ctr_var[:, k].round(1)
    var_cols[f'Qualité (cos² F1-F{n_comp})'] = (load[:, :n_comp] ** 2).sum(axis=1).round(3)
    var_df = pd.DataFrame(var_cols, index=variables)
    loadings = pd.DataFrame(load[:, :n_comp], index=variables, columns=axes[:n_comp]).round(3)

    # Individus : ceux qui pèsent le plus sur les deux premiers axes (souvent des valeurs à vérifier)
    lines = _line_numbers(sub.index)
    ind_df = pd.DataFrame({'N° ligne': lines})
    for k in range(min(n_comp, 2)):
        ind_df[f'F{k + 1}'] = scores_all[:, k].round(2)
        ind_df[f'Contrib. F{k + 1} (%)'] = ctr_ind[:, k].round(2)
    ind_df['cos² (F1-F2)'] = cos_ind[:, :min(n_comp, 2)].sum(axis=1).round(3)
    top_ind = ind_df.sort_values(f'Contrib. F1 (%)', ascending=False).head(10)

    # Éboulis
    fig_scree = go.Figure()
    fig_scree.add_trace(go.Bar(x=axes, y=explained.round(2), name='Variance (%)', marker_color=BLUE))
    fig_scree.add_trace(go.Scatter(x=axes, y=cumulative.round(2), name='Cumulée (%)', mode='lines+markers',
                                   marker_color=ORANGE, line=dict(width=2)))
    fig_scree.add_hline(y=100 / p, line_dash='dash', line_color=GREEN, annotation_text='Kaiser (λ = 1)',
                        annotation_position='top right')
    fig_scree.add_hline(y=80, line_dash='dot', line_color='gray', annotation_text='80 %', annotation_position='right')
    _layout(fig_scree, 380, title='Éboulis des valeurs propres', yaxis_title='Variance expliquée (%)',
            margin=dict(t=90), legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5))

    if n_comp >= 2:
        pos = _sample_positions(n)
        sc = pd.DataFrame(scores[pos, :2], columns=['F1', 'F2'])
        fig_biplot = px.scatter(sc, x='F1', y='F2', color_discrete_sequence=[BLUE], opacity=0.55,
                                title=f'Nuage des individus (F1 × F2){" — échantillon de %d" % len(pos) if len(pos) < n else ""}')
        scale = max(sc['F1'].abs().max(), sc['F2'].abs().max()) * 0.6
        for i, var in enumerate(variables):
            fig_biplot.add_annotation(x=load[i, 0] * scale, y=load[i, 1] * scale, ax=0, ay=0, text=_short(var),
                                      font=dict(size=10, color=ORANGE), arrowhead=2, arrowcolor=ORANGE, arrowwidth=1.5)
        fig_biplot.add_hline(y=0, line_dash='dash', line_color='#ccc')
        fig_biplot.add_vline(x=0, line_dash='dash', line_color='#ccc')
        fig_biplot.update_xaxes(title=f'F1 ({explained[0]:.1f} %)')
        fig_biplot.update_yaxes(title=f'F2 ({explained[1]:.1f} %)')
        _layout(fig_biplot, 440)

        theta = np.linspace(0, 2 * np.pi, 100)
        fig_circle = go.Figure()
        fig_circle.add_trace(go.Scatter(x=np.cos(theta), y=np.sin(theta), mode='lines', line=dict(color='#ccc'), showlegend=False))
        for i, var in enumerate(variables):
            fig_circle.add_annotation(x=load[i, 0], y=load[i, 1], ax=0, ay=0, text=_short(var), font=dict(size=10, color=BLUE),
                                      arrowhead=2, arrowcolor=BLUE, arrowwidth=2)
            fig_circle.add_trace(go.Scatter(x=[load[i, 0]], y=[load[i, 1]], mode='markers', marker=dict(size=8, color=ORANGE),
                                            showlegend=False, hovertemplate=f'{variables[i]}<br>F1 %{{x:.2f}} · F2 %{{y:.2f}}<extra></extra>'))
        fig_circle.add_hline(y=0, line_color='#ddd')
        fig_circle.add_vline(x=0, line_color='#ddd')
        _layout(fig_circle, 440, title='Cercle des corrélations (F1 × F2)',
                xaxis=dict(range=[-1.1, 1.1], title=f'F1 ({explained[0]:.1f} %)'),
                yaxis=dict(range=[-1.1, 1.1], scaleanchor='x', title=f'F2 ({explained[1]:.1f} %)'))
    else:
        fig_biplot = _empty_fig('Une seule composante demandée : choisissez au moins 2 axes pour le plan factoriel.')
        fig_circle = _empty_fig('Une seule composante demandée : choisissez au moins 2 axes pour le cercle des corrélations.')

    scores_df = pd.DataFrame(scores, index=lines, columns=axes[:n_comp])
    scores_df.index.name = 'N° ligne'
    return {
        'method': 'ACP', 'n_obs': n, 'n_vars': p, 'variables': variables, 'dropped_constant': constant,
        'n_components': n_comp, 'eigenvalues': eigval.round(4).tolist(), 'inertia': [round(e, 2) for e in explained.tolist()],
        'cumulative': [round(c, 2) for c in cumulative.tolist()],
        'n_kaiser': n_kaiser, 'n_80': n_80, 'n_suggested': n_suggested, 'kmo': adequacy['kmo'], 'kmo_label': _kmo_label(adequacy['kmo']),
        'bartlett_p': adequacy['bartlett_p'],
        'loadings': loadings, 'var_table_df': var_df,
        'eig_table': _html(eig_df, index=False), 'loadings_table': _html(loadings),
        'var_table': _html(var_df), 'ind_table': _html(top_ind, index=False),
        'chart_scree': _json(fig_scree), 'chart_biplot': _json(fig_biplot), 'chart_circle': _json(fig_circle),
        'tables': {'Valeurs propres': eig_df, 'Variables (corr. et contrib.)': var_df.reset_index(names='Variable'),
                   'Individus (coordonnées)': ind_df},
        'scores': scores_df,
    }


# ─── ACM ─────────────────────────────────────────────────────────────────────

def _indicator_matrix(sub, variables):
    blocks, var_of, mod_of, skipped = [], [], [], []
    for v in variables:
        cat = sub[v].astype('category')
        if len(cat.cat.categories) < 2:
            skipped.append(v)
            continue
        blocks.append(pd.get_dummies(cat).values.astype(float))
        for m in cat.cat.categories:
            var_of.append(v)
            mod_of.append(str(m))
    return blocks, var_of, mod_of, skipped


def mca_core(df, variables, n_axes=None):
    """AFC du tableau disjonctif complet. Renvoie un dictionnaire de tableaux numpy et d'étiquettes ; sert à
    l'ACM elle-même et à la classification des variables catégorielles."""
    sub = df[variables].dropna().astype(str)
    if len(sub) < 3:
        raise ValueError('Trop peu de lignes complètes pour une ACM (valeurs manquantes sur les variables choisies).')
    blocks, var_of, mod_of, skipped = _indicator_matrix(sub, variables)
    Q = len(blocks)
    if Q < 2:
        raise ValueError('Sélectionnez au moins deux variables catégorielles ayant chacune 2 modalités ou plus.')
    Z = np.hstack(blocks)
    n, J = Z.shape
    count = Z.sum(axis=0)
    c = count / (n * Q)                                          # poids des modalités
    S = (Z / (n * Q) - c[None, :] / n) / np.sqrt(c[None, :] / n)
    K = J - Q
    U, sv, Vt = np.linalg.svd(S, full_matrices=False)
    U, sv, Vt = U[:, :K], sv[:K], Vt[:K]
    keep = sv > 1e-9
    U, sv, Vt = U[:, keep], sv[keep], Vt[keep]
    K = len(sv)
    if K == 0:
        raise ValueError("Les variables choisies ne présentent aucune variation commune exploitable (une seule modalité observée).")
    if n_axes:
        n_axes = min(n_axes, K)
    rows = np.sqrt(n) * U * sv                                   # coordonnées principales des individus
    cols = (Vt.T / np.sqrt(c)[:, None]) * sv                     # coordonnées principales des modalités
    return {'sub': sub, 'Q': Q, 'J': J, 'n': n, 'count': count, 'c': c, 'var_of': var_of, 'mod_of': mod_of,
            'skipped': skipped, 'eig': sv ** 2, 'rows': rows, 'cols': cols, 'K': K}


def benzecri_rates(eig, Q):
    """Taux d'inertie modifiés de Benzécri (axes de valeur propre > 1/Q) et leur cumul."""
    useful = eig > 1.0 / Q
    mod = np.zeros_like(eig)
    mod[useful] = ((Q / (Q - 1.0)) * (eig[useful] - 1.0 / Q)) ** 2
    total = mod.sum()
    rates = mod / total * 100 if total > 0 else mod
    return rates, np.cumsum(rates)


def run_mca(df: pd.DataFrame, variables: list, n_components: int = 2) -> dict:
    core = mca_core(df, variables)
    n, Q, J, K = core['n'], core['Q'], core['J'], core['K']
    if K < 2:
        raise ValueError("L'ACM a besoin d'au moins 2 axes : choisissez des variables à plus de modalités.")
    eig, c = core['eig'], core['c']
    n_comp = max(2, min(int(n_components), K))
    raw = eig / eig.sum() * 100
    bz, bz_cum = benzecri_rates(eig, Q)
    n_useful = int((eig > 1.0 / Q).sum())

    G = core['cols']                                             # J × K
    ctr = c[:, None] * G ** 2 / eig[None, :] * 100
    d2 = (G ** 2).sum(axis=1)
    cos = G ** 2 / d2[:, None]
    var_of, mod_of = np.array(core['var_of']), np.array(core['mod_of'])
    cats = pd.DataFrame({'Variable': [_short(v, 40) for v in var_of], 'Modalité': mod_of,
                         'Effectif': core['count'].astype(int), 'Poids (%)': (core['count'] / n * 100).round(1)})
    for k in range(n_comp):
        cats[f'F{k + 1}'] = G[:, k].round(3)
        cats[f'Contrib. F{k + 1} (%)'] = ctr[:, k].round(1)
        cats[f'cos² F{k + 1}'] = cos[:, k].round(3)
    var_ctr = pd.DataFrame({f'Contrib. F{k + 1} (%)': [ctr[var_of == v, k].sum() for v in dict.fromkeys(var_of)]
                            for k in range(n_comp)}, index=[_short(v, 40) for v in dict.fromkeys(var_of)]).round(1)

    eig_df = pd.DataFrame({
        'Axe': [f'F{k + 1}' for k in range(K)], 'Valeur propre': eig.round(4),
        'Inertie brute (%)': raw.round(2), 'Brute cumulée (%)': np.cumsum(raw).round(2),
        'Taux de Benzécri (%)': bz.round(2), 'Benzécri cumulé (%)': bz_cum.round(2)}).head(max(n_comp, min(K, 8)))

    pos = _sample_positions(n)
    sc = pd.DataFrame(core['rows'][pos, :2], columns=['F1', 'F2'])
    fig_rows = px.scatter(sc, x='F1', y='F2', opacity=0.5, color_discrete_sequence=[BLUE],
                          title='Plan factoriel — Individus (F1 × F2)' + (f' — échantillon de {len(pos)}' if len(pos) < n else ''))
    fig_rows.add_hline(y=0, line_dash='dash', line_color='#ccc')
    fig_rows.add_vline(x=0, line_dash='dash', line_color='#ccc')
    fig_rows.update_xaxes(title=f'F1 ({bz[0]:.1f} % Benzécri)')
    fig_rows.update_yaxes(title=f'F2 ({bz[1]:.1f} % Benzécri)')
    _layout(fig_rows, 420)

    order = np.argsort(-(ctr[:, 0] + ctr[:, 1]))
    shown = order[:MODALITIES_SHOWN] if J > MODALITIES_SHOWN else np.arange(J)
    fig_cats = go.Figure()
    for i, v in enumerate(dict.fromkeys(var_of)):
        idx = [j for j in shown if var_of[j] == v]
        if not idx:
            continue
        fig_cats.add_trace(go.Scatter(
            x=G[idx, 0], y=G[idx, 1], mode='markers+text', name=_short(v, 26),
            text=[_short(mod_of[j], 24) for j in idx], textposition='top center',
            marker=dict(size=[8 + 40 * np.sqrt(c[j]) for j in idx], color=PALETTE[i % len(PALETTE)]),
            customdata=[[var_of[j], mod_of[j], ctr[j, 0], ctr[j, 1]] for j in idx],
            hovertemplate='<b>%{customdata[0]}</b> : %{customdata[1]}<br>F1 %{x:.2f} · F2 %{y:.2f}'
                          '<br>Contrib. F1 %{customdata[2]:.1f} % · F2 %{customdata[3]:.1f} %<extra></extra>'))
    fig_cats.add_hline(y=0, line_dash='dash', line_color='#ccc')
    fig_cats.add_vline(x=0, line_dash='dash', line_color='#ccc')
    fig_cats.update_xaxes(title=f'F1 ({bz[0]:.1f} % Benzécri)')
    fig_cats.update_yaxes(title=f'F2 ({bz[1]:.1f} % Benzécri)')
    _layout(fig_cats, 460, title='Plan factoriel — Modalités (F1 × F2)'
            + (f' — les {MODALITIES_SHOWN} plus contributives sur {J}' if J > MODALITIES_SHOWN else ''))

    top_cats = cats.assign(_s=ctr[:, 0] + ctr[:, 1]).sort_values('_s', ascending=False).drop(columns='_s').head(15)
    rare = [f'{_short(v)} = {m}' for v, m, w in zip(var_of, mod_of, core['count'] / n) if w < 0.02]
    rows_df = pd.DataFrame(core['rows'][:, :n_comp], index=_line_numbers(core['sub'].index),
                           columns=[f'F{k + 1}' for k in range(n_comp)])
    rows_df.index.name = 'N° ligne'
    return {
        'method': 'ACM', 'n_obs': n, 'n_vars': Q, 'variables': [v for v in variables if v not in core['skipped']],
        'skipped': core['skipped'], 'n_modalities': J, 'n_components': n_comp,
        'eigenvalues': eig.round(4).tolist(), 'inertia': [round(e, 2) for e in bz.tolist()],
        'inertia_raw': [round(e, 2) for e in raw.tolist()], 'benzecri_cumulative': [round(e, 2) for e in bz_cum.tolist()],
        'n_useful_axes': n_useful, 'rare_modalities': rare,
        'cats_df': cats, 'var_contrib_df': var_ctr,
        'eig_table': _html(eig_df, index=False), 'cats_table': _html(top_cats, index=False), 'var_table': _html(var_ctr),
        'chart_rows': _json(fig_rows), 'chart_cats': _json(fig_cats),
        'tables': {'Valeurs propres': eig_df, 'Modalités (coord., contrib., cos²)': cats,
                   'Variables (contributions)': var_ctr.reset_index(names='Variable'),
                   'Individus (coordonnées)': rows_df.reset_index()},
        'scores': rows_df,
    }


# ─── AFC ─────────────────────────────────────────────────────────────────────

def run_ca(df: pd.DataFrame, row_var: str, col_var: str) -> dict:
    sub = df[[row_var, col_var]].dropna()
    ct = pd.crosstab(sub[row_var], sub[col_var])
    ct = ct.loc[ct.sum(axis=1) > 0, ct.sum(axis=0) > 0]
    I, Jc = ct.shape
    if I < 2 or Jc < 2:
        raise ValueError("L'AFC demande deux variables ayant chacune au moins 2 modalités observées.")
    N = float(ct.values.sum())
    P = ct.values / N
    r, c = P.sum(axis=1), P.sum(axis=0)
    S = (P - np.outer(r, c)) / np.sqrt(np.outer(r, c))
    U, sv, Vt = np.linalg.svd(S, full_matrices=False)
    K = min(I, Jc) - 1
    U, sv, Vt = U[:, :K], sv[:K], Vt[:K]
    eig = sv ** 2
    total = eig.sum()
    explained = eig / total * 100 if total > 0 else eig
    F = (U * sv) / np.sqrt(r)[:, None]                           # coordonnées principales des lignes
    G = (Vt.T * sv) / np.sqrt(c)[:, None]
    chi2 = N * total
    dof = (I - 1) * (Jc - 1)
    p_val = float(stats.chi2.sf(chi2, dof))
    cramer = float(np.sqrt(chi2 / (N * (min(I, Jc) - 1))))
    ctr_r = r[:, None] * F ** 2 / eig[None, :] * 100
    ctr_c = c[:, None] * G ** 2 / eig[None, :] * 100
    cos_r = F ** 2 / (F ** 2).sum(axis=1, keepdims=True)
    cos_c = G ** 2 / (G ** 2).sum(axis=1, keepdims=True)
    k2 = min(2, K)

    def table(names, coords, ctr, cos, mass, label):
        out = pd.DataFrame({label: [str(x) for x in names], 'Poids (%)': (mass * 100).round(1)})
        for k in range(k2):
            out[f'F{k + 1}'] = coords[:, k].round(3)
            out[f'Contrib. F{k + 1} (%)'] = ctr[:, k].round(1)
            out[f'cos² F{k + 1}'] = cos[:, k].round(3)
        return out

    rows_df = table(ct.index, F, ctr_r, cos_r, r, _short(row_var, 40))
    cols_df = table(ct.columns, G, ctr_c, cos_c, c, _short(col_var, 40))
    eig_df = pd.DataFrame({'Axe': [f'F{k + 1}' for k in range(K)], 'Valeur propre': eig.round(4),
                           'Inertie (%)': explained.round(2), 'Inertie cumulée (%)': np.cumsum(explained).round(2)}).head(6)
    expected = np.outer(ct.sum(axis=1), ct.sum(axis=0)) / N
    low_expected = float((expected < 5).mean() * 100)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=F[:, 0], y=F[:, 1] if k2 > 1 else np.zeros(I), mode='markers+text',
                             text=[_short(x, 26) for x in ct.index], textposition='top center', name=_short(row_var, 30),
                             marker=dict(size=[8 + 70 * np.sqrt(x) for x in r], color=BLUE, symbol='circle'),
                             hovertemplate='%{text}<br>F1 %{x:.2f} · F2 %{y:.2f}<extra></extra>'))
    fig.add_trace(go.Scatter(x=G[:, 0], y=G[:, 1] if k2 > 1 else np.zeros(Jc), mode='markers+text',
                             text=[_short(x, 26) for x in ct.columns], textposition='top center', name=_short(col_var, 30),
                             marker=dict(size=[8 + 70 * np.sqrt(x) for x in c], color=ORANGE, symbol='square'),
                             hovertemplate='%{text}<br>F1 %{x:.2f} · F2 %{y:.2f}<extra></extra>'))
    fig.add_hline(y=0, line_dash='dash', line_color='#ccc')
    fig.add_vline(x=0, line_dash='dash', line_color='#ccc')
    _layout(fig, 480, title=f'Plan factoriel AFC : {_short(row_var, 40)} × {_short(col_var, 40)}',
            xaxis_title=f'F1 ({explained[0]:.1f} %)', yaxis_title=f'F2 ({explained[1]:.1f} %)' if k2 > 1 else 'F2')
    return {
        'method': 'AFC', 'row_var': row_var, 'col_var': col_var, 'n_obs': int(N), 'n_vars': 2, 'variables': [row_var, col_var],
        'chi2': round(chi2, 2), 'dof': dof, 'p_value': round(p_val, 4), 'cramers_v': round(cramer, 3),
        'low_expected_pct': round(low_expected, 1), 'inertia': [round(e, 2) for e in explained.tolist()],
        'eigenvalues': eig.round(4).tolist(), 'total_inertia': round(float(total), 4),
        'rows_df': rows_df, 'cols_df': cols_df,
        'eig_table': _html(eig_df, index=False), 'rows_table': _html(rows_df, index=False), 'cols_table': _html(cols_df, index=False),
        'ct_html': ct.to_html(classes='table table-sm table-bordered text-center', border=0),
        'chart_biplot': _json(fig),
        'tables': {'Tableau de contingence': ct.reset_index(), 'Valeurs propres': eig_df,
                   'Lignes': rows_df, 'Colonnes': cols_df},
    }


# ─── Classification ──────────────────────────────────────────────────────────

def _vtests_numeric(X_raw: pd.DataFrame, labels):
    """Valeur-test de la moyenne de chaque variable dans chaque classe (|v| > 2 : écart notable)."""
    n = len(X_raw)
    mean, var = X_raw.mean(), X_raw.var(ddof=0)
    out = {}
    for lab in sorted(set(labels)):
        mask = np.asarray(labels) == lab
        nc = int(mask.sum())
        if nc == 0 or nc == n:
            continue
        denom = np.sqrt((n - nc) / (n - 1) * var / nc)
        v = ((X_raw[mask].mean() - mean) / denom.replace(0, np.nan)).fillna(0)
        out[lab] = v
    return pd.DataFrame(out)


def _vtests_modalities(sub: pd.DataFrame, labels):
    """Valeur-test de chaque modalité dans chaque classe (loi hypergéométrique)."""
    n = len(sub)
    labels = np.asarray(labels)
    rows = []
    for var in sub.columns:
        for mod, nm in sub[var].value_counts().items():
            for lab in sorted(set(labels)):
                nc = int((labels == lab).sum())
                ncm = int(((labels == lab) & (sub[var].values == mod)).sum())
                p = nm / n
                denom = np.sqrt(nc * p * (1 - p) * (n - nc) / (n - 1)) if n > 1 else 0
                v = (ncm - nc * p) / denom if denom > 0 else 0.0
                rows.append((lab, var, str(mod), ncm, nc, nm, v))
    return pd.DataFrame(rows, columns=['classe', 'variable', 'modalité', 'n_cm', 'n_c', 'n_m', 'v'])


def _ward_labels(X, k_values, max_n=CAH_MAX):
    """Ward (exact jusqu'à CAH_MAX individus, sinon sur un échantillon puis affectation au centre le plus proche).
    Renvoie (linkage, fonction de découpage en k classes pour tous les individus)."""
    n = len(X)
    rng = np.random.default_rng(RNG_SEED)
    sample = np.arange(n) if n <= max_n else np.sort(rng.choice(n, max_n, replace=False))
    Z = hierarchy.linkage(X[sample], method='ward')

    def cut(k):
        lab = hierarchy.fcluster(Z, t=k, criterion='maxclust') - 1
        if n <= max_n:
            return lab
        centers = np.vstack([X[sample][lab == c].mean(axis=0) for c in range(lab.max() + 1)])
        d = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2) if n * len(centers) * X.shape[1] < 5e7 else None
        if d is None:
            d = np.vstack([((X[i:i + 2000, None, :] - centers[None, :, :]) ** 2).sum(axis=2) for i in range(0, n, 2000)])
        return d.argmin(axis=1)
    return Z, cut, sample


def _silhouette(X, labels):
    if len(set(labels)) < 2 or len(set(labels)) >= len(X):
        return 0.0
    kwargs = {'sample_size': SIL_SAMPLE, 'random_state': RNG_SEED} if len(X) > SIL_SAMPLE else {}
    return float(silhouette_score(X, labels, **kwargs))


def _dendrogram_fig(Z, k, p=30):
    d = hierarchy.dendrogram(Z, truncate_mode='lastp', p=min(p, len(Z) + 1), no_plot=True)
    fig = go.Figure()
    for ic, dc in zip(d['icoord'], d['dcoord']):
        fig.add_trace(go.Scatter(x=ic, y=dc, mode='lines', line=dict(color=BLUE, width=1.4), hoverinfo='skip', showlegend=False))
    if 2 <= k <= len(Z):
        cut = (Z[-(k - 1), 2] + Z[-k, 2]) / 2 if k > 2 else (Z[-1, 2] + Z[-2, 2]) / 2
        fig.add_hline(y=cut, line_dash='dash', line_color=ORANGE, annotation_text=f'{k} classes', annotation_position='top right')
    leaves = d['ivl']
    fig.update_xaxes(tickmode='array', tickvals=[5 + 10 * i for i in range(len(leaves))], ticktext=leaves, tickangle=-45)
    fig.update_yaxes(title='Distance de Ward')
    return _layout(fig, 400, title='Dendrogramme (les feuilles regroupent les individus ; effectif entre parenthèses)')


def run_clustering(df: pd.DataFrame, variables: list, n_clusters=3, method: str = 'kmeans', kind: str = 'numeric') -> dict:
    """method : 'kmeans' | 'cah' (Ward). kind : 'numeric' (variables numériques) | 'mca' (variables catégorielles,
    classification sur les axes de l'ACM). n_clusters None ou 0 → nombre de classes suggéré par la silhouette."""
    method = method if method in ('kmeans', 'cah') else 'kmeans'
    if kind == 'mca':
        core = mca_core(df, variables)
        k_axes = int(max(1, min(core['K'], max(2, (core['eig'] > 1.0 / core['Q']).sum()), 8)))
        X = core['rows'][:, :k_axes]
        sub_cat = core['sub']
        index = core['sub'].index
        X_raw = None
        used_vars = [v for v in variables if v not in core['skipped']]
        space = f"{k_axes} premiers axes de l'ACM"
        constant = []
    else:
        sub, constant = _prepare_numeric_df(df, variables)
        X = StandardScaler().fit_transform(sub)
        X_raw, sub_cat, index = sub, None, sub.index
        used_vars = list(sub.columns)
        space = 'variables centrées-réduites'
    n = len(X)
    if n < 6:
        raise ValueError('Trop peu d\'individus pour une classification.')
    kmax = int(min(8, n - 1))
    ks = list(range(2, kmax + 1))

    sils, inertias, partitions = {}, {}, {}
    if method == 'kmeans':
        for k in ks:
            km = KMeans(n_clusters=k, random_state=RNG_SEED, n_init=3).fit(X)
            partitions[k] = km.labels_
            inertias[k] = float(km.inertia_)
            sils[k] = _silhouette(X, km.labels_)
        Z = cut = None
    else:
        Z, cut, _ = _ward_labels(X, ks)
        total_ss = float(((X - X.mean(axis=0)) ** 2).sum())
        for k in ks:
            lab = cut(k)
            partitions[k] = lab
            within = sum(float(((X[lab == c] - X[lab == c].mean(axis=0)) ** 2).sum()) for c in np.unique(lab))
            inertias[k] = within
            sils[k] = _silhouette(X, lab)
    suggested = max(sils, key=sils.get) if sils else 3
    auto = not n_clusters
    k = int(suggested if auto else max(2, min(int(n_clusters), kmax)))
    labels = partitions[k] if k in partitions else (KMeans(n_clusters=k, random_state=RNG_SEED, n_init=10).fit_predict(X)
                                                    if method == 'kmeans' else cut(k))
    if method == 'kmeans' and not auto:
        labels = KMeans(n_clusters=k, random_state=RNG_SEED, n_init=10).fit_predict(X)     # solution finale, plus soignée
    sil = _silhouette(X, labels)
    names = np.array([f'Classe {int(l) + 1}' for l in labels])
    # Numérotation par effectif décroissant : « Classe 1 » est toujours la plus nombreuse
    order = pd.Series(names).value_counts().index.tolist()
    rename = {old: f'Classe {i + 1}' for i, old in enumerate(order)}
    names = np.array([rename[x] for x in names])
    class_order = [f'Classe {i + 1}' for i in range(len(order))]

    counts = pd.Series(names).value_counts().reindex(class_order)
    counts_df = pd.DataFrame({'Classe': counts.index, 'Effectif': counts.values.astype(int),
                              'Part (%)': (counts.values / n * 100).round(1)})

    # Caractérisation
    traits, vt_table = {}, None
    if X_raw is not None:
        vt = _vtests_numeric(X_raw, names)
        means_df = X_raw.groupby(names).mean().reindex(class_order).round(2)
        means_df.loc['Ensemble'] = X_raw.mean().round(2)
        vt_table = vt.T.reindex(class_order).round(1)
        for cl in class_order:
            col = vt[cl].sort_values(key=abs, ascending=False)
            traits[cl] = [{'label': _short(var, 40), 'v': round(float(v), 1),
                           'sens': 'haut' if v > 0 else 'bas'} for var, v in col.head(5).items() if abs(v) >= 2]
    else:
        vt = _vtests_modalities(sub_cat, names)
        means_df = None
        for cl in class_order:
            sel = vt[(vt['classe'] == cl) & (vt['v'] >= 2)].sort_values('v', ascending=False).head(5)
            traits[cl] = [{'label': f"{_short(r.variable, 28)} = {r['modalité']}", 'v': round(float(r.v), 1), 'sens': 'sur',
                           'part_classe': round(100 * r.n_cm / r.n_c, 1), 'part_totale': round(100 * r.n_m / n, 1)}
                          for _, r in sel.iterrows()]
        vt_table = vt[vt['v'].abs() >= 2].assign(variable=lambda d: d['variable'].map(_short)).sort_values(['classe', 'v'], ascending=[True, False]) \
            .rename(columns={'classe': 'Classe', 'variable': 'Variable', 'v': 'Valeur-test', 'n_cm': 'Effectif dans la classe',
                             'n_c': 'Taille de la classe', 'n_m': 'Effectif total'}).round({'Valeur-test': 1})

    # Graphiques
    fig_elbow = make_subplots(rows=1, cols=2, subplot_titles=['Coude (inertie)', 'Silhouette'])
    fig_elbow.add_trace(go.Scatter(x=ks, y=[inertias[x] for x in ks], mode='lines+markers', marker_color=BLUE, name='Inertie'), row=1, col=1)
    fig_elbow.add_trace(go.Scatter(x=ks, y=[sils[x] for x in ks], mode='lines+markers', marker_color=ORANGE, name='Silhouette'), row=1, col=2)
    fig_elbow.add_vline(x=suggested, line_dash='dot', line_color=GREEN, row=1, col=2, annotation_text=f'k suggéré = {suggested}')
    fig_elbow.update_xaxes(title='Nombre de classes', dtick=1)
    _layout(fig_elbow, 340, showlegend=False)

    pos = _sample_positions(n)
    plane = PCA(n_components=2).fit_transform(X) if kind == 'numeric' else X[:, :2]
    if plane.shape[1] < 2:                                   # variables presque redondantes : un seul axe
        plane = np.hstack([plane, np.zeros((len(plane), 1))])
    scatter_df = pd.DataFrame(plane[pos], columns=['Axe 1', 'Axe 2'])
    scatter_df['Classe'] = names[pos]
    fig_scatter = px.scatter(scatter_df, x='Axe 1', y='Axe 2', color='Classe', symbol='Classe', category_orders={'Classe': class_order},
                             color_discrete_sequence=PALETTE, opacity=0.7,
                             title=f'Répartition des {k} classes ({"projection ACP" if kind == "numeric" else "plan F1 × F2 de l\'ACM"})')
    _layout(fig_scatter, 420)

    if X_raw is not None and 2 <= len(used_vars) <= MAX_RADAR_VARS:
        norm = (means_df.drop(index='Ensemble') - means_df.drop(index='Ensemble').min()) / (
            means_df.drop(index='Ensemble').max() - means_df.drop(index='Ensemble').min() + 1e-9)
        fig_radar = go.Figure()
        for i, cl in enumerate(norm.index):
            vals = norm.loc[cl].tolist() + [norm.loc[cl].iloc[0]]
            fig_radar.add_trace(go.Scatterpolar(r=vals, theta=[_short(v, 20) for v in used_vars] + [_short(used_vars[0], 20)],
                                                fill='toself', name=cl, line_color=PALETTE[i % len(PALETTE)]))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), title='Profils des classes (normalisé)')
        _layout(fig_radar, 400)
    else:
        fig_radar = _empty_fig('Profil radar disponible pour 2 à %d variables numériques ; voir les valeurs-tests ci-dessous.' % MAX_RADAR_VARS)

    fig_dendro = _dendrogram_fig(Z, k) if method == 'cah' else None
    classes = [{'name': cl, 'n': int(counts[cl]), 'pct': round(counts[cl] / n * 100, 1), 'traits': traits.get(cl, [])} for cl in class_order]
    result = {
        'method': 'Classification hiérarchique (Ward)' if method == 'cah' else 'Classification K-Means',
        'cluster_method': method, 'kind': kind, 'space': space,
        'n_clusters': k, 'n_obs': n, 'n_vars': len(used_vars), 'variables': used_vars, 'dropped_constant': constant,
        'silhouette': round(sil, 3), 'suggested_k': suggested, 'auto_k': auto, 'silhouettes': {kk: round(v, 3) for kk, v in sils.items()},
        'classes': classes, 'class_index': [int(i) for i in index], 'class_labels': names.tolist(),
        'counts_table': _html(counts_df, index=False),
        'means_table': _html(means_df) if means_df is not None else '',
        'vtests_table': _html(vt_table, index=(X_raw is not None)) if vt_table is not None else '',
        'chart_elbow': _json(fig_elbow), 'chart_scatter': _json(fig_scatter), 'chart_radar': _json(fig_radar),
        'chart_dendrogram': _json(fig_dendro) if fig_dendro is not None else None,
        'tables': {'Effectifs par classe': counts_df,
                   **({'Moyennes par classe': means_df.reset_index(names='Classe')} if means_df is not None else {}),
                   'Valeurs-tests': vt_table.reset_index(names='Classe') if X_raw is not None else vt_table,
                   'Appartenance': pd.DataFrame({'N° ligne': _line_numbers(index), 'Classe': names})},
    }
    return result
