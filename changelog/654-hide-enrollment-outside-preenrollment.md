# What's new

## Enrollment proposals only during the pre-enrollment period (issue #654):

- New yearly **Pre-enrollment period** in Settings → EMS Management → Course Management Settings (day, month and time it opens and closes, no year, centre's local time; by default 1 May 08:00 to 31 July 23:59), validated like the convalidation request period.
- Outside it, Academic management → Enrollment → Enrollment proposal is hidden from tutors, Department/Seminar Chiefs, guidance and coexistence (guidance and coexistence were confused looking for student data there, which they already have on the student's file). Academic administration, the secretary's office, Head of Studies/Deputy Head of Studies, the Director and the administrator always see it. Empty folders left behind are hidden too (guidance and coexistence lose Academic management entirely outside the period).
- Opening the proposals from a saved link outside the period shows a message with the date it opens again.
- Menu visibility is ormcached, so a daily cron (woken up exactly one minute after each opening/closing, and on every change of the period's settings) clears the registry cache only when the period's state really changes, twice a year.

# Changes

## Authorizations: a single menu entry, forms in Configuration (issue #654):

- Academic management → Authorizations is now one entry, like the other sections: it opens the responses list, and its **New** button opens the Send Authorizations assistant (same roles as the assistant). The Send Authorizations / Responses / Configuration submenus are gone (removed by the upgrade itself, no migration).
- Academic management → Configuration is organised in sections, like Convalidations already was: **Enrollment** (Enrollment Items, Enrollment Templates, Task Assignment) and **Authorizations** (Authorization Forms, moved here from the old submenu). Head of Studies/Deputy Head of Studies reach only the Authorizations section there.
- Outside the pre-enrollment period a tutor entering Academic management lands on that list instead of a dialog.

## Authorization answers follow the chain of command (issue #654):

- The Authorizations list now shows a tutor the answers of the students they act as tutor of through the hierarchy (`tutor_scope_user_ids`, issue #483), not only their own group's: a Department/Seminar Chief also follows the answers of the students of the tutors in their department. Staff who see every student are unchanged.

## Head of Studies reads student documents (issue #654):

- Head of Studies/Deputy Head of Studies and the Director now reach Academic management > Student Documents and read every document type (ID card, IBAN, medical card, benefit proofs, Google credentials) of the students whose tutor is below them in the chain of command, read only: approving, rejecting and reopening stays with the secretary's office. Another Head of Studies' students stay out; Department/Seminar Chiefs still only read the Google credentials. New Head of Studies manual "Consulting student documents".

## Head of Studies reads the whole Enrollment menu (issue #654):

- Head of Studies/Deputy Head of Studies and the Director now reach every screen of Academic management > Enrollment (Enrollments, Preinscription, Students without destination) and of Configuration > Enrollment (Enrollment Items, Enrollment Templates, Task Assignment), for the whole centre and read only: a new read rule on enrollments and their lines; the rest was already readable. The "Enrollment proposal" and "Suggest destination group" buttons of those lists stay with the secretary's office and the academic administration. Department/Seminar Chiefs are unchanged. Preinscription offers New and Delete, and Enrollments offers New, only to the secretary's office and the academic administration, even though the Heads of Studies manage contacts elsewhere (Enrollments got its own views for it, so the Sales app is unchanged).

## Head of Studies maintains the convalidation reasons (issue #654):

- Head of Studies/Deputy Head of Studies and the Director now reach Academic management > Configuration > Convalidations and create, edit and archive the documentation request and refusal reasons they pick from; deleting stays with the academic administration.

## Academic management permission review (issue #654):

- Enrollments, Preinscription and the contact form those screens open are read only for the Heads of Studies (no New, Edit or Delete there; their contact rights elsewhere are unchanged). Enrollments has its own views for it, so the Sales app is unchanged.
- Enrollment Items no longer offer New and Edit to the Heads of Studies, who can only read them (saving failed with an access error).
- The authorization forms' "Apply to / Remove from Pre-Enrollments" buttons are only for the academic administration, the secretary's office and the Heads of Studies, who can now remove pending authorizations (it failed for them); a tutor opening a form no longer sees them.
- Students without destination no longer offers deleting contacts from the list.
- The academic administrator can edit Task Assignment with that role alone, as the top of every permission.

# Internal changes

## Yearly periods share one implementation (issue #654):

- The convalidation request period's arithmetic and validation on res.company became generic helpers taking the fields' prefix (`_ems_yearly_period_keys/_open/_next_change`, `_ems_check_yearly_period`); the convalidation methods are thin wrappers. Its three validation messages are now parametrized by the period's name (re-translated).
- Who always sees the enrollment proposals reuses the "sees every student" check instead of its own list of groups. Screens that are read only for the Heads of Studies share one helper (`EmsBase.view_read_only_for_non_enrollment_editors`).
- Tests: `set_yearly_period`/`open_yearly_period`/`close_yearly_period` in tests/common.py; the reader tests, the guidance tour and the tutor doc screenshots open the pre-enrollment period in their fixtures. New TestPreenrollmentPeriod, TestAuthorizationMenus and a tutor tour checking the menu bar outside the period.
