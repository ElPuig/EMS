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

# Changes

## Default strike reason follows the reasons' order:

- The reason preselected when issuing a strike is now the first active one in the reasons list (by sequence), the same criterion the roll-call dialog already used, instead of always the seeded "Other / General" reason. Both ways of issuing a strike now agree even after an administrator reorders the reasons.

# Internal changes

## Strike browser tour fixed after the session form's field rename:

- The existing strike tour still looked for the session form's old `attendance_session_line_ids` widget, renamed to `all_attendance_session_line_ids` in 18.0.0.31.0, so its "session history" leg always failed; selectors updated.
- New browser tour covering the "New strike" dialog end to end, driven by a plain teacher account, plus backend tests for issuing without a session, the issuer restriction, the default reason and the button's visibility per role. New screenshot in the teachers' strike manual.
