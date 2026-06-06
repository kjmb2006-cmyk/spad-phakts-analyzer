import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')


def _prepare_numeric_df(df: pd.DataFrame, variables: list) -> pd.DataFrame:
    sub = df[variables].copy()
    for var in variables:
        sub[var] = pd.to_numeric(sub[var], errors='coerce')
    sub = sub.dropna()
    if sub.shape[0] < 2:
        raise ValueError(
            'Les variables sélectionnées contiennent trop de valeurs manquantes ou pas assez de lignes valides.')
    if sub.shape[1] < 2:
        raise ValueError('Sélectionnez au moins deux variables numériques pour cette analyse.')
    return sub


# ─── ACP (PCA) ────────────────────────────────────────────────────────────────

def run_pca(df: pd.DataFrame, variables: list, n_components: int = 2) -> dict:
    sub = _prepare_numeric_df(df, variables)
    n = len(sub)
    scaler = StandardScaler()
    X = scaler.fit_transform(sub)
    n_comp = min(n_components, len(variables), n)
    pca = PCA(n_components=n_comp)
    scores = pca.fit_transform(X)

    explained = pca.explained_variance_ratio_ * 100
    cumulative = np.cumsum(explained)

    # Eigenvalues table
    eig_df = pd.DataFrame({
        'Composante': [f'F{i+1}' for i in range(n_comp)],
        'Valeur propre': pca.explained_variance_.round(3),
        'Variance expliquée (%)': explained.round(2),
        'Variance cumulée (%)': cumulative.round(2),
    })

    # Loadings (correlations variables-axes)
    loadings = pd.DataFrame(
        pca.components_.T,
        index=variables,
        columns=[f'F{i+1}' for i in range(n_comp)]
    ).round(3)

    # Scree plot
    fig_scree = go.Figure()
    fig_scree.add_trace(go.Bar(x=eig_df['Composante'], y=eig_df['Variance expliquée (%)'],
                                name='Variance (%)', marker_color='#1a6fa8'))
    fig_scree.add_trace(go.Scatter(x=eig_df['Composante'], y=eig_df['Variance cumulée (%)'],
                                    name='Cumulée (%)', mode='lines+markers',
                                    marker_color='#e05c1a', line=dict(width=2)))
    fig_scree.add_hline(y=80, line_dash='dot', line_color='gray',
                         annotation_text='80%', annotation_position='right')
    fig_scree.update_layout(title='Eboulis des valeurs propres (Scree plot)',
                             height=360, plot_bgcolor='white', paper_bgcolor='white',
                             font=dict(family='Inter, sans-serif'),
                             yaxis_title='Variance expliquée (%)',
                             legend=dict(orientation='h', y=1.1))

    # Biplot (F1 × F2)
    scores_df = pd.DataFrame(scores[:, :2], columns=['F1', 'F2'])
    fig_biplot = px.scatter(scores_df, x='F1', y='F2',
                             title='Nuage des individus (F1 × F2)',
                             color_discrete_sequence=['#1a6fa8'],
                             opacity=0.6)
    # Add variable arrows
    scale = max(scores_df['F1'].abs().max(), scores_df['F2'].abs().max()) * 0.6
    for i, var in enumerate(variables):
        lx = loadings.loc[var, 'F1'] * scale
        ly = loadings.loc[var, 'F2'] * scale
        fig_biplot.add_annotation(x=lx, y=ly, ax=0, ay=0,
                                   text=var, font=dict(size=10, color='#e05c1a'),
                                   arrowhead=2, arrowcolor='#e05c1a', arrowwidth=1.5)
    fig_biplot.add_hline(y=0, line_dash='dash', line_color='#ccc')
    fig_biplot.add_vline(x=0, line_dash='dash', line_color='#ccc')
    fig_biplot.update_layout(height=420, plot_bgcolor='white', paper_bgcolor='white',
                              font=dict(family='Inter, sans-serif'))

    # Correlation circle
    theta = np.linspace(0, 2 * np.pi, 100)
    fig_circle = go.Figure()
    fig_circle.add_trace(go.Scatter(x=np.cos(theta), y=np.sin(theta),
                                     mode='lines', line=dict(color='#ccc'), showlegend=False))
    for var in variables:
        x_end = float(loadings.loc[var, 'F1'])
        y_end = float(loadings.loc[var, 'F2'])
        fig_circle.add_annotation(x=x_end, y=y_end, ax=0, ay=0,
                                   text=var, font=dict(size=10, color='#1a6fa8'),
                                   arrowhead=2, arrowcolor='#1a6fa8', arrowwidth=2)
        fig_circle.add_trace(go.Scatter(x=[x_end], y=[y_end], mode='markers',
                                         marker=dict(size=8, color='#e05c1a'),
                                         showlegend=False))
    fig_circle.update_layout(title='Cercle des corrélations (F1 × F2)',
                              height=420, plot_bgcolor='white', paper_bgcolor='white',
                              xaxis=dict(range=[-1.1, 1.1], title=f'F1 ({explained[0]:.1f}%)'),
                              yaxis=dict(range=[-1.1, 1.1], scaleanchor='x',
                                         title=f'F2 ({explained[1]:.1f}%)' if n_comp > 1 else ''),
                              font=dict(family='Inter, sans-serif'))

    return {
        'method': 'ACP',
        'n_obs': n,
        'n_vars': len(variables),
        'variables': variables,
        'eig_table': eig_df.to_html(classes='table table-sm table-bordered text-center',
                                    border=0, index=False),
        'loadings_table': loadings.to_html(classes='table table-sm table-bordered text-center',
                                            border=0),
        'chart_scree': fig_scree.to_json(engine='json'),
        'chart_biplot': fig_biplot.to_json(engine='json'),
        'chart_circle': fig_circle.to_json(engine='json'),
        'inertia': [round(e, 2) for e in explained.tolist()],
    }


