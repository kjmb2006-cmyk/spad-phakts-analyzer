"""
SPAD Analyzer — Suivi multi-formulaires en tâche de fond

Contrairement à kobo_sync.py (qui suit UN formulaire à la fois — celui en
cours d'analyse), ce module suit PLUSIEURS formulaires simultanément pour
donner une vue d'ensemble façon « tableau de complétude » : nombre de
soumissions par formulaire, évolution dans le temps, cible optionnelle.

Périmètre volontairement restreint par rapport à un tableau de complétude
complet (type spadapp-zeta.vercel.app) : pas de notion d'établissement ni
de district — SPAD Analyzer n'a pas de référentiel de ce type ici (voir
modules/completeness.py pour le suivi établissement/district des 7
formulaires officiels). Ici, la cible est soit :
  - saisie librement par l'utilisateur (cible « manuelle ») ;
  - détectée automatiquement (cible « détectée ») si l'utilisateur indique
    que ce formulaire suivi correspond à l'un des 7 formulaires SPAD
    officiels (F5-F07) — la cible nationale du référentiel est alors reprise
    telle quelle, sans jamais interroger l'établissement du formulaire (ce
    module ne connaît que le compteur global, pas la répartition).

Sondage léger : interroge uniquement le compteur de soumissions
(`get_asset_info`), jamais les données complètes — pour rester rapide même
avec plusieurs formulaires suivis en parallèle.
"""
import threading
import datetime

_lock = threading.Lock()
_threads = {}       # uid -> (Thread, Event)
_trackers = {}       # uid -> dict d'état (voir _new_entry)

DEFAULT_INTERVAL = 120  # secondes — plus long que kobo_sync (un seul formulaire, plus léger)


def resolve_target(form_type, target_manuel):
    """Détermine (cible, source) à partir d'un type de formulaire SPAD optionnel
    et/ou d'une cible saisie librement. La détection automatique est
    prioritaire dès que form_type est un code SPAD reconnu."""
    if form_type:
        from modules import reference_data as rd
        ref = rd.load()
        nat = rd.national_targets(ref)
        if form_type in nat:
            return nat[form_type], "detectee"
    if target_manuel:
        return target_manuel, "manuelle"
    return None, None


def _new_entry(uid, name, target, instance, form_type=None, target_source=None):
    return {
        "uid": uid,
        "name": name,
        "instance": instance,
        "target": target,          # int ou None
        "form_type": form_type,    # code SPAD (F5..F07) si détecté, sinon None
        "target_source": target_source,  # 'detectee' | 'manuelle' | None
        "count": None,             # dernier effectif connu
        "history": [],             # [(HH:MM:SS, count), ...] — mémoire courte, non persistée
        "last_check_at": None,
        "last_success_at": None,
        "error": None,
        "added_at": datetime.datetime.now().strftime('%H:%M:%S'),
    }


def _status_for(entry):
    """Calcule un statut simple à partir du compteur et de la cible (si définie)."""
    if entry["count"] is None:
        return "inconnu"
    if not entry["target"]:
        return "suivi"
    if entry["count"] <= 0:
        return "zero"
    ratio = entry["count"] / entry["target"]
    if ratio >= 1:
        return "cible"
    return "en_cours"


def _loop(token, uid, instance, interval, stop_event):
    from modules.kobo_connector import get_asset_info
    while not stop_event.is_set():
        now = datetime.datetime.now().strftime('%H:%M:%S')
        try:
            res = get_asset_info(token, uid, instance=instance)
        except Exception as e:
            with _lock:
                if uid in _trackers:
                    _trackers[uid]["last_check_at"] = now
                    _trackers[uid]["error"] = str(e)
            if stop_event.wait(interval):
                break
            continue

        with _lock:
            if uid in _trackers:
                entry = _trackers[uid]
                entry["last_check_at"] = now
                if res.get("success"):
                    entry["last_success_at"] = now
                    entry["count"] = res.get("submission_count", entry["count"])
                    entry["error"] = None
                    entry["history"].append((now, entry["count"]))
                    entry["history"] = entry["history"][-30:]  # 30 derniers points suffisent pour une mini-tendance
                else:
                    entry["error"] = res.get("error", "Erreur inconnue")
        if stop_event.wait(interval):
            break


def add(token, instance, uid, name, target=None, interval=DEFAULT_INTERVAL, form_type=None):
    """Ajoute (ou remplace) un formulaire au suivi et démarre son polling.

    `target` est la cible saisie librement (ignorée si `form_type` est un
    code SPAD reconnu — la cible est alors détectée automatiquement, voir
    resolve_target())."""
    remove(uid)
    resolved_target, target_source = resolve_target(form_type, target)
    with _lock:
        _trackers[uid] = _new_entry(uid, name, resolved_target, instance,
                                     form_type=form_type, target_source=target_source)
    stop_event = threading.Event()
    t = threading.Thread(target=_loop, args=(token, uid, instance, interval, stop_event), daemon=True)
    with _lock:
        _threads[uid] = (t, stop_event)
    t.start()


def remove(uid):
    """Arrête le suivi d'un formulaire, s'il est actif."""
    with _lock:
        pair = _threads.pop(uid, None)
        _trackers.pop(uid, None)
    if pair:
        _, stop_event = pair
        stop_event.set()


def set_target(uid, target=None, form_type=None):
    resolved_target, target_source = resolve_target(form_type, target)
    with _lock:
        if uid in _trackers:
            _trackers[uid]["target"] = resolved_target
            _trackers[uid]["form_type"] = form_type
            _trackers[uid]["target_source"] = target_source


def list_tracked():
    """Snapshot sérialisable en JSON de tous les formulaires suivis."""
    with _lock:
        out = []
        for uid, entry in _trackers.items():
            e = dict(entry)
            e["status"] = _status_for(entry)
            e["pct"] = round(100 * entry["count"] / entry["target"], 1) if (entry["target"] and entry["count"] is not None) else None
            out.append(e)
    out.sort(key=lambda e: e["name"].lower())
    return out


def is_tracked(uid):
    with _lock:
        return uid in _trackers


def clear_all():
    """Arrête tous les suivis en cours — utilisé à la déconnexion KoboToolbox."""
    with _lock:
        uids = list(_threads.keys())
    for uid in uids:
        remove(uid)
