"""
SPAD Analyzer — Lecture et interprétation de la comparaison multi-enquête

Le texte « Lecture automatique » placé sous chaque comparaison dit, dans l'ordre :
  1. ce que l'on observe dans chaque enquête (modalité dominante, moyenne et médiane) ;
  2. si l'écart d'une enquête à l'autre est établi — test global, valeur de p, valeur q
     corrigée des tests multiples, intensité de l'écart (V de Cramér) ;
  3. les évolutions entre enquêtes consécutives dont l'intervalle de confiance à 95 %
     exclut 0, avec leur amplitude ;
  4. les précautions de lecture (effectifs faibles, tableau creux, distribution asymétrique).

Il décrit et nuance ; il ne conclut jamais à une cause. La synthèse placée au-dessus
rappelle qu'un test signale un écart peu probablement dû au hasard, pas qu'il est important
ni qu'il traduit une évolution réelle si les enquêtes ne sont pas comparables.
"""

SMALL_N = 30                 # en dessous, la lecture est prudente
MANY_MODALITIES = 12
SKEW_RATIO = 0.25            # |moyenne − médiane| / écart-type au-delà duquel la médiane est préférable


def _fr(x, nd=1):
    """Nombre à la française (virgule décimale)."""
    if x is None:
        return '—'
    return f'{x:.{nd}f}'.replace('.', ',').replace('-', '−')


def _signed(x, nd=1):
    return ('+' if x > 0 else '−' if x < 0 else '') + _fr(abs(x), nd)


def _p(p):
    return 'p < 0,0001' if p < 0.0001 else f'p = {_fr(p, 4)}'


def _q(q):
    return None if q is None else ('q < 0,0001' if q < 0.0001 else f'q = {_fr(q, 4)}')


def _name(n, limit=44):
    n = str(n)
    return n if len(n) <= limit else n[:limit - 1] + '…'


def _effect_label(v):
    return 'très faible' if v < 0.1 else 'faible' if v < 0.3 else 'modérée' if v < 0.5 else 'forte'


def _significance(test, corrected):
    """('établi' | 'avant correction' | 'non', p, q) selon le test et la correction."""
    p, q = test['p_value'], test.get('q_value') if corrected else None
    if q is not None:
        return ('établi' if q < 0.05 else 'avant correction' if p < 0.05 else 'non'), p, q
    return ('établi' if p < 0.05 else 'non'), p, None


def _test_clause(test, corrected):
    status, p, q = _significance(test, corrected)
    return ', '.join(x for x in (_p(p), _q(q)) if x), status


YES = ('oui', 'yes', 'vrai', 'true', '1')


def _mirror_free(rows):
    """Pour une variable à deux modalités (oui/non), les deux lignes d'une transition sont le
    miroir l'une de l'autre : on ne garde que « oui » (ou, à défaut, la hausse)."""
    pairs = {}
    for e in rows:
        pairs.setdefault((e['de'], e['vers']), []).append(e)
    keep = []
    for group in pairs.values():
        if len(group) == 2 and all(e.get('unite') == 'points de %' for e in group):
            group = [max(group, key=lambda e: (str(e['modalite']).strip().lower() in YES, e['diff']))]
        keep += group
    return keep


def _evolution_lines(rows, what):
    """Évolutions entre enquêtes consécutives dont l'IC à 95 % exclut 0 (les trois plus fortes)."""
    if not rows:
        return []
    ordered = _mirror_free(rows)
    strongest = sorted((e for e in ordered if e.get('significatif')), key=lambda e: -abs(e['diff']))[:3]
    sig = [e for e in ordered if any(e is k for k in strongest)]       # les plus nettes, relues dans l'ordre du temps
    n_more = sum(1 for e in ordered if e.get('significatif')) - len(sig)
    if not any(e.get('significatif') for e in rows):
        return ["• Évolution : aucun écart entre enquêtes consécutives n'est établi au seuil de 95 % "
                "(les intervalles de confiance contiennent 0)."]
    out = []
    for e in sig:
        pct = e.get('unite') == 'points de %'
        if pct:
            out.append(f"• Évolution : de « {_name(e['de'])} » à « {_name(e['vers'])} », « {e['modalite']} » passe de "
                       f"{_fr(e['v1'])} % à {_fr(e['v2'])} % ({_signed(e['diff'])} points ; IC à 95 % [{_fr(e['ic_bas'])} ; {_fr(e['ic_haut'])}]).")
        else:
            out.append(f"• Évolution : de « {_name(e['de'])} » à « {_name(e['vers'])} », {what} passe de "
                       f"{_fr(e['v1'], 2)} à {_fr(e['v2'], 2)} ({_signed(e['diff'], 2)} ; IC à 95 % [{_fr(e['ic_bas'], 2)} ; {_fr(e['ic_haut'], 2)}]).")
    if n_more:
        out.append(f"  … et {n_more} autre(s) écart(s) établi(s), visibles dans le tableau d'évolution.")
    return out


