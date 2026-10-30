"""
SPAD Analyzer — Lecture d'un code PHAKTS : clé d'alignement, affixe, unité

Un code PHAKTS s'écrit Radical__Déterminant__Affixe!directive (grammaire
v2025.10.22-ext2). L'affixe est le DERNIER segment « __ » ; il porte le type
(B booléen, C triléen, X choix, A date, Z texte, G généré par Kobo, P image,
1Y / 2K… entier ou réel avec son unité). Même règle que classifyCode() dans
public/phakts-core.js : les deux doivent rester alignées.

La clé d'alignement sert à reconnaître la même variable d'une enquête à
l'autre (base centrale, analyse multi-enquête). C'est le code SANS sa
directive et SANS le chemin de groupe Kobo :

    groupe/Age__1Y!0<N<120   →  Age__1Y
    Sport__X/Football        →  Sport__X/Football   (case d'un choix multiple)
    Allaitement__B           ≠  Allaitement__Duree__1W
    Age__1Y (années)         ≠  Age__1M (mois)

Couper au premier « __ » (ancien comportement) confondait ces variables.
"""
import re

# Unités reconnues derrière un affixe numérique (1Y = entier en années…).
UNITES = {
    'Y': 'années', 'M': 'mois', 'W': 'semaines', 'D': 'jours', 'H': 'heures',
    'K': 'kg', 'L': 'cm', 'T': '°C', 'F': 'FCFA', 'V': 'litres', 'P': '%',
    'S': 'secondes', 'U': 'unités', 'Q': 'quantité',
}
UNITES_TEMPS = ('Y', 'M', 'W', 'D', 'H', 'S')

AFFIXES_TYPES = {'B': 'booléen', 'C': 'triléen', 'X': 'choix', 'SRC': 'choix (source)', 'A': 'date',
                 'Z': 'texte', 'E': 'texte', 'G': 'généré par Kobo', 'P': 'image'}
_NUMERIC_AFFIX = re.compile(r'^([12])([A-Z]?)$')


def split_code(column):
    """(code sans directive, directive) — la directive suit le premier « ! »."""
    code, _, directive = str(column).partition('!')
    return code, directive


def affix_of(column):
    """Dernier segment « __ » du code, hors chemin de groupe et directive ;
    '' si la colonne n'est pas codifiée."""
    code = split_code(column)[0].split('/')
    code = next((p for p in code if '__' in p), '')
    segments = code.split('__')
    if len(segments) < 2:
        return ''
    # Case d'un choix multiple (Sport__X/Football) : l'affixe est celui de la question.
    affix = segments[-1]
    return affix if (affix in AFFIXES_TYPES or _NUMERIC_AFFIX.match(affix)) else ''


def is_coded(column):
    return bool(affix_of(column))


def stem_of(column):
    """Le code sans son affixe : Age__1Y → Age ; Allaitement__Duree__1W →
    Allaitement__Duree. Deux variables au même radical et à des affixes
    différents posent la même question sous un autre type ou une autre unité."""
    code = split_code(column)[0]
    parts = code.split('/')
    for i, p in enumerate(parts):
        if '__' in p:
            head, _, last = p.rpartition('__')
            if last in AFFIXES_TYPES or _NUMERIC_AFFIX.match(last):
                parts[i] = head
            break
    return '/'.join(parts[i:]) if '__' in code else code


def alignment_key(column, keep_path=False):
    """Clé d'alignement (voir l'en-tête du module). Une colonne non codifiée
    garde son nom ; keep_path=False retire alors le chemin de groupe Kobo."""
    parts = str(column).split('/')
    first = next((i for i, p in enumerate(parts) if '__' in p), None)
    if first is None:
        return str(column).split('!', 1)[0] if keep_path else (parts[-1].strip() or str(column))
    parts = parts[first:]
    parts[0] = parts[0].split('!', 1)[0]
    return '/'.join(parts).strip()


def numeric_unit(column):
    """Unité d'une variable numérique (1Y → 'Y'), '' sinon."""
    m = _NUMERIC_AFFIX.match(affix_of(column))
    return m.group(2) if m else ''


def describe_affix(affix):
    """Libellé lisible d'un affixe : 1Y → « entier, années », X → « choix »."""
    if affix in AFFIXES_TYPES:
        return AFFIXES_TYPES[affix]
    m = _NUMERIC_AFFIX.match(affix or '')
    if m:
        nature = 'entier' if m.group(1) == '1' else 'réel'
        return f'{nature}, {UNITES[m.group(2)]}' if m.group(2) in UNITES else nature
    return affix or 'non codifié'
