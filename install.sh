#!/bin/bash
echo "Installing the EMS..."

MODULES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

source "$MODULES_DIR/ems/scripts/odoo_modules.sh"
ems_clone_oca_repos "$MODULES_DIR"

echo "Installing system (apt) Python dependencies..."
sudo apt-get update -qq
# Some packages (e.g. python3-lxml-html-clean) only exist as a separate apt package
# on newer Ubuntu releases where lxml split html.clean out of python3-lxml itself;
# on older releases the module already ships inside python3-lxml, so skip silently.
APT_PACKAGES=""
for pkg in $(grep -v '^#' "$MODULES_DIR/ems/apt-requirements.txt"); do
    if ! apt-cache policy "$pkg" 2>/dev/null | grep -q 'Candidate: (none)'; then
        APT_PACKAGES="$APT_PACKAGES $pkg"
    else
        echo "Skipping $pkg: no installation candidate on this OS release."
    fi
done
sudo apt-get install -y $APT_PACKAGES

sudo service odoo stop || true
sudo -u odoo bash -c 'odoo -d ems --stop-after-init -i ems -c /etc/odoo/odoo.conf --without-demo=WITHOUT_DEMO'
EXIT_CODE=$?

# Declares, once and for good, whether this install is a real deployment or a development/testing
# one - devel.sh/deploy.sh both re-declare this too (in case the answer here was wrong, or the
# box's role changes later), but this is the one script EVERY install goes through, so it's what
# guarantees the flag is never left unset. See CLAUDE.md's "Development vs. production environment
# declaration" section.
if [ $EXIT_CODE -eq 0 ]; then
    environment_type="$1"
    if [[ -z "$environment_type" ]]; then
        read -p "Is this a production or a development/testing environment? [prod/dev]: " environment_type
        while [[ "$environment_type" != "prod" && "$environment_type" != "dev" ]]; do
            read -p "Please answer 'prod' or 'dev': " environment_type
        done
    fi
    value=$([[ "$environment_type" == "prod" ]] && echo "production" || echo "dev")
    sudo -u odoo bash -c "psql -d ems -c \"INSERT INTO ir_config_parameter (key, value) VALUES ('ems.environment_type', '${value}') ON CONFLICT (key) DO UPDATE SET value = '${value}';\""
fi

sudo service odoo start || true
echo "Done!"
exit $EXIT_CODE
