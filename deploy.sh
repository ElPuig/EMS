#!/bin/bash
# Production-only deploy pipeline, run by the self-hosted GitHub Actions
# runner (.github/workflows/deploy-on-release.yml). update.sh/upgrade.sh/
# test.sh are also used for day-to-day local development, so the staging
# dry-run and rollback logic below stays here instead of in those scripts.
set -e

BACKUP_DIR="/root/backups"
BACKUP_RETENTION_DAYS=30
FILESTORE_PATH="/var/lib/odoo/.local/share/Odoo/filestore/ems"
STAGING_DB="ems_staging"

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

backup_database() {
    echo ">> Backing up database before deployment..."
    mkdir -p "$BACKUP_DIR"

    VERSION=$(sudo -u odoo psql -d ems -t -c "SELECT latest_version FROM ir_module_module WHERE name='ems';" | tr -d ' \n')
    TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
    BACKUP_FILE="$BACKUP_DIR/ems_v${VERSION}_${TIMESTAMP}.zip"

    sudo -u odoo pg_dump --no-owner -d ems > "$WORK_DIR/dump.sql"
    cp -r "$FILESTORE_PATH" "$WORK_DIR/filestore"
    (cd "$WORK_DIR" && zip -r "$BACKUP_FILE" dump.sql filestore/)

    echo ">> Backup saved: $BACKUP_FILE"
    find "$BACKUP_DIR" -name "ems_*.zip" -mtime +$BACKUP_RETENTION_DAYS -delete
}

# Restore the dump just taken by backup_database() into a scratch database
# and run the real upgrade against it, so a data/migration failure like the
# 2026-07-08 ems.planning incident is caught here instead of on production.
staging_dry_run() {
    echo ">> Dry-running the upgrade against a copy of current production data..."
    sudo -u odoo dropdb --if-exists "$STAGING_DB"
    sudo -u odoo createdb "$STAGING_DB"
    sudo -u odoo psql -d "$STAGING_DB" -q < "$WORK_DIR/dump.sql"

    if sudo -u odoo bash -c "odoo -d $STAGING_DB -u ems --stop-after-init -c /etc/odoo/odoo.conf"; then
        echo ">> Dry-run OK."
        sudo -u odoo dropdb --if-exists "$STAGING_DB"
        return 0
    else
        echo ">> Dry-run FAILED - aborting before touching production." >&2
        sudo -u odoo dropdb --if-exists "$STAGING_DB"
        return 1
    fi
}

# If the real upgrade fails anyway (the dry-run doesn't cover everything,
# e.g. filestore-dependent code), restore the pre-deploy backup so
# production isn't left half-migrated.
restore_backup() {
    echo ">> Upgrade failed - restoring pre-deploy backup..." >&2
    sudo service odoo stop || true
    sudo -u odoo dropdb --if-exists ems
    sudo -u odoo createdb ems
    sudo -u odoo psql -d ems -q < "$WORK_DIR/dump.sql"
    rm -rf "$FILESTORE_PATH"
    cp -r "$WORK_DIR/filestore" "$FILESTORE_PATH"
    sudo service odoo start || true
    echo ">> Production restored to its pre-deploy state." >&2
}

cd /root/myModules/ems
echo ">> New EMS release detected: starting deployment for $1"

backup_database
./update.sh

if ! staging_dry_run; then
    exit 1
fi

if ! ./upgrade.sh; then
    restore_backup
    exit 1
fi

echo ">> Deployment completed for $1"
