#!/bin/bash
echo "Upgrading the EMS..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sudo service odoo stop || true

echo "Upgrading odoo package..."
sudo apt-get install --only-upgrade -y odoo

echo "Installing system (apt) Python dependencies..."
sudo apt-get update -qq
# Some packages (e.g. python3-lxml-html-clean) only exist as a separate apt package
# on newer Ubuntu releases where lxml split html.clean out of python3-lxml itself;
# on older releases the module already ships inside python3-lxml, so skip silently.
APT_PACKAGES=""
for pkg in $(grep -v '^#' "$SCRIPT_DIR/apt-requirements.txt"); do
    if ! apt-cache policy "$pkg" 2>/dev/null | grep -q 'Candidate: (none)'; then
        APT_PACKAGES="$APT_PACKAGES $pkg"
    else
        echo "Skipping $pkg: no installation candidate on this OS release."
    fi
done
sudo apt-get install -y $APT_PACKAGES

# The odoo .deb package's postinst restarts the odoo.service unit on its
# own once the package is set up, regardless of it having been stopped
# above - stop it again so it doesn't hold the HTTP port when the explicit
# upgrade run below tries to bind it.
sudo service odoo stop || true

# Build psql connection args from /etc/odoo/odoo.conf when a db_host is configured
# (e.g. in CI where PostgreSQL is a remote service). Locally, db_host is absent
# and psql falls back to the unix socket.
CONF=/etc/odoo/odoo.conf
get_conf() { grep "^\s*$1\s*=" "$CONF" 2>/dev/null | head -1 | sed 's/.*=\s*//' | tr -d ' '; }
DB_HOST=$(get_conf db_host)
DB_PORT=$(get_conf db_port)
DB_USER=$(get_conf db_user)
DB_PASS=$(get_conf db_password)

# Odoo writes "False" for unset options; normalise to empty so guards work correctly
[ "$DB_HOST" = "False" ] && DB_HOST=""
[ "$DB_PORT" = "False" ] && DB_PORT=""
[ "$DB_PASS" = "False" ] && DB_PASS=""

PSQL_ARGS="-d ems"
if [ -n "$DB_HOST" ]; then
    PSQL_ARGS="-h $DB_HOST -p ${DB_PORT:-5432} -U ${DB_USER:-odoo} $PSQL_ARGS"
fi

# Job queue must be cleaned
# source: https://github.com/OCA/queue/tree/18.0/queue_job#known-issues-roadmap
sudo -u odoo bash -c "PGPASSWORD='$DB_PASS' psql $PSQL_ARGS -c \"UPDATE queue_job SET state='pending' WHERE state IN ('started', 'enqueued');\""

sudo -u odoo bash -c 'odoo -d ems -u ems --i18n-overwrite --stop-after-init -c /etc/odoo/odoo.conf --dev=all'
EXIT_CODE=$?
sudo service odoo start || true
exit $EXIT_CODE
