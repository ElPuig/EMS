# Breaking changes

## Portal authorization record rule is no longer `noupdate`:

`rule_ems_authorization_portal` (`security/rules/portal.xml`) moved out of the
`<data noupdate="1">` block into a plain `<data>` one, so its domain now tracks the data model
on every upgrade. A centre that had edited that rule's `domain_force` by hand will lose that
edit on the next upgrade. This was necessary, not cosmetic: the rule had to change with the
model (an authorization can now exist without an enrollment), and `noupdate` made that edit a
silent no-op. `migrations/18.0.0.25.0/pre-migrate.py` clears the `noupdate` flag the existing
record still carries from its old block, which `models._load_records()` would otherwise keep
honouring regardless of how the file is written.

Worth knowing for anyone who changes a record in a `noupdate="1"` block in the future:
`odoo/tools/convert.py::_tag_record()` skips an already-existing record based on the FILE's
noupdate flag alone (around line 347), before `_load_records()` ever gets to check the record's
own `ir_model_data.noupdate`. Clearing the stored flag from a migration is therefore not enough
on its own. Verified empirically on the dev database: clearing the stored flag while leaving the
block as `noupdate="1"` changed nothing at all.

# What's new

## Authorizations can be sent to students during the school year:

New authorizations come up once the course is already running - published by the Departament
d'Educació, or decided in a tutoring meeting - and until now every `ems.authorization` had to
hang off an enrollment (`enrollment_id` was `required=True`), which for the running course is
already confirmed and closed. An authorization is now anchored on the student and the academic
year (`partner_id`, `course_id`), with `enrollment_id` set only for the ones that arrive through
the enrollment process.

## Send Authorizations assistant:

New `ems.authorization.send.wizard` (Academic management > Authorizations > Send Authorizations,
and as an Actions entry on the students list). Recipients are chosen two ways: the students
selected in a list, or groups/studies/levels picked in the assistant - of which at least one is
required, so an empty choice never means the whole centre. Only forms marked as sendable during
the course are offered, the groups/studies/levels on offer are limited to the scope of the forms
being sent, and each student only receives the forms whose own scope matches them (anyone picked
by hand outside it is reported and skipped). Everything resolves through the enrollments of the
selected academic year, so ex-students still attached to a group record are never asked for
anything. A student already holding that (course, authorization) - by either route - is skipped
and reported, never asked twice and never reset. Restricted to the secretary's office, the
academic administration and the head of studies.

A third route, "each template's own scope", existed in the first iteration and was removed after
testing by hand: a form with no scope, or a wide one, silently targeted every enrolled student it
covered.

## Email notification, one per student:

New trilingual `mail.template` `email_template_authorization_send`, sent once per student per
batch and listing every authorization in it, rather than one email per authorization. An adult
student is emailed himself; a minor's family is emailed instead, via the
`_ems_notification_recipients()` rule shared with the portal access wizard. Queued rather than
sent inline, so a whole-level batch does not block the request.

## Authorizations follow-up list:

