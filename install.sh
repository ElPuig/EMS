#!/bin/bash
echo "Installing the EMS..."

MODULES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OCA_REPOS=(
    "https://github.com/OCA/queue.git"
    "https://github.com/OCA/partner-contact.git"
)
OCA_BRANCH="18.0"

for repo_url in "${OCA_REPOS[@]}"; do
    repo_name=$(basename "$repo_url" .git)
    target="$MODULES_DIR/$repo_name"
    if [ ! -d "$target/.git" ]; then
        echo "# $repo_name (cloning):"
        git clone --depth 1 --branch "$OCA_BRANCH" "$repo_url" "$target"
    fi
done

sudo service odoo stop || true
sudo -u odoo bash -c 'odoo -d ems --stop-after-init -i ems -c /etc/odoo/odoo.conf --without-demo=WITHOUT_DEMO'
EXIT_CODE=$?
sudo service odoo start || true
echo "Done!"
exit $EXIT_CODE
