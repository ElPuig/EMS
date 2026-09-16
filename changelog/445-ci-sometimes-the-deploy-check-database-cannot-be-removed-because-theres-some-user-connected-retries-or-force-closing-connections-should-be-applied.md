# Internal changes

## `/deploy-check`'s scratch database cleanup now survives lingering connections (issue #445):
- The dry-run's own `ems_pr_check` scratch database could occasionally be left stranded on the production host: `dropdb` failed with "database is being accessed by other users" when a previous run's `odoo` process (or a cancelled run's, since this job cancels in-progress runs) still held a connection open at the exact moment the drop ran.
- Both the pre-clone drop and the final cleanup step now use `dropdb --force` (terminates lingering sessions itself before dropping) wrapped in a 5-attempt retry loop with a 5s backoff, to also cover a new connection landing in the brief window between `--force`'s termination and the actual `DROP DATABASE`.

# Related with:
- Closes #445