# ─── ACM (MCA) ────────────────────────────────────────────────────────────────

def run_mca(df: pd.DataFrame, variables: list, n_components: int = 2) -> dict:
    sub = df[variables].dropna().astype(str)

    # Burt matrix approach / indicator matrix
    dummies = pd.get_dummies(sub)
    n, p = dummies.shape
    n_comp = min(n_components, p - len(variables))

    # Correspondance on indicator matrix
    Z = dummies.values.astype(float)
    row_masses = Z.sum(axis=1)
    col_masses = Z.sum(axis=0)
    N = Z.sum()

    Dr_inv = np.diag(1.0 / row_masses)
    Dc_inv = np.diag(1.0 / col_masses)

    P = Z / N
    r = P.sum(axis=1, keepdims=True)
    c = P.sum(axis=0, keepdims=True)
    S = (P - r @ c) / (np.sqrt(r) * np.sqrt(c))

    U, sv, Vt = np.linalg.svd(S, full_matrices=False)
    sv = sv[1:]  # skip trivial first
    U = U[:, 1:]
    Vt = Vt[1:, :]
    n_comp = min(n_comp, len(sv))

    inertia = sv[:n_comp] ** 2
    total_inertia = sv ** 2
    explained = inertia / total_inertia.sum() * 100

    scores_rows = (U[:, :n_comp] * sv[:n_comp])
    scores_cols = (Vt[:n_comp, :].T * sv[:n_comp])

    scores_df = pd.DataFrame(scores_rows[:, :2], columns=['F1', 'F2'])
    cols_df = pd.DataFrame(scores_cols[:, :2], columns=['F1', 'F2'],
                           index=dummies.columns)

    # Row scores plot
    fig_rows = px.scatter(scores_df, x='F1', y='F2',
                          title='Plan factoriel — Individus (F1 × F2)',
                          opacity=0.5, color_discrete_sequence=['#1a6fa8'])
    fig_rows.add_hline(y=0, line_dash='dash', line_color='#ccc')
    fig_rows.add_vline(x=0, line_dash='dash', line_color='#ccc')
    fig_rows.update_layout(height=400, plot_bgcolor='white', paper_bgcolor='white',
                           font=dict(family='Inter, sans-serif'))

    # Category scores plot
    colors = px.colors.qualitative.Set2
    fig_cats = go.Figure()
    for i, var in enumerate(variables):
        mask = [c.startswith(var + '_') or c == var for c in cols_df.index]
        sub_cols = cols_df[mask]
        fig_cats.add_trace(go.Scatter(
            x=sub_cols['F1'], y=sub_cols['F2'],
            mode='markers+text',
            text=[c.split('_', 1)[-1] if '_' in c else c for c in sub_cols.index],
            textposition='top center',
            name=var,
            marker=dict(size=12, color=colors[i % len(colors)]),
        ))
    fig_cats.add_hline(y=0, line_dash='dash', line_color='#ccc')
    fig_cats.add_vline(x=0, line_dash='dash', line_color='#ccc')
    fig_cats.update_layout(title='Plan factoriel — Modalités (F1 × F2)',
                           height=420, plot_bgcolor='white', paper_bgcolor='white',
                           font=dict(family='Inter, sans-serif'))

    eig_df = pd.DataFrame({
        'Axe': [f'F{i+1}' for i in range(n_comp)],
        'Valeur propre': sv[:n_comp].round(4),
        'Inertie expliquée (%)': explained.round(2),
        'Inertie cumulée (%)': np.cumsum(explained).round(2),
    })

    return {
        'method': 'ACM',
        'n_obs': n,
        'n_vars': len(variables),
        'variables': variables,
        'eig_table': eig_df.to_html(classes='table table-sm table-bordered text-center',
                                    border=0, index=False),
        'chart_rows': fig_rows.to_json(engine='json'),
        'chart_cats': fig_cats.to_json(engine='json'),
        'inertia': [round(e, 2) for e in explained.tolist()],
    }


