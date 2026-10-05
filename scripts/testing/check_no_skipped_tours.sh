#!/bin/bash
# Fails if a test log shows any tour test skipped, or no tour test run at all.
#
# Odoo skips a tour (unittest.SkipTest) instead of failing it whenever the browser can't be
# used: Chrome not starting, Chrome not installed, websocket-client missing. The run still
# ends with "0 failed, 0 error(s)", which is how CI stayed green for months without running a
# single tour (issue #563).
#
# Usage: check_no_skipped_tours.sh <odoo test log>

LOG_FILE="$1"
TOUR_TEST='Test[A-Za-z0-9_]*Tour[A-Za-z0-9_]*\.test_[A-Za-z0-9_]+'

if ! grep -qE "Starting $TOUR_TEST" "$LOG_FILE"; then
    echo "::error::No tour test ran at all - check the shard's --test-tags selector."
    exit 1
fi

SKIPPED=$(grep -oE "skipped $TOUR_TEST : .*" "$LOG_FILE")
if [ -n "$SKIPPED" ]; then
    echo "::error::$(echo "$SKIPPED" | wc -l) tour test(s) were skipped instead of run:"
    echo "$SKIPPED"
    exit 1
fi

echo "Every tour test ran ($(grep -cE "Starting $TOUR_TEST" "$LOG_FILE") started, none skipped)."
