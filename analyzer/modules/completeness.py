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
import pandas as pd
from modules import reference_data as rd
from modules import forms_registry


def form_fields(form_code):
    """Noms des champs Kobo (établissement/district) pour ce formulaire —
    dérivés du registre (modules/forms_registry.py, écran /admin/forms)
    plutôt que d'un dict figé par formulaire."""
    form = forms_registry.get(form_code)
    if form is None:
        return {'etablissement': None, 'district': None}
    return {'etablissement': form.get('etab_field'), 'district': form.get('district_field')}


def etablissement_forms():
    """Codes des formulaires actifs dont la cible/le décompte se fait au
    niveau établissement (motif historique F5/F6/F7/F8/F02)."""
    return tuple(f['code'] for f in forms_registry.all_forms(include_inactive=False) if f['grain'] == 'etablissement')


def district_forms():
    """Codes des formulaires actifs dont la cible/le décompte se fait au
    niveau district (motif historique F01/F07)."""
    return tuple(f['code'] for f in forms_registry.all_forms(include_inactive=False) if f['grain'] == 'district')


def enqueteur_forms():
    """Codes des formulaires actifs remplis par les enquêteurs."""
    return tuple(f['code'] for f in forms_registry.all_forms(include_inactive=False) if f['actor'] == 'enqueteur')


def superviseur_forms():
    """Codes des formulaires actifs remplis par les superviseurs (volet RDM)."""
    return tuple(f['code'] for f in forms_registry.all_forms(include_inactive=False) if f['actor'] == 'superviseur')


def enqueteur_table_forms():
    """Sous-ensemble de enqueteur_forms() réellement présent dans
    enqueteur_table() (grain établissement uniquement — voir le filtre dans
    enqueteur_table() ci-dessous). Un formulaire roster (grain enquêteur,
    motif RAA Phase 1 — voir forms_registry.py) a lui aussi actor='enqueteur'
    mais PAS de colonne par personne dans ce tableau (il a sa propre vue
    régionale, roster_family_table()) : passer enqueteur_forms() tel quel
    comme liste de colonnes à un template qui lit row.forms[code] lève une
    jinja2.exceptions.UndefinedError (cas réel rencontré sur
    /completude/enqueteurs après l'ajout de formulaires roster)."""
    return tuple(fc for fc in enqueteur_forms()
                 if (forms_registry.get(fc) or {}).get('grain') == 'etablissement')


def superviseur_table_forms():
    """Équivalent de enqueteur_table_forms() pour superviseur_table() —
    grain district uniquement (motif F01/F07)."""
    return tuple(fc for fc in superviseur_forms()
                 if (forms_registry.get(fc) or {}).get('grain') == 'district')


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
    fields = form_fields(form_code)
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
    is_floor = rd.is_floor(form_code)
    col = find_column(df, form_fields(form_code)['district'])
    counts = df[col].value_counts(dropna=True).to_dict() if col is not None else {}

    rows = []
    for code, d in ref['districts'].items():
        recu = int(counts.get(code, 0))
        cible = rd.target_for(ref, form_code, district_code=code)
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


def roster_completeness(form, df):
    """Reçu/cible pour un formulaire au grain 'enqueteur'/'superviseur'
    (motif « roster » — voir modules/forms_registry.py) : une MÊME personne
    répond une seule fois, donc 'reçu' compte les valeurs DISTINCTES
    d'identity_field parmi les lignes qui passent role_filter — jamais un
    décompte par établissement/district (qui n'aurait pas de sens ici, une
    soumission pouvant référencer plusieurs établissements à la fois).

    Renvoie une liste à UN élément (plutôt qu'un dict nu) pour rester
    compatible avec les appelants de form_completeness(), qui itèrent tous
    sur une liste de lignes (national_summary() fait sum(r['recu'] for r in
    rows), par exemple)."""
    cible = form['target_rule']['params']['n']
    if df is None:
        return [{'recu': 0, 'cible': cible, 'taux': None, 'statut': 'inconnu'}]

    sub = df
    role_filter = form.get('role_filter')
    if role_filter:
        col = find_column(sub, role_filter['field'])
        if col is not None:
            values = sub[col].astype(str).str.strip().str.lower()
            sub = sub[values == str(role_filter['value']).strip().lower()]
        else:
            sub = sub.iloc[0:0]  # champ de rôle absent : aucune ligne ne peut être attribuée à ce rôle

    identity_field = form.get('identity_field')
    if identity_field:
        col = find_column(sub, identity_field)
        recu = int(sub[col].dropna().astype(str).str.strip().nunique()) if col is not None else 0
    else:
        recu = int(len(sub))

    return [{
        'recu': recu, 'cible': cible,
        'taux': round(100 * recu / cible, 1) if cible else None,
        'statut': status_for(recu, cible),
    }]


