#!/usr/bin/env bash
#
# Sauvegarde quotidienne de SPAD en production (lancée par spad-backup.timer,
# en root) : données de SPAD Analyzer et de PHAKTS Studio, plus la
# configuration nécessaire pour reconstruire le serveur (services systemd,
# variables d'environnement, sites nginx).
#
# Archives : /var/backups/spad/spad-AAAAMMJJ-HHMMSS.tar.gz (0600, root) —
# elles contiennent des secrets (.env) et des données personnelles.
# Conservation : 14 jours, plus la première archive de chaque mois sur 6 mois.
# Copie hors serveur : scripts/pull-backups.sh depuis un poste de l'équipe.
#
# Restauration : extraire dans un dossier temporaire (jamais directement dans /),
#   tar xzf spad-….tar.gz -C /tmp/restauration --numeric-owner
# arrêter les services, recopier les fichiers voulus à leur place, relancer.
set -euo pipefail

REPO=/var/www/spad-analyzer
DEST=/var/backups/spad
DB="$REPO/analyzer/data/reference/spad.db"
STAMP=$(date +%Y%m%d-%H%M%S)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
umask 077

install -d -m 700 "$DEST"
STAGE="$WORK/racine"
mkdir -p "$STAGE"

for path in "$REPO/analyzer/data" "$REPO/data" \
            /etc/spad-analyzer.env /etc/phakts-studio.env \
            /etc/systemd/system/spad-analyzer.service /etc/systemd/system/phakts-studio.service \
            /etc/systemd/system/spad-kobo-refresh.service /etc/systemd/system/spad-kobo-refresh.timer \
            /etc/systemd/system/spad-backup.service /etc/systemd/system/spad-backup.timer \
            /etc/nginx/sites-available/spad-analyzer /etc/nginx/sites-available/studio-spad-analyzer; do
  if [ -e "$path" ]; then cp -a --parents "$path" "$STAGE"; fi
done

# La base SQLite (mode WAL) ne se copie pas comme un fichier ordinaire : une
# écriture en cours donnerait une copie incohérente. .backup produit une copie
# cohérente même pendant que l'application tourne ; on la vérifie avant d'archiver.
if [ -f "$DB" ]; then
  rm -f "$STAGE$DB" "$STAGE$DB-wal" "$STAGE$DB-shm"
  sqlite3 "$DB" ".backup '$STAGE$DB'"
  if [ "$(sqlite3 "$STAGE$DB" 'PRAGMA integrity_check;')" != "ok" ]; then
    echo "ÉCHEC : la copie de spad.db est corrompue, archive non créée" >&2
    exit 1
  fi
  chown --reference="$DB" "$STAGE$DB"
  chmod --reference="$DB" "$STAGE$DB"
fi

ARCHIVE="$DEST/spad-$STAMP.tar.gz"
tar czf "$ARCHIVE.tmp" --numeric-owner -C "$STAGE" $(ls "$STAGE")
mv "$ARCHIVE.tmp" "$ARCHIVE"
chmod 600 "$ARCHIVE"

find "$DEST" -maxdepth 1 -name 'spad-*.tar.gz' ! -name 'spad-??????01-*' -mtime +14 -delete
find "$DEST" -maxdepth 1 -name 'spad-??????01-*.tar.gz' -mtime +190 -delete

echo "Sauvegarde créée : $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1)) — $(ls "$DEST" | wc -l) archive(s) conservée(s)"
