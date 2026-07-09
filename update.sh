#!/bin/bash
set -e
MODULES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Updating EMS references..."

echo "# Updating apt package index..."
apt-get update -qq

for dir in "$MODULES_DIR"/*/; do
    if [ -d "$dir/.git" ]; then
        echo "# $(basename "$dir"):"
        git -C "$dir" pull
    fi
done

echo "Done!"
