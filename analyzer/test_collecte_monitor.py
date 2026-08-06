import json
import tempfile
from pathlib import Path

from modules.collecte_monitor import (
    load_state,
    save_state,
    append_sync_event,
    build_dashboard_metrics,
    build_collecte_views,
)


def test_append_sync_event_and_dashboard_metrics():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / 'collecte_state.json'
        state = load_state(path)
        state = append_sync_event(state, path, form_name='Formulaire A', count=120, status='réussi', target=200)
        state = append_sync_event(state, path, form_name='Formulaire A', count=150, status='réussi', target=200)

        assert state['target'] == 200
        assert state['last_sync_count'] == 150
        assert len(state['history']) == 2

        metrics = build_dashboard_metrics(state, current_count=150)
        assert metrics['received'] == 150
        assert metrics['cible'] == 200
        assert metrics['taux'] == 75.0
        assert len(metrics['evolution']) == 2
        assert metrics['zones'][0]['name'] == 'Zone 1'


def test_save_state_persists_to_disk():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / 'collecte_state.json'
        state = {'target': 500, 'history': []}
        save_state(path, state)
        loaded = load_state(path)
        assert loaded['target'] == 500
        assert isinstance(loaded['history'], list)


def test_build_collecte_views_uses_real_state_and_metadata():
    state = {
        'target': 200,
        'history': [{'form_name': 'Collecte F5', 'count': 80, 'status': 'réussi'}],
        'last_sync_at': '2026-08-04 10:00',
        'last_sync_count': 80,
        'last_sync_status': 'réussi',
        'last_form_name': 'Collecte F5',
    }
    payload = build_collecte_views(state, current_count=80, data_meta={'n_vars': 24, 'missing_pct': 8.5})

    assert payload['geo_items'][0]['name'] == 'Zone 1'
    assert payload['teams'][0]['name'] == 'Équipe terrain 1'
    assert payload['alerts'][0]['type'] == 'Synchronisation réussie'
    assert payload['quality_items'][0]['variable'] == 'Observations'
    assert payload['stratified_summary'][0]['label'] == 'Zone 1'
    assert payload['interpretation']['risk_level'] in {'faible', 'moyen', 'élevé'}
    assert 'recommandation' in payload['interpretation']


def test_build_collecte_views_includes_sync_status():
    state = {
        'target': 200,
        'history': [{'form_name': 'Collecte F5', 'count': 80, 'status': 'réussi'}],
        'last_sync_at': '2026-08-04 10:00',
        'last_sync_count': 80,
        'last_sync_status': 'réussi',
        'last_form_name': 'Collecte F5',
    }
    payload = build_collecte_views(
        state,
        current_count=80,
        data_meta={'n_vars': 24, 'missing_pct': 8.5},
        sync_status={'active': True, 'has_pending': True, 'available_n_obs': 95},
    )

    assert payload['sync_status']['active'] is True
    assert payload['sync_status']['has_pending'] is True
    assert payload['sync_status']['available_n_obs'] == 95
