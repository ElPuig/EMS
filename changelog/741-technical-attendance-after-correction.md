# Fixes

## Red "no check-in" attendance left after correcting a detected absence (#741):

- Correcting a detected absence's check-in ("Correct check-in", whole or part of it) created the teacher's manual attendance but kept the one-second technical attendance Odoo's nightly absence detection leaves on a day without check-in, so the day kept showing a red entry next to the corrected one (the overtime was already right, the technical one weighed 0 h). Found on a teacher whose partial absence request covered 15:00-18:00 and whose rest of the day was corrected.
- Now any real attendance created on a day, or moved onto it (`hr.attendance.create()`/`write()` on employee/check-in/check-out), deletes that employee's technical attendance of that local day; Odoo recomputes the day's overtime on deletion. Covers manual attendances entered by hand and late check-ins too.
- Never deleted when a check-in correction request is about it: `ems.attendance_correction.attendance_id` is `ondelete='cascade'`, so the request would vanish with it; accepting the request turns it into the real attendance anyway. The same guard now applies to the public holiday cleanup, which shares the lookup (`hr.attendance._ems_technical_attendances_on()`).
- `migrations/18.0.0.44.1/post-migrate.py` clears the ones already left behind (one in production's 02/11 dump, one in the dev database; 0.23 s over the dev database's attendances). About 1.5 ms per attendance created.
