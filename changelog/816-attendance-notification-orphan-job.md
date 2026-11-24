# Fixes

## Attendance notification jobs no longer fail when their issue was deleted:

- Deleting a session, a roll-call line or a student removes the attendance issue through the database cascade, which never cancelled the queued family notification. The job then ran against a record that no longer existed and ended as a failed job ("Record does not exist or has been deleted"). The job now ends quietly and sends nothing when there is nothing left to notify.
