#!/bin/bash
echo "Upgrading the EMS..."
sudo service odoo stop || true

echo "Upgrading odoo package..."
apt-get install --only-upgrade -y odoo

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
