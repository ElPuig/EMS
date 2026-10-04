# Internal changes

## Every browser tour runs in CI again, in shards balanced by measured time:

- CI runs every tour again (issue #563 had limited it to one canary tour while Chrome was
  fixed), the role smoke crawlers included.
- Shards are now named after what they run: "backend-N" (tests without a browser) and
  "tours-N" (browser tours), and both are balanced by each test class's measured duration
  (`scripts/testing/test_timings.json`) instead of a round-robin split. A class with no measured
  time yet counts as the median of its kind, and the last backend shard runs every EMS test not
  listed in another shard, so a new test is never left out.
- The backend tests are split in four shards instead of one, and the tours in ten (measured:
  807 s of tours in total; with this split no shard has more than ~90 s of tests).
- Tried and dropped: installing EMS with the tests enabled (`odoo -i ems --test-enable`) to save
  one module load per shard. The at_install tests then run before the install has finished
  (no `hr_employee_public` SQL view or sales journal yet), and ~190 tests error out, so each
  shard still installs EMS first and runs the tests with `-u ems`.
- `scripts/testing/update_test_timings.py` refreshes the durations from a CI run's test logs.
- Fixed the three tours that failed once they really ran in CI: the tour shards now install
  `wkhtmltopdf` (a tour printing a report from the browser behaves differently without it), the
  role hierarchy-lock tour creates its own employees for the roles it opens instead of relying
  on the development database's real ones and picks the role by its exact name (`:contains`
  also matched "Deputy head of studies", listed first on a clean database), and the
  justification tour expects the typed time in
  the company's timezone (its old expectation predated the #518 timezone fix).
