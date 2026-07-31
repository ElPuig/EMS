# What's new:

## Pending-identification teachers from schedule imports:
- Importing a working-schedule file (per-teacher or the general cog-menu importer) no longer fails when a row names a not-yet-hired post with a placeholder code (e.g. `X1`, `X2`) instead of a real e-mail.
- A "Pending teacher (X1)" employee is created automatically, with the schedule/subjects/attendance lists already assigned — no manual setup needed.
- Re-importing an updated file for the same still-unstaffed post (same code) updates that same employee in place, never creating a duplicate.
- These employees show a "Pending identification" indicator (Teachers list column, kanban badge, form ribbon), with a matching search filter/group-by.
- Resolving a pending teacher's real identity reuses the existing "Generate Google account" button: fill in the real name + personal email, click the button — no separate confirmation step.

# Internal changes:

## Employee model:
- `hr.employee` gains `schedule_import_code` (Char) and computed `pending_identification` (Boolean), added to `ems_employee` in `models/employees/employee.py`.
- New `views/community/employee/search.xml` (this model had no EMS-owned search view before).
