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

# The GitHub Actions runner already runs this whole script as 'odoo', but deploy.sh is also run
# by hand for manual recovery (typically as root) - re-exec as 'odoo' so every operation below
# (git checkout/pull included, via ./update.sh) is always owned by the same user that odoo.service
# runs as, regardless of who invoked deploy.sh. A root-owned git checkout/pull is exactly what left
# several docs/ directories unwritable by 'odoo' in the 2026-07-12 incident.
if [ "$(whoami)" != "odoo" ]; then
    exec sudo -u odoo "$0" "$@"
fi

BACKUP_DIR="/root/backups"
BACKUP_RETENTION_DAYS=30
FILESTORE_PATH="/var/lib/odoo/.local/share/Odoo/filestore/ems"

WORK_DIR=$(mktemp -d)
# Owned by 'odoo' regardless of who invokes this script (the CI runner already runs as 'odoo';
# a manual root recovery run does not), so the 'sudo -u odoo cp/dropdb/psql' calls below can
# always read/write it.
chown odoo:odoo "$WORK_DIR"
trap 'rm -rf "$WORK_DIR"' EXIT

backup_database() {
    echo ">> Backing up database before deployment..."
    mkdir -p "$BACKUP_DIR"

    VERSION=$(sudo -u odoo psql -d ems -t -c "SELECT latest_version FROM ir_module_module WHERE name='ems';" | tr -d ' \n')
    TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
    BACKUP_FILE="$BACKUP_DIR/ems_v${VERSION}_${TIMESTAMP}.zip"

    sudo -u odoo pg_dump --no-owner -d ems > "$WORK_DIR/dump.sql"
    # Always as the 'odoo' user, even though the GitHub Actions runner already runs this whole
    # script as 'odoo' - deploy.sh is also run by hand (as root) for manual recovery, and a plain
    # 'cp' then would leave the filestore root-owned, which the real odoo.service (User=odoo)
    # can't write into on its next module data load (2026-07-12 incident).
    sudo -u odoo cp -r "$FILESTORE_PATH" "$WORK_DIR/filestore"
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
    # As 'odoo', not root - see the WORK_DIR/backup_database comment above; the same 'cp -r' as
    # root here is exactly what broke the filestore permissions in the 2026-07-12 incident.
    sudo -u odoo rm -rf "$FILESTORE_PATH"
    sudo -u odoo cp -r "$WORK_DIR/filestore" "$FILESTORE_PATH"

    # Reconcile schema with the reverted code - should be a fast no-op since both now match, but
    # confirms consistency before real traffic hits it instead of just hoping it's fine. Not
    # allowed to abort the function on failure (unlike the rest of restore_backup, which relies on
    # 'set -e'): odoo.service must still get restarted and HEAD must still return to 'main' even if
    # this reconciliation itself fails, otherwise production is left down AND undeployable (2026-07-12
    # incident: this step failed, 'set -e' killed the function here, and both the service restart and
    # the 'git checkout main' below never ran).
    if ! sudo -u odoo bash -c "odoo -d ems -u ems --stop-after-init -c /etc/odoo/odoo.conf"; then
        echo ">> WARNING: post-restore reconciliation failed - investigate before the next deploy, but restarting the service on the restored data first." >&2
    fi

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

# Declares this as a production environment (see CLAUDE.md's "Development vs. production
# environment declaration") - idempotent, re-declared on every deploy in case install.sh's own
# initial answer was ever wrong.
sudo -u odoo psql -d ems -c "INSERT INTO ir_config_parameter (key, value) VALUES ('ems.environment_type', 'production') ON CONFLICT (key) DO UPDATE SET value = 'production';"

echo ">> Deployment completed for $1"
