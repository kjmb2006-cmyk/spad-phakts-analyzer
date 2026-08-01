# Cahier des charges — SPAD PHAKTS Analyzer

**Version du document :** 1.0 — 1ᵉʳ août 2026
**Rédigé à partir de :** l'état actuel du dépôt `kjmb2006-cmyk/spad-phakts-analyzer` (branche `main`) et de l'instance déployée `https://spadapp-zeta.vercel.app`
**Statut :** document de référence — décrit l'existant et sert de socle pour les évolutions futures
**Maîtrise d'ouvrage :** SPAD (WHO) — Bureau régional Afrique
**Auteur du produit :** Dr Jean-Marc Bertrand KORANDJI, avec l'équipe SPAD (Dr Wognin V., Dr M'Bra V. D. P., Mlle Dieng S., Mme Aman A. Sarah)

> Ce cahier des charges est un document **reconstitué à partir de l'application existante** (code source + application en ligne), et non un cahier des charges initial rédigé avant développement. Il formalise ce qui a été construit, afin de servir de référence pour la maintenance, les audits, la formation de nouveaux contributeurs et la planification des évolutions.

---

## Table des matières

1. [Contexte et justification](#1-contexte-et-justification)
2. [Objectifs du projet](#2-objectifs-du-projet)
3. [Périmètre](#3-périmètre)
4. [Acteurs et utilisateurs](#4-acteurs-et-utilisateurs)
5. [Vue d'ensemble fonctionnelle](#5-vue-densemble-fonctionnelle)
6. [Exigences fonctionnelles détaillées](#6-exigences-fonctionnelles-détaillées)
   - 6.1 [Module A — PHAKTS Studio (codification)](#61-module-a--phakts-studio-codification)
   - 6.2 [Module B — SPAD Analyzer (analyse statistique)](#62-module-b--spad-analyzer-analyse-statistique)
   - 6.3 [Module C — Suivi & Complétude nationale](#63-module-c--suivi--complétude-nationale)
   - 6.4 [Module D — Projets d'enquête génériques](#64-module-d--projets-denquête-génériques)
   - 6.5 [Module E — Intégration KoboToolbox](#65-module-e--intégration-kobotoolbox)
   - 6.6 [Module F — Authentification et accès](#66-module-f--authentification-et-accès)
7. [Exigences non fonctionnelles](#7-exigences-non-fonctionnelles)
8. [Architecture technique](#8-architecture-technique)
9. [Modèle de données et référentiel](#9-modèle-de-données-et-référentiel)
10. [Intégrations et API externes](#10-intégrations-et-api-externes)
11. [Sécurité et protection des données](#11-sécurité-et-protection-des-données)
12. [Environnements et déploiement](#12-environnements-et-déploiement)
13. [Livrables](#13-livrables)
14. [Historique des versions et jalons](#14-historique-des-versions-et-jalons)
15. [Critères de recette](#15-critères-de-recette)
16. [Risques, limites et hypothèses ouvertes](#16-risques-limites-et-hypothèses-ouvertes)
17. [Glossaire](#17-glossaire)
18. [Annexe — Référence rapide de la grammaire PHAKTS](#18-annexe--référence-rapide-de-la-grammaire-phakts)

---

## 1. Contexte et justification

Les enquêtes de santé publique (tabac, vaccination, revue des décès maternels…) menées par les équipes SPAD/OMS reposent sur des questionnaires collectés via **KoboToolbox**. Trois problèmes récurrents motivent ce projet :

1. **Absence de standard de codification** : deux enquêteurs ou statisticiens codifient rarement une même question de la même façon, ce qui complique la comparaison entre enquêtes et l'automatisation des analyses.
2. **Chaîne d'analyse fragmentée** : une fois les données collectées, produire des statistiques descriptives, des tableaux croisés, des analyses multivariées et un rapport nécessitait plusieurs outils (Excel, SPSS/R, Word) sans continuité entre eux.
3. **Manque de visibilité en temps réel sur l'avancement du terrain** : lors d'une enquête nationale multi-formulaires (7 formulaires officiels, plusieurs régions/districts/établissements de Côte d'Ivoire), il n'existait pas de tableau de bord centralisé permettant de savoir, à un instant donné, quels établissements ou districts ont atteint leur cible de collecte.

**SPAD PHAKTS Analyzer** répond à ces trois problèmes par une suite logicielle unique combinant codification normalisée, analyse statistique et suivi de complétude terrain, utilisable **hors ligne** (application de bureau) et **en ligne** (version web hébergée).

---

## 2. Objectifs du projet

### Objectifs généraux

- Fournir un **langage de codification formel et reproductible** pour les questionnaires de santé publique (grammaire PHAKTS).
- Permettre à une équipe technique de **passer d'un questionnaire brut à un formulaire KoboToolbox déployable** en quelques minutes.
- Offrir une **chaîne d'analyse statistique complète**, du chargement des données brutes au rapport final PDF/Word, sans changer d'outil.
- Donner aux superviseurs et coordinateurs une **vue en temps réel de la complétude de la collecte** (soumissions reçues vs. cibles attendues), par région, district, établissement, enquêteur et superviseur.

### Objectifs spécifiques mesurables

| # | Objectif | Critère de succès |
|---|---|---|
| O1 | Codifier automatiquement un lot de questions en langage PHAKTS | Codification correcte proposée pour ≥ 90 % des questions d'un modèle de référence standard, en < 10 s pour un lot de 50 questions |
| O2 | Générer un XLSForm valide et déployable sur KoboToolbox | Fichier conforme (3 feuilles `survey` / `choices` / `settings`) importable sans erreur dans Kobo |
| O3 | Produire un rapport d'analyse statistique complet | Rapport PDF/Word généré en un clic, incluant sommaire, sections choisies, commentaires automatiques |
| O4 | Suivre la complétude d'une collecte nationale multi-formulaires | Calcul reçu/cible/taux disponible par région, district, enquêteur et superviseur, avec détection d'anomalies (zéro collecte, dépassement de cible) |
| O5 | Fonctionner sans connexion internet pour les tâches cœur de métier | Codification de base, analyse statistique et génération de rapport opérationnelles sans API externe |

---

## 3. Périmètre

### Dans le périmètre

- Codification PHAKTS de questionnaires (saisie manuelle, import de fichiers, agent conversationnel IA).
- Génération de XLSForms KoboToolbox et déploiement direct sur une instance Kobo.
- Analyse statistique de données d'enquête importées (Excel) ou synchronisées depuis KoboToolbox (tris à plat, descriptives, tableaux croisés, analyses multivariées, comparaison multi-enquêtes, cartographie).
- Génération de rapports PDF/Word.
- Suivi de complétude d'une collecte nationale structurée (référentiel régions/districts/établissements/cibles), spécifique au contexte Côte d'Ivoire (7 formulaires officiels : tabac, vaccination, revue des décès maternels).
- Suivi générique de complétude pour tout autre projet d'enquête Kobo/ODK, hors référentiel SPAD.
- Distribution en application de bureau (macOS, Windows) et en application web hébergée.

### Hors périmètre

- Collecte de données sur le terrain (rôle dévolu à KoboToolbox / ODK Collect — l'application ne remplace pas l'outil de collecte mobile).
- Gestion des comptes utilisateurs KoboToolbox (création, permissions) — l'application consomme l'API Kobo via un jeton fourni par l'utilisateur.
- Analyses statistiques avancées hors du périmètre couvert (pas de modélisation prédictive, pas de séries temporelles complexes, pas de tests d'hypothèses au-delà du χ² et des corrélations).
- Traduction de l'interface dans une langue autre que le français (l'interface est bilingue **techniquement** — codes en anglais, UI en français — mais pas multilingue au sens localisation).
- Authentification multi-utilisateurs avec rôles différenciés (le verrou d'accès actuel est un mot de passe unique partagé, pas une gestion de comptes).

---

## 4. Acteurs et utilisateurs

| Acteur | Description | Besoins principaux |
|---|---|---|
| **Concepteur d'enquête / épidémiologiste** | Rédige le questionnaire, le codifie, génère le XLSForm | Codification rapide et fiable, cohérence entre enquêtes |
| **Statisticien / analyste de données** | Analyse les données collectées | Statistiques descriptives, croisées, multivariées, export |
| **Superviseur régional / national** | Suit l'avancement de la collecte terrain | Vue synthétique reçu/cible par échelon géographique, alertes anomalies |
| **Coordinateur de projet** | Configure un nouveau projet de suivi générique | Définir un référentiel d'unités de collecte et une cible par unité |
| **Enquêteur (indirect)** | Ne se connecte pas à l'application, mais son activité est mesurée | Traçabilité de sa production via le code d'enquêteur |
| **Administrateur technique** | Déploie et maintient l'application (bureau ou web) | Configuration des variables d'environnement, sécurité, mises à jour |

---

## 5. Vue d'ensemble fonctionnelle

L'application est composée de **deux applications intégrées dans un même produit** :

```
┌───────────────────────────────────────────────────────────────────────┐
│                     SPAD PHAKTS Analyzer (Electron)                   │
│                                                                         │
│  ┌─────────────────────────────┐    ┌────────────────────────────┐   │
│  │        PHAKTS Studio          │    │        SPAD Analyzer        │   │
│  │   (Node.js / Express, front   │───▶│   (Python / Flask, front    │   │
│  │    statique HTML/JS)          │    │    Jinja2 + Plotly)          │   │
│  │                                │    │                              │   │
│  │  A. Codification               │    │  B. Analyse statistique      │   │
│  │  A. Éditeur                    │    │  C. Suivi & Complétude       │   │
│  │  A. Uploads                    │    │     nationale                │   │
│  │  A. Résultats / XLSForm        │    │  D. Projets génériques       │   │
│  │  A. Agent IA (Claude API)      │    │  E. Connecteur KoboToolbox   │   │
│  │  A. DPF (base de              │    │  F. Authentification          │   │
│  │     connaissance)              │    │                              │   │
│  └─────────────────────────────┘    └────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
```

- **PHAKTS Studio** est l'entrée par défaut de l'application de bureau ; il peut aussi tourner seul, en web statique (ex. usage hors-ligne/PWA).
- **SPAD Analyzer** est accessible depuis PHAKTS Studio (bouton « Analyse SPAD ») ou en application web autonome (c'est le cas de l'instance publique `spadapp-zeta.vercel.app`, qui héberge uniquement ce module).
- Les deux modules communiquent par transfert de fichier XLSForm (« Envoyer vers SPAD ») mais restent fonctionnellement indépendants et peuvent être déployés séparément.

---

## 6. Exigences fonctionnelles détaillées

### 6.1 Module A — PHAKTS Studio (codification)

#### A.1 Codification de questions

- **Saisie en lot** : coller une liste de questions (une par ligne) et lancer une codification automatique par le moteur PHAKTS.
- **Saisie structurée** (onglet Éditeur) : une question à la fois, avec ses modalités de réponse, en deux sous-modes (« Rédiger » carte par carte, ou « Coller & enrichir » en deux colonnes).
- **Modèles de référence** : 3 modèles pré-remplis (court, complet Q1-Q56, annoté avec sauts Kobo) pour démarrer rapidement.
- Un compteur de questions détectées s'affiche en temps réel pendant la saisie.

#### A.2 Import de fichiers (Uploads)

- Formats supportés hors ligne : TXT, CSV, PDF, DOCX, JPG, PNG, XLSX/XLS.
- Formats supportés en ligne (avec serveur API actif) : PDF, Word, images (OCR), texte, CSV, Excel.
- Taille maximale : 50 Mo par fichier.
- Détection automatique des colonnes « Question/Libellé/Intitulé » et « Modalités/Choix/Réponses » dans les fichiers Excel.
- Extraction + codification en une seule action (« Extraire & analyser »).

#### A.3 Résultats et export

- Tableau des codifications : numéro, libellé d'origine, code PHAKTS (PF/Question), modalités (PF/Modalités), skip logic, type détecté, actions (modifier/supprimer).
- Édition en ligne d'une codification (activation des champs, validation).
- Détection automatique de skip logic (« Si oui », « Si non », « En cas de », « Si autre », « Lorsque ») à partir des libellés, avec pré-condition qu'une question booléenne précède la question conditionnelle.
- Export **XLSX codifié PHAKTS** (feuille unique avec les codes).
- Export **XLSForm KoboToolbox** (3 feuilles : `survey`, `choices`, `settings`), conforme au format d'import Kobo.
- Transfert direct du résultat vers le module SPAD Analyzer.
- Ajout manuel de lignes, réinitialisation complète des résultats.
- Déploiement direct d'un XLSForm généré vers un compte KoboToolbox connecté (si connexion active).

#### A.4 Agent IA PHAKTS

- Assistant conversationnel capable de : codifier des questions, expliquer une règle de grammaire ou un choix de code, apprendre une nouvelle codification validée par l'utilisateur, proposer de nouveaux patrons PHAKTS.
- Fonctionne **en ligne** via l'API Claude (Anthropic) si une clé API est configurée.
- Fonctionne **hors ligne** en mode dégradé : classification d'intention (codifier / enseigner / expliquer une règle / discuter) combinée au moteur PHAKTS local et aux exemples déjà mémorisés dans le DPF.
- Sauvegarde automatique optionnelle des codifications validées dans le DPF (case à cocher).
- Actions rapides : nouvelle conversation, exemple guidé, question sur la grammaire, enseignement d'une nouvelle codification.

#### A.5 DPF — Dictionnaire des Propriétés Fonctionnelles

- Base de connaissance de la grammaire PHAKTS organisée en 9 (+1) sections : Types de questions, Types numériques, Conventions syntaxiques, Listes prédéfinies (éditables), Exemples du modèle de référence, Modèle Tabac Mère-Enfant, Méthode de codage en 5 étapes, Skip Logic, **Codifications apprises par l'agent IA** (section personnelle, alimentée par l'usage), et une section Extensions de grammaire éditable.
- Listes prédéfinies enrichissables par l'utilisateur (bouton ＋).
- Export XLSX du DPF complet (documentation papier / référence partagée).
- Gestion de la section « apprise » : rafraîchir, exporter, vider entièrement, ou retirer une entrée individuellement.

### 6.2 Module B — SPAD Analyzer (analyse statistique)

#### B.1 Import des données

- Import d'un fichier Excel local (`.xlsx`/`.xls`), avec détection automatique d'une éventuelle 2ᵉ feuille comme « tableau répété » (sous-questions Kobo à choix multiples).
- Import direct depuis KoboToolbox (voir module E).
- Redirection automatique vers l'aperçu des données après import.

#### B.2 Aperçu et questionnaire des variables

- Tableau récapitulatif : variable, libellé, type, modalités attendues, observations valides, manquantes, % manquant.
- Édition en ligne des libellés de question (clic → édition → Entrée pour valider), avec persistance sur l'ensemble des analyses et du rapport final.
- Export du questionnaire au format XLSX (2 feuilles : Questionnaire + Métadonnées).
- Aperçu paginé des 20 premières lignes de données brutes.

#### B.3 Analyse brute

8 sous-vues : Qualité & Profil (jauge de qualité, composition par type), Variables continues (moyenne, médiane, IC 95 %, asymétrie, aplatissement, IQR, outliers, histogramme + boxplot/violon), Catégorielles (fréquences, bar chart, donut, entropie de Shannon, indice de Herfindahl), Binaires (prévalence + IC 95 %), Manquantes (barres + heatmap), Corrélations (matrice de Pearson), Vue d'ensemble (tableau exhaustif), Tableau brut paginé.

#### B.4 Statistiques descriptives

- Sélection ciblée de variables catégorielles, continues, et groupes binaires (questions à choix multiples Kobo, détectées automatiquement).
- Par variable : tableau de fréquences avec IC 95 % de Wilson, graphique barres + courbe cumulative (Pareto), donut annoté du mode, commentaire automatique généré + zone de commentaire libre persistée en session.

#### B.5 Analyse croisée dynamique

- Interface façon tableau croisé dynamique Excel : filtres, lignes (multi-sélection hiérarchique), colonnes (multi-sélection), valeur (numérique ou comptage), agrégation (nombre, somme, moyenne, médiane, min, max, écart-type, modalités uniques), affichage en pourcentage (lignes/colonnes/total).
- Résultats : tableau croisé avec totaux marginaux, tableau de pourcentages, test du χ² de Pearson + V de Cramér + p-value (cas 2D simple), heatmap et bar chart associés.

#### B.6 Analyses multivariées

- 4 méthodes : ACP (composantes principales, variables continues), ACM (correspondances multiples, variables catégorielles), AFC (correspondances factorielles, 2 variables catégorielles), Clustering K-means (segmentation paramétrable en N groupes).
- Chaque méthode produit : plan factoriel, inerties/variances expliquées, tableau des contributions, interprétation textuelle automatique, export XLSX des résultats.

#### B.7 Analyse multi-enquête (DPF / PHAKTS)

- Import simultané de plusieurs fichiers Excel (une enquête par fichier), avec détection du nombre de variables codifiées PHAKTS par fichier.
- Matrice de couverture variable × enquête, avec 3 modes d'alignement : par radical PHAKTS (recommandé), par nom exact de colonne, ou union libre (conservation de toutes les variables, `NaN` où absent).
- Constitution d'un « panier » de comparaisons : sélection multiple de variables, ajout au panier, affichage en panneaux pliables avec tableau croisé et graphique (barres pour catégorielles, boxplot pour continues) par variable comparée.
- Le panier persiste entre les pages et peut être inclus automatiquement dans le rapport PDF/Word.

#### B.8 Carte géographique

- Détection automatique des coordonnées GPS (latitude/longitude standard ou format brut KoboToolbox `lat lon alt prec`).
- Affichage sur carte interactive : marqueurs cliquables (infobulle ID + variables sélectionnées), zoom automatique sur l'emprise des données, filtres par variable catégorielle.

#### B.9 Génération de rapport PDF / Word

- Choix du format (PDF ou Word), titre et auteur personnalisables.
- Sélection des sections à inclure : choix multiples, statistiques descriptives, tableaux croisés, analyse brute (avec sous-sélection des 8 sous-vues), multi-enquête (panier sauvegardé).
- Sélection fine des variables à inclure par catégorie.
- Sélection d'un tableau croisé spécifique (ligne + colonne) à inclure.
- Génération en un clic, téléchargement automatique du fichier `.pdf` ou `.docx`.
- Rapport structuré : table des matières, en-tête institutionnel SPAD/OMS, commentaires automatiques sur chaque tableau.

### 6.3 Module C — Suivi & Complétude nationale

Ce module est spécifique au contexte des enquêtes officielles SPAD en Côte d'Ivoire et repose sur un **référentiel organisationnel figé** (régions, districts, établissements, cibles par formulaire).

#### C.1 Référentiel organisationnel

- Référentiel région / district / établissement / enquêteur / superviseur, chargé depuis un fichier Excel de référence (`data/reference/org_unit.xlsx`), dérivé du fichier `choices` du XLSForm réellement utilisé sur le terrain.
- Tirage au sort documenté des établissements enquêtés (`tirage_etablissements.xlsx`), avec méthodologie de sélection (1 EPHR/EPHD + 4 CSU + 5 CSR par district) et comptage SIG des décès maternels par établissement.
- **Anonymisation obligatoire** : les noms d'enquêteurs/superviseurs sont remplacés par un code (ex. `D01ENQ1`) avant tout commit — le dépôt étant public. Les noms d'établissements, non considérés comme donnée personnelle, sont conservés en clair.
- Règles de cible par formulaire (7 formulaires officiels F5, F6, F7, F8, F01, F02, F07 — voir §9), avec statut « à confirmer » affiché dans l'interface tant qu'aucun document méthodologique officiel ne les valide formellement (règles actuellement déduites par recoupement empirique des totaux nationaux observés).

#### C.2 Calcul de complétude

- Rattachement des soumissions Kobo réelles (via le code d'établissement/district soumis dans le formulaire) au référentiel organisationnel, en gérant les champs Kobo groupés (`groupe/champ`).
- Calcul, pour chaque unité (établissement, district, enquêteur, superviseur) : nombre de soumissions **reçues**, **cible** attendue, **taux** de complétude, **statut** (`zero` / `en_cours` / `cible` / `verifier`).
- Mapping manuel formulaire Kobo ↔ formulaire SPAD officiel (`/completude/mapper`) puis déclenchement du calcul (`/completude/calculer`).
- Mise en cache du résultat de calcul par session (horodatage affiché).

#### C.3 Vues de restitution

- **Vue nationale** (`/completude`) : synthèse globale, formulaire par formulaire.
- **Vue par région** (`/completude/regions`).
- **Vue par district** (`/completude/districts`) — tableau triable par colonne (ex. libellé du district), chaque en-tête de colonne pilotant l'ordre d'affichage.
- **Vue par enquêteur** (`/completude/enqueteurs`) et **par superviseur** (`/completude/superviseurs`), avec sous-titre indiquant le district de rattachement.
- **Vue anomalies** (`/completude/anomalies`) : liste des unités à zéro collecte et des unités en dépassement de cible.
- **Vue graphiques** (`/completude/graphiques`) : visualisations agrégées + **tendance sur 30 jours** de la progression nationale.
- Export des résultats en **CSV** (`/completude/export.csv`) et **XLSX** (`/completude/export.xlsx`).

#### C.4 Suivi multi-formulaires en temps réel

- Page « Suivi » (`/suivi`), indépendante du référentiel régions/districts : suit plusieurs formulaires Kobo simultanément (ajout/retrait de formulaire suivi, cible libre ou détectée automatiquement si le formulaire correspond à l'un des 7 formulaires SPAD officiels).
- Sondage léger en tâche de fond (uniquement le compteur de soumissions, pas les données complètes) pour rester performant avec plusieurs formulaires suivis en parallèle.
- Synchronisation en direct via webhook Kobo (`/webhook/kobo`) et endpoints de contrôle (`/kobo/sync/start|stop|status|apply`).

### 6.4 Module D — Projets d'enquête génériques

- Généralisation du suivi de complétude à **n'importe quelle enquête KoboToolbox ou ODK**, indépendamment du référentiel SPAD figé.
- Création d'un projet (`/projets/creer`) à partir d'un fichier de référence fourni par l'utilisateur : une ligne par unité de collecte (établissement, école, village, ménage…), avec colonnes obligatoires `code` (identifiant exact de l'unité, tel que soumis dans Kobo/ODK) et `cible` (nombre de soumissions attendues), et colonnes optionnelles `nom` (libellé) et `groupe` (zone/district/région d'agrégation).
- Liaison d'un projet à un formulaire Kobo/ODK (`/projets/<id>/lier`), calcul de la complétude (`/projets/<id>/calculer`), consultation du détail (`/projets/<id>`), suppression (`/projets/<id>/supprimer`).
- Réutilise la même logique de statut (`zero` / `en_cours` / `cible` / `verifier`) que le module C, pour une cohérence visuelle et sémantique entre les deux systèmes de suivi.

### 6.5 Module E — Intégration KoboToolbox

- Connexion à une instance KoboToolbox via jeton API (token), avec choix de l'instance : `kf.kobotoolbox.org` (publique mondiale), `eu.kobotoolbox.org` (RGPD Europe), `kobo.humanitarianresponse.info` (ONU/OMS/GPEI), ou URL personnalisée.
- Récupération de la liste des formulaires (assets) de l'utilisateur connecté et chargement des données d'un formulaire choisi dans SPAD Analyzer.
- Rafraîchissement des données (nouvelles soumissions) sans recharger l'ensemble du jeu de données.
- Déploiement direct d'un XLSForm généré par PHAKTS Studio vers le compte Kobo connecté.
- Diagnostic de connexion Kobo (`/kobo/diagnostic`) pour le support technique.
- Déconnexion (`/kobo/disconnect`).

### 6.6 Module F — Authentification et accès

- Verrou d'accès par **mot de passe unique partagé** (`ANALYZER_PASSWORD`), activé uniquement si la variable d'environnement est définie — inactif par défaut en usage desktop local (où l'accès est déjà restreint au poste de l'utilisateur, `127.0.0.1`).
- Obligatoire dès que l'application est exposée publiquement (Render, Vercel), afin d'éviter un accès anonyme aux données d'enquête.
- Session Flask signée par une `SECRET_KEY` ; page de connexion dédiée (`/login`), déconnexion (`/logout`).
- Pas de gestion de comptes individuels ni de rôles différenciés à ce stade (voir §16, limites connues).

---

## 7. Exigences non fonctionnelles

| Catégorie | Exigence |
|---|---|
| **Disponibilité hors ligne** | La codification de base, l'analyse statistique et la génération de rapport doivent fonctionner sans connexion internet (seuls l'agent IA en ligne, l'OCR en ligne et la connexion KoboToolbox nécessitent une connexion). |
| **Performance** | Codification d'un lot de 50 questions en moins de 10 secondes ; import et aperçu d'un fichier Excel de quelques milliers de lignes en moins de quelques secondes. |
| **Compatibilité** | Application de bureau : macOS 12+ (Intel/Apple Silicon), Windows 10/11 (x64). Application web : navigateurs modernes (Chrome, Edge, Firefox, Safari récents). |
| **Ressources minimales** | 4 Go de RAM (8 Go recommandés), 1,5 Go d'espace disque libre. |
| **Ergonomie** | Interface entièrement en français ; 3 thèmes d'apparence (clair / mixte / sombre), préférence mémorisée localement ; retour visuel systématique sur les actions longues (barres de progression, animations de chargement). |
| **Reproductibilité** | Deux personnes codifiant la même question doivent obtenir le même code PHAKTS, grâce à la grammaire formelle et au DPF partagé. |
| **Robustesse réseau** | Rate limiting sur l'API PHAKTS Studio (par défaut 50 requêtes / 15 min) ; gestion des erreurs KoboToolbox (timeout, jeton invalide) sans interruption de l'application. |
| **Portabilité des données** | Toute production (codifications, questionnaires, résultats d'analyse, rapports) exportable en formats standards (XLSX, CSV, PDF, DOCX) ne nécessitant pas l'application pour être relue. |
| **Traçabilité** | Chaque calcul de complétude est horodaté et affiché à l'utilisateur ; le DPF conserve l'origine des codifications apprises. |

---

## 8. Architecture technique

### 8.1 Vue technique globale

| Composant | Rôle | Stack |
|---|---|---|
| **PHAKTS Studio (front)** | Interface de codification | HTML/CSS/JS statique (`public/PHAKTS·STUDIO.html`), PWA (`manifest.webmanifest`, `service-worker.js`) |
| **PHAKTS Studio (API)** | Codification, extraction de fichiers, agent IA, génération XLSForm | Node.js / Express (`api/server.js`, `api/grammar.js`, `api/xlsform.js`) |
| **SPAD Analyzer** | Analyse statistique, suivi de complétude | Python / Flask (`analyzer/app.py`, ~2 800 lignes), moteur de rendu Jinja2 + Plotly |
| **Emballage desktop** | Distribution bureau macOS/Windows | Electron (`electron-main.js`, `preload.js`), `electron-builder` |

### 8.2 Dépendances clés

- **Node.js** (≥ 18) : `express`, `@anthropic-ai/sdk` (agent IA), `exceljs` (génération XLSX), `multer` (upload), `mammoth` (extraction Word), `pdf-parse` / `pdfjs-dist` (extraction PDF), `ocrad.js` (OCR local), `helmet` + `express-rate-limit` (sécurité), `cors`.
- **Python** : `flask`, `pandas`, `numpy`, `scipy`, `scikit-learn` (ACP/ACM/AFC/K-means), `plotly` + `kaleido` (graphiques), `openpyxl` / `xlsxwriter` (Excel), `reportlab` (PDF), `python-docx` (Word), `gunicorn` (serveur de production).

### 8.3 Organisation des modules Python (`analyzer/modules/`)

| Module | Responsabilité |
|---|---|
| `data_loader.py` | Chargement et normalisation des fichiers Excel / exports Kobo |
| `completeness.py` | Moteur de calcul reçu/cible/taux/statut |
| `reference_data.py` | Référentiel organisationnel (régions/districts/établissements/cibles) |
| `descriptive.py` | Statistiques descriptives |
| `crosstabs.py` | Tableaux croisés dynamiques + tests statistiques |
| `multivariate.py` | ACP / ACM / AFC / Clustering |
| `multi_survey.py` | Comparaison multi-enquête (alignement PHAKTS) |
| `raw_analysis.py` | Les 8 sous-vues de l'analyse brute |
| `geo_analysis.py` | Détection et traitement des coordonnées GPS |
| `report_generator.py` | Génération PDF/Word |
| `kobo_connector.py` | Client API KoboToolbox (auth, assets, données) |
| `kobo_sync.py` | Synchronisation en direct d'un formulaire en cours d'analyse |
| `kobo_track.py` | Suivi en tâche de fond de plusieurs formulaires (page Suivi) |
| `projets.py` | Projets d'enquête génériques hors référentiel SPAD |
| `comments.py` | Génération de commentaires automatiques sur les tableaux |
| `tendance.py` | Calcul de tendance temporelle (complétude sur 30 jours) |

### 8.4 Flux de données type

```
Questionnaire brut
   │  (PHAKTS Studio : Codification / Éditeur / Uploads / Agent IA)
   ▼
Codification PHAKTS  ──export──▶ XLSX codifié
   │
   ▼
XLSForm KoboToolbox  ──déploiement──▶ Formulaire Kobo actif
   │
   ▼
Soumissions terrain (ODK Collect / Kobo Collect)
   │
   ▼
KoboToolbox (stockage cloud)
   │  (connecteur Kobo : chargement direct ou export manuel Excel)
   ▼
SPAD Analyzer ─┬─▶ Analyse statistique ─▶ Rapport PDF/Word
               └─▶ Rattachement au référentiel ─▶ Suivi de complétude (région/district/enquêteur/superviseur)
```

---

## 9. Modèle de données et référentiel

### 9.1 Référentiel organisationnel SPAD (Côte d'Ivoire, phase pilote 2026)

- **Hiérarchie** : Région → District → Établissement (avec enquêteur(s) et superviseur(s) rattachés).
- **120 établissements** tirés au sort selon la méthodologie : 1 EPHR/EPHD + 4 CSU + 5 CSR par district (graine aléatoire fixe, `seed=20260713`), avec comptage SIG des décès maternels par établissement.
- **7 formulaires officiels suivis** :

| Code | Objet | Règle de cible | Total national attendu |
|---|---|---|---|
| F5 | Tabac — Femmes enceintes/allaitantes | 15 par établissement, fixe | 1 800 |
| F6 | Tabac — Personnel de santé (CAP) | 3 si EPH/CSU, 2 si CSR-DM, 1 si CSR-D | ≈ 271–273 |
| F7 | Vaccination — Ménages | 15 par établissement, fixe | 1 800 |
| F8 | Vaccination — Établissement | 1 par établissement, fixe | 120 |
| F01 | Revue des décès maternels (RDM) — District | 1 par district, fixe | 12 |
| F02 | RDM — Établissement | 1 par établissement, fixe (une fiche par établissement, indépendamment du nombre de décès SIG) | 120 |
| F07 | RDM — Grille | Somme des décès maternels notifiés au SIG pour les établissements du district (plancher, un dépassement est normal) | ≈ 187–188 |

> Ces règles de cible sont **des reconstructions déduites empiriquement** par recoupement des totaux déjà observés sur l'instance en production, faute de document méthodologique officiel séparé. Elles sont marquées « à confirmer » dans l'interface tant qu'aucune source primaire ne les valide formellement (voir §16).

### 9.2 Clés de rattachement des soumissions

Chaque formulaire identifie son district/établissement via un champ Kobo contenant un **code** (pas un libellé), utilisé comme clé de jointure avec le référentiel :

| Formulaire | Champ établissement | Champ district |
|---|---|---|
| F5 / F6 / F7 / F8 | `Etablissement_Sanitaire__X` | `District_Sanitaire__X` |
| F01 | — | `F01_01a__X` |
| F02 | `F02_01__E` | `F02_00_district__X` |
| F07 | `RDM_NOT03__X` | `RDM_NOT02__X` |

### 9.3 Statuts de complétude

| Statut | Signification |
|---|---|
| `zero` | Aucune soumission reçue pour une unité ayant une cible |
| `en_cours` | Soumissions reçues, cible non encore atteinte |
| `cible` | Cible atteinte exactement |
| `verifier` | Dépassement de cible (anomalie potentielle à vérifier) |

### 9.4 Référentiel « projets génériques »

Structure minimale, indépendante du référentiel SPAD : une ligne par unité de collecte avec `code` (identifiant exact, obligatoire), `cible` (nombre attendu, obligatoire), `nom` (libellé, optionnel) et `groupe` (zone d'agrégation, optionnel).

---

## 10. Intégrations et API externes

| Intégration | Usage | Mode |
|---|---|---|
| **API Anthropic (Claude)** | Agent IA de codification conversationnelle, OCR/extraction avancée en ligne | Optionnelle — clé API à configurer dans `.env` (`ANTHROPIC_API_KEY`) ; l'application reste fonctionnelle sans (mode dégradé local) |
| **API KoboToolbox** | Liste des formulaires, chargement/rafraîchissement des soumissions, déploiement de XLSForm, webhook de synchronisation en direct | Optionnelle — jeton API fourni par l'utilisateur, 3 instances pré-configurées + URL personnalisée |

---

## 11. Sécurité et protection des données

- **Aucune donnée personnelle d'enquêteur/superviseur** n'est stockée en clair dans le dépôt de code (remplacée par un code alphanumérique) — le dépôt GitHub étant public.
- **Clés de session** (`SECRET_KEY`) : valeur par défaut codée en dur acceptable uniquement en usage desktop local (accès déjà restreint au système d'exploitation) ; **valeur aléatoire obligatoire** dès exposition publique, faute de quoi les sessions (donc l'authentification) peuvent être falsifiées.
- **Mot de passe d'accès** (`ANALYZER_PASSWORD`) : recommandé fortement, mais optionnel — l'application ne doit **jamais** être déployée sur une URL publique sans cette variable définie.
- **CORS** : liste blanche d'origines autorisées configurable (`ALLOWED_ORIGINS`), pas de `*` en production.
- **Rate limiting** sur l'API Node (`RATE_LIMIT_MAX`, 50 requêtes / 15 min par défaut) et jeton d'authentification API optionnel (`API_TOKEN`).
- **Limite de taille de fichier** : 50 Mo par upload (protection contre les abus).
- **Jetons KoboToolbox** : stockés en session serveur (Flask), jamais persistés en clair sur disque de façon durable.

---

## 12. Environnements et déploiement

| Environnement | Description | Statut |
|---|---|---|
| **Application de bureau (Electron)** | Package `.dmg` (macOS, arm64) et installeur `.exe` NSIS (Windows), embarque PHAKTS Studio + SPAD Analyzer (avec Python embarqué) | Documenté (`BUILD_WINDOWS.md`, manuel utilisateur) |
| **SPAD Analyzer sur Render** | Déploiement web du seul module Flask (`render.yaml`, plan gratuit, veille après 15 min d'inactivité, ~60 s de réveil) | Documenté (`DEPLOIEMENT_RENDER.md`) |
| **SPAD Analyzer sur Vercel** | Instance actuellement en production, référencée par son URL (`spadapp-zeta.vercel.app`) comme source de vérité pour les règles de cible du référentiel | Utilisée en production, non documentée dans le dépôt (pas de `vercel.json` présent) |
| **PHAKTS Studio en web statique / PWA** | Utilisable hors ligne via `manifest.webmanifest` + `service-worker.js` | Documenté |

**Recommandation** : documenter formellement la configuration Vercel (fichier `vercel.json` ou procédure équivalente à `DEPLOIEMENT_RENDER.md`) pour fiabiliser et reproduire le déploiement de production actuel.

---

## 13. Livrables

- Code source (dépôt GitHub `kjmb2006-cmyk/spad-phakts-analyzer`).
- Application de bureau installable (macOS `.dmg`, Windows `.exe`).
- Application web déployée (SPAD Analyzer).
- Manuel utilisateur complet (`MANUEL_UTILISATEUR.md`, 11 sections).
- Documentation de déploiement (`DEPLOIEMENT_RENDER.md`, `BUILD_WINDOWS.md`, `GITHUB_SETUP.md`).
- Le présent cahier des charges.
- Export DPF (documentation de la grammaire PHAKTS, format XLSX).

---

## 14. Historique des versions et jalons

| Jalon | Contenu |
|---|---|
| **v1.0.0** (juin 2026) | Codification PHAKTS hors ligne/en ligne, agent IA avec apprentissage DPF, génération XLSForm, SPAD Analyzer complet (descriptives, croisée dynamique, multivariées, multi-enquête, cartographie), rapports PDF/Word, build multi-OS |
| **Authentification** | Verrou par mot de passe partagé + configuration de déploiement Render |
| **Synchronisation Kobo** | Actualisation automatique en tâche de fond (polling) |
| **Suivi multi-formulaires** | Nouvelle page « Suivi » — suivi temps réel de plusieurs formulaires Kobo |
| **Référentiel organisationnel SPAD** | Régions/districts/établissements/cibles (phase pilote 2026) |
| **Moteur de complétude** | Rattachement soumissions ↔ référentiel |
| **Vue de complétude nationale** | Nouvelle page « Complétude » |
| **Vues région et district** | Déclinaison géographique de la complétude |
| **Vues enquêteur et superviseur** | Déclinaison par acteur terrain |
| **Page anomalies** | Détection zéro-collecte / dépassement de cible |
| **Projets d'enquête génériques** | Extension du suivi de complétude à toute enquête Kobo/ODK |
| **Graphiques + export + tendance 30 jours** | Dernière évolution en date — visualisations agrégées et tendance temporelle de la complétude nationale |

---

## 15. Critères de recette

| # | Critère | Méthode de vérification |
|---|---|---|
| R1 | Une liste de 50 questions du modèle de référence est codifiée sans erreur bloquante | Test manuel avec le modèle « complet Q1-Q56 » |
| R2 | Le XLSForm généré s'importe sans erreur dans une instance KoboToolbox | Import réel sur `kf.kobotoolbox.org` ou instance de test |
| R3 | L'import d'un export Kobo réel (2 feuilles) produit un aperçu correct des variables et de leurs types | Test avec un export réel anonymisé |
| R4 | Le rapport PDF et le rapport Word se génèrent et s'ouvrent sans erreur | Génération + ouverture dans Adobe Reader / Word / LibreOffice |
| R5 | Le calcul de complétude reproduit les totaux nationaux déjà validés (1800 / 1800 / 120 / 12 / 120 pour F5/F7/F8/F01/F02) | Comparaison aux totaux exacts connus (voir §9.1) |
| R6 | Les vues région/district/enquêteur/superviseur sont cohérentes entre elles (somme des sous-totaux = total national) | Contrôle croisé des exports CSV/XLSX |
| R7 | L'application refuse l'accès sans mot de passe lorsque `ANALYZER_PASSWORD` est défini | Test de connexion sans authentification sur un déploiement public |
| R8 | La codification et l'analyse restent utilisables sans connexion internet | Test en mode avion sur l'application de bureau |

---

## 16. Risques, limites et hypothèses ouvertes

- **Règles de cible non officiellement validées** : les règles de cible des formulaires F5–F07 (§9.1) sont des reconstructions empiriques, faute de document méthodologique séparé. Un écart a déjà été identifié et documenté pour F6 (271 calculé vs. ≈ 273 observé). **Action recommandée** : faire valider ces règles par le porteur méthodologique de l'enquête et lever la mention « à confirmer » dans l'UI une fois fait.
- **Champs Kobo groupés non vérifiés en conditions réelles** : la gestion des préfixes `groupe/champ` dans `completeness.py` a été écrite par anticipation, aucune soumission réelle groupée n'ayant encore été observée pour confirmer le comportement exact.
- **Authentification à un seul niveau** : un mot de passe partagé unique ne permet ni traçabilité par utilisateur connecté, ni droits différenciés (lecture seule vs. administration). À envisager si le nombre d'utilisateurs de la version web augmente.
- **Déploiement Vercel non documenté dans le dépôt** : contrairement à Render, aucune configuration versionnée (`vercel.json`) ne décrit l'instance de production actuelle — risque de perte de configuration en cas de changement d'opérateur.
- **Dépendance à un référentiel figé** : toute évolution du découpage administratif (nouveaux districts/établissements) ou du nombre de formulaires officiels nécessite une mise à jour manuelle du référentiel (`org_unit.xlsx`).
- **Palier gratuit Render** : mise en veille après 15 minutes d'inactivité (~60 s de réveil), acceptable pour un usage ponctuel mais pas pour un accès garanti en continu.
- **Absence de tests automatisés end-to-end sur l'interface web** : les fichiers `test_*.py` présents couvrent l'analyse et la complétude côté serveur, mais aucun test d'interface (front) n'est identifié dans le dépôt.

---

## 17. Glossaire

| Terme | Définition |
|---|---|
| **PHAKTS** | *Public Health Assessment & Knowledge Taxonomy & Grammar Rules* — grammaire formelle de codification des questions d'enquête en santé publique |
| **DPF** | Dictionnaire des Propriétés Fonctionnelles — base de connaissance centralisant les codifications PHAKTS validées |
| **XLSForm** | Format Excel standard utilisé par KoboToolbox/ODK pour définir un formulaire de collecte (feuilles `survey`, `choices`, `settings`) |
| **RDM** | Revue des Décès Maternels — dispositif de surveillance épidémiologique |
| **SIG** | Système d'Information Sanitaire — source des décomptes officiels de décès maternels |
| **CAP** | Connaissances, Attitudes, Pratiques — type d'enquête (ex. F6, tabac chez le personnel de santé) |
| **EPHR / EPHD** | Établissement Public Hospitalier Régional / Départemental |
| **CSU / CSR** | Centre de Santé Urbain / Rural |
| **Skip Logic** | Règle de branchement conditionnel entre questions (« si oui → afficher la question suivante ») |
| **ACP / ACM / AFC** | Analyse en Composantes Principales / des Correspondances Multiples / Factorielle des Correspondances |

---

## 18. Annexe — Référence rapide de la grammaire PHAKTS

**Structure générale** : `Radical__TYPE!contrainte`

| Code | Description | Exemple |
|---|---|---|
| `__B!boolean` | Booléen Oui/Non | `Vaccination__B!boolean` |
| `__X!1*1Liste_` | Choix unique | `Sexe__X!1*1Sexe_` |
| `__X!1*Liste_` | Choix multiples | `Symptomes__X!1*Symptomes_` |
| `__SRC!1*Source_` | Source d'information | `Info_Source__SRC!1*Source_Info_Sante_` |
| `__Z` | Texte libre | `Commentaire__Z` |
| `__A!YYYY/MM/DD` | Date ISO | `Date_Naissance__A!YYYY/MM/DD` |
| `__1Y!Y` | Entier années | `Age__1Y!0<N<120` |
| `__1M!M` | Entier mois | `Grossesse__1M!0<N<24` |
| `__2K` | Réel kg | `Poids__2K!0<R<300` |
| `__2T` | Réel °C | `Temperature__2T!35<R<42` |

**Séparateurs de listes** : virgule `,` = choix exclusifs (select_one) ; pipe `|` = choix cumulables (select_multiple) ; `0` en fin de liste = négation/Autre/Aucun.

**Skip Logic** : `Lexia__B = Oui -> @Cible` (si Oui, afficher la cible) ; `!Lexia__B -> @Cible` (négation) ; règles multiples séparées par `;`.

*(Référence complète : DPF, section H, accessible dans l'onglet Dictionnaire des Propriétés Fonctionnelles de l'application.)*

---

*Document généré à partir de l'analyse du code source et de l'application en production. À faire relire et valider par l'auteur du produit (Dr Jean-Marc Bertrand KORANDJI) avant diffusion officielle.*
