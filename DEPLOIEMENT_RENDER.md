# Déploiement de SPAD Analyzer sur Render (gratuit)

Ce guide déploie **uniquement le module SPAD Analyzer** (analyse statistique
+ connecteur KoboToolbox) en tant qu'application web accessible par
navigateur. Le module PHAKTS Studio (codification/XLSForm, qui appelle
l'API Claude) reste un usage desktop local — non déployé ici.

Render (render.com) est utilisé : hébergement Python gratuit, sans carte
bancaire requise, avec 750 h/mois offertes. Limite à connaître : sur le
plan gratuit, l'application se met en veille après 15 min d'inactivité et
met **~60 secondes** à se réveiller au premier accès suivant — normal, pas
une panne.

## Ce qui a déjà été préparé dans le dépôt

- `render.yaml` (racine du dépôt) — décrit le service à Render automatiquement
- `analyzer/requirements.txt` — inclut déjà `gunicorn` (serveur de production)
- Mot de passe Administrateur (`ANALYZER_PASSWORD_ADMIN`) — protège l'application
  une fois publique ; sans lui, tout le monde avec l'URL pourrait importer/consulter
  des données. L'administrateur autorise ensuite chaque compte Data individuellement
  (voir « Comptes Data » ci-dessous) — il n'y a plus de mot de passe Data partagé.
- Clé de session (`SECRET_KEY`) — générée automatiquement par Render à la
  création du service (option `generateValue` dans `render.yaml`)

## Étapes (à faire par vous — la création de compte ne peut pas être faite à votre place)

1. **Créer un compte Render** : allez sur [render.com](https://render.com) →
   *Get Started* → **Sign in with GitHub**. Comme le dépôt est déjà sur votre
   compte GitHub (`kjmb2006-cmyk/spad-phakts-analyzer`), un seul clic suffit
   — pas de nouveau mot de passe à créer.

2. **Autoriser Render à voir le dépôt** : lors de la première connexion,
   Render demande l'accès à vos dépôts GitHub. Autorisez au minimum
   `spad-phakts-analyzer`.

3. **Créer le service** : dans le tableau de bord Render → **New** →
   **Blueprint** → sélectionnez le dépôt `spad-phakts-analyzer`. Render
   détecte automatiquement `render.yaml` et propose de créer le service
   `spad-analyzer`.

4. **Définir le mot de passe Administrateur** : Render vous demandera la valeur
   de `ANALYZER_PASSWORD_ADMIN` (marquée `sync: false`, donc non stockée dans le
   dépôt) — choisissez un mot de passe que vous seul (ou les quelques personnes
   habilitées à administrer l'outil) connaîtrez.

5. **Déployer** : cliquez sur **Apply** / **Create Web Service**. Le premier
   build prend 3 à 5 minutes (installation de pandas, scikit-learn, etc.).

6. **Récupérer l'URL** : une fois le déploiement terminé, Render affiche une
   URL du type `https://spad-analyzer.onrender.com`. Connectez-vous avec le
   mot de passe Administrateur défini à l'étape 4.

## Comptes Data (équipe SPAD)

Il n'y a plus de mot de passe Data partagé : chaque membre de l'équipe crée
son propre compte.

1. Chaque utilisateur va sur `<votre URL>/register`, choisit un identifiant
   et un mot de passe — le compte reste **en attente**.
2. Vous (l'administrateur) allez dans **Comptes Data** (menu de gauche une
   fois connecté en Administrateur) et cliquez **Autoriser** en face de son
   nom.
3. Il peut alors se connecter normalement (onglet « Accès complet — Data »
   à l'écran de connexion).

Le menu **Journal d'activité** liste, pour chaque compte Data, les pages
visitées et actions effectuées (horodatées) — pour savoir qui a modifié la
correspondance de formulaires ou lancé un calcul.

## Optionnel : afficher les noms réels des enquêteurs/superviseurs en ligne

Par défaut, les vues « par enquêteur » / « par superviseur » affichent les
noms réels **uniquement sur votre poste local** (fichier
`analyzer/data/reference/noms_personnel.local.json`, jamais commité — le
dépôt GitHub public ne contient que les codes, ex. `D01ENQ1`). La version
déployée sur Render affiche donc les codes tant que rien de plus n'est fait.

Pour que la version en ligne (protégée par le mot de passe Administrateur)
affiche elle aussi les vrais noms, sans jamais les mettre sur GitHub, utilisez
un **Secret File** Render :

1. Sur votre poste, ouvrez `analyzer/data/reference/noms_personnel.local.json`
   et copiez tout son contenu.
2. Dans le tableau de bord Render → votre service `spad-analyzer` →
   onglet **Environment** → section **Secret Files** → **Add Secret File**.
3. Renseignez :
   - **Filename** (chemin de montage) : `/etc/secrets/noms_personnel.local.json`
   - **Contents** : collez le contenu copié à l'étape 1
4. Enregistrez — Render redéploie automatiquement. Le fichier est monté
   uniquement dans le conteneur en cours d'exécution ; il n'apparaît jamais
   dans le dépôt Git ni dans l'historique des commits.

Pour retirer les noms de la version en ligne plus tard, supprimez simplement
ce Secret File dans le tableau de bord Render — le code retombe alors sur
les codes, sans rien changer côté application.

## Après le déploiement

- **Tester** : ouvrez l'URL, entrez le mot de passe, vérifiez qu'un import
  de fichier Excel fonctionne. Si vous testez la connexion KoboToolbox
  depuis cette URL hébergée, l'actualisation automatique (voir
  `analyzer/modules/kobo_sync.py`) fonctionnera de la même façon qu'en local.
- **Redéploiements** : chaque `git push` sur la branche `main` redéploie
  automatiquement (`autoDeploy` est activé par défaut sur Render pour les
  Blueprints).
- **Limite mémoire (512 Mo, plan gratuit)** : avec pandas + scikit-learn +
  scipy chargés, de très gros fichiers importés (plusieurs dizaines de Mo,
  dizaines de milliers de lignes) pourraient faire dépasser cette limite et
  provoquer un redémarrage du service. Pour la taille du pilote SPAD actuel
  (~2 800 soumissions), cela ne devrait pas poser de problème.
- **Le webhook KoboToolbox** (`/webhook/kobo`, voir note dans `app.py`) reste
  inactif tant qu'il n'a pas été corrigé (bug de portée de session) — même
  une fois l'app publique, ne pas configurer de REST Service Kobo dessus
  sans cette correction préalable.
