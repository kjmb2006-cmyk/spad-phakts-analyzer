import pandas as pd
import numpy as np
import re

# Colonnes techniques KoBoToolbox à exclure automatiquement
_KOBO_META_COLS = {
    '_id', '_uuid', '_submission_time', '_validation_status', '_notes',
    '_status', '_submitted_by', '__version__', '_tags', 'meta/rootUuid',
    '_index', '_parent_table_name', '_parent_index', 'formhub/uuid', '_xform_id_string',
    '_submission__id', '_submission__uuid', '_submission__submission_time',
    '_submission__validation_status', '_submission__notes',
    '_submission__status', '_submission__submitted_by',
    '_submission___version__', '_submission__tags',
    '_submission_meta/rootUuid',
}

_GEO_DROP_PATTERN = re.compile(r'(altitude|precision)', re.IGNORECASE)
_GEO_RAW_PATTERN  = re.compile(r'géolocalisation', re.IGNORECASE)
_LAT_PATTERN      = re.compile(r'latitude', re.IGNORECASE)
_LON_PATTERN      = re.compile(r'longitude', re.IGNORECASE)
_FREE_TEXT_PATTERN = re.compile(r'^si autre', re.IGNORECASE)


def load_excel(path: str, sheet: int = 0) -> pd.DataFrame:
    """Charge un fichier Excel (KoBoToolbox ou autre) et nettoie les colonnes."""
    df = pd.read_excel(path, sheet_name=sheet, engine='openpyxl')
    df.columns = [str(c).strip() for c in df.columns]
    df.dropna(how='all', inplace=True)
    df.dropna(axis=1, how='all', inplace=True)
    return df


def _decode_by_line(raw: bytes) -> str:
    """Décode ligne par ligne : UTF-8 si la ligne l'est, sinon Windows-1252. Un
    export Kobo (UTF-8) retouché dans Excel mélange les deux ; décoder le fichier
    entier d'un seul codage abîme soit les lignes d'origine (« â€” »), soit les
    lignes ressaisies (« Ã© »). Fins de ligne CRLF, LF ou CR acceptées."""
    lines = []
    for line in re.split(rb'\r\n|\n|\r', raw):
        try:
            lines.append(line.decode('utf-8'))
        except UnicodeDecodeError:
            lines.append(line.decode('cp1252', errors='replace'))
    text = '\n'.join(lines)
    return text[1:] if text.startswith('\ufeff') else text


_PHAKTS_LIKE = re.compile(r'__[A-Za-z0-9]+(?:!|$)')


def _looks_like_header(row, columns):
    """Ligne d'en-tête supplémentaire : la plupart de ses cellules répètent le nom
    de la colonne ou sont un code PHAKTS (Radical__Affixe), jamais une réponse."""
    filled = [(c, v) for c, v in zip(columns, row) if str(v).strip()]
    if len(filled) < 5:
        return False
    hits = sum(1 for c, v in filled if v == c or _PHAKTS_LIKE.search(str(v)))
    return hits >= 0.6 * len(filled)


def load_csv(path: str):
    """Export CSV (Kobo ou retouché) → (DataFrame, notes). Séparateur détecté
    (; , tabulation), codage mélangé toléré, lignes d'en-tête répétées ou lignes
    de codes DPF proposés juste sous l'en-tête retirées des données. Les notes
    disent ce qui a été corrigé, pour que rien ne se fasse en silence."""
    with open(path, 'rb') as f:
        text = _decode_by_line(f.read())
    first = text.split('\n', 1)[0]
    delimiter = max((';', ',', '\t'), key=first.count)
    import io
    df = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False,
                     skipinitialspace=False, engine='python', on_bad_lines='skip')
    df.columns = [str(c).strip() for c in df.columns]
    notes = []
    dropped = 0
    while len(df) and dropped < 5 and _looks_like_header(df.iloc[0].tolist(), df.columns):
        df = df.iloc[1:]
        dropped += 1
    if dropped:
        notes.append(f"{dropped} ligne(s) d'en-tête supplémentaire(s) sous les noms de colonnes ignorée(s) "
                     "(noms répétés ou codes DPF proposés) : ce ne sont pas des réponses.")
    df = df.reset_index(drop=True)
    df = df.where(df != '', np.nan)
    df = df.dropna(how='all').dropna(axis=1, how='all')
    for col in df.columns:
        affix = _affix_of(col)
        if affix in ('', ) or re.match(r'^[12][A-Z]?$', affix):
            num = pd.to_numeric(df[col], errors='coerce')
            filled = df[col].dropna()
            if len(filled) and num.notna().sum() == len(filled) and not filled.astype(str).str.match(r'^0\d').any():
                df[col] = num
    return df, notes


