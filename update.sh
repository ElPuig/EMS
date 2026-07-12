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
        git -C "$dir" pull
    fi
done

echo "# Updating apt package index..."
sudo apt-get update -qq

echo "Done!"