def roster_by_district(form, df, ref):
    """Répartition par district d'un formulaire roster (grain enquêteur/superviseur).

    Applique role_filter, groupe par district_field, compte les valeurs
    distinctes d'identity_field par district. Si la règle de cible est
    'fixed_per_district' (motif RAA Phase 1 : 1 DRS/DDS/superviseur et 5
    enquêteurs attendus PAR district), chaque district reçoit sa propre
    cible/taux/statut — pas seulement un total national brut comme avant.
    Pour 'fixed_national' (motif UGP/Programmes — pas réparti par district),
    cible de district reste None : seul le total national est significatif.

    Capture aussi la date de la dernière soumission par district
    (_submission_time, préservé par kobo_load_data(keep_meta_cols=...) —
    voir modules/data_loader.py) : nécessaire pour la colonne « Dernière
    soumission » du tableau régional combiné (roster_family_table()).

    Renvoie :
      {
        'national': {'recu', 'cible', 'taux', 'statut'},
        'by_district': {district_code: {'nom', 'region_code', 'recu',
                         'cible', 'taux', 'statut',
                         'last_submission' (ISO, pour tri/comparaison),
                         'last_submission_display' (jj/mm HH:MM)}},
      }
    """
    rule = form['target_rule']
    national_cible = forms_registry.national_target(form, ref)
    per_district_cible = rule['params']['n'] if rule['type'] == 'fixed_per_district' else None

    sub = df
    role_filter = form.get('role_filter')
    if sub is not None and role_filter:
        col = find_column(sub, role_filter['field'])
        if col is not None:
            values = sub[col].astype(str).str.strip().str.lower()
            sub = sub[values == str(role_filter['value']).strip().lower()]
        else:
            sub = sub.iloc[0:0]

    identity_field = form.get('identity_field')
    district_field = form.get('district_field')

    if sub is None or len(sub) == 0:
        national_recu = 0
    elif identity_field:
        col = find_column(sub, identity_field)
        national_recu = int(sub[col].dropna().astype(str).str.strip().nunique()) if col is not None else 0
    else:
        national_recu = int(len(sub))

    national = {
        'recu': national_recu, 'cible': national_cible,
        'taux': round(100 * national_recu / national_cible, 1) if national_cible else None,
        'statut': status_for(national_recu, national_cible),
    }

    by_district = {
        d_code: {
            'nom': d['nom'], 'region_code': d['region_code'],
            'recu': 0, 'cible': per_district_cible, 'taux': None,
            'statut': status_for(0, per_district_cible),
            'last_submission': None, 'last_submission_display': None,
        }
        for d_code, d in ref['districts'].items()
    }

    if sub is not None and len(sub) > 0 and district_field:
        d_col = find_column(sub, district_field)
        if d_col is not None:
            working = sub.copy()
            working['__district'] = working[d_col].astype(str).str.strip()

            if identity_field:
                id_col = find_column(working, identity_field)
                if id_col is not None:
                    valid = working.dropna(subset=[id_col]).copy()
                    valid['__id'] = valid[id_col].astype(str).str.strip()
                    counts = valid.groupby('__district')['__id'].nunique()
                else:
                    counts = working['__district'].value_counts()
            else:
                counts = working['__district'].value_counts()

            for d_code, cnt in counts.items():
                if d_code in by_district:
                    recu = int(cnt)
                    by_district[d_code]['recu'] = recu
                    by_district[d_code]['taux'] = (
                        round(100 * recu / per_district_cible, 1) if per_district_cible else None)
                    by_district[d_code]['statut'] = status_for(recu, per_district_cible)

            ts_col = find_column(working, '_submission_time')
            if ts_col is not None:
                ts_series = pd.to_datetime(working[ts_col], errors='coerce')
                last_by_district = ts_series.groupby(working['__district']).max()
                for d_code, ts in last_by_district.items():
                    if d_code in by_district and pd.notna(ts):
                        by_district[d_code]['last_submission'] = ts.isoformat()
                        by_district[d_code]['last_submission_display'] = ts.strftime('%d/%m %H:%M')

    return {'national': national, 'by_district': by_district}


