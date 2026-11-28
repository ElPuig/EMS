# What's new

## Evaluation board decisions per student (issue #881):

- The students' table of the evaluation board minute has a "Board decision" column. In the 2nd and 3rd evaluations it is a forecast (Possible repeater, Moves up to the 2nd year or, in the study's last course, Can graduate, Drops out); in the extraordinary evaluation (2a convocatòria) it is the decision (Promotes or, in the last course, Gets the title, Repeats, Drops out). The dropdown only offers the round's options (`ems_selection_allowed` widget, `allowed_decisions`), and the server refuses any other value.
- "Promotes" and "Repeats" fill a "Recommended enrollment" with the modules failed in the course, editable by the tutor; it only recomputes when the decision changes. "Failed" is the academic record's rule (an outcome below 5 or never scored; the work placement never fails a module; convalidated ones left out), now one shared helper, `ems.grade_outcome_line._ems_subjects_passed()`, used by both.
- "Drops out" shows an "Expected withdrawal" button on the row that opens the student's existing expected-withdrawal wizard, only for whoever may mark it (the student's tutor and chain, whoever registers exits); nothing is marked automatically.
- The minute's PDF prints the decision and the recommended modules. The decision is not shown in the portal.

## The board's decision feeds the enrollment, the transition and the academic record (issue #881):

- Enrollment proposal: the board meets before any proposal exists (a student still being evaluated has none), so the proposal reads the extraordinary board's decision. When the pre-enrollment course picks no template, it preselects the same course's template for students who repeat and the next one for students who promote, when they all agree; the dialog sums the decisions up. On creation, a student who repeats keeps only the recommended modules (plus the tutorship and the non-module lines), and both decisions add the recommended modules the template lacks.
- Course transition: a new preview warning lists the students whose incoming-course enrollment contradicts the decision (an enrollment for one who drops out, another course for one who repeats, the same course for one who promotes or gets the title). The confirmed enrollment is still what the transition applies.
- Academic record: `ems.student.year_record.board_decision` keeps the decision, copied when the record is generated, independent of the academic result.
- Measured on the dev database (DAM2A, 14 students, cold): failed modules 17.3 ms, decision options 15.7 ms, final decisions 5.6 ms, transition check over 1,153 students 29.9 ms.

# Related with

- Closes #881
