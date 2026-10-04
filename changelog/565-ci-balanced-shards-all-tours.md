# Internal changes

## Every browser tour runs in CI again, in shards balanced by measured time:

- CI runs every tour again (issue #563 had limited it to one canary tour while Chrome was
  fixed), the role smoke crawlers included.
- Shards are now named after what they run: "backend-N" (tests without a browser) and
  "tours-N" (browser tours), and both are balanced by each test class's measured duration
  (`scripts/testing/test_timings.json`) instead of a round-robin split. A class with no measured
  time yet counts as the median of its kind, and the last backend shard runs every EMS test not
  listed in another shard, so a new test is never left out.
- The backend tests are split in two shards instead of one.
- `scripts/testing/update_test_timings.py` refreshes the durations from a CI run's test logs.
