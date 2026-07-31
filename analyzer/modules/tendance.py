"""
SPAD Analyzer — Historique de complétude (tendance 30 jours)

Chaque calcul de complétude nationale (/completude/calculer) ajoute un point
d'historique — date + taux national par formulaire — à un fichier JSONL
persistant, local à l'installation (pas synchronisé, pas commité). Un seul
point par jour calendaire : recalculer plusieurs fois le même jour remplace
le point du jour, il ne l'empile pas.

Honnête sur ses limites : cette application desktop ne tourne pas en
continu — l'historique ne se constitue que les jours où l'utilisateur
ouvre l'app et clique sur « Calculer ». Tant que moins de 2 jours distincts
ne sont accumulés, aucune courbe n'a de sens à tracer (voir
completude_graphiques() côté route).
"""
import os
import json
import datetime

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_PATH = os.path.join(_BASE_DIR, 'data', 'completude_historique.jsonl')


def add_snapshot(national_summary):
    """Ajoute (ou remplace) le point d'historique du jour courant."""
    today = datetime.date.today().isoformat()
    existing = [e for e in _load_all() if e['date'] != today]
    existing.append({
        'date': today,
        'taux': {code: v.get('taux') for code, v in national_summary.items()},
    })
    existing.sort(key=lambda e: e['date'])
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
        for e in existing:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')


def _load_all():
    if not os.path.exists(HISTORY_PATH):
        return []
    out = []
    with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    out.sort(key=lambda e: e['date'])
    return out


def load_history(days=30):
    """Les `days` derniers points distincts (au plus un par jour)."""
    return _load_all()[-days:]
