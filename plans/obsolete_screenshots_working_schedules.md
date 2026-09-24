# Plan: regenerate the working-schedules screenshots (last obsolete ones)

**Status: current as of 2026-09-24, not started.** Deferred by the developer to its own, final
branch after `488-documentation-images-phase-3`, which ships everything else. Re-check
`docs/assets/admin/working-schedules-*` and `tests/test_docs_screenshots*.py` before starting, in
case something moved in between.

## Where things stand

The "obsolete screenshots" review of 2026-09-24 is done except for this group:

- Every screenshot a test regenerates (74) was re-run and pixel-compared with the published one:
  none had outdated content.
- Every hand-made screenshot was checked and, where outdated or showing real (blurred) people,
  replaced by a test-generated one with made-up data and the numbered callouts the manuals cite
  (see the branch's changelog for the list).
- Out of scope for good: `docs/assets/families/gmail_password_recovery-*` (7) - Google's own UI,
  not EMS.

## What is left: 12 admin images, `docs/{en,ca,es}/admin/working-schedules.md`

All were made with fixtures but **in the English UI** (dialog titled "Odoo", English labels), and
the Catalan/Spanish manuals reuse them - so they are the only screenshots not shown in Catalan.

| Image | Screen |
|---|---|
| `working-schedules-edit-cards.png` | Two cards on the same weekday, each with its own date range (teacher's Schedule tab, edit mode) |
| `working-schedules-midcourse-handoff.png` | Both subjects side by side on Monday's read-only weekly grid |
| `working-schedules-import-01-welcome.png` | Import wizard, Welcome step with a planner file attached |
| `working-schedules-import-02-resolve-groups.png` | Resolve groups: an unresolved group name from the file |
| `working-schedules-import-02b-resolve-groups-classroom.png` | Resolve groups: a resolved group still missing its classroom |
| `working-schedules-import-03-resolve-subjects.png` | Resolve subjects: a subject/group mismatch |
| `working-schedules-import-04-resolve-teachers.png` | Resolve teachers: the New checkbox before the Teacher dropdown |
| `working-schedules-import-05-file-conflicts.png` | File conflicts: a card with the bulk resolution dropdown |
| `working-schedules-import-06-existing-schedule-conflicts.png` | Existing schedule conflicts: a File entry vs a Database session |
| `working-schedules-import-07-overall-summary.png` | Overall summary |
| `working-schedules-import-07b-overall-summary-download.png` | The summary CSV download link |

## How to do it

- Mechanism and practical rules: `docs/en/developers/shared/testing.md`, section
  "DocsScreenshotMixin" (marks, `mouse:` clicks, union clips, scoping native actions to fixtures,
  wizard records created `with_user(<login user>)`).
- Add a method (or two) to `tests/test_docs_screenshots_admin.py`, logging in as `doc_shot_admin`
  (Catalan).
- The import wizard's screens are driven by planner XML files: reuse the builders in
  `tests/test_working_schedules_import_wizard.py` (`_xml_file*`, `_attachment_ids`,
  `_xml_two_teachers_same_slot`, `_create_self_conflict_setup`...) and the fixtures of
  `tests/test_working_schedules_import_wizard_tour.py`, which already reach each screen (unknown
  group, group without classroom, subject mismatch, unknown teacher, conflicts). Build one wizard
  per screen server-side, advance it to the wanted step, and open it by `res_id` in a
  `target='new'` action. The wizard's `create()` needs a current course on the company.
- The two schedule images: the teacher's Schedule tab, built with
  `resource.calendar.apply_schedule_changes()` like `test_capture_working_schedules` in
  `tests/test_docs_screenshots_teachers.py` (two blocks on the same weekday with different date
  ranges for the mid-course handoff).
- Check every image for English text: this wizard's own labels have never been captured in
  Catalan, so expect to find `.po` gaps and fix them in the same branch (the manual's own text
  names the screens in English in `en/` only).
- Delete this file once done.
