# What's new

## Daily summary of pending tasks by email (one email per person and working day):

- EMS hands work to the staff as activities in the to-do tray (convalidation requests, supporting documents to validate, attendance corrections, absence approvals...), and most of them deliberately send no email when created (one email per task would flood an inbox: the Deputy Head of Studies got 45 convalidation requests in a few days). Nothing ever reminded anyone by email, so a person who could not open EMS that day had no way to know work was waiting.
- New cron (every 15 minutes) that sends each internal user a single email listing every open activity assigned to them (EMS's own and native Odoo ones), grouped by activity type, with a direct link to each record (`/mail/view`, access-checked), its summary, due date and a discreet "overdue" mark; at most 20 tasks per type, then "and N more". Subject in the recipient's language with the task count.
- Sent once a day at the start of the person's working day: their own working schedule decides (approved absences and public holidays already subtracted, so nothing is sent on a weekend, a holiday or a whole-day absence); people without a schedule of their own use the company's default schedule framework, public holidays subtracted. Only when there is at least one pending task.
- On by default; everyone can turn theirs off from My Profile > Preferences > Notifications (`res.users.ems_task_digest`, self-writable). No migration needed: the new boolean column is filled with its default for existing users.
- Sent through `mail.template.send_mail()` (mail queue), not `message_post()`, so it reaches the inbox whatever the user's notification preference and leaves no chatter trace. Trilingual template in `mails/shared/task_digest.xml`.

# Changes

## Attendance correction requests no longer email the approver immediately:

- A correction request is not urgent, so its approval task is now scheduled with `mail_activity_quick_update`: Odoo's "X has assigned you an activity" email is no longer sent, and the approver learns of it from the to-do tray and the daily pending-tasks digest instead (developer decision 2026-10-01; absence requests, which can be urgent, keep their immediate email). Head of Studies manuals updated.

# Internal changes

## Shared "expected working day" helpers on hr.employee:

- The per-day schedule helpers of the automatic check-out (`_get_expected_intervals`, `_get_framework_intervals`, `_get_local_day_bounds` on `hr.attendance`) moved to `hr.employee` (`_ems_expected_intervals`, `_ems_framework_intervals`, `_ems_local_day_bounds`, `models/employees/workday.py`) so the digest reuses them; the automatic check-out, public-holiday cleanup and roll-call "within working hours" check now call them. Behaviour unchanged (TestEmployeeAutocheckout, TestPublicHoliday, TestAttendanceSession* green).
