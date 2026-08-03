#!/bin/bash
# SPAD PHAKTS Analyzer — Démarrage en un clic (macOS)
# Double-cliquez ce fichier dans Finder pour lancer l'application complète
# (PHAKTS Studio + SPAD Analyzer), sans avoir à ouvrir un terminal ni taper
# de commande npm.
cd "$(dirname "$0")"

echo "========================================================="
echo "  SPAD PHAKTS Analyzer"
echo "========================================================="

if [ ! -d "node_modules" ]; then
  echo "Première exécution détectée — installation des dépendances..."
  echo "(peut prendre quelques minutes, uniquement cette fois-ci)"
  npm install
fi

echo "Démarrage de l'application..."
echo "Cette fenêtre doit rester ouverte pendant l'utilisation de l'application."
echo

npm run electron
