"""
Lecture automatique de chaque résultat d'analyse. Reprise dans l'interface sous chaque variable
(bloc « Lecture automatique » + commentaire libre) et dans les rapports PDF/Word/Excel.

Même esprit que la comparaison multi-enquête (modules/multi_comments.py) : on dit ce que l'on observe
avec ses intervalles de confiance, on dit si un écart ou une association est établi et de quelle
intensité, on signale les précautions (effectifs faibles, valeurs manquantes, effectifs théoriques
trop petits, distribution asymétrique). On décrit et on nuance ; on ne conclut jamais à une cause.

Chaque fonction renvoie du texte en puces (une par ligne, « • »), chiffres à la française.
"""
from modules.multi_comments import _fr

SMALL_N = 30
MISSING_WARN = 20           # % de valeurs manquantes à partir duquel on met en garde
RARE_PCT = 5


def _name(x, limit=48):
    from modules.dataset import readable
    return readable(x, limit)


def _lines(*items):
    return '\n'.join(f'• {i}' for i in items if i)


def _missing_line(pct, n_missing):
    if not pct:
        return ''
    base = f"Valeurs manquantes : {_fr(pct)} % ({n_missing})"
    return base + (" — part élevée : les résultats ne portent que sur les répondants." if pct >= MISSING_WARN else '.')


def _small_line(n):
    return f"Effectif faible (n = {n}) : lecture prudente, les intervalles de confiance sont larges." if n and n < SMALL_N else ''


# ─── Variable catégorielle ───────────────────────────────────────────────────

def auto_comment_categorical(r: dict) -> str:
    rows = r.get('rows') or []
    n_valid = r.get('n_valid') or 0
    if r.get('empty') or not rows:
        return "Aucune valeur valide pour cette variable."
    top = rows[0]
    lead = (f"« {top['modalite']} » est la modalité la plus fréquente : {_fr(top['pct'])} % "
            f"(IC à 95 % [{_fr(top['ic_lo'])} ; {_fr(top['ic_hi'])}], n = {top['n']})")
    if len(rows) > 1:
        second = rows[1]
        gap = top['pct'] - second['pct']
        lead += f", devant « {second['modalite']} » ({_fr(second['pct'])} %)"
        lead += '.' if gap >= 10 else " — écart mince : les deux modalités ne se distinguent pas nettement."
    else:
        lead += '.'
    top3 = sum(x['pct'] for x in rows[:3])
    shape = (f"{len(rows)} modalités ; les 3 premières cumulent {_fr(min(top3, 100))} %" if len(rows) > 3
             else f"{len(rows)} modalité{'s' if len(rows) > 1 else ''}")
    if r.get('hhi') is not None:
        shape += (" — distribution très concentrée." if r['hhi'] >= 0.5 else " — concentration modérée." if r['hhi'] >= 0.25
                  else " — distribution équilibrée.")
    rare = [x for x in rows if x['pct'] < RARE_PCT]
    rare_line = (f"{len(rare)} modalité(s) rare(s) (< {RARE_PCT} %) : à regrouper avant tout croisement."
                 if len(rare) >= 2 and len(rows) > 4 else '')
    return _lines(lead, shape, rare_line, _missing_line(r.get('missing_pct'), r.get('missing')), _small_line(n_valid))


# ─── Variable continue ───────────────────────────────────────────────────────