def all_roster_by_district(ref, form_dataframes):
    """Calcule roster_by_district() pour tous les formulaires roster actifs."""
    result = {}
    for form in forms_registry.all_forms(include_inactive=False):
        if form.get('grain') not in ('enqueteur', 'superviseur'):
            continue
        df = form_dataframes.get(form['code'])
        result[form['code']] = roster_by_district(form, df, ref)
    return result


def roster_family(form_code):
    """Formulaires roster actifs partageant le même name_hint que form_code
    — motif introduit pour RAA Phase 1 : UN SEUL formulaire Kobo porte
    plusieurs rôles (DRS/DDS/Superviseur/Enquêteurs), chacun son propre code
    SPAD avec son role_filter, mais tous mappés au même UID Kobo. Permet de
    les afficher groupés dans un seul tableau régional (roster_family_table())
    plutôt qu'une page par rôle."""
    form = forms_registry.get(form_code)
    if not form:
        return []
    hint = form.get('name_hint')
    if not hint:
        return [form]
    family = [f for f in forms_registry.all_forms(include_inactive=False)
              if f.get('name_hint') == hint and f.get('grain') in ('enqueteur', 'superviseur')]
    return family or [form]


def roster_family_table(ref, form_dataframes, family_forms):
    """Combine plusieurs formulaires roster d'une même famille (même
    formulaire Kobo source) en UNE ligne par district : un sous-total par
    rôle (par_role), un total combiné (tous rôles confondus) et la dernière
    soumission la plus récente tous rôles confondus — reproduit le tableau
    « Niveau déconcentré » de l'application de référence (spad-raa-suivi).

    Renvoie (table, per_form) où table est
      {district_code: {'nom', 'region_code', 'par_role': {code: cellule},
                        'total_recu', 'total_cible', 'total_taux',
                        'total_statut', 'last_submission_display'}}
    et per_form est {code: résultat brut de roster_by_district()} (réutilisé
    pour les cartes KPI nationales par rôle)."""
    per_form = {f['code']: roster_by_district(f, form_dataframes.get(f['code']), ref) for f in family_forms}

    table = {
        d_code: {
            'nom': d['nom'], 'region_code': d['region_code'],
            'par_role': {}, 'total_recu': 0, 'total_cible': 0,
            'last_submission': None, 'last_submission_display': None,
        }
        for d_code, d in ref['districts'].items()
    }

    for f in family_forms:
        data = per_form[f['code']]
        for d_code, cell in data['by_district'].items():
            if d_code not in table:
                continue
            table[d_code]['par_role'][f['code']] = cell
            table[d_code]['total_recu'] += cell['recu']
            table[d_code]['total_cible'] += (cell['cible'] or 0)
            ls = cell.get('last_submission')
            if ls and (table[d_code]['last_submission'] is None or ls > table[d_code]['last_submission']):
                table[d_code]['last_submission'] = ls
                table[d_code]['last_submission_display'] = cell.get('last_submission_display')

    for row in table.values():
        recu, cible = row['total_recu'], row['total_cible']
        row['total_taux'] = round(100 * recu / cible, 1) if cible else None
        row['total_statut'] = status_for(recu, cible)

    return table, per_form


def roster_daily_counts(form_dataframes, family_forms):
    """Nombre de soumissions reçues par jour, tous rôles confondus — pour le
    graphique « Rythme des soumissions ». Les formulaires d'une même famille
    partagent le même UID Kobo (un seul jeu de soumissions réel, rechargé une
    fois par code SPAD mappé) : on prend donc le premier jeu de données non
    vide plutôt que de sommer plusieurs copies du même décompte."""
    df = None
    for f in family_forms:
        candidate = form_dataframes.get(f['code'])
        if candidate is not None and len(candidate):
            df = candidate
            break
    if df is None:
        return []
    ts_col = find_column(df, '_submission_time')
    if ts_col is None:
        return []
    ts = pd.to_datetime(df[ts_col], errors='coerce').dropna()
    if ts.empty:
        return []
    counts = ts.dt.date.value_counts().sort_index()
    return [{'date': d.strftime('%d/%m'), 'count': int(c)} for d, c in counts.items()]


