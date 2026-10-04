# Internal changes

## CI browser tours never ran (Chrome did not start):

- Browser tours had never run in GitHub CI: Chrome never opened its devtools port on the
  runner, Odoo skipped every tour instead of failing it, and the run still reported
  "0 failed, 0 error(s)" (223 of 224 tours skipped in v18.0.0.32.0, the same since at least
  July).
- Root cause: the tests run Odoo with `sudo -u odoo`, which kept a HOME the odoo user can't
  write to, so Chrome's crash handler failed ("chrome_crashpad_handler: --database is
  required") and Chrome hung before opening its devtools port. `test.sh` and the local sharded
  runner now use `sudo -H -u odoo`, giving Odoo (and Chrome) the odoo user's own HOME.
- New check before the tests (`scripts/testing/check_chrome_starts.sh`): launches Chrome the way
  Odoo does, as the `odoo` user, and fails the job right away with Chrome's own output if it
  doesn't start.
- New check after the tests (`scripts/testing/check_no_skipped_tours.sh`): the job fails if any
  tour was skipped, or if no tour ran at all, so this can't go silently green again.
- CI runs a single canary tour (`TestLevelTour`) instead of 8 tour shards until every tour is
  brought back in #565, after the test-suite improvements. A local full `./test.sh` still runs
  every tour.