def auto_comment_continuous(r: dict) -> str:
    if r.get('error'):
        return r['error']
    n = r.get('n_valid') or 0
    mean, median, std = r.get('mean'), r.get('median'), r.get('std')
    ci = f" (IC à 95 % [{_fr(r['ic_lo'], 2)} ; {_fr(r['ic_hi'], 2)}])" if r.get('ic_lo') is not None else ''
    lead = f"Moyenne {_fr(mean, 2)}{ci}, médiane {_fr(median, 2)}" + (f" (Q1-Q3 : {_fr(r['q1'], 1)} – {_fr(r['q3'], 1)})" if r.get('q1') is not None else '') + f" ; n = {n}."
    cv = r.get('cv')
    disp = ''
    if cv is not None:
        label = 'faible' if cv < 15 else 'modérée' if cv < 35 else 'forte'          # cv en %
        disp = f"Dispersion {label} (coefficient de variation {_fr(cv, 0)} %, écart-type {_fr(std, 2)})."
    skew = r.get('skew')
    shape = ''
    if skew is not None and abs(skew) >= 1:
        side = 'à droite (quelques valeurs élevées)' if skew > 0 else 'à gauche (quelques valeurs faibles)'
        shape = f"Distribution asymétrique {side} (asymétrie {_fr(skew, 1)}) : la médiane résume mieux que la moyenne."
    elif std and mean is not None and median is not None and abs(mean - median) > 0.25 * std:
        shape = "Moyenne et médiane s'écartent : la médiane résume mieux la valeur typique."
    outliers = (f"{r['n_outliers']} valeur(s) hors des barrières de Tukey (1,5 × écart interquartile) [{_fr(r['fence_low'], 1)} ; {_fr(r['fence_high'], 1)}] : "
                "à vérifier avant d'interpréter la moyenne.") if r.get('n_outliers') else ''
    normal = ''
    if r.get('normality_p') is not None and n > 8:
        normal = (f"Normalité rejetée ({r['normality_test']}, p {'< 0,001' if r['normality_p'] < 0.001 else '= ' + _fr(r['normality_p'], 3)}) : "
                  "préférer les tests non paramétriques pour comparer des groupes." if not r.get('is_normal') else
                  f"Compatible avec une loi normale ({r['normality_test']}, p = {_fr(r['normality_p'], 3)}).")
    return _lines(lead, disp, shape, outliers, normal, _missing_line(r.get('missing_pct'), r.get('n_missing')), _small_line(n))


# ─── Question à choix multiples ──────────────────────────────────────────────

def auto_comment_binary_group(r: dict) -> str:
    rows = r.get('rows') or []
    parent = _name(r.get('parent', ''))
    if not rows:
        return f"Question « {parent} » : aucune donnée exploitable."
    n = r.get('n_total') or 0
    top = rows[0]
    lead = (f"{len(rows)} choix proposés ; le plus cité est « {top['option']} » : {_fr(top['pct'])} % des répondants "
            f"(IC à 95 % [{_fr(top['ic_lo'])} ; {_fr(top['ic_hi'])}], n = {top['n']}) sur {n} répondants.")
    over50 = [x for x in rows if x['pct'] >= 50]
    spread = (f"{len(over50)} choix {'dépasse' if len(over50) == 1 else 'dépassent'} 50 % des répondants" if over50
              else "Aucun choix ne dépasse 50 % des répondants")
    if r.get('mean_choices') is not None:
        spread += f" ; un répondant en cite en moyenne {_fr(r['mean_choices'], 1)}."
    else:
        spread += '.'
    rare = [x for x in rows if x['pct'] < RARE_PCT]
    rare_line = f"{len(rare)} choix cité(s) par moins de {RARE_PCT} % des répondants." if len(rare) >= 2 else ''
    return _lines(lead, spread, rare_line, _small_line(n))


# ─── Croisement de deux variables ────────────────────────────────────────────

def _cell_sentence(c):
    sens = 'plus' if c['residual'] > 0 else 'moins'
    return (f"parmi « {_name(c['row'])} » ({c['row_total']}), {_fr(c['row_share'])} % sont « {_name(c['col'])} » contre "
            f"{_fr(c['overall_share'])} % en moyenne : {sens} que si les deux variables étaient indépendantes (résidu {_fr(c['residual'], 1).replace('-', '−')}).")


def auto_comment_crosstab(r: dict) -> str:
    if r.get('chi2') is None and r.get('cramers_v') is None:
        return r.get('auto_comment', '') or ''
    v, p = r.get('cramers_v'), r.get('p_val')
    significant = p is not None and p < 0.05
    if significant:
        lead = (f"Association {r['assoc_label']} entre les deux variables (V de Cramér = {_fr(v, 2)}, χ² = {_fr(r['chi2'], 1)}, "
                f"{'p < 0,001' if p < 0.001 else 'p = ' + _fr(p, 3)}), n = {r['n']}.")
    else:
        lead = (f"Aucune association établie (χ² = {_fr(r['chi2'], 1)}, p = {_fr(p, 3)}, V = {_fr(v, 2)}), n = {r['n']} : "
                "les écarts observés peuvent tenir au hasard de l'échantillonnage.")
    cells = [_cell_sentence(c) for c in (r.get('top_cells') or [])[:3]] if significant else []
    extra = []
    if r.get('odds_ratio') is not None:
        lo, hi = r['or_ci']
        extra.append(f"Odds ratio = {_fr(r['odds_ratio'], 2)} (IC à 95 % [{_fr(lo, 2)} ; {_fr(hi, 2)}])"
                     + (f" ; test exact de Fisher p = {_fr(r['fisher_p'], 3)}." if r.get('fisher_p') is not None else '.'))
    elif r.get('fisher_p') is not None:
        extra.append(f"Test exact de Fisher : p = {_fr(r['fisher_p'], 3)}.")
    return _lines(lead, *cells, *extra, r.get('warning'))


