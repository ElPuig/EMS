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

# psql connection args (DB_PASS, PSQL_ARGS) from odoo.conf - see odoo_psql_setup.
source "$SCRIPT_DIR/scripts/odoo_modules.sh"
CONF=/etc/odoo/odoo.conf
odoo_psql_setup "$CONF" ems

# Job queue must be cleaned
# source: https://github.com/OCA/queue/tree/18.0/queue_job#known-issues-roadmap
sudo -u odoo bash -c "PGPASSWORD='$DB_PASS' psql $PSQL_ARGS -c \"UPDATE queue_job SET state='pending' WHERE state IN ('started', 'enqueued');\""

# Not just ems: its installed OCA dependencies too, or their code (refreshed by update.sh) runs
# against a stale schema - see ems_modules_to_upgrade in scripts/odoo_modules.sh.
MODULES=$(ems_modules_to_upgrade "$CONF" ems)
echo "Upgrading modules: $MODULES"
sudo -u odoo bash -c "odoo -d ems -u $MODULES --i18n-overwrite --stop-after-init -c $CONF --dev=all"
EXIT_CODE=$?
sudo service odoo start || true
exit $EXIT_CODE
