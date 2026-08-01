# What's new:

## Pending-identification teachers from schedule imports:
- Importing a working-schedule file (per-teacher or the general cog-menu importer) no longer fails when a row names a not-yet-hired post with a placeholder code (e.g. `X1`, `X2`) instead of a real e-mail.
- A "Pending teacher (X1)" employee is created automatically, with the schedule/subjects/attendance lists already assigned — no manual setup needed.
- Re-importing an updated file for the same still-unstaffed post (same code) updates that same employee in place, never creating a duplicate.
- These employees show a "Pending identification" indicator (Teachers list column, kanban badge, form ribbon), with a matching search filter/group-by.
- Resolving a pending teacher's real identity reuses the existing "Generate Google account" button: fill in the real name + personal email, click the button — no separate confirmation step.

# Fixes:

## Working-schedule import wizard showed a generic error popup instead of the usual red banner:
- An unresolvable group name or subject code in an uploaded schedule file raised uncaught from inside the onchange preview, so Odoo displayed it as a blocking modal dialog instead of the same in-form banner (with the Import button disabled) used for every other validation problem in this wizard (unknown teacher e-mail, missing classroom...).
- Both onchange handlers (`_onchange_file`, `_onchange_attachment_ids`) now catch that error and fold it into the same in-form banner, consistently with the rest of the wizard.
- That banner (and every other blocking, per-item problem: unknown e-mail, unresolved group/subject, missing classroom) now renders as an intro sentence + a real bullet list (one line per problem), matching the existing "these teachers already have a schedule" warning style, instead of one long comma-separated sentence.

## Import button could be clicked before file validation had actually finished:
- Attaching a file made the button visible/enabled immediately (it was only hidden once a problem was confirmed), so clicking fast enough could trigger the import before the background validation RPC returned.
- The button now starts hidden and is only ever shown once the same onchange positively confirms the file has no blocking problems - there is no window where it can render as clickable before that.

## "Pending identification" kanban badge showed on every teacher, not only pending ones:
- The badge's `t-if` read `record.pending_identification.value` - for a kanban record, `.value` is the *formatted* display value (for a Boolean field, Odoo's formatter returns an HTML checkbox markup string, which is always truthy regardless of true/false); `.raw_value` is the actual boolean and is what a conditional must use. Confirmed by reading Odoo's own `getFormattedRecord`/`formatBoolean` and by reproducing the bug live via a browser tour (a non-pending "confirmed" teacher's card also showed the badge).
- Fixed to `record.pending_identification.raw_value`, matching the `.raw_value` convention already used throughout this same view (and its `hr.hr_kanban_view_employees` parent). The pre-existing `tutorships` badge's `t-if` had the same `.value`/`.raw_value` mix-up (harmless in practice only because Char's formatter happens to return the same string) - fixed for consistency while in the area.
- Also moved the badge so it always renders on its own line directly below the employee's name (previously anchored after `job_title`, so it could end up sharing a line with the job title text when one was set).

## `devel.sh` left `hr.employee.work_email` stale after replacing real e-mails:
- `work_email` is a stored compute of `work_contact_id.email` (native Odoo); the script's raw SQL `UPDATE` on `res_partner.email` bypasses the ORM, so that cached copy on `hr.employee` never got refreshed - teachers kept showing their original (real-looking) e-mail even after the script ran.
- `devel.sh` now also refreshes `hr_employee.work_email` from the now-updated `res_partner.email` right after replacing it.

## Groups can now be archived and reactivated instead of duplicated:
- `ems.group` gains the standard Odoo `active` field (default `True`) — a group not running this course but that may come back in a future one (a cycle skipping a year, a shift suspended temporarily...) can now be archived via the Action menu (Archive/Unarchive), keeping its history (tutor, classroom, past students/schedule) instead of losing it to a delete-and-recreate cycle.
- Creating (or renaming, via `course`/`acronym`/`study_id`/`group_type`/`external_id`) a group into a name that matches an already-archived group no longer silently creates a duplicate: it raises a dialog offering a one-click "Reactivate" action (an `ir.actions.server` calling the new `action_reactivate()`) that reactivates the existing group and opens it, instead. Declining leaves everything untouched — the attempted create/rename is fully rolled back via a savepoint, nothing is created or renamed.
- Admin docs (`docs/{en,ca,es}/admin/groups.md`) and the technical reference (`docs/en/developers/contacts/group.md`) updated; new tests in `test_group.py` + a new browser tour (`ems_group_reactivate_archived_duplicate`) covering both the accept and decline paths.

# Internal changes:

## Employee model:
- `hr.employee` gains `schedule_import_code` (Char) and computed `pending_identification` (Boolean), added to `ems_employee` in `models/employees/employee.py`.
- New `views/community/employee/search.xml` (this model had no EMS-owned search view before).
