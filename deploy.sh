#!/bin/bash
# Production-only deploy pipeline, run by the self-hosted GitHub Actions
# runner (.github/workflows/deploy-on-release.yml). update.sh/upgrade.sh/
# test.sh are also used for day-to-day local development, so the rollback
# logic below stays here instead of in those scripts.
#
# No staging dry-run here: that's done manually via /deploy-check on the PR
# before merging (.github/workflows/deploy-check.yml), which is a required
# step right before squash. Repeating the same dump+restore+upgrade cycle
# here would mostly just slow down every deploy - the residual risk (prod
# data changing in the gap between the PR check and the actual deploy) is
# covered by the automatic rollback below instead.
set -e

BACKUP_DIR="/root/backups"
BACKUP_RETENTION_DAYS=30
FILESTORE_PATH="/var/lib/odoo/.local/share/Odoo/filestore/ems"

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

# If the real upgrade fails (e.g. production data drifted since the
# /deploy-check dry-run on the PR), restore the pre-deploy backup - code
# AND database together, not just the database. update.sh already pulled
# the new (failing) code before upgrade.sh ran, so restoring only the DB
# would leave it mismatched against that code (the same "column does not
# exist" class of failure as the 2026-07-08 incident's manual recovery).
restore_backup() {
    echo ">> Upgrade failed - restoring pre-deploy backup (v${VERSION})..." >&2
    sudo service odoo stop || true

    git fetch --tags
    git checkout "v${VERSION}"

    sudo -u odoo dropdb --if-exists ems
    sudo -u odoo createdb ems
    sudo -u odoo psql -d ems -q < "$WORK_DIR/dump.sql"
    rm -rf "$FILESTORE_PATH"
    cp -r "$WORK_DIR/filestore" "$FILESTORE_PATH"

    # Reconcile schema with the reverted code - should be a fast no-op
    # since both now match, but confirms consistency before real traffic
    # hits it instead of just hoping it's fine.
    sudo -u odoo bash -c "odoo -d ems -u ems --stop-after-init -c /etc/odoo/odoo.conf"

    sudo service odoo start || true

    # Leave the checkout back on main so the *next* deploy's update.sh can
    # git pull normally instead of failing (or worse, silently no-op'ing)
    # on a detached HEAD.
    git checkout main

    echo ">> Production restored to its pre-deploy state (v${VERSION})." >&2
}

cd /root/myModules/ems
echo ">> New EMS release detected: starting deployment for $1"

# Always deploy from main, regardless of what a previous manual recovery
# left checked out - don't rely on remembering to do this by hand.
git checkout main

backup_database
./update.sh

if ! ./upgrade.sh; then
    restore_backup
    exit 1
fi

echo ">> Deployment completed for $1"
