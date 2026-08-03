import pandas as pd
import numpy as np
import re

# Colonnes techniques KoBoToolbox à exclure automatiquement
_KOBO_META_COLS = {
    '_id', '_uuid', '_submission_time', '_validation_status', '_notes',
    '_status', '_submitted_by', '__version__', '_tags', 'meta/rootUuid',
    '_index', '_parent_table_name', '_parent_index', 'formhub/uuid',
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


def clean_kobo_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Supprime les colonnes techniques KoBoToolbox (garde lat/lon pour la carte).
    Convertit les colonnes contenant des listes (select_multiple, GPS brut)
    en chaînes de caractères pour éviter les TypeError lors de l'analyse.
    """
    cols_to_drop = []
    for col in df.columns:
        if col in _KOBO_META_COLS:
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
        'columns':       df.columns.tolist(),
    }


def get_filtered_vars(df: pd.DataFrame, types_wanted: list) -> list:
    """Retourne les colonnes dont le type est dans types_wanted."""
    vt = get_var_types(df)
    return [col for col, t in vt.items() if t in types_wanted]