New backend list/form/search for `ems.authorization` itself (Academic management > Authorizations >
Responses), opening flat on the running academic year. Filters for pending/accepted/rejected and
for sent-during-the-course vs from-an-enrollment, group by authorization, student, year or status,
and a searchable `group_id` (related to the student's main group).

## `apply_on` on the authorization template:

Two independent flags replace what was, in the first iteration, a single `apply_on` selection:
`apply_on_enrollment` (default on) and `sendable_during_course`. A form may take both routes, and
`_check_has_a_route()` rejects one that takes neither. Both are needed together in practice:
"Apply to Pre-Enrollments" only reaches draft/sent enrollments, so a form created once part of the
enrollments were already confirmed (several of this centre's June forms) can only reach those
students if it can also be sent by hand. A form with `apply_on_enrollment` off is invisible to all
four automatic-attachment paths - `create()`, `action_apply_to_open_enrollments()`,
`action_remove_from_open_enrollments()` and `sale.order._get_authorization_commands()`. That last
one is the important one: without it, the next onchange on any draft enrollment, including one for
the following course, would pull in a form created mid-year for a different one. The template list
now opens flat with both flags as columns; grouped by level and collapsed, it showed nothing of
which route each form takes. On the form, both toggles save with the form rather than on click:
switching "applies to enrollment" off first otherwise saved a form with neither route and tripped
the constraint before the other flag could be switched on.

## Tutors send authorizations to their own students:

Tutors reach Academic management > Authorizations too: they send forms from the catalogue to their
own students - picking some of them, or their own groups; never a whole study or level - and follow
up the answers in Responses, which for them lists their own students' authorizations only. The
catalogue itself (the Configuration section) stays with the secretary's office, the academic
administration and the head of studies. Enforced on the server, not only in the pickers: the wizard
drops any student who is not the tutor's, and the Responses screen decides its domain in Python,
because every teacher could already read every authorization through a pre-existing record rule.

# Changes

## Portal: "Enrollment and authorizations":

The portal's enrollment page is renamed on the home card and in the navigation bar, and now
shows the authorizations block on the confirmed-enrollment page too - it only ever appeared on
the draft one, which is exactly the page a student never sees again once their enrollment is
settled. The block (list, help modal, one response modal per authorization, client-side check on
the required data fields) was extracted into a shared QWeb template used by both pages, so they
cannot drift. The route `/my/gestion-matriculas` is unchanged: published emails and manuals link
to it.

A pending authorization sent during the course deliberately does not block confirming an
enrollment: both gates (`sale.order.action_confirm()` and the portal's own confirm) read the
enrollment's own one2many, and a test now pins that.

## Portal layout of the authorizations block:

On a confirmed enrollment the block sits right under the enrollment details, as section 2, with
payment and communications renumbered after it. It carries its own top and bottom margin, since
some of the cards around it express their spacing as `mt-` rather than `mb-` and left it glued
to the card above. It also renders for a student with no enrollment for the course being
enrolled into: an authorization sent during the course hangs off the student, and that case
previously fell inside the page's "no enrollment" branch and showed nothing.

## Student file reads the student's own authorizations:

The four authorization badges and the Secretary tab's list now read `ems.authorization` by
student and academic year instead of walking the enrollment, so an authorization accepted
mid-year counts. The list stays scoped to the year in force, which keeps the invariant that it
can never look empty next to a green badge. `auth_share`'s consumers (attendance notifications,
strikes, notices) are unaffected: the semantics only widen.

`res.partner._ems_course_in_force()` is per student, not per centre - it reads the course off
`_ems_enrollment_in_force()` and only falls back to the centre's running course when the student
holds no enrollment at all. Getting this wrong re-broke the four existing tests covering the
122-of-122 SMX students case during development; the per-centre shortcut is what caused that bug
originally. `_ems_running_course()` is the per-centre answer, used for the assistant's default.

## Head of studies reaches the authorization forms:

Authorizations have a submenu of their own under Academic management, instead of being mixed into
Enrollment: Send Authorizations and Responses first, then a Configuration section holding
Authorization Forms (moved out of the enrollment Configuration menu, same xmlid). The whole submenu
is gated to academic admin, secretary and head of studies, so the head of studies reaches the forms
without being given the enrollment Configuration menu, which is back to exactly what main has. They
get full CRUD on the authorization template models, plus a record rule of their own on
`ems.authorization`: without it they would inherit only the teacher's read-only rule and the tutor's
own-students-only one (rules of different groups are ANDed), so they could not send an authorization
to a student they do not tutor.

# Internal changes

## Recipient resolution extracted onto `res.partner`:

`_resolve_recipients()`/`_family_contacts()` moved off `ems.portal.access.wizard` to
`res.partner._ems_notification_recipients()`/`_ems_family_contacts()`
(`models/contacts/portal.py`), since both wizards need the identical "adult himself, minor's
family instead" rule. Not `ems.base`: `res.partner` deliberately does not inherit it (the
`channel_ids` table clash). This also removed a real duplicate -
`get_portal_inner_circle_ids()` was running the same `res.partner.relation.all` search inline.

## Uniqueness of standalone authorizations:

`ems_authorization_unique_standalone`, a partial unique index on
`(partner_id, course_id, template_id) WHERE enrollment_id IS NULL`, created from `init()` the
same way `sale.order.init()` already does. Partial on purpose: an enrollment-bound row is
already keyed by its own enrollment, and a cancelled enrollment may legitimately coexist with an
active one for the same (student, course), so a blanket index would not even build on real data.
The existing `unique(enrollment_id, template_id)` constraint is untouched and imposes nothing on
standalone rows, PostgreSQL treating NULLs as distinct.

## `partner_id`/`course_id` are plain stored fields, not stored computes:

They are derived from the enrollment in `create()` (and in `write()` when `enrollment_id`
changes), with an `@api.onchange` for the form, rather than by a stored compute. A stored compute
that must preserve a value the assistant set has no safe way to read its own current value
without risking recursion, and the explicit version keeps the backfill in exactly one place -
the migration. Neither field is `required=True`: Odoo attempts `SET NOT NULL` during
`_auto_init`, before `post-migrate.py` can backfill, and `sql.set_not_null()` swallows that
failure with a warning - so the constraint would be silently absent on every upgraded database
and present on every fresh one. `_check_target()` covers both paths identically.

## Certificate report and filename:

`report_authorization_certificate` reads the student, year and study off the authorization
itself, hides the enrollment-code row when there is none, and no longer hardcodes "Responded
from: Student Portal" - it distinguishes a portal response from a backoffice one by
`response_uid.share`. `_certificate_filename()` falls back to the academic year when there is no
enrollment code to name the file after.

## User and developer documentation:

Trilingual manuals: `docs/{en,ca,es}/secretary/authorizations.md` (creating a form and choosing its
routes, sending to selected students or to groups/studies/levels, what the family receives,
following up the answers, answering on a family's behalf), linked from the secretariat index and
from the head of studies' one - the screens are identical for both roles, so it is one manual
referenced twice; and a new `docs/{en,ca,es}/tutors/authorizations.md` for tutors (sending to their
own students or groups, following up their own students' answers), linked from the tutors index.
`manual-portal-alumne.md` gains an "Answering an authorization" step in all three languages, and
`manual-confirmacio-matricula.md` follows the portal page's new name. The developer reference covers
the two route flags and their four filter points, the scope-limited sending, the tutor restrictions
and where each is enforced, the per-student `_ems_course_in_force()` rule, the shared portal
template, the onchange default-phase trap, and the `noupdate` trap in full.

## Portal translations:

The portal's "Respond" button has a text of its own instead of sharing "Answer" with the column
header, whose translation was a noun ("Resposta"/"Respuesta"); the column keeps it, the button reads
"Respondre"/"Responder". "Document" gets its missing Catalan translation.

## Screenshot generator:

`tests/test_docs_screenshots.py` rebuilds the five PNGs the manuals use (a tutor's view of the send assistant included). Tagged `-standard`, so
`./test.sh` never runs it; run by hand with `--test-tags='ems_screenshots/ems'`. Each shot is
clipped to a single element via the devtools protocol and taken against fixtures that live in a
rolled-back transaction, so a published manual can never carry a real student's name. Writing
it paid for itself immediately: the send assistant's recipient preview turned out to render
empty, which no test had noticed.

## Recipient preview fixed:

Found testing by hand, both in the send assistant. The preview is built in an onchange, where every
relational value is a virtual record wrapping the real one and never compares equal to a persisted
record: it came out empty for groups/studies/levels (and earlier, built off the unsaved wizard's own
empty `_origin`, for everyone) while sending worked. `._origin` now goes on the related records
wherever they are compared or searched with. Separately, opening the assistant from a form's own
"Send to Students" button failed with "record does not exist": the button passes the form's id as
`active_ids`, which was read as a student id; students are now only read from `active_ids` when
`active_model` is `res.partner`. Both are pinned by tests, the preview through `odoo.tests.Form`,
and the template tour now opens the assistant from the form's button.

The tutor tour found a third one: the web client gets a new record's values from the onchange's
default phase, which never computed the groups/studies/levels the sender may pick, so the group
picker came up empty when the assistant opened - even with a form preloaded. Those sets are now
filled when the assistant opens and recomputed when the chosen forms change. A per-user field
read in browser-side expressions (to narrow the student picker and hide studies/levels for
tutors) behaved differently in the browser than on the server and was dropped: studies and levels
are removed from the tutor's view on the server with groups=, and someone else's student picked by
a tutor shows in the preview as "Not one of your students" and is never sent to.

## Test coverage:

New `TestAuthorizationStandalone` (15 cases: creation without an enrollment, derivation from it,
the constraint, the partial index, rendering the legal text with no enrollment, the
acceptance-only and signed-document rules still applying, a pending standalone not blocking
`action_confirm()`, and a portal user only seeing their own). New
`TestAuthorizationSendWizard` (18 cases covering the three targeting routes, exclusion of
unenrolled students, skip-not-recreate, one-email-per-student, adult-vs-minor recipients, and who
may send). New portal action cases for answering and downloading a standalone authorization,
plus a regression guard on the ownership check. New browser tours: the authorizations block on
the CONFIRMED portal page, and the follow-up list plus the send assistant driven by a secretary
account rather than admin. `apply_on` steps added to the existing template tour, and the send
assistant tour now asserts the recipient preview actually lists the student.

## Translations:

47 new blocks in each of `i18n/ca_ES.po` and `i18n/es_ES.po`, plus 49 existing blocks that
gained a reference to one of this feature's records. That second half is the part a msgid diff
never reports: labels like *Student*, *Academic Year*, *Study* or *Send to* already existed for
other fields, so the text was not new - but the new field's own `#:` reference had to be added
to the block that was already there or it would render untranslated. Verified by reading the
jsonb values back out of the database rather than trusting the files.

A first pass missed the portal's own menu label and home card, which stayed in English for
Catalan and Spanish users: the terms were filtered by source file name (`portal_main`,
`portal_header`) while the reference Odoo exports carries the view's xmlid
(`portal_my_home_ems_custom_landing`, `ems_portal_custom_header_menu`). Filtering by xmlid
found them, along with the renumbered section headings.
