# 🚀 SPAD Analyzer — Guide de démarrage multiplateforme

L'application fonctionne sur **macOS**, **Windows** et **Linux**.

## 📋 Prérequis

- **Python 3.10+** (téléchargez depuis [python.org](https://www.python.org))
- **Google Chrome** (recommandé) ou tout navigateur compatible

## 🎯 Démarrage rapide par système

### macOS
1. Double-cliquez sur **`start.command`**
2. La première fois, l'installation des dépendances (~1-2 min) sera automatique
3. Votre navigateur s'ouvrira automatiquement

```bash
# Ou en terminal :
./start.command
```

### Windows
1. Double-cliquez sur **`start.bat`**
2. La première fois, Python créera l'environnement virtuel (~1-2 min)
3. Votre navigateur s'ouvrira automatiquement à `http://localhost:5050`

**Note :** Si Python n'est pas trouvé lors du double-clic :
- Installez Python 3.10+ depuis [python.org](https://www.python.org)
- ✅ Cochez **"Add Python to PATH"** pendant l'installation
- ✅ Cochez **"Install for all users"** si possible

**Si start.bat ne fonctionne pas :**
- Utilisez **`start_simple.bat`** après avoir lancé start.bat une première fois
- Ou utilisez **`start.ps1`** (PowerShell) :
  ```powershell
  powershell -ExecutionPolicy Bypass -File start.ps1
  ```
  **Note :** Si PowerShell bloque l'exécution, changez temporairement la politique :
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```
- Ou suivez l'installation manuelle ci-dessous

### Linux
1. Ouvrez un terminal dans ce dossier
2. Rendez le script exécutable :
   ```bash
   chmod +x start.sh
   ```
3. Lancez-le :
   ```bash
   ./start.sh
   ```

Ou directement :
```bash
python3 run.py
```

## 🌐 Accès à l'application

Une fois lancée, l'application est accessible à :
```
http://localhost:5050
```

## ⚙️ Installation manuelle (mode expert)

```bash
# Créer l'environnement virtuel
python3 -m venv venv

# L'activer
# macOS/Linux :
source venv/bin/activate
# Windows :
venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python run.py
```

## 🛑 Arrêt de l'application

- **macOS/Linux :** Fermez le terminal ou appuyez sur `Ctrl+C`
- **Windows :** Fermez la fenêtre ou appuyez sur `Ctrl+C` dans le terminal
- L'application libérera automatiquement le port 5050

## 📊 Fonctionnalités

- Importation de fichiers Excel/CSV
- Connexion à KoboToolbox
- Analyse statistique complète
- Génération de rapports PDF et Word
- Analyses multivariées (ACP, ACM, clustering...)

## 🐛 Troubleshooting

### "Python not found" (Windows)
→ Réinstallez Python depuis [python.org](https://www.python.org) en cochant **"Add Python to PATH"**

### "Impossible de créer l'environnement virtuel" (Windows)
→ Assurez-vous que votre antivirus n'empêche pas la création de dossiers
→ Essayez d'exécuter le script en tant qu'administrateur (clic droit → "Exécuter en tant qu'administrateur")

### "Erreur lors de l'installation des dépendances" (Windows)
→ Vérifiez votre connexion internet
→ Essayez manuellement :
```cmd
venv\Scripts\activate
pip install -r requirements.txt
```

### "Port 5050 already in use"
→ L'ancien processus n'a pas terminé. Attendez quelques secondes ou redémarrez votre PC

### "Navigateur ne s'ouvre pas automatiquement"
→ L'application sera accessible manuellement à `http://localhost:5050`

### Dépendances manquantes
→ Lancez manuellement :
```bash
pip install -r requirements.txt
```

## 📝 Fichiers de configuration

- `config.py` — Configuration de l'application (port, dossiers...)
- `requirements.txt` — Dépendances Python
- `app.py` — Application Flask principale

---

**Besoin d'aide ?** Consultez [DEMARRAGE.md](DEMARRAGE.md) pour plus de détails.
