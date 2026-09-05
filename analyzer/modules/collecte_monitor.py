import datetime
import json
from pathlib import Path
from typing import Any, Dict, List

# Ordre de priorité pour détecter la colonne géographique RÉELLE d'un
# formulaire Kobo arbitraire (ce module suit UN formulaire quelconque en
# cours d'analyse — pas forcément un des formulaires du registre SPAD, donc
# aucun nom de colonne fixe n'est garanti). Correspondance insensible à la
# casse sur un mot-clé contenu dans le nom de colonne — reflète la
# convention SPAD réelle observée (ex. "ENTETE_STANDARD/District_Sanitaire__X").
_GEO_FIELD_KEYWORDS = [
    ['district_sanitaire', 'district'],
    ['region_sanitaire', 'région_sanitaire', 'region', 'région'],
    ['etablissement_sanitaire', 'établissement_sanitaire', 'etablissement', 'établissement'],
    ['zone', 'commune', 'localite', 'localité'],
]


def detect_geo_column(df):
    """Renvoie le nom de la meilleure colonne géographique du formulaire
    chargé (district > région > établissement > zone/commune), ou None si
    aucune n'est détectée — mieux vaut ne rien afficher qu'inventer des
    zones fictives."""
    if df is None or getattr(df, 'empty', True):
        return None
    cols_lower = {col: str(col).lower() for col in df.columns}
    for keywords in _GEO_FIELD_KEYWORDS:
        for col, low in cols_lower.items():
            if any(k in low for k in keywords):
                return col
    return None


def real_geo_breakdown(df, target: int = 0):
    """Répartition RÉELLE des soumissions par unité géographique détectée
    dans le formulaire chargé (district, à défaut région, à défaut
    établissement) — remplace les anciennes « Zone 1/2/3 » qui étaient
    entièrement fictives (comptages calculés par arithmétique arbitraire à
    partir du seul total, sans jamais lire les données réelles).

    La cible par unité est une répartition ÉGALE de la cible globale entre
    les unités effectivement présentes dans les données : ce module suit un
    formulaire Kobo quelconque, sans les règles de cible par établissement
    du registre SPAD (voir modules/completeness.py pour ce cas précis, avec
    un vrai référentiel établissement/district). C'est une approximation
    assumée, pas une cible officielle.

    Renvoie (items, colonne_utilisée) — items est une liste vide si aucune
    colonne géographique n'a été trouvée, ou si le formulaire n'a aucune
    soumission avec une valeur renseignée dans cette colonne."""
    col = detect_geo_column(df)
    if not col:
        return [], None

    values = df[col].dropna().astype(str).str.strip()
    values = values[values != '']
    if values.empty:
        return [], col

    grouped = values.value_counts()
    n = len(grouped)
    target = int(target or 0)
    target_per_unit = target / n if (target and n) else 0

    items = []
    for name, received in grouped.items():
        received = int(received)
        if target_per_unit:
            rate = round(100 * received / target_per_unit, 1)
        else:
            rate = None
        if rate is None:
            status, badge = 'Reçu', 'bg-secondary'
        elif rate >= 100:
            status, badge = 'Cible atteinte', 'bg-success'
        elif rate >= 50:
            status, badge = 'En cours', 'bg-info'
        else:
            status, badge = 'À risque', 'bg-warning'
        items.append({
            'name': str(name),
            'received': received,
            'target': round(target_per_unit) if target_per_unit else 0,
            'rate': rate if rate is not None else 0.0,
            'status': status,
            'badge_class': badge,
        })

    items.sort(key=lambda it: it['rate'])
    return items, col


# Même logique que _GEO_FIELD_KEYWORDS/detect_geo_column ci-dessus, appliquée
# au champ Enquêteur — ce module suit un formulaire Kobo quelconque, donc
# aucun nom de colonne fixe n'est garanti (voir modules/completeness.py pour
# le cas des 7 formulaires officiels, où l'enquêteur est déduit de
# l'établissement assigné plutôt que d'un champ de soumission).
_ENQ_FIELD_KEYWORDS = [
    ['enqueteur', 'enquêteur'],
]


