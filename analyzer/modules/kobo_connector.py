"""
SPAD Analyzer — Connecteur KoboToolbox
Compatible toutes instances :
  • kf.kobotoolbox.org              (instance publique mondiale)
  • eu.kobotoolbox.org              (instance Europe RGPD)
  • kobo.humanitarianresponse.info  (ONU/WHO/GPEI)
  • kobonew.humanitarianresponse.info
  • Instance personnalisée (saisie par l'utilisateur)
"""
import requests
import urllib3
import pandas as pd
from modules.data_loader import clean_kobo_dataframe

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Toutes les instances KoboToolbox connues (testées dans l'ordre)
KOBO_INSTANCES = [
    "https://kf.kobotoolbox.org",
    "https://eu.kobotoolbox.org",
    "https://kobo.humanitarianresponse.info",
    "https://kobonew.humanitarianresponse.info",
]

# Endpoints testés pour valider le token
# /api/v2/me/ retourne username uniquement si authentifié → meilleur indicateur
AUTH_ENDPOINTS = [
    "/api/v2/me/",
    "/api/v2/assets/?limit=1&format=json",
]

TIMEOUT = 25


def _normalize_instance(base):
    """Ajoute le schéma manquant (ex. KOBO_INSTANCE=kf.kobotoolbox.org fourni
    sans https:// dans l'environnement serveur) — sans ça, requests échoue
    avec 'Invalid URL... No scheme supplied' au lieu d'une erreur claire.
    validate_token()/_instances_to_try() le faisaient déjà pour l'instance
    personnalisée saisie interactivement ; get_asset_info()/load_data()/
    list_assets() ne le faisaient pas pour un instance= passé directement
    (ex. depuis la variable d'environnement KOBO_INSTANCE, utilisée pour les
    calculs automatisés sans session Kobo active)."""
    if not base:
        return base
    base = base.rstrip('/')
    if not base.startswith('http'):
        base = 'https://' + base
    return base


def _instances_to_try(custom_instance=None):
    """Retourne la liste d'instances à tester, avec instance personnalisée en tête."""
    if custom_instance:
        base = _normalize_instance(custom_instance)
        return [base] + [i for i in KOBO_INSTANCES if i != base]
    return KOBO_INSTANCES


def _get(url, token):
    """Requête GET avec fallback SSL désactivé (proxy ONU/WHO)."""
    h = {"Authorization": f"Token {token}", "Accept": "application/json"}
    try:
        return requests.get(url, headers=h, timeout=TIMEOUT, verify=True)
    except requests.exceptions.SSLError:
        return requests.get(url, headers=h, timeout=TIMEOUT, verify=False)


def _detect(token):
    """
    Détecte l'instance et l'endpoint valides.
    Retourne (base_url, endpoint) ou (None, None).
    """
    for base in _instances_to_try():
        for ep in AUTH_ENDPOINTS:
            try:
                r = _get(f"{base}{ep}", token)
                if r.status_code == 200:
                    return base, ep
                elif r.status_code == 401:
                    return None, "token_invalide"
            except Exception:
                continue
    return None, None


def diagnose(token, custom_instance=None):
    """Diagnostic détaillé — teste chaque instance × endpoint."""
    results = []
    for base in _instances_to_try(custom_instance):
        entry = {"instance": base, "endpoints": []}
        reachable = False
        for ep in AUTH_ENDPOINTS:
            ep_result = {"endpoint": ep, "status": None, "http_code": None, "error": None}
            try:
                r = _get(f"{base}{ep}", token)
                ep_result["http_code"] = r.status_code
                if r.status_code == 200:
                    ep_result["status"]   = "ok"
                    entry["username"]     = r.json().get("username", "")
                    reachable             = True
                elif r.status_code == 401:
                    ep_result["status"] = "token_invalide"
                    ep_result["error"]  = "Token non reconnu."
                    reachable           = True
                else:
                    ep_result["status"] = f"http_{r.status_code}"
                    ep_result["error"]  = f"HTTP {r.status_code}"
            except requests.exceptions.SSLError as e:
                ep_result["status"] = "ssl_error"
                ep_result["error"]  = str(e)[:100]
            except requests.exceptions.ConnectionError:
                ep_result["status"] = "injoignable"
                ep_result["error"]  = "Connexion refusée."
            except requests.exceptions.Timeout:
                ep_result["status"] = "timeout"
                ep_result["error"]  = f"Timeout {TIMEOUT}s"
            except Exception as e:
                ep_result["status"] = "erreur"
                ep_result["error"]  = str(e)[:100]
            entry["endpoints"].append(ep_result)
        entry["reachable"] = reachable
        results.append(entry)
    return results


def _instance_label(base):
    if "humanitarianresponse" in base:
        return "Humanitaire ONU/WHO"
    if "eu.kobotoolbox" in base:
        return "Europe (RGPD)"
    return base.replace("https://", "")


def validate_token(token, custom_instance=None):
    """
    Valide le token sur toutes les instances connues + instance personnalisée.
    Stratégie :
      1. /api/v2/me/ → retourne username seulement si authentifié → preuve fiable
      2. Fallback /api/v2/assets/ → accepté uniquement si count > 0 (formulaires présents)
    """
    token_invalid_seen = False
    instances = _instances_to_try(custom_instance)

    # Passe 1 : /api/v2/me/ — preuve d'authentification la plus fiable
    for base in instances:
        try:
            r = _get(f"{base}/api/v2/me/", token)
            if r.status_code == 200:
                data = r.json()
                username = data.get("username", "")
                if username:
                    return {
                        "valid":          True,
                        "username":       username,
                        "email":          data.get("email", ""),
                        "instance":       base,
                        "instance_label": _instance_label(base),
                    }
            elif r.status_code in (401, 403):
                token_invalid_seen = True
        except Exception:
            continue

    # Passe 2 : /api/v2/assets/ — accepté seulement si au moins 1 formulaire
    for base in instances:
        try:
            r = _get(f"{base}/api/v2/assets/?limit=1&format=json", token)
            if r.status_code == 200:
                data = r.json()
                count = data.get("count", 0)
                if count and count > 0:
                    name = data["results"][0].get("owner__username", "") if data.get("results") else ""
                    return {
                        "valid":          True,
                        "username":       name or "—",
                        "email":          "",
                        "instance":       base,
                        "instance_label": _instance_label(base),
                    }
            elif r.status_code in (401, 403):
                token_invalid_seen = True
        except Exception:
            continue

    if token_invalid_seen:
        return {
            "valid": False,
            "error": (
                "Token invalide ou expiré. Régénérez votre clé API :\n"
                "KoboToolbox → Profil → Paramètres du compte → Sécurité → Clé API."
            ),
        }

    return {
        "valid": False,
        "error": (
            "Aucune instance KoboToolbox n'a reconnu ce token. "
            "Vérifiez l'URL de votre instance dans le champ dédié."
        ),
    }


def detect_instance(token, custom_instance=None):
    instances = _instances_to_try(custom_instance)
    for base in instances:
        try:
            r = _get(f"{base}/api/v2/me/", token)
            if r.status_code == 200 and r.json().get("username"):
                return base
        except Exception:
            continue
    for base in instances:
        try:
            r = _get(f"{base}/api/v2/assets/?limit=1&format=json", token)
            if r.status_code == 200 and r.json().get("count", 0) > 0:
                return base
        except Exception:
            continue
    return None


def list_assets(token, instance=None, custom_instance=None):
    """
    Liste tous les formulaires accessibles.
    Charge toutes les pages (pagination automatique).
    """
    base = _normalize_instance(instance) or detect_instance(token, custom_instance)
    if not base:
        return {"success": False, "error": "Aucune instance accessible."}

    # Types d'assets à inclure (survey = formulaire principal)
    TYPES_VOULUS = {"survey", "template"}

    url    = f"{base}/api/v2/assets/?format=json&limit=200"
    assets = []

    try:
        while url:
            r = _get(url, token)
            if r.status_code != 200:
                return {"success": False, "error": f"Erreur HTTP {r.status_code}."}

            data = r.json()
            for a in data.get("results", []):
                asset_type = a.get("asset_type", "survey")
                # Inclure tous les types si le filtre ne donne rien
                assets.append({
                    "uid":              a.get("uid", ""),
                    "name":             a.get("name", "Sans nom"),
                    "asset_type":       asset_type,
                    "submission_count": a.get("deployment__submission_count", 0),
                    "date_modified":    (a.get("date_modified", "") or "")[:10],
                    "deployed":         a.get("has_deployment", False),
                })
            url = data.get("next")  # pagination automatique

        if not assets:
            return {"success": False,
                    "error": "Aucun formulaire trouvé sur ce compte KoboToolbox."}

        # Tri : déployés et plus de soumissions en premier
        assets.sort(key=lambda x: (not x["deployed"], -x["submission_count"]))

        return {
            "success":  True,
            "assets":   assets,
            "total":    len(assets),
            "instance": base,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_asset_info(token, uid, instance=None):
    base = _normalize_instance(instance) or detect_instance(token)
    if not base:
        return {"success": False, "error": "Instance introuvable."}
    try:
        r = _get(f"{base}/api/v2/assets/{uid}/?format=json", token)
        if r.status_code == 404:
            return {"success": False, "error": "Formulaire introuvable."}
        if r.status_code != 200:
            return {"success": False, "error": f"Erreur HTTP {r.status_code}."}
        d = r.json()
        return {
            "success":          True,
            "uid":              uid,
            "name":             d.get("name", ""),
            "submission_count": d.get("deployment__submission_count", 0),
            "date_modified":    (d.get("date_modified", "") or "")[:10],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def load_data(token, uid, instance=None, limit=30000):
    base = _normalize_instance(instance) or detect_instance(token)
    if not base:
        return {"success": False, "error": "Instance KoboToolbox introuvable."}
    url   = f"{base}/api/v2/assets/{uid}/data/?format=json&limit=3000"
    all_r = []
    pages = 0
    try:
        while url:
            r = _get(url, token)
            if r.status_code == 404:
                return {"success": False, "error": "Formulaire introuvable."}
            if r.status_code == 403:
                return {"success": False, "error": "Accès refusé."}
            if r.status_code == 401:
                return {"success": False, "error": "Token invalide."}
            if r.status_code != 200:
                return {"success": False, "error": f"Erreur HTTP {r.status_code}."}
            data = r.json()
            all_r.extend(data.get("results", []))
            pages += 1
            url = data.get("next")
            if len(all_r) >= limit:
                break
        if not all_r:
            return {"success": False, "error": "Aucune soumission disponible."}
        df = clean_kobo_dataframe(pd.DataFrame(all_r))
        return {
            "success": True, "df": df,
            "n_obs":   len(df), "n_vars": len(df.columns),
            "pages":   pages,   "instance": base,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── Déploiement d'un XLSForm ─────────────────────────────────────────────────

def deploy_xlsform(token, xls_path, name=None, instance=None, custom_instance=None):
    """
    Importe un fichier XLSForm (.xlsx) dans KoboToolbox via POST /api/v2/imports/.
    Retourne {'success': True, 'uid': ..., 'url': ..., 'instance': ...}
    ou {'success': False, 'error': ...}.
    """
    import os, time
    if not os.path.exists(xls_path):
        return {"success": False, "error": f"Fichier introuvable : {xls_path}"}

    # Détecte l'instance correcte si pas fournie
    base = _normalize_instance(instance)
    if not base:
        det = _detect(token)
        base = det.get('instance') if det.get('valid') else None
    if not base:
        for b in _instances_to_try(custom_instance):
            try:
                r = _get(f"{b}/api/v2/me/", token)
                if r.status_code == 200 and r.json().get('username'):
                    base = b
                    break
            except Exception:
                continue
    if not base:
        return {"success": False, "error": "Aucune instance KoboToolbox valide pour ce token."}

    # 1. Upload via /api/v2/imports/ (KoboToolbox a retiré l'ancien endpoint
    # sans préfixe /api/v2/ — désormais 410 Gone, cas réel constaté)
    headers = {"Authorization": f"Token {token}"}
    upload_url = f"{base}/api/v2/imports/"
    try:
        with open(xls_path, 'rb') as f:
            files = {'file': (os.path.basename(xls_path), f,
                              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            data = {}
            if name:
                data['name'] = name
            try:
                r = requests.post(upload_url, headers=headers, files=files, data=data,
                                  timeout=60, verify=True)
            except requests.exceptions.SSLError:
                r = requests.post(upload_url, headers=headers, files=files, data=data,
                                  timeout=60, verify=False)
        if r.status_code not in (200, 201):
            return {"success": False, "error": f"Upload échoué (HTTP {r.status_code}) : {r.text[:300]}"}
        imp = r.json()
        import_uid = imp.get('uid') or imp.get('url', '').rstrip('/').split('/')[-1]
        if not import_uid:
            return {"success": False, "error": f"Réponse import sans uid : {str(imp)[:200]}"}
    except Exception as e:
        return {"success": False, "error": f"Échec de l'upload : {e}"}

    # 2. Polling : attendre que l'import soit terminé
    poll_url = f"{base}/api/v2/imports/{import_uid}/"
    asset_uid = None
    deadline = time.time() + 60
    last_status = None
    while time.time() < deadline:
        try:
            try:
                rp = requests.get(poll_url, headers=headers, timeout=20, verify=True)
            except requests.exceptions.SSLError:
                rp = requests.get(poll_url, headers=headers, timeout=20, verify=False)
            if rp.status_code != 200:
                time.sleep(1.5)
                continue
            jp = rp.json()
            last_status = jp.get('status')
            if last_status == 'complete':
                msgs = jp.get('messages', {}) or {}
                created = msgs.get('created') or []
                if created:
                    asset_uid = created[0].get('uid') or created[0].get('url', '').rstrip('/').split('/')[-1]
                else:
                    asset_uid = jp.get('asset_uid') or jp.get('uid')
                break
            elif last_status in ('error', 'failed'):
                msgs = jp.get('messages', {}) or {}
                err_msg = (msgs.get('error') or msgs.get('exception')
                           or jp.get('detail') or "Erreur d'import inconnue")
                return {"success": False, "error": f"Import KoboToolbox échoué : {err_msg}"}
        except Exception:
            pass
        time.sleep(1.5)

    if not asset_uid:
        return {"success": False, "error": f"Import non terminé après 60 s (statut={last_status})."}

    # 3. Déployer pour rendre le formulaire collectable
    deploy_url = f"{base}/api/v2/assets/{asset_uid}/deployment/"
    deploy_payload = {'active': True}
    try:
        try:
            rd = requests.post(deploy_url, headers=headers, json=deploy_payload,
                               timeout=30, verify=True)
        except requests.exceptions.SSLError:
            rd = requests.post(deploy_url, headers=headers, json=deploy_payload,
                               timeout=30, verify=False)
        deployed = rd.status_code in (200, 201)
    except Exception:
        deployed = False

    return {
        "success": True,
        "uid": asset_uid,
        "url": f"{base}/#/forms/{asset_uid}",
        "deployed": deployed,
        "instance": base,
    }
