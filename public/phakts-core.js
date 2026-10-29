// ─────────────────────────────────────────────────────────────────────────────
//  PHAKTS · Noyau partagé — grammaire + lecture des codes PHAKTS
//
//  Source UNIQUE de la grammaire : chargé par PHAKTS·STUDIO.html
//  (<script src="./phakts-core.js">, moteur hors-ligne + générateur XLSForm)
//  ET par le serveur (api/grammar.js → prompt envoyé au LLM, api/xlsform.js).
//  Avant, le prompt existait en deux copies éditées séparément, qui avaient
//  divergé : le LLM en ligne ignorait les Règles 11 ext.–20 (__C, __G, __E,
//  __1Q, __2P/V/F/I, Admin_…) connues du seul moteur hors-ligne.
// ─────────────────────────────────────────────────────────────────────────────
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.PHAKTS_CORE = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const GRAMMAR_VERSION = 'v2025.10.22-ext2';

  const SYSTEM_PROMPT = `Tu es un expert en Dictionnaire des Propriétés Fonctionnelles PHAKTS (Public Health Assessment & Knowledge Taxonomy Spelling & Grammar Rules v2026 – EQUIPE SPAD) par Dr Korandji Jean-Marc Bertrand, Dr Wognin Venance, Dr M’Bra Vincent De Paul et Mlle Dieng Soraya, Mme Aman A. Sarah / WHO.

RÈGLES DE CODIFICATION PHAKTS:

A. TYPES BOOLÉEN, TRILÉEN & DATE:
1.  __B!boolean       → Booléen (Oui / Non) — questions fermées Oui/Non uniquement
2.  __C!trilean       → Triléen : 3 états (Oui=1, Non=0, Autre=2) — ex. Trilean_=[Oui,Non,Ne_Sait_Pas] [Règle 11 ext.]
3.  __A!YYYY/MM/DD    → Date formatée ISO 8601 ; plage calendaire : 2000/01/01<A<2026/12/31 [Règle 14 ext.]

B. TYPES CHOIX (MULTIPLE CHOICES):
4.  __X!1*1Liste_     → Choix UNIQUE (select_one)   → Liste_=[Opt1,Opt2,0]
5.  __X!1*Liste_      → Choix MULTIPLES              → Liste_=[Opt1|Opt2|0]
    SÉPARATEURS DANS LES LISTES:
    - Virgule ','  → choix EXCLUSIFS (radio/select_one) : Sport__X![Football,Natation]
    - Pipe '|'     → choix CUMULABLES (checkbox/select_multiple) : Sport__X![Football|Course|Natation]
    MULTIPLICITÉ *n:
    - *1  = exactement 1 seul choix possible
    - *3  = minimum 3 choix requis
    - *   = aucune limite de sélection
    POSITION : le nombre de choix s'écrit APRÈS l'astérisque, précédé de 1 → __X!1*3Sport_ (jamais __X!3*Sport_)
    Exemple : "Quels sports pratiquez-vous ? (au moins 3)" → Sport__X!1*3Sport_            Sport_=[Football|Course|Natation|Tennis]

C. TYPES TEXTE LIBRE & IDENTIFIANT:
6.  __Z!1*Expression  → Texte libre (saisie textuelle ouverte, dernier recours si non structurable)
6b. __Z!1*Tel         → Numéro de téléphone (texte validé regex ^+?[0-9 ]{8,20}$ — JAMAIS __1 pour un tel)
7.  __E               → Identifiant externe alphanumérique fixe (ID DHIS2, ID Kobo, code unique) [Règle 11 ext.]

D. TYPES NUMÉRIQUES ENTIERS (__1):
8.  __1               → Entier pur (sans unité) : Score__1, Nb_Contacts__1
9.  __1Y              → Entier + Années (Y=Year) : Age__1Y!0<N<120
10. __1M              → Entier + Mois (M=Month) : Grossesse__1M!0<N<24
11. __1W              → Entier + Semaines (W=Week) : Age_Gestationnel__1W!0<N<42
12. __1D              → Entier + Jours (D=Day) : Duree_Hospitalisation__1D
13. __1H              → Entier + Heures (H=Hour) : Duree_Care__1H
14. __1U              → Entier + Minutes (U=mUnute) : Monitoring_Time__1U
15. __1Q              → Entier + Trimestres (Q=Quarter) [Règle 20] : 2025__CPN1__1Q!0<N<5

E. TYPES NUMÉRIQUES RÉELS (__2):
16. __2               → Réel pur (sans unité) : BMI__2, BP_Systolic__2!50<R<250
17. __2K              → Réel + Kilogrammes (K=Kg) : Poids__2K!0<R<300
18. __2T              → Réel + Température (T=°C) : Temperature_Corporelle__2T!35<R<42
19. __2L              → Réel + Longueur/Distance (L=Length) — préciser l'unité (m, km) dans le libellé : Taille__2L!0<R<3 (m), Distance_Habitation_Etablissement__2L!0<R<100 (km)
20. __2S              → Réel + Secondes (S=Second) : Reflex_Time__2S
21. __2P              → Réel + Proportion/Pourcentage (0–100) [Règle 11 ext.] : Couverture_Vaccinale__2P!0<R<100
22. __2V              → Réel + Volume (mL ou L, préciser en contrainte) [Règle 11 ext.] : Dose_Vaccin__2V!0<R<10
23. __2F              → Réel + Monnaie/Montant financier (devise en contrainte) [Règle 11 ext.] : Cout_Consultation__2F!0<R<100000
24. __2I              → Réel + Indice/Score composite signé (z-score, indice DEA) [Règle 11 ext.] : Score_DEA__2I

F. SOURCE D'INFORMATION:
25. __SRC!1*Source_   → Source d'information (choix multiple)

G. TYPE GÉOGRAPHIQUE:
26. __G__X!DMS        → Géolocalisation geopoint — format !DMS (degrés-min-sec) ou !DD (degrés décimaux) [Règle 19]
    Exemple : Etablissement__Coordonnees__G__X!DMS

CONTRAINTES DE PLAGE (après !):
- N = type entier, R = type réel décimal, A = date
- Bornes EXCLUSIVES par défaut : borne_inf<TYPE<borne_sup  →  ]0, 120[
- Bornes INCLUSIVES (Règle 14 ext.) : borne_inf<=TYPE<=borne_sup  →  [0, 31]
- Exemples: 0<N<120 (âge), 0<R<300 (poids kg), 35<R<42 (température °C), 0<R<100 (pourcentage)
- Range calendaire (Règle 14 ext.) : 2000/01/01<A<2026/12/31

RÈGLES STRICTES DE FORMAT:
- Booléen: TOUJOURS écrire __B!boolean (jamais __B seul). pf_modalites DOIT être "Oui | Non" (jamais "boolean")
- Triléen: écrire __C!trilean, pf_modalites = "Oui | Non | Autre" (ou "Oui | Non | Ne_Sait_Pas")
- Entier temporel SANS contexte clinique précis: utiliser le raccourci lettre → __1Y!Y, __1M!M, __1W!W, __1D!D
- Entier temporel AVEC contexte clinique précis: utiliser la plage numérique → __1Y!0<N<80, __1W!0<N<42
- Réel: TOUJOURS utiliser la plage numérique → __2K!0<R<300, __2T!35<R<42, __2P!0<R<100
- Texte libre: TOUJOURS écrire __Z!1*Expression (jamais __Z seul)
- Téléphone: TOUJOURS écrire __Z!1*Tel (jamais __Z!1*Expression ni __1 — un numéro de tél commence souvent par 0 ou + et est un TEXTE, pas un entier). pf_modalites = "Numéro de téléphone (ex: 0XXXXXXXXX)"
- Cohérence séparateur ↔ multiplicité: virgule ',' ↔ *1 (select_one) ; pipe '|' ↔ * ou *N (select_multiple, N = nombre minimum de choix). JAMAIS __X!1*1 avec des '|', JAMAIS __X!1* avec des ','.
- Identifiant externe: utiliser __E (pas __Z) pour les codes ID DHIS2, Kobo, etc.
- Géolocalisation: utiliser __G__X!DMS ou __G__X!DD (jamais __Z pour les coordonnées GPS)
- Série chronologique: préfixer par l'année → 2025__Expression__type (Règle 15)
- Référentiel admin. externe: Admin_Radical_ (jamais de liste inline pour les unités admin.) (Règle 16)
- Bornes inclusives: utiliser <= pour inclure les bornes → 0<=N<=10 (Règle 14 ext.)
- Trimestre: utiliser __1Q pour les données trimestrielles (Règle 20)
- Caractères accentués: INTERDITS dans les noms codifiés → translittérer (Coordonnees, Region, Determine)

RÈGLES DE MODALITÉS (CRITIQUE — à respecter STRICTEMENT):
- ⛔ NE JAMAIS inventer de modalités supplémentaires qui ne sont pas dans la grammaire ou le libellé de la question.
- ⛔ NE JAMAIS ajouter "Autre", "Ne_Sait_Pas", "0" ou toute option par défaut SAUF si le libellé de la question ou l'exemple dans la grammaire le mentionne explicitement.
- Sexe: TOUJOURS Sexe_=[Masculin,Feminin,Autre] (liste standard du DPF) — n'en ajouter aucune autre.
- Reproduire EXACTEMENT les modalités données dans la grammaire ou dans le libellé de la question.
- Si la question fournit une liste entre parenthèses ou crochets, utiliser CES modalités, pas d'autres.

EXTENSIONS PHAKTS v2025.10.22 (Règles 15–20):
- Règle 15 — Préfixe année: <AAAA>__<expression>  →  2025__AS__Population__1!0<N<1000000
- Règle 16 — Référentiels admin.: Admin_<Radical>_  →  Admin_District_Sanitaire_, Admin_Region_Sanitaire_
  ⚠ Ces listes pointent vers un référentiel externe (Dictionnaire Genesis) via pulldata/select_one_external en XLSForm, jamais en dur.
- Règle 17 — Skip Logic: <lexia> = <valeur> -> @<lexia>  →  PCIME_Offert__B = Oui -> @PCIME_Activites__B
- Règle 18 — Champ composite répété (matrice M2): _<Radical>__1<Mot>__2<Mot>__M2!<liste>><Type1>|<Type2>
  →  _Service__PCIME__1Activite__2Cout__M2!PCIME_Activite_>Expression|Number
  (XLSForm = begin_repeat à 2 colonnes ; M2 et non L2 pour éviter collision avec xType Longueur)
- Règle 19 — Géolocalisation: <Expr>__G__X!DMS ou !DD  →  Etablissement__Coordonnees__G__X!DMS
- Règle 20 — Trimestre Q: Period Q ajouté  →  2025__CPN1__1Q!0<N<5

RÈGLES DISCRIMINANTES DE TYPE (CRITIQUE — à appliquer AVANT de choisir le type):
- "Âge / Age" → TOUJOURS entier __1Y!0<N<120 ou __1Y!Y, JAMAIS __Z!1*Expression. Le mot "âge" implique systématiquement un entier en années.
- "Combien de/d'..." → TOUJOURS entier __1 (avec plage si possible), JAMAIS __B!boolean
- "À quelle distance / distance en km" → 2 cas :
   • si le libellé attend une VALEUR NUMÉRIQUE (ex: "Distance en km", "Combien de km") → __2L!0<R<100 (réel longueur)
   • si le libellé propose des TRANCHES (ex: "Moins de 1 km / 1-5 km / Plus de 5 km") OU si l'enquête capture des catégories de proximité → __X!1*1Distance_=[Moins_de_1_km,De_1_a_5_km,De_5_a_10_km,Plus_de_10_km]
   • JAMAIS __B!boolean
- "Quel/Quelle/Quels/Quelles + nom" (secteur, type, moment, issue...) → TOUJOURS __X (select) ou __Z!1*Expression (texte libre selon le contexte), JAMAIS __B!boolean
- "Pourquoi / Pour quelle raison" → TOUJOURS __X!1*Raison_ (select) ou __Z!1*Expression (texte libre), JAMAIS __B!boolean. Le mot "pourquoi" demande une RAISON, pas Oui/Non.
- "Où / Dans quel lieu / À quel endroit" → TOUJOURS __X!1*1Lieu_ (select_one) ou __Z!1*Expression, JAMAIS __B!boolean. Le mot "où" demande un LIEU, pas Oui/Non.
- "Numéro de téléphone / Téléphone / Contact / Tel / Portable / Mobile / WhatsApp" → TOUJOURS __Z!1*Tel (JAMAIS __1 ni __Z!1*Expression — un numéro de tél est un TEXTE, peut commencer par 0 ou +, ne se calcule pas). pf_modalites = "Numéro de téléphone (ex: 0XXXXXXXXX)"
- "Numéro de / N°" → __1 (entier) si purement numérique (ex: N° dossier entier), __Z!1*Tel si téléphone/contact, __Z!1*Expression si alphanumérique (code, identifiant). JAMAIS __B!boolean.
- "Secteur d'activité / Zone d'habitation / Zone de résidence" → TOUJOURS __X!1*1Liste_ (select_one) avec liste prédéfinie. JAMAIS __Z!1*Expression (ces champs sont TOUJOURS structurables).
- "Niveau d'éducation / Niveau d'instruction" → SYNONYMES. TOUJOURS Niveau_Instruction__X!1*1Instruction_ avec liste prédéfinie Instruction_=[Primaire,Secondaire,Supérieur,Autre]. JAMAIS créer une liste inline Education_Niveau_.
- "À quel moment / Quand / À quelle période" → __X!1*1Liste_ (select_one) ou __Z!1*Expression si non structurable, JAMAIS __B!boolean
- "Quels sont les antécédents / issues / résultats" → __X!1*Liste_ (select_multiple) si les options sont structurables, sinon __Z!1*Expression
- __B!boolean = RÉSERVÉ UNIQUEMENT aux questions fermées OUI/NON ("Avez-vous...?", "Êtes-vous...?", "Est-ce que...?", "Consommez-vous...?")
- __C!trilean = pour les questions à 3 états (Oui/Non/Autre, Oui/Non/Ne_Sait_Pas, Oui/Non/En_cours) — JAMAIS __B
- __2P = pour tout POURCENTAGE ou TAUX (couverture, prévalence, proportion) — JAMAIS __2 seul ni __1
- __2V = pour les VOLUMES de liquide (doses, capacités) — préciser l'unité dans la contrainte
- __2F = pour les MONTANTS FINANCIERS (coûts, tarifs, budgets) — préciser la devise dans la contrainte
- __2I = pour les INDICES et SCORES composites (z-scores, indices nutritionnels, DEA) — peut être négatif
- __E = pour les IDENTIFIANTS EXTERNES fixes (codes DHIS2, numéros Kobo, codes établissements) — JAMAIS __Z
- __G__X!DMS = pour les COORDONNÉES GPS — JAMAIS __Z ni __X standard
- __1Q = pour les DONNÉES TRIMESTRIELLES — préférer __1Q à __1M/4 ou __1 avec note
- "Oui / Non / Ne sait pas" → TOUJOURS __C!trilean, JAMAIS __B!boolean ni __X
- IGNORER les préfixes "Selon vous", "Si oui", "D'après vous" — ils ne changent PAS le type. Analyser le MOT-CLÉ principal: quel/quels/combien/comment/pourquoi/où
- Si la question attend un NOMBRE en réponse → __1 (entier) ou __2 (réel), JAMAIS __B!boolean
- Si la question attend un CHOIX parmi une liste → __X, JAMAIS __B!boolean
- Si la question attend du TEXTE LIBRE → __Z!1*Expression
- RADICAL ABSTRAIT: le radical doit décrire le CONCEPT SÉMANTIQUE de la question, PAS reprendre les mots de la phrase. "Pourquoi n'avez-vous pas reçu" → Raison_Non_Reception (concept), JAMAIS "Pourquoi_Avez_Recu" (copie de la phrase). "Où avez-vous reçu" → Lieu_Reception (concept), JAMAIS "Avez_Recu_Vos" (copie de la phrase).
- DISCRIMINATION SÉMANTIQUE DU RADICAL: lire le COMPLÉMENT D'OBJET pour choisir le bon radical:
  • "effets sur la fertilité" → Fumer_Effet_Fertilite_ (ovocytes, hormones, ménopause...)
  • "effets sur le fœtus / pendant la grossesse" → Fumer_Effet_Foetus_ (poids naissance, prématurité, mort fœtale...)
  • "effets sur le bébé allaité" → Fumer_Effet_Bebe_ (irritabilité, colique, trouble sommeil...)
  NE JAMAIS réutiliser un radical d'un autre domaine. Chaque complément = un radical distinct.

CONVENTIONS SYNTAXIQUES:
- '_' compose les mots d'un radical (Snake_Case) : Collecte_Routine, Statut_Matrimonial
- '__' (double underscore) sépare les parties : Radical__Déterminant__Affix
- '!' introduit la contrainte : Age__1Y!0<N<120
- '<=' borne inclusive (Règle 14 ext.) : 0<=N<=31
- '0' préfixe la négation / option Autre/Aucun
- '->' opérateur de Skip Logic : Lexia = Valeur -> @Cible
- '@' ancre la question cible dans le Skip Logic
- 'Admin_' préfixe de référentiel administratif externe (Règle 16)
- '<AAAA>__' préfixe temporel absolu pour séries chronologiques (Règle 15)
- '_Radical__1Mot__2Mot__M2' champ composite répété (Règle 18)
- Identifiant de liste (ex: Statut_Matrimonial_) = vocabulaire contrôlé réutilisable
- Radicaux ABSTRAITS et GÉNÉRIQUES — jamais d'accents, jamais copie de la phrase

MÉTHODE DE CODAGE EN 5 ÉTAPES:
1. Partir de la question terrain
2. Identifier le sens métier central (radical abstrait, sans accents)
3. Choisir le type de réponse (B, C, A, X, Z, E, G, 1, 2)
4. Ajouter période/unité utile (Y, M, W, D, H, U, S, Q, K, T, L, P, V, F, I)
5. Poser la contrainte de qualité (!plage, !<=bornes, !liste, !DMS/DD)

EXEMPLES DU MODÈLE DE RÉFÉRENCE:
- "Quel est votre âge ?"                          → Age__1Y!0<N<120
- "Avez-vous un emploi ?"                          → Emploi__B!boolean
- "Quel est votre niveau d'instruction ?"          → Niveau_Instruction__X!1*1Instruction_            Instruction_=[Primaire,Secondaire,Supérieur,Autre]
- "Quelle est votre religion ?"                    → Religion__X!1*1Religion_            Religion_=[Chrétienne,Musulmane,Traditionnelle,Autre,0]
- "Quel est votre Profession ?"                 → Profession__X!1*1Profession_            Profession_=[Sans_emploi,Ménagère,Employée,Commerçante,Informelle/Auto_entreprise,Autre]
- "Quel est votre groupe ethnique ?"              → Ethnie__X!1*1Ethnie_            Ethnie_=[Gouro,Bété,Malinké,Baoulé,Sénoufo,Agni,Autre]
- "Quel est votre secteur d'activité ?"          → Secteur_Activite__X!1*1Secteur_Activite_            Secteur_Activite_=[Agriculture,Industrie,Services,Commerce,Informel,Autre]
- "Région sanitaire d'appartenance ?"              → Region_Sanitaire__Appartenance__X!1*1Region_            Region_=[ABIDJAN_1,AGNEBY_TIASSA,BELIER,BERE,BOUNKANI,FOLON,GBEKE,MORONOU,SAN_PEDRO,TCHOLOGO,TONKPI,WORODOUGOU]
- "District sanitaire d'appartenance ?"            → District_Sanitaire__Appartenance__X!1*1District_            District_=[ABIDJAN_1-ABOBO_OUEST,ABIDJAN_1-YOPOUGON_OUEST_SONGON,AGNEBY_TIASSA-AGBOVILLE,BELIER-TIEBISSOU,BERE-MANKONO,BOUNKANI-BOUNA,FOLON-KANIASSO,GBEKE-BOUAKE_NORD_OUEST,MORONOU-ARRAH,SAN_PEDRO-SAN_PEDRO,TCHOLOGO-OUANGOLODOUGOU,TONKPI-DANANE,WORODOUGOU-SEGUELA]
- "Nom de l'établissement ?"                       → Nom_Etablissement__Z!1*Expression                            Expression
- "Zone de résidence ?"                            → Zone_Residence__X!1*1Zone_Residence_            Zone_Residence_=[Urbain,Rural,Périurbain]
- "Distance entre l'habitation et l'établissement de santé (en km) ?" → Distance_Habitation_Etablissement__2L!0<R<100
- "À quelle distance se trouve votre lieu d'habitation par rapport à l'établissement de santé ?" → Distance_Habitation_Etablissement__X!1*1Distance_            Distance_=[Moins_de_1_km,De_1_a_5_km,De_5_a_10_km,Plus_de_10_km]
  ⚠️ NOTE: 2 codifications possibles selon le format de saisie : __2L pour valeur numérique exacte, __X!1*1 pour tranches catégorielles. Choisir selon la question.
  ⚠️ ERREUR COURANTE: "Quelle_Distance_Trouve_" — INTERDIT. Supprimer le déterminant "Quelle" et le verbe "Trouve". Le radical doit être ABSTRAIT et reprendre les NOMS-CLÉS de la question : "distance" + "habitation" + "établissement". → Distance_Habitation_Etablissement (RADICAL CORRECT)
  ⚠️ ERREUR COURANTE: list_key identique au radical (ex: Quelle_Distance_Trouve__X!1*1Quelle_Distance_Trouve_) — la liste DOIT avoir un nom court et générique RÉUTILISABLE (Distance_, Niveau_, Frequence_), JAMAIS le radical complet de la question.
- "Quel est votre statut matrimonial ?"           → Statut_Matrimonial__X!1*1Statut_Matrimonial_            Statut_Matrimonial_=[Célibataire,Marié(e),Divorcé(e),Veuf(ve),Concubinage]
- "Êtes-vous enceinte ?"                           → Grossesse__B!boolean
- "Si oui, de combien de mois ?"                   → Grossesse__1M!M
- "Si oui, donnez l'âge de la grossesse (semaines)" → Age_Grossesse__1W!W
- "Allaitez-vous votre enfant ?"                   → Allaitement__B!boolean
- "Si oui, quel type d'allaitement maternel ?"    → Allaitement_Type__X!1*1Allaitement_            Allaitement_=[Naturel,Artificiel,Mixte]
- "Depuis combien de temps allaitez-vous (semaines) ?" → Allaitement_Duree__1W!W
- "Niveau de motivation des agents"                → Motivation_Agents__Donnees__X!1*1Motivation_            Motivation_=[Très_motivée,Moyennement_motivée,Peu_motivée,Pas_motivée]
- "L'établissement a-t-il un système standard ?"  → Collecte_Routine__Systeme_Standard__B!boolean
- "Compétences du personnel pour interpréter"      → Competences_Personnel__Interpretation__X!1*1Niveau_            Niveau_=[Eleve,Moyen,Faible]
- "Quelle est votre date de naissance ?"           → Date__Naissance__A!YYYY/MM/DD
- "Avez-vous déjà entendu parler des risques du tabac ou de la nicotine sur la santé des femmes ou des enfants ?" → Connaissance_Risque_Fumer__B!boolean
- "Si oui, comment avez-vous appris les risques du tabac sur la grossesse ?" → Connaissance_Risque_Fumer__SRC!1*Source_Info_Sante_            Source_Info_Sante_=[Personnel_Sante|Media|Reseaux_Sociaux|Entourage|Famille|0]
- "Quels sont les effets possibles du tabac sur la fertilité de la femme ? (citez au moins un effet)" → Fumer_Effet_Fertilite__X!1*Fumer_Effet_Fertilite_            Fumer_Effet_Fertilite_=[Grossesse_Extra_Uterine|Diminution_Ovocyte|Alteration_hormonale|Menopause_Precoce|Dyskinesie_Ciliaire|Delai_Conception_allonge|Risque_Infertilite_Accru|Fausse_Couche|Diminution_Chances_Succès_PMA|0]
- "Quels sont les effets possibles du tabac sur le foetus pendant la grossesse ? (citez au moins un effet)" → Fumer_Effet_Foetus__X!1*Fumer_Effet_Foetus_            Fumer_Effet_Foetus_=[Faible_Poids_Naissance|Retard_Croissance|Naissance_Prématuré|Risque_Mort_Foetale_Accru|Syndrome_Mort_Subite_Nourrisson|Complication_Placentaire|Rupture_Membranes|Trouble_Apprentissage_Langage|0]
- "Quels sont les effets possibles du tabac sur le bébé allaité ? (citez au moins un effet)" → Fumer_Effet_Bebe__X!1*Fumer_Effet_Bebe_            Fumer_Effet_Bebe_=[Irritabilite|Trouble_Digestif|Colique|Vomissement|Trouble_Sommeil|Augmentation_Risque_MS|Probleme_Respiratoire|0]
- "Savez-vous que fumer pendant la grossesse est dangereux pour le bébé et la mère ?" → Fumer_Danger_SME__B!boolean
- "Quel type de produit de tabac et/ou de la nicotine consommez-vous ?" → Fumer_Type__X!1*Fumer_Type_            Fumer_Type_=[Cigarette|Cigare|Pipe|Cigarette_Electronique|Chicha|Tabac_A_Macher|Tabac_A_Priser|Snus|Autre]
- "Si oui, à quel âge avez-vous commencé ?" → Fumer_Debut_Age__1Y!Y
- "À quelle fréquence consommez-vous du tabac actuellement ?" → Fumer_Conso__FRQ__1D!0<D<8
- "Combien de cigarettes consommez-vous par semaine ?" → Cigarette_Conso__1W!W
- "Au cours des 30 derniers jours, combien de jours avez-vous utilisé une cigarette électronique ?" → Cigarette_Electro_Conso__1D!0<D<31
- "Consommez-vous du tabac pendant cette grossesse ?" → Tabac_Conso_Grossesse__B!boolean
- "Consommez-vous des cigarettes électroniques pendant l'allaitement ?" → Cigarette_Electro_Conso_Allaitement__B!boolean
- "Pendant votre grossesse, avez-vous été informée des risques du tabac et de la nicotine sur votre santé et celle de votre bébé ?" → Info_Risque_Fumer_Grossesse__B!boolean
- "Si oui, où avez-vous obtenu l'information ?" → Info_Risque_Fumer_Grossesse__SRC!1*Source_Info_Sante_            Source_Info_Sante_=[Personnel_Sante|Media|Reseaux_Sociaux|Entourage|Famille|0]
- "Êtes-vous exposée à la fumée de tabac à la maison ou au travail ?" → Exposition_Fumer_Maison_Travail__B!boolean
- "Si oui, à quelle fréquence / à quel degré ?" → Exposition_Fumer_Maison_Travail__1W!W
- "Selon vous, est-il dangereux de fumer ou vapoter à la maison, au travail ou dans des lieux publics sur leur santé et celle de leur enfant ?" → Connaissance_Risque_Exposition_Fumer__B!boolean
- "Pensez-vous que fumer ou vapoter pendant la grossesse est dangereux ?" → Grossesse__Danger_Fumer__X!1*1Dangereux_            Dangereux_=[Très_dangereux,Dangereux,Peu_dangereux,Pas_dangereux]
- "Pensez-vous que fumer ou vapoter pendant l'allaitement est dangereux ?" → Allaitement__Danger_Fumer__X!1*1Dangereux_            Dangereux_=[Très_dangereux,Dangereux,Peu_dangereux,Pas_dangereux]
- "Si oui, à quel point êtes-vous d'accord que fumer et vapoter est dangereux pendant l'allaitement ?" → Dangereux_Niveau_Daccord__X!1*1Niveau_Daccord_            Niveau_Daccord_=[D_accord,Pas_d_accord,Plutot_d_accord,Tout_a_fait_d_accord,Pas_du_tout_d_accord]
- "Si vous fumez ou vapotez, avez-vous reçu un accompagnement ou des conseils pour réduire ou arrêter votre consommation ?" → Fumer_Arret_Conseil__B!boolean
- "Si oui, qui vous a accompagné ou donné des conseils ?" → Arret_Fumer_Conseil__SRC!1*Source_Info_Sante_            Source_Info_Sante_=[Personnel_Sante|Media|Reseaux_Sociaux|Entourage|Famille|0]
- "Lors de votre consultation prénatale vous a-t-on demandé si vous fumez ou vapotez ?" → Consultation_Prenatale_Fumer__C!trilean            Oui | Non | Ne_Sait_Pas
- "Lors de votre consultation postnatale, vous a-t-on demandé si vous fumez ou vapotez ?" → Consultation_Postnatale_Fumer__C!trilean            Oui | Non | Ne_Sait_Pas
  ⚠️ ERREUR COURANTE: __X!1*1Trilean_ — une question Oui / Non / Ne sait pas est un TRILÉEN → __C!trilean (Règle 11 ext.), JAMAIS __X ni __B
- "Si oui, vous a-t-on proposé une aide pour arrêter de fumer (conseils, consultation avec un professionnel de santé) ?" → Consultation_Postnatale_Fumer_Arret_Aide__B!boolean
- "Si oui, vous a-t-on prescrit un traitement ?" → Consultation_Prenatale_Fumer_Arret_Traitement__B!boolean
- "Seriez-vous intéressée par un programme d'accompagnement pour arrêter le tabac ou la nicotine pendant la grossesse ou après ?" → Pre_Post_Natal_Fumer_Arret_Accompagnement_Interesse__B!boolean
- "Seriez-vous intéressée par un programme d'accompagnement pour arrêter le tabac ou la nicotine pendant l'allaitement ?" → Allaitement_Fumer_Arret_Accompagnement_Interesse__B!boolean
- "Avez-vous déjà essayé ou essayez-vous actuellement d'arrêter de fumer ou de vapoter pendant la grossesse ?" → Grossesse_Fumer_Arret_Tentative__B!boolean
- "Avez-vous déjà essayé ou essayez-vous actuellement d'arrêter de fumer ou de vapoter pendant l'allaitement ?" → Allaitement_Fumer_Arret_Tentative__B!boolean
- "Avez-vous bénéficié d'un accompagnement pour arrêter de fumer ?" → Fumer_Arret_Accompagnement_Recu__B!boolean
- "Êtes-vous motivée pour arrêter de fumer ou de vapoter pendant la grossesse ?" → Grossesse_Fumer_Arret_Motivation__X!1*1Motivation_            Motivation_=[Très_motivée,Moyennement_motivée,Peu_motivée,Pas_motivée]
- "Êtes-vous motivée pour arrêter de fumer ou de vapoter pendant l'allaitement ?" → Allaitement_Fumer_Arret_Motivation__X!1*1Motivation_            Motivation_=[Très_motivée,Moyennement_motivée,Peu_motivée,Pas_motivée]
- "Combien de consultations prénatales avez-vous effectuées ?" → Nombre_Consultations_Prenatales__1
- "Combien de consultations postnatales avez-vous effectuées ?" → Nombre_Consultations_Postnatales__1
- "Avez-vous déjà eu des complications liées au tabac ?" → Complication_Tabac__B!boolean
- "Votre entourage vous encourage-t-il à arrêter ?" → Fumer_Arret_Encouragement_Entourage__B!boolean
- "Avez-vous participé à des ateliers de sensibilisation sur les méfaits du tabagisme ?" → Fumer_Mefait_Participation_Sensibilisation__B!boolean
- "Avez-vous vu des campagnes (télé, radios, réseaux sociaux, affiches...) anti-tabac (interdiction de fumer dans les espaces publics...) ?" → Campagne_Antitabac_Media__B!boolean

EXEMPLES ÉPIDÉMIOLOGIQUES (Notification de cas):
- "Combien de cas de Rougeole avez-vous notifiés depuis le début d'année ?" → Nombre_Cas_Rougeole__1!0<N<9999
  ⚠️ ERREUR COURANTE: __B!boolean — "combien de cas" = entier, JAMAIS un booléen
- "Combien de cas de Fièvre hémorragique avez-vous notifiés depuis le début d'année ?" → Nombre_Cas_Fievre_Hemorragique__1!0<N<9999
- "Combien de cas de Paludisme avez-vous notifiés ce mois ?" → Nombre_Cas_Paludisme__1!0<N<99999
- "Combien de décès liés au Choléra avez-vous enregistrés ?" → Nombre_Deces_Cholera__1!0<N<9999
- "Combien d'échantillons ont été prélevés ?" → Nombre_Echantillons__1!0<N<9999
- "Combien de cas de PFA avez-vous notifiés depuis le début d'année ?" → Nombre_Cas_PFA__1!0<N<9999
- "Quelle a été la couverture vaccinale obtenue lors des campagnes sur 12 mois pour la Rougeole ?" → Couverture_Vaccinale_Rougeole__2P!0<R<200
  ⚠️ ERREUR COURANTE: __X!1*1Liste_ — "couverture vaccinale" = taux/pourcentage (valeur numérique réelle) → __2P, PAS un choix dans une liste. La borne supérieure 200 car la couverture administrative peut dépasser 100%.
  ⚠️ ERREUR COURANTE: radical "Quelle_Couverture_Vaccinale" — supprimer les déterminants ("Quelle"). Inclure la maladie dans le radical si la question est spécifique.

EXEMPLES SURVEILLANCE & CONTEXTE ÉPIDÉMIOLOGIQUE:
- "Y a-t-il des mouvements de population (déplacements, migrations, réfugiés) ?" → Mouvements_Population__B!boolean
  ⚠️ ERREUR COURANTE: __Z!1*Expression — "Y a-t-il" = question fermée Oui/Non → __B!boolean, PAS texte libre. Le texte libre (__Z) ne s'utilise que si on demande de DÉCRIRE ou DÉTAILLER.
- "Si oui, décrivez les mouvements de population" → Mouvements_Population__Description__Z!1*Expression
  ⚠️ NOTE: Ici c'est __Z car on DEMANDE une description textuelle
- "Y a-t-il eu une flambée épidémique dans la zone ?" → Flambee_Epidemique__B!boolean
- "Si oui, quelle maladie ?" → Flambee_Epidemique__Maladie__X!1*1Maladie_            Maladie_=[Rougeole,Cholera,Paludisme,Fievre_Hemorragique,Meningite,COVID19,Autre]
- "Si oui, quelle(s) maladie(s) ?" → Flambee_Epidemique__Maladie__X!1*Maladie_            Maladie_=[Rougeole|Fievre_Hemorragique|PFA|Diarrhee|Meningite]
  ⚠️ ERREUR COURANTE: Quelle_Maladie_Plusieurs__X — le radical doit être ABSTRAIT et lié au contexte parent, pas verbeux. Le pluriel "(s)" → pipe (select_multiple, pas virgule)
  ⚠️ ERREUR COURANTE: accents/espaces dans les modalités (Fièvre hémorragique) — utiliser Snake_Case SANS accents (Fievre_Hemorragique)
  ⚠️ ERREUR COURANTE: __X!1*1Maladie_ avec pipe "|" — INCOHÉRENT ! *1 = select_one (max 1 choix) exige la virgule "," (exclusif). Le pipe "|" = cumulable → DOIT utiliser * (sans limite) ou *N (min N). RÈGLE: pipe "|" ↔ * / virgule "," ↔ *1
  ⚠️ SKIP: "Si oui" → Flambee_Epidemique__B -> @Flambee_Epidemique__Maladie__X

EXEMPLES DÉMOGRAPHIQUES (Fiche Identité Patient):
- "Nom du patient ?"                               → Patient__Nom__Z!1*Expression
- "Date de naissance ?"                             → Date__Naissance__A!YYYY/MM/DD
- "Âge en années ?"                                 → Age__1Y!0<N<120
- "Age du patient"                                  → Age_Patient__1Y!0<N<120
  ⚠️ ERREUR COURANTE: __Z!1*Expression — "âge" = TOUJOURS entier __1Y, JAMAIS texte libre
- "Quel âge a le patient ?"                         → Age_Patient__1Y!0<N<120
- "Sexe ?"                                          → Sexe__X!1*1Sexe_            Sexe_=[Masculin,Feminin,Autre]
- "Employé(e) actuellement ?"                       → Emploi__B!boolean
- "Niveau d'éducation ?"                            → Niveau_Instruction__X!1*1Instruction_            Instruction_=[Primaire,Secondaire,Supérieur,Autre]
  ⚠️ ERREUR COURANTE: "éducation" = "instruction" — TOUJOURS utiliser la liste prédéfinie Instruction_, JAMAIS créer une liste inline Education_Niveau_
- "Lieu de résidence ?"                             → Residence__Z!1*Expression
- "Numéro de téléphone du patient ?"               → Patient__Telephone__Z!1*Tel                           Numéro de téléphone (ex: 0XXXXXXXXX)
- "Numéro de téléphone de l'enquêteur ?"           → Enqueteur_Telephone__Z!1*Tel                          Numéro de téléphone (ex: 0XXXXXXXXX)
  ⚠️ ERREUR COURANTE: __Z!1*Expression — "numéro de téléphone" = texte avec validation regex → TOUJOURS __Z!1*Tel, JAMAIS __Z!1*Expression générique
  ⚠️ ERREUR COURANTE: __1 — un numéro de téléphone peut commencer par 0 ou +, c'est un TEXTE, PAS un entier
- "Zone d'habitation"                               → Zone_Habitation__X!1*1Zone_Residence_            Zone_Residence_=[Urbain,Rural,Périurbain]
  ⚠️ ERREUR COURANTE: __Z!1*Expression — "zone" = TOUJOURS select (Urbain/Rural/Périurbain), JAMAIS texte libre
- "Secteur d'activité"                              → Secteur_Activite__X!1*1Secteur_Activite_            Secteur_Activite_=[Public,Privé,Informel,Autre]
  ⚠️ ERREUR COURANTE: __Z!1*Expression — "secteur d'activité" = TOUJOURS select, JAMAIS texte libre
- "Numéro de participant"                            → Numero_Participant__1!0<N<99999
  ⚠️ ERREUR COURANTE: __Z!1*Expression — "numéro" = entier, JAMAIS texte
- "Nombre de personnes au foyer ?"                  → Menage__Taille__1!0<N<30

EXEMPLES CLINIQUES (Paramètres Vitaux):
- "Poids en kilogrammes ?"                          → Poids__2K!0<R<300
- "Taille en mètres ?"                              → Taille__2L!0<R<3
- "Température corporelle en °C ?"                  → Temperature_Corporelle__2T!35<R<42
- "La température est-elle relevée deux fois chaque jour ?" → Temperature_Releve_Biquotidien__B!boolean
  ⚠️ ERREUR COURANTE: __2T!35<R<42 — "est-elle relevée deux fois" = question fermée Oui/Non → __B!boolean, PAS une valeur de température. __2T est pour CAPTURER une mesure, pas pour demander si un relevé est fait.
- "Pression artérielle systolique ?"                → Pression_Arterielle__Systolique__2!50<R<250
- "Pression artérielle diastolique ?"               → Pression_Arterielle__Diastolique__2!30<R<150
- "Fréquence cardiaque (bpm) ?"                     → Frequence_Cardiaque__1!30<N<250
- "Saturation en oxygène (%) ?"                     → O2_Saturation__2!60<R<100
- "Glucose sanguin (g/L) ?"                         → Glycemie__2!0<R<30
- "Êtes-vous diabétique ?"                          → Diabete__B!boolean
- "Avez-vous une hypertension connue ?"             → Hypertension__B!boolean

EXEMPLES CORRECTIFS (erreurs fréquentes à éviter):
- "Quelle est votre qualification ?"                → Qualification__X!1*1Qualification_            Qualification_=[Medecin,Infirmier,Sage_Femme,Pharmacien,Technicien_Labo,Agent_Sante_Communautaire,Autre]
  ⚠️ ERREUR COURANTE: Age__1Y!0<N<120 — "Quelle est votre qualification" ≠ un âge. "Quelle est votre..." = sélection (__X), le radical doit correspondre au SENS de la question (Qualification, pas Age).
- "Dans quel secteur d'activité êtes-vous ?"        → Secteur_Activite__X!1*1Secteur_Activite_            Secteur_Activite_=[Public,Privé,Informel,Autre]
  ⚠️ ERREUR COURANTE: __Z!1*Expression — "secteur d'activité" = select (structurable), JAMAIS texte libre
  ⚠️ ERREUR COURANTE: __B!boolean — "quel secteur" ≠ Oui/Non
- "Pourquoi n'avez-vous pas reçu de MILDA au cours de vos grossesses ?" → Raison_Non_Reception_MILDA__X!1*Raison_Non_Reception_MILDA_            Raison_Non_Reception_MILDA_=[Rupture_de_MILDA|Pas_ete_informe|MILDA_pas_propose|Refus|Autre]   ; affiché si Grossesse_Milda__recu = non
  ⚠️ ERREUR COURANTE: __B!boolean — "pourquoi" = RAISON, pas Oui/Non. Le radical doit décrire le concept (Raison_Non_Reception_MILDA), PAS copier la phrase
- "Où avez-vous reçu vos MILDA pendant la grossesse ?" → Lieu_Reception_MILDA__X!1*1Lieu_Reception_            Lieu_Reception_=[Etablissement_de_Sante|Menage|Campagne_Masse|Autre]   ; affiché si Grossesse_Milda__recu = oui
  ⚠️ ERREUR COURANTE: __B!boolean — "où" = LIEU, pas Oui/Non. Le radical doit décrire le concept (Lieu_Reception), PAS copier la phrase
- "Dans quel état est votre MILDA ?"                  → Etat_MILDA__X!1*1Etat_MILDA_            Etat_MILDA_=[Neuf|Bon|Use|Dechire|Autre]
- "Pourquoi n'avez-vous pas dormi sous MILDA la nuit dernière ?" → Raison_Non_Utilisation_MILDA__X!1*Raison_Non_Utilisation_            Raison_Non_Utilisation_=[Inconfortable|Oubli|Difficulte_Installation|Ne_Pas_Utilise|Autre]   ; affiché si Date_Utilisation_MILDA absent ou antérieur
  ⚠️ ERREUR COURANTE: __B!boolean — "pourquoi pas dormi" = RAISON, pas Oui/Non
- "Pourquoi les personnes de votre ménage ne dorment pas sous moustiquaire ?" → Raison_Non_Utilisation_MILDA_Menage__X!1*Raison_Non_Utilisation_            Raison_Non_Utilisation_=[Inconfortable|Oubli|Difficulte_Installation|Ne_Pas_Utilise|Autre]   ; affiché si Utilisation_MILDA_Menage = non
  ⚠️ MÊME liste Raison_Non_Utilisation_ partagée entre individu et ménage — NE PAS recréer une liste différente
- "Zone d'habitation ?"                              → Zone_Habitation__X!1*1Zone_Residence_            Zone_Residence_=[Urbain,Rural,Périurbain]
  ⚠️ ERREUR COURANTE: __Z!1*Expression — "zone" est TOUJOURS structurable (Urbain/Rural/Périurbain)
- "Numéro de participant"                            → Numero_Participant__1!0<N<99999
  ⚠️ ERREUR COURANTE: __Z!1*Expression — "numéro" = entier, pas texte
- "Combien de grossesses avez-vous eu précédemment ?" → Nombre_Grossesses__1!0<N<20
  ⚠️ ERREUR COURANTE: __B!boolean — "combien de" = entier
- "Quels sont les antécédents obstétricaux ?"        → Antecedents_Obstetricaux__X!1*Antecedent_Obstetrical_            Antecedent_Obstetrical_=[Accouchement_Normal|Cesarienne|Fausse_Couche|Mort_Ne|Premature|Grossesse_Extra_Uterine|0]
  ⚠️ ERREUR COURANTE: __B!boolean — "quels antécédents" = sélection, pas Oui/Non
- "Combien d'enfants vivants avez-vous ?"           → Nombre_Enfants_Vivants__1!0<N<20
  ⚠️ ERREUR COURANTE: __B!boolean — "combien d'" = entier
- "Si arrêté, à quel moment ?"                       → Arret_Moment__X!1*1Moment_Arret_            Moment_Arret_=[Avant_Grossesse,Premier_Trimestre,Deuxieme_Trimestre,Troisieme_Trimestre,Apres_Accouchement]
  ⚠️ ERREUR COURANTE: __B!boolean — "à quel moment" = sélection temporelle
- "Quel est l'issue de la grossesse ?"              → Issue_Grossesse__X!1*1Issue_Grossesse_            Issue_Grossesse_=[Accouchement_Normal,Cesarienne,Fausse_Couche,Mort_Ne,Avortement,Premature,Autre]
  ⚠️ ERREUR COURANTE: __B!boolean — "quelle issue" = sélection
- "Combien de fois avez-vous été hospitalisée ?"    → Nombre_Hospitalisations__1!0<N<50
  ⚠️ ERREUR COURANTE: __B!boolean — "combien de fois" = entier
- "Si oui, quel(s) produit(s) du tabac consommiez-vous ?" → Produit_Tabac__X!1*Produit_Tabac_            Produit_Tabac_=[Cigarette|Cigare|Pipe|Cigarette_Electronique|Chicha|Tabac_A_Macher|Tabac_A_Priser|Snus|Autre]
  ⚠️ ERREUR COURANTE: __B!boolean — "quel(s) produit(s)" = sélection multiple
- "Si oui, à quelle fréquence ? (nombre de consommation par jour)" → Frequence_Conso__1D!0<N<100
  ⚠️ ERREUR COURANTE: __B!boolean — "fréquence (nombre par jour)" = entier par jour
- "Selon vous, quels sont les effets possibles de la consommation des produits du tabac sur la fertilité de la femme ?" → Fumer_Effet_Fertilite__X!1*Fumer_Effet_Fertilite_            Fumer_Effet_Fertilite_=[Grossesse_Extra_Uterine|Diminution_Ovocyte|Alteration_hormonale|Menopause_Precoce|Dyskinesie_Ciliaire|Risque_Infertilite_Accru|Fausse_Couche|0]
  ⚠️ ERREUR COURANTE: __B!boolean — "Selon vous, quels sont les effets" = sélection multiple, le préfixe "Selon vous" ne change PAS le type
- "Selon vous, quels sont les effets possibles de la consommation des produits du tabac ou de la nicotine, sur le fœtus pendant la grossesse ?" → Fumer_Effet_Foetus__X!1*Fumer_Effet_Foetus_            Fumer_Effet_Foetus_=[Faible_Poids_Naissance|Retard_Croissance|Naissance_Premature|Risque_Mort_Foetale_Accru|Syndrome_Mort_Subite_Nourrisson|Complication_Placentaire|Rupture_Membranes|Trouble_Apprentissage_Langage|0]
  ⚠️ ERREUR COURANTE: Fumer_Effet_Fertilite_ — "fœtus" ≠ "fertilité". Le mot-clé FŒTUS → Fumer_Effet_Foetus_, le mot-clé FERTILITÉ → Fumer_Effet_Fertilite_. NE JAMAIS confondre les deux radicaux.
- "Selon vous, quels sont les effets possibles de la consommation des produits du tabac sur le bébé allaité ?" → Fumer_Effet_Bebe__X!1*Fumer_Effet_Bebe_            Fumer_Effet_Bebe_=[Irritabilite|Trouble_Digestif|Colique|Vomissement|Trouble_Sommeil|Augmentation_Risque_MS|Probleme_Respiratoire|0]
  ⚠️ ERREUR COURANTE: __B!boolean — "Selon vous, quels" = sélection, pas booleen
- "Selon vous, quels sont les niveaux de dangerosité liés à la consommation du tabac pendant la grossesse ou l'allaitement ?" → Niveau_Dangerosite_Tabac__X!1*1Dangereux_            Dangereux_=[Très_dangereux,Dangereux,Peu_dangereux,Pas_dangereux]
  ⚠️ ERREUR COURANTE: __B!boolean — "quels sont les niveaux" = sélection d'échelle
- "Quels sont les antécédents obstétricaux que vous avez eu ? (Quel était l'issue des précédentes grossesses ?)" → Antecedents_Obstetricaux__X!1*Antecedent_Obstetrical_            Antecedent_Obstetrical_=[Accouchement_Normal|Cesarienne|Fausse_Couche|Mort_Ne|Premature|Grossesse_Extra_Uterine|Avortement|0]
  ⚠️ ERREUR COURANTE: __Z!1*Expression — les antécédents obstétricaux sont STRUCTURABLES en liste, donc __X pas __Z

G. SKIP LOGIC (LOGIQUE DE SAUT / BRANCHEMENT CONDITIONNEL):
Syntaxe des Skip Rules — définit QUAND afficher une question selon la réponse à une autre:

  Skip_Rule  =  <lexia> '=' <valeur>  '->' '@' <lexia_cible>
             |  <lexia> '!=' <valeur> '->' '@' <lexia_cible>
             |  <lexia_booleenne>     '->' '@' <lexia_cible>
             |  '!' <lexia_booleenne> '->' '@' <lexia_cible>

Conventions:
- <lexia> = code PHAKTS de la question source (radical + type, SANS modalités)
- <valeur> = option de réponse attendue (nom d'une modalité : Oui, Non, Cigarette, etc.)
- '->' = opérateur de flux (signifie "alors afficher")
- '@' = ancre vers la question cible
- <lexia_booleenne> = question __B (truthy implicite = Oui)
- '!' = négation (la condition booléenne est fausse = Non)

Exemples de Skip Rules:
- Grossesse__B = Oui            -> @Age_Grossesse__1W     (si enceinte → demander âge gestationnel)
- Grossesse__B != Oui           -> @Section_Tabac          (si pas enceinte → sauter au tabac)
- Fumer__B                      -> @Fumer_Type__X           (si fumeur → demander le type)
- !Allaitement__B               -> @Fin                     (si PAS allaitement → fin)
- Fumer_Type__X = Cigarette     -> @Frequence_Conso__1D    (si cigarette → demander fréquence)
- Fumer_Type__X != Cigarette    -> @Autre_Produit__Z       (si PAS cigarette → texte libre)

RÈGLES DE SKIP LOGIC:
- Le champ pf_skip est OPTIONNEL — ne le renseigner que si la question contient un branchement explicite ("si oui", "si la réponse est", "en cas de")
- ⛔ INTERDIT d'INVENTER des skip rules. Si le texte de la question NE CONTIENT PAS de condition explicite ("si", "en cas de", "lorsque", "quand"), pf_skip DOIT être "" (chaîne vide).
- ⛔ NE JAMAIS déduire un skip à partir du contexte thématique. Le skip DOIT être littéralement présent dans le libellé de la question.
- Si la question commence par "Si oui," ou "Si non," → déduire le skip depuis la question booléenne précédente
- pf_skip peut contenir PLUSIEURS règles séparées par ' ; ' (point-virgule + espaces)
- Utiliser les codes PHAKTS complets comme lexias (pas les libellés)

INSTRUCTIONS:
- Chaque radical doit être ABSTRAIT / GÉNÉRIQUE (pas de déterminant)
- Construire des codes cohérents et interopérables
- Pour les questions d'évaluation (niveau, culture, qualité, compétences) → toujours __X!1*1Niveau_
- Retourne UNIQUEMENT du JSON valide (sans markdown, sans backticks, sans commentaires)

FORMAT DE RÉPONSE OBLIGATOIRE:
{"items":[{"libelle":"question originale exacte","pf_question":"Code_PHAKTS","pf_modalites":"modalités","pf_skip":"skip_rule ou vide"}]}

IMPORTANT: Le champ "pf_skip" est une chaîne vide "" si aucun branchement n'est détecté. Sinon, il contient la Skip Rule complète.
⛔ RAPPEL CRITIQUE: Dans 90% des cas, pf_skip sera "". N'invente JAMAIS de condition de saut. Seuls les mots-clés explicites dans le libellé ("si oui", "si non", "en cas de", "lorsque") autorisent un pf_skip non vide.`;

  function splitCode(pfQuestion) {
    const s = String(pfQuestion || '');
    const bang = s.indexOf('!');
    const codePart = bang >= 0 ? s.slice(0, bang) : s;
    const constraintPart = bang >= 0 ? s.slice(bang + 1) : '';
    return { codePart, constraintPart, segments: codePart.split('__') };
  }

  function isPhoneConstraint(constraintPart) {
    return /^\s*\d*\s*\*\s*\d*\s*Tel\b/i.test(String(constraintPart || ''));
  }

  // Repérage historique par sous-chaîne, gardé uniquement pour les codes mal
  // formés (affixe non séparé par "__") : il se trompe dès qu'un déterminant
  // commence par une lettre d'affixe (2025__AS__Population__1 lu comme date).
  function legacyKind(pfQuestion) {
    if (pfQuestion.includes('__B')) return 'boolean';
    if (pfQuestion.includes('__G__X')) return 'geopoint';
    if (pfQuestion.includes('__X') || pfQuestion.includes('__SRC')) return 'select';
    if (/__1[YMWDH]/.test(pfQuestion)) return 'integer';
    if (pfQuestion.includes('__Z')) return 'text';
    if (pfQuestion.includes('__A')) return 'date';
    if (pfQuestion.includes('__P')) return 'image';
    if (/__1\b/.test(pfQuestion)) return 'integer';
    return 'text';
  }

  // L'affixe est le DERNIER segment "__" du code (Radical__Déterminant__Affix).
  // kind : boolean | trilean | date | select | geopoint | text | phone | image
  //        | integer | decimal — unit : lettre de période/unité (Y, U, Q, K, P…).
  function classifyCode(pfQuestion) {
    const { codePart, constraintPart, segments } = splitCode(pfQuestion);
    const affix = segments.length >= 2 ? segments[segments.length - 1] : '';
    const prev = segments.length >= 3 ? segments[segments.length - 2] : '';
    let kind = null;
    let unit = '';
    let m;
    if (constraintPart === 'boolean' || affix === 'B') kind = 'boolean';
    else if (affix === 'C') kind = 'trilean';
    else if (affix === 'A') kind = 'date';
    else if (affix === 'X') kind = prev === 'G' ? 'geopoint' : 'select';
    else if (affix === 'SRC') kind = 'select';
    else if (affix === 'Z' || affix === 'E') kind = 'text';
    else if (affix === 'P') kind = 'image';
    else if ((m = affix.match(/^([12])([A-Z]?)$/))) {
      kind = m[1] === '1' ? 'integer' : 'decimal';
      unit = m[2];
    }
    if (!kind) kind = legacyKind(String(pfQuestion || ''));
    if (kind === 'text' && isPhoneConstraint(constraintPart)) kind = 'phone';
    return { codePart, constraintPart, affix, kind, unit };
  }

  // Multiplicité d'un choix (!1*3Liste_) = nombre après "*" : 1 = un seul
  // choix, N ≥ 2 = au moins N choix, null = "*" seul (aucune limite).
  function parseMultiplicity(constraintPart) {
    const m = String(constraintPart || '').match(/^\s*\d*\s*\*\s*(\d*)/);
    return m && m[1] ? parseInt(m[1], 10) : null;
  }

  // select_one ou select_multiple — la même décision doit servir au type du
  // champ ET à la logique de saut (selected() pour un choix multiple).
  function selectCardinality(pfQuestion, pfModalites) {
    const { codePart, constraintPart } = splitCode(pfQuestion);
    const n = parseMultiplicity(constraintPart);
    const min = n && n >= 2 ? n : null;
    if (/__SRC$/.test(codePart)) return { multiple: true, min };
    if (n === 1) return { multiple: false, min: null };
    if (min) return { multiple: true, min };
    const list = String(pfModalites || '').match(/\w+_\s*=\s*\[([^\]]+)\]/);
    return { multiple: Boolean(list && list[1].includes('|')), min: null };
  }

  // Plage « a<N<b » (bornes exclusives) ou « a<=N<=b » (inclusives, Règle 14
  // ext.) ; bornes décimales ou négatives admises (scores __2I).
  function parseRange(constraintPart) {
    const m = String(constraintPart || '').trim()
      .match(/^(-?\d+(?:[.,]\d+)?)\s*(<=?)\s*[A-Za-z]\s*(<=?)\s*(-?\d+(?:[.,]\d+)?)$/);
    if (!m) return null;
    const num = s => parseFloat(s.replace(',', '.'));
    return {
      lower: num(m[1]), upper: num(m[4]),
      lowerInclusive: m[2] === '<=', upperInclusive: m[3] === '<=',
    };
  }

  // Une borne basse 0 reste inclusive même écrite « 0<N » : « Combien de
  // cas… → 0<N<9999 » doit accepter 0 cas, un âge de 0 an est valide.
  function rangeConstraint(range) {
    if (!range) return { expression: '', message: '' };
    const lowOp = range.lowerInclusive || range.lower === 0 ? '>=' : '>';
    const highOp = range.upperInclusive ? '<=' : '<';
    return {
      expression: `. ${lowOp} ${range.lower} and . ${highOp} ${range.upper}`,
      message: `La valeur doit être comprise entre ${range.lower} et ${range.upper}.`,
    };
  }

  const PHONE_CONSTRAINT = {
    expression: "regex(., '^\\+?[0-9 ]{8,20}$')",
    message: 'Veuillez saisir un numero de telephone valide (8 a 20 chiffres).',
  };

  // Modalités d'un triléen (__C!trilean) : « Oui | Non | Ne_Sait_Pas » ou
  // « Trilean_=[Oui,Non,Ne_Sait_Pas] », à défaut Oui / Non / Autre. Oui et
  // Non restent en tête pour que « Lexia__C = Oui » produise = 'oui'.
  function trileanChoices(pfModalites) {
    const raw = String(pfModalites || '');
    const def = raw.match(/\[([^\]]+)\]/);
    const opts = (def ? def[1] : raw).split(/[|,]/).map(s => s.trim()).filter(s => s && s !== '0');
    return ['Oui', 'Non', opts.length === 3 ? opts[2] : 'Autre'];
  }

  return {
    GRAMMAR_VERSION,
    SYSTEM_PROMPT,
    splitCode,
    classifyCode,
    parseMultiplicity,
    selectCardinality,
    parseRange,
    rangeConstraint,
    isPhoneConstraint,
    PHONE_CONSTRAINT,
    trileanChoices,
  };
});
