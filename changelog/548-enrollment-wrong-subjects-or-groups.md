# Changes

## Student's Studies tab: subjects limited to the student's study, group defaulted by course:
- The subject selection list on the student's Studies tab now only offers subjects of the student's own study (a DAM student is no longer offered GA subjects).
- Picking a subject now fills in the group of the course the study's enrollment template sells it for (e.g. a 1st-year module added to a 2nd-year student goes to the equivalent 1st-year group), the same group the enrollment placement already picked on confirmation. A reinforcement group chosen by hand is kept.
- The subject-to-group resolution is now one shared helper (ems.group._ems_group_for_subject) used by the manual line, the enrollment placement and the study-change refresh, instead of being duplicated.
