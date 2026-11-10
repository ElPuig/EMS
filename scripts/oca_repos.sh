#!/bin/bash
# The third-party (OCA) repositories EMS depends on, and how every installation gets them. Shared
# by install.sh, update.sh (so deploy.sh too) and .github/workflows/deploy-check.yml. Meant to be
# sourced, not executed.
#
# Adding a repository here is all a new dependency needs: the next update.sh (every deploy runs
# it) clones it next to this checkout and adds it to the addons_path of odoo.conf, and the upgrade
# then installs the new module EMS depends on. Before this, a new repository (OCA/sign, for
# sign_oca, in v18.0.0.46.0) had to be cloned and configured by hand on every box.

OCA_REPOS=(
    "https://github.com/OCA/queue.git"
    "https://github.com/OCA/partner-contact.git"
    "https://github.com/OCA/sign.git"
)
OCA_BRANCH="18.0"

# Prints the folder each OCA repository lives in, under the modules folder $1.
oca_repo_dirs() {
    local repo_url
    for repo_url in "${OCA_REPOS[@]}"; do
        echo "$1/$(basename "$repo_url" .git)"
    done
}

# Runs a command as the current user if it can write to $1, and through sudo otherwise (e.g. the
# 'odoo' user cloning into a root-owned /root/myModules).
_oca_run_writable() {
    local target="$1"
    shift
    if [ -w "$target" ]; then
        "$@"
    else
        sudo "$@"
    fi
}

# Clones, into the modules folder $1, every OCA repository not there yet. A repository cloned
# through sudo is handed to the owner of the EMS checkout, so the next update.sh can git pull it
# as that same user (see deploy.sh: production runs everything as 'odoo').
oca_clone_missing() {
    local modules_dir="$1" repo_url target owner
    for repo_url in "${OCA_REPOS[@]}"; do
        target="$modules_dir/$(basename "$repo_url" .git)"
        [ -d "$target/.git" ] && continue
        echo "# $(basename "$target") (cloning):"
        _oca_run_writable "$modules_dir" git clone --depth 1 --branch "$OCA_BRANCH" "$repo_url" "$target"
        owner=$(stat -c '%U:%G' "$modules_dir/ems" 2>/dev/null)
        if [ -n "$owner" ] && [ "$(stat -c '%U:%G' "$target")" != "$owner" ]; then
            _oca_run_writable "$target" chown -R "$owner" "$target"
        fi
    done
}

# Adds to the addons_path of the odoo.conf file $1 every OCA repository folder under the modules
# folder $2 it does not list yet, keeping the existing entries as they are. Does nothing when the
# file has no addons_path line (nothing to extend).
oca_sync_addons_path() {
    local conf="$1" modules_dir="$2" line current dir missing=""
    line=$(grep -m1 '^\s*addons_path\s*=' "$conf" 2>/dev/null) || return 0
    current=$(sed 's/^[^=]*=//' <<< "$line" | tr ',' '\n' | sed 's/^\s*//; s/\s*$//; s#/*$##')
    for dir in $(oca_repo_dirs "$modules_dir"); do
        grep -qxF "$dir" <<< "$current" || missing="$missing, $dir"
    done
    [ -z "$missing" ] && return 0
    echo "# odoo.conf: adding${missing#,} to addons_path"
    # Not `sed -i`: it writes a temporary file next to the conf, and /etc/odoo is root's even when
    # odoo.conf is odoo's (the v18.0.0.46.0 deploy stopped there, issue #766). The new content is
    # built under /tmp and written over the existing file, which only needs permission on the file
    # and keeps its owner and mode.
    local tmp status=0
    tmp=$(mktemp) || return 1
    sed "0,/^\s*addons_path\s*=.*/s##&${missing}#" "$conf" > "$tmp" \
        && _oca_run_writable "$conf" tee "$conf" < "$tmp" > /dev/null || status=$?
    rm -f "$tmp"
    return $status
}
