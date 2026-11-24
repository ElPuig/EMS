# Fixes

## Attendance notification jobs no longer fail when their issue was deleted:

- Deleting a session, a roll-call line or a student removes the attendance issue through the database cascade, which never cancelled the queued family notification. The job then ran against a record that no longer existed and ended as a failed job ("Record does not exist or has been deleted"). The job now ends quietly and sends nothing when there is nothing left to notify.
- A migration cancels the notification jobs that had already failed for this reason.

# Internal changes

## Email tests no longer depend on the machine they run on:

- On a development machine the guard cancels OdooBot's emails before the mocked transport sees them, so tests of automatic notices failed there and passed on CI. The shared test helper that mocks outgoing email now also switches that guard parameter on inside the test's own transaction.
