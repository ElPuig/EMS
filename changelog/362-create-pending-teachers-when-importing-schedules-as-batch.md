# What's new:

## Reason-aware "Archived" ribbon for students and teachers, plus a new student Expulsion outcome:
- Archived students now show **why** at a glance instead of a generic "Archived": a green **Alumni** ribbon (graduated), an orange **Withdrawal** ribbon, or a red **Expelled** ribbon — on both the form and the kanban card.
- Archived teachers show their actual departure reason the same way (**Retired**, **Resigned**, a new **Transfer** reason for teachers reassigned to a different centre, or **Fired**), also on both form and kanban — teachers' kanban previously showed nothing at all for an archived employee.
- A single reusable field widget (`ems_archived_reason_ribbon`) drives all of this for both models, reading a plain label + hex color pair (`archived_reason_label`/`archived_reason_color`) computed per model — see `docs/en/developers/contacts/contact.md` and `docs/en/developers/employees/employee.md`.
- `hr.departure.reason` gains a `color` field (same hex color-picker widget already used for `ems.attendance_status`/`ems.role`), so an admin can pick the ribbon color for each departure reason, including any new ones added later.
- New: the withdrawal wizard now asks the admin to choose between **Withdrawal** and **Expulsion** when archiving a student (voluntary vs. administrative withdrawal stays a free-text note, not a separate option). The confirm button's label adapts to the choice ("Withdraw"/"Expel"). Expulsion always results in `contact_type = 'expelled'`, even for a student who had already graduated once.
- A full audit of every place `contact_type`/`exit_type` was filtered or branched on (menu domains, search filters, `transition_status`, Google Workspace account suspension, `_academic_result()`, category sync) was done before adding the new `expelled`/`expulsion` values, to make sure none of them silently missed the new case.

## Pending-identification teachers from schedule imports:
- Importing a working-schedule file (per-teacher or the general cog-menu importer) no longer fails when a row names a not-yet-hired post with a placeholder code (e.g. `X1`, `X2`) instead of a real e-mail.
- A "Pending teacher (X1)" employee is created automatically, with the schedule/subjects/attendance lists already assigned — no manual setup needed.
- Re-importing an updated file for the same still-unstaffed post (same code) updates that same employee in place, never creating a duplicate.
- These employees show a "Pending identification" indicator (Teachers list column, kanban + form ribbon in a soft, non-garish yellow), with a matching search filter/group-by. The kanban indicator started as a badge under the name; changed to a ribbon (2026-08-01) to match the other reason-aware ribbons added to that same kanban right after it.
- Resolving a pending teacher's real identity reuses the existing "Generate Google account" button: fill in the real name + personal email, click the button — no separate confirmation step.

# Fixes:

