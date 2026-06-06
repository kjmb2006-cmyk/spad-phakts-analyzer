"""
Génération de commentaires automatiques (1-2 phrases) pour chaque résultat
d'analyse. Repris dans l'UI sous chaque variable, et dans le rapport PDF/Word.
"""

def auto_comment_categorical(r: dict) -> str:
    """Commentaire pour un tri à plat (variable catégorielle)."""
    var = r.get('variable', 'Variable')
    mode = r.get('mode_val', '—')
    mode_pct = r.get('mode_pct', 0)
    n_cats = r.get('n_cats', 0)
    missing_pct = r.get('missing_pct', 0)
    hhi = r.get('hhi', 0)

    # Diversité — HHI Hirschman-Herfindahl (0..1) : 1 = mono-catégorie ; faible = équirépartition
    if hhi >= 0.5:
        diversity = 'distribution très concentrée'
    elif hhi >= 0.25:
        diversity = 'concentration modérée'
    else:
        diversity = 'distribution équilibrée'

    parts = [
        f"Mode : « {mode} » ({mode_pct}% des observations valides)",
        f"{n_cats} modalité{'s' if n_cats > 1 else ''} — {diversity}",
    ]
    if missing_pct > 0:
        parts.append(f"{missing_pct}% de valeurs manquantes")
    return " · ".join(parts) + "."


def auto_comment_continuous(r: dict) -> str:
    """Commentaire pour une variable continue."""
    if r.get('error'):
        return r['error']
    mean = r.get('mean', 0)
    median = r.get('median', 0)
    std = r.get('std', 0)
    cv = r.get('cv', 0)
    n_out = r.get('n_outliers', 0)
    missing_pct = r.get('missing_pct', 0)
    is_normal = r.get('is_normal', False)
    n_valid = r.get('n_valid', 0)

    # Coefficient de variation
    try:
        cv_v = float(cv) if cv not in (None, '—') else 0
    except (TypeError, ValueError):
        cv_v = 0
    if cv_v == 0 or cv_v is None:
        disp_label = 'dispersion non calculable'
    elif cv_v < 0.15:
        disp_label = 'faible dispersion'
    elif cv_v < 0.35:
        disp_label = 'dispersion modérée'
    else:
        disp_label = 'forte dispersion'

    skew_hint = ''
    try:
        if median and mean and abs(mean - median) / max(abs(median), 1) > 0.15:
            skew_hint = ' · distribution asymétrique (mean ≠ median)'
    except (TypeError, ZeroDivisionError):
        pass

    parts = [
        f"Moyenne {mean} (écart-type {std}) · Médiane {median}",
        f"{disp_label}{skew_hint}",
    ]
    if n_out:
        parts.append(f"{n_out} valeur{'s' if n_out > 1 else ''} aberrante{'s' if n_out > 1 else ''} (IQR)")
    if missing_pct > 0:
        parts.append(f"{missing_pct}% manquants")
    if not is_normal and n_valid > 8:
        parts.append("normalité rejetée")
    return " · ".join(parts) + "."


def auto_comment_crosstab(r: dict) -> str:
    """Commentaire pour un tableau croisé."""
    sig = r.get('sig_label', '')
    assoc = r.get('assoc_label', '')
    cv = r.get('cramers_v', 0)
    n = r.get('n', 0)
    return (f"Association {assoc} (V de Cramér = {cv}) · "
            f"{sig.capitalize()} · n = {n} observations.")


def auto_comment_binary_group(r: dict) -> str:
    """Commentaire pour une analyse de groupe binaire (questions multi-choix)."""
    parent = r.get('parent', '')
    rows = r.get('rows', [])
    if not rows:
        return f"Groupe « {parent} » : aucune donnée exploitable."
    # rows est typiquement [{'variable': ..., 'count': ..., 'pct': ...}]
    top = max(rows, key=lambda x: x.get('pct', x.get('count', 0)))
    name = top.get('label') or top.get('variable', '?')
    pct = top.get('pct', '?')
    return (f"{len(rows)} modalités proposées · "
            f"Modalité la plus citée : « {name} » ({pct}%).")
