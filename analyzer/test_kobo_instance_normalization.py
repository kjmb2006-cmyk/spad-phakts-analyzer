#!/usr/bin/env python3
"""
Test script — modules/kobo_connector.py normalise bien un instance= fourni
sans schéma (ex. variable d'environnement KOBO_INSTANCE=kf.kobotoolbox.org,
sans https://), utilisée comme repli pour les calculs automatisés de
Complétude nationale quand aucune session Kobo n'est active.

Contexte : validate_token() (saisie interactive) normalisait déjà l'absence
de schéma via _instances_to_try(), mais get_asset_info()/load_data()/
list_assets()/deploy_xlsform() faisaient `base = instance` tel quel — un
KOBO_INSTANCE mal formaté (sans https://) faisait échouer silencieusement
tout calcul de complétude côté serveur avec 'Invalid URL... No scheme
supplied' au lieu d'un message clair, ou pire, un statut « Non calculé »
sans explication visible.
"""
from modules import kobo_connector as kc

print("=" * 70)
print("TEST — Normalisation de l'instance KoboToolbox (schéma manquant)")
print("=" * 70)

assert kc._normalize_instance('kf.kobotoolbox.org') == 'https://kf.kobotoolbox.org'
assert kc._normalize_instance('https://kf.kobotoolbox.org') == 'https://kf.kobotoolbox.org'
assert kc._normalize_instance('https://kf.kobotoolbox.org/') == 'https://kf.kobotoolbox.org'
assert kc._normalize_instance('http://eu.kobotoolbox.org') == 'http://eu.kobotoolbox.org'
assert kc._normalize_instance(None) is None
assert kc._normalize_instance('') == ''
print("OK — _normalize_instance() ajoute le schéma manquant, laisse intact le reste")

# get_asset_info() ne doit jamais planter avec 'No scheme supplied' quand on
# lui passe une instance sans schéma — elle doit atteindre le vrai réseau
# (donc échouer proprement pour un faux uid/token, pas sur l'URL elle-même).
res = kc.get_asset_info('faux-token', 'faux-uid', instance='kf.kobotoolbox.org')
assert 'No scheme supplied' not in (res.get('error') or ''), res
print("OK — get_asset_info() avec une instance sans schéma n'échoue plus sur l'URL")

res = kc.load_data('faux-token', 'faux-uid', instance='kf.kobotoolbox.org')
assert 'No scheme supplied' not in (res.get('error') or ''), res
print("OK — load_data() avec une instance sans schéma n'échoue plus sur l'URL")

print()
print("=" * 70)
print("TOUS LES TESTS DE NORMALISATION D'INSTANCE SONT PASSÉS")
print("=" * 70)
