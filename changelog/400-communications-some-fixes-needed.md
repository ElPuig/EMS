# What's new:

## Head of Studies, Deputy Head of Studies and Quality coordinator can now access Communications:
- `ems.notice` (Notices) is now reachable by `group_head_of_studies` (covers both HOS and
  DHOS, per the group's own comment) and `group_quality_admin` (the Quality coordinator role,
  distinct from the plain Quality team `group_quality`) - previously only
  `group_academic_admin` had any model access at all.
- Each of these users only sees the notices they personally created; Administrators and the
  Director see every notice centre-wide.
- New `unlink()` guard on `ems.notice`: a notice can only be permanently deleted while still
  in `Draft` state; once scheduled/sent/failed, it must be archived instead (applies to every
  role, including admins, since a sent notice has real delivery history worth keeping).
- New `ir.model.access.csv`/`ir.rule` rows for `ems.notice.line` mirroring the notice's own
  visibility (via `notice_id.create_uid`), since lines are only ever edited inline from their
  parent notice.

## Quality coordinator's Surveys access is now read-all / edit-own:
- The Quality coordinator (`group_quality_admin`) now sees every survey centre-wide
  (read-only for other coordinators' surveys) but can only create/edit/delete the ones they
  personally created themselves - across all 4 related models (survey, blocks, recipients,
  enrollments), not just the survey itself.
- The plain Quality team role (`group_quality`, not the coordinator) is unaffected: still
  unrestricted create/edit access to every survey, same as before.

## Choosing which student email a Notice uses:
- New `recipient_email_type` field on `ems.notice` ("Recipient email"): `Corporate` (a
  student's institutional Google Workspace address), `Personal`, or `Both` (default). Replaces
  the previous hardcoded fallback (`student.student_email or student.email`, always preferring
  corporate) with an explicit choice - `Both` sends to *both* addresses separately when a
  student has them (two recipient lines), not just a fallback pick. Only affects the student
  side of a send; families are unaffected (they only ever have one email address), and the
  field is hidden entirely on a families-only notice.
- A student with no address matching the chosen option is excluded and now surfaces a warning
  naming them, instead of being silently dropped.

## "Show only mine" default filter on Notices and Surveys:
- Head of Studies/Deputy Head of Studies and the Quality coordinator can now see every
  notice/survey centre-wide (widened from the initial "own only" read restriction above,
  same day) - but their list opens with a "Show only mine" filter already applied, same
  comfortable default as everyone else, one click away from supervising the rest. Mirrors the
  existing `only_mine` filter idiom from `ems.attendance_template`/`.attendance_session`/
  `.attendance_justification`, just defaulted on instead of off. Editing/deleting someone
  else's record is still never possible for these roles, regardless of the filter - only the
  read visibility changed.

# Fixes:

## Admins only saw their own notices instead of every notice:
- `security/rules/communications.xml`'s "users see own" rule had no group restriction (a
  "global" rule), which Odoo ANDs against every other rule instead of offering it as an
  alternative - so the "admins see all" rule was silently neutralized and an academic admin
  only ever saw the notices they personally created. Fixed by scoping the "own" rule to the
  specific non-admin groups instead of leaving it global.

## Admins had no access at all to the Surveys section:
- `group_academic_admin` had no `ir.model.access.csv` row for any of the 4 survey-related
  models, despite the "Surveys" menu already listing it as one of the menu's visible groups -
  opening it would have raised an access error. Added the missing access rows and matching
  "sees everything" record rules.

## "Both" option on a Notice's "Send to" was never actually translated:
- The `.po` entry existed but had an empty `msgstr` in both Catalan and Spanish - now
  translated, and shared with the new `recipient_email_type` field's own "Both" option.

## `TestNoticeTour` was failing on this box (and likely any non-English dev environment):
- Looked like a timing/hang issue (10s TIMEOUT, no error) but was actually a translation
  mismatch: the tour asserts on literal English button text ("Send now"), which only matches
  when the `admin` account's language is `en_US` - not guaranteed on a real dev box. Fixed the
  same way an identical issue was already fixed for the attendance tour: force `admin`'s
  language to English for the duration of the test only, restored afterward.

## The same admin-language issue was silently breaking 44 other tour tests:
- Audited all 77 `test_*_tour.py` files for the same risk (a selector matching translatable
  Odoo/EMS text, with no language forced) and fixed every one found: 45 files total (including
  the notice/attendance ones above), ~55 test methods, using the same shared fix. Extracted the
  previously-duplicated fix into `tests/common.py::force_user_language_to_english(test, user)`
  and documented the convention in CLAUDE.md so it isn't rediscovered a third time.
- Two more files log in as a freshly created fixture user rather than the real `admin` account;
  those got a lighter prophylactic fix (`'lang': 'en_US'` set directly at creation) since a new
  `res.users` record on this box doesn't reliably default to `en_US` either.
- `test_group_archive_confirmation_tour` initially still failed after this pass - not a
  separate bug, one of `TestGroupTour`'s three test methods was simply missed when the fix was
  first applied to that file. Fixed once found (via the failure screenshot, which showed the
  cog menu rendering in Spanish).

# Internal changes:

- New `TestNoticeAccessControl` (`tests/test_notice.py`) and `TestLimesurveyAccessControl`
  (`tests/test_limesurvey_header.py`) regression-cover every role/visibility combination above,
  including a real before/after check for the admin-sees-all bug.
- New unlink-guard tests on `ems.notice`, including a functional check (under an `es_ES`
  language context) that the new error message's translation actually applies at runtime, not
  just that a `.po` entry exists for it.
- Updated `docs/en/developers/communications/{notice,limesurvey}.md` with the new
  access-control tables and the root-cause writeup of both bugs above.
- New user manuals (English/Catalan/Spanish): `docs/{en,ca,es}/admin/notice.md`,
  `docs/{en,ca,es}/head_of_studies/notice.md` and `docs/{en,ca,es}/admin/survey.md` - this
  feature previously had no user-facing documentation at all in any language.
- New `recipient_email_type` tests in `tests/test_notice.py` (corporate/personal/both,
  skip+warn behaviour, both-selection-labels-translated regression) and a new tour step
  exercising the field's `<select>` widget in `static/tests/tours/notice_tour.js`.