def _affix_of(col):
    from modules.phakts_codes import affix_of
    return affix_of(col)


def load_excel_sheets(path: str) -> dict:
    """Charge toutes les feuilles d'un fichier Excel."""
    sheets = pd.read_excel(path, sheet_name=None, engine='openpyxl')
    result = {}
    for name, df in sheets.items():
        df.columns = [str(c).strip() for c in df.columns]
        df.dropna(how='all', inplace=True)
        df.dropna(axis=1, how='all', inplace=True)
        result[name] = df
    return result


def _flatten_cell(val):
    """Convertit listes/dicts en chaîne lisible pour l'analyse."""
    if isinstance(val, list):
        return ', '.join(str(v) for v in val) if val else np.nan
    if isinstance(val, dict):
        return str(val)
    return val


def clean_kobo_dataframe(df: pd.DataFrame, keep_meta_cols=()) -> pd.DataFrame:
    """
    Supprime les colonnes techniques KoBoToolbox (garde lat/lon pour la carte).
    Convertit les colonnes contenant des listes (select_multiple, GPS brut)
    en chaînes de caractères pour éviter les TypeError lors de l'analyse.

    keep_meta_cols : colonnes techniques à NE PAS supprimer malgré leur
    présence dans _KOBO_META_COLS — ex. ('_submission_time', '_submitted_by')
    pour les formulaires « roster » (motif RAA Phase 1), qui en ont besoin
    pour compter les répondants distincts et dater la dernière soumission
    par district (voir modules/completeness.py::roster_by_district()). Vide
    par défaut : comportement inchangé pour tous les autres appelants."""
    cols_to_drop = []
    for col in df.columns:
        if col in _KOBO_META_COLS:
            if col in keep_meta_cols:
                continue
            cols_to_drop.append(col)
        elif _FREE_TEXT_PATTERN.match(col):
            cols_to_drop.append(col)
        elif _GEO_DROP_PATTERN.search(col):
            cols_to_drop.append(col)
        elif _GEO_RAW_PATTERN.search(col) and not _LAT_PATTERN.search(col) and not _LON_PATTERN.search(col):
            cols_to_drop.append(col)

    df = df.drop(columns=cols_to_drop, errors='ignore')

    # Aplatir les colonnes qui contiennent des listes ou des dicts
    # (cas KoboToolbox : select_multiple, groupes répétés, GPS brut)
    for col in df.columns:
        sample = df[col].dropna()
        if len(sample) > 0 and isinstance(sample.iloc[0], (list, dict)):
            df[col] = df[col].apply(_flatten_cell)

    return df


def detect_geo_columns(df: pd.DataFrame) -> list[dict]:
    """Détecte les paires latitude/longitude dans le DataFrame."""
    lat_cols = [c for c in df.columns if _LAT_PATTERN.search(c)]
    lon_cols = [c for c in df.columns if _LON_PATTERN.search(c)]
    pairs = []
    for lat in lat_cols:
        lon_candidate = _LAT_PATTERN.sub('longitude', lat)
        matches = [c for c in lon_cols if c.lower() == lon_candidate.lower()]
        if not matches:
            matches = lon_cols[:1]
        if matches:
            name = _LAT_PATTERN.sub('', lat).strip('_ ') or 'Position'
            pairs.append({'lat': lat, 'lon': matches[0], 'name': name})
    return pairs


