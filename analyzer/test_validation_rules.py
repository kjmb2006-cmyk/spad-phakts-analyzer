#!/usr/bin/env python3
"""
Test script — validation des données : contrôles, règles, synthèse par enquêteur, portée « étude ».
"""
import os
import tempfile

import numpy as np
import pandas as pd

from modules import validation_rules as vr

vr.DB_PATH = os.path.join(tempfile.mkdtemp(), 'spad_test.db')              # base de test : rien dans la vraie base

print("=" * 70)
print("TEST — validation des données")
print("=" * 70)
checks = 0


def ok(cond, msg=''):
    global checks
    assert cond, msg
    checks += 1


rng = np.random.default_rng(5)
n = 200
start = pd.Timestamp('2026-03-02 08:00:00', tz='UTC') + pd.to_timedelta(np.arange(n) * 40, unit='m')
minutes = rng.normal(30, 4, n).clip(8)
enq = rng.choice(['E1', 'E2', 'E3', 'E4'], n)
minutes[(enq == 'E3')] = rng.normal(7, 1, (enq == 'E3').sum())               # E3 expédie ses entretiens
df = pd.DataFrame({'start': start.astype(str), 'end': (start + pd.to_timedelta(minutes, unit='m')).astype(str),
                   'ENTETE/Code_Enqueteur__E': enq, 'ENTETE/District__X': rng.choice(['A', 'B'], n),
                   'ENTETE/Etablissement__X': [f'ES{i // 3}' for i in range(n)], 'ENTETE/Numero_Ordre__1': [i % 3 + 1 for i in range(n)],
                   'Age__1Y!0<=N<=120': rng.integers(18, 70, n), 'Poids__2K': rng.normal(65, 10, n).round(1)})
df.loc[7, 'Age__1Y!0<=N<=120'] = 150                                          # hors plage PHAKTS
df.loc[11, 'Poids__2K'] = 900                                                 # valeur extrême seulement
df.loc[20, 'ENTETE/Numero_Ordre__1'] = df.loc[19, 'ENTETE/Numero_Ordre__1']    # même établissement, même numéro d'ordre
df.loc[20, 'ENTETE/Etablissement__X'] = df.loc[19, 'ENTETE/Etablissement__X']

res = vr.run_validation(df)
titles = {c['titre']: c for c in res['checks']}

# ── Valeurs atypiques à part des défauts de collecte
ok('Valeur hors de la plage PHAKTS (Age__1Y!0<=N<=120)' in titles and 8 in titles['Valeur hors de la plage PHAKTS (Age__1Y!0<=N<=120)']['lignes'])
extreme = titles['Valeurs extrêmes (Poids__2K)']
ok(12 in extreme['lignes'] and extreme['categorie'] == vr.ATYPICAL)
ok(12 not in {l for c in res['checks'] if c['categorie'] != vr.ATYPICAL for l in c['lignes']})
ok(res['n_atypiques'] >= 1 and res['pct_sans_anomalie'] == round(100 * (n - res['n_signalees']) / n, 1), res)
core_lines = vr.error_lines(res, (vr.ERREUR, vr.A_VERIFIER))
ok(12 not in core_lines and 8 in core_lines, core_lines)
print("OK — valeurs extrêmes comptées à part : elles ne font pas baisser le « % sans anomalie »")

# ── Durée relative à la médiane
rel = next(c for c in res['checks'] if c['titre'].startswith('Entretien très court par rapport'))
precision = sum(enq[l - 1] == 'E3' for l in rel['lignes']) / len(rel['lignes'])
ok(len(rel['lignes']) >= 20 and precision > 0.95, (len(rel['lignes']), precision))      # ce sont les entretiens d'E3, pas des faux positifs
print("OK — entretiens très courts par rapport à la durée habituelle repérés")

