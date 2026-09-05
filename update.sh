#!/bin/bash
set -e
MODULES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Updating EMS references..."

# Pull all module repos (including this one) before touching apt, so that a
# future failure in the apt step below can never block this script from
# fetching its own fix via git pull - see the 2026-07-10 apt permission
# incident, where a fix committed to update.sh could never reach production
# because the old, still-broken update.sh on disk always failed on the apt
# line before ever reaching this loop.
for dir in "$MODULES_DIR"/*/; do
    if [ -d "$dir/.git" ]; then
        name="$(basename "$dir")"
        # A detached HEAD (e.g. the EMS checkout in CI, pinned to a specific
        # PR commit) has no branch for git pull to merge with - skip it
        # rather than fail; a real checkout on a branch (local/production
        # usage) still gets pulled as usual.
        if ! git -C "$dir" symbolic-ref -q HEAD > /dev/null; then
            echo "# $name: skipped (detached HEAD)"
            continue
        fi
        echo "# $name:"
        # Scoped to the branch actually checked out here, not a bare 'git pull' - a bare pull
        # fetches EVERY branch from the remote's default refspec, not just this one, and updates
        # every branch's own remote-tracking ref/reflog in the process. If ANY of those (even a
        # branch this checkout has nothing to do with right now) has a stale/permission-broken
        # ref file, 'git fetch' returns non-zero for the whole pull, and 'set -e' aborts this
        # script before it ever reaches upgrade.sh - exactly what happened in production for
        # release v18.0.0.23.2 (GitHub Actions run 33918336342): 'main' fetched fine, but the
        # unrelated '376-absence-management' branch's reflog was root-owned and blocked the
        # whole command. 'git pull <remote> <ref>' with an explicit ref bypasses the remote's
        # default fetch refspec entirely and only ever touches THIS branch's own remote-tracking
        # ref - no other branch, in any module repo (this one's own feature branches, or the OCA
        # repos' '18.0'), is ever fetched or gets a ref/reflog written at all. Works identically
        # whether this is a manual devel run on a feature branch or deploy.sh's production run
        # (which always 'git checkout main' first) - it always pulls whatever is actually
        # checked out, never a hardcoded branch name.
        branch="$(git -C "$dir" symbolic-ref --short HEAD)"
        git -C "$dir" pull origin "$branch"
    fi
done

echo "# Updating apt package index..."
sudo apt-get update -qq

echo "Done!"
