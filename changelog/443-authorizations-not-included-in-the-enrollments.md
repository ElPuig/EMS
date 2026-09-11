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

New `ems.authorization.send.wizard` (Academic management > Enrollment > Send Authorizations, and
as an Actions entry on the students list). Resolves recipients three ways: the students selected
in a list, the groups/studies/levels chosen in the assistant, or each template's own
level/study scope. All three resolve through the enrollments of the selected academic year, so
ex-students still attached to a group record are never asked for anything. A student already
holding that (course, authorization) - by either route - is skipped and reported, never asked
twice and never reset. Restricted to the secretary's office, the academic administration and
the head of studies.

## Email notification, one per student:

New trilingual `mail.template` `email_template_authorization_send`, sent once per student per
batch and listing every authorization in it, rather than one email per authorization. An adult
student is emailed himself; a minor's family is emailed instead, via the
`_ems_notification_recipients()` rule shared with the portal access wizard. Queued rather than
sent inline, so a whole-level batch does not block the request.

## Authorizations follow-up list:

New backend list/form/search for `ems.authorization` itself (Academic management > Enrollment >
Authorizations), opening flat on the running academic year. Filters for pending/accepted/
rejected and for sent-during-the-course vs from-an-enrollment, group by authorization, student,
year or status, and a searchable `group_id` (related to the student's main group).

## `apply_on` on the authorization template:

New required selection deciding whether a template takes part in the enrollment process
(`enrollment`, the default, and what every pre-existing template gets) or is only ever sent by
hand during the course (`standalone`). A standalone template is invisible to all four automatic
attachment paths - `create()`, `action_apply_to_open_enrollments()`,
`action_remove_from_open_enrollments()` and `sale.order._get_authorization_commands()`. That
last one is the important one: without it, the next onchange on any draft enrollment, including
one for the following course, would pull in a template created mid-year for a different one.

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

`group_head_of_studies` is added to the Academic management > Configuration menu, with the
Enrollment Items and Enrollment Templates entries given their own explicit `groups=` so opening
that menu does not also hand over the enrollment items and packs. They get full CRUD on the
authorization template models, plus a record rule of their own on `ems.authorization`: without
it they would inherit only the teacher's read-only rule and the tutor's own-students-only one
(rules of different groups are ANDed), so they could not send an authorization to a student they
do not tutor.

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
account rather than admin. `apply_on` steps added to the existing template tour.
