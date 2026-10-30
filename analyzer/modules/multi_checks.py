"""
SPAD Analyzer — Contrôles de cohérence ENTRE enquêtes

Avant de comparer plusieurs enquêtes, on vérifie qu'elles se comparent :

  - unités / types : la même question (Age) posée en années dans une enquête
    (Age__1Y) et en mois dans une autre (Age__1M), ou en oui/non (__B) d'un
    côté et oui/non/ne sait pas (__C) de l'autre ;
  - codage des modalités : « Masculin / Féminin » d'un côté, « M / F » ou
    « 1 / 2 » de l'autre — sinon le tableau comparatif ne montre que du vide ;
  - répondants communs : le même fichier ajouté deux fois, ou une même
    soumission présente dans deux enquêtes (identifiant _uuid identique) ;
  - Factum : une enquête sans Factum ne peut être ni ordonnée dans le temps
    ni versée à la base centrale.

Les contrôles de qualité PROPRES à chaque enquête (doublons, heures, seuils,
valeurs extrêmes, règles saisies par l'équipe) viennent de validation_rules.py.
"""
import re
import unicodedata

import pandas as pd

from modules import phakts_codes as pc
from modules.validation_rules import ERREUR, A_VERIFIER, INFO

CATEGORIE = 'Cohérence entre enquêtes'
MAX_MODALITES = 60            # au-delà, la variable est du texte libre, pas une liste
ID_COLUMNS = ('_uuid', 'meta/instanceID', 'instanceID', '_id')
TECHNICAL = re.compile(r'^(_|meta/|formhub/)|^__version__$|^Factum', re.I)
MIN_ROWS_IDENTICAL = 10
IDENTICAL_RATIO = 0.9


def _norm(value):
    """Valeur comparable : sans accent, casse, ponctuation ni espaces multiples."""
    s = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[\s_\-\.]+', ' ', s).strip()


def _check(severite, titre, detail, enquetes):
    return {'severite': severite, 'categorie': CATEGORIE, 'titre': titre, 'detail': detail,
            'enquetes': sorted(enquetes)}


def _join(names, limit=4):
    names = list(names)
    return ', '.join(names[:limit]) + (f' (+{len(names) - limit})' if len(names) > limit else '')


# ─── Unités et types ─────────────────────────────────────────────────────────

def unit_and_type_checks(surveys):
    """Même question (même code sans affixe) sous des affixes différents."""
    by_stem = {}
    for name, df in surveys.items():
        for col in df.columns:
            affix = pc.affix_of(col)
            if affix:
                by_stem.setdefault(pc.stem_of(col), {}).setdefault(affix, set()).add(name)
    out = []
    for stem, per_affix in sorted(by_stem.items()):
        if len(per_affix) < 2:
            continue
        involved = set().union(*per_affix.values())
        if len(involved) < 2:
            continue       # plusieurs affixes dans UNE seule enquête : rien à comparer
        parts = [f"{stem}__{a} ({pc.describe_affix(a)}) dans {_join(sorted(names))}"
                 for a, names in sorted(per_affix.items())]
        numeric = [a for a in per_affix if re.match(r'^[12][A-Z]?$', a)]
        if len(numeric) == len(per_affix):
            units = {pc.numeric_unit(f'{stem}__{a}') for a in numeric}
            if len(units) > 1:
                out.append(_check(ERREUR, f'Unités différentes — {stem}',
                                  ' ; '.join(parts) + ". Ces variables ne sont pas alignées : elles sont comparées "
                                  'séparément, jamais ensemble. Convertir l\'une des deux avant de les comparer.',
                                  involved))
                continue
        out.append(_check(A_VERIFIER, f'Types différents — {stem}',
                          ' ; '.join(parts) + '. Variables non alignées : vérifier qu\'il s\'agit bien de la même question.',
                          involved))
    return out


# ─── Codage des modalités ────────────────────────────────────────────────────

