#!/usr/bin/env python3
"""
Test script — garde-fou de correspondance formulaire SPAD ↔ KoboToolbox
(modules/reference_data.py::validate_mapping()).

Contexte : un utilisateur a mappé F6 et F7 de manière inversée, et F8 sur
le même formulaire Kobo que F07, sans s'en rendre compte — le calcul de
complétude aurait silencieusement donné des taux faux pour ces formulaires.
Vérifie que :
  - un même formulaire Kobo mappé sur 2 codes SPAD est détecté comme erreur
    (bloquant, jamais un cas légitime)
  - un nom de formulaire qui ne correspond pas au préfixe attendu du code
    est détecté comme avertissement (heuristique, non bloquant)
  - une correspondance correcte ne déclenche ni l'un ni l'autre
  - la route /completude/calculer est bloquée (pas de calcul) en cas
    d'erreur, et redirige proprement
"""
from modules import reference_data as rd

print("=" * 70)
print("TEST — Garde-fou correspondance formulaire SPAD ↔ KoboToolbox")
print("=" * 70)

ASSETS = [
    {'uid': 'uid5', 'name': '5_PNLTA_SPAD_Fiche_Femmes_Enceintes_Allaitantes'},
    {'uid': 'uid6', 'name': '6_PNLTA_SPAD_Fiche_CAP_Personnel_Sante'},
    {'uid': 'uid7', 'name': '7_PEV_SPAD_Fiche_Menage_Non_Vaccination'},
    {'uid': 'uid8', 'name': '8_PEV_SPAD_Fiche_Etablissement_Non_Vaccination'},
    {'uid': 'uid01', 'name': 'F01 - RDM SPAD - Fiche district'},
    {'uid': 'uid02', 'name': 'F02 - RDM SPAD - Fiche établissement'},
    {'uid': 'uid07', 'name': 'F07 - RDM SPAD - Grille integree de revue'},
]

# ── Cas 1 : correspondance entièrement correcte ──
mapping_ok = {'F5': 'uid5', 'F6': 'uid6', 'F7': 'uid7', 'F8': 'uid8',
              'F01': 'uid01', 'F02': 'uid02', 'F07': 'uid07'}
erreurs, avertissements = rd.validate_mapping(mapping_ok, ASSETS)
assert erreurs == [], erreurs
assert avertissements == [], avertissements
print("OK — correspondance correcte : aucune erreur, aucun avertissement")

# ── Cas 2 : F6/F7 inversés, F8 mappé sur le même formulaire que F07 (bug réel observé) ──
mapping_bug = {'F5': 'uid5', 'F6': 'uid7', 'F7': 'uid6', 'F8': 'uid07',
               'F01': 'uid01', 'F02': 'uid02', 'F07': 'uid07'}
erreurs, avertissements = rd.validate_mapping(mapping_bug, ASSETS)
assert len(erreurs) == 1, erreurs
assert 'F8' in erreurs[0] and 'F07' in erreurs[0]
print(f"OK — doublon F8/F07 détecté comme erreur bloquante : {erreurs[0]}")

# F6/F7 inversés + F8 (nom "F07 - RDM..." ne contient pas "8_", en plus
# d'être déjà signalé comme doublon ci-dessus) = 3 avertissements de nom.
assert len(avertissements) == 3, avertissements
assert any(a.startswith('F6') for a in avertissements)
assert any(a.startswith('F7') for a in avertissements)
assert any(a.startswith('F8') for a in avertissements)
print("OK — inversion F6/F7 et nom incohérent pour F8 détectés comme avertissements (3 lignes)")

# ── Cas 3 : formulaire au nom atypique (pas de préfixe reconnu) — avertissement, pas erreur ──
assets_atypique = ASSETS + [{'uid': 'uidX', 'name': 'Formulaire Tabac Femmes Enceintes 2026 (v3)'}]
mapping_atypique = {'F5': 'uidX'}
erreurs, avertissements = rd.validate_mapping(mapping_atypique, assets_atypique)
assert erreurs == []
assert len(avertissements) == 1 and avertissements[0].startswith('F5')
print("OK — nom atypique signalé en avertissement seulement (pas de blocage abusif)")

print()
print("=" * 70)
print("TESTS UNITAIRES PASSÉS — vérification des routes Flask")
print("=" * 70)

from modules import form_mapping  # noqa: E402
from modules import kobo_track  # noqa: E402

from app import app  # noqa: E402

app.config['TESTING'] = True
client = app.test_client()

# Le menu de correspondance de /completude liste désormais les formulaires
# déjà ajoutés dans Suivi multi-formulaires (kobo_track.list_tracked()),
# pas un appel direct à l'API Kobo — on peuple kobo_track avec les mêmes
# formulaires que ASSETS plutôt que de simuler list_assets().
_test_uids = [a['uid'] for a in ASSETS]
for a in ASSETS:
    kobo_track._trackers[a['uid']] = kobo_track._new_entry(a['uid'], a['name'], None, 'inst')

# La correspondance SPAD <-> Kobo est persistée côté serveur (voir
# modules/form_mapping.py, pas la session) — on sauvegarde/restaure la
# vraie config d'un déploiement réel plutôt que de l'écraser durablement.
_original_mapping = form_mapping.load()
try:
    form_mapping.save(mapping_bug)

    # La page de mapping doit afficher l'erreur ET l'avertissement
    r = client.get('/completude')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Correspondance incorrecte' in html
    assert 'pointent vers le même formulaire Kobo' in html
    assert 'Vérifiez ces correspondances' in html
    print("OK — /completude affiche l'erreur bloquante et les avertissements")

    # Le calcul doit être bloqué (redirection, pas de cache créé)
    with client.session_transaction() as sess:
        sess.pop('completude_path', None)
    r = client.post('/completude/calculer', follow_redirects=True)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Correspondance incorrecte' in html
    with client.session_transaction() as sess:
        assert sess.get('completude_path') is None, "le calcul n'aurait pas dû s'exécuter"
    print("OK — /completude/calculer bloqué tant que le doublon n'est pas corrigé")

    # Une fois corrigé, le calcul doit à nouveau être permis (pas plus loin
    # testé ici — juste que la validation elle-même ne bloque plus)
    form_mapping.save(mapping_ok)
    r = client.get('/completude')
    html = r.get_data(as_text=True)
    assert 'Correspondance incorrecte' not in html and 'Vérifiez ces correspondances' not in html
    print("OK — plus aucune alerte une fois la correspondance corrigée")
finally:
    form_mapping.save(_original_mapping)
    for uid in _test_uids:
        kobo_track.remove(uid)

print()
print("=" * 70)
print("TOUS LES TESTS DE VALIDATION DE CORRESPONDANCE SONT PASSÉS")
print("=" * 70)
