#!/bin/bash
# Run EMS automated tests.
#
# Usage:
#   ./test.sh              - run all EMS tests
#   ./test.sh TestLevel    - run only the named test class

echo "Running EMS tests..."
sudo service odoo stop || true

TAG="/ems"
if [ -n "$1" ]; then
    TAG="/ems:$1"
fi

sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags=${TAG} --stop-after-init -c /etc/odoo/odoo.conf 2>&1"
EXIT_CODE=$?
sudo service odoo start || true
exit $EXIT_CODE