def interpret_categorical(r, corrected=True):
    st = r.get('stats') or {}
    surveys = st.get('surveys') or []
    test = r.get('test')
    lines = []
    verdict = _significance(test, corrected)[0] if test else None
    if surveys:
        tops = {s['top'] for s in surveys}
        if len(tops) == 1:
            detail = ' ; '.join(f"{_name(s['name'])} {_fr(s['top_pct'])} %" for s in surveys)
            lines.append(f"• Répartition : « {next(iter(tops))} » est la modalité la plus fréquente dans toutes les enquêtes ({detail}).")
        else:
            detail = ' ; '.join(f"« {_name(s['name'])} » (n = {s['n']}) : « {s['top']} » ({_fr(s['top_pct'])} %)" for s in surveys)
            if verdict == 'établi':
                lines.append("• Répartition : la modalité dominante change d'une enquête à l'autre — " + detail + '.')
            else:
                lines.append(f"• Répartition : modalité la plus fréquente, enquête par enquête — {detail}"
                             + ("; les écarts entre enquêtes restent dans la marge du hasard." if verdict == 'non' else '.'))
        if st.get('n_modalites', 0) > MANY_MODALITIES:
            lines.append(f"• La variable compte {st['n_modalites']} modalités : la lecture porte sur la plus fréquente, "
                         "le détail figure dans les tableaux.")
    if test:
        clause, status = _test_clause(test, corrected)
        if status == 'établi':
            v = test.get('cramers_v')
            lines.append(f"• Comparaison globale : les répartitions diffèrent d'une enquête à l'autre (χ², {clause})"
                         + (f". Intensité de l'écart : {_effect_label(v)} (V de Cramér = {_fr(v, 2)})." if v is not None else '.'))
        elif status == 'avant correction':
            lines.append(f"• Comparaison globale : l'écart est significatif avant correction mais plus après (χ², {clause}) : "
                         "à confirmer, il peut tenir au grand nombre d'indicateurs testés.")
        else:
            lines.append(f"• Comparaison globale : aucune différence de répartition n'est établie entre les enquêtes (χ², {clause}).")
    else:
        lines.append("• Comparaison globale : non réalisée (elle demande au moins deux enquêtes et deux modalités observées).")
    lines += _evolution_lines(r.get('evolution'), '')
    small = [s for s in surveys if s['n'] < SMALL_N]
    if small:
        lines.append("• Précaution : effectifs faibles dans " + ', '.join(f"« {_name(s['name'])} » (n = {s['n']})" for s in small)
                     + " — lecture prudente ; l'absence d'écart détecté ne prouve pas l'équivalence.")
    if test and (test.get('low_expected_pct') or 0) > 20:
        lines.append(f"• Précaution : {_fr(test['low_expected_pct'], 0)} % des cases ont un effectif théorique inférieur à 5 — "
                     "le χ² est peu fiable ici ; s'appuyer sur la lecture descriptive.")
    return '\n'.join(lines)


