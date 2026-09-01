# Fixes:

## Native "Create User" button on the employee form could bypass EMS's own account-creation flow (issue #375):

The Human Resources tab's native `action_create_user` button duplicated the header's "Create EMS
User" action (`action_create_ems_user`), but creates a `res.users` record directly - it does not
go through EMS's own Google Workspace account creation/adoption flow (`google_ws_state`). An admin
using the native button instead of the header one would end up with an EMS user whose Google
Workspace linkage was never set up. Hidden (`invisible="1"`) so only the EMS-aware path remains
available on the form.
