#!/bin/bash
# Checks that headless Chrome starts the way Odoo's tour tests launch it
# (odoo/tests/common.py's ChromeBrowser: same switches, run as the same user, started when
# Chrome writes its DevToolsActivePort file). When that file doesn't appear within 10s,
# Odoo *skips* the tour instead of failing it, which is how CI stayed green for months
# without running a single tour (issue #563). This check fails loudly instead, with Chrome's
# own output, before any test runs.
#
# Usage (as root): check_chrome_starts.sh [user] [extra Chrome switches...]
#   user defaults to "odoo", the user test.sh runs Odoo as.
#   CHROME_CHECK_ENV="VAR=value ..." adds environment variables to Chrome's environment.
# Exits 0 if Chrome started, 1 otherwise.

RUN_AS="${1:-odoo}"
shift
TIMEOUT_SECONDS=20

PROFILE_DIR=$(sudo -u "$RUN_AS" mktemp -d --suffix=_chrome_check)
OUTPUT_FILE=$(mktemp)

# shellcheck disable=SC2086
sudo -u "$RUN_AS" env TMPDIR="$PROFILE_DIR" ${CHROME_CHECK_ENV:-} google-chrome \
    --headless --disable-extensions --disable-background-networking \
    --disable-background-timer-throttling --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding --disable-breakpad \
    --disable-client-side-phishing-detection --disable-crash-reporter \
    --disable-dev-shm-usage --disable-namespace-sandbox --disable-translate --no-sandbox \
    --disable-gpu --enable-unsafe-swiftshader --mute-audio \
    --autoplay-policy=no-user-gesture-required --disable-default-apps \
    --disable-device-discovery-notifications --no-default-browser-check \
    --remote-debugging-address=127.0.0.1 --remote-debugging-port=0 \
    --user-data-dir="$PROFILE_DIR" --enable-logging --v=1 --no-first-run \
    "$@" about:blank >"$OUTPUT_FILE" 2>&1 &

STARTED=1
for _ in $(seq $((TIMEOUT_SECONDS * 10))); do
    if [ -s "$PROFILE_DIR/DevToolsActivePort" ]; then
        STARTED=0
        break
    fi
    sleep 0.1
done

pkill -f -- "--user-data-dir=$PROFILE_DIR" 2>/dev/null
sleep 1
pkill -9 -f -- "--user-data-dir=$PROFILE_DIR" 2>/dev/null

if [ "$STARTED" -eq 0 ]; then
    echo "Chrome started as '$RUN_AS' ${CHROME_CHECK_ENV:+($CHROME_CHECK_ENV) }$*"
else
    echo "::error::Chrome did not start as '$RUN_AS' ${CHROME_CHECK_ENV:+($CHROME_CHECK_ENV) }$* within ${TIMEOUT_SECONDS}s"
    echo "--- Chrome output ---"
    tail -n 60 "$OUTPUT_FILE"
    echo "--- chrome_debug.log ---"
    tail -n 60 "$PROFILE_DIR/chrome_debug.log" 2>/dev/null
fi

rm -rf "$PROFILE_DIR" "$OUTPUT_FILE"
exit "$STARTED"
