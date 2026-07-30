"""
SPAD Analyzer — Suivi multi-formulaires en tâche de fond

Contrairement à kobo_sync.py (qui suit UN formulaire à la fois — celui en
cours d'analyse), ce module suit PLUSIEURS formulaires simultanément pour
donner une vue d'ensemble façon « tableau de complétude » : nombre de
soumissions par formulaire, évolution dans le temps, cible optionnelle.

Périmètre volontairement restreint par rapport à un tableau de complétude
complet (type spadapp-zeta.vercel.app) : pas de notion d'établissement ni
de district — SPAD Analyzer n'a pas de référentiel de ce type. Ici, une
« cible » est un simple nombre optionnel saisi par l'utilisateur pour un
formulaire donné (ex. 1800 soumissions attendues), pas une cible calculée
par établissement.

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


def _new_entry(uid, name, target, instance):
    return {
        "uid": uid,
        "name": name,
        "instance": instance,
        "target": target,          # int ou None
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


def add(token, instance, uid, name, target=None, interval=DEFAULT_INTERVAL):
    """Ajoute (ou remplace) un formulaire au suivi et démarre son polling."""
    remove(uid)
    with _lock:
        _trackers[uid] = _new_entry(uid, name, target, instance)
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


def set_target(uid, target):
    with _lock:
        if uid in _trackers:
            _trackers[uid]["target"] = target


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
