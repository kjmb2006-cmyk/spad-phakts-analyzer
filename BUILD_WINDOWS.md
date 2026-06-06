# SPAD PHAKTS Analyzer — Build Windows

L'application est conçue pour fonctionner sur **macOS, Windows et Linux**. La
plupart de la base est déjà prête (Electron supporte les 3 plateformes nativement
et le `package.json` contient déjà les cibles `dist:mac`, `dist:win`, `dist:linux`).

Le seul élément spécifique à chaque plateforme est le **Python embarqué** : il
faut un Python Windows à côté du Python macOS actuel.

---

## Plan en 3 étapes

### 1. Préparer le Python embarqué Windows

Le dossier `python-embed/` contient un Python ARM64 macOS. Pour Windows il faut :

```bash
# Sur la machine de build (ou via curl + unzip sur Windows directement)
curl -L -o /tmp/python-win.zip https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
mkdir -p python-embed-win
unzip /tmp/python-win.zip -d python-embed-win

# Activer l'import des packages site (par défaut désactivé dans la distribution embed)
# Décommenter la ligne `import site` dans python-embed-win/python311._pth

# Installer les dépendances Python du projet
cd python-embed-win
curl -L -o get-pip.py https://bootstrap.pypa.io/get-pip.py
./python.exe get-pip.py
./python.exe -m pip install -r ../analyzer/requirements.txt
cd ..
```

### 2. Renommer le Python macOS actuel

```bash
mv python-embed python-embed-mac
```

### 3. Adapter `package.json` (déjà fait dans la version reconstruite)

La configuration `build.extraResources` utilise désormais
`python-embed-${platform}` qui se résout en `python-embed-mac`, `python-embed-win`
ou `python-embed-linux` selon la cible.

---

## Construction

### Option A — Build natif sur Windows (recommandé)

C'est la voie la plus fiable. Sur une machine Windows :

1. Installer **Node.js ≥ 18** (https://nodejs.org/)
2. Cloner / copier le projet sur la machine Windows
3. Préparer le `python-embed-win/` (étape 1 ci-dessus)
4. Installer les dépendances Node :
   ```cmd
   npm install
   ```
5. Construire l'installeur :
   ```cmd
   npm run dist:win
   ```
6. Le fichier produit est `dist-electron\SPAD PHAKTS Analyzer Setup 1.0.0.exe`.

### Option B — Cross-compile depuis macOS (faisable mais limité)

`electron-builder` peut cross-compiler vers Windows depuis macOS, mais il faut :

1. Installer **Wine** (sur Mac Intel uniquement — pas sur Apple Silicon natif) :
   ```bash
   brew install --cask wine-stable
   ```
2. Préparer le `python-embed-win/` sur le Mac (le ZIP Python est multiplateforme)
3. Lancer :
   ```bash
   npm run dist:win
   ```

**Limites de la cross-compilation depuis macOS** :
- Pas de signature Authenticode (besoin d'un certificat Windows)
- Wine peut échouer sur certaines étapes (création de l'installeur NSIS)
- Sur Mac Apple Silicon, Wine n'est pas fiable

### Option C — GitHub Actions (CI/CD)

Le plus propre pour une distribution professionnelle :

```yaml
# .github/workflows/build-windows.yml
name: Build Windows
on: [push, workflow_dispatch]
jobs:
  build-win:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - name: Prepare embedded Python
        run: |
          Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip" -OutFile python.zip
          Expand-Archive python.zip -DestinationPath python-embed-win
          # Activer site-packages
          (Get-Content python-embed-win\python311._pth) -replace '#import site','import site' | Set-Content python-embed-win\python311._pth
          Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile python-embed-win\get-pip.py
          python-embed-win\python.exe python-embed-win\get-pip.py
          python-embed-win\python.exe -m pip install -r analyzer\requirements.txt
        shell: pwsh
      - run: npm install
      - run: npm run dist:win
      - uses: actions/upload-artifact@v4
        with:
          name: spad-phakts-windows
          path: dist-electron/*.exe
```

Le `.exe` est téléchargeable depuis l'onglet **Actions** de GitHub.

---

## Ce qui marche déjà sur Windows sans modification

- **Tout le code Node.js (api/server.js)** — Express, Anthropic SDK, ExcelJS, etc.
- **Tout le code Python (analyzer/)** — Flask, pandas, plotly, etc.
- **L'interface HTML (PHAKTS·STUDIO)** — c'est du HTML/CSS/JS standard
- **Le launcher Electron (electron-main.js)** — utilise déjà `process.platform`
  pour adapter les chemins
- **L'icône Windows** — `public/icons/icon.ico` existe déjà
- **Les scripts batch** — `analyzer/start.bat`, `start.ps1`, `diagnose.bat`
- **Documentation** — `analyzer/README_Windows.md`, `TROUBLESHOOTING_Windows.md`

---

## Détails techniques à connaître

### Différences entre Python macOS et Windows embarqué
- macOS : Python complet installé via Homebrew, structure UNIX (`bin/`, `lib/`)
- Windows : distribution `embeddable` minimaliste de python.org, structure plate
  (`python.exe` à la racine, pas de `bin/`)

### Adapter `electron-main.js` (déjà compatible)
Le fichier détecte la plateforme et choisit le bon binaire Python :

```js
const pythonExe = process.platform === 'win32'
  ? path.join(pythonDir, 'python.exe')
  : path.join(pythonDir, 'bin', 'python3');
```

### Taille de l'installeur
- macOS DMG actuel : ~348 MB
- Windows NSIS estimé : ~280–320 MB (Python Windows embeddable est plus léger)

### Signature de code (production)
Pour éviter l'avertissement Windows SmartScreen :
1. Acheter un certificat de signature de code (~250–600 €/an)
2. Configurer dans `package.json` :
   ```json
   "win": {
     "certificateFile": "cert.pfx",
     "certificatePassword": "${env.CERT_PASS}"
   }
   ```

---

## Recommandation

Pour un déploiement rapide et propre : **Option A (build natif sur Windows)**.

Si vous n'avez pas de machine Windows immédiatement disponible, je peux :
1. **Préparer tout le projet** côté Mac (déjà fait) → un dossier prêt à copier.
2. **Vous donner les 4 commandes** à exécuter sur n'importe quel PC Windows
   pour générer le `.exe`.
3. **Configurer GitHub Actions** si vous voulez automatiser la chaîne.

Faites-moi savoir quelle option vous préférez et je continue.
