# What's new:

## Subject convalidation requests from the student portal (issue #276):
- New portal page Convalidations (/my/convalidaciones, also a home card and a top-bar link): a student, or the family of a minor for the selected child, ticks the modules of their vocational training study to convalidate, picks the grounds (prior studies / professional certificate / other), attaches the supporting documents (at least one file) and submits. The page lists every request with the resolution and remarks of each module, and a request can be cancelled while nothing has been resolved yet.
- The study offered is the one of the student's enrollment for the course being enrolled into, falling back to their current group's study. Only studies whose level has the new "Allows convalidations" flag qualify (set for CFGM and CFGS in data/cat/ems.level.csv, the cycles the centre publishes convalidation forms for). The tutorship is never offered, and a module already requested is not offered again unless it was rejected.
- Decisions taken without the developer (autopilot): ESO/Batxillerat convalidations are out of scope, as agreed; no request window/deadline setting (the centre's page publishes none); the Head of Studies is not sent an activity per request, the list's default "To resolve" filter is the work queue.

## Convalidation resolution by the Head of Studies (issue #276):
- New models ems.convalidation (the request, with chatter and supporting documents) and ems.convalidation.line (one per module: Pending, Forwarded to the Department of Education, Convalidated, Rejected), under Academic management > Convalidations, plus a Convalidations stat button on the student form.
- Only the Head of Studies (Director included) and the academic administration can resolve a module; the secretariat registers paper requests and follows them up but gets an error if it tries to resolve. Teachers have no access.
- The request state is computed from its modules (Submitted, In progress, Resolved, Cancelled); a forwarded module keeps the request open until the Department's answer is recorded. "Convalidate pending subjects" resolves every pending module at once.
- When a request becomes resolved, the resolution is emailed (new template EMS: Convalidation resolved, ca/es/en) to the student when adult or to the family when a minor, the same recipient rule as the other EMS notices, and the recipients are logged in the chatter. Reopening and resolving again sends a new email.

## Convalidated subjects in grades and academic history (issue #276):
- ems.grade_subject_line and ems.student.year_record.subject get an is_convalidated flag, kept in sync from the granted convalidation lines (the only source of truth). A convalidated subject counts as complete and passed with a final grade of 5, whatever its outcomes hold, and both grade screens (teacher matrix and tutor view) show CV in the Final column.
- The flag reaches finalised evaluation sessions too (the Department can answer after the rounds are closed), new grade lines start with it, the EM grading wizard skips convalidated modules, and the course transition's incomplete-evaluation check treats them as complete.
- A year record already frozen is updated when the convalidation of its own course is resolved later; revoking it rebuilds the subject's state and final grade from the record's own RAs and grades.
- Decision taken without the developer (autopilot): a textual "CV" in an Esfera grade import is still not turned into the flag, so a later sync can never silently undo an imported value; the request stays the single source.

# Internal changes:

## Convalidation tests, tours and docs (issue #276):
- tests/test_convalidation.py (34 tests: requests, access per role, notification, grades and year record sync, portal helpers), tests/test_portal_convalidation.py (11 HTTP tests of the portal routes) and tests/test_convalidation_tour.py (5 tours, each as the least-privileged role: Head of Studies for the list/form/stat button, the group's tutor-teacher for CV in both grade screens, a portal student submitting with a file).
- TestDocsScreenshots gets a convalidation capture method (form, list and two portal shots, now in docs/assets); its student fixture now sets a Student ID, which issue #460 made mandatory (same fix as branch 478).
- Technical doc docs/en/developers/grades/convalidation.md; Head of Studies manual (shared with the secretariat) and families portal manual in ca/es/en; CV and the level flag added to the teachers', tutors' and admin level manuals.
