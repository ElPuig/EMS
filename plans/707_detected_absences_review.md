# Issue #707 handoff: detected absences reviewed by the Head of Studies first

**Status (2026-10-25): code written in a cloud session WITHOUT Odoo. Nothing in this branch has
ever been run: not `./upgrade.sh`, not a single test, not the tour.** This file tells the local
session (VSCode, with Odoo and the `ems` dev database) what is left to do, in order. Delete it
when the issue is closed (CLAUDE.md, "Design plans").

Issue: https://github.com/ElPuig/EMS/issues/707 (its body is the original spec; the decisions
below supersede it where they differ). Branch: `707-detected-absences-review`, from `main` at
`v18.0.0.40.0`.

## Decisions taken with the developer (don't reopen them)

1. **Both origins alike.** Informed entries (`origin = 'informed'`) go through the same review as
   the missing check-in ones: no automatic reminder to the teacher, review activity for the
   approver. (The issue body said "No check-in only, to confirm": confirmed the other way.)
2. **Create absence = a draft on the detected absence, not an `hr.leave`.** The teacher must accept
   the responsible declaration themselves, so nobody files the request for them. Odoo 18's
   `hr.leave` has no draft state (it starts as "To Approve", which already blocks overlaps, shows
   on the guard duty board, tells the chiefs and opens the approval activity), so the draft is the
   entry's own `prepared` state + `proposed_leave_type_id`; the teacher's "Request the absence"
   opens the usual form prefilled with the type, day and hours, and they send it as always. The
   issue's "approved at once" / "who may approve it" points no longer apply.
3. **Migration folder `migrations/18.0.0.40.1/`** (the developer: "prepare it for a fix, v40.1";
   it may still become a minor). The manifest version was NOT bumped (CLAUDE.md): the migration
   only runs once the release branch carries `18.0.0.40.1`. If the release is a minor, rename the
   folder.

## What the branch contains

See `docs/en/developers/employees/absence.md`, section "Detected absences", for the full design
(states, the review, the four actions, reminders, access). In short:

- `models/employees/absence_pending.py`: states `pending` (To review) / `justification_requested`
  / `prepared` / `linked` / `corrected` / `discarded`; `active`, `requested_date`,
  `proposed_leave_type_id`, `can_review`; review activity on `create()`; the four actions;
  reminders only for `justification_requested`/`prepared`, counted from `requested_date`.
- `models/employees/absence_pending_prepare_wizard.py`: the "Create absence" wizard.
- `models/attendance/guard_duty_board.py`: the board reads every unresolved state.
- Views, rules (`rule_absence_pending_own` now hides entries the teacher wasn't involved in), ACL
  for the wizard, activity type `ems.mail_activity_absence_review`.
- `migrations/18.0.0.40.1/post-migrate.py`.
- Tests: `tests/test_absence_detection.py`, `tests/test_absence_pending.py`,
  `tests/test_absence_review.py` (new), `tests/test_task_digest.py`, `tests/test_access_matrix.py`,
  tour `tests/test_absence_pending_tour.py` + `static/tests/tours/absence_pending_tour.js`.
- Manuals ca/es/en, `.po` entries, `changelog/707-detected-absences-review.md`.

## What the cloud session could check

Python syntax (`py_compile`), XML well-formedness, `.po` parsing (`polib`), `pylint
--enable=redefined-builtin` on the touched files, and a careful reread of the diff. Nothing else.

## To do locally, in this order

1. `git fetch origin && git checkout 707-detected-absences-review`.
2. **Bump the manifest to `18.0.0.40.1` locally only to exercise the migration, or not at all**:
   on this dev DB the migration only runs if the stored version is lower than the manifest's.
   Recommended: run `./upgrade.sh` once as is (schema, data, views load), then test the migration
   on a throwaway copy if needed. Never commit a version bump without the developer's go-ahead.
3. `./upgrade.sh 2>&1 | tee <scratchpad>/upgrade.log` and look for WARNING/ERROR/CRITICAL.
   Likely first-run failures to look at: the view arch (`statusbar_visible`, the list header
   buttons), the new record rule domain, the activity type CSV row, the wizard's view.
4. Scoped tests (each one, output to a file):
   `./test.sh TestAbsenceDetection`, `./test.sh TestAbsencePending`, `./test.sh TestAbsenceReview`,
   `./test.sh TestTaskDigest`, `./test.sh TestAccessMatrix`, `./test.sh TestGuardBoardUnchecked`,
   `./test.sh TestGuardDutyBoard`, then the tour `./test.sh TestAbsencePendingTour` (refresh any
   open backend tab first). Fix what fails; the "assumptions to verify" below are where to look
   first.
5. Translations: export `ca_ES`/`es_ES` (CLAUDE.md, "All literals must be translatable"), diff
   against the `.po` files (entries were added by hand here, so check nothing is missing and the
   `#:` references match), `./upgrade.sh`, read back a few labels in the DB (the new state labels,
   the activity type name, the wizard's fields), `./test.sh TestI18nCoverage`.
6. LanguageTool: `scripts/i18n/lt_check.py --since origin/main` (the ca/es manuals and `.po`
   entries were written without it).
7. Quality audit (CLAUDE.md, "Quality audit when closing") and permission audit (CLAUDE.md,
   "Permission audit") of Absences > Management > Detected absences for every role; efficiency of
   `create()` (review activity per entry) and of the reminder cron, measured cold on the dev DB.
8. Screenshots for the Head of Studies manual if wanted (`tests/test_docs_screenshots_head_of_studies.py`):
   the list with the Actions dropdown and the "Create absence" wizard. None were added here.
9. Update `changelog/707-detected-absences-review.md` with anything that changed, delete this
   file, push, closing checklist table, card to "Ready to merge".

## Assumptions to verify (written without being able to run Odoo)

- `hr.leave.default_get()` keeps `default_holiday_status_id` from the context even though EMS
  calls super with `holiday_status_display_name=False` (it should: that flag only stops Odoo from
  picking a type itself). Checked by `test_the_prepared_request_opens_with_its_type`.
- `hr.attendance._check_validity`: creating a closed attendance in the past, or moving a check-in
  earlier, while the teacher has other attendances (an open one today, one later that day).
  Covered by `TestAbsenceReview`'s correction tests; if it raises in a real case, the action
  raises a `UserError` naming the teacher.
- Archiving with `active = False`: `mail.activity.mixin` unlinks the activities of an archived
  record; the review activity is marked done before archiving, so it should show as done, not
  vanish. Check in the test that the activity is not left open.
- The list's header buttons (`o_ems_header_actions`) call `type="object"` methods on the selected
  records; they are restricted with `groups=` (per-record rights can't drive a list header
  button), so a Department Chief gets no buttons and the server check covers the rest.
- The new `active` field and the new `state` values on an existing table: Odoo adds the column
  with its default (`True`) for existing rows; `post-migrate.py` then moves the old entries.
- `mail_activity_quick_update=True` keeps the review activity from emailing the approver (the
  digest is their notice), as in `_ems_report_at_workday_start()`.
