"""
SPAD Analyzer — Générateur générique de dictionnaire d'indicateurs

Lit la feuille "survey" (+ "choices" si présente) de N'IMPORTE QUEL XLSForm
KoboToolbox/ODK et produit un dictionnaire de variables avec, pour chacune :
  - nom, section, label, type XLSForm, liste de choix
  - suffixe PHAKTS détecté (xType/period), si le formulaire est codifié
    PHAKTS (voir data/reference/... ou la doc PHAKTS_Dictionnaire) — sinon
    vide
  - traitement statistique recommandé : grille fine par xType si détecté,
    sinon grille générique par type XLSForm brut (fonctionne sur n'importe
    quel XLSForm standard, codifié PHAKTS ou non)
  - rôle suggéré (indicateur / stratification suggérée / exclu) — une
    suggestion de départ, à valider/ajuster par l'utilisateur : aucune
    détection sémantique automatique du contenu des questions n'est
    tentée ici (voir modules/enquete_analyse.py pour les scores composites,
    où le regroupement par domaine est entièrement piloté par l'utilisateur
    via l'interface, pas deviné).
  - points de qualité détectés (suffixe PHAKTS incohérent avec le nombre
    réel de modalités de la liste choices utilisée)

Ce module ne connaît rien à SPAD ni à un formulaire particulier — il ne
fait que lire la structure du XLSForm fourni.
"""
import re
import pandas as pd

# ─── Grammaire PHAKTS (dictionnaire des règles v2025.10.22-ext2) ───────────
# xType : A=Date, B=Booléen, C=Triléen, K=Masse, L=Longueur, T=Température,
# G=Géolocalisation, P=Proportion, V=Volume, F=Monnaie, I=Indice/score
# composite, E=Identifiant externe. Extensions observées dans les XLSForms
# SPAD réels : X=Choix (select_one/select_multiple), Z=Texte libre/champ
# technique — non présentes dans la table xType officielle mais utilisées
# de façon cohérente dans les formulaires audités.
GRILLE_XTYPE = {
    'B': "Proportion (%) + IC95% (Wilson) — bivarié : χ² ou Fisher exact (effectifs <5) "
         "— multivarié : régression logistique",
    'C': "Proportions par modalité + IC95% — bivarié : χ² ou Fisher exact "
         "— multivarié : régression logistique (après regroupement binaire si besoin)",
    'X_one': "Fréquences par modalité (%) + IC95% — bivarié : χ² ou Fisher exact "
             "— multivarié : régression logistique (modalité de référence) ou multinomiale",
    'X_multi': "Proportion « oui » par item (%) + IC95% — bivarié : test par item (χ²/Fisher) "
               "— envisager un score composite (numérateur/dénominateur) "
               "— multivarié : régression logistique par item ou sur le score composite",
    'period': "Moyenne ± écart-type OU médiane [IQR] selon normalité (Shapiro-Wilk) "
              "— bivarié : t-test/Mann-Whitney (2 groupes), ANOVA/Kruskal-Wallis (>2 groupes) "
              "— multivarié : régression linéaire (ou log-linéaire si distribution asymétrique)",
    'A': "Non analysé directement comme continu — dérive un délai/une durée si pertinent, "
         "sinon utilisé pour stratification temporelle uniquement",
    'Z': "Exclu de l'analyse quantitative (texte libre, identifiant technique ou verbatim)",
    'E': "Exclu de l'analyse quantitative (identifiant) — sauf usage en stratification qualité",
    'I': "Moyenne ± écart-type ou médiane [IQR] (comme continu) — bivarié : t-test/Mann-Whitney "
         "ou ANOVA/Kruskal-Wallis — multivarié : régression linéaire",
}

# ─── Grille générique de repli — XLSForm sans codification PHAKTS ──────────
GRILLE_TYPE_BRUT = {
    'select_one': "Fréquences par modalité (%) + IC95% (Wilson) — bivarié : χ²/Fisher "
                  "— multivarié : régression logistique",
    'select_multiple': "Proportion « oui » par item (%) + IC95% — envisager un score composite "
                        "— multivarié : régression logistique par item",
    'integer': "Moyenne ± écart-type OU médiane [IQR] selon normalité — t-test/Mann-Whitney/"
               "ANOVA/Kruskal-Wallis — régression linéaire",
    'decimal': "Moyenne ± écart-type OU médiane [IQR] selon normalité — t-test/Mann-Whitney/"
               "ANOVA/Kruskal-Wallis — régression linéaire",
    'range': "Moyenne ± écart-type OU médiane [IQR] selon normalité — t-test/Mann-Whitney/"
             "ANOVA/Kruskal-Wallis — régression linéaire",
    'date': "Non analysé directement comme continu — dérive un délai/une durée si pertinent",
    'dateTime': "Non analysé directement comme continu — dérive un délai/une durée si pertinent",
    'time': "Non analysé directement comme continu — dérive un délai/une durée si pertinent",
    'text': "Exclu de l'analyse quantitative (texte libre) — analyse qualitative séparée possible",
    'calculate': "À valider manuellement (champ calculé — dépend de la formule)",
    'geopoint': "Exclu de l'analyse statistique (cartographie uniquement)",
    'geotrace': "Exclu de l'analyse statistique (cartographie uniquement)",
    'geoshape': "Exclu de l'analyse statistique (cartographie uniquement)",
}
_TYPES_TECHNIQUES = {
    'image', 'audio', 'video', 'file', 'barcode', 'acknowledge', 'hidden',
    'start', 'end', 'today', 'deviceid', 'username', 'phonenumber', 'audit',
    'note', 'begin_group', 'end_group', 'begin_repeat', 'end_repeat',
}

