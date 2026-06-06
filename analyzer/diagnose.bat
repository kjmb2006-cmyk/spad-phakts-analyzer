@echo off
REM SPAD Analyzer — Diagnostic Windows
REM Ce script aide à diagnostiquer les problèmes de démarrage

echo =======================================================
echo   SPAD Analyzer — Diagnostic Windows
echo =======================================================
echo.

REM Check current directory
echo → Répertoire actuel : %CD%
echo.

REM Check if run.py exists
if exist "run.py" (
    echo ✅ run.py trouvé
) else (
    echo ❌ run.py introuvable
    goto :error
)

REM Check if requirements.txt exists
if exist "requirements.txt" (
    echo ✅ requirements.txt trouvé
) else (
    echo ❌ requirements.txt introuvable
    goto :error
)

echo.
echo → Recherche de Python...

REM Try different Python commands
set PYTHON_FOUND=0

python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ python trouvé
    python --version
    set PYTHON_CMD=python
    set PYTHON_FOUND=1
    goto :python_found
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ py trouvé
    py --version
    set PYTHON_CMD=py
    set PYTHON_FOUND=1
    goto :python_found
)

py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ py -3 trouvé
    py -3 --version
    set PYTHON_CMD=py -3
    set PYTHON_FOUND=1
    goto :python_found
)

python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ python3 trouvé
    python3 --version
    set PYTHON_CMD=python3
    set PYTHON_FOUND=1
    goto :python_found
)

python3.12 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ python3.12 trouvé
    python3.12 --version
    set PYTHON_CMD=python3.12
    set PYTHON_FOUND=1
    goto :python_found
)

python3.11 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ python3.11 trouvé
    python3.11 --version
    set PYTHON_CMD=python3.11
    set PYTHON_FOUND=1
    goto :python_found
)

echo ❌ Aucun Python trouvé dans le PATH
echo.
echo Solutions :
echo 1. Installez Python depuis https://www.python.org
echo 2. Cochez "Add Python to PATH" pendant l'installation
echo 3. Redémarrez votre ordinateur
goto :error

:python_found
echo.
echo → Test de création d'environnement virtuel...

REM Test venv creation
%PYTHON_CMD% -c "import venv; print('✅ Module venv disponible')" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Module venv non disponible
    goto :error
)

echo ✅ Module venv OK
echo.

REM Check if venv already exists
if exist "venv\Scripts\python.exe" (
    echo ✅ Environnement virtuel trouvé
    echo → Test de l'environnement virtuel...
    call venv\Scripts\python --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ Environnement virtuel fonctionnel
    ) else (
        echo ❌ Environnement virtuel corrompu
        echo → Supprimez le dossier venv et relancez start.bat
        goto :error
    )
) else (
    echo ❌ Environnement virtuel introuvable
    echo → Lancez start.bat pour le créer
)

echo.
echo → Test des dépendances...

REM Test if we can import flask
call venv\Scripts\python -c "import flask; print('✅ Flask disponible')" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Dépendances manquantes
    echo → Lancez start.bat pour les installer
) else (
    echo ✅ Dépendances OK
)

echo.
echo =======================================================
echo   Diagnostic terminé
echo =======================================================
echo.
echo Si tout est ✅, l'application devrait fonctionner.
echo Lancez start.bat ou start_simple.bat
echo.
pause
exit /b 0

:error
echo.
echo =======================================================
echo   ERREUR détectée - Consultez les solutions ci-dessus
echo =======================================================
echo.
pause
exit /b 1