# Breaking changes

## The daily pending-tasks email and the tutor's attendance report are now one daily summary:

- Each member of staff gets at most one EMS message a day, at the moment chosen in My Profile > Preferences > Daily summary (start of their working day by default, end of it, end of their students' classes for tutors, or a fixed time), with three sections shown only when they have something: pending tasks, their students' attendance issues (tutors) and notices for their information.
- It honours Odoo's own "Notification" preference, now shown in the same block: by email or in the EMS inbox. The old switch to turn the pending-tasks email off is gone.
- Upgrade (18.0.0.44.0): tutors keep the report moment they had chosen, except the old default (end of their working day), which becomes the new default (start of their working day). Tutor report jobs still pending are cancelled; their issues go in the next summary.

# What's new

## Informative notices to staff wait for the daily summary (ems.info_notice):

- New queue of notices that need no action and aren't urgent (ems.info_notice._ems_queue): they are no longer sent on the spot but in the recipient's next daily summary, grouped by the record (usually a student) they are about. Rule recorded in CLAUDE.md for every new notification to staff.

# Internal changes

## Daily summary scheduling replaces the per-tutor queue job:

- res.users.ems_digest_next records when each person's summary is due; a 15-minute cron sends the due ones and keeps the old rules: an end-of-day moment reports that day's issues, an issue recorded after the moment waits for the next one (never one email per roll-call click, #588), a tutor's issues fall back to the end of the centre's day when the tutor doesn't work, and tasks are never sent on a day off or during an absence.
- The "Daily issues" screen computes Pending/Sent/Failed and the scheduled date from the summary instead of a queue job.
- The two mail templates (pending-tasks digest, tutor report) are replaced by one QWeb body translated through the .po files; tests merged into tests/test_daily_summary.py.