_SUFFIX_RE = re.compile(r'__(\d[A-Za-z]{0,2}|[A-Za-z]{1,2})\Z')
_CARDINALITE_ATTENDUE = {'B': 2, 'C': 3}


def _extract_suffix(name):
    m = _SUFFIX_RE.search(name)
    return m.group(1) if m else None


def _xtype_key(suffix, is_multi):
    if not suffix:
        return None
    if suffix[0] in ('1', '2'):
        return 'period'
    if suffix == 'X':
        return 'X_multi' if is_multi else 'X_one'
    if suffix in GRILLE_XTYPE:
        return suffix
    return None


def _traitement(raw_type, suffix, is_multi):
    xkey = _xtype_key(suffix, is_multi)
    if xkey:
        return GRILLE_XTYPE[xkey], True
    type_simple = raw_type.split(' ')[0]
    if type_simple in GRILLE_TYPE_BRUT:
        return GRILLE_TYPE_BRUT[type_simple], False
    if type_simple in _TYPES_TECHNIQUES:
        return "Exclu de l'analyse quantitative (champ technique)", False
    return "À déterminer manuellement (type non reconnu)", False


ROLES = ('indicateur', 'stratification', 'exclu')


def _suggested_role(name, list_name, raw_type):
    """Suggestion de départ (une des 3 valeurs canoniques de ROLES),
    éditable — pas de détection sémantique du contenu des questions. Repère
    seulement la convention SPAD/PHAKTS des listes de référence
    administrative (Admin_*) pour suggérer la stratification géographique,
    sans jamais l'imposer."""
    if list_name and (list_name.lower().startswith('admin_')
                       or 'region' in list_name.lower() or 'district' in list_name.lower()):
        return 'stratification'
    if raw_type.split(' ')[0] in _TYPES_TECHNIQUES:
        return 'exclu'
    return 'indicateur'


def parse_xlsform(path):
    """Lit un XLSForm (feuilles survey + choices) et renvoie un DataFrame —
    un dictionnaire de variables prêt à être révisé/édité par l'utilisateur
    avant toute analyse (voir modules/enquete_analyse.py)."""
    survey = pd.read_excel(path, sheet_name='survey')
    survey.columns = [str(c).strip() for c in survey.columns]

    label_col = next((c for c in survey.columns if c.lower().startswith('label')), None)
    relevant_col = next((c for c in survey.columns if c.lower().startswith('relevant')), None)

    try:
        choices = pd.read_excel(path, sheet_name='choices')
        choices.columns = [str(c).strip() for c in choices.columns]
        list_col = next((c for c in choices.columns if c.lower() == 'list_name'), choices.columns[0])
        n_modalites = choices[list_col].value_counts().to_dict()
    except Exception:
        n_modalites = {}

    rows = []
    group_stack = []

    for _, r in survey.iterrows():
        raw_type = str(r.get('type', '')).strip()
        name = r.get('name')
        label = r.get(label_col) if label_col else None
        relevant = r.get(relevant_col) if relevant_col else None

        if raw_type == 'begin_group' or raw_type.startswith('begin_group'):
            group_stack.append((str(name), str(label) if pd.notna(label) else str(name)))
            continue
        if raw_type == 'end_group' or raw_type.startswith('end_group'):
            if group_stack:
                group_stack.pop()
            continue
        if raw_type in ('note', 'begin_repeat', 'end_repeat') or pd.isna(name):
            continue

        section_label = group_stack[-1][1] if group_stack else '(hors section)'
        name = str(name)
        is_multi = raw_type.startswith('select_multiple')
        type_simple = raw_type.split(' ')[0]
        list_name = raw_type.split(' ', 1)[1] if ' ' in raw_type else ''

        suffix = _extract_suffix(name)
        traitement, is_phakts = _traitement(raw_type, suffix, is_multi)
        role = _suggested_role(name, list_name, raw_type)

        note_qualite = ''
        if is_phakts and type_simple == 'select_one' and suffix in _CARDINALITE_ATTENDUE and list_name in n_modalites:
            attendu = _CARDINALITE_ATTENDUE[suffix]
            reel = n_modalites[list_name]
            if reel != attendu:
                note_qualite = (f"Suffixe __{suffix} attend {attendu} modalité(s), "
                                 f"liste « {list_name} » en a {reel} — à corriger ou reclasser.")

        rows.append({
            'nom': name,
            'section': section_label,
            'label': label if pd.notna(label) else '',
            'type_xlsform': raw_type,
            'liste_choices': list_name,
            'suffixe_phakts': suffix or '',
            'role': role,
            'domaine': '',
            'inclure_score_composite': False,
            'sens_item': '',
            'valeurs_favorables': '',
            'traitement_statistique_recommande': traitement,
            'relevant_skip_logic': relevant if pd.notna(relevant) else '',
            'note_qualite': note_qualite,
        })

    return pd.DataFrame(rows)


def modalites_liste(path, list_name):
    """Renvoie les valeurs (name) possibles d'une liste choices — utilisé
    par l'UI pour aider l'utilisateur à choisir les valeurs favorables."""
    try:
        choices = pd.read_excel(path, sheet_name='choices')
        choices.columns = [str(c).strip() for c in choices.columns]
        list_col = next((c for c in choices.columns if c.lower() == 'list_name'), choices.columns[0])
        name_col = next((c for c in choices.columns if c.lower() == 'name'), choices.columns[1])
        return choices[choices[list_col] == list_name][name_col].astype(str).tolist()
    except Exception:
        return []
