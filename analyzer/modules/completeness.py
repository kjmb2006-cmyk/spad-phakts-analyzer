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


def etablissement_table(ref, form_dataframes):
    """Table établissement × formulaire (F5/F6/F7/F8/F02 — les seuls
    formulaires au grain établissement). C'est le grain le plus fin du
    référentiel : base des vues de détail région → district → établissement
    (drill-down), à la différence de district_table() qui agrège déjà les
    établissements de chaque district."""
    table = {code: {'nom': e['nom_complet'], 'type': e['type'],
                     'district_code': e['district_code'], 'region_code': e['region_code'],
                     'enqueteur_code': e['enqueteur_code'], 'forms': {}}
              for code, e in ref['etablissements'].items()}

    for form_code in ETABLISSEMENT_FORMS:
        df = form_dataframes.get(form_code)
        if df is None:
            for code in table:
                table[code]['forms'][form_code] = _empty_cell()
            continue
        rows = etablissement_completeness(ref, form_code, df)
        by_code = {r['etablissement_code']: r for r in rows}
        for code in table:
            r = by_code.get(code)
            table[code]['forms'][form_code] = (
                {'recu': r['recu'], 'cible': r['cible'], 'taux': r['taux'], 'statut': r['statut']}
                if r else _empty_cell()
            )
    return table


ENQUETEUR_FORMS = ('F5', 'F6', 'F7', 'F8')
SUPERVISEUR_FORMS = ('F01', 'F02', 'F07')


def enqueteur_table(ref, form_dataframes):
    """Table enquêteur × formulaire (F5/F6/F7/F8 uniquement — les seuls
    formulaires remplis par les enquêteurs). Agrège les 2 établissements
    assignés à chaque enquêteur (voir etab['enqueteur_code'] dans le
    référentiel)."""
    etabs_par_enq = {}
    for ecode, etab in ref['etablissements'].items():
        etabs_par_enq.setdefault(etab['enqueteur_code'], []).append(ecode)

    table = {code: {'nom': e['nom_complet'], 'sous_titre': e['district_code'], 'forms': {}}
              for code, e in ref['enqueteurs'].items()}

    for form_code in ENQUETEUR_FORMS:
        df = form_dataframes.get(form_code)
        if df is None:
            for code in table:
                table[code]['forms'][form_code] = _empty_cell()
            continue
        rows = etablissement_completeness(ref, form_code, df)
        by_etab = {r['etablissement_code']: r for r in rows}
        for enq_code, etab_codes in etabs_par_enq.items():
            if enq_code not in table:
                continue  # code enquêteur du référentiel étab. absent de la liste enquêteurs (ne devrait pas arriver)
            recu  = sum(by_etab[e]['recu'] for e in etab_codes if e in by_etab)
            cible = sum((by_etab[e]['cible'] or 0) for e in etab_codes if e in by_etab)
            table[enq_code]['forms'][form_code] = {
                'recu': recu, 'cible': cible,
                'taux': round(100 * recu / cible, 1) if cible else None,
                'statut': status_for(recu, cible),
            }
    return table


