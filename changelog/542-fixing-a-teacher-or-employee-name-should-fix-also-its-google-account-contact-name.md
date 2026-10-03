# Fixes

## Name corrections reach the Google account and the EMS user:

- Fixing a teacher's or ASP's name in EMS now also updates the name on their Google
  Workspace account. Writing `hr.employee.name` on staff whose `work_email` is in the
  company's Google domain enqueues `action_sync_google_account_name()` (deduplicated
  queue job), which patches the Google user's `givenName`/`familyName` with the same
  first-word/rest split used when the account is created. Suspended accounts are renamed
  too; the corporate address never changes; a non-corporate `work_email` is skipped.
- Same for students: writing `name`/`firstname`/`lastname` on a student with a
  `student_email` queues the rename with their `firstname`/`lastname`. Their portal user
  shares the partner, so it already followed.
- The Directory API call lives once in `google.workspace.mixin._gw_sync_account_name()`.
  A 403/404 answer (account deleted, or outside the managed OUs) posts a chatter note
  instead of failing the job forever; any other Google error fails the job as usual.
  Dry-run only logs the payload. A successful rename is noted in the chatter.
- The employee's EMS user (`res.users`) is renamed too, synchronously
  (`hr.employee._sync_user_name()`): native hr only syncs user -> employee, so a
  pending-identification placeholder replaced by the real teacher's name ("X1 (mitja
  jornada admin)" -> "Carolina Navas Morales") left the user, and the Google account,
  with the placeholder. Writes `firstname`/`lastname`, not `name`, so the native sync
  does not bounce back.
- Migration `18.0.0.33.0/post-migrate.py`: every EMS user whose name had drifted from its
  employee's gets the employee's name (5 users in the 2026-10-02 production dump), and the
  Google rename is queued for them.
- Admin manuals (`alta-professor-compte-google.md`, `student-google-account.md`, en/ca/es),
  both Google Workspace developer docs updated; new chatter strings translated (ca_ES/es_ES).

# Internal changes

## devel.sh forces Google Workspace dry-run:

- `devel.sh` now sets `res.company.google_ws_dry_run = TRUE`. A database restored from
  production kept the live service account, and since the email rewrite leaves every
  corporate address on the centre's own domain, creating an account on a dev box would
  have created a real one in the centre's Google Workspace.
