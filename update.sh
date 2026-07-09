#!/bin/bash
set -e
MODULES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Updating EMS references..."

echo "# Updating apt package index..."
apt-get update -qq

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

echo "Done!"
