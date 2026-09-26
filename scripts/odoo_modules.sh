#!/bin/bash
# Shared helpers for every script that upgrades the EMS module: upgrade.sh, deploy.sh and
# .github/workflows/deploy-check.yml. Meant to be sourced, not executed.

# Prints option $2 from the odoo.conf file $1. Odoo writes "False" for unset options; normalised to
# empty so callers can test with [ -n ... ].
odoo_conf_get() {
    local value
    value=$(grep "^\s*$2\s*=" "$1" 2>/dev/null | head -1 | sed 's/^[^=]*=//' | tr -d ' ')
    [ "$value" = "False" ] && value=""
    echo "$value"
}

# Sets DB_PASS and PSQL_ARGS to reach database $2 as configured in odoo.conf $1. Locally and in
# production db_host is absent and psql falls back to the unix socket; in CI PostgreSQL is a remote
# service.
odoo_psql_setup() {
    local conf="$1" db="$2" host port user
    host=$(odoo_conf_get "$conf" db_host)
    port=$(odoo_conf_get "$conf" db_port)
    user=$(odoo_conf_get "$conf" db_user)
    DB_PASS=$(odoo_conf_get "$conf" db_password)
    PSQL_ARGS="-d $db"
    if [ -n "$host" ]; then
        PSQL_ARGS="-h $host -p ${port:-5432} -U ${user:-odoo} $PSQL_ARGS"
    fi
}

# Prints the comma-separated module list to pass to 'odoo -u' for database $2 (odoo.conf $1): ems
# plus every *installed* module found in any third-party addons_path folder (the OCA repos, e.g.
# queue/ and partner-contact/ - whatever update.sh git-pulls, discovered from the conf rather than
# hardcoded, so a newly added repo is picked up on its own).
#
# 'odoo -u ems' only upgrades ems and the modules depending on it, never ems' own dependencies. So
# without this, update.sh refreshes an OCA repo's code but its database side (schema, data, field
# translations, migrations) never follows - found 2026-09-26 in production, where queue_job's new
# code paused its job runner ("database ems schema is outdated, -u queue_job required") and no
# notice email left the queue for four days.
#
# Odoo's own addons folder (identified as the one shipping 'base') is skipped: -u on those modules
# would reload most of Odoo for nothing. On a failed module lookup, falls back to plain 'ems' (the
# previous behaviour) with a warning rather than aborting the upgrade.
ems_modules_to_upgrade() {
    local conf="$1" db="$2" installed dir manifest module modules="ems"
    odoo_psql_setup "$conf" "$db"
    if ! installed=$(sudo -u odoo bash -c "PGPASSWORD='$DB_PASS' psql $PSQL_ARGS -Atc \"SELECT name FROM ir_module_module WHERE state = 'installed'\""); then
        echo "WARNING: could not list installed modules - upgrading ems only." >&2
        echo "$modules"
        return
    fi
    for dir in $(odoo_conf_get "$conf" addons_path | tr ',' ' '); do
        [ -f "$dir/base/__manifest__.py" ] && continue
        for manifest in "$dir"/*/__manifest__.py; do
            [ -f "$manifest" ] || continue
            module=$(basename "$(dirname "$manifest")")
            grep -qx "$module" <<< "$installed" || continue
            grep -qx "$module" <<< "${modules//,/$'\n'}" || modules="$modules,$module"
        done
    done
    echo "$modules"
}
