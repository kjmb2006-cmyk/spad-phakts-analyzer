@echo off
REM Test rapide de Python et pip

echo =======================================================
echo   Test rapide Python/pip
echo =======================================================
echo.

echo → Test de Python...
python --version
if %errorlevel% neq 0 (
    echo ❌ python échoue
) else (
    echo ✅ python OK
)

echo.
echo → Test de py...
py --version
if %errorlevel% neq 0 (
    echo ❌ py échoue
) else (
    echo ✅ py OK
)

echo.
echo → Test de python3...
python3 --version
if %errorlevel% neq 0 (
    echo ❌ python3 échoue
) else (
    echo ✅ python3 OK
)

echo.
echo → Test de venv...
python -c "import venv; print('✅ venv disponible')" 2>nul
if %errorlevel% neq 0 (
    echo ❌ venv non disponible
)

echo.
echo → Test de pip...
python -m pip --version
if %errorlevel% neq 0 (
    echo ❌ pip échoue
) else (
    echo ✅ pip OK
)

echo.
echo =======================================================
echo   Test terminé
echo =======================================================
echo.
echo Si tout est ✅, Python est correctement installé.
echo Si tout est ❌, réinstallez Python depuis python.org
echo.
pause