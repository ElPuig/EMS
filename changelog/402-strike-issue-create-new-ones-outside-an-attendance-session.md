# What's new

## Strikes can be issued outside an attendance session:

- Coexistence > Strikes has a new "New strike" button (teachers and every role above them; hidden from secretary, who can only read strikes) for incidents noticed outside class, such as a student caught in a corridor or the playground. It opens a dialog with student, reason, kicked out of class, date and time (defaults to now, editable) and details, sent with an explicit "Send" button.
- A dialog rather than the list's standard "New" on purpose: saving a strike emails the student, the tutor and possibly the family right away, and Odoo's full-page form autosaves when the user navigates away, so a half-filled strike could be sent by accident. Closing the dialog or clicking "Cancel" discards it.
- The issuer is always the logged-in teacher, shown read-only in the dialog (the existing record rule already forbids issuing on someone else's behalf); only administrators can change the "Teacher" field.
- The date and time can be set by hand to record an incident noticed earlier, but never in the future: a model constraint rejects a future date for every strike, whichever way it's created, and the date picker greys out later days.
- Notifications and escalation to the coexistence coordinator work exactly as for a strike issued from the roll-call view.

## New strike from the student's own form:

- The "Strikes" button in a student's form header is now always shown (with 0 when the student has none), not only once they have one.
- The strikes list it opens keeps the "New strike" button, and the dialog then opens with that student already chosen and read-only; everything else works as in the dialog above (issuer read-only except for administrators, never a future date, same notifications). The student is passed through a dedicated context key because Odoo drops default_* keys from a list's context before running its header buttons.

## "Actions" dropdown on the student and employee forms (replaces loose header buttons and the form's cog entries):

- Every action on a contact's form now sits in one "Actions" button in the header: the Google
  account lifecycle (create, suspend, reset password, reactivate, cancel scheduled deactivation,
  delete), plus Portal access (students/families), Send authorizations, Request contact data and
  Download Google credentials, which used to be hidden in the form's cog menu. Each entry is only
  listed when it applies to that student and that user (account state, role, being their tutor),
  and the button doesn't show at all when nothing applies.
- "Download Google credentials" is only offered on the form when the student has a credentials
  PDF the user may read, instead of answering "nothing to download" after the click.
- On the students list those four bulk actions stay in the cog menu, now bound to the list only
  so they don't appear twice on the form.
- The employee form gets the same dropdown: the Google account / EMS user actions (mark as
  identified, create Google account, create EMS user, suspend, re-link Google sign-in,
  reactivate, cancel scheduled deactivation) and Odoo's own "Deduct Extra Hours" all move into
  it, and the extra, second header EMS used to add is gone (a single header now). "Deduct Extra
  Hours" comes from hr_holidays_attendance, now listed in the module's dependencies (it was
  already auto-installed) so it is always loaded before the view that moves it.
- New reusable form component (form_compilers registry + OWL dropdown): any form gets it by
  wrapping its header buttons in `<div name="ems_actions" string="Actions">`; on small screens
  the entries fold into Odoo's own cog menu as before. Tours updated, plus a new tour covering
  the dropdown itself as a tutor.

## Teachers no longer offered actions they can't carry out:

- A plain teacher (or a tutor on someone else's student) no longer sees Archive/Unarchive in the
  cog menu of students, families and staff: it always ended in a permissions error. The client
  shows those entries whenever the `active` field isn't read-only, so contacts and employees now
  report it read-only to users whose only write access is the teacher's (record-rule limited to
  their own tutees, and archiving a student is a withdrawal, secretary/Head of Studies/admin only). TAC keeps it
  on staff, where it does have write access.
- On a student's form, "Portal access", "Send authorizations" and "Request contact data" are only
  offered when the user may act on that student, with the same rule each assistant already
  applied (the tutor and the chiefs above, plus secretary/admin, and for the two requests also
  Head of Studies). Before, a tutor could open them on another group's student and get an
  assistant that silently dropped the student.

# Changes

## Head of Studies can register withdrawals and expulsions:

- Head of Studies, Deputy Head of Studies and Director can now register a student's withdrawal
  or expulsion (the withdrawal assistant, the "Withdrawal" button of the tutor's enrollment list,
  and Archive on a student's form), which used to be limited to the secretary and administrators.
  The whole exit runs with their rights: enrollments cancelled, history frozen, operational
  records cleared, portal access revoked, student archived.

## Default strike reason follows the reasons' order:

- The reason preselected when issuing a strike is now the first active one in the reasons list (by sequence), the same criterion the roll-call dialog already used, instead of always the seeded "Other / General" reason. Both ways of issuing a strike now agree even after an administrator reorders the reasons.

# Internal changes

## Strike browser tour fixed after the session form's field rename:

- The existing strike tour still looked for the session form's old `attendance_session_line_ids` widget, renamed to `all_attendance_session_line_ids` in 18.0.0.31.0, so its "session history" leg always failed; selectors updated.
- New browser tour covering the "New strike" dialog end to end, driven by a plain teacher account, plus backend tests for issuing without a session, the issuer restriction, the default reason and the button's visibility per role. New screenshot in the teachers' strike manual.
