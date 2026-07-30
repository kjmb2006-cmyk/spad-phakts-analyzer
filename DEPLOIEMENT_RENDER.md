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
- Mot de passe d'accès (`ANALYZER_PASSWORD`) — protège l'application une fois
  publique ; sans lui, tout le monde avec l'URL pourrait importer/consulter
  des données
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

4. **Définir le mot de passe** : Render vous demandera la valeur de
   `ANALYZER_PASSWORD` (marquée `sync: false`, donc non stockée dans le
   dépôt) — choisissez un mot de passe que vous partagerez avec l'équipe
   SPAD amenée à utiliser l'outil.

5. **Déployer** : cliquez sur **Apply** / **Create Web Service**. Le premier
   build prend 3 à 5 minutes (installation de pandas, scikit-learn, etc.).

6. **Récupérer l'URL** : une fois le déploiement terminé, Render affiche une
   URL du type `https://spad-analyzer.onrender.com`. C'est celle-ci que vous
   partagez avec l'équipe, accompagnée du mot de passe défini à l'étape 4.

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