# ─── AFC ──────────────────────────────────────────────────────────────────────

def run_ca(df: pd.DataFrame, row_var: str, col_var: str) -> dict:
    sub = df[[row_var, col_var]].dropna()
    ct = pd.crosstab(sub[row_var], sub[col_var])

    N = ct.values.sum()
    P = ct.values / N
    r = P.sum(axis=1, keepdims=True)
    c = P.sum(axis=0, keepdims=True)
    S = (P - r @ c) / (np.sqrt(r) * np.sqrt(c))

    U, sv, Vt = np.linalg.svd(S, full_matrices=False)
    inertia = sv ** 2
    explained = inertia / inertia.sum() * 100

    row_scores = U[:, :2] * sv[:2]
    col_scores = Vt[:2, :].T * sv[:2]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=row_scores[:, 0], y=row_scores[:, 1],
        mode='markers+text',
        text=ct.index.astype(str).tolist(),
        textposition='top center',
        name=row_var,
        marker=dict(size=12, symbol='circle', color='#1a6fa8'),
    ))
    fig.add_trace(go.Scatter(
        x=col_scores[:, 0], y=col_scores[:, 1],
        mode='markers+text',
        text=ct.columns.astype(str).tolist(),
        textposition='top center',
        name=col_var,
        marker=dict(size=12, symbol='square', color='#e05c1a'),
    ))
    fig.add_hline(y=0, line_dash='dash', line_color='#ccc')
    fig.add_vline(x=0, line_dash='dash', line_color='#ccc')
    fig.update_layout(
        title=f'Plan factoriel AFC : {row_var} × {col_var}',
        xaxis_title=f'F1 ({explained[0]:.1f}%)',
        yaxis_title=f'F2 ({explained[1]:.1f}%)' if len(sv) > 1 else 'F2',
        height=460, plot_bgcolor='white', paper_bgcolor='white',
        font=dict(family='Inter, sans-serif'),
    )

    eig_df = pd.DataFrame({
        'Axe': [f'F{i+1}' for i in range(min(4, len(sv)))],
        'Valeur propre': sv[:4].round(4),
        'Inertie (%)': explained[:4].round(2),
        'Inertie cumulée (%)': np.cumsum(explained[:4]).round(2),
    })

    return {
        'method': 'AFC',
        'row_var': row_var,
        'col_var': col_var,
        'eig_table': eig_df.to_html(classes='table table-sm table-bordered text-center',
                                    border=0, index=False),
        'chart_biplot': fig.to_json(engine='json'),
        'ct_html': ct.to_html(classes='table table-sm table-bordered text-center', border=0),
    }


