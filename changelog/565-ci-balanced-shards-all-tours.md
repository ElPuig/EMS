# Internal changes

## Every browser tour runs in CI again, in shards balanced by measured time:

- CI runs every tour again (issue #563 had limited it to one canary tour while Chrome was
  fixed), the role smoke crawlers included.
- Shards are now named after what they run: "backend-N" (tests without a browser) and
  "tours-N" (browser tours), and both are balanced by each test class's measured duration
  (`scripts/testing/test_timings.json`) instead of a round-robin split. A class with no measured
  time yet counts as the median of its kind, and the last backend shard runs every EMS test not
  listed in another shard, so a new test is never left out.
- The backend tests are split in three shards instead of one, and the tours in twelve.
- Each test shard loads the EMS module once instead of twice: it installs EMS with the tests
  enabled (`EMS_TEST_INSTALL=1 ./test.sh`, i.e. `odoo -i ems --test-enable`) instead of running
  `install.sh` and then `-u ems`. `install.sh` itself is still checked by the scripts job. The
  OCA cloning moved to a shared `ems_clone_oca_repos` function (`scripts/odoo_modules.sh`), used
  by `install.sh` and the CI.
- `scripts/testing/update_test_timings.py` refreshes the durations from a CI run's test logs.
