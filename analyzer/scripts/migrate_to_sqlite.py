"""
SPAD Analyzer — Migration ponctuelle JSON -> SQLite (spad.db)

À lancer À LA MAIN sur le serveur, APRÈS un `git pull` mais AVANT le
redémarrage des services (systemctl restart spad-analyzer.service) —
jamais déclenché automatiquement au démarrage de l'app. Raison : les
modules migrés (form_mapping.py, forms_registry.py, accounts.py)
importent déjà tout seuls l'ancien .local.json dans spad.db au premier
accès si la table est vide (voir leur _bootstrap_from_legacy_json()/
_bootstrap()) — pratique pour le dev local et les tests, mais risqué au
tout premier déploiement en production : le worker gunicorn fraîchement
redémarré ET le timer systemd scripts/kobo_completude_refresh.py (relancé
toutes les 2 min, donc potentiellement dans la même fenêtre) verraient
alors TOUS LES DEUX la base vide et tenteraient le seed en même temps.

En lançant cette migration à la main avant tout redémarrage de service,
spad.db existe déjà et est déjà peuplé quand gunicorn et le timer
démarrent — leur propre bootstrap ne fait plus rien (table non vide),
aucune course possible. Idempotent : relancer ce script après une
première migration réussie ne fait rien (affiche juste les comptes déjà
en place) — sans danger si on l'exécute deux fois par erreur.

Ne modifie, ne renomme ni ne supprime JAMAIS les .local.json d'origine :
ils restent le filet de sécurité pour revenir en arrière (il suffit de
supprimer spad.db et redéployer le commit précédent).

Usage : venv/bin/python3 scripts/migrate_to_sqlite.py
"""
import os
import sys
import json

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ANALYZER_DIR = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _ANALYZER_DIR)

from modules import form_mapping, forms_registry, accounts


def _legacy_count(path):
    if not os.path.exists(path):
        return None  # fichier absent : rien à comparer, pas une erreur
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"    (impossible de relire {path} pour comparaison : {e})", file=sys.stderr)
        return None
    return len(data)


def main():
    checks = [
        ('form_mapping', form_mapping._LEGACY_JSON_PATH, lambda: len(form_mapping.load())),
        ('forms_registry', forms_registry._LEGACY_JSON_PATH, lambda: len(forms_registry.all_forms())),
        ('accounts', accounts._LEGACY_JSON_PATH, lambda: len(accounts.list_users())),
    ]

    print(f"Base SQLite cible : {form_mapping.DB_PATH}\n")

    mismatches = []
    for name, legacy_path, count_fn in checks:
        legacy_n = _legacy_count(legacy_path)
        db_n = count_fn()  # déclenche le bootstrap si la table était vide
        status = "importé" if legacy_n is None else (
            "OK" if legacy_n == db_n else "ÉCART — à vérifier")
        print(f"  {name:16s} : {db_n:4d} ligne(s) en base"
              + (f" (vs {legacy_n} dans {os.path.basename(legacy_path)}) [{status}]"
                 if legacy_n is not None else " (pas d'ancien fichier JSON — seed par défaut)"))
        if legacy_n is not None and legacy_n != db_n:
            mismatches.append(name)

    print()
    if mismatches:
        print(f"⚠️  Écart détecté sur : {', '.join(mismatches)} — vérifiez avant de redémarrer les services.",
              file=sys.stderr)
        return 1
    print("Migration vérifiée — vous pouvez maintenant redémarrer les services "
          "(systemctl restart spad-analyzer.service, ou ./scripts/deploy-lws.sh).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
