#!/bin/bash
# Run EMS automated tests.
#
# Usage:
#   ./test.sh                          - run ALL EMS tests, sharded in parallel (see below) -
#                                         the "final gate" form.
#   ./test.sh TestLevel                - run only the named test class (sequential, against
#                                         the real ems database directly - the fast loop for
#                                         iterative dev work, no clone overhead)
#   ./test.sh '/ems:A,/ems:B'          - run a full --test-tags expression verbatim, sequential
#                                         (CI shards use this form - see scripts/testing/compute_test_shards.py)
#   ./test.sh '-/ems:A,-/ems:B'        - same, but as an exclusion list (everything except A/B)
#
# The no-argument form parallelizes across the same shard split CI uses
# (scripts/testing/compute_test_shards.py: one "fast" shard + N "tour" shards, self-maintaining
# - discovers tests/*_tour.py at run time, no script edit needed when a new tour file appears).
# See scripts/testing/run_sharded_tests.py for how each shard gets its own throwaway database
# clone and HTTP port. A scoped run (single class or an
# explicit tag expression) always stays sequential and unsharded, straight against the real ems
# database - cloning overhead isn't worth paying for a run that's already a few seconds long,
# and this is the loop CLAUDE.md's own workflow depends on staying fast for iterative Red-Green
# cycles.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Running EMS tests..."
sudo service odoo stop || true

if [ -z "$1" ]; then
    python3 "$SCRIPT_DIR/scripts/testing/run_sharded_tests.py"
    EXIT_CODE=$?
else
    TAG="/ems"
    case "$1" in
        /*|-*) TAG="$1" ;;      # already a full --test-tags expression - pass through as-is
        *)     TAG="/ems:$1" ;; # bare class name - existing single-class shorthand
    esac
    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags=${TAG} --stop-after-init -c /etc/odoo/odoo.conf 2>&1"
    EXIT_CODE=$?
fi

sudo service odoo start || true
exit $EXIT_CODE
