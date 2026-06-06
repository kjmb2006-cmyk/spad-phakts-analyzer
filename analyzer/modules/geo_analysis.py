import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go


def create_map(df: pd.DataFrame, lat_col: str, lon_col: str,
               color_col: str = None, size_col: str = None,
               hover_cols: list = None) -> dict:
    """
    Carte interactive avec Plotly Scattermap / Densitymap (API plotly 5.18+ / 6.x).
    Utilise open-street-map (sans token Mapbox requis).
    """
    extra_cols = (
        ([color_col] if color_col and color_col in df.columns else []) +
        ([size_col]  if size_col  and size_col  in df.columns else []) +
        [c for c in (hover_cols or []) if c in df.columns]
    )
    sub = df[[lat_col, lon_col] + extra_cols].copy()

    sub[lat_col] = pd.to_numeric(sub[lat_col], errors='coerce')
    sub[lon_col] = pd.to_numeric(sub[lon_col], errors='coerce')
    sub = sub.dropna(subset=[lat_col, lon_col])

    sub = sub[
        sub[lat_col].between(-90, 90) &
        sub[lon_col].between(-180, 180) &
        (sub[lat_col] != 0) & (sub[lon_col] != 0)
    ]

    n_points = len(sub)
    if n_points == 0:
        return {'error': 'Aucun point géographique valide trouvé.'}

    center_lat = float(sub[lat_col].mean())
    center_lon = float(sub[lon_col].mean())

    # ── Carte principale (points) ─────────────────────────────────────────────
    valid_hover = [c for c in (hover_cols or []) if c in sub.columns]

    def _make_hover(row):
        parts = [f'<b>Lat:</b> {row[lat_col]:.5f}', f'<b>Lon:</b> {row[lon_col]:.5f}']
        for c in valid_hover:
            parts.append(f'<b>{c}:</b> {row[c]}')
        return '<br>'.join(parts)

    if color_col and color_col in sub.columns:
        sub[color_col] = sub[color_col].astype(str)
        categories = sub[color_col].unique().tolist()
        palette = px.colors.qualitative.Set2

        traces = []
        for i, cat in enumerate(categories):
            mask = sub[color_col] == cat
            s = sub[mask]
            traces.append(go.Scattermap(
                lat=s[lat_col],
                lon=s[lon_col],
                mode='markers',
                marker=dict(size=10, opacity=0.85, color=palette[i % len(palette)]),
                name=cat,
                text=s.apply(_make_hover, axis=1),
                hoverinfo='text',
            ))
        fig_map = go.Figure(traces)
    else:
        fig_map = go.Figure(go.Scattermap(
            lat=sub[lat_col],
            lon=sub[lon_col],
            mode='markers',
            marker=dict(size=10, opacity=0.85, color='#1a6fa8'),
            name='Observations',
            text=sub.apply(_make_hover, axis=1),
            hoverinfo='text',
        ))

    fig_map.update_layout(
        map_style='open-street-map',
        map=dict(center=dict(lat=center_lat, lon=center_lon), zoom=7),
        title=f'Carte des observations ({n_points} points)',
        margin=dict(l=0, r=0, t=50, b=0),
        height=520,
        font=dict(family='Inter, sans-serif'),
        legend=dict(orientation='v', x=0.01, y=0.99,
                    bgcolor='rgba(255,255,255,0.85)',
                    bordercolor='#dee2e6', borderwidth=1),
    )

    # ── Carte de densité (heatmap) ────────────────────────────────────────────
    fig_density = go.Figure(go.Densitymap(
        lat=sub[lat_col],
        lon=sub[lon_col],
        radius=25,
        colorscale='Hot',
        showscale=True,
        opacity=0.7,
        name='Densité',
    ))
    fig_density.update_layout(
        map_style='open-street-map',
        map=dict(center=dict(lat=center_lat, lon=center_lon), zoom=7),
        title=f'Carte de densité ({n_points} points)',
        margin=dict(l=0, r=0, t=50, b=0),
        height=520,
        font=dict(family='Inter, sans-serif'),
    )

    # ── Statistiques géographiques ────────────────────────────────────────────
    geo_stats = {
        'N points': n_points,
        'Lat. moyenne': round(center_lat, 5),
        'Lon. moyenne': round(center_lon, 5),
        'Lat. min': round(float(sub[lat_col].min()), 5),
        'Lat. max': round(float(sub[lat_col].max()), 5),
        'Lon. min': round(float(sub[lon_col].min()), 5),
        'Lon. max': round(float(sub[lon_col].max()), 5),
    }

    # Distribution par variable colorée
    color_chart_json = None
    if color_col and color_col in sub.columns:
        counts = sub[color_col].value_counts().reset_index()
        counts.columns = [color_col, 'Effectif']
        fig_dist = px.bar(
            counts, x=color_col, y='Effectif',
            color=color_col,
            title=f'Répartition par {color_col}',
            color_discrete_sequence=px.colors.qualitative.Set2,
            text='Effectif',
        )
        fig_dist.update_traces(textposition='outside')
        fig_dist.update_layout(
            showlegend=False, height=300,
            plot_bgcolor='white', paper_bgcolor='white',
            font=dict(family='Inter, sans-serif'),
            margin=dict(t=50, b=40),
        )
        fig_dist.update_yaxes(gridcolor='#f0f0f0')
        color_chart_json = fig_dist.to_json(engine='json')

    return {
        'n_points': n_points,
        'center_lat': round(center_lat, 5),
        'center_lon': round(center_lon, 5),
        'stats': geo_stats,
        'chart_map': fig_map.to_json(engine='json'),
        'chart_density': fig_density.to_json(engine='json'),
        'color_chart': color_chart_json,
        'lat_col': lat_col,
        'lon_col': lon_col,
        'color_col': color_col,
    }
