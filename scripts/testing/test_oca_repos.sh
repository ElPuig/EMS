#!/bin/bash
# Checks scripts/oca_repos.sh's oca_sync_addons_path() the way production runs it (issue #766):
# the 'odoo' user editing an odoo.conf it owns inside a folder owned by root, which is what made
# `sed -i` fail during the v18.0.0.46.0 deploy. Run as root (it creates the files and switches to
# 'odoo'); exits non-zero on the first failed check. Used by the CI's scripts job.
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
chmod 755 "$work"

# A modules folder with every OCA repository already cloned, and a conf missing the last one.
mkdir -p "$work/etc" "$work/mods/ems"
source "$SCRIPTS_DIR/oca_repos.sh"
dirs=($(oca_repo_dirs "$work/mods"))
for dir in "${dirs[@]}"; do
    mkdir -p "$dir/.git"
done
unset 'dirs[${#dirs[@]}-1]'
listed=$(IFS=,; echo "${dirs[*]}" | sed 's/,/, /g')
printf '[options]\naddons_path = /usr/lib/x, %s/mods, %s\ndb_host = False\n' "$work" "$listed" > "$work/etc/odoo.conf"
cp "$SCRIPTS_DIR/oca_repos.sh" "$work/oca_repos.sh"
chown root:root "$work/etc" && chmod 755 "$work/etc"
chown odoo:odoo "$work/etc/odoo.conf" && chmod 640 "$work/etc/odoo.conf"
chmod 644 "$work/oca_repos.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }
run_as_odoo() { sudo -u odoo bash -ec "source '$work/oca_repos.sh'; oca_sync_addons_path '$work/etc/odoo.conf' '$work/mods'"; }

run_as_odoo || fail "oca_sync_addons_path failed as odoo with a root-owned folder"
for dir in $(oca_repo_dirs "$work/mods"); do
    grep -q "^addons_path = .*$dir" "$work/etc/odoo.conf" || fail "$dir missing from addons_path"
done
grep -q '^db_host = False$' "$work/etc/odoo.conf" || fail "the rest of odoo.conf was not kept"
[ "$(stat -c '%U:%G %a' "$work/etc/odoo.conf")" = "odoo:odoo 640" ] || fail "owner or mode changed"
[ "$(ls -A "$work/etc")" = "odoo.conf" ] || fail "files left in the conf folder: $(ls -A "$work/etc")"

before=$(md5sum < "$work/etc/odoo.conf")
run_as_odoo || fail "second run failed"
[ "$(md5sum < "$work/etc/odoo.conf")" = "$before" ] || fail "second run changed odoo.conf"

echo "oca_sync_addons_path: OK"
