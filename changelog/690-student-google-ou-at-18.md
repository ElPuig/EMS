# What's new

## Students coming of age: one daily check for everything that changes at 18:

- New daily cron "EMS: Students coming of age" (`res.partner._ems_cron_coming_of_age`, `models/contacts/coming_of_age.py`): it finds the active students who turned 18 since its previous successful run and calls the `_ems_on_coming_of_age()` hook on them. Every feature that has to act that day extends the hook with `super()`, instead of each one growing its own cron.
- The window starts at `lastcall`, the previous successful run Odoo passes to the cron in the context, so a failed or skipped run never leaves a student behind and nobody is handled twice. One SQL search, a few milliseconds on the centre's data; no new field and no migration. `ADULT_AGE` is shared with `is_adult`.
- Whatever reads `is_adult` when it runs (notification recipients, who acts on the portal, contact data requests) already follows the birthday without the hook; the developer doc lists them.

## Student Google accounts move to the adults OU when the student turns 18:

- First extension of the hook: the Google Workspace integration enqueues the existing relocation job (minors OU -> adults OU). Until now the account only moved when the birth date was edited, so a student who simply turned 18 stayed in the minors OU (19 such accounts found in production on 2026-10-25, moved by hand the same day).
- Admin manual (ca/es/en) and developer docs updated.

# Internal changes

## Lifecycle cron tests independent of the development data:

- `test_cron_does_nothing_before_the_dates` patched the suspension job itself, so a real former student falling due that day in the development data the test shards clone made queue_job reject the mock. The cron tests now patch the enqueueing helpers and assert on the students handed to them.