def all_roster_families(ref, form_dataframes):
    """Regroupe tous les formulaires roster actifs par name_hint (même
    formulaire Kobo, rôles différents) et calcule, pour chaque groupe, la
    table régionale combinée + le rythme des soumissions. Clé du résultat :
    name_hint du groupe."""
    roster_forms = [f for f in forms_registry.all_forms(include_inactive=False)
                     if f.get('grain') in ('enqueteur', 'superviseur')]
    groups = {}
    for f in roster_forms:
        hint = f.get('name_hint') or f['code']
        groups.setdefault(hint, []).append(f)

    result = {}
    for hint, family in groups.items():
        table, per_form = roster_family_table(ref, form_dataframes, family)
        result[hint] = {
            'forms': [{'code': f['code'], 'label': f['label'],
                       'role_value': (f.get('role_filter') or {}).get('value')} for f in family],
            'by_district': table,
            'per_form': per_form,
            'daily': roster_daily_counts(form_dataframes, family),
        }
    return result


def named_roster_detail(form, df):
    """Reçu/cible d'un formulaire au grain 'roster_national' (motif UGP/
    Programmes — RAA Phase 1) : la cible varie par ENTITÉ NOMMÉE, pas par
    district (voir target_rule.type == 'fixed_named_list' dans
    forms_registry.py). Une valeur de match préfixée "AUTRE:xxx" désigne une
    entité qui n'a pas de code Kobo dédié, saisie en texte libre via le champ
    "<field>_Autre__Z" (convention PHAKTS pour un "Autre, précisez") — cas
    réel : la 5e entité de l'UGP RAA Phase 1 ("DPPS") n'existe que sous cette
    forme, les 4 autres (DIS/OMS/INSP/ANSTAT) ont un code Kobo direct.

    Renvoie {'national': {...}, 'entries': [{'label','recu','cible','taux',
    'statut'}, ...]} — pas de dimension district/région, donc pas de place
    dans district_table()/region_table() (voir le filtre ajouté là-bas)."""
    rule = form['target_rule']
    field = rule['params']['field']
    entries_cfg = rule['params']['entries']
    national_cible = sum(e['n'] for e in entries_cfg)

    sub = df
    role_filter = form.get('role_filter')
    if sub is not None and role_filter:
        col = find_column(sub, role_filter['field'])
        if col is not None:
            values = sub[col].astype(str).str.strip().str.lower()
            sub = sub[values == str(role_filter['value']).strip().lower()]
        else:
            sub = sub.iloc[0:0]

    field_col = find_column(sub, field) if sub is not None else None
    autre_col = find_column(sub, field + '_Autre__Z') if sub is not None else None
    field_vals = sub[field_col].astype(str).str.strip().str.lower() if field_col is not None else None
    autre_vals = sub[autre_col].astype(str).str.strip().str.lower() if autre_col is not None else None

    entries = []
    national_recu = 0
    for cfg in entries_cfg:
        recu = 0
        if field_vals is not None:
            for m in cfg['match']:
                if m.upper().startswith('AUTRE:'):
                    want = m.split(':', 1)[1].strip().lower()
                    if autre_vals is not None:
                        recu += int(((field_vals == 'autre') & (autre_vals == want)).sum())
                else:
                    recu += int((field_vals == m.strip().lower()).sum())
        cible = cfg['n']
        entries.append({
            'label': cfg['label'], 'recu': recu, 'cible': cible,
            'taux': round(100 * recu / cible, 1) if cible else None,
            'statut': status_for(recu, cible),
        })
        national_recu += recu

    national = {
        'recu': national_recu, 'cible': national_cible,
        'taux': round(100 * national_recu / national_cible, 1) if national_cible else None,
        'statut': status_for(national_recu, national_cible),
    }
    return {'national': national, 'entries': entries}


def named_roster_completeness(form, df):
    """Forme compatible form_completeness() : une liste à un élément, comme
    roster_completeness() — voir named_roster_detail() pour le détail par
    entité (utilisé par la page dédiée /completude/roster-national/<code>)."""
    return [named_roster_detail(form, df)['national']]


