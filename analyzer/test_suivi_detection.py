#!/usr/bin/env python3
"""
Test script — détection automatique du type SPAD dans « Suivi
multi-formulaires » (modules/reference_data.py::guess_form_type(), route
/suivi).

Contexte : la colonne « Type (détection auto.) » ne détectait en réalité
rien — l'utilisateur partait d'un menu vide et pouvait associer n'importe
quel type à n'importe quel formulaire sans avertissement (reproduit : F5
assigné à un formulaire de vaccination ménages, etc.). Vérifie que :
  - guess_form_type() reconnaît les 7 formulaires SPAD officiels à partir
    de leur nom Kobo réel, et ne devine rien pour un nom sans rapport
  - la page /suivi pré-sélectionne le type deviné dans le menu déroulant
  - un type suivi manuellement qui ne correspond pas au nom du formulaire
    déclenche un avertissement visible
  - le même type assigné à 2 formulaires suivis différents déclenche aussi
    un avertissement
"""
from modules import reference_data as rd

print("=" * 70)
print("TEST — Détection automatique du type (Suivi multi-formulaires)")
print("=" * 70)

NOMS_REELS = {
    'F5':  '5_PNLTA_SPAD_Fiche_Femmes_Enceintes_Allaitantes_Tabac',
    'F6':  '6_PNLTA_SPAD_Fiche_CAP_Personnel_de_Sante_Tabac',
    'F7':  '7_PEV_SPAD_Fiche_Menage_Non_Vaccination',
    'F8':  '8_PEV_SPAD_Fiche_Etablissement_Non_Vaccination',
    'F01': 'F01 - RDM SPAD - Fiche district',
    'F02': 'F02 - RDM SPAD - Fiche établissement',
    'F07': 'F07 - RDM SPAD - Grille integree de revue',
}
for code, nom in NOMS_REELS.items():
    assert rd.guess_form_type(nom) == code, f"{code} : deviné {rd.guess_form_type(nom)!r}"
print("OK — les 7 formulaires officiels sont correctement reconnus depuis leur nom réel")

assert rd.guess_form_type('Questionnaire sans rapport avec SPAD') is None
assert rd.guess_form_type('') is None
assert rd.guess_form_type(None) is None
print("OK — aucune détection forcée sur un nom sans rapport (pas de faux positif)")

print()
print("=" * 70)
print("TESTS UNITAIRES PASSÉS — vérification de la route /suivi")
print("=" * 70)

from modules import kobo_connector, kobo_track  # noqa: E402

ASSETS = [
    {'uid': f'uid_{c}', 'name': n, 'asset_type': 'survey', 'submission_count': 10, 'deployed': True}
    for c, n in NOMS_REELS.items()
]


def fake_list_assets(token, instance=None, custom_instance=None):
    return {"success": True, "assets": ASSETS, "total": len(ASSETS), "instance": "https://kf.kobotoolbox.org"}


kobo_connector.list_assets = fake_list_assets

from app import app  # noqa: E402

app.config['TESTING'] = True
client = app.test_client()
with client.session_transaction() as sess:
    sess['kobo_token'] = 'fake-token'
    sess['kobo_instance'] = 'https://kf.kobotoolbox.org'

kobo_track.clear_all()

# Page /suivi : chaque formulaire non encore suivi doit avoir son type
# deviné pré-sélectionné dans le menu déroulant.
r = client.get('/suivi')
assert r.status_code == 200
html = r.get_data(as_text=True)
assert 'détecté depuis le nom' in html
print("OK — /suivi pré-sélectionne le type deviné pour les formulaires non suivis")

# Reproduit exactement le cas signalé : F5 assigné au formulaire de
# vaccination ménages (F7 attendu) — doit déclencher un avertissement.
kobo_track._trackers['uid_F7'] = kobo_track._new_entry(
    'uid_F7', NOMS_REELS['F7'], target=1800, instance='https://kf.kobotoolbox.org',
    form_type='F5', target_source='detectee',
)
r = client.get('/suivi')
html = r.get_data(as_text=True)
assert 'Vérifiez ces associations' in html
assert 'est suivi comme F5' in html and 'plutôt à F7' in html
print("OK — association incohérente (F5 sur un formulaire de vaccination ménages) détectée et signalée")

# Doublon : le même type F5 assigné à un 2e formulaire suivi.
kobo_track._trackers['uid_F5'] = kobo_track._new_entry(
    'uid_F5', NOMS_REELS['F5'], target=1800, instance='https://kf.kobotoolbox.org',
    form_type='F5', target_source='detectee',
)
r = client.get('/suivi')
html = r.get_data(as_text=True)
assert 'assigné à 2 formulaires suivis différents' in html
print("OK — doublon de type (F5 sur 2 formulaires suivis) détecté et signalé")

# Nettoyage direct (les entrées ont été injectées directement dans
# _trackers pour le test, sans passer par add() / les threads de polling
# associés — clear_all() ne les verrait donc pas via _threads).
kobo_track._trackers.clear()
r = client.get('/suivi')
html = r.get_data(as_text=True)
assert 'Vérifiez ces associations' not in html
print("OK — plus aucun avertissement une fois les suivis retirés")

print()
print("=" * 70)
print("TOUS LES TESTS DE DÉTECTION SUIVI SONT PASSÉS")
print("=" * 70)
