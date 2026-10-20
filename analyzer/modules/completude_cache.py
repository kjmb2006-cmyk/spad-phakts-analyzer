"""
SPAD Analyzer — Cache partagé de la Complétude nationale

Un seul fichier canonique (completude_autorefresh.json, dans UPLOAD_FOLDER)
sert de source pour toutes les vues de Complétude. form_mapping.py (la
correspondance formulaire SPAD -> Kobo) est GLOBAL, pas propre à une
session : il n'existe donc qu'UN calcul valide à un instant donné, pas un
par utilisateur. Ce fichier est tenu à jour automatiquement par un timer
systemd côté serveur (scripts/kobo_completude_refresh.py, toutes les 2 min)
et peut être rafraîchi immédiatement via le bouton « Calculer » de l'appli
(app.py::completude_calculer()) — les deux écrivent ce même fichier via
build_cache()/save_cache() ci-dessous, pour ne jamais diverger (c'est cette
divergence qui avait rendu le script silencieusement obsolète : son propre
calcul manquait les clés 'roster'/'roster_families'/'named_roster' ajoutées
depuis à la route Flask).

Avant ce module, _load_completude_cache() (app.py) ne lisait qu'un chemin
stocké en session — un filet de sécurité "session -> fichier le plus
récent du dossier" avait été retiré (commit ac2d60d) après un bug réel où
une session neuve affichait le calcul (potentiellement sans rapport) d'un
AUTRE utilisateur. Ce risque ne s'applique pas ici : comme le mapping est
déjà global, il n'y a jamais deux calculs "légitimement différents" en
même temps — seulement des instantanés plus ou moins récents du même
calcul canonique.
"""
import os
import json
import tempfile

from modules import completeness as cp
from modules import forms_registry
from modules.kobo_connector import load_data as _kobo_load_data

CACHE_FILENAME = 'completude_autorefresh.json'


def cache_path(upload_folder):
    return os.path.join(upload_folder, CACHE_FILENAME)


def build_cache(ref, token, instance, mapping):
    """Télécharge chaque formulaire mappé et calcule toutes les vues de
    complétude en une seule passe (évite de retirer les mêmes données
    depuis Kobo pour chaque vue nationale/région/district/roster...).

    Renvoie (cache_dict ou None, errors, n_ok) — cache_dict est None
    seulement si AUCUN formulaire mappé n'a pu être chargé, pour que
    l'appelant puisse choisir de conserver le cache existant plutôt que de
    l'écraser par un résultat vide sur une panne Kobo passagère."""
    form_dataframes = {}
    errors = []
    for code, uid in mapping.items():
        form = forms_registry.get(code)
        if not form or not form.get('active', True):
            # Code désactivé (ou supprimé) du registre dont la correspondance
            # Kobo n'a jamais été nettoyée — l'interroger ne sert à rien et
            # peut échouer bruyamment pour un code qui n'apparaît plus nulle
            # part dans l'UI (voir même garde dans l'ancienne route Flask).
            continue
        is_roster = form.get('grain') in ('enqueteur', 'superviseur')
        keep_cols = ('_submission_time', '_submitted_by') if is_roster else ()
        res = _kobo_load_data(token, uid, instance=instance, keep_meta_cols=keep_cols)
        if res.get('success'):
            form_dataframes[code] = res['df']
        else:
            errors.append(f"{code} : {res.get('error', 'erreur inconnue')}")

    if not form_dataframes:
        return None, errors, 0

    cache = {
        'national':         cp.national_summary(ref, form_dataframes),
        'district':         cp.district_table(ref, form_dataframes),
        'region':           cp.region_table(ref, form_dataframes),
        'etablissement':    cp.etablissement_table(ref, form_dataframes),
        'enqueteur':        cp.enqueteur_table(ref, form_dataframes),
        'superviseur':      cp.superviseur_table(ref, form_dataframes),
        'roster':           cp.all_roster_by_district(ref, form_dataframes),
        'roster_families':  cp.all_roster_families(ref, form_dataframes),
        'named_roster':     cp.all_named_rosters(ref, form_dataframes),
        'anomalies_zero':   cp.all_anomalies_zero(ref, form_dataframes),
        'anomalies_excess': cp.all_anomalies_excess(ref, form_dataframes),
        'export':           cp.export_rows(ref, form_dataframes),
    }
    return cache, errors, len(form_dataframes)


def save_cache(cache, upload_folder, computed_at):
    """Écriture atomique (fichier temporaire + remplacement) : ce cache est
    désormais relu en continu par toutes les vues Complétude — sans écriture
    atomique, une lecture concurrente pourrait tomber sur un JSON tronqué
    pendant que le timer (ou le bouton Calculer) réécrit le fichier."""
    cache = dict(cache)
    cache['computed_at'] = computed_at
    os.makedirs(upload_folder, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=upload_folder, prefix='.completude_tmp_')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(tmp_path, cache_path(upload_folder))
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise


def load_cache(upload_folder):
    path = cache_path(upload_folder)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None