def auto_comment_pivot(r: dict) -> str:
    """Tableau croisé qui n'est pas un simple comptage de deux variables : plus haute et plus basse valeur."""
    frame = (r.get('frames') or {}).get('Tableau')
    head = f"{r.get('agg_label', 'Valeur')} de « {_name(r['value_var'])} »" if r.get('value_var') else "Effectifs"
    head += f" selon {' × '.join(_name(x) for x in r['rows'])}" + (f" et {' × '.join(_name(x) for x in r['cols'])}" if r.get('cols') else '') + '.'
    items = [head]
    try:
        body = frame.iloc[:-1, :-1] if frame.shape[1] > 1 else frame.iloc[:-1]
        flat = body.stack().dropna()
        if len(flat) >= 2:
            hi, lo = flat.idxmax(), flat.idxmin()
            label = lambda idx: ' / '.join(str(x) for x in (idx if isinstance(idx, tuple) else (idx,)))
            items.append(f"Valeur la plus élevée : {_fr(float(flat.max()), 2)} ({label(hi)}) ; la plus basse : {_fr(float(flat.min()), 2)} ({label(lo)}).")
        total = frame.iloc[-1, -1]
        items.append(f"Ensemble : {_fr(float(total), 2)}.")
    except Exception:
        pass
    items.append(r.get('pct_note'))
    items.append("Aucun test d'association n'est calculé pour cette présentation : choisissez une ligne, une colonne et le comptage pour en obtenir un."
                 if r.get('chi2') is None and len(r['rows']) + len(r.get('cols', [])) > 2 else '')
    return _lines(*items)


def auto_comment_strata(s: dict) -> str:
    if not s:
        return ''
    items = [f"Croisement refait dans {len(s['levels'])} strate(s) de « {_name(s['layer'])} »"
             + (f" ({s['n_levels_total'] - s['shown']} strate(s) non affichée(s))" if s['n_levels_total'] > s['shown'] else '') + '.']
    for b in s['levels']:
        verdict = ('association établie' if b['p_val'] is not None and b['p_val'] < 0.05 else 'pas d\'association établie')
        items.append(f"« {b['level']} » (n = {b['n']}) : {verdict}"
                     + (f", V = {_fr(b['cramers_v'], 2)}" if b['cramers_v'] is not None else '')
                     + (f", odds ratio {_fr(b['odds_ratio'], 2)}" if b.get('odds_ratio') is not None else '') + '.')
    if s.get('mh'):
        orr, (lo, hi), p = s['mh']
        items.append(f"Odds ratio commun de Mantel-Haenszel = {_fr(orr, 2)} (IC à 95 % [{_fr(lo, 2)} ; {_fr(hi, 2)}], p {'< 0,001' if p < 0.001 else '= ' + _fr(p, 3)}), "
                     f"à comparer à l'odds ratio brut {_fr(s['crude_or'], 2)}.")
        if s.get('confounding'):
            items.append(f"Les deux diffèrent de plus de 20 % : « {_name(s['layer'])} » est probablement un facteur de confusion — "
                         "lire l'association à l'intérieur des strates, pas sur l'ensemble.")
    return _lines(*items)


