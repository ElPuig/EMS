# Internal changes

## CI switches to another Ubuntu mirror when the runner's is too slow:

- The CI's package install (`.github/actions/setup-odoo`) now goes through `scripts/testing/apt_install_with_mirror_fallback.sh`: it refreshes the indexes and downloads every package first, each under a time limit (2 and 4 minutes), and installs from apt's cache afterwards. On 2026-11-05 a slow `azure.archive.ubuntu.com` left four test jobs hanging for 12-22 minutes until cancelled by hand.
- When the limit runs out, the Ubuntu sources (one-line `sources.list`, the 24.04 deb822 `ubuntu.sources` and the runner image's `mirror+file:` mirror list, which only falls back on errors, not on slowness) are pointed at `archive.ubuntu.com`, then `mirrors.edge.kernel.org`, up to 3 attempts; what was already downloaded is kept. Odoo's and Chrome's repositories are left alone.
- apt retries dropped connections (`Acquire::Retries=3`) and drops a stalled one after 30s. The log shows the mirror used and the download time, and a slow mirror raises a warning annotation on the run's summary page.
