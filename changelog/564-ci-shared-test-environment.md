# Internal changes

## Shorter CI shard setup:

- Every CI shard now installs its system packages, Odoo and (tour shards only) Chrome in a single
  apt transaction, with one package-index refresh instead of three.
- The CI no longer runs `update.sh` and `upgrade.sh` after the fresh install: `install.sh`
  already clones the OCA repositories, and `test.sh`'s own `-u ems`, which runs the at_install
  tests, already reloads the module a second time. The upgrade path on real data stays covered
  by `/deploy-check`.
- Measured before the change: each shard spent about 4 minutes on setup, of which these steps
  were roughly 1 minute. Sharing one prepared environment across shards (the original idea for
  this issue) was dropped after measuring: the shared job would have to finish before any shard
  starts, so the total wall-clock time would grow, not shrink.
