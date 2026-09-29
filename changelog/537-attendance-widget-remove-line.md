# What's new

## Remove a student from a session's roll-call (not required to attend):
- The roll-call screen (Student's Attendances → Current) has a new button at the end of each row to remove that student from the session's roll-call, e.g. for an exam only part of the group sits (issue #537). The student then counts neither as attended nor as absent.
- Implemented as the line's own `active` field (archived line), not a new status and not a deletion, so it can be undone: the row stays on the list greyed out, with its status/notes/strike buttons locked, and a restore button.
- Removed lines are left out of every attendance report and of the absence percentage automatically (archived records are skipped by `search`/`read_group`).
- Notifications: removing a line behaves like switching it to a non-notifiable status. A pending family notification is cancelled; an already-sent one triggers the usual rectification email, whose status now reads "Not required to attend (removed from the roll-call)" (same wording in the tutor's daily digest). Restoring a line with a notifiable status notifies again.
- Double periods: a student removed from the first period stays removed (and restorable) in the continuation session.
- A student with a strike in that session can't be removed (they were in class).
- Works in Guard mode too (same write path as any other line edit).
- The History session form now lists removed students too, muted, through a new `all_attendance_session_line_ids` One2many (`active_test=False`); `attendance_session_line_ids` keeps Odoo's default filtering everywhere else.
- Backend tests, a teacher-login browser tour (remove, restore, remove again; History form), teacher manual (en/ca/es) with an updated screenshot, developer doc and ca/es translations.

# Fixes

## Admins without a teaching profile could not start a roll-call:
- An admin whose employee isn't a teacher sees every slot of the day on the roll-call screen, but "Start session" failed with a required-field error on the session's teacher (it defaults to the caller's own teaching employee). The session is now recorded under the slot's own teacher (first template teacher, always present since `teacher_ids` is required).
- Automatic check-in now only applies when the session's teacher is the user actually taking the roll-call, so an admin starting a colleague's session never checks that colleague in.
- Backend test and an admin-login browser tour; teacher manual (admin section, en/ca/es) and developer doc updated.

