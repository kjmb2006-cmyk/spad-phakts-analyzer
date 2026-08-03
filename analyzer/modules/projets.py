"""
SPAD Analyzer — Projets d'enquête génériques

Généralise le suivi de complétude (même logique reçu/cible/taux/statut que
le référentiel SPAD — modules/reference_data.py + modules/completeness.py)
à N'IMPORTE QUELLE enquête KoboToolbox ou ODK, pas seulement les 7
formulaires SPAD officiels.

Contrairement au référentiel SPAD (régions/districts/établissements figés,
règles de cible spécifiques par formulaire — F6 selon le type, F02 fixe,
F07 sur les décès SIG...), un « projet » générique repose sur un fichier de
référence fourni par l'utilisateur : une ligne par unité de collecte
(établissement, école, village, ménage...), avec au minimum :
  - code  : identifiant de l'unité — DOIT correspondre exactement à la
            valeur soumise dans le champ Kobo/ODK choisi (ex. le code
            d'un select_one)
  - cible : nombre de soumissions attendues pour cette unité
et optionnellement :
  - nom    : libellé affiché (reprend `code` si absent)
  - groupe : zone/district/région d'agrégation (facultatif)

Ce module ne connaît rien à SPAD — il ne fait que réutiliser status_for()
de completeness.py pour rester visuellement et sémantiquement cohérent
(mêmes statuts : zero / en_cours / cible / verifier).
"""
import os
import json
import uuid
import shutil
import datetime
import pandas as pd

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJETS_DIR = os.path.join(_BASE_DIR, 'data', 'projets')

REQUIRED_COLUMNS = ('code', 'cible')
OPTIONAL_COLUMNS = ('nom', 'groupe')


def _index_path():
    return os.path.join(PROJETS_DIR, 'index.json')


