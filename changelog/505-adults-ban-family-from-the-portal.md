# Breaking changes

## Families lose an adult student from the portal unless he shares with them:
- `res.partner.get_portal_students()`, the single point every portal page reads a family's
  students from, now leaves out an adult child who has not authorized sharing with the family
  (`auth_share`). No account is revoked and no cron is involved: `is_adult` is computed from the
  birth date on every read, so the family loses the child the day he turns 18 and gets him back
  as soon as he accepts the "share with the family" authorization.
- A family looking at an adult child who shares with it is view-only
  (`_ems_portal_is_view_only()` now depends on the selected student): Attendance, Grades,
  Profile and the Communications addressed to the student; Enrollment and authorizations,
  Convalidations and Documentation are hidden and refused, exactly as for a minor on his own
  account.
- A family left with no child to see gets a notice on the portal home instead of empty pages.
- The student himself takes over every section on the day he turns 18, provided he already has
  his own portal user (granted to minors since #515). Students without one still need the
  portal access wizard: the developer chose not to grant it automatically.

# Internal changes

## Single portal rule for acting on a student's behalf:
- `_ems_portal_can_act_for()` now resolves to "the logged-in partner is among the student's
  `_ems_notification_recipients()`", and `_ems_portal_is_view_only()` is its negation for the
  selected student, so the account-granting rule and the portal rule can no longer drift apart.
- The header menu's `t-cache` key now includes the visible students and the view-only flag,
  since both change without any write when a child turns 18.
- The convalidations page's "student is of age" notice was removed: nobody who can't act for
  the student reaches that page any more.
- `plans/portal_family_access_adult_students.md` deleted (implemented).
