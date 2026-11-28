# Evaluation board minutes (issues #880 and #881)

The minute of an evaluation board (*junta d'avaluació*) replaces the evaluation tabs of the tutor's
spreadsheet. It is an ordinary `ems.minute` of the type **Acta de junta d'avaluació** (`JA`,
`__import__.minute_type_board`, `data/custom/quality/`), scoped to a group's teaching team, plus three
section kinds of its own and the round it is about (`grade_round`). Attendance of the teaching team,
the follow-up of earlier agreements, the agreements and the signatures are the minutes' own.

```mermaid
sequenceDiagram
    participant HoS as Head of Studies
    participant S as ems.grade_session
    participant M as ems.minute (JA)
    participant T as Tutor
    HoS->>S: state = board (state wizard)
    S->>M: _ems_create_board_minutes() (one per group and round, if missing)
    M->>M: students, outcomes passed/evaluated, statistics, areas A-D
    M-->>T: quiet task "Write the evaluation board minute"
    T->>M: difficulties, comments, family comments, send for approval
    M-->>T: task done
```

## Section kinds

| Kind | Data | Notes |
|---|---|---|
| `board_difficulties` | `ems.minute.board.difficulty`: `area` (A prior knowledge and basic competences, B expectations and interests, C study techniques and habits, D behaviour), `tests`, `diagnosis`, `objectives`, `priority` | The four rows are created with the minute. |
| `board_statistics` | On the minute: `board_withdrawals`, `board_absence_count`, `board_unjustified_count`, `board_working_count` (computed from the students' `works`), `board_period_from/to` | Computed **once**, when the minute is created; the tutor corrects them by hand (developer, issue #880). |
| `board_students` | `ems.minute.board.student`: `passed_count`, `evaluated_count`, `works`, `comments` (the teaching team's, stay in the minute), `family_comment` (the tutor's, for the student and the family) | One row per student of the group's tutorship (`tutorship_group_id`). |

`board_kinds` (non-stored) says which of the three the minute's type has: the form shows each block,
and `grade_round`, only then. The PDF (`reports/minute_report.xml`) prints the difficulties, the
statistics and the teaching team's comments; never the family comments.

## Creation

`ems.grade_session.write()` (`models/quality/minute_board.py`): when sessions move to `board`,
`ems.minute._ems_create_board_minutes(sessions)` creates, in sudo, one minute per group and round that
has none yet, written by the group's tutor (`redactor_employee_id`), and gives the tutor a quiet task
(`ems.mail_activity_board_minute_write`, via `_ems_sync_user_tasks`), marked done once the minute is
sent for approval. Going back to open and to the board again does not create a second one.

- **Outcomes passed and evaluated**: from the round's outcome lines of each student, in every session
  (also another group's); one search for the whole minute. "Update the outcomes from the grades"
  (`action_board_refresh_grades`) reads them again while the minute is open, since grades can change
  during the board.
- **Term**: from the group's previous board minute's date, or 1 September of the current course,
  until the creation day.
- **Withdrawals**: the group's enrolled students (archived enrollments included) who withdrew or were
  expelled in the term, with the registered reason (`exit_type`, `exit_date`, `exit_reason`).
- **Absences**: from the roll-calls (`ems.attendance_session_line`), weighting each session by its
  length (`end_time - start_time` of the header): a student counts when absences exceed 25% of their
  hours, or unjustified ones (any absence but `ems.attendance_status_justified`) exceed 5%. One grouped
  raw SQL query for the whole group, because the length lives on the header, which `_read_group` cannot
  sum through the line.

## The board's decisions (issue #881)

Each `ems.minute.board.student` line carries a `decision`:

| Minute's round | Decisions offered | Meaning |
|---|---|---|
| 1st | none (the column is hidden) | |
| 2nd and 3rd | `repeat_risk`, `next_course` (or `graduate_expected` in the study's last course), `dropout` | a forecast |
| Extraordinary (`4`) | `promote` (or `graduate` in the study's last course), `repeat`, `dropout` | the decision |

The study's last course is the group's course when no group of the same study has a higher one
(`_ems_board_last_course`). `allowed_decisions` (non-stored) gives the line's options to the
`ems_selection_allowed` dropdown, and `_check_decision` refuses any other value on the server.

`recommended_subject_ids` is a stored editable compute on `decision`: for `promote` and `repeat` it is
filled with the modules failed in the course up to the minute's round (`_ems_board_failed_subjects`), and
emptied for every other decision. "Failed" is the academic record's own rule,
`ems.grade_outcome_line._ems_subjects_passed()`: a module passes when every outcome's latest scored grade
is 5 or more; the work placement (external part) never fails it, and a convalidated module is left out.
Two searches for the minute. It only recomputes when the decision
changes, so the tutor's edits stay. A `dropout` decision shows a button that opens the student's own
"Expected withdrawal" wizard (`res.partner.action_withdrawal_expected_wizard`, with its permission check):
nothing is marked automatically.

`_ems_final_decisions(students, course)` (one search, sudo) returns the extraordinary board's line per
student for a course. Three readers use it:

```mermaid
flowchart LR
    line["ems.minute.board.student<br/>decision + recommended modules<br/>(extraordinary board)"]
    proposal["Enrollment proposal wizard<br/>template + modules"]
    transition["Course transition preview<br/>warning on mismatch"]
    record["ems.student.year_record<br/>board_decision"]
    line --> proposal
    line --> transition
    line --> record
```

- **Enrollment proposal** (`ems.enrollment_proposal_wizard`): when no template is chosen by the
  pre-enrollment course, the decision selects it (same course for `repeat`, next one for `promote`) if
  every selected student agrees. On creation, when the template is the course the decision sends the
  student to and the study is the student's own: `repeat` drops the template's module lines that are not
  recommended (the tutorship and the non-module lines stay), and both decisions add the recommended
  modules the template lacks. `board_decision_info` summarises the decisions in the dialog. In the
  centre the proposal comes after the board: a student still being evaluated has none yet.
- **Course transition** (`_board_mismatches`): a warning listing the students whose incoming-course
  enrollment contradicts the decision (an enrollment for a student who drops out; another course or study
  for one who repeats; the same course for one who promotes or gets the title). The enrollment is still
  what the transition applies.
- **Academic record**: `ems.student.year_record.board_decision`, copied when the record is generated.
  It is independent of `academic_result`, which keeps coming from the destination enrollment and the
  grades.

The minute's PDF prints the decision and the recommended modules' acronyms in the students' table. The
decision is never shown in the portal.

## The family comment in the portal

`res.partner._ems_portal_board_comments()` gives each round's `family_comment`;
`_ems_portal_grade_rounds()` adds it to the rounds the portal and the grades' PDF show, which are only
the published and final ones: the comment appears with the grades, never before.

## Access

The two line models have the minutes' lines' access (teachers, secretary, quality administrator and
academic administrator), narrowed by record rules that repeat, through `minute_id`, the minute's own
read and write rules (`security/rules/quality.xml`). Repeated on purpose: a record rule's domain is
evaluated without the related model's rules, so `('minute_id.id', '!=', False)` would let any teacher
read every student comment.

## Cost

Measured on the dev database (odoo shell, a group of 14 students): creating the minute takes 0.34 s,
of which the absences query 16 ms; refreshing the outcomes, 8 ms.

The decisions (issue #881), measured cold on the same group's minute set to the extraordinary round: the
failed modules of its 14 students, 17.3 ms; setting a decision on every line, recommended
modules included, 18.3 ms; the options of the 14 lines, 15.7 ms; the final decisions of 14 students,
5.6 ms (one search); the transition's mismatch check over a study scope of 1,153 students, 29.9 ms,
incoming enrollments index included.