def _load_index():
    os.makedirs(PROJETS_DIR, exist_ok=True)
    p = _index_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _save_index(items):
    os.makedirs(PROJETS_DIR, exist_ok=True)
    with open(_index_path(), 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def list_projets():
    return _load_index()


def get_projet(projet_id):
    return next((p for p in _load_index() if p['id'] == projet_id), None)


def _reference_path(projet_id):
    return os.path.join(PROJETS_DIR, projet_id, 'reference.xlsx')


def _cache_path(projet_id):
    return os.path.join(PROJETS_DIR, projet_id, 'resultat.json')


def validate_reference_file(path):
    """Vérifie que le fichier a bien les colonnes minimales. Lève ValueError sinon.
    Retourne le nombre de lignes valides (avec un code non vide)."""
    df = pd.read_excel(path)
    cols_lower = {str(c).lower().strip(): c for c in df.columns}
    missing = [c for c in REQUIRED_COLUMNS if c not in cols_lower]
    if missing:
        raise ValueError(
            f"Colonne(s) manquante(s) dans le fichier de référence : {', '.join(missing)}. "
            f"Attendu au minimum : code, cible (optionnel : nom, groupe)."
        )
    n_valid = df[cols_lower['code']].astype(str).str.strip().replace('nan', '').ne('').sum()
    if n_valid == 0:
        raise ValueError("Aucune ligne avec un code valide dans le fichier de référence.")
    return int(n_valid)


def create_projet(nom, reference_file_storage, champ_unite, kobo_uid=None, kobo_name=None, kobo_instance=None):
    """Crée un projet à partir d'un fichier Excel uploadé (werkzeug FileStorage)."""
    projet_id = uuid.uuid4().hex[:10]
    projet_dir = os.path.join(PROJETS_DIR, projet_id)
    os.makedirs(projet_dir, exist_ok=True)
    ref_path = os.path.join(projet_dir, 'reference.xlsx')
    reference_file_storage.save(ref_path)

    try:
        n_unites = validate_reference_file(ref_path)
    except ValueError:
        shutil.rmtree(projet_dir, ignore_errors=True)
        raise

    entry = {
        'id': projet_id,
        'nom': nom,
        'champ_unite': champ_unite,
        'kobo_uid': kobo_uid,
        'kobo_name': kobo_name,
        'kobo_instance': kobo_instance,
        'n_unites': n_unites,
        'created_at': datetime.datetime.now().strftime('%d/%m/%Y %H:%M'),
        'computed_at': None,
        'has_xlsform': False,
        'analyse_computed_at': None,
    }
    items = _load_index()
    items.append(entry)
    _save_index(items)
    return entry


def update_kobo_link(projet_id, kobo_uid, kobo_name, kobo_instance=None):
    items = _load_index()
    for p in items:
        if p['id'] == projet_id:
            p['kobo_uid'] = kobo_uid
            p['kobo_name'] = kobo_name
            p['kobo_instance'] = kobo_instance
    _save_index(items)


def delete_projet(projet_id):
    items = [p for p in _load_index() if p['id'] != projet_id]
    _save_index(items)
    projet_dir = os.path.join(PROJETS_DIR, projet_id)
    if os.path.isdir(projet_dir):
        shutil.rmtree(projet_dir, ignore_errors=True)


def load_reference(projet_id):
    """Retourne {code: {'nom', 'cible', 'groupe'}} depuis le fichier stocké."""
    df = pd.read_excel(_reference_path(projet_id))
    cols = {str(c).lower().strip(): c for c in df.columns}
    out = {}
    for _, row in df.iterrows():
        raw_code = row.get(cols['code'])
        if pd.isna(raw_code):
            continue
        code = str(raw_code).strip()
        if not code:
            continue
        cible_raw = row.get(cols['cible'])
        try:
            cible = int(cible_raw) if pd.notna(cible_raw) else 0
        except (ValueError, TypeError):
            cible = 0
        nom = str(row[cols['nom']]).strip() if 'nom' in cols and pd.notna(row.get(cols['nom'])) else code
        groupe = str(row[cols['groupe']]).strip() if 'groupe' in cols and pd.notna(row.get(cols['groupe'])) else None
        out[code] = {'nom': nom, 'cible': cible, 'groupe': groupe}
    return out


def find_unit_column(df, champ_unite):
    """Retrouve la colonne d'unité par nom exact ou suffixe `.../champ` (préfixe
    de groupe Kobo) — même logique que completeness.find_column()."""
    if champ_unite is None or df is None:
        return None
    if champ_unite in df.columns:
        return champ_unite
    for c in df.columns:
        if str(c).endswith('/' + champ_unite):
            return c
    return None


def unit_completeness(reference, champ_unite, df):
    """reçu/cible/taux/statut par unité — réutilise status_for() de completeness.py."""
    from modules.completeness import status_for
    col = find_unit_column(df, champ_unite)
    counts = df[col].astype(str).str.strip().value_counts().to_dict() if col is not None else {}

    rows = []
    for code, unit in reference.items():
        recu = int(counts.get(code, 0))
        cible = unit['cible']
        rows.append({
            'code': code, 'nom': unit['nom'], 'groupe': unit['groupe'],
            'recu': recu, 'cible': cible,
            'taux': round(100 * recu / cible, 1) if cible else None,
            'statut': status_for(recu, cible),
        })
    return rows


def group_completeness(rows):
    """Agrège unit_completeness() par groupe (colonne facultative du référentiel)."""
    from modules.completeness import status_for
    groups = {}
    for r in rows:
        g = r['groupe'] or '(sans groupe)'
        a = groups.setdefault(g, {'recu': 0, 'cible': 0})
        a['recu'] += r['recu']
        a['cible'] += (r['cible'] or 0)
    out = []
    for g, a in groups.items():
        out.append({
            'groupe': g, 'recu': a['recu'], 'cible': a['cible'],
            'taux': round(100 * a['recu'] / a['cible'], 1) if a['cible'] else None,
            'statut': status_for(a['recu'], a['cible']),
        })
    out.sort(key=lambda x: x['groupe'])
    return out


def save_result(projet_id, rows, groups):
    with open(_cache_path(projet_id), 'w', encoding='utf-8') as f:
        json.dump({'unites': rows, 'groupes': groups}, f, ensure_ascii=False)
    items = _load_index()
    for p in items:
        if p['id'] == projet_id:
            p['computed_at'] = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    _save_index(items)


def load_result(projet_id):
    path = _cache_path(projet_id)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────
# Analyse épidémiologique générique (XLSForm → dictionnaire → statistiques)
#
# Étend un projet (déjà défini par son fichier de référence code/cible/
# groupe ci-dessus) avec un XLSForm optionnel : dictionnaire de variables
# auto-généré (modules/xlsform_dictionary.py), édité par l'utilisateur,
# puis analysé (modules/enquete_analyse.py) — fonctionne pour n'importe
# quel questionnaire, pas seulement les formulaires SPAD.
# ─────────────────────────────────────────────────────────────────────────

def _xlsform_path(projet_id):
    return os.path.join(PROJETS_DIR, projet_id, 'xlsform.xlsx')


def _dictionnaire_path(projet_id):
    return os.path.join(PROJETS_DIR, projet_id, 'dictionnaire.csv')


def _rapport_path(projet_id):
    return os.path.join(PROJETS_DIR, projet_id, 'rapport_analyse.docx')


def _analyse_resume_path(projet_id):
    return os.path.join(PROJETS_DIR, projet_id, 'analyse_resume.json')


def rapport_path(projet_id):
    """Chemin du rapport Word généré — None si pas encore d'analyse."""
    p = _rapport_path(projet_id)
    return p if os.path.exists(p) else None


def attach_xlsform(projet_id, file_storage):
    """Enregistre le XLSForm et génère le dictionnaire de variables initial
    (suggestions éditables — voir modules/xlsform_dictionary.py)."""
    from modules.xlsform_dictionary import parse_xlsform
    projet_dir = os.path.join(PROJETS_DIR, projet_id)
    os.makedirs(projet_dir, exist_ok=True)
    xls_path = _xlsform_path(projet_id)
    file_storage.save(xls_path)

    try:
        dic = parse_xlsform(xls_path)
    except Exception as e:
        try:
            os.remove(xls_path)
        except OSError:
            pass
        raise ValueError(f"Impossible de lire le XLSForm (feuilles 'survey'/'choices' attendues) : {e}")

    dic.to_csv(_dictionnaire_path(projet_id), index=False, encoding='utf-8-sig')

    items = _load_index()
    for p in items:
        if p['id'] == projet_id:
            p['has_xlsform'] = True
    _save_index(items)
    return len(dic)


def load_dictionnaire(projet_id):
    path = _dictionnaire_path(projet_id)
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, keep_default_na=False, na_values=['']).fillna('')