def get_var_types(df: pd.DataFrame) -> dict:
    """
    Détecte le type de chaque variable :
    - 'binaire'     : 0/1 uniquement
    - 'categorielle': texte ou ≤ 15 modalités
    - 'continue'    : numérique > 15 valeurs uniques
    - 'date'        : dates/timestamps
    - 'texte_libre' : chaînes longues non catégorielles
    """
    types = {}
    for col in df.columns:
        series = df[col].dropna()
        if len(series) == 0:
            types[col] = 'categorielle'
            continue

        # Date
        if pd.api.types.is_datetime64_any_dtype(series):
            types[col] = 'date'
            continue

        # Numeric
        if pd.api.types.is_numeric_dtype(series):
            try:
                uniq = series.nunique()
                vals = set(series.unique())
            except TypeError:
                series = series.astype(str)
                uniq = series.nunique()
                vals = set()
            if vals <= {0, 1}:
                types[col] = 'binaire'
            elif uniq <= 15:
                types[col] = 'categorielle'
            else:
                types[col] = 'continue'
        else:
            # String / object — peut contenir des listes (KoboToolbox)
            try:
                uniq = series.nunique()
            except TypeError:
                # Valeurs non-hashables (listes, dicts) → convertir en str
                series = series.apply(
                    lambda v: ', '.join(str(x) for x in v) if isinstance(v, list)
                    else str(v) if isinstance(v, dict) else v
                )
                uniq = series.nunique()
            avg_len = series.astype(str).str.len().mean()
            if uniq <= 20:
                types[col] = 'categorielle'
            elif avg_len > 50:
                types[col] = 'texte_libre'
            else:
                types[col] = 'categorielle'
    return types


def summarize_dataframe(df: pd.DataFrame) -> dict:
    """Résumé stocké tel quel dans session['data_meta'] — donc dans le cookie
    de session Flask, limité à ~4 Ko par les navigateurs. 'columns' (la liste
    complète des noms de colonnes) n'est lue nulle part dans le code mais
    gonflait ce résumé bien au-delà de cette limite dès qu'un formulaire a
    beaucoup de colonnes à noms longs (ex. RAA Phase 1 : 292 colonnes
    préfixées par groupe, certaines > 70 caractères) — le navigateur rejette
    alors silencieusement le cookie, donc TOUTE la session (data_path,
    kobo_uid...) reste bloquée sur son état précédent malgré une
    synchronisation signalée comme réussie (cas réel : tableau de bord
    "Suivi d'un formulaire" resté bloqué sur d'anciennes données après
    plusieurs synchronisations manifestement réussies)."""
    var_types = get_var_types(df)
    counts = {t: 0 for t in ['categorielle', 'continue', 'binaire', 'date', 'texte_libre']}
    for t in var_types.values():
        counts[t] = counts.get(t, 0) + 1
    missing = int(df.isnull().sum().sum())
    total_cells = df.shape[0] * df.shape[1]
    return {
        'n_obs':         df.shape[0],
        'n_vars':        df.shape[1],
        'n_categorielle': counts['categorielle'],
        'n_continue':    counts['continue'],
        'n_binaire':     counts['binaire'],
        'n_date':        counts['date'],
        'missing':       missing,
        'missing_pct':   round(missing / total_cells * 100, 1) if total_cells > 0 else 0,
    }


def get_filtered_vars(df: pd.DataFrame, types_wanted: list) -> list:
    """Retourne les colonnes dont le type est dans types_wanted."""
    vt = get_var_types(df)
    return [col for col, t in vt.items() if t in types_wanted]
