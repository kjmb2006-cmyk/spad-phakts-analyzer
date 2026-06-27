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
6. [SPAD Analyzer — Analyse statistique](#6-spad-analyzer--analyse-statistique)
   - 6.1 [Importer les données](#61-importer-les-données)
   - 6.2 [Aperçu et questionnaire des variables](#62-aperçu-et-questionnaire-des-variables)
   - 6.3 [Analyse brute](#63-analyse-brute)
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

PHAKTS (*Public Health Assessment & Knowledge Taxonomy & Grammar Rules*) est
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

Page « *Aperçu des données* ». Affiche :

- **Tableau récapitulatif** : N° / Variable (code) / Question/Libellé / Type /
  Modalités attendues / Obs. valides / Manquantes / % manq.
- **Libellés éditables** : cliquez sur n'importe quelle question pour la
  modifier, Entrée pour valider, Échap pour annuler. La modification est
  sauvegardée automatiquement et survivra à toutes les analyses + au rapport.
- **Bouton 📊 Télécharger questionnaire XLSX** : exporte un fichier Excel
  formaté avec 2 feuilles (*Questionnaire* + *Métadonnées*), utilisable comme
  document papier.
- **Aperçu des 20 premières lignes** des données brutes.

### 6.3 Analyse brute

Page « *Analyse brute* ». 8 onglets organisés :

1. **Qualité & Profil** : jauge qualité, composition par type, profil numérique
   (nb. obs / vars / complètes / continues / catégorielles / binaires)
2. **Variables continues** : pour chaque variable, statistiques (Moyenne,
   Médiane, IC 95%, asymétrie, aplatissement, IQR, outliers) + histogramme
   avec courbe normale théorique + boxplot/violon
3. **Catégorielles** : pour chaque variable, table de fréquences + bar chart
   horizontal + donut + indicateurs d'hétérogénéité (entropie de Shannon,
   Herfindahl)
4. **Binaires** : table récap (prévalence, IC 95%) + jauge de prévalence
5. **Manquantes** : graphique en barres + heatmap des données manquantes
6. **Corrélations** : matrice de corrélations Pearson pour les variables
   numériques
7. **Vue d'ensemble** : grand tableau exhaustif variable × statistiques
8. **Tableau brut** : aperçu paginé des données

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
   - **Analyse brute** (qualité, profil, continues, catégorielles, binaires,
     manquantes, corrélations, vue d'ensemble)
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

- Décochez la section **Analyse brute** si vous n'en avez pas besoin
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
*Public Health Assessment & Knowledge Taxonomy & Grammar*
