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

## Customizable Notice signature, and replies now go to the actual sender:
- `ems.mail_notice` used to hardcode "Kind regards, {centre name}" directly into every Notice
  email, in English only regardless of the recipient's language. New
  `res.company.notice_email_signature` (Settings → EMS Management, translatable) sets a
  centre-wide default; each `ems.notice` gets its own editable copy (`signature` field) at
  creation time, so admins/HOS/DHOS/Quality coordinator can customize or clear it per
  communication without touching the shared default.
- Replies to a Notice used to go to a fixed technical address (`ems@elpuig.xeill.net`, the
  same for every sender) - `Reply-To` now resolves to whoever actually sent the notice
  (`sent_by`, falling back to `create_uid`). The visible "From" address stays the fixed
  technical one on purpose - the configured SMTP relays only accept sending as that exact
  address (`ir_mail_server.from_filter`), so that part can't safely change.

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

## The new "Show only mine" default filter broke 2 pre-existing survey tours:
- `TestLimesurveyHeaderTour`/`TestLimesurveyRecipientTour` seed their survey fixture via the
  plain (superuser) test env, so it had `create_uid=SUPERUSER_ID` - invisible to the tour's real
  `admin` login under the new default "Show only mine" filter (empty list, tour times out
  finding the seeded row). Fixed by creating those fixtures `with_user(admin)` instead - found
  only by running the full, unscoped `./test.sh` gate, since scoped ORM tests never render a
  search view's default filter at all.

## Seeding a new translatable `Html` field's initial multi-language value needed a non-obvious API:
- `res.company.notice_email_signature`'s initial value (all 3 languages) had to bypass two
  ORM approaches that looked correct but weren't: a loop of `with_context(lang=X).write(...)`
  calls cascades a new value onto every language that isn't "manually customized" yet,
  clobbering earlier writes; `record.update_field_translations()` silently does nothing on an
  `Html` field's still-empty value, since `fields.Html` uses a callable `translate` (term-by-
  term diffing, needs a pre-existing value) rather than the plain `True` that API expects. A
  direct SQL jsonb write is what actually works for a one-time seed like this - documented in
  `docs/en/developers/communications/notice.md` so this isn't rediscovered.

## update.sh's git pull could break a deploy over an unrelated branch's stale ref:
- A bare `git pull` fetches every branch from the remote, not just the one checked out - if
  any other branch's local remote-tracking ref/reflog is stale or permission-broken (as
  happened in production for release v18.0.0.23.2, over a completely unrelated branch), the
  whole `git fetch` fails and `set -e` aborts `update.sh` before it ever reaches `upgrade.sh`,
  even though the branch actually being deployed (`main`) would have fetched fine on its own.
  Now scoped to `git pull origin "$(git -C "$dir" symbolic-ref --short HEAD)"` - only ever
  touches the checked-out branch's own ref, in every module repo (this one and both OCA ones).
  Verified for real: ran the updated script end-to-end, which pulled genuine upstream changes
  into the `queue`/`partner-contact` OCA repos and correctly no-op'd on this repo's own
  already-up-to-date branch.

## Curriculum models crashed with a raw database error on the stock "Duplicate" action:
- `ems.study`/`ems.subject`/`ems.level`/`ems.content`/`ems.criteria`/`ems.outcome` each have a
  unique code/acronym constraint but no `copy()` override, so clicking "Duplicate" raised
  `UniqueViolation` instead of working or failing cleanly. Disabled duplication on all 6
  instead of writing a custom `copy()` - can revisit if a future curriculum change genuinely
  needs cloning one of these.

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
- New tests for `signature`/`reply_to` (`tests/test_notice.py`): company-default inheritance,
  per-notice editability, rendered `body_html` uses the notice's own signature (not a
  hardcoded one), `reply_to` resolves to `sent_by` with a `create_uid` fallback. New tour step
  confirming the Signature field is pre-filled on a new notice.
- Manifest bumped to `18.0.0.23.3`; new `migrations/18.0.0.23.3/post-migrate.py` backfills
  `notice_email_signature` for existing installations.
- New tour steps on `study_tour.js`/`subject_tour.js`/`level_tour.js` asserting "Duplicate" is
  absent from the Action menu; verified as a real (not vacuous) check via `git stash` on the
  view files - same tours fail without the `duplicate="0"` fix, pass with it.
- CLAUDE.md's "PR changelog" section: re-added the "no manual line wraps in the final delivered
  document" rule, which had been reverted earlier for an unrelated branch-deletion reason.
