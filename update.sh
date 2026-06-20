#!/bin/bash
echo "Updating all modules..."

MODULES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# OCA external dependencies — cloned on first run, pulled on subsequent runs
OCA_REPOS=(
    "https://github.com/OCA/queue.git"
    "https://github.com/OCA/partner-contact.git"
)
OCA_BRANCH="18.0"

for repo_url in "${OCA_REPOS[@]}"; do
    repo_name=$(basename "$repo_url" .git)
    target="$MODULES_DIR/$repo_name"
    if [ ! -d "$target/.git" ]; then
        echo "# $repo_name (cloning):"
        git clone --depth 1 --branch "$OCA_BRANCH" "$repo_url" "$target"
    fi
done

# Pull all git repos in the modules directory
for dir in "$MODULES_DIR"/*/; do
    if [ -d "$dir/.git" ]; then
        echo "# $(basename "$dir"):"
        git -C "$dir" pull
    fi
done

echo "Done!"
