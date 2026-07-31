"""
SPAD Analyzer — Calcul de complétude (rattache les soumissions Kobo réelles
au référentiel organisationnel pour calculer reçu / cible / taux / statut).

Champs d'identification par formulaire — extraits des XLSForms fournis par
l'utilisateur (section « ENTETE_STANDARD », commune à F5/F6/F7/F8, et champs
spécifiques pour les fiches RDM F01/F02/F07). Ces champs contiennent le CODE
de l'établissement/district (ex. « EPHR_PUBLIC_DE_ABENGOUROU »), pas son
libellé — c'est ce code qui sert de clé de jointure avec le référentiel.

Kobo exporte parfois les champs regroupés (`begin_group`) avec un préfixe
« groupe/champ » — _find_column() gère les deux cas (avec ou sans préfixe)
puisqu'aucune soumission réelle n'a encore été observée pour trancher.
"""
from modules import reference_data as rd

FORM_FIELDS = {
    'F5':  {'etablissement': 'Etablissement_Sanitaire__X', 'district': 'District_Sanitaire__X'},
    'F6':  {'etablissement': 'Etablissement_Sanitaire__X', 'district': 'District_Sanitaire__X'},
    'F7':  {'etablissement': 'Etablissement_Sanitaire__X', 'district': 'District_Sanitaire__X'},
    'F8':  {'etablissement': 'Etablissement_Sanitaire__X', 'district': 'District_Sanitaire__X'},
    'F01': {'etablissement': None,                          'district': 'F01_01a__X'},
    'F02': {'etablissement': 'F02_01__E',                   'district': 'F02_00_district__X'},
    'F07': {'etablissement': 'RDM_NOT03__X',                'district': 'RDM_NOT02__X'},
}

# Formulaires dont la cible/le décompte se fait au niveau établissement vs. district
ETABLISSEMENT_FORMS = ('F5', 'F6', 'F7', 'F8', 'F02')
DISTRICT_FORMS = ('F01', 'F07')


def find_column(df, field_name):
    """Retrouve une colonne par nom exact ou par suffixe `.../field_name`."""
    if field_name is None or df is None:
        return None
    if field_name in df.columns:
        return field_name
    for c in df.columns:
        if str(c).endswith('/' + field_name):
            return c
    return None


def status_for(recu, cible, is_floor=False):
    """Statut d'un couple (reçu, cible), cohérent avec le vocabulaire déjà
    utilisé dans l'UI (status-pill : zero / en_cours / cible / verifier)."""
    if not cible:
        return 'zero' if not recu else 'suivi'
    if not recu:
        return 'zero'
    ratio = recu / cible
    if is_floor:
        return 'cible'  # F07 : cible = plancher, la dépasser est normal
    if ratio >= 2:
        return 'verifier'  # doublons potentiels
    if ratio >= 1:
        return 'cible'
    return 'en_cours'


def etablissement_completeness(ref, form_code, df):
    """Reçu par établissement pour un formulaire donné (F5/F6/F7/F8/F02)."""
    fields = FORM_FIELDS[form_code]
    col = find_column(df, fields['etablissement'])
    counts = df[col].value_counts(dropna=True).to_dict() if col is not None else {}

    rows = []
    for code, etab in ref['etablissements'].items():
        recu = int(counts.get(code, 0))
        cible = rd.target_for(ref, form_code, etablissement_code=code)
        rows.append({
            'etablissement_code': code,
            'etablissement_nom':  etab['nom_complet'],
            'district_code':      etab['district_code'],
            'region_code':        etab['region_code'],
            'recu':  recu,
            'cible': cible,
            'taux':  round(100 * recu / cible, 1) if cible else None,
            'statut': status_for(recu, cible),
        })
    return rows


def district_completeness(ref, form_code, df):
    """Reçu par district pour un formulaire donné (F01/F07)."""
    is_floor = (form_code == 'F07')
    col = find_column(df, FORM_FIELDS[form_code]['district'])
    counts = df[col].value_counts(dropna=True).to_dict() if col is not None else {}

    rows = []
    for code, d in ref['districts'].items():
        recu = int(counts.get(code, 0))
        cible = rd.target_for(ref, form_code, district_code=code) if is_floor else 1
        rows.append({
            'district_code': code,
            'district_nom':  d['nom'],
            'region_code':   d['region_code'],
            'recu':  recu,
            'cible': cible,
            'taux':  round(100 * recu / cible, 1) if cible else None,
            'statut': status_for(recu, cible, is_floor=is_floor),
        })
    return rows


def form_completeness(ref, form_code, df):
    """Répartiteur : établissement ou district selon le formulaire."""
    if form_code in ETABLISSEMENT_FORMS:
        return etablissement_completeness(ref, form_code, df)
    if form_code in DISTRICT_FORMS:
        return district_completeness(ref, form_code, df)
    raise ValueError(f"Formulaire inconnu : {form_code}")


