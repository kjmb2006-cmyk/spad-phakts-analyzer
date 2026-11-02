# SPAD PHAKTS Analyzer — Manuel d'utilisation

**Version 1.0 — 2026**
**Auteur :** Dr Jean-Marc Bertrand KORANDJI / SPAD (WHO)
**Équipe SPAD :** Dr Wognin V., Dr M'Bra V. D. P., Dr KORANDJI J. M. B., Mlle Dieng S., Mme Aman A. Sarah

---

## Table des matières

1. [Présentation](#1-présentation)
2. [Installation](#2-installation)
3. [Premier lancement](#3-premier-lancement)
4. [Vue d'ensemble de l'interface](#4-vue-densemble-de-linterface)
5. [PHAKTS Studio — Codification des questionnaires](#5-phakts-studio--codification-des-questionnaires)
   - 5.1 [Onglet Codification](#51-onglet-codification)
   - 5.2 [Onglet Éditeur](#52-onglet-éditeur)
   - 5.3 [Onglet Uploads](#53-onglet-uploads)
   - 5.4 [Onglet Résultats](#54-onglet-résultats)
   - 5.5 [Onglet Agent IA PHAKTS](#55-onglet-agent-ia-phakts)
   - 5.6 [Onglet DPF — Dictionnaire des Propriétés Fonctionnelles](#56-onglet-dpf--dictionnaire-des-propriétés-fonctionnelles)
   - 5.7 [Onglet Correction DPF](#57-onglet-correction-dpf)
6. [SPAD Analyzer — Analyse statistique](#6-spad-analyzer--analyse-statistique)
   - 6.1 [Importer les données](#61-importer-les-données)
   - 6.2 [Aperçu et questionnaire des variables](#62-aperçu-et-questionnaire-des-variables)
   - 6.3 [Diagnostic des données](#63-diagnostic-des-données)
   - 6.4 [Statistiques descriptives](#64-statistiques-descriptives)
   - 6.5 [Analyse Croisée Dynamique](#65-analyse-croisée-dynamique)
   - 6.6 [Analyses multivariées](#66-analyses-multivariées)
   - 6.7 [Analyse multi-enquête (DPF / PHAKTS)](#67-analyse-multi-enquête-dpf--phakts)
   - 6.8 [Carte géographique](#68-carte-géographique)
   - 6.9 [Génération du rapport PDF / Word](#69-génération-du-rapport-pdf--word)
7. [KoboToolbox — Connexion directe](#7-kobotoolbox--connexion-directe)
8. [Personnalisation de l'apparence](#8-personnalisation-de-lapparence)
9. [Grammaire PHAKTS — Référence rapide](#9-grammaire-phakts--référence-rapide)
10. [Dépannage](#10-dépannage)
11. [Crédits & contact](#11-crédits--contact)

---

## 1. Présentation

**SPAD PHAKTS Analyzer** est une suite logicielle dédiée à la **santé publique**.
Elle réunit deux modules complémentaires dans une seule application :

- **PHAKTS Studio** — codification automatique des questions d'enquête selon
  la grammaire PHAKTS et génération de **XLSForms KoboToolbox** prêts à déployer.
- **SPAD Analyzer** — analyse statistique complète des données collectées
  (tris à plat, tableaux croisés dynamiques, analyses multivariées, comparaisons
  multi-enquêtes, cartographie, rapports PDF/Word automatiques).

PHAKTS (*Public Health Assessment & Knowledge Taxonomy Spelling & Grammar Rules*) est
une **grammaire formelle** qui standardise la codification des questions
d'enquête en santé publique. Le **DPF — Dictionnaire des Propriétés
Fonctionnelles** centralise toutes les codifications validées.

### À qui s'adresse cette application ?

- Épidémiologistes, médecins de santé publique, analystes de données sanitaires
- Équipes terrain de l'OMS / WHO et partenaires
- Étudiants en santé publique et statistique appliquée
- Toute personne devant codifier un questionnaire ou analyser des données
  d'enquête sanitaire

### Principes fondateurs

- **Hors ligne par défaut** — vous pouvez codifier, analyser et générer des
  rapports sans aucune connexion internet
- **Bilingue technique** — codes PHAKTS en anglais (universels), interface en
  français
- **Reproductible** — la grammaire formelle et le DPF garantissent que deux
  équipes différentes codifient la même question de la même façon

---

## 2. Installation

### 2.1 Configuration minimale requise

| Composant | macOS | Windows |
|---|---|---|
| Système | macOS 12 Monterey ou plus récent | Windows 10 (64 bits) ou Windows 11 |
| Processeur | Intel ou Apple Silicon (M1/M2/M3/M4) | x64 (Intel/AMD) |
| RAM | 4 Go minimum, 8 Go recommandés | 4 Go minimum, 8 Go recommandés |
| Espace disque | 1,5 Go libre | 1,5 Go libre |
| Internet | Optionnel (pour l'Agent IA en ligne) | Optionnel (pour l'Agent IA en ligne) |

### 2.2 Installation sur macOS

1. Téléchargez le fichier **`SPAD PHAKTS Analyzer-1.0.0-arm64.dmg`** depuis la
   page de release ou via le canal de distribution interne SPAD.
2. **Double-cliquez** sur le DMG.
3. Une fenêtre Finder s'ouvre — **glissez l'icône SPAD PHAKTS Analyzer** dans le
   dossier **Applications**.
4. Allez dans **Applications**, **clic droit** sur SPAD PHAKTS Analyzer →
   **Ouvrir**.
5. Au premier lancement, macOS affiche un avertissement *« cette application
   provient d'un développeur non identifié »*. Cliquez **Ouvrir** (l'app n'est
   pas signée Apple par défaut — c'est normal).

### 2.3 Installation sur Windows

1. Téléchargez **`SPAD PHAKTS Analyzer Setup 1.0.0.exe`**.
2. **Double-cliquez** sur l'installeur.
3. Si Windows SmartScreen affiche *« Windows a protégé votre ordinateur »* :
   - Cliquez **Informations complémentaires**
   - Puis **Exécuter quand même**
4. L'assistant d'installation NSIS démarre :
   - Choisissez le dossier d'installation (par défaut :
     `C:\Program Files\SPAD PHAKTS Analyzer`)
   - Cochez **Créer un raccourci sur le bureau** ✓
   - Cochez **Créer un raccourci dans le menu Démarrer** ✓
   - Cliquez **Installer**
5. ~30 secondes plus tard, l'application est installée. Lancez-la depuis le
   raccourci bureau ou le menu Démarrer.

### 2.4 Désinstallation

**macOS** : glissez l'icône depuis le dossier Applications vers la corbeille.

**Windows** : Panneau de configuration → Programmes → SPAD PHAKTS Analyzer →
Désinstaller. Ou utilisez le raccourci *Désinstaller SPAD PHAKTS Analyzer*
créé dans le menu Démarrer.

---

## 3. Premier lancement

Lorsque vous lancez l'application pour la première fois :

1. Une fenêtre noire/sombre s'ouvre — c'est **PHAKTS Studio**.
2. En haut à droite, vérifiez le **statut du serveur API** :
   - 🟢 **PHAKTS·STUDIO API** vert = serveur de codification connecté
   - 🔴 **API hors ligne** = mode local uniquement (toujours fonctionnel pour
     la codification de base)
3. Dans l'en-tête, vous voyez :
   - **Sélecteur d'apparence** (☀️ Clair / ◐ Mixte / 🌙 Sombre)
   - **Champ « Serveur API »** (modifiable si besoin)
   - **Champ « Formulaire »** (donnez un nom à votre projet)
   - Bouton **🗎 Nouveau** (pour repartir d'un formulaire vide)

Si l'application détecte une **session précédente**, un bandeau bleu apparaît
en haut : *« Session précédente détectée — N codifications enregistrées. »*
- **↶ Restaurer** : reprend votre travail
- **✕ Effacer** : démarre une session neuve

---

## 4. Vue d'ensemble de l'interface

PHAKTS Studio est organisée en **7 onglets** :

| Onglet | Rôle |
|---|---|
| ▶ **Codification** | Coller des questions et obtenir leur codification PHAKTS automatique |
| ✎ **Éditeur** | Rédiger ou enrichir des questions une par une avec leurs modalités |
| ⬆ **Uploads** | Importer un fichier (PDF, Word, Excel, image scannée…) pour extraction automatique |
| ⊞ **Résultats** | Visualiser, modifier, exporter les codifications produites |
| 🛠 **Correction DPF** | Vérifier un questionnaire codifié ou un XLSForm contre la grammaire PHAKTS et le DPF, et le corriger |
| 🤖 **Agent IA PHAKTS** | Dialoguer avec l'IA experte en codification |
| ⊘ **Dictionnaire des Propriétés Fonctionnelles** | Référence de la grammaire PHAKTS + codifications apprises |
| 📊 **Analyse SPAD** | Bascule vers le module d'analyse statistique des données |

---

## 5. PHAKTS Studio — Codification des questionnaires

### 5.1 Onglet Codification

C'est l'onglet par défaut au démarrage. C'est ici que vous **transformez vos
questions brutes en codes PHAKTS**.

**Procédure :**

1. **Donnez un nom à votre formulaire** dans le champ en haut à droite
   (ex. *« Enquête CAP Tabac Femmes Enceintes »*).
2. **Collez vos questions** dans la grande zone de texte, **une par ligne** :
   ```
   Quel est votre âge ?
   Êtes-vous enceinte ?
   Si oui, depuis combien de mois ?
   Quel est votre statut matrimonial ?
   Fumez-vous ?
   ```
3. Le compteur en bas à droite affiche *« N questions détectées »*.
4. Cliquez sur **CODIFIER AVEC PHAKTS** (bouton bleu).
5. Une animation *« CODIFICATION PHAKTS EN COURS… »* s'affiche pendant 2-10 sec.
6. L'application bascule automatiquement sur l'onglet **Résultats**.

**Mode de référence** (utile pour démarrer) : la liste déroulante propose 3
modèles types — *court*, *complet (Q1-Q56)*, *annoté avec sauts Kobo*. Cliquez
sur **Charger le modèle** pour pré-remplir la zone, ou sur **Coder et exporter
les 2 fichiers** pour un cycle complet en un clic.

### 5.2 Onglet Éditeur

Pour une saisie **structurée question-par-question avec leurs modalités** :

Deux sous-modes :

- **Rédiger** (par défaut) : une carte par question avec champ texte + bouton
  *+ Modalités* pour saisir les options de réponse.
- **Coller & enrichir** : 2 colonnes côte à côte. À gauche, vous collez vos
  questions ; à droite, en face de chaque question, vous saisissez ses
  modalités séparées par virgule ou pipe.

Cliquez **CODIFIER** quand vous avez fini.

### 5.3 Onglet Uploads

Pour **extraire automatiquement des questions** depuis un fichier existant.

**Formats supportés :**
- Hors ligne : **TXT, CSV, PDF, DOCX, JPG, PNG, XLSX/XLS**
- En ligne (avec serveur API) : PDF, Word, images, texte, CSV, Excel
- Taille maximale : 50 MB par fichier

**Pour les fichiers Excel** : l'application détecte automatiquement la colonne
*« Question »* / *« Libellé »* / *« Intitulé »* et la colonne
*« Modalités »* / *« Choix »* / *« Réponses »* si elles existent. Sinon elle
utilise la 1ʳᵉ colonne.

**Procédure :**

1. **Glissez-déposez** votre fichier dans la zone pointillée, OU cliquez
   **Sélectionner des fichiers**.
2. L'upload démarre, la barre de progression avance.
3. Une carte du fichier apparaît avec les boutons :
   - 🔍 **Extraire & analyser** : extraction automatique et codification
   - **Copier ID** : pour usage avancé
   - **✕** : supprimer

### 5.4 Onglet Résultats

Affiche le **tableau des codifications** produit par l'un des 3 onglets
précédents. Colonnes :

| Colonne | Description |
|---|---|
| **#** | Numéro d'ordre |
| **Libellé** | Question d'origine |
| **PF/Question (Code PHAKTS)** | Code généré, ex. `Age__1Y!0<N<120` |
| **PF/Modalités** | Modalités de réponse |
| **Skip Logic** | Règle de branchement conditionnel (« Si oui → … ») |
| **Type** | Type détecté (Boolean, Select_one, etc.) |
| **Actions** | ✎ Modifier · ✕ Supprimer |

**Barre d'actions (en haut) :**

- **📗 XLSX Codifié (PHAKTS)** : export Excel avec les codes PHAKTS
- **📘 XLSForm (KoboToolbox)** : génère le XLSForm prêt à déployer dans Kobo
  (3 feuilles : survey, choices, settings)
- **📊 Envoyer vers SPAD** : transmet le XLSForm à l'onglet Analyse SPAD
- **+ Ajouter** : ajoute manuellement une codification
- **✓ Skip Logic auto** : détecte automatiquement les Skip Logic (« Si oui »,
  « Si non », « En cas de », « Si autre »…) à partir des libellés
- **🎓 Mémoriser** : enregistre toutes les codifications validées dans le DPF
- **🗑 Réinitialiser** : efface tous les résultats (et le DPF mémorisé)

**Modifier une ligne** : cliquez ✎ pour activer les champs édition, modifiez,
puis cliquez ✓ pour sauvegarder.

### 5.5 Onglet Agent IA PHAKTS

🤖 L'**Agent IA Expert PHAKTS** est un assistant conversationnel qui peut :
- **Codifier** une ou plusieurs questions
- **Expliquer** une règle de grammaire ou un choix de code
- **Apprendre** une nouvelle codification que vous validez (sauvegardée dans
  le DPF)
- **Proposer activement** de nouveaux patrons PHAKTS (radicaux, listes
  contrôlées)

**Interface :**

- Fenêtre de discussion centrale (messages historisés)
- Zone de saisie en bas
- Cases à cocher :
  - ☑ **Sauvegarder automatiquement dans le DPF** (recommandé)
- Boutons :
  - **↺ Nouvelle conversation** : repart à zéro
  - **💡 Exemple : codifier 3 questions**
  - **❓ Question sur la grammaire**
  - **🎓 Enseigner une nouvelle codification**

**Exemples d'utilisation :**

```
> Codifie ces questions :
> 1. Quel est l'âge du patient ?
> 2. Le patient est-il vacciné contre la rougeole ?
> 3. Quelle est sa zone de résidence ? (Urbaine / Rurale / Périurbaine)
```

```
> Quelle est la différence entre __X!1*1Liste_ et __X!1*Liste_ ?
```

```
> Je veux ajouter une nouvelle codification au DPF :
> Libellé : « Statut de la couverture sanitaire universelle »
> Code : Couverture_Sanitaire_Universelle__X!1*1CSU_Statut_
> Modalités : CSU_Statut_=[Couvert,Non_Couvert,En_Cours,Inconnu]
```

L'agent répond en prose puis émet un bloc JSON `items` qui enrichit
automatiquement le DPF si la case est cochée.

**Mode hors ligne** : l'Agent reste utilisable sans serveur API — il classifie
votre intention (codify / teach / rule / chat) et utilise le moteur PHAKTS
local + les exemples mémorisés du DPF.

### 5.6 Onglet DPF — Dictionnaire des Propriétés Fonctionnelles

⊘ Le **DPF** est la **base de connaissance vivante** de la grammaire PHAKTS.
Il regroupe 9 sections :

| Section | Contenu |
|---|---|
| A | Types de Questions (`__B`, `__X`, `__SRC`, `__Z`, `__A`) |
| B | Types Numériques (`__1Y`, `__1M`, `__1W`, `__1D`, `__1H`, `__2K`, `__2T`, `__2L`, `__2S`) |
| C | Conventions Syntaxiques (Snake_Case, `__`, `!`, `,`, `|`, `_=[…]`, `0`) |
| D | Listes Prédéfinies (Trilean, Niveau, Motivation, Dangereux, Statut_Matrimonial, Source_Info_Sante…) — éditables avec ＋ |
| E | Exemples du Modèle de Référence (~50 questions standard) |
| F | Modèle Tabac Mère-Enfant (cas d'usage complet) |
| G | Méthode de Codage en 5 Étapes |
| H | Skip Logic (Branchement Conditionnel) |
| **I** | **Codifications apprises par l'Agent IA** *(nouveau)* |

**Section I — votre DPF personnel :**

Tout ce que vous validez (via *Mémoriser* dans l'onglet Résultats ou
auto-sauvegarde de l'Agent IA) apparaît ici, avec :
- ↻ **Rafraîchir** : recharger la liste
- ⬇ **Exporter XLSX** : télécharger le DPF en Excel
- **✕ Vider** : supprimer toutes les codifications apprises
- **✕** par ligne : retirer une codification spécifique

**Bouton « Télécharger DPF »** (en haut à droite) : export complet du DPF
(sections A-H + I) au format XLSX, utilisable comme documentation papier ou
référence partagée.

### 5.7 Onglet Correction DPF

Cet onglet **vérifie qu'un questionnaire déjà codifié respecte la grammaire
PHAKTS et le DPF**, repère chaque codification qui ne les respecte pas, et
propose la correction juste.

**Fichiers acceptés** (`.xlsx`) — déposez-le dans la zone prévue :

- un **questionnaire codifié** : colonnes *Libellé*, *PF/Question*,
  *PF/Modalités*, *Skip Logic* (toutes les feuilles sont vérifiées) ;
- un **XLSForm KoboToolbox** : feuilles *survey* et *choices*. Le type du champ
  (`integer`, `select_one`, `text`…) sert à vérifier l'affixe du nom ;
- une **liste de libellés à codifier** : une colonne *Libellé* (ou *Question*), avec ou
  sans colonne *Modalités*. Les libellés sans code d'un questionnaire codifié sont
  traités de la même façon. Deux boutons proposent, pour chaque libellé, un code PHAKTS
  et ses modalités :
  - **✨ Codifier (hors-ligne)** — le codifieur local du Studio, sans appel réseau :
    gratuit, instantané, reproductible, mais plus sommaire (une question fermée mal
    tournée peut ressortir en booléen par défaut) ;
  - **🤖 Codifier avec l'IA PHAKTS** — le même modèle que l'onglet Codification
    (`/api/codify`) : reconnaît mieux « Pourquoi… / Si oui, quel… », propose les listes
    du DPF et, quand le libellé le dit explicitement, une Skip Logic. Nécessite le
    serveur API (bouton grisé sinon) et **consomme des appels payants** — jamais
    déclenché automatiquement, uniquement sur ce clic. Les deux boutons peuvent être
    utilisés l'un après l'autre sur le même fichier : l'IA peut rattraper les
    libellés où la version hors-ligne a mal deviné.

  Dans les deux cas, le code proposé passe ensuite par le même audit que les autres
  (type, listes du DPF, variable équivalente du DPF, mots interrogatifs, saut « Si
  oui »…) — y compris une Skip Logic proposée par l'IA : si elle cite une question qui
  n'existe pas, l'écart est signalé comme n'importe quel saut mal écrit, jamais appliqué
  tel quel. Le fichier corrigé ajoute les colonnes *PF/Question* et *Skip Logic* (et
  *PF/Modalités* si elle n'existait pas) ; relisez toujours l'onglet **Questionnaire
  corrigé** : un code tiré d'un libellé reste une proposition ;
- un **fichier de données** (export Kobo « XLS », c'est-à-dire `.xlsx`) : la première
  ligne porte soit les noms de variables, soit les libellés des questions. Un nom
  est vérifié comme un code ; un libellé reçoit un code PHAKTS proposé d'après son
  texte et ses valeurs. Le type se lit sur les valeurs de la colonne (entier,
  réel, date, oui/non). Seuls les **en-têtes** sont renommés, jamais les valeurs ;
  les colonnes système de Kobo (`_id`, `_uuid`, géolocalisation…) et les colonnes
  « Question/choix » d'un choix multiple sont gérées à part (renommées avec leur
  question). Deux colonnes qui recevraient le même code se voient proposer un code
  distinct (« …_VPO__1 »). La feuille *Renommages colonnes* donne ancien → nouvel
  en-tête.

**Les titres de section ne sont jamais codifiés**, dans un questionnaire comme dans
un fichier de données : une ligne « SECTION 1 : … » / « PARTIE B… » ou tout en
capitales, une colonne dont l'en-tête commence par ces mêmes mots, sont écartées et
comptées à part (message *« N titre(s) de section ignoré(s) »*). Dans un fichier de
données, un en-tête **compact** tout en majuscules (`SEXE`, `FCFA`, `ID`…) reste en
revanche une vraie variable à codifier — seul un mot-clé explicite de section écarte
une colonne, pour ne jamais faire disparaître une variable réelle en silence.

> Un fichier **.xls** ancien (Excel 97-2003) n'est pas lu : ouvrez-le dans
> Excel, puis *Enregistrer sous… .xlsx*.

**Ce qui est contrôlé** :

| Catégorie | Exemples |
|---|---|
| **Faute de frappe** | `!boulean`, `Practiques`, coquille recopiée du DPF (`Netoyage`), `!` oublié |
| **Type variable** | affixe `__Z` alors que la question définit une liste (→ `__X`), unité inconnue (`1C`), « Combien… » codé en booléen, pourcentage sans `__2P` |
| **Modalités** | accents, espaces, parenthèses dans les valeurs, doublons, crochets, identifiant de liste différent de la contrainte |
| **Liste DPF** | liste `Sexe_` différente de celle du DPF, mêmes valeurs qu'une liste du DPF sous un autre nom, région/district codés en liste inline (Règle 16) |
| **Registre DPF** | variable déjà définie dans le DPF (feuille DPF-2) sous un autre code ; variable nouvelle à soumettre au Comité DPF |
| **Skip Logic** | condition sur une question inexistante, cible qui n'est pas la question, valeur hors liste, « Si oui » sans règle |
| **Sémantique** | radical sans rapport avec le libellé |

**Deux sortes de corrections** :

- **Corrections appliquées d'office** (accent, constante de type, unité `1N` → `1`,
  séparateur `,` pour un choix unique / `|` pour un choix multiple, `1*` quand le
  libellé annonce plusieurs réponses, code XLSForm tiré du type du champ…) :
  marquées *Corrigé*. Décochez pour en refuser une.
- **Propositions** (code tiré d'un libellé, type d'une colonne deviné, changer le type d'une question codifiée, reprendre la liste du
  DPF, réécrire un saut, remplacer par la variable équivalente du DPF) :
  **jamais appliquées sans votre accord**. Cochez *Appliquer* ligne par ligne,
  ou *« ↳ les N lignes »* pour une même règle, ou
  *« Accepter les propositions affichées »* après filtrage.

L'onglet **Questionnaire corrigé** montre le résultat ligne par ligne avant
tout export.

**Exports** :

- **⬇ Télécharger le fichier corrigé** : votre classeur, mise en forme
  conservée, cellules corrigées surlignées en vert et annotées (valeur
  d'origine), plus trois feuilles : *Synthèse DPF*, *Journal des corrections
  PHAKTS* (Feuille, Ligne, Champ, Catégorie, Sévérité, Avant, Après) et
  *Écarts à valider*.
- **📑 Rapport de conformité** : ces trois feuilles seules.
- **⊞ Charger dans Résultats** (questionnaire codifié uniquement) : poursuivre
  vers la génération du XLSForm.

**Cas du XLSForm** : seule la colonne `name` est corrigée, et le nouveau nom est
propagé dans toutes les formules (`${ancien_nom}` → `${nouveau_nom}` : `relevant`,
`constraint`, `calculation`, `instance_name`…). Un champ renommé donne une autre
colonne dans les exports : la feuille *Renommages XLSForm* du fichier corrigé
donne la correspondance ancien → nouveau, et chaque cellule changée garde
l'ancien nom en note.

**À savoir sur le DPF** : le DPF contient lui-même des accents et des fautes
(`Evalution`, `Netoyage`, `Conssomation`, `Tabgagique`…). L'outil compare sur
une clé normalisée et **ne propose jamais** une graphie fautive du DPF. Quand le
DPF et la grammaire divergent (séparateur `,` ou `|`, unité `1N`), c'est la
grammaire qui s'applique (décision SPAD du 02/11/2026). Pour utiliser un DPF plus récent : *📥 Charger un DPF plus récent*
(listes **et** variables sont rechargées).

---

## 6. SPAD Analyzer — Analyse statistique

Pour accéder à l'analyse statistique, cliquez sur **📊 Analyse SPAD** dans la
barre d'onglets de PHAKTS Studio. Une fenêtre intégrée s'ouvre avec
l'analyseur Flask. À gauche, une barre latérale liste les sections.

### 6.1 Importer les données

**Méthode 1 — depuis un fichier Excel local :**

1. Cliquez **Importer les données** (bouton dans la barre latérale).
2. **Glissez votre fichier .xlsx ou .xls** dans la zone, ou cliquez pour le
   sélectionner.
3. Si le fichier contient plusieurs feuilles, la 1ʳᵉ est traitée comme la
   feuille principale, la 2ᵈ comme « tableau répété » (sous-questions Kobo).
4. Vous êtes redirigé automatiquement vers *Aperçu des données*.

**Méthode 2 — depuis KoboToolbox** : voir [section 7](#7-kobotoolbox--connexion-directe).

### 6.2 Aperçu et questionnaire des variables

Page « *Aperçu des données* ». Deux parties :

**Les données, ligne par ligne**

- **Recherche** dans toutes les colonnes à la fois, **tri** par colonne
  (numérique quand la colonne l'est), **filtre par colonne**, choix des
  colonnes affichées, 10 à 200 lignes par page.
- **Filtre « lignes signalées »** : ne garde que les soumissions relevées par
  la validation des données.
- **Aller à la ligne N** et **Cette vue (CSV)** : exporte exactement ce qui est
  affiché (recherche, filtres et tri compris).
- **Fiche d'une soumission** : un clic sur une ligne ouvre toutes les réponses
  classées par section, avec leur libellé et les anomalies relevées à la
  validation. On passe à la ligne précédente ou suivante, ou directement à la
  prochaine ligne signalée. Le bouton **Écarter / Rétablir** retire la
  soumission des analyses sans toucher au fichier. Les numéros de ligne de la
  page *Validation des données* ouvrent directement cette fiche.

**Le dictionnaire des variables**

- Pour chaque variable : code, libellé, type, modalités, et règles du
  formulaire (obligatoire, saut de logique, contrainte) quand un XLSForm est
  joint.
- **Libellé éditable** : cliquez sur la question, Entrée pour valider, Échap
  pour annuler. Un badge dit d'où vient le libellé (vous, le XLSForm ou le
  code). Il est conservé avec le jeu de données et repris par les analyses, les
  rapports, les exports SPSS/Stata et le questionnaire.
- **Type corrigé** : si le type reconnu est faux (un code numérique qui est en
  réalité une catégorie, par exemple), choisissez le bon dans la liste. Un badge
  « corrigé » le signale et toutes les analyses suivantes en tiennent compte.
- **Bouton Télécharger questionnaire (XLSX)** : fichier Excel formaté
  (*Questionnaire* + *Métadonnées*), avec section, origine du libellé et, si le
  XLSForm est joint, obligatoire, saut de logique et contrainte.

**Préparer les données** (menu *Préparer les données*)

Crée des variables à partir de celles qui existent, avec un aperçu du résultat
avant l'enregistrement :

- **Regrouper des modalités** (« Primaire » + « Secondaire » → « Scolarisé »),
- **Créer des classes** à partir de bornes (0 ; 15 ; 25 ; 50) ou de quantiles,
- **Calculer** une variable (par exemple un indice de masse corporelle),
- **Poser une condition** (oui / non) à partir d'une expression,
- **Extraire une partie d'une date** (année, mois, trimestre, semaine,
  année-mois).

Les variables créées sont proposées dans les statistiques, les croisements, les
analyses multivariées et les rapports, et se recalculent pour les nouvelles
soumissions. Un **filtre de lignes** (« ne garder que » ou « mettre de côté »)
écarte des soumissions des analyses sans modifier le fichier ; il est
réversible et refuse de vider le jeu de données.

### 6.3 Diagnostic des données

Page « *Diagnostic des données* » (anciennement « Analyse brute »). Elle répond
à une question : *ces données sont-elles en état d'être analysées ?*

1. **Score de qualité** (jauge) : calculé à partir de mesures vérifiables,
   détaillées à côté — complétude réelle, validité (quand la validation a été
   faite), unicité des soumissions, part des variables exploitables.
2. **Par où continuer** : recommandations classées (croisements, analyses
   multivariées, corrections à faire), avec le formulaire prérempli.
3. **Réponses manquantes : réelles ou prévues par le formulaire** : avec le
   XLSForm joint, une question qui ne s'appliquait pas à la personne (saut de
   logique) n'est pas comptée comme un manque. La page distingue les manquants
   *bruts* des manquants *réels*, et regroupe les cases d'une question à choix
   multiples.
4. **Anomalies de structure** : colonnes presque vides, variables constantes,
   taux de manquants élevés, doublons.
5. **Quelles variables vont ensemble** : associations entre variables
   catégorielles (V de Cramér, avec p corrigé) et corrélations de **Spearman**
   entre variables continues. Un lien quasi total (district et région, par
   exemple) est marqué *redondant* et n'est pas recommandé.
6. **Composition et distributions** des variables.
7. **Profil des variables** : une ligne par variable (type, effectifs,
   manquants, résumé, alertes) — recherche et filtres par type ou alerte.

Le diagnostic porte sur tout ce qui a été collecté, **lignes écartées
comprises**.

### 6.4 Statistiques descriptives

Page « *Statistiques descriptives* ». Permet de sélectionner précisément :
- Variables catégorielles à analyser
- Variables continues à analyser
- Groupes binaires (questions à choix multiples KoboToolbox détectées
  automatiquement)

Pour chaque variable cochée, vous obtenez :
- **Tableau de fréquences** avec IC 95% Wilson
- **Graphique barres + courbe cumulative** (Pareto)
- **Donut** avec annotation centrale du mode
- **Commentaire automatique** + zone de **commentaire libre** sauvegardé en
  session

### 6.5 Analyse Croisée Dynamique

Page « *Analyse Croisée Dynamique* ». **Style tableau croisé dynamique
Excel** :

- **Filtres** (panneau pliable) : restreindre l'analyse à un sous-ensemble
- **Lignes** : sélection multiple de variables (hiérarchie)
- **Colonnes** : sélection multiple
- **Valeur** : variable numérique (ou *« Comptage des observations »* par
  défaut)
- **Agrégation** : Nombre / Somme / Moyenne / Médiane / Min / Max / Écart-type /
  Modalités uniques
- **Pourcentages** : Aucun / % lignes / % colonnes / % total

**Résultats** :
- Tableau croisé complet (avec totaux marginaux)
- Tableau pourcentages (si demandé)
- χ² de Pearson + V de Cramér + p-value (si comptage simple 2D)
- Heatmap + bar chart si 2D simple

### 6.6 Analyses multivariées

Page « *Analyses multivariées* ». 4 méthodes :

- **ACP** (Analyse en Composantes Principales) — variables continues
- **ACM** (Analyse des Correspondances Multiples) — variables catégorielles
- **AFC** (Analyse Factorielle des Correspondances) — 2 variables catégorielles
- **Clustering** (K-means) — segmentation en N groupes

Chaque méthode produit :
- Plan factoriel (scatter)
- Inerties / variances expliquées
- Tableau des contributions
- Interprétation textuelle

### 6.7 Analyse multi-enquête (DPF / PHAKTS)

Page « *Analyse multi-enquête* ». Permet de **comparer plusieurs enquêtes**
alignées via la codification PHAKTS.

**Section 1 — Importer les enquêtes :**

Glissez plusieurs fichiers Excel (un par enquête). Pour chacun, l'application
détecte le nombre de variables codifiées PHAKTS. Les enquêtes empilées
apparaissent dans un tableau avec bouton 🗑 pour en retirer une.

**Section 2 — Couverture des variables :**

Matrice variable × enquête (1 = présente, 0 = absente). Trois modes d'alignement :
- **PHAKTS (radical)** *(recommandé)* — aligne par le radical avant le `__`
- **Nom exact** — aligne uniquement si le nom de colonne est identique
- **Union (libre)** — conserve toutes les variables, NaN où absent

**Section 3 — Comparer plusieurs variables entre enquêtes :**

1. Cochez (Ctrl/Cmd-clic) **plusieurs variables** dans la liste
2. Cliquez **+ Ajouter au panier**
3. Chaque variable apparaît dans un panneau pliable (accordéon) avec son
   tableau croisé et son graphique (barres pour catégorielles, boxplot pour
   continues)
4. Bouton **🗑 Retirer du panier** par variable
5. **Vider le panier** pour repartir à zéro

**Le panier de comparaisons survit entre les pages** et est automatiquement
inclus dans le rapport PDF/Word si vous cochez la section « Multi-enquête ».

### 6.8 Carte géographique

Page « *Carte géographique* ». Si vos données contiennent des **coordonnées
GPS** (latitude/longitude, ou format KoboToolbox brut « lat lon alt prec »),
elles sont automatiquement détectées et affichées sur une carte interactive
avec :
- Marqueurs cliquables (infobulle = ID + variables sélectionnées)
- Zoom auto sur la zone des données
- Filtres par variable catégorielle

### 6.9 Génération du rapport PDF / Word

Page « *Rapport PDF* ». Configurez et téléchargez votre rapport :

1. **Format** : ⦿ PDF ou ⦿ Word
2. **Titre & Auteur**
3. **Sections à inclure** (cases à cocher) :
   - Questions à choix multiples
   - Statistiques descriptives
   - Tableaux croisés
   - **Diagnostic des données** (score de qualité, profil, continues,
     catégorielles, binaires, manquantes réelles, corrélations, vue d'ensemble)
   - **Multi-enquête** (comparaisons sauvegardées dans le panier — DPF / PHAKTS)
4. **Sélection fine** : pour chaque catégorie (catégorielles, continues, choix
   multiples), cochez les variables à inclure individuellement
5. **Tableau croisé spécifique** : ligne + colonne à inclure (optionnel)
6. Cliquez **Générer le rapport**
7. Le fichier (.pdf ou .docx) se télécharge automatiquement

Le rapport contient une **table des matières**, un **en-tête professionnel**
avec logo SPAD/WHO, et des **commentaires automatiques** sur chaque tableau.

---

## 7. KoboToolbox — Connexion directe

PHAKTS Analyzer peut se connecter **directement à votre serveur KoboToolbox**
pour récupérer les données sans passer par un export manuel.

### 7.1 Connecter votre compte

1. En haut à droite de l'interface SPAD, cliquez sur le bouton
   **🔗 KoboToolbox** (rouge si non connecté, vert si connecté).
2. Une fenêtre modale s'ouvre.
3. **Choisissez l'instance** :
   - 🌐 *kf.kobotoolbox.org* (publique mondiale)
   - 🇪🇺 *eu.kobotoolbox.org* (Europe RGPD)
   - 🌍 *kobo.humanitarianresponse.info* (ONU / WHO / GPEI)
   - ✏️ Autre URL
4. **Collez votre Token API** :
   - Connectez-vous sur l'instance Kobo dans un navigateur
   - Profil → Paramètres du compte → Sécurité → **Clé API** → copiez-la
   - Collez-la dans le champ Token de l'application
5. Cliquez **Valider et se connecter**.
6. ✓ Connecté — votre nom d'utilisateur s'affiche en haut

### 7.2 Récupérer un formulaire

1. Cliquez **Voir mes formulaires** dans la modale ou dans la barre latérale.
2. La liste de tous vos projets Kobo apparaît.
3. Cliquez **Charger** sur le formulaire désiré.
4. Les données sont téléchargées et chargées dans SPAD Analyzer.
5. Le bouton **Rafraîchir les données** apparaît dans la barre latérale —
   utilisez-le pour récupérer les nouvelles soumissions sans tout recharger.

### 7.3 Déployer un XLSForm sur Kobo

Depuis l'onglet **Résultats** de PHAKTS Studio :
1. Cliquez **📘 XLSForm (KoboToolbox)** pour générer le formulaire
2. Si vous êtes connecté à Kobo, un bouton **Déployer sur Kobo** apparaît
3. Le formulaire est créé dans votre compte Kobo, prêt à recevoir des
   soumissions

---

## 8. Personnalisation de l'apparence

Dans l'en-tête de PHAKTS Studio, 3 thèmes sont disponibles :

| Thème | Description |
|---|---|
| ☀️ **Clair** | Fond blanc, idéal pour impressions, projections en réunion |
| ◐ **Mixte** | En-tête sombre + contenu clair (recommandé pour usage quotidien) |
| 🌙 **Sombre** *(défaut)* | Tout sombre, confortable pour longues sessions et yeux sensibles |

Le choix est **sauvegardé automatiquement** dans votre navigateur — vous le
retrouverez au prochain lancement.

---

## 9. Grammaire PHAKTS — Référence rapide

### Structure générale

```
Radical__TYPE!contrainte
```

- **Radical** : en `Snake_Case`, abstrait et générique (ex. `Statut_Matrimonial`)
- **__** : double underscore obligatoire
- **TYPE** : voir tableau ci-dessous
- **!contrainte** : optionnel, précise la qualité (plage de valeurs, liste…)

### Types de questions

| Code | Description | Exemple |
|---|---|---|
| `__B!boolean` | Booléen Oui/Non | `Vaccination__B!boolean` |
| `__X!1*1Liste_` | Choix unique | `Sexe__X!1*1Sexe_` |
| `__X!1*Liste_` | Choix multiples | `Symptomes__X!1*Symptomes_` |
| `__SRC!1*Source_` | Source d'information | `Info_Source__SRC!1*Source_Info_Sante_` |
| `__Z!1*Expression` | Texte libre | `Commentaire__Z` |
| `__A!YYYY/MM/DD` | Date ISO | `Date_Naissance__A!YYYY/MM/DD` |

### Types numériques

| Code | Type | Exemple |
|---|---|---|
| `__1` | Entier générique | `Score__1` |
| `__1Y!Y` | Entier années | `Age__1Y!0<N<120` |
| `__1M!M` | Entier mois | `Grossesse__1M!0<N<24` |
| `__1W!W` | Entier semaines | `Age_Gestationnel__1W` |
| `__1D` | Entier jours | `Duree_Hospitalisation__1D` |
| `__2K` | Réel kg | `Poids__2K!0<R<300` |
| `__2T` | Réel °C | `Temperature__2T!35<R<42` |
| `__2L` | Réel mètres | `Taille__2L!0<R<3` |

### Séparateurs de listes

- **Virgule `,`** = choix **exclusifs** (select_one) : `Football,Natation,Course`
- **Pipe `|`** = choix **cumulables** (select_multiple) : `Football|Course|Natation`
- **`0`** en fin de liste = négation / Autre / Aucun

### Listes prédéfinies courantes

| Liste | Valeurs |
|---|---|
| `boolean` | Oui, Non |
| `Trilean_` | Oui, Non, Ne_Sait_Pas |
| `Niveau_` | Eleve, Moyen, Faible |
| `Motivation_` | Très_motivée, Moyennement_motivée, Peu_motivée, Pas_motivée |
| `Dangereux_` | Très_dangereux, Dangereux, Peu_dangereux, Pas_dangereux |
| `Statut_Matrimonial_` | Célibataire, Marié(e), Divorcé(e), Veuf(ve), Concubinage |
| `Source_Info_Sante_` | Personnel_Sante, Media, Reseaux_Sociaux, Entourage, Famille, 0 |

### Skip Logic (branchement conditionnel)

| Syntaxe | Signification |
|---|---|
| `Lexia__B = Oui -> @Cible` | Si réponse Oui, afficher la cible |
| `Lexia__X != Val -> @Cible` | Si réponse ≠ valeur, afficher la cible |
| `Lexia__B -> @Cible` | Si booléen Oui (implicite) |
| `!Lexia__B -> @Cible` | Si booléen Non (négation) |
| `règle1 ; règle2` | Plusieurs règles, séparées par `;` |

---

## 10. Dépannage

### L'application ne démarre pas (Windows)

- Vérifiez que vous avez **Visual C++ Redistributable 2019** installé
  (https://aka.ms/vs/17/release/vc_redist.x64.exe)
- Réinstallez l'application en cliquant droit → **Exécuter en tant
  qu'administrateur**

### L'application ne démarre pas (macOS)

- **Clic droit → Ouvrir** au lieu de double-clic (contourne Gatekeeper la
  première fois)
- Vérifiez dans **Préférences Système → Sécurité et confidentialité** qu'il
  n'y a pas un blocage avec un bouton *Ouvrir quand même*

### « API hors ligne » en haut à droite

- C'est **normal** si vous n'avez pas configuré de clé Anthropic
- L'application fonctionne quand même : la codification utilise le moteur
  local + les exemples DPF mémorisés
- Pour activer l'API, ajoutez votre clé Anthropic dans le fichier `.env` du
  dossier d'installation (voir documentation administrateur)

### L'analyse SPAD n'affiche pas mes données

- Vérifiez que vous avez bien cliqué **Importer les données** et choisi un
  fichier `.xlsx`
- Si le fichier vient de KoboToolbox, vérifiez qu'il a au moins **une feuille
  Excel** (pas seulement des médias)
- Erreur 500 (KeyError 'Modalité') → variable 100% manquante → ignorez-la
  via la page Statistiques descriptives

### Le bouton « Skip Logic auto » ne détecte rien

- L'inférence se base sur les libellés des questions précédentes. Vérifiez
  que vos libellés contiennent : *« Si oui »*, *« Si non »*, *« En cas de »*,
  *« Si autre »*, *« Lorsque »*, ou *« Si \<Valeur\> »*
- La règle nécessite qu'une **question booléenne précède** la question
  conditionnelle (pour Si oui/Si non/En cas de)

### Le rapport PDF est trop gros

- Décochez la section **Diagnostic des données** si vous n'en avez pas besoin
- Limitez le nombre de variables sélectionnées dans chaque catégorie

### Le rapport Word ne s'ouvre pas

- Vérifiez que vous avez Microsoft Word ≥ 2016 ou LibreOffice ≥ 6
- Pour un format plus compatible, utilisez **PDF** plutôt que Word

### Les fichiers téléchargés vont où ?

- macOS / Windows : dossier **Téléchargements** par défaut
- Pour changer : configurez le téléchargement dans votre navigateur intégré

### J'ai effacé une codification du DPF par erreur

- Si vous avez un export XLSX du DPF antérieur (bouton ⬇ Exporter), vous
  pouvez la recréer manuellement via l'Agent IA :
  *« Je veux ajouter au DPF : Libellé = …, Code = … »*

---

## 11. Crédits & contact

### Auteur principal

**Dr Jean-Marc Bertrand KORANDJI**
Concepteur de la grammaire PHAKTS et du Dictionnaire des Propriétés
Fonctionnelles (DPF).
SPAD (WHO) — Bureau régional Afrique

### Équipe SPAD

- Dr Wognin Venance
- Dr M'Bra Vincent De Paul
- Dr KORANDJI Jean-Marc Bertrand
- Mlle Dieng Soraya
- Mme Aman A. Sarah

### Licence

MIT License — usage libre, modification autorisée avec mention de l'auteur.

### Citation académique

Si vous utilisez SPAD PHAKTS Analyzer dans une publication, citez :

> KORANDJI, J.-M. B., WOGNIN, V., M'BRA, V. D. P., DIENG, S., AMAN, A. S. (2026).
> *SPAD PHAKTS Analyzer — A Public Health Assessment & Knowledge Taxonomy
> framework for survey codification and analysis.* SPAD / WHO.

### Versions et historique

- **v1.0.0** — Première version stable (2026-06)
  - Codification PHAKTS hors-ligne et en ligne
  - Agent IA conversationnel avec apprentissage DPF
  - Génération XLSForm KoboToolbox
  - Analyseur SPAD complet (descriptives, croisée dynamique, multivariées,
    multi-enquête, cartographie)
  - Rapports PDF / Word automatiques
  - Build multi-OS (macOS + Windows)

### Support

Pour toute question, anomalie ou suggestion d'amélioration :

- **Issues GitHub** : https://github.com/kjmb2006-cmyk/spad-phakts-analyzer/issues
- **Email équipe SPAD** : *(à compléter selon canal interne)*

---

*Copyright © 2026 Dr Jean-Marc Bertrand KORANDJI / SPAD (WHO).
Tous droits réservés.*

*PHAKTS · STUDIO · v2026 · EQUIPE · SPAD*
*Public Health Assessment & Knowledge Taxonomy Spelling & Grammar*
