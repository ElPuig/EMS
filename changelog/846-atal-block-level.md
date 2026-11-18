# Changes

## Schedule declaration: level per student-support (ATAL) block:

- A tutoring block of a teacher's schedule (Tutorship Time, Student support) can now name the level it is given to (ESO, Bachillerato...), from its card on the Schedule tab or from the attendance form.
- Non-teaching types get a new declaration code, "Level or tutoring", assigned to Student support by a migration. Each block of such a type says whether it counts as Support (the default) or as Tutoring. The official schedule declaration puts Support hours in the level's own row (ESO, BAT, CFGM...) and Tutoring hours in its tutoring row (T-ESO, T-BAT, T-FP...), with no new rows, so a teacher with student support in two levels is declared correctly. Tutorship Time always counts as tutoring.
- A block without a level uses the tutored group's level, or the level with most class hours; a Support block with no level at all goes to Altres.
- Re-importing a schedule file keeps the level and the attention type of a block that is still the same (same day, hours and type).

# Fixes

## My Profile and the employee form open for roles without schedule data:

- Someone whose only roles are Quality, Settings or Erasmus+, or who has no EMS role, could not open My Profile or an employee form: loading the Schedule tab ended in an access error. These roles no longer get that tab, and a Settings administrator opens the employee form without its roles, tutorships and subjects.
