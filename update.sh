#!/bin/bash
echo "Updating all modules..."

MODULES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for dir in "$MODULES_DIR"/*/; do
    if [ -d "$dir/.git" ]; then
        echo "# $(basename "$dir"):"
        git -C "$dir" pull
    fi
done

echo "Done!"
