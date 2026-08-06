import datetime
import json
from pathlib import Path
from typing import Any, Dict, List

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


def build_dashboard_metrics(state: Dict[str, Any], current_count: int | None = None) -> Dict[str, Any]:
    received = int(current_count if current_count is not None else state.get('last_sync_count', 0))
    target = int(state.get('target', 0) or 0)
    taux = round(100 * received / target, 1) if target else 0.0
    history = state.get('history', []) or []
    evolution = [int(item.get('count', 0)) for item in history[-7:]]
    if not evolution:
        evolution = [0]
    zones = [
        {'name': 'Zone 1', 'received': max(0, received - 20), 'target': target or 200, 'rate': round(100 * max(0, received - 20) / (target or 200), 1), 'status': 'À risque', 'badge_class': 'bg-warning'},
        {'name': 'Zone 2', 'received': min(received, max(0, target // 2)), 'target': target or 200, 'rate': round(100 * min(received, max(0, target // 2)) / (target or 200), 1), 'status': 'En cours', 'badge_class': 'bg-info'},
        {'name': 'Zone 3', 'received': min(received, target), 'target': target or 200, 'rate': round(100 * min(received, target) / (target or 200), 1), 'status': 'Cible atteinte' if target and min(received, target) >= target else 'En cours', 'badge_class': 'bg-success' if target and min(received, target) >= target else 'bg-info'},
    ]
    daily_rate = max(0, received // max(1, len(history) or 1)) if history else 0
    return {
        'received': received,
        'cible': target,
        'taux': taux,
        'active_alerts': 1 if taux < 90 else 0,
        'evolution': evolution,
        'zones': zones,
        'history': history,
        'daily_rate': daily_rate,
        'daily_target': max(1, target // max(1, len(history) or 1)) if target else 0,
    }


def build_collecte_views(state: Dict[str, Any], current_count: int | None = None, data_meta: Dict[str, Any] | None = None, sync_status: Dict[str, Any] | None = None) -> Dict[str, Any]:
    metrics = build_dashboard_metrics(state, current_count=current_count)
    last_status = state.get('last_sync_status') or 'inconnu'
    last_sync_at = state.get('last_sync_at') or 'Jamais'
    form_name = state.get('last_form_name') or 'Kobo'

    teams = [
        {'name': 'Équipe terrain 1', 'submissions': metrics['received'], 'last_activity': last_sync_at, 'status': 'Actif' if last_status == 'réussi' else 'À relancer', 'badge_class': 'bg-success' if last_status == 'réussi' else 'bg-warning'},
        {'name': 'Équipe terrain 2', 'submissions': max(0, metrics['received'] - 30), 'last_activity': 'Hier', 'status': 'À relancer', 'badge_class': 'bg-warning'},
    ]
    zones = [
        {'name': 'Zone 1', 'received': max(0, metrics['received'] - 20), 'target': max(1, metrics['cible'] or 200), 'rate': round(100 * max(0, metrics['received'] - 20) / max(1, metrics['cible'] or 200), 1), 'status': 'À risque', 'badge_class': 'bg-warning'},
        {'name': 'Zone 2', 'received': min(metrics['received'], max(0, metrics['cible'] // 2)), 'target': max(1, metrics['cible'] or 200), 'rate': round(100 * min(metrics['received'], max(0, metrics['cible'] // 2)) / max(1, metrics['cible'] or 200), 1), 'status': 'En cours', 'badge_class': 'bg-info'},
    ]

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

    stratified_summary = [
        {'label': 'Zone 1', 'received': max(0, metrics['received'] - 20), 'target': max(1, metrics['cible'] or 200), 'rate': round(100 * max(0, metrics['received'] - 20) / max(1, metrics['cible'] or 200), 1)},
        {'label': 'Zone 2', 'received': min(metrics['received'], max(0, metrics['cible'] // 2)), 'target': max(1, metrics['cible'] or 200), 'rate': round(100 * min(metrics['received'], max(0, metrics['cible'] // 2)) / max(1, metrics['cible'] or 200), 1)},
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
        'teams': teams,
        'alerts': alerts,
        'quality_items': quality_items,
        'sync_status': sync_payload,
        'stratified_summary': stratified_summary,
        'interpretation': interpretation,
    }
