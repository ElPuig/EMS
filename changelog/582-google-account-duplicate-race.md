# Fixes

## Duplicate Google accounts when "Create Google account" raced the automatic creation (#582):

- Saving a teacher or a student with every required field queues the automatic creation of the
  Google account. Pressing "Create Google account" right after created the account again, directly
  in the web request, at the same time: both saw no corporate email, the loser got "already exists"
  from Google, created the next candidate address and then rolled back on the database. The result
  was a second, orphan account in Google that EMS knew nothing about (found in production on
  2026-10-05 with two new teachers).
- The button now queues the same job as the automatic creation (same identity key, so a second
  press adds nothing) and answers with a notification. It is hidden while a creation job is
  waiting or running (`google_ws_creation_pending`), since queue_job's own deduplication ignores a
  started job.
- `_gw_create_account()` locks the record's row (`FOR UPDATE NOWAIT`) before calling Google, on
  both employees and students, so any other concurrent creation for the same person fails before
  touching Google and is retried, finding the address already saved.
- Employees' job target is now `_gw_create_account()` (as students' already was);
  `action_create_google_account()` is only the button.
- User manuals (admin, head of studies, tutors; ca/es/en): the account is created automatically on
  save, and the button is only needed when that wasn't possible.
