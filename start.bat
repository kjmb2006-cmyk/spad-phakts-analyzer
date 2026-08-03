@echo off
REM SPAD PHAKTS Analyzer — Demarrage en un clic (Windows)
REM Double-cliquez ce fichier dans l'Explorateur pour lancer l'application
REM complete (PHAKTS Studio + SPAD Analyzer), sans terminal ni commande npm.
cd /d "%~dp0"

echo =========================================================
echo   SPAD PHAKTS Analyzer
echo =========================================================

if not exist node_modules (
  echo Premiere execution detectee - installation des dependances...
  echo ^(peut prendre quelques minutes, uniquement cette fois-ci^)
  call npm install
)

echo Demarrage de l'application...
echo Cette fenetre doit rester ouverte pendant l'utilisation de l'application.
echo.

call npm run electron
pause