def all_named_rosters(ref, form_dataframes):
    """Calcule named_roster_detail() pour tous les formulaires roster
    national actifs (motif UGP/Programmes)."""
    result = {}
    for form in forms_registry.all_forms(include_inactive=False):
        if form.get('grain') != 'roster_national':
            continue
        df = form_dataframes.get(form['code'])
        result[form['code']] = named_roster_detail(form, df)
    return result


def form_completeness(ref, form_code, df):
    """Répartiteur : établissement, district, "roster" géographique
    (enquêteur/superviseur) ou "roster national" (grain roster_national)
    selon le grain du formulaire."""
    if form_code in etablissement_forms():
        return etablissement_completeness(ref, form_code, df)
    if form_code in district_forms():
        return district_completeness(ref, form_code, df)
    form = forms_registry.get(form_code)
    if form and form.get('grain') in ('enqueteur', 'superviseur'):
        return roster_completeness(form, df)
    if form and form.get('grain') == 'roster_national':
        return named_roster_completeness(form, df)
    raise ValueError(f"Formulaire inconnu : {form_code}")


def district_reel(district_table, form_code):
    """« Cible réelle atteinte » d'un formulaire : proportion de DISTRICTS
    ayant individuellement atteint ou dépassé 100 %, sur le nombre de
    districts pour lesquels un taux est calculé — par opposition à la cible
    agrégée (somme reçu / somme cible au niveau national), qui peut afficher
    100 % alors que la collecte reste très inégale d'un district à l'autre
    (quelques districts très en avance compensant plusieurs très en retard).

    Renvoie un dict {atteints, total, pct, css} prêt à afficher (code couleur
    d'alerte façon status-pill : vert si tous les districts y sont, orange à
    partir de la moitié, rouge en dessous), ou None si aucun district n'a de
    taux calculé pour ce formulaire (rien à afficher plutôt qu'un 0 % trompeur)."""
    total, atteints = 0, 0
    for d in district_table.values():
        taux = d['forms'].get(form_code, {}).get('taux')
        if taux is None:
            continue
        total += 1
        if taux >= 100:
            atteints += 1
    if not total:
        return None
    pct = round(100 * atteints / total, 1)
    css = 'cible' if pct >= 100 else ('en-cours' if pct >= 50 else 'verifier')
    return {'atteints': atteints, 'total': total, 'pct': pct, 'css': css}


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
            'statut': status_for(recu, cible, is_floor=rd.is_floor(code)),
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
        form = forms_registry.get(form_code)
        is_roster = bool(form) and form.get('grain') in ('enqueteur', 'superviseur')
        df = form_dataframes.get(form_code)

        if is_roster:
            # Un formulaire roster (motif RAA Phase 1 : DRS/DDS/Superviseur/
            # Enquêteurs sur le même formulaire Kobo, un role_filter chacun)
            # n'est PAS un formulaire de grain district classique — le
            # décompte brut de district_completeness() ignorerait
            # role_filter et mélangerait tous les rôles entre eux (cas réel
            # observé : les 4 colonnes affichaient la même valeur par
            # district). roster_by_district() applique le bon filtre.
            roster_result = roster_by_district(form, df, ref)
            for code in table:
                cell = roster_result['by_district'].get(code)
                table[code]['forms'][form_code] = (
                    {'recu': cell['recu'], 'cible': cell['cible'], 'taux': cell['taux'], 'statut': cell['statut']}
                    if cell else _empty_cell()
                )
            continue

        if form and form.get('grain') == 'roster_national':
            # Motif UGP/Programmes : aucune dimension district/région (cible
            # par entité nommée, pas par unité géographique) — rien à
            # afficher ici, voir /completude/roster-national/<code>.
            for code in table:
                table[code]['forms'][form_code] = _empty_cell()
            continue

        if df is None:
            for code, d in ref['districts'].items():
                cible = rd.target_for(ref, form_code, district_code=code) if form_code in district_forms() else None
                table[code]['forms'][form_code] = _empty_cell(cible)
            continue

        if form_code in etablissement_forms():
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
                table[region_code]['forms'][form_code] = _empty_cell(cible if form_code in district_forms() else None)
            else:
                table[region_code]['forms'][form_code] = {
                    'recu': recu, 'cible': cible,
                    'taux': round(100 * recu / cible, 1) if cible else None,
                    'statut': status_for(recu, cible, is_floor=rd.is_floor(form_code)),
                }
    return table