def auto_comment_choix_multiples(r: dict) -> str:
    rows = sorted(r['rows'], key=lambda x: -x['pct_all'])
    var = _name(r['var'])
    sig = [x for x in rows if x['significant']]
    lead = (f"{r['n_options']} choix croisés avec « {var} » ({r['n_respondents']} répondants). "
            + (f"{len(sig)} choix diffèrent nettement selon « {var} » après correction des tests multiples."
               if sig else "Aucun choix ne diffère nettement selon cette variable après correction des tests multiples."))
    items = [lead]
    for x in sig[:3]:
        items.append(f"« {x['option']} » : cité par {_fr(x['pct_all'])} % de l'ensemble, mais de façon inégale selon les catégories "
                     f"(V = {_fr(x['cramers_v'], 2)}, q {'< 0,001' if x['q_val'] < 0.001 else '= ' + _fr(x['q_val'], 3)}) — voir le tableau des parts.")
    small = [c for c, n in r['category_sizes'].items() if n < SMALL_N]
    if small:
        items.append("Catégories à effectif faible : " + ', '.join(f"« {_name(c)} » ({r['category_sizes'][c]})" for c in small) + " — lecture prudente.")
    if any(x['warning'] for x in r['rows']):
        items.append("Certains tests reposent sur des effectifs théoriques faibles : s'appuyer sur la lecture descriptive pour ces choix.")
    return _lines(*items)


# ─── Variable décomposée par un sous-groupe ──────────────────────────────────

def auto_comment_group(r: dict) -> str:
    g = _name(r['group'])
    t = r.get('test')
    if r['kind'] == 'continuous':
        order = sorted(r['groups'], key=lambda x: -x['mean'])
        lead = (f"Moyenne la plus élevée : « {_name(order[0]['name'])} » ({_fr(order[0]['mean'], 2)}) ; la plus basse : "
                f"« {_name(order[-1]['name'])} » ({_fr(order[-1]['mean'], 2)}), selon « {g} ».")
        verdict = ''
        if t:
            verdict = (f"Écart entre groupes établi ({t['test']}, p {'< 0,001' if t['p_value'] < 0.001 else '= ' + _fr(t['p_value'], 3)})."
                       if t['p_value'] < 0.05 else f"Aucun écart établi entre groupes ({t['test']}, p = {_fr(t['p_value'], 3)}).")
        small = [x for x in r['groups'] if x['n'] < SMALL_N]
    else:
        lead = f"Répartition de la variable selon « {g} » ({len(r['groups'])} groupes)."
        verdict = ''
        if t:
            verdict = (f"Association {t['assoc_label']} établie (V = {_fr(t['cramers_v'], 2)}, p {'< 0,001' if t['p_val'] < 0.001 else '= ' + _fr(t['p_val'], 3)})."
                       if t['p_val'] < 0.05 else f"Aucune association établie (p = {_fr(t['p_val'], 3)}).")
            verdict += (' ' + t['warning']) if t.get('warning') else ''
        small = [x for x in r['groups'] if x['n'] < SMALL_N]
    smalls = ("Groupes à effectif faible : " + ', '.join(f"« {_name(x['name'])} » ({x['n']})" for x in small) + " — lecture prudente.") if small else ''
    return _lines(lead, verdict, smalls)


# ─── Analyses multivariées ───────────────────────────────────────────────────

