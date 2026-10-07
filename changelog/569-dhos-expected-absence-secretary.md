# Fixes:

## Expected absences: the management team can be reached through their department:
- A Head of Studies or Deputy could only enter expected absences for the teachers below them in the
  hierarchy (parent_id), so nobody but the Director could enter one for a member of the management
  team: the Area Managers (Head of Studies, Deputy, Secretary) report to the Director, out of every
  other branch. E.g. the Deputy in charge of VET couldn't select the Secretary.
- Their reach now also includes the teachers whose department hangs from an area they manage: the
  Secretary, teaching in a VET department, is reached by VET's Area Manager; the Director, teaching
  in an ESO/BTX department, by ESO/BTX's. Same rule for the record rule and the teacher picker; for
  every other teacher nothing changes.
- The Head of Studies' absences manual (en/ca/es) and the developer doc describe it.
