# What's new

## Student portal sign-in with the corporate Google account:
- A student's portal user (login = personal email, since it exists before the corporate
  account does) can now also be opened with "Log in with Google" using the student's
  corporate account (`student_email`). Both ways coexist on the same user: many students had
  lost their portal password.
- The link is made lazily on the first Google sign-in (`res.users._auth_oauth_signin` override,
  `models/contacts/portal_google_signin.py`): only for a verified email inside the centre's
  Workspace domain, only for portal (share) users, only when exactly one student matches and
  the Google id is not already linked elsewhere. No migration, backfill or Directory API call.
- Changing a student's `student_email` unlinks Google sign-in from his portal user, so the old
  Google account can no longer open it.
- Prerequisite outside the code: the Google Cloud OAuth client must accept accounts from the
  students' organizational units.

## Minor students get their own view-only portal account:
- The portal access wizard now grants access to the student himself as well as to his family
  (`res.partner._ems_portal_access_recipients()`); authorizations and convalidation notices
  keep going only to the family (`_ems_notification_recipients()` unchanged).
- A minor on his own account (`_ems_portal_is_view_only()`) sees Home, Attendance (schedule),
  Grades, Profile, and only the Communications addressed to him. Enrollment and
  authorizations, Convalidations and Documentation are hidden from the menu and home cards and
  refused server side (redirect to `/my/home`); the native quotation/order/invoice portal pages
  are refused too, since a minor is the customer of his own enrollment.
- Exception kept: a minor applicant with no family on file (GEDAC preinscription) still
  manages his own enrollment, and can now also request convalidations.
- A minor student with no family on file still gets his own view-only access (the missing
  family is reported as a note/issue instead of blocking the grant).

# Fixes

## Portal header served another family's children (cache shared across users):
- The portal header menu sits inside a QWeb `t-cache` block, which is shared by every user,
  and its key did not include the user. Confirmed with a test: a family with several children
  opening a page after another family (neither with a selected student yet) got the other
  family's header, with the other family's children's names in the student switcher. The key
  now includes `request.env.user.id` (`views/portal/portal_header.xml`), which the new
  view-only menu also needs. Regression test:
  `TestPortalViewOnly.test_header_student_switcher_is_never_served_to_another_family`.

# Internal changes

## Shared Google sign-in linking helper:
- `hr.employee._ems_link_google_signin(user, google_id)` became
  `res.users._ems_link_google_signin(google_id)` (`models/shared/google_signin.py`), shared by
  the staff account creation/relink flows and the new student portal sign-in.

## Portal test fixtures given an adult birth date:
- Portal tests whose student had no birth date (counted as a minor) now set one, since a
  minor's own account is view-only.
