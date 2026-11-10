#!/bin/bash
# Installs apt packages on a CI runner, switching to another Ubuntu mirror when the current one
# is too slow (issue #765). On 2026-11-05 the runner's mirror served packages at a few KB/s and
# several jobs hung for 12-22 minutes in a plain 'apt-get install' until cancelled by hand.
#
# Each attempt refreshes the indexes and downloads every package (--download-only), both under a
# time limit. If either runs out, the Ubuntu sources are pointed at the next mirror and the next
# attempt starts; what was already downloaded stays in apt's cache. Once the download finishes,
# the packages are installed from that cache, with no network. The first attempt keeps whatever
# the runner image is configured with; only Ubuntu's own repositories are switched (Odoo's and
# Chrome's are left as they are).
#
# Usage (as root): apt_install_with_mirror_fallback.sh <package>...
# Environment: APT_UPDATE_TIMEOUT / APT_DOWNLOAD_TIMEOUT, seconds per attempt (120 / 240);
# APT_ETC, apt's configuration directory (/etc/apt; another one only to try the script out).

set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <package>..." >&2
    exit 2
fi

UPDATE_TIMEOUT=${APT_UPDATE_TIMEOUT:-120}
DOWNLOAD_TIMEOUT=${APT_DOWNLOAD_TIMEOUT:-240}
APT_ETC=${APT_ETC:-/etc/apt}
# Mirrors for attempts 2 and 3; attempt 1 uses the runner's own (azure.archive.ubuntu.com).
FALLBACK_MIRRORS=(archive.ubuntu.com mirrors.edge.kernel.org)
# Retries for dropped connections, and give up on a stalled one after 30s.
APT_OPTS=(-o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30)

# Ubuntu 24.04 uses deb822 '.sources' files; older images, a one-line sources.list.
ubuntu_source_files() {
    ls "$APT_ETC"/sources.list "$APT_ETC"/sources.list.d/*.list "$APT_ETC"/sources.list.d/*.sources \
        2>/dev/null || true
}

show_ubuntu_sources() {
    # shellcheck disable=SC2046
    grep -h -E '^[[:space:]]*(URIs:|deb )' $(ubuntu_source_files) 2>/dev/null \
        | grep -E 'ubuntu\.com|kernel\.org|mirror\+file' | sort -u | sed 's/^/    /' || true
}

# Points every Ubuntu source at http://<host>/ubuntu/, whether it names a mirror directly or goes
# through the runner image's mirror list ('mirror+file:/etc/apt/apt-mirrors.txt', which only
# moves on to its next entry when a mirror fails, never when it is slow).
switch_mirror() {
    local host=$1 file
    for file in $(ubuntu_source_files); do
        sed -E -i \
            -e "s#mirror\+file:/etc/apt/apt-mirrors\.txt#http://${host}/ubuntu/#g" \
            -e "s#https?://([a-z0-9.-]*archive\.ubuntu\.com|security\.ubuntu\.com|mirrors\.edge\.kernel\.org)/ubuntu/?#http://${host}/ubuntu/#g" \
            "$file"
    done
}

attempt=1
max_attempts=$((${#FALLBACK_MIRRORS[@]} + 1))
while true; do
    if [ "$attempt" -eq 1 ]; then
        mirror="runner default"
    else
        mirror=${FALLBACK_MIRRORS[$((attempt - 2))]}
        switch_mirror "$mirror"
    fi
    echo "apt attempt ${attempt}/${max_attempts}, Ubuntu mirror: ${mirror}"
    show_ubuntu_sources

    start=$(date +%s)
    failed_step=""
    if ! timeout --kill-after=10 "$UPDATE_TIMEOUT" apt-get update -qq "${APT_OPTS[@]}"; then
        failed_step="apt-get update (limit ${UPDATE_TIMEOUT}s)"
    elif ! timeout --kill-after=10 "$DOWNLOAD_TIMEOUT" \
            apt-get install -y -q --download-only "${APT_OPTS[@]}" "$@"; then
        failed_step="package download (limit ${DOWNLOAD_TIMEOUT}s)"
    fi
    elapsed=$(($(date +%s) - start))

    if [ -z "$failed_step" ]; then
        echo "Packages downloaded in ${elapsed}s from Ubuntu mirror: ${mirror}"
        break
    fi
    # A workflow annotation, so a slow mirror shows on the run's summary page, not only in the log.
    echo "::warning title=Slow or failing apt mirror::${failed_step} failed or ran out of time after ${elapsed}s on Ubuntu mirror '${mirror}' (attempt ${attempt}/${max_attempts})"
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "Giving up: no Ubuntu mirror delivered the packages in time." >&2
        exit 1
    fi
    attempt=$((attempt + 1))
done

# Everything is in apt's cache: --no-download makes a missing package an error, not a new fetch.
apt-get install -y -q --no-download "$@"
