@echo off
REM Build a single-file Windows executable for SPAD Analyzer using PyInstaller
REM Usage: double-click this file or run from cmd.exe in the project root

echo =======================================================
echo   SPAD Analyzer — Packaging for Windows (PyInstaller)
echo =======================================================
echo.

REM Move to repository root (this script lives in scripts\)
cd /d "%~dp0.."

REM Ensure Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python introuvable. Assurez-vous que Python est installé et dans le PATH.
    echo → Téléchargez: https://www.python.org/downloads/ (cochez "Add Python to PATH")
    pause
    exit /b 1
)

REM Create venv if missing
if not exist "venv\Scripts\python.exe" (
    echo → Création de l'environnement virtuel...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Impossible de créer le venv.
        pause
        exit /b 1
    )
)

REM Activate venv
call venv\Scripts\activate

REM Install requirements + pyinstaller
echo → Installation des dépendances et PyInstaller...
pip install -r requirements.txt pyinstaller --quiet
if errorlevel 1 (
    echo ❌ Échec de l'installation des paquets. Vérifiez votre connexion internet et réessayez.
    pause
    exit /b 1
)

REM Run PyInstaller to produce one-file exe
echo → Lancement de PyInstaller (cela peut prendre quelques minutes)...
pyinstaller --noconfirm --onefile --name SPAD_Analyzer \
    --add-data "templates;templates" \
    --add-data "static;static" \
    --add-data "modules;modules" \
    --add-data "data;data" \
    run.py

if exist "dist\SPAD_Analyzer.exe" (
    echo ✅ Build terminé : dist\SPAD_Analyzer.exe
    echo Note: Si l'antivirus signale le binaire, créez une exception pour ce fichier.
    pause
) else (
    echo ❌ Build échoué. Consultez le dossier 'build' et le fichier 'dist' pour plus d'informations.
    pause
    exit /b 1
)

REM Deactivate venv
deactivate >nul 2>&1

exit /b 0