def national_summary(ref, form_dataframes):
    """Vue nationale agrégée. form_dataframes : {code_formulaire: DataFrame|None}."""
    nat_targets = rd.national_targets(ref)
    summary = {}
    for code in rd.FORM_CODES:
        cible = nat_targets[code]
        df = form_dataframes.get(code)
        if df is None:
            summary[code] = {'label': rd.FORM_LABELS[code], 'recu': 0, 'cible': cible,
                              'taux': None, 'statut': 'inconnu'}
            continue
        rows = form_completeness(ref, code, df)
        recu = sum(r['recu'] for r in rows)
        summary[code] = {
            'label': rd.FORM_LABELS[code],
            'recu': recu, 'cible': cible,
            'taux': round(100 * recu / cible, 1) if cible else None,
            'statut': status_for(recu, cible, is_floor=(code == 'F07')),
        }
    return summary


def _empty_cell(cible=None):
    return {'recu': 0, 'cible': cible, 'taux': None, 'statut': 'inconnu'}


def district_table(ref, form_dataframes):
    """Table district × formulaire : {district_code: {'nom', 'region_code', 'forms': {code: cellule}}}.

    Pour F5/F6/F7/F8/F02 (cible établissement), agrège les établissements du
    district. Pour F01/F07 (déjà au niveau district), reprend directement le
    résultat de district_completeness().
    """
    table = {code: {'nom': d['nom'], 'region_code': d['region_code'], 'forms': {}}
              for code, d in ref['districts'].items()}

    for form_code in rd.FORM_CODES:
        df = form_dataframes.get(form_code)
        if df is None:
            for code, d in ref['districts'].items():
                cible = rd.target_for(ref, form_code, district_code=code) if form_code in DISTRICT_FORMS else None
                table[code]['forms'][form_code] = _empty_cell(cible)
            continue

        if form_code in ETABLISSEMENT_FORMS:
            rows = etablissement_completeness(ref, form_code, df)
            agg = {}
            for r in rows:
                a = agg.setdefault(r['district_code'], {'recu': 0, 'cible': 0})
                a['recu'] += r['recu']
                a['cible'] += (r['cible'] or 0)
            for code in table:
                a = agg.get(code, {'recu': 0, 'cible': 0})
                table[code]['forms'][form_code] = {
                    'recu': a['recu'], 'cible': a['cible'],
                    'taux': round(100 * a['recu'] / a['cible'], 1) if a['cible'] else None,
                    'statut': status_for(a['recu'], a['cible']),
                }
        else:
            rows = district_completeness(ref, form_code, df)
            by_code = {r['district_code']: r for r in rows}
            for code in table:
                r = by_code.get(code)
                table[code]['forms'][form_code] = (
                    {'recu': r['recu'], 'cible': r['cible'], 'taux': r['taux'], 'statut': r['statut']}
                    if r else _empty_cell()
                )
    return table


def region_table(ref, form_dataframes):
    """Table région × formulaire — agrège district_table() par région
    (F01/F07 : somme sur les districts de la région ; les autres : somme
    directe sur les établissements de la région, plus précise qu'une somme
    de sommes de districts déjà arrondis)."""
    dtable = district_table(ref, form_dataframes)
    table = {code: {'nom': r['nom'], 'forms': {}} for code, r in ref['regions'].items()}

    for form_code in rd.FORM_CODES:
        for region_code in ref['regions']:
            districts_in_region = [d for d, info in dtable.items() if info['region_code'] == region_code]
            recu = sum(dtable[d]['forms'][form_code]['recu'] for d in districts_in_region)
            cible = sum((dtable[d]['forms'][form_code]['cible'] or 0) for d in districts_in_region)
            df = form_dataframes.get(form_code)
            if df is None:
                table[region_code]['forms'][form_code] = _empty_cell(cible if form_code in DISTRICT_FORMS else None)
            else:
                table[region_code]['forms'][form_code] = {
                    'recu': recu, 'cible': cible,
                    'taux': round(100 * recu / cible, 1) if cible else None,
                    'statut': status_for(recu, cible, is_floor=(form_code == 'F07')),
                }
    return table


def anomalies_zero(ref, form_code, df):
    """Établissements/districts à 0 soumission alors que le formulaire est déployé."""
    rows = form_completeness(ref, form_code, df)
    return [r for r in rows if r['recu'] == 0 and r['cible']]


def anomalies_excess(ref, form_code, df, threshold=2.0):
    """Couples au-delà de `threshold` × cible — doublons potentiels."""
    rows = form_completeness(ref, form_code, df)
    return [r for r in rows if r['cible'] and r['recu'] >= threshold * r['cible']]