def save_dictionnaire(projet_id, df):
    df.to_csv(_dictionnaire_path(projet_id), index=False, encoding='utf-8-sig')


def run_analysis(projet_id, data_df):
    """Exécute l'analyse complète (statistiques univariées, scores
    composites, croisement, stratification, qualité des données, rapport
    Word) à partir du dictionnaire validé et des données Kobo/ODK réelles.
    Réutilise la complétude par groupe déjà calculée (load_result) plutôt
    que de la recalculer."""
    from modules import enquete_analyse as ea

    p = get_projet(projet_id)
    dic = load_dictionnaire(projet_id)
    if dic is None:
        raise ValueError("Aucun dictionnaire — attachez d'abord un XLSForm.")

    dic, manquantes, extra_cols = ea.match_columns(dic, data_df)
    univ = ea.univariate_table(dic, data_df)
    scores, detail_domaines, items_ignores = ea.compute_composite_scores(dic, data_df)
    corr, corr_tests = ea.croisement_scores(scores)
    strat_df = ea.stratified_analysis(dic, data_df, scores)
    qual_df, couverture = ea.data_quality_table(dic, data_df, manquantes, extra_cols)

    resultat = load_result(projet_id)
    groupe_completude = resultat['groupes'] if resultat else None

    figures = ea.make_figures(scores, corr, strat_df, groupe_completude)
    try:
        docx_bytes = ea.build_report(
            p['nom'], len(data_df), univ, scores, detail_domaines, items_ignores,
            corr, corr_tests, strat_df, qual_df, couverture, figures, groupe_completude,
        )
    finally:
        for fp in figures.values():
            try:
                os.remove(fp)
            except OSError:
                pass

    with open(_rapport_path(projet_id), 'wb') as f:
        f.write(docx_bytes)

    resume = {
        'n_soumissions': len(data_df),
        'n_variables_dictionnaire': len(dic),
        'n_non_trouvees': len(manquantes),
        'variables_non_trouvees': list(manquantes['nom']),
        'n_colonnes_hors_dictionnaire': len(extra_cols),
        'scores': {
            domaine: {
                'n': int(scores[f'Score_{domaine}'].notna().sum()),
                'moyenne': round(float(scores[f'Score_{domaine}'].mean()), 1),
                'mediane': round(float(scores[f'Score_{domaine}'].median()), 1),
                'items': items,
            }
            for domaine, items in detail_domaines.items()
            if f'Score_{domaine}' in scores.columns and scores[f'Score_{domaine}'].notna().any()
        },
        'n_anomalies_completion': len(couverture.get('anomalies_completion', [])),
        'n_variables_stratification': int(strat_df['stratification'].nunique()) if not strat_df.empty else 0,
    }
    with open(_analyse_resume_path(projet_id), 'w', encoding='utf-8') as f:
        json.dump(resume, f, ensure_ascii=False)

    items = _load_index()
    for pi in items:
        if pi['id'] == projet_id:
            pi['analyse_computed_at'] = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    _save_index(items)

    return resume


def load_analyse_resume(projet_id):
    path = _analyse_resume_path(projet_id)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
