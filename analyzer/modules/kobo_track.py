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

Persistance : contrairement à form_mapping.py/forms_registry.py (relus
depuis le disque à chaque appel, aucun état en mémoire), ce module maintient
un état vivant muté en continu par des threads de sondage — le disque n'est
ici qu'une sauvegarde de secours pour retrouver la liste des formulaires
suivis (uid, nom, cible, type) après un redémarrage complet de l'app, sans
quoi elle repartait de zéro à chaque fois (et cassait par ricochet le menu
de correspondance de Complétude nationale, qui ne propose que les
formulaires actuellement suivis). Le sondage en tâche de fond, lui, ne peut
reprendre qu'une fois un token KoboToolbox de nouveau disponible en session
— voir resume(), appelé depuis app.py dès qu'une connexion Kobo s'établit.
"""
import os
import json
import threading
import datetime

_lock = threading.Lock()
_threads = {}       # uid -> (Thread, Event)
_trackers = {}       # uid -> dict d'état (voir _new_entry)

DEFAULT_INTERVAL = 120  # secondes — plus long que kobo_sync (un seul formulaire, plus léger)

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_MODULE_DIR)
TRACK_PATH = os.path.join(_ANALYZER_DIR, 'data', 'reference', 'kobo_track.local.json')

# Champs persistés : ce qui redéfinit le suivi (uid implicite via la clé du
# dict, nom, cible, type). L'historique (mini-tendance) et les horodatages
# d'erreur/sondage sont volontairement exclus — obsolètes dès le redémarrage,
# ils redeviennent pertinents en quelques cycles de sondage.
_PERSISTED_FIELDS = ('name', 'instance', 'target', 'form_type', 'target_source', 'count')


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


def _load_persisted():
    if not os.path.exists(TRACK_PATH):
        return {}
    try:
        with open(TRACK_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_persisted():
    with _lock:
        data = {uid: {k: entry.get(k) for k in _PERSISTED_FIELDS} for uid, entry in _trackers.items()}
    os.makedirs(os.path.dirname(TRACK_PATH), exist_ok=True)
    try:
        with open(TRACK_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # best-effort — un suivi non persisté ne doit jamais faire planter l'app


def _restore_from_disk():
    """Recharge les formulaires suivis persistés au démarrage du process —
    remplit _trackers (donc /suivi et la correspondance de Complétude les
    affichent immédiatement) mais ne démarre aucun thread de sondage : aucun
    token KoboToolbox n'est disponible à l'import, voir resume()."""
    for uid, saved in _load_persisted().items():
        entry = _new_entry(uid, saved.get('name', uid), saved.get('target'), saved.get('instance'),
                            form_type=saved.get('form_type'), target_source=saved.get('target_source'))
        entry['count'] = saved.get('count')
        _trackers[uid] = entry


def resume(token, instance=None):
    """(Ré)-démarre le sondage pour les formulaires restaurés depuis le
    disque qui n'ont pas encore de thread actif — à appeler dès qu'un token
    KoboToolbox redevient disponible en session (app.py : auto_kobo_connect()
    et kobo_connect()). Idempotent : ignore les uid déjà suivis activement."""
    with _lock:
        candidates = [uid for uid in _trackers if uid not in _threads]
    for uid in candidates:
        with _lock:
            entry = _trackers.get(uid)
            already = uid in _threads
        if not entry or already:
            continue
        uid_instance = entry.get('instance') or instance
        stop_event = threading.Event()
        t = threading.Thread(target=_loop, args=(token, uid, uid_instance, DEFAULT_INTERVAL, stop_event), daemon=True)
        with _lock:
            if uid in _threads or uid not in _trackers:
                continue
            _threads[uid] = (t, stop_event)
        t.start()


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
        if res.get("success"):
            _save_persisted()  # garde le dernier effectif connu à jour sur disque
        elif res.get("error") == "Formulaire introuvable.":
            # 404 DÉFINITIF de Kobo (get_asset_info le distingue déjà des
            # erreurs réseau/token transitoires) : le formulaire a été
            # supprimé côté Kobo, cet uid ne reviendra jamais. Retirer
            # automatiquement du suivi plutôt que sonder indéfiniment un
            # formulaire qui n'existe plus (cas réel signalé : supprimé
            # dans la Bibliothèque Kobo, restait bloqué sur "non déployé"
            # dans Suivi multi-formulaires sans jamais disparaître).
            remove(uid)
            break
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
    _save_persisted()
    stop_event = threading.Event()
    t = threading.Thread(target=_loop, args=(token, uid, instance, interval, stop_event), daemon=True)
    with _lock:
        _threads[uid] = (t, stop_event)
    t.start()


def remove(uid):
    """Arrête le suivi d'un formulaire, s'il est actif."""
    with _lock:
        pair = _threads.pop(uid, None)
        existed = _trackers.pop(uid, None) is not None
    if pair:
        _, stop_event = pair
        stop_event.set()
    if existed:
        _save_persisted()


def set_target(uid, target=None, form_type=None):
    resolved_target, target_source = resolve_target(form_type, target)
    with _lock:
        if uid in _trackers:
            _trackers[uid]["target"] = resolved_target
            _trackers[uid]["form_type"] = form_type
            _trackers[uid]["target_source"] = target_source
    _save_persisted()


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
        uids = list(set(_trackers.keys()) | set(_threads.keys()))
    for uid in uids:
        remove(uid)


_restore_from_disk()
