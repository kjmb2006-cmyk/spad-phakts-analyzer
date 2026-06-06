#!/bin/bash
# SPAD Analyzer — Double-cliquez pour lancer l'application

# Se placer dans le dossier du script
cd "$(dirname "$0")"

# Libérer le port si déjà utilisé
PID=$(lsof -ti:5050 2>/dev/null)
if [ -n "$PID" ]; then
  echo "→ Arrêt de l'instance précédente (PID $PID)..."
  kill -9 $PID 2>/dev/null
  sleep 1
fi

# Vérifier que le venv existe
if [ ! -f "venv/bin/python" ]; then
  echo "→ Création de l'environnement virtuel..."
  python3.12 -m venv venv
  echo "→ Installation des dépendances (patientez ~1 min)..."
  venv/bin/pip install -r requirements.txt --quiet
fi

echo ""
echo "======================================================="
echo "  SPAD Analyzer — Démarrage"
echo "======================================================="
echo "  → Navigateur s'ouvre automatiquement..."
echo "  → Fermez cette fenêtre pour arrêter"
echo "======================================================="
echo ""

# Lancer l'application
# (run.py gère l'ouverture du navigateur automatiquement)
venv/bin/python run.py
