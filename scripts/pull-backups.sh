#!/usr/bin/env bash
#
# Copie hors serveur des sauvegardes SPAD : rapatrie sur ce poste les archives
# de /var/backups/spad qui n'y sont pas encore. Les archives contiennent des
# secrets et des données personnelles : le dossier local est réservé à
# l'utilisateur courant (700).
#
# Usage : ./scripts/pull-backups.sh [dossier]   (défaut : ~/SPAD-Sauvegardes)
set -euo pipefail

SSH_KEY="$HOME/.ssh/spad_lws_vps"
VPS_HOST="root@185.98.137.200"
DEST="${1:-$HOME/SPAD-Sauvegardes}"

mkdir -p "$DEST"
chmod 700 "$DEST"
rsync -av --ignore-existing -e "ssh -i $SSH_KEY -o ConnectTimeout=10 -o BatchMode=yes" "$VPS_HOST:/var/backups/spad/" "$DEST/"
echo "Sauvegardes disponibles dans $DEST :"
ls -lh "$DEST" | tail -n +2