## Every reason-aware ribbon showed the default red, never the actual color:
- `archived_reason_color` (Alumni's green, Withdrawal's orange, a departure reason's own color...) was only ever referenced through the `ems_archived_reason_ribbon` widget's own `color_field` option, never as its own declared `<field/>` in the view - and, unlike Many2many field widgets, this field registry's `relatedFields` mechanism turns out to only auto-fetch for x2many/many2one_reference field types in this Odoo version (confirmed by reading `web/static/src/views/fields/field.js`), never for a plain `Char` like this one. The color value was therefore never actually reaching the client, and the widget's own default-red fallback showed every time, regardless of the real color.
- Fixed by explicitly declaring `<field name="archived_reason_color" invisible="1"/>` alongside the ribbon field in all four views (`contact/{form,kanban}.xml`, `employee/{form,kanban}.xml`). New tour steps assert the actual rendered color (not just the text) to catch this specific regression going forward.

## Working-schedule import wizard showed a generic error popup instead of the usual red banner:
- An unresolvable group name or subject code in an uploaded schedule file raised uncaught from inside the onchange preview, so Odoo displayed it as a blocking modal dialog instead of the same in-form banner (with the Import button disabled) used for every other validation problem in this wizard (unknown teacher e-mail, missing classroom...).
- Both onchange handlers (`_onchange_file`, `_onchange_attachment_ids`) now catch that error and fold it into the same in-form banner, consistently with the rest of the wizard.
- That banner (and every other blocking, per-item problem: unknown e-mail, unresolved group/subject, missing classroom) now renders as an intro sentence + a real bullet list (one line per problem), matching the existing "these teachers already have a schedule" warning style, instead of one long comma-separated sentence.

## Import button could be clicked before file validation had actually finished:
- Attaching a file made the button visible/enabled immediately (it was only hidden once a problem was confirmed), so clicking fast enough could trigger the import before the background validation RPC returned.
- The button now starts hidden and is only ever shown once the same onchange positively confirms the file has no blocking problems - there is no window where it can render as clickable before that.

## Pending-identification info banner truncated a not-yet-hired teacher's full name to its first word:
- Both the blue "pending identification" banner and the actual pending-employee creation identified a not-yet-known teacher by naively taking the first whitespace-separated token of the planner row's raw `name` attribute, assuming the shape was always `"<code-or-email> <discardable label>"`. That assumption holds for a short placeholder code (`"X1"`) but not when the planner instead puts the person's own real, multi-word name in that field (e.g. `"Fulanito Menganito"`) - the old code silently kept only `"Fulanito"`.
- Fixed with a proper check (`_teacher_identifier`, `models/employees/working_schedule.py`): search the whole value for an actual e-mail pattern; if none is found, keep the entire (stripped) value as the identifier instead of just its first token. Applied uniformly everywhere a teacher node's `name` is parsed (`_onchange_file`, `_onchange_attachment_ids`, `create()`).
- The blue banner (`info_message` → `info_html`) now renders as a real bullet list too, matching the other banners in this wizard, instead of one comma-separated sentence.
- All four of this wizard's list banners (blocking issues, pending-identification, overridden teachers, external conflicts) now lay out their bullet list in up to 3 CSS columns (`ems_wizard_bullet_list` in `ems.css`) instead of one long single-column list, since these are short flat items and a long list was wasting the dialog's horizontal space - collapses to 1 column on narrow screens.
- Fixed a follow-up regression from the 3-column layout above (reported 2026-08-01): a single long line (e.g. one unknown-e-mail error, or one conflict line) had its own wrapped text visually split across all 3 columns instead of staying together in the first one - CSS multi-column's default fragmentation behaviour. Fixed with `break-inside: avoid` on each list item; verified in a real browser via a new tour assertion (bounding-box width check) rather than trusting the CSS fix by reasoning alone.

## Working-schedule import wizard looked hung while a file was being processed:
- Attaching a file to either upload field (the per-employee scoped `file` or the general cog-menu's `attachment_ids`) triggers a server-side onchange that parses the whole planner XML - slow enough, with zero visual feedback, to look hung.
- Both fields now use new thin widget subclasses (`ems_blocking_binary`/`ems_blocking_many2many_binary`, `static/src/js/backend/working_schedule_import_blocking_upload.js`) that wrap the upload with Odoo's own `ui.block()`/`.unblock()` overlay (spinner + "Reading and validating the schedule file, please wait..." message) - the same native mechanism Odoo already uses for long button actions, not a bespoke spinner. See `docs/en/developers/employees/working_schedule.md`.

## "Pending identification" kanban badge showed on every teacher, not only pending ones:
- The badge's `t-if` read `record.pending_identification.value` - for a kanban record, `.value` is the *formatted* display value (for a Boolean field, Odoo's formatter returns an HTML checkbox markup string, which is always truthy regardless of true/false); `.raw_value` is the actual boolean and is what a conditional must use. Confirmed by reading Odoo's own `getFormattedRecord`/`formatBoolean` and by reproducing the bug live via a browser tour (a non-pending "confirmed" teacher's card also showed the badge).
- Fixed to `record.pending_identification.raw_value`, matching the `.raw_value` convention already used throughout this same view (and its `hr.hr_kanban_view_employees` parent). The pre-existing `tutorships` badge's `t-if` had the same `.value`/`.raw_value` mix-up (harmless in practice only because Char's formatter happens to return the same string) - fixed for consistency while in the area.
- Also moved the badge so it always renders on its own line directly below the employee's name (previously anchored after `job_title`, so it could end up sharing a line with the job title text when one was set).

## `devel.sh` left `hr.employee.work_email` stale after replacing real e-mails:
- `work_email` is a stored compute of `work_contact_id.email` (native Odoo); the script's raw SQL `UPDATE` on `res_partner.email` bypasses the ORM, so that cached copy on `hr.employee` never got refreshed - teachers kept showing their original (real-looking) e-mail even after the script ran.
- `devel.sh` now also refreshes `hr_employee.work_email` from the now-updated `res_partner.email` right after replacing it.