def etablissement_table(ref, form_dataframes):
    """Table établissement × formulaire (F5/F6/F7/F8/F02 uniquement — les
    formulaires au grain établissement). Utilisée pour le détail « par
    district » (liste des établissements) et « par établissement »."""
    table = {code: {'nom': e['nom_complet'], 'district_code': e['district_code'],
                     'region_code': e['region_code'], 'enqueteur_code': e['enqueteur_code'],
                     'forms': {}}
              for code, e in ref['etablissements'].items()}

    for form_code in etablissement_forms():
        df = form_dataframes.get(form_code)
        if df is None:
            for code in table:
                table[code]['forms'][form_code] = _empty_cell(
                    rd.target_for(ref, form_code, etablissement_code=code))
            continue
        rows = etablissement_completeness(ref, form_code, df)
        by_code = {r['etablissement_code']: r for r in rows}
        for code in table:
            r = by_code.get(code)
            table[code]['forms'][form_code] = (
                {'recu': r['recu'], 'cible': r['cible'], 'taux': r['taux'], 'statut': r['statut']}
                if r else _empty_cell(rd.target_for(ref, form_code, etablissement_code=code))
            )
    return table


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

    # Un formulaire « roster » (grain enquêteur/superviseur, voir
    # forms_registry.py) n'a pas de comptage par établissement — exclu ici,
    # il apparaît seulement en cible nationale agrégée (national_summary()).
    for form_code in enqueteur_forms():
        form = forms_registry.get(form_code)
        if form and form.get('grain') not in ('etablissement',):
            continue
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
    superviseur par district, reprend directement district_table().

    Les formulaires « roster » (grain enquêteur/superviseur) sont exclus de
    cette table par personne — pas de comptage par district pour eux, voir
    enqueteur_table()."""
    dtable = district_table(ref, form_dataframes)
    etab_district_codes = {fc for fc in superviseur_forms()
                            if (forms_registry.get(fc) or {}).get('grain') == 'district'}
    table = {}
    for code, s in ref['superviseurs'].items():
        d = s['district_code']
        drow = dtable.get(d, {'forms': {}})
        table[code] = {
            'nom': s['nom_complet'], 'sous_titre': d,
            'forms': {fc: drow['forms'].get(fc, _empty_cell()) for fc in etab_district_codes},
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
    N'inclut que les formulaires effectivement mappés (comme les autres vues)."""
    rows = []
    for code in rd.FORM_CODES:
        df = form_dataframes.get(code)
        if df is None:
            continue
        if code in etablissement_forms():
            for r in etablissement_completeness(ref, code, df):
                rows.append({
                    'region':        ref['regions'].get(r['region_code'], {}).get('nom', r['region_code']),
                    'district':      ref['districts'].get(r['district_code'], {}).get('nom', r['district_code']),
                    'unite':         r['etablissement_nom'],
                    'formulaire':    code,
                    'formulaire_label': rd.FORM_LABELS[code],
                    'cible': r['cible'], 'recu': r['recu'], 'taux': r['taux'], 'statut': r['statut'],
                })
        else:
            for r in district_completeness(ref, code, df):
                rows.append({
                    'region':        ref['regions'].get(r['region_code'], {}).get('nom', r['region_code']),
                    'district':      r['district_nom'],
                    'unite':         r['district_nom'],
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
                'district_code': r.get('district_code'), 'region_code': r.get('region_code'),
                'cible': r['cible'],
            })
    return out


def all_anomalies_excess(ref, form_dataframes, threshold=2.0):
    """Combine anomalies_excess() sur tous les formulaires effectivement mappés.
    Les formulaires à cible plancher (motif F07 — somme des décès SIG) sont
    exclus : la dépasser est normal, pas une anomalie (voir rd.is_floor())."""
    out = []
    for code in rd.FORM_CODES:
        if rd.is_floor(code):
            continue
        df = form_dataframes.get(code)
        if df is None:
            continue
        for r in anomalies_excess(ref, code, df, threshold=threshold):
            out.append({
                'formulaire': code, 'formulaire_label': rd.FORM_LABELS[code],
                'unite': _unit_label(r),
                'etablissement_code': r.get('etablissement_code'),
                'district_code': r.get('district_code'), 'region_code': r.get('region_code'),
                'recu': r['recu'], 'cible': r['cible'],
                'ratio': round(r['recu'] / r['cible'], 2) if r['cible'] else None,
            })
    return out