def interpret_continuous(r, corrected=True):
    st = (r.get('stats') or {}).get('surveys') or []
    test = r.get('test')
    lines = []
    if st:
        lines.append('• Valeurs : ' + ' ; '.join(
            f"« {_name(s['name'])} » moyenne {_fr(s['mean'], 2)}, médiane {_fr(s['median'], 2)} (n = {s['n']})" for s in st) + '.')
        means = [s['mean'] for s in st]
        if len(means) >= 3 and all(a < b for a, b in zip(means, means[1:])):
            lines.append("• La moyenne augmente d'une enquête à l'autre.")
        elif len(means) >= 3 and all(a > b for a, b in zip(means, means[1:])):
            lines.append("• La moyenne diminue d'une enquête à l'autre.")
    if test:
        clause, status = _test_clause(test, corrected)
        sujet = 'les distributions' if 'Kruskal' in test.get('test', '') else 'les moyennes'
        label = test.get('test', 'test')
        if status == 'établi':
            lines.append(f"• Comparaison globale : {sujet} diffèrent d'une enquête à l'autre ({label}, {clause}).")
        elif status == 'avant correction':
            lines.append(f"• Comparaison globale : l'écart est significatif avant correction mais plus après ({label}, {clause}) : "
                         "à confirmer, il peut tenir au grand nombre d'indicateurs testés.")
        else:
            lines.append(f"• Comparaison globale : aucune différence entre enquêtes n'est établie ({label}, {clause}).")
    else:
        lines.append("• Comparaison globale : non réalisée (elle demande au moins deux enquêtes avec trois valeurs chacune).")
    lines += _evolution_lines(r.get('evolution'), 'la moyenne')
    small = [s for s in st if s['n'] < SMALL_N]
    if small:
        lines.append("• Précaution : effectifs faibles dans " + ', '.join(f"« {_name(s['name'])} » (n = {s['n']})" for s in small)
                     + " — lecture prudente ; l'absence d'écart détecté ne prouve pas l'équivalence.")
    skewed = [s for s in st if s.get('std') and abs(s['mean'] - s['median']) > SKEW_RATIO * s['std']]
    if skewed:
        lines.append("• Précaution : distribution asymétrique dans " + ', '.join(f"« {_name(s['name'])} »" for s in skewed)
                     + " (moyenne et médiane s'écartent) — privilégier la médiane.")
    return '\n'.join(lines)


def interpret(r, corrected=True):
    """Lecture d'une comparaison (dictionnaire produit par multi_survey) ; '' en cas d'erreur de calcul."""
    if r.get('error'):
        return ''
    return (interpret_continuous if r.get('kind') == 'continuous' else interpret_categorical)(r, corrected)


def synthese(results, order, corrected=True, n_errors=0):
    """Synthèse en tête des comparaisons : ce qui diffère, ce qui est à confirmer, ce qui est stable."""
    ok = [r for r in results if not r.get('error')]
    if not ok:
        return ''
    name = lambda r: r.get('variable') or r.get('radical') or ''
    show = lambda r: name(r) + (f" ({r['label']})" if r.get('label') else '')
    tested = [r for r in ok if r.get('test')]
    status = {id(r): _significance(r['test'], corrected)[0] for r in tested}
    established = [r for r in tested if status[id(r)] == 'établi']
    tentative = [r for r in tested if status[id(r)] == 'avant correction']
    stable = [r for r in tested if status[id(r)] == 'non']
    lines = [f"{len(ok)} indicateur(s) comparé(s) entre {len(order)} enquêtes, de la plus ancienne à la plus récente : "
             + ' → '.join(_name(o) for o in order) + '.']
    if established:
        strongest = sorted(established, key=lambda r: -(r['test'].get('cramers_v') or 0))
        lines.append(f"Écarts établis{' après correction des tests multiples' if corrected else ''} ({len(established)}) : "
                     + ', '.join(show(r) for r in strongest[:8]) + (' …' if len(strongest) > 8 else '') + '.')
    else:
        lines.append("Aucun écart n'est établi entre les enquêtes"
                     + (' après correction des tests multiples.' if corrected else '.'))
    if tentative:
        lines.append("À confirmer (significatifs avant correction seulement) : " + ', '.join(show(r) for r in tentative[:8]) + '.')
    if stable:
        lines.append(f"Sans écart détectable ({len(stable)}) : " + ', '.join(name(r) for r in stable[:8]) + (' …' if len(stable) > 8 else '') + '.')
    if n_errors:
        lines.append(f"⚠ {n_errors} contrôle(s) de cohérence en erreur (section 2) : les lever avant d'interpréter ces écarts, "
                     "qui peuvent venir des données elles-mêmes (unités, codages, doublons).")
    lines.append("Pour mémoire : un test signale qu'un écart est peu probablement dû au hasard, pas qu'il est important ni qu'il a "
                 "une cause précise ; il ne traduit une évolution réelle que si les enquêtes portent sur des populations et des "
                 "méthodes d'échantillonnage comparables.")
    return '\n'.join(lines)