def detect_enqueteur_column(df):
    """Renvoie le nom de la colonne Enquêteur du formulaire chargé, ou None
    si aucune n'est détectée."""
    if df is None or getattr(df, 'empty', True):
        return None
    cols_lower = {col: str(col).lower() for col in df.columns}
    for keywords in _ENQ_FIELD_KEYWORDS:
        for col, low in cols_lower.items():
            if any(k in low for k in keywords):
                return col
    return None


def enqueteur_breakdown(df):
    """Nombre de collectes par enquêteur, à partir de la colonne détectée
    dans le formulaire chargé. Renvoie (items, colonne_utilisée) — items est
    une liste vide si aucune colonne Enquêteur n'a été trouvée, ou si aucune
    soumission n'a de valeur renseignée dans cette colonne."""
    col = detect_enqueteur_column(df)
    if not col:
        return [], None

    values = df[col].dropna().astype(str).str.strip()
    values = values[values != '']
    if values.empty:
        return [], col

    grouped = values.value_counts()
    items = [{'name': str(name), 'received': int(n)} for name, n in grouped.items()]
    items.sort(key=lambda it: -it['received'])
    return items, col


DEFAULT_STATE = {
    'target': 0,
    'history': [],
    'last_sync_at': None,
    'last_sync_count': 0,
    'last_sync_status': 'inconnu',
    'last_form_name': None,
}


def _state_path(path: Path | str | None = None) -> Path:
    if path is None:
        from config import Config
        return Path(Config.UPLOAD_FOLDER) / 'collecte_state.json'
    return Path(path)


def load_state(path: Path | str | None = None) -> Dict[str, Any]:
    p = _state_path(path)
    if not p.exists():
        return dict(DEFAULT_STATE)
    try:
        with p.open('r', encoding='utf-8') as fh:
            data = json.load(fh)
        state = dict(DEFAULT_STATE)
        state.update(data)
        state['history'] = list(state.get('history', []))
        return state
    except Exception:
        return dict(DEFAULT_STATE)


