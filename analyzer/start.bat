@echo off
REM SPAD Analyzer — Windows Startup Script (Version Simplifiée)
REM Double-cliquez sur ce fichier pour démarrer l'application

echo =======================================================
echo   SPAD Analyzer — Démarrage Windows
echo =======================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Free port 5050 if already in use
echo → Libération du port 5050...
netstat -aon | findstr ":5050" >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5050"') do (
        echo → Arrêt du processus %%a...
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

REM Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo → Création de l'environnement virtuel...
    echo.
    
    REM Try to find Python
    set PYTHON_CMD=
    
    REM Try python first
    python --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python
        goto :create_venv
    )
    
    REM Try py launcher
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
        goto :create_venv
    )
    
    REM Try py -3
    py -3 --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py -3
        goto :create_venv
    )
    
    REM Try python3
    python3 --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python3
        goto :create_venv
    )
    
    REM Try specific version executables if installed
    python3.12 --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python3.12
        goto :create_venv
    )
    python3.11 --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python3.11
        goto :create_venv
    )
    
    REM No Python found
    echo ❌ ERREUR: Python n'est pas installé ou pas dans le PATH
    echo.
    echo SOLUTIONS:
    echo 1. Téléchargez Python depuis: https://www.python.org/downloads/
    echo 2. Lors de l'installation, COCHEZ "Add Python to PATH"
    echo 3. Redémarrez votre ordinateur
    echo 4. Relancez ce script
    echo.
    echo Ou exécutez manuellement dans une invite de commande:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo   python run.py
    echo.
    pause
    exit /b 1
    
    :create_venv
    echo → Utilisation de: %PYTHON_CMD%
    
    REM Create virtual environment
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo ❌ ERREUR: Impossible de créer l'environnement virtuel
        echo → Vérifiez que votre antivirus n'empêche pas la création de dossiers
        echo → Essayez d'exécuter ce script en tant qu'administrateur
        pause
        exit /b 1
    )
    
    echo → Installation des dépendances (patientez 1-2 minutes)...
    call venv\Scripts\pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo ❌ ERREUR: Impossible d'installer les dépendances
        echo → Vérifiez votre connexion internet
        echo → Essayez manuellement: venv\Scripts\pip install -r requirements.txt
        pause
        exit /b 1
    )
    
    echo ✅ Installation terminée !
    echo.
)

REM Check if run.py exists
if not exist "run.py" (
    echo ❌ ERREUR: Fichier run.py introuvable
    echo → Assurez-vous que tous les fichiers sont dans le même dossier
    pause
    exit /b 1
)

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