## Archiving a group with active students now asks for a single, clear confirmation:
- Archiving is always allowed and never removes/unenrolls anyone (a group's member list doesn't live on the group itself), but silently archiving a group people are still actively using could be confusing. Archiving one that still has active `main_student_ids`/`reinforcement_student_ids` now shows a clear 4-paragraph confirmation explaining exactly that (no student is removed, the group just stops showing in default views, and the end-of-course transition will still clear it if that's the reason), with **Proceed**/**Cancel** actions, instead of archiving silently.
- Declining leaves the group completely untouched.
- Exactly one dialog shows, not two or three: earlier iterations first fixed a redundant double-confirmation (Odoo's own generic "are you sure?" followed by our own), then fixed the remaining dialog's cosmetics (a fixed "Odoo Warning" title and a "Close" button that couldn't be relabeled - both inherent to Odoo's generic `RedirectWarning` dialog templates). The final design has `EmsGroupFormController`/`EmsGroupListController` (`static/src/js/backend/group_{form,list}_controller.js`) call a new `get_archive_confirmation_message()` RPC *before* ever attempting the archive, showing their own properly-titled `ConfirmationDialog` only when needed - Odoo's generic dialogs are never shown at all on this path. `write()`'s original guard remains as a safety net for any non-UI caller (a direct ORM call, an import script).
- `views/community/group/{form,list}.xml` now declare the `active` field (invisible) - discovered empirically that Odoo's Archive/Unarchive Action-menu item only appears on a view that declares this field itself, not just on the model.
- The group's form now shows the standard Odoo "Archived" ribbon when inactive (same `web_ribbon`/`invisible="active"` pattern used natively across Odoo core), so an archived group is visible at a glance, not just via the Action menu's label.

## "Archived" ribbon rolled out across every archivable model:
- Following the same standard Odoo pattern just added to `ems.group`, the "Archived" ribbon (`web_ribbon`, `invisible="active"`) now also shows on: `hr.employee`, `hr.department`, `ems.strike_reason`, `ems.attendance_status`, `ems.non_teaching_type`, `ems.strike`, `ems.attendance_correction`, `ems.attendance_template`, `ems.attendance_justification`, `ems.attendance_schedule`, `ems.attendance_session_header`, `ems.enrollment`, `ems.teaching`, `ems.grade_session`, `ems.notice`, `ems.limesurvey_header`, `ems.limesurvey_block`, `ems.limesurvey_recipient`.
- `res.partner` already had the native "Archived" ribbon (`base.view_partner_form`); for a **student** specifically it now says **"Alumni"** or **"Withdrawal"** instead (matching `contact_type`'s own selection labels) - clearer than a generic "Archived", and consistent with how the rest of the app already distinguishes the two. Other archived partners (family, provider, applicant) keep the native generic ribbon unchanged.

## Groups can now be archived and reactivated instead of duplicated:
- `ems.group` gains the standard Odoo `active` field (default `True`) — a group not running this course but that may come back in a future one (a cycle skipping a year, a shift suspended temporarily...) can now be archived via the Action menu (Archive/Unarchive), keeping its history (tutor, classroom, past students/schedule) instead of losing it to a delete-and-recreate cycle.
- Creating (or renaming, via `course`/`acronym`/`study_id`/`group_type`/`external_id`) a group into a name that matches an already-archived group no longer silently creates a duplicate: it raises a dialog offering a one-click "Reactivate" action (an `ir.actions.server` calling the new `action_reactivate()`) that reactivates the existing group and opens it, instead. Declining leaves everything untouched — the attempted create/rename is fully rolled back via a savepoint, nothing is created or renamed.
- Admin docs (`docs/{en,ca,es}/admin/groups.md`) and the technical reference (`docs/en/developers/contacts/group.md`) updated; new tests in `test_group.py` + a new browser tour (`ems_group_reactivate_archived_duplicate`) covering both the accept and decline paths.

# Internal changes:

## Employee model:
- `hr.employee` gains `schedule_import_code` (Char) and computed `pending_identification` (Boolean), added to `ems_employee` in `models/employees/employee.py`.
- New `views/community/employee/search.xml` (this model had no EMS-owned search view before).

## Migration:
- `migrations/18.0.0.22.0/pre-migrate.py`: clears the stored `noupdate` flag on `hr.departure.reason`'s three native records (`hr.departure_fired/resigned/retired`) so `data/main/hr.departure.reason.csv`'s new `color` values can actually reach them on upgrade — confirmed empirically that they were silently ignored otherwise (native `hr` module data ships `noupdate="1"`).
- New `hr.departure.reason` record `ems.departure_reason_transfer` ("Transfer").

## New files:
- `models/employees/departure_reason.py` (`hr.departure.reason` `color` field), `views/community/employee/departure_reason.xml` (color widget on the native list/form).
- `static/src/js/backend/archived_reason_ribbon_field.js` + `static/src/xml/backend/archived_reason_ribbon_field.xml` (the shared `ems_archived_reason_ribbon` field widget).
- `tests/test_departure_reason.py`, `tests/test_employee_archived_reason_tour.py` + `static/tests/tours/employee_archived_reason_tour.js`.
