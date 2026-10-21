# What's new

## Enrollment proposals only during the pre-enrollment period (issue #654):

- New yearly **Pre-enrollment period** in Settings → EMS Management → Course Management Settings (day, month and time it opens and closes, no year, centre's local time; by default 1 May 08:00 to 31 July 23:59), validated like the convalidation request period.
- Outside it, Academic management → Enrollment → Enrollment proposal is hidden from tutors, Department/Seminar Chiefs, guidance and coexistence (guidance and coexistence were confused looking for student data there, which they already have on the student's file). Academic administration, the secretary's office, Head of Studies/Deputy Head of Studies, the Director and the administrator always see it. Empty folders left behind are hidden too (guidance and coexistence lose Academic management entirely outside the period).
- Opening the proposals from a saved link outside the period shows a message with the date it opens again.
- Menu visibility is ormcached, so a daily cron (woken up exactly one minute after each opening/closing, and on every change of the period's settings) clears the registry cache only when the period's state really changes, twice a year.

# Changes

## Authorizations: a single menu entry, forms in Configuration (issue #654):

- Academic management → Authorizations is now one entry, like the other sections: it opens the responses list, and its **New** button opens the Send Authorizations assistant (same roles as the assistant). The Send Authorizations / Responses / Configuration submenus are gone (removed by the upgrade itself, no migration).
- Academic management → Configuration is organised in sections, like Convalidations already was: **Enrollment** (Enrollment Items, Enrollment Templates) and **Authorizations** (Authorization Forms, moved here from the old submenu). Head of Studies/Deputy Head of Studies reach only the Authorizations section there.
- Outside the pre-enrollment period a tutor entering Academic management lands on that list instead of a dialog.

# Internal changes

## Yearly periods share one implementation (issue #654):

- The convalidation request period's arithmetic and validation on res.company became generic helpers taking the fields' prefix (`_ems_yearly_period_keys/_open/_next_change`, `_ems_check_yearly_period`); the convalidation methods are thin wrappers. Its three validation messages are now parametrized by the period's name (re-translated).
- Tests: `set_yearly_period`/`open_yearly_period`/`close_yearly_period` in tests/common.py; the reader tests, the guidance tour and the tutor doc screenshots open the pre-enrollment period in their fixtures. New TestPreenrollmentPeriod, TestAuthorizationMenus and a tutor tour checking the menu bar outside the period.
