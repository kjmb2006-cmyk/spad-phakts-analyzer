#!/usr/bin/env bash
#
# Programme sur ce Mac le rapatriement hebdomadaire des sauvegardes SPAD
# (pull-backups.sh), chaque lundi à 09:00. Si le Mac est éteint ou en veille
# à cette heure, macOS lance la tâche au réveil suivant.
#
# Le script est copié hors du Bureau : macOS interdit aux tâches planifiées
# de lire ~/Desktop sans autorisation explicite.
#
# Usage : ./scripts/install-weekly-pull.sh            (installe ou met à jour)
#         ./scripts/install-weekly-pull.sh --remove   (désinstalle)
set -euo pipefail

LABEL="com.spad.pull-backups"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SCRIPT_DIR="$HOME/Library/Application Support/SPAD"
SCRIPT="$SCRIPT_DIR/pull-backups.sh"
LOG="$HOME/Library/Logs/spad-pull-backups.log"
DOMAIN="gui/$(id -u)"

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true

if [ "${1:-}" = "--remove" ]; then
  rm -f "$PLIST" "$SCRIPT"
  echo "Rapatriement hebdomadaire désinstallé."
  exit 0
fi

mkdir -p "$SCRIPT_DIR" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
install -m 700 "$(dirname "$0")/pull-backups.sh" "$SCRIPT"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$SCRIPT</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF

launchctl bootstrap "$DOMAIN" "$PLIST"
echo "Rapatriement programmé chaque lundi à 09:00 vers ~/SPAD-Sauvegardes."
echo "Journal : $LOG"
