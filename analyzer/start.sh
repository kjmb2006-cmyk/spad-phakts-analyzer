#!/bin/bash
# SPAD Analyzer — Linux Startup Script
# Make it executable with: chmod +x start.sh
# Then double-click or run: ./start.sh

# Change to script directory
cd "$(dirname "$0")"

# Free port 5050 if already in use
PID=$(lsof -ti:5050 2>/dev/null)
if [ -n "$PID" ]; then
  echo "→ Arrêt de l'instance précédente (PID $PID)..."
  kill -9 $PID 2>/dev/null
  sleep 1
fi

# Check if venv exists
if [ ! -f "venv/bin/python" ]; then
  echo "→ Création de l'environnement virtuel..."
  python3 -m venv venv
  if [ $? -ne 0 ]; then
    echo "ERREUR: Python3 n'est pas trouvé. Installez-le avec: sudo apt-get install python3-venv"
    read -p "Appuyez sur Entrée pour quitter..."
    exit 1
  fi
  echo "→ Installation des dépendances (patientez ~2 min)..."
  venv/bin/pip install -r requirements.txt --quiet
  if [ $? -ne 0 ]; then
    echo "ERREUR: Impossible d'installer les dépendances."
    read -p "Appuyez sur Entrée pour quitter..."
    exit 1
  fi
fi

echo ""
echo "======================================================="
echo "  SPAD Analyzer — Démarrage"
echo "======================================================="
echo "  → Navigateur s'ouvre automatiquement..."
echo "  → Appuyez sur Ctrl+C pour arrêter"
echo "======================================================="
echo ""

# Launch the application
venv/bin/python run.py
