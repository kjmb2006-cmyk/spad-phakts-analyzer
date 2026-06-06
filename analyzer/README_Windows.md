# 🚀 SPAD Analyzer — Démarrage Windows

## Démarrage rapide

1. **Double-cliquez sur `diagnose.bat`** (recommandé)
   - Identifie automatiquement les problèmes
   - Donne des solutions précises

2. **Puis double-cliquez sur `start.bat`**
   - Installation automatique (~2 min la première fois)
   - Lancement automatique de l'application

## Si ça ne marche pas

### Option 1 : Script simplifié
- Lancez d'abord `start.bat` une fois (pour l'installation)
- Puis utilisez `start_simple.bat` pour les lancements suivants

### Option 2 : PowerShell (ultra-fiable)
```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```

### Option 3 : Installation manuelle
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## 📋 Scripts disponibles

- **`diagnose.bat`** — Diagnostic automatique (lancez-le en premier !)
- **`start.bat`** — Installation + lancement complet
- **`start_simple.bat`** — Lancement rapide (venv déjà créé)
- **`start.ps1`** — Version PowerShell (plus robuste)

## 🚨 Problèmes courants

| Problème | Solution |
|----------|----------|
| "Python not found" | Installez Python (cochez "Add to PATH") |
| "Accès refusé" | Exécutez en tant qu'administrateur |
| "Antivirus" | Ajoutez une exception pour ce dossier |
| "Port 5050 occupé" | Fermez autres applications |

## 📖 Aide détaillée

Consultez **`TROUBLESHOOTING_Windows.md`** pour des solutions étape par étape.

## 🌐 Accès

Une fois lancé : **http://localhost:5050**

---
**Besoin d'aide ?** Lancez `diagnose.bat` et consultez TROUBLESHOOTING_Windows.md

## 🔧 Build .exe (optionnel)

Si vous souhaitez distribuer l'application sous forme d'exécutable Windows, un script pratique est fourni : [scripts/make_windows_exe.bat](scripts/make_windows_exe.bat).

Usage rapide (depuis l'invite de commandes, dossier racine du projet) :

```powershell
scripts\make_windows_exe.bat
```

Le script crée un `venv`, installe `PyInstaller` et empaquette `run.py` avec les dossiers `templates`, `static`, `modules` et `data` dans un seul fichier `dist\SPAD_Analyzer.exe`.

Remarques :
- Vérifiez que Python est installé et dans le `PATH` (cochez "Add Python to PATH" lors de l'installation).
- Si un antivirus signale l'exécutable, ajoutez une exception pour le fichier final.

PowerShell (alternative) :

```powershell
.\scripts\make_windows_exe.ps1
```

Cette version PowerShell effectue les mêmes étapes (création de `venv`, installation de `PyInstaller`, build). Exécutez PowerShell en tant qu'administrateur si vous rencontrez des problèmes d'autorisation.
