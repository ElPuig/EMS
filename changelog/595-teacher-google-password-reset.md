# What's new

## Reset a teacher's Google password from their record:

- New "Reset Google password" entry in the employee form's Actions dropdown, for the same roles
  that already manage the staff Google account (academic admin and HR: Head of Studies,
  Secretariat, TAC). It is offered while the account exists in Google and is not suspended, and
  the method re-checks the groups server-side.
- The account gets a new random password to change at next login; the new credentials PDF and the
  welcome email go out exactly as on account creation, and a chatter note records it. A Google
  refusal is reported and leaves the previous credentials untouched.
- The Directory API call is now shared with the student reset (`_gw_reset_password` in the
  Google Workspace mixin) instead of living in the student model.

## Google credentials PDF kept on the teacher's record:

- The credentials PDF is stored in a new "Google credentials" field, shown read-only in a "Google
  account" block of the Human Resources tab, restricted to admin and HR roles (the field's groups also protect its file on
  download). Only the latest PDF is kept; a reset replaces it.
- Before, each PDF was a loose attachment on the employee, shown nowhere on the form and readable
  by anyone who could read the employee.

# Internal changes

## Migration of the existing credentials PDFs:

- `migrations/18.0.0.35.0/post-migrate.py` moves each employee's latest loose credentials PDF
  into the new protected field and deletes the loose attachments (a file missing from the
  filestore is skipped).
