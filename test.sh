#!/bin/bash
# Run EMS automated tests.
#
# Usage:
#   ./test.sh                          - run all EMS tests
#   ./test.sh TestLevel                - run only the named test class
#   ./test.sh '/ems:A,/ems:B'          - run a full --test-tags expression verbatim (CI shards
#                                         use this form - see .github/scripts/compute_test_shards.py)
#   ./test.sh '-/ems:A,-/ems:B'        - same, but as an exclusion list (everything except A/B)

echo "Running EMS tests..."
sudo service odoo stop || true

TAG="/ems"
if [ -n "$1" ]; then
    case "$1" in
        /*|-*) TAG="$1" ;;      # already a full --test-tags expression - pass through as-is
        *)     TAG="/ems:$1" ;; # bare class name - existing single-class shorthand
    esac
fi

sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags=${TAG} --stop-after-init -c /etc/odoo/odoo.conf 2>&1"
EXIT_CODE=$?
sudo service odoo start || true
exit $EXIT_CODE
