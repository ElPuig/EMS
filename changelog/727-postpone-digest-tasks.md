# What's new

## Snooze a task out of the daily summary (Snooze 1d / 3d / 7d):
- The daily summary now lists only the tasks due today or overdue (company day), so postponing a task is moving its due date: it leaves the summary, and the subject's count, until that day and comes back on its own. Someone whose tasks are all due later gets no summary scheduled at all (`res.users._ems_digest_task_domain()`, shared by the candidate search, `_ems_digest_has_content()` and `_ems_digest_task_groups()`).
- My Activities (to-do tray, "View all activities") gets "Snooze 1d" and "Snooze 3d" next to Odoo's own "Snooze 7d", per row and for the selected tasks. All three count from the company's today (Odoo's own `action_snooze` used the server's UTC date, a day behind just after local midnight). A small CSS rule widens that list's button cell, which Odoo sized too narrow for five buttons and cut the labels.
- The summary email explains how to postpone a task; the teachers' daily summary manual has a new "Postponing a task" section with a screenshot.

# Changes

## Tasks EMS creates are due today:
- So they reach the first summary after they appear, and their owner decides whether to postpone them: the attendance correction request (was due in 2 days, a margin from before detected absences and the unified summary), the admins' "Automatic check-in/check-out failed" (inherited the to-do type's 5 days), and Odoo's own absence approval (dated 15 days before the absence; only new ones are moved, so a snoozed one stays snoozed). The employee's "upload the supporting document" step keeps its due date (the day after the absence ends, when it can be uploaded).
