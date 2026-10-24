# Changes:

## Detected absences are reviewed by the Head of Studies before the teacher hears about them (issue #707):
- Detected absences (missing check-ins and those entered by hand) no longer remind the teacher on their own. Each new one becomes a "Review detected absence" task for whoever corrects the teacher's attendance (their Head or Deputy Head of Studies up the `parent_id` chain, else the area's attendance manager, else the academic administrators), listed in their daily pending-tasks digest with no email of its own.
- From the form's Actions dropdown, or on several selected in the list, the reviewer can: request a justification (the teacher is told at once and reminded as before); correct the check-in for the detected hours (an attendance is created, or a late check-in moved back, telling nobody); create the absence (choose a type: the teacher's request is prepared with it and the teacher only has to check it, accept the responsible declaration and send it, since nobody can declare it on their behalf); or discard it (archived, telling nobody). Only the teacher's reviewers and the administrators can; a mixed selection acts on what it can and says how many it left.
- New states: To review, Justification requested, Absence prepared, Requested, Check-in corrected, Discarded. The teacher only sees an entry once they have been asked about it. The reminders and the report now count from the day the reviewer asked, not from the absence.
- Main case it solves: the Wednesday 14:00-16:00 meetings are in everyone's schedule, but whoever is not convened checks in at 16:00 and was detected; now the Head of Studies corrects or discards it and the teacher never hears about it.

# Internal changes:

## Detected absences review: migration and tests (issue #707):
- `migrations/18.0.0.40.1/post-migrate.py` (`ems.absence_pending._ems_migrate_to_review()`): entries already reminded or reported move to "Justification requested", counting from their last reminder; the rest stay "To review" and get their review task. To move if the release is not 18.0.0.40.1.
- The guard duty board plans around every unresolved state (`_ems_unresolved_domain()`).
- New `tests/test_absence_review.py`; `test_absence_detection.py` reworked around the review (its fixture is now the shared `AbsenceDetectionCase`); new tour `ems_absence_pending_review` as a Head of Studies (list bulk action + wizard, form Actions dropdown).

# Related with:
- Closes #707