def save_state(path: Path | str | None = None, state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    p = _state_path(path)
    payload = dict(DEFAULT_STATE)
    if state:
        payload.update(state)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return payload


def append_sync_event(state: Dict[str, Any], path: Path | str | None = None, form_name: str = 'Kobo', count: int = 0, status: str = 'réussi', target: int | None = None) -> Dict[str, Any]:
    payload = dict(state or {})
    if target is not None:
        payload['target'] = int(target)
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    payload['last_sync_at'] = timestamp
    payload['last_sync_count'] = int(count)
    payload['last_sync_status'] = status
    payload['last_form_name'] = form_name or payload.get('last_form_name')
    payload.setdefault('history', [])
    payload['history'].append({
        'form_name': form_name,
        'count': int(count),
        'status': status,
        'target': payload.get('target', 0),
        'timestamp': timestamp,
    })
    payload['history'] = payload['history'][-10:]
    save_state(path, payload)
    return payload


def build_dashboard_metrics(state: Dict[str, Any], current_count: int | None = None, df=None) -> Dict[str, Any]:
    received = int(current_count if current_count is not None else state.get('last_sync_count', 0))
    target = int(state.get('target', 0) or 0)
    taux = round(100 * received / target, 1) if target else 0.0
    history = state.get('history', []) or []
    evolution = [int(item.get('count', 0)) for item in history[-7:]]
    if not evolution:
        evolution = [0]
    # Répartition géographique RÉELLE (district/région/établissement détecté
    # dans les données chargées) — jamais de zones fictives. Liste vide si
    # aucune donnée n'est chargée ou qu'aucune colonne géographique n'est
    # détectée ; le gabarit l'affiche alors clairement plutôt que d'inventer
    # un contenu.
    zones, geo_column = real_geo_breakdown(df, target)
    enqueteurs, enqueteur_column = enqueteur_breakdown(df)
    daily_rate = max(0, received // max(1, len(history) or 1)) if history else 0
    return {
        'received': received,
        'cible': target,
        'taux': taux,
        'active_alerts': 1 if taux < 90 else 0,
        'evolution': evolution,
        'zones': zones,
        'geo_column': geo_column,
        'enqueteurs': enqueteurs,
        'enqueteur_column': enqueteur_column,
        'history': history,
        'daily_rate': daily_rate,
        'daily_target': max(1, target // max(1, len(history) or 1)) if target else 0,
    }


def build_collecte_views(state: Dict[str, Any], current_count: int | None = None, data_meta: Dict[str, Any] | None = None, sync_status: Dict[str, Any] | None = None, df=None) -> Dict[str, Any]:
    metrics = build_dashboard_metrics(state, current_count=current_count, df=df)
    last_status = state.get('last_sync_status') or 'inconnu'
    last_sync_at = state.get('last_sync_at') or 'Jamais'
    form_name = state.get('last_form_name') or 'Kobo'

    teams = [
        {'name': 'Équipe terrain 1', 'submissions': metrics['received'], 'last_activity': last_sync_at, 'status': 'Actif' if last_status == 'réussi' else 'À relancer', 'badge_class': 'bg-success' if last_status == 'réussi' else 'bg-warning'},
        {'name': 'Équipe terrain 2', 'submissions': max(0, metrics['received'] - 30), 'last_activity': 'Hier', 'status': 'À relancer', 'badge_class': 'bg-warning'},
    ]
    zones = metrics['zones']
    geo_column = metrics['geo_column']

    sync_payload = {
        'active': False,
        'has_pending': False,
        'available_n_obs': None,
        'last_check_at': None,
        'error': None,
    }
    if sync_status:
        sync_payload.update(sync_status)

    alerts = []
    if last_status != 'réussi':
        alerts.append({'zone': form_name, 'type': 'Synchronisation échouée', 'level': 'Critique', 'level_class': 'bg-danger', 'date': last_sync_at, 'status': 'Ouverte', 'status_class': 'bg-warning'})
    else:
        alerts.append({'zone': 'Collecte globale', 'type': 'Synchronisation réussie', 'level': 'Info', 'level_class': 'bg-info', 'date': last_sync_at, 'status': 'Ouverte', 'status_class': 'bg-info'})

    if sync_payload.get('active') and sync_payload.get('has_pending'):
        alerts.append({'zone': 'Synchronisation', 'type': 'Nouvelles soumissions prêtes à appliquer', 'level': 'Alerte', 'level_class': 'bg-warning', 'date': last_sync_at, 'status': 'En attente', 'status_class': 'bg-warning'})

    target = int(state.get('target', 0) or 0)
    if target and metrics['received'] < target and metrics['taux'] < 80:
        deficit = target - metrics['received']
        alerts.append({'zone': 'Rythme', 'type': f'Rythme faible — {deficit} soumissions manquantes', 'level': 'Alerte', 'level_class': 'bg-warning', 'date': last_sync_at, 'status': 'À traiter', 'status_class': 'bg-warning'})

    # Même répartition géographique réelle que « zones » — juste projetée
    # sur les colonnes attendues par le tableau « Tableaux stratifiés »
    # (label/received/target/rate, sans statut ni badge).
    stratified_summary = [
        {'label': z['name'], 'received': z['received'], 'target': z['target'], 'rate': z['rate']}
        for z in zones
    ]

    if metrics['taux'] >= 95:
        risk_level = 'faible'
        recommendation = 'Le rythme est soutenu, il reste à sécuriser la qualité des données.'
    elif metrics['taux'] >= 80:
        risk_level = 'moyen'
        recommendation = 'Le rythme est acceptable mais un suivi de terrain reste utile.'
    else:
        risk_level = 'élevé'
        recommendation = 'Le rythme est insuffisant, il faut renforcer la relance ciblée.'

    interpretation = {
        'risk_level': risk_level,
        'recommendation': recommendation,
        'recommandation': recommendation,
        'current_rate': metrics['taux'],
    }

    meta = data_meta or {}
    quality_items = [
        {'variable': 'Observations', 'missing': f"{meta.get('missing_pct', 0):.1f}%", 'outliers': '—', 'status': 'Correct' if meta.get('missing_pct', 0) < 10 else 'À surveiller', 'badge_class': 'bg-success' if meta.get('missing_pct', 0) < 10 else 'bg-warning'},
        {'variable': 'Variables', 'missing': f"{meta.get('n_vars', 0)}", 'outliers': '—', 'status': 'Correct', 'badge_class': 'bg-success'},
    ]
    return {
        'metrics': metrics,
        'geo_items': zones,
        'geo_column': geo_column,
        'teams': teams,
        'alerts': alerts,
        'quality_items': quality_items,
        'sync_status': sync_payload,
        'stratified_summary': stratified_summary,
        'interpretation': interpretation,
    }
