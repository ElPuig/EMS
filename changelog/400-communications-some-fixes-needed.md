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
