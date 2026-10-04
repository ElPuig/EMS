# Internal changes

## Shorter CI shard setup:

- Every CI shard now installs its system packages, Odoo and (tour shards only) Chrome in a single
  apt transaction, with one package-index refresh instead of three.
- The test shards no longer run `update.sh` and `upgrade.sh` after the fresh install: `test.sh`'s
  own `-u ems`, which runs the at_install tests, already reloads the module. Those two scripts
  are now checked once, by a new "Scripts (install, update, upgrade)" job that runs the same
  sequence as production (`install.sh`, `update.sh`, `upgrade.sh`) on a fresh install, without
  tests, in parallel with the shards, so it adds no wall-clock time. "Test (all)" requires it
  too. The upgrade path on real data stays covered by `/deploy-check`.
- The shared setup (packages, Odoo, configuration, `install.sh`) lives in a local composite
  action, `.github/actions/setup-odoo`, used by both the shards and the scripts job.
- Measured before the change: each shard spent about 4 minutes on setup, of which these steps
  were roughly 1 minute. Sharing one prepared environment across shards (the original idea for
  this issue) was dropped after measuring: the shared job would have to finish before any shard
  starts, so the total wall-clock time would grow, not shrink.
