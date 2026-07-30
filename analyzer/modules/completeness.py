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


def anomalies_zero(ref, form_code, df):
    """Établissements/districts à 0 soumission alors que le formulaire est déployé."""
    rows = form_completeness(ref, form_code, df)
    return [r for r in rows if r['recu'] == 0 and r['cible']]


def anomalies_excess(ref, form_code, df, threshold=2.0):
    """Couples au-delà de `threshold` × cible — doublons potentiels."""
    rows = form_completeness(ref, form_code, df)
    return [r for r in rows if r['cible'] and r['recu'] >= threshold * r['cible']]