def auto_comment_multivariate(r: dict) -> str:
    method = r.get('method', '')
    if method == 'ACP':
        ine, cum = r['inertia'], r['cumulative']
        k = min(r['n_components'], len(ine))
        lead = (f"Les {k} premiers axes résument {_fr(cum[k - 1])} % de l'information "
                f"(F1 : {_fr(ine[0])} %" + (f", F2 : {_fr(ine[1])} %" if len(ine) > 1 else '') + f") ; {r['n_obs']} individus, {r['n_vars']} variables.")
        axes = (f"Critère de Kaiser : {r['n_kaiser']} axe(s) de valeur propre > 1 ; 80 % de l'information demandent {r['n_80']} axe(s)."
                f" Axes conseillés : {r['n_suggested']}.")
        top = r['var_table_df']
        col = top.filter(like='Contrib. F1').iloc[:, 0].sort_values(ascending=False)
        corr = top.filter(like='Corr. F1').iloc[:, 0]
        names = [f"{_name(v)} ({_fr(corr[v], 2)})" for v in col.index[:3]]
        f1 = "L'axe F1 est surtout porté par : " + ', '.join(names) + " (corrélation avec l'axe)."
        adequacy = ''
        if r.get('kmo') is not None:
            adequacy = f"Adéquation des données : KMO = {_fr(r['kmo'], 2)} ({r['kmo_label']})" + \
                       ("" if r['kmo'] >= 0.6 else " — les variables sont peu corrélées : l'ACP résume mal") + \
                       (f" ; test de Bartlett p {'< 0,001' if r['bartlett_p'] < 0.001 else '= ' + _fr(r['bartlett_p'], 3)}." if r.get('bartlett_p') is not None else '.')
        dropped = f"Variables constantes écartées : {', '.join(_name(v) for v in r['dropped_constant'])}." if r.get('dropped_constant') else ''
        return _lines(lead, axes, f1, adequacy, dropped)
    if method == 'ACM':
        bz, raw = r['inertia'], r['inertia_raw']
        lead = (f"{r['n_obs']} individus, {r['n_vars']} variables, {r['n_modalities']} modalités. F1 porte {_fr(bz[0])} % de l'inertie "
                f"corrigée (Benzécri) — {_fr(raw[0])} % en inertie brute, qui sous-estime toujours l'information — et F2 {_fr(bz[1])} %.")
        cats = r['cats_df']
        c1 = cats.sort_values('Contrib. F1 (%)', ascending=False).head(4)
        f1 = "Modalités qui définissent F1 : " + ', '.join(f"« {_name(row['Variable'], 24)} = {row['Modalité']} » ({_fr(row['F1'], 2)})" for _, row in c1.iterrows()) + '.'
        axes = f"{r['n_useful_axes']} axe(s) dépassent l'inertie moyenne (1/{r['n_vars']}) : ce sont les seuls à interpréter."
        rare = (f"Modalités rares (< 2 %) qui tirent les axes : {', '.join(r['rare_modalities'][:4])} — envisager de les regrouper."
                if r.get('rare_modalities') else '')
        return _lines(lead, f1, axes, rare)
    if method == 'AFC':
        ine = r['inertia']
        verdict = (f"Association établie entre « {_name(r['row_var'])} » et « {_name(r['col_var'])} » (χ² = {_fr(r['chi2'], 1)}, "
                   f"p {'< 0,001' if r['p_value'] < 0.001 else '= ' + _fr(r['p_value'], 3)}, V = {_fr(r['cramers_v'], 2)})."
                   if r['p_value'] < 0.05 else
                   f"Aucune association établie entre ces variables (p = {_fr(r['p_value'], 3)}) : le plan factoriel ne reflète alors que du hasard.")
        lead = f"F1 explique {_fr(ine[0])} % de l'inertie" + (f" et F2 {_fr(ine[1])} %" if len(ine) > 1 else '') + f" ; n = {r['n_obs']}."
        reading = "Deux modalités proches sur le plan ont des profils proches ; une modalité éloignée du centre s'écarte de la répartition moyenne."
        warn = (f"{_fr(r['low_expected_pct'], 0)} % des cases ont un effectif théorique < 5 : lecture prudente." if r.get('low_expected_pct', 0) > 20 else '')
        return _lines(verdict, lead, reading, warn)
    if 'lassification' in method:
        sil = r['silhouette']
        quality = ('structure forte' if sil >= 0.5 else 'structure raisonnable' if sil >= 0.25 else 'structure faible : les classes se recouvrent')
        lead = (f"{r['n_clusters']} classes sur {r['n_obs']} individus ({r['space']}) ; silhouette = {_fr(sil, 2)} ({quality}). "
                + (f"Nombre de classes choisi automatiquement (silhouette maximale)." if r.get('auto_k') else
                   f"La silhouette suggère {r['suggested_k']} classe(s)." if r['suggested_k'] != r['n_clusters'] else
                   "C'est aussi le nombre de classes que suggère la silhouette."))
        items = [lead]
        for c in r['classes']:
            if c['traits']:
                desc = '; '.join(f"{t['label']}" + (f" ({_fr(t['part_classe'], 0)} % contre {_fr(t['part_totale'], 0)} %)" if 'part_classe' in t else
                                                     f" ({'+' if t['v'] > 0 else '−'})") for t in c['traits'][:3])
                items.append(f"{c['name']} ({_fr(c['pct'])} %) : {desc}.")
            else:
                items.append(f"{c['name']} ({_fr(c['pct'])} %) : proche de la moyenne, sans trait marquant.")
        small = [c['name'] for c in r['classes'] if c['pct'] < 5]
        if small:
            items.append(f"Classe(s) très petite(s) : {', '.join(small)} — à vérifier (individus atypiques ?).")
        return _lines(*items)
    return ''
