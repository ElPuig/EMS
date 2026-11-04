# What's new

## Snooze a task out of the daily summary (1, 3 or 7 days):
- The daily summary now lists only the tasks due today or overdue (company day), so postponing a task is moving its due date: it leaves the summary, and the subject's count, until that day and comes back on its own. Someone whose tasks are all due later gets no summary scheduled at all (`res.users._ems_digest_task_domain()`, shared by the candidate search, `_ems_digest_has_content()` and `_ems_digest_task_groups()`).
- My Activities (to-do tray, "View all activities"): each row is one line of icons with the text as tooltip (Done, Cancel and a bell in place of Odoo's "Snooze 7d"). The bell (view widget `ems_activity_snooze`) opens a popover with 1, 3 and 7 days, each showing the date the task would move to (from `serverNow()`). The header's single "Snooze" opens the same choices in a small dialog for the selected tasks (client action with `target: 'new'`). Both call `mail.activity.action_ems_snooze(days)`, which only accepts 1/3/7 and counts from the company's today (Odoo's own `action_snooze`, also overridden, used the server's UTC date, a day behind just after local midnight).
- The summary email explains how to postpone a task; the teachers' daily summary manual has a new "Postponing a task" section with a screenshot.

# Changes

## Tasks EMS creates are due today:
- So they reach the first summary after they appear, and their owner decides whether to postpone them: the attendance correction request (was due in 2 days, a margin from before detected absences and the unified summary), the admins' "Automatic check-in/check-out failed" (inherited the to-do type's 5 days), and Odoo's own absence approval (dated 15 days before the absence; only new ones are moved, so a snoozed one stays snoozed). The employee's "upload the supporting document" step keeps its due date (the day after the absence ends, when it can be uploaded).
