# Fixes

## Head of Studies/Deputy Head of Studies/Director can now edit any student's enrollments:

- A Head/Deputy Head of Studies got an "Access error" (no write rights, blamed on the tutor-only rule) editing an enrollment (subject x group) from a student's form for a student they don't personally tutor - they only inherited the same read-only/tutees-only access as a plain teacher.
- Added a dedicated centre-wide record rule so Head of Studies, Deputy Head of Studies and Director have full read/write/create/delete access to every enrollment, same pattern already used for family contacts and attendance templates/schedules.
- The manual "New enrollment" creation guard (previously admins/secretary only) was extended the same way, so creating one manually also works for these roles now.
- Deliberately kept out of scope: the equivalent gap on the enrolment header itself (`sale.order`/`sale.order.line`) - same root cause, confirmed present, left for a future fix.
