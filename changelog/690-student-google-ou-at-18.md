# What's new

## Student Google accounts move to the adults OU when the student turns 18:

- The daily student Google Workspace lifecycle cron now has a third stage, `_gw_relocate_students_turning_18`: every active student with a corporate account, not suspended, whose 18th birthday falls since the cron's previous successful run gets the existing `action_relocate_google_account` job enqueued (minors OU -> adults OU). Until now the account only moved when the birth date was edited, so a student who simply turned 18 stayed in the minors OU (19 such accounts found in production on 2026-10-25, moved by hand the same day).
- The window starts at `lastcall`, the previous successful run Odoo passes to the cron in the context, so a failed or skipped run never leaves a student behind and nobody is relocated twice. One SQL search, ~4 ms on the centre's data; no new field and no migration.
- Admin manual (ca/es/en) and developer doc updated.

# Internal changes

## Lifecycle cron tests independent of the development data:

- `test_cron_does_nothing_before_the_dates` patched the suspension job itself, so a real former student falling due that day in the development data the test shards clone made queue_job reject the mock. The cron tests now patch the enqueueing helpers and assert on the students handed to them.
