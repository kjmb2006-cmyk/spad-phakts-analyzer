"""
SPAD Analyzer — Synchronisation automatique KoboToolbox
Interroge périodiquement KoboToolbox en tâche de fond (polling) pour
détecter de nouvelles soumissions sans action manuelle de l'utilisateur.

Application desktop mono-utilisateur : pas de webhook possible (pas d'URL
publique) — l'actualisation « quasi temps réel » repose donc sur un
polling à intervalle réglable, avec application explicite des nouvelles
données par l'utilisateur (jamais de remplacement silencieux d'un jeu de
données en cours d'analyse).
"""
import threading
import datetime

_lock = threading.Lock()
_thread = None
_stop_event = None

_state = {
    "active":           False,
    "uid":               None,
    "name":              None,
    "instance":          None,
    "interval":          300,   # secondes
    "last_check_at":     None,  # dernière tentative de sondage
    "last_success_at":   None,  # dernier sondage réussi
    "baseline_n_obs":    None,  # effectif de la donnée actuellement appliquée
    "available_n_obs":   None,  # effectif vu au dernier sondage réussi
    "error":             None,
}
_pending_df = None  # DataFrame en attente d'application (hors _state pour ne pas le sérialiser par erreur)

# Callback optionnel appelé DIRECTEMENT depuis le thread de sondage quand de
# nouvelles données sont détectées (jamais sérialisé dans _state — une
# fonction Python, pas une donnée JSON). Utilisé uniquement par "Suivi d'un
# formulaire" (voir app.py::collecte_sync_auto()) pour appliquer les
# nouvelles soumissions sans dépendre d'un onglet de navigateur ouvert — le
# thread n'a pas accès à la session Flask (liée à une requête HTTP), donc ce
# callback écrit directement sur des CHEMINS DE FICHIERS fixes plutôt que
# dans `session`. La page "Aperçu des données" (kobo_sync_start(), sans
# callback) garde elle son comportement d'origine : ne jamais remplacer
# silencieusement le jeu de données en cours d'analyse, application
# manuelle via le bouton "Appliquer".
_on_new_data = None


def _loop(token, uid, instance, interval, stop_event):
    from modules.kobo_connector import load_data
    while not stop_event.is_set():
        if stop_event.wait(interval):
            break
        now = datetime.datetime.now().strftime('%H:%M:%S')
        try:
            res = load_data(token, uid, instance=instance)
        except Exception as e:
            with _lock:
                _state["last_check_at"] = now
                _state["error"] = str(e)
            continue

        global _pending_df
        with _lock:
            _state["last_check_at"] = now
            if res.get("success"):
                _state["last_success_at"]  = now
                _state["available_n_obs"]  = res["n_obs"]
                _state["error"]            = None
                if res["n_obs"] != _state["baseline_n_obs"]:
                    if _on_new_data is not None:
                        try:
                            _on_new_data(res["df"], _state["name"])
                            _state["baseline_n_obs"] = res["n_obs"]
                            _pending_df = None
                        except Exception as e:
                            _state["error"] = f"Application automatique échouée : {e}"
                            _pending_df = res["df"]
                    else:
                        _pending_df = res["df"]
                else:
                    _pending_df = None
            else:
                _state["error"] = res.get("error", "Erreur inconnue")


def start(token, uid, instance, name, interval, baseline_n_obs, on_new_data=None):
    """Démarre (ou redémarre) le polling en tâche de fond pour ce formulaire.

    on_new_data(df, name), si fourni, est appelé depuis le thread dès qu'une
    nouvelle soumission est détectée, pour l'appliquer immédiatement côté
    serveur (voir note ci-dessus) — sinon comportement d'origine (attente
    d'une application manuelle via pop_pending_df())."""
    global _thread, _stop_event, _pending_df, _on_new_data
    stop()
    interval = max(60, min(int(interval or 300), 3600))
    with _lock:
        _state.update(
            active=True, uid=uid, name=name, instance=instance,
            interval=interval, baseline_n_obs=baseline_n_obs,
            available_n_obs=baseline_n_obs,
            last_check_at=None, last_success_at=None, error=None,
        )
        _pending_df = None
    _on_new_data = on_new_data
    _stop_event = threading.Event()
    _thread = threading.Thread(
        target=_loop, args=(token, uid, instance, interval, _stop_event), daemon=True
    )
    _thread.start()


def stop():
    """Arrête le polling en cours, s'il y en a un."""
    global _thread, _stop_event, _pending_df, _on_new_data
    if _stop_event is not None:
        _stop_event.set()
    _thread = None
    _stop_event = None
    _pending_df = None
    _on_new_data = None
    with _lock:
        _state["active"] = False


def status():
    """État courant, sérialisable en JSON (sans le DataFrame)."""
    with _lock:
        s = dict(_state)
        s["has_pending"] = _pending_df is not None
    return s


def set_baseline(n_obs):
    """Réaligne le compteur de référence (ex. après un rafraîchissement manuel)."""
    global _pending_df
    with _lock:
        _state["baseline_n_obs"]  = n_obs
        _state["available_n_obs"] = n_obs
        _pending_df = None


def pop_pending_df():
    """Consomme et renvoie le DataFrame en attente (ou None) ; remet la référence à jour."""
    global _pending_df
    with _lock:
        df = _pending_df
        if df is not None:
            _state["baseline_n_obs"] = _state["available_n_obs"]
            _pending_df = None
    return df
