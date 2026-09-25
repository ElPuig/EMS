# Fixes

## Tutors can create their students' Google account (issue #513):
- The student form's "Create Google account" header button was only offered to the secretary,
  academic admin and TAC, so a tutor opening one of their students with no corporate account yet
  (typically because data was missing at enrolment) saw neither that button nor "Reset Google
  password" (hidden by design until an account exists), and had to go through the secretary's
  office.
- The button is now also offered to the student's own tutor scope (the tutor, the chiefs above
  them along the hierarchy and the Director), exactly like the password reset (#490): a new
  per-record `res.partner.can_create_google_account` (secretary, plus everyone in
  `can_reset_google_password`) drives its visibility, and `action_create_google_account()`
  repeats the same check server-side (AccessError otherwise). A tutor of another group or a chief
  of another branch still gets nothing.
- The creation body moved to a private `_gw_create_account()`, called directly (no permission
  check) by the automatic paths: the queue job enqueued by `_gw_enqueue_if_ready()` and the
  re-creation of a deleted account on reactivation. Those jobs run as whoever triggered them,
  which includes portal users submitting an enrolment, so they must not go through the button's
  check. Jobs already queued under the old method name keep calling `action_create_google_account()`
  and are therefore subject to the check.
- Tests (backend + a tutor tour), tutor/admin/Head of Studies manuals (en/ca/es, with a new
  screenshot) and ca/es translations updated.
