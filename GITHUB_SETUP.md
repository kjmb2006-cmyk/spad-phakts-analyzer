# GitHub Actions — Mise en route

Ce projet possède deux workflows GitHub Actions prêts à l'emploi :

| Fichier | Quand il se déclenche | Ce qu'il produit |
|---|---|---|
| [`build-windows.yml`](.github/workflows/build-windows.yml) | Push sur `main` qui touche le code source, ou manuel | Un installeur Windows `.exe` (artefact téléchargeable) |
| [`release.yml`](.github/workflows/release.yml) | Push d'un tag `v*.*.*`, ou manuel | Une **GitHub Release** publique avec `.exe` (Windows) + `.dmg` (macOS) |

---

## 1. Créer le dépôt GitHub

```bash
# Dans le dossier du projet
cd "/Users/mac/Desktop/Consultance 2026/Coordination/01-Projet SPAD OMS/Codification PHAKS/SPAD-PHAKTS-Analyzer"

# Initialiser git (si pas déjà fait)
git init
git branch -M main

# Premier commit
git add -A
git commit -m "Initial commit — SPAD PHAKTS Analyzer v1.0.0"
```

Ensuite, sur GitHub.com :
1. **New repository** → nom : `spad-phakts-analyzer` (ou autre)
2. **NE PAS** initialiser avec README / .gitignore / licence (vous en avez déjà)
3. Copiez l'URL HTTPS ou SSH affichée

Et de retour dans le terminal :

```bash
git remote add origin https://github.com/VOTRE-USERNAME/spad-phakts-analyzer.git
git push -u origin main
```

> ⚠️ Le `.env` qui contient la clé Anthropic est exclu par `.gitignore`. Le
> commit est sûr — aucune clé ne sera publiée.

---

## 2. Premier build Windows

Une fois le code poussé :

1. Ouvrez votre dépôt sur GitHub
2. Cliquez sur l'onglet **Actions**
3. À gauche, cliquez **Build Windows**
4. À droite, **Run workflow** → **Run workflow** (laissez les valeurs par défaut)
5. Attendez ~6-10 minutes (téléchargement Python, install dépendances, build)
6. Quand le job devient ✅, ouvrez le run et descendez à la section **Artifacts**
7. Téléchargez **SPAD-PHAKTS-Analyzer-Windows-Setup** (zip qui contient le `.exe`)

Le `.exe` est l'installeur NSIS prêt à distribuer.

---

## 3. Publier une release officielle (Windows + macOS)

Quand vous voulez publier une version sur la page « Releases » de GitHub :

```bash
# Mettre à jour la version dans package.json si nécessaire
# Puis créer un tag annoté
git tag -a v1.0.0 -m "SPAD PHAKTS Analyzer v1.0.0"
git push origin v1.0.0
```

GitHub Actions va automatiquement :
1. Builder Windows (`.exe`) ET macOS (`.dmg`) en parallèle
2. Créer une **GitHub Release** avec ces deux fichiers attachés
3. La page **Releases** de votre dépôt aura un bouton de téléchargement public

L'URL de la release sera :
`https://github.com/VOTRE-USERNAME/spad-phakts-analyzer/releases/tag/v1.0.0`

Vous pouvez la partager directement à vos collègues — pas besoin de cloner.

---

## 4. Coûts & limites

- **Public repo** : GitHub Actions est **100 % gratuit, illimité**.
- **Private repo** : 2 000 minutes Linux + 2 000 / 10 (Windows) = **200 min Windows gratuites/mois**.
  Un build Windows prend ~8 min → ~25 builds gratuits par mois pour un repo privé.

Le projet n'a pas de secret commercial dans le code (la clé Anthropic reste
dans votre `.env` local, jamais commitée), donc **un repo public est sûr** et
vous donne builds illimités.

---

## 5. Personnaliser les workflows

### Construire seulement sur push manuel
Dans `.github/workflows/build-windows.yml`, retirez les lignes `push:` :

```yaml
on:
  workflow_dispatch: {}
```

### Ajouter Linux à la release
Dans `release.yml`, ajoutez un job :

```yaml
build-linux:
  name: Linux (.AppImage)
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with: { node-version: '20', cache: 'npm' }
    - run: |
        mkdir -p python-embed-linux python-embed-win python-embed-mac
        # Linux : utiliser le Python système, copier les requirements
        python3 -m pip install --target python-embed-linux/lib/python-site -r analyzer/requirements.txt
    - run: npm ci
    - run: npm run dist:linux
    - uses: actions/upload-artifact@v4
      with:
        name: build-linux
        path: dist-electron/*.AppImage
```

Puis dans `publish-release.needs`, ajoutez `build-linux` et dans `files:`
ajoutez `artifacts/**/*.AppImage`.

### Signer le code Windows (Authenticode)

1. Achetez un certificat de signature (Sectigo, DigiCert, ~250-600 €/an)
2. Encodez-le en base64 : `base64 -i cert.pfx -o cert.b64`
3. Sur GitHub : **Settings → Secrets and variables → Actions → New secret** :
   - `WIN_CERT_B64` : contenu de cert.b64
   - `WIN_CERT_PASS` : mot de passe du PFX
4. Dans `build-windows.yml`, avant `npm run dist:win` :
   ```yaml
   - name: Importer le certificat
     shell: pwsh
     run: |
       $bytes = [Convert]::FromBase64String("${{ secrets.WIN_CERT_B64 }}")
       [IO.File]::WriteAllBytes("cert.pfx", $bytes)
   ```
   et dans `package.json` :
   ```json
   "win": {
     "certificateFile": "cert.pfx",
     "certificatePassword": "${env.WIN_CERT_PASS}"
   }
   ```

L'installeur signé n'affiche plus l'avertissement Windows SmartScreen.

---

## 6. Dépannage rapide

| Symptôme | Cause | Solution |
|---|---|---|
| `npm ci` plante avec EBADENGINE | Version Node trop ancienne | Le workflow utilise Node 20, vérifiez `node-version: '20'` |
| Build Python plante sur scipy/scikit-learn | Pas de wheel pré-compilé | Verrouillez Python à 3.11.9 (déjà fait dans le workflow) |
| `electron-builder` ne trouve pas python-embed | Mauvais nom de dossier | Vérifiez que `package.json` utilise bien `python-embed-${platform}` |
| SmartScreen bloque l'installeur | Pas de signature Authenticode | Cf. section 5 ci-dessus, ou demandez à l'utilisateur de cliquer « Exécuter quand même » |
| L'app plante au démarrage sur Windows | Python embed non trouvé à l'exécution | Vérifier que `electron-main.js` adapte le chemin selon `process.platform` |

---

## En résumé

1. **3 commandes** pour mettre le projet sur GitHub
2. **1 clic** dans l'onglet Actions pour lancer le build Windows
3. **1 tag git** pour publier une release officielle multi-OS

Le tout en **moins de 30 minutes**, sans machine Windows.