# ─── CLASSIFICATION ───────────────────────────────────────────────────────────

def run_clustering(df: pd.DataFrame, variables: list, n_clusters: int = 3) -> dict:
    sub = _prepare_numeric_df(df, variables)
    n = len(sub)
    scaler = StandardScaler()
    X = scaler.fit_transform(sub)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)
    sil = silhouette_score(X, labels) if n_clusters > 1 else 0

    sub_out = sub.copy()
    sub_out['Classe'] = [f'Classe {l+1}' for l in labels]

    # Cluster profiles
    profile = sub_out.groupby('Classe').agg(['mean', 'count'])
    profile.columns = ['_'.join(c) for c in profile.columns]
    means_df = sub_out.groupby('Classe')[variables].mean().round(2)
    counts_df = sub_out.groupby('Classe').size().reset_index(name='Effectif')
    counts_df['Part (%)'] = (counts_df['Effectif'] / n * 100).round(1)

    # Elbow method (k=2..8)
    ks = range(2, min(9, n))
    inertias = [KMeans(n_clusters=k, random_state=42, n_init=10).fit(X).inertia_ for k in ks]
    sils = []
    for k in ks:
        lb = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(X)
        sils.append(silhouette_score(X, lb) if k > 1 else 0)

    fig_elbow = make_subplots(rows=1, cols=2,
                               subplot_titles=['Méthode du coude (Inertie)',
                                               'Silhouette moyenne'])
    fig_elbow.add_trace(go.Scatter(x=list(ks), y=inertias, mode='lines+markers',
                                    marker_color='#1a6fa8', name='Inertie'), row=1, col=1)
    fig_elbow.add_trace(go.Scatter(x=list(ks), y=sils, mode='lines+markers',
                                    marker_color='#e05c1a', name='Silhouette'), row=1, col=2)
    fig_elbow.update_layout(height=330, showlegend=False, plot_bgcolor='white',
                             paper_bgcolor='white', font=dict(family='Inter, sans-serif'))

    # Scatter plot of clusters (first 2 dims via PCA)
    pca2 = PCA(n_components=2)
    coords = pca2.fit_transform(X)
    scatter_df = pd.DataFrame(coords, columns=['PC1', 'PC2'])
    scatter_df['Classe'] = sub_out['Classe'].values
    fig_scatter = px.scatter(scatter_df, x='PC1', y='PC2', color='Classe',
                              title=f'Répartition des {n_clusters} classes (projection ACP)',
                              color_discrete_sequence=px.colors.qualitative.Set2,
                              symbol='Classe')
    fig_scatter.update_layout(height=400, plot_bgcolor='white', paper_bgcolor='white',
                               font=dict(family='Inter, sans-serif'))

    # Radar chart of means per cluster (normalized)
    means_norm = (means_df - means_df.min()) / (means_df.max() - means_df.min() + 1e-9)
    fig_radar = go.Figure()
    colors = px.colors.qualitative.Set2
    for i, classe in enumerate(means_norm.index):
        vals = means_norm.loc[classe].tolist()
        vals += [vals[0]]
        cats = variables + [variables[0]]
        fig_radar.add_trace(go.Scatterpolar(r=vals, theta=cats, fill='toself',
                                             name=classe,
                                             line_color=colors[i % len(colors)]))
    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                             showlegend=True, height=380,
                             title='Profils des classes (normalisé)',
                             font=dict(family='Inter, sans-serif'))

    return {
        'method': 'Classification K-Means',
        'n_clusters': n_clusters,
        'n_obs': n,
        'variables': variables,
        'silhouette': round(sil, 3),
        'counts_table': counts_df.to_html(classes='table table-sm table-bordered text-center',
                                           border=0, index=False),
        'means_table': means_df.to_html(classes='table table-sm table-bordered text-center',
                                         border=0),
        'chart_elbow': fig_elbow.to_json(engine='json'),
        'chart_scatter': fig_scatter.to_json(engine='json'),
        'chart_radar': fig_radar.to_json(engine='json'),
    }