def category_checks(surveys):
    """Listes de modalités qui ne se recoupent pas d'une enquête à l'autre."""
    values = {}     # clé -> {enquête: {valeur normalisée: libellé d'origine}}
    for name, df in surveys.items():
        for col in df.columns:
            key = pc.alignment_key(col, keep_path=True)
            if pc.affix_of(col) not in ('X', 'B', 'C') or '/' in key.split('__')[-1]:
                continue                          # numérique, texte, ou case d'un choix multiple (0/1)
            distinct = df[col].dropna().astype(str).str.strip().unique()
            if not 0 < len(distinct) <= MAX_MODALITES:
                continue
            values.setdefault(key, {})[name] = {_norm(v): str(v) for v in distinct}
    out = []
    for key, per_survey in sorted(values.items()):
        if len(per_survey) < 2:
            continue
        names = sorted(per_survey)
        exclusive = {n: sorted(set(per_survey[n]) - set().union(*(set(per_survey[m]) for m in names if m != n)))
                     for n in names}
        sides = [n for n in names if exclusive[n]]
        # enquête dont les modalités ne recoupent celles d'AUCUNE autre : sa colonne restera vide face aux autres
        isolated = [n for n in names if all(not (set(per_survey[n]) & set(per_survey[m])) for m in names if m != n)]
        if isolated:
            others = [n for n in names if n not in isolated]
            sample = ' ; '.join(f"{n} : {_join(per_survey[n].values(), 5)}" for n in isolated)
            versus = (f" Les autres enquêtes utilisent : {_join(sorted({v for n in others for v in per_survey[n].values()}), 5)}."
                      if others else '')
            out.append(_check(ERREUR, f'Modalités sans aucune valeur commune — {key}',
                              f'{sample} : aucune réponse en commun avec les autres enquêtes.{versus} '
                              'Le tableau comparatif sera vide pour elles : harmoniser le codage des réponses.', isolated))
        elif len(sides) >= 2:
            sample = ' ; '.join(f"{n} seulement : {_join([per_survey[n][v] for v in exclusive[n]], 4)}" for n in sides)
            out.append(_check(A_VERIFIER, f'Modalités différentes — {key}',
                              f'{sample}. Même réponse écrite différemment (« Masculin » / « M ») ? Sinon, listes réellement différentes.',
                              sides))
    return out


# ─── Répondants communs ──────────────────────────────────────────────────────

def respondent_checks(surveys):
    out = []
    names = list(surveys)
    ids = {}
    for name, df in surveys.items():
        col = next((c for c in ID_COLUMNS if c in df.columns), None)
        if col is not None:
            ids[name] = set(df[col].dropna().astype(str).str.strip())
    flagged = set()
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            both = ids.get(a, set()) & ids.get(b, set())
            if both:
                flagged.add((a, b))
                out.append(_check(ERREUR, 'Mêmes soumissions dans deux enquêtes',
                                  f'{len(both)} identifiant(s) de soumission (_uuid) identiques dans « {a} » et « {b} » : '
                                  'le même fichier a-t-il été ajouté deux fois ? Ces lignes seraient comptées deux fois.',
                                  [a, b]))
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if (a, b) in flagged:
                continue
            da, db = surveys[a], surveys[b]
            common = [c for c in da.columns if c in db.columns and not TECHNICAL.match(str(c))][:25]
            if len(common) < 3 or min(len(da), len(db)) < MIN_ROWS_IDENTICAL:
                continue
            ha = set(pd.util.hash_pandas_object(da[common].astype(str), index=False))
            hb = set(pd.util.hash_pandas_object(db[common].astype(str), index=False))
            shared = len(ha & hb)
            if shared >= IDENTICAL_RATIO * min(len(ha), len(hb)):
                out.append(_check(ERREUR, 'Données identiques dans deux enquêtes',
                                  f'{shared} ligne(s) identiques sur {len(common)} colonnes communes entre « {a} » et « {b} » '
                                  f'(≥ {int(IDENTICAL_RATIO * 100)} % de la plus petite) : même enquête chargée deux fois ?',
                                  [a, b]))
    return out


# ─── Factum ──────────────────────────────────────────────────────────────────

def factum_checks(surveys, factums):
    """factums : {nom d'enquête: Factum valide ou ''}."""
    missing = [n for n in surveys if not factums.get(n)]
    out = []
    if missing:
        out.append(_check(A_VERIFIER, 'Enquête sans Factum',
                          f'{_join(missing)} : sans Factum, l\'enquête ne peut être ni placée dans le temps (les écarts '
                          'entre enquêtes suivent l\'ordre d\'import) ni versée à la base centrale. Le renseigner dans la pile ci-dessus.',
                          missing))
    seen = {}
    for n in surveys:
        if factums.get(n):
            seen.setdefault(factums[n], []).append(n)
    for fac, names in seen.items():
        if len(names) > 1:
            out.append(_check(ERREUR, 'Même Factum pour plusieurs enquêtes',
                              f'{_join(names)} portent le même Factum ({fac}) : une étude, une collecte. '
                              'Corriger le n° de collecte (nCm) ou retirer le doublon.', names))
    return out


_ORDER = {ERREUR: 0, A_VERIFIER: 1, INFO: 2}


def check_surveys(surveys, factums=None):
    """Tous les contrôles entre enquêtes, du plus grave au moins grave."""
    if len(surveys) < 2:
        return factum_checks(surveys, factums or {}) if surveys else []
    checks = (unit_and_type_checks(surveys) + category_checks(surveys)
              + respondent_checks(surveys) + factum_checks(surveys, factums or {}))
    checks.sort(key=lambda c: (_ORDER[c['severite']], c['titre']))
    return checks
