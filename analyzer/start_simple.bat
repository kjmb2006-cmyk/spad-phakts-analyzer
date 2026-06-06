@echo off
REM SPAD Analyzer — Démarrage simplifié (Windows)
REM Utilisez ce script si start.bat ne fonctionne pas

echo =======================================================
echo   SPAD Analyzer — Démarrage simplifié
echo =======================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo ❌ ERREUR: Environnement virtuel introuvable
    echo.
    echo SOLUTIONS:
    echo 1. Lancez d'abord start.bat pour créer l'environnement
    echo 2. Ou exécutez manuellement dans une invite de commande:
    echo      python -m venv venv
    echo      venv\Scripts\activate
    echo      pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Check if run.py exists
if not exist "run.py" (
    echo ❌ ERREUR: Fichier run.py introuvable
    pause
    exit /b 1
)

echo → Test de l'environnement virtuel...
call venv\Scripts\python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERREUR: Environnement virtuel corrompu
    echo → Supprimez le dossier venv et relancez start.bat
    pause
    exit /b 1
)

echo ✅ Environnement OK
echo → Lancement de l'application...
echo.
echo =======================================================
echo   SPAD Analyzer — Prêt !
echo =======================================================
echo   → http://localhost:5050
echo   → Fermez cette fenêtre pour arrêter
echo =======================================================
echo.

REM Launch the application
call venv\Scripts\python run.py

pause