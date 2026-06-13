#!/bin/bash
set -e

BACKUP_DIR="/root/backups"
BACKUP_RETENTION_DAYS=30
FILESTORE_PATH="/var/lib/odoo/.local/share/Odoo/filestore/ems"

backup_database() {
    echo ">> Backing up database before deployment..."
    mkdir -p "$BACKUP_DIR"

    VERSION=$(sudo -u odoo psql -d ems -t -c "SELECT latest_version FROM ir_module_module WHERE name='ems';" | tr -d ' \n')
    TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
    WORK_DIR=$(mktemp -d)
    BACKUP_FILE="$BACKUP_DIR/ems_v${VERSION}_${TIMESTAMP}.zip"

    sudo -u odoo pg_dump --no-owner -d ems > "$WORK_DIR/dump.sql"
    cp -r "$FILESTORE_PATH" "$WORK_DIR/filestore"
    (cd "$WORK_DIR" && zip -r "$BACKUP_FILE" dump.sql filestore/)
    rm -rf "$WORK_DIR"

    echo ">> Backup saved: $BACKUP_FILE"
    find "$BACKUP_DIR" -name "ems_*.zip" -mtime +$BACKUP_RETENTION_DAYS -delete
}

cd /root/myModules/ems
echo ">> New EMS release detected: starting deployment for $1"
backup_database
./update.sh
./upgrade.sh
echo ">> Deployment completed for $1"