def superviseur_table(ref, form_dataframes):
    """Table superviseur × formulaire (F01/F02/F07 — le volet RDM). Un
    superviseur par district, reprend directement district_table()."""
    dtable = district_table(ref, form_dataframes)
    table = {}
    for code, s in ref['superviseurs'].items():
        d = s['district_code']
        drow = dtable.get(d, {'forms': {}})
        table[code] = {
            'nom': s['nom_complet'], 'sous_titre': d,
            'forms': {fc: drow['forms'].get(fc, _empty_cell()) for fc in SUPERVISEUR_FORMS},
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


def export_rows(ref, form_dataframes):
    """Grain établissement × formulaire (F5/F6/F7/F8/F02) et district ×
    formulaire (F01/F07) — une ligne par couple, pour l'export CSV/XLSX.
    Reprend la même hiérarchie que le drill-down région → district →
    établissement de l'interface : chaque ligne porte aussi le code de
    l'établissement (vide au grain district) ainsi que l'enquêteur et le
    superviseur responsables, pour permettre un filtre/pivot par acteur
    directement dans le tableur. N'inclut que les formulaires effectivement
    mappés (comme les autres vues)."""
    sup_by_district = {s['district_code']: s for s in ref['superviseurs'].values()}
    rows = []
    for code in rd.FORM_CODES:
        df = form_dataframes.get(code)
        if df is None:
            continue
        if code in ETABLISSEMENT_FORMS:
            for r in etablissement_completeness(ref, code, df):
                etab = ref['etablissements'].get(r['etablissement_code'], {})
                enq = ref['enqueteurs'].get(etab.get('enqueteur_code'), {})
                sup = sup_by_district.get(r['district_code'], {})
                rows.append({
                    'region':        ref['regions'].get(r['region_code'], {}).get('nom', r['region_code']),
                    'district':      ref['districts'].get(r['district_code'], {}).get('nom', r['district_code']),
                    'etablissement_code': r['etablissement_code'],
                    'unite':         r['etablissement_nom'],
                    'enqueteur_code': etab.get('enqueteur_code', ''),
                    'enqueteur_nom':  enq.get('nom_complet', ''),
                    'superviseur_code': sup.get('code', ''),
                    'superviseur_nom':  sup.get('nom_complet', ''),
                    'formulaire':    code,
                    'formulaire_label': rd.FORM_LABELS[code],
                    'cible': r['cible'], 'recu': r['recu'], 'taux': r['taux'], 'statut': r['statut'],
                })
        else:
            for r in district_completeness(ref, code, df):
                sup = sup_by_district.get(r['district_code'], {})
                rows.append({
                    'region':        ref['regions'].get(r['region_code'], {}).get('nom', r['region_code']),
                    'district':      r['district_nom'],
                    'etablissement_code': '',
                    'unite':         r['district_nom'],
                    'enqueteur_code': '',
                    'enqueteur_nom':  '',
                    'superviseur_code': sup.get('code', ''),
                    'superviseur_nom':  sup.get('nom_complet', ''),
                    'formulaire':    code,
                    'formulaire_label': rd.FORM_LABELS[code],
                    'cible': r['cible'], 'recu': r['recu'], 'taux': r['taux'], 'statut': r['statut'],
                })
    return rows


def _unit_label(row):
    """Nom de l'unité concernée, que la ligne soit au niveau établissement
    (F5/F6/F7/F8/F02) ou district (F01/F07)."""
    return row.get('etablissement_nom') or row.get('district_nom')


def all_anomalies_zero(ref, form_dataframes):
    """Combine anomalies_zero() sur tous les formulaires effectivement mappés."""
    out = []
    for code in rd.FORM_CODES:
        df = form_dataframes.get(code)
        if df is None:
            continue
        for r in anomalies_zero(ref, code, df):
            out.append({
                'formulaire': code, 'formulaire_label': rd.FORM_LABELS[code],
                'unite': _unit_label(r),
                'etablissement_code': r.get('etablissement_code'),
                'district_code': r.get('district_code'),
                'cible': r['cible'],
            })
    return out


def all_anomalies_excess(ref, form_dataframes, threshold=2.0):
    """Combine anomalies_excess() sur tous les formulaires effectivement mappés.
    F07 exclu : sa cible est un plancher (somme des décès SIG) — la dépasser
    est normal, pas une anomalie (voir modules/reference_data.py)."""
    out = []
    for code in rd.FORM_CODES:
        if code == 'F07':
            continue
        df = form_dataframes.get(code)
        if df is None:
            continue
        for r in anomalies_excess(ref, code, df, threshold=threshold):
            out.append({
                'formulaire': code, 'formulaire_label': rd.FORM_LABELS[code],
                'unite': _unit_label(r),
                'etablissement_code': r.get('etablissement_code'),
                'district_code': r.get('district_code'),
                'recu': r['recu'], 'cible': r['cible'],
                'ratio': round(r['recu'] / r['cible'], 2) if r['cible'] else None,
            })
    return out
