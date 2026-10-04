#!/bin/bash
# Runs a command as the odoo user the way the tests need it: with the odoo user's own HOME
# (-H) and without the caller's XDG_* directories. Chrome (tour tests) keeps its crash
# handler's database under those directories; when they belong to another user (on a GitHub
# runner sudo keeps XDG_CONFIG_HOME=/home/runner/.config), the crash handler fails with
# "--database is required", Chrome never starts and Odoo skips every tour (issue #563).
#
# Usage (as root): as_odoo.sh <command> [args...]

exec sudo -H -u odoo env -u XDG_CONFIG_HOME -u XDG_CACHE_HOME -u XDG_DATA_HOME \
    -u XDG_STATE_HOME -u XDG_RUNTIME_DIR "$@"