# ── Synthèse par enquêteur : E3 « à regarder »
cands = dict(vr.group_candidates(df))
ok(cands.get('ENTETE/Code_Enqueteur__E') == 'enquêteur' and cands.get('ENTETE/District__X') == 'lieu', cands)
summary = vr.summary_by(df, res, 'ENTETE/Code_Enqueteur__E')
by = {g['groupe']: g for g in summary['groupes']}
ok(by['E3']['a_regarder'] and not by['E1']['a_regarder'], by)
ok(by['E3']['duree_mediane'] < 12 and by['E1']['duree_mediane'] > 25, (by['E3']['duree_mediane'], by['E1']['duree_mediane']))
ok(sum(g['lignes'] for g in summary['groupes']) == n and summary['groupes'][0]['groupe'] == 'E3')
print("OK — synthèse par enquêteur : E3 (entretiens expédiés) ressort en tête, durée médiane comprise")

# ── Clé d'unicité : devinée (peu de répétitions) puis règle explicite
guess = next(c for c in res['checks'] if c['titre'].startswith('Même « Etablissement__X »'))
ok(guess['severite'] == vr.A_VERIFIER and guess['lignes'] == [20, 21], guess['lignes'])
many = df.copy()
many['ENTETE/Numero_Ordre__1'] = 1                                            # 1 seul numéro d'ordre : ce n'est pas une clé
ok(not any(c['titre'].startswith('Même « Etablissement__X »') for c in vr.run_validation(many)['checks']), 'une fausse clé est ignorée')
ok(vr.add_rule('fichier:a.xlsx', 'ENTETE/Etablissement__X|ENTETE/Numero_Ordre__1', 'unique', '', False, 'Un numéro par établissement', 'test')[0])
rules = vr.list_rules('fichier:a.xlsx')
ok(rules[0]['operateur'] == 'unique' and rules[0]['portee'] == 'enquete')
unique = next(c for c in vr.run_validation(df, rules)['checks'] if c['titre'] == 'Un numéro par établissement')
ok(unique['severite'] == vr.ERREUR and unique['lignes'] == [20, 21], unique['lignes'])
ok(not vr.add_rule('fichier:a.xlsx', '', 'unique', '', False)[0], 'une clé sans variable est refusée')
print("OK — clé d'unicité : devinée avec prudence, règle explicite en erreur")

# ── Portée « étude » : la règle d'une vague s'applique aux autres
ok(vr.add_rule('etude:PGT14_OS2_RC2_2__CIV_MS__Etude_Tabac', 'Age__1Y!0<=N<=120', '<=', '100', False, 'Âge raisonnable', 'test')[0])
ok(vr.list_rules(['fichier:b.xlsx', 'etude:PGT14_OS2_RC2_2__CIV_MS__Etude_Tabac'])[0]['portee'] == 'etude')
ok(vr.list_rules(['fichier:b.xlsx', None]) == [] and vr.list_rules('fichier:autre.xlsx') == [])
study_rule = vr.list_rules(['fichier:b.xlsx', 'etude:PGT14_OS2_RC2_2__CIV_MS__Etude_Tabac'])[0]
ok(vr.delete_rule(study_rule['id'], ['fichier:b.xlsx', 'etude:PGT14_OS2_RC2_2__CIV_MS__Etude_Tabac']))
ok(not vr.delete_rule(rules[0]['id'], ['fichier:b.xlsx']), "une règle d'une autre enquête ne se supprime pas")
print("OK — règle d'étude : partagée entre les vagues, supprimable, sans fuite vers une autre enquête")

# ── Contrôles supplémentaires (formulaire) intégrés au résultat
extra = [vr._check('Formulaire (XLSForm)', 'Réponse obligatoire absente (x)', 'd', vr.ERREUR, ['x'], np.arange(n) == 2)]
r2 = vr.run_validation(df, extra_checks=extra)
ok(3 in r2['checks'][0]['lignes'] and r2['n_erreurs'] >= 2 and r2['n_signalees'] >= res['n_signalees'])
print("OK — contrôles issus du formulaire intégrés au résultat")

print()
print(f"TOUS LES TESTS DE VALIDATION SONT PASSÉS ({checks} vérifications)")
