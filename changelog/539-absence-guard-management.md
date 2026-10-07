# What's new:

## Managing absences from the guard duty board's absences table (issues #539, #571, #581):
- The absent teacher's chain of command (their Seminar/Department Chief, then Head of Studies or
  Deputy, then Direction; never every holder of those roles, never the absent teacher) and the
  administrator organise
  each absence from the absences table. Every other teacher sees the result read-only.
- Send a guard (#571): clicking an absence line opens a dialog offering only the teachers on
  guard duty in that block (WC guards and absent guards excluded) plus a free-text message. The
  guard gets an Odoo message (inbox or email, per their preference) with date, time, group,
  subject, room, absent teacher and the message. Reassigning tells the previous guard they are
  released; assigning the same guard again re-sends an updated message.
- Covered lines are struck out and share a colour with their guard's badge; each guard covering
  in the same block gets a different colour (8-colour palette, also in the PDF).
- Late entry / early leave / no classes (#539, #581): the board detects when the empty lessons
  (every teacher away, no co-teacher, no other half of a split group, no guard sent) are the
  first or last of the group's whole day, tags those lines ("Could start at 10:00") and offers the
  change in a "Late entry / early leave proposals" box, with a selector to tell the families about
  less than allowed (e.g. one hour late instead of two) and send a guard to the rest. "Propose
  notice" opens a pre-filled draft ems.notice for that group's students and families, worded like
  the centre's own ("Due to the justified absence of the assigned teacher, ..."), sent from the
  notice's own form; once sent or scheduled, those lines are struck out ("Starts at 10:00") and need
  no guard. A shorter change than allowed is never flagged for correction.
- Nothing is automatic. When an absence changes afterwards (refused, cancelled, shortened, or a
  co-teacher turns out to be in), a "Guards no longer needed" box offers "Release guard", and the
  proposals box offers "Propose correction" when the families were told more than the absences now
  allow (a new draft with the corrected time, or back to the usual timetable). Both boxes are only
  shown to whoever can act on them.
- Coverage and communications are keyed by teacher + date + period + group, never by the absence
  record: what was organised on an expected absence (ems.absence_pending) stays when the teacher
  files the real request, and only the extra days/hours it adds come up as new lines.
- A day already over can no longer be managed.
- The guard duty board opens on the absences table, now the first of its two views.
- The board keeps its week, day, shift, view and levels in the URL: coming back from a notice (breadcrumbs
  or the browser's back button), reloading or sharing the link returns to the same place.
- Every struck-out line carries an info icon on its left and explains why it needs no guard
  (co-taught, guard sent, or families told) when hovered or clicked anywhere, for every teacher; for
  a guard already sent, the popover lets whoever organises the absence change or remove it.

## Communications open to Department and Seminar chiefs:
- Department and Seminar chiefs now see Communications > Notices and can send notices to the
  students and families of the groups their department teaches: every group where a teacher of
  their department (or of a sub-department) has classes, resolved from the teaching assignments
  that follow the teachers' schedules, so there is nothing to configure.
- They see their own notices and can read (not edit) other people's notices addressed to those
  groups; the Groups field only offers those groups and the server refuses any other.
- The guard duty board's timetable-change notices are ordinary notices of theirs.

# Internal changes:

## devel.sh cancels everything a production copy left pending:
- Its first step now runs as the postgres superuser, before the Odoo service can reach the
  database: it cancels every unfinished queue job (any state, waiting-on-dependency ones included),
  Odoo's own outgoing mail queue and outgoing SMS, stops with the service down if anything is left,
  and only then grants the odoo role access back (so it also works on a copy locked right after
  pg_restore).

## Department scope for notices:
- ems.group.department_chief_user_ids (non-stored, searchable; models/communications/
  notice_department_scope.py): Department/Seminar chiefs of the departments, or ancestor
  departments, of the teachers with an ems.teaching for the group. Drives the record rules,
  ems.notice.available_group_ids (form domain) and _check_department_chief_groups. Users holding
  academic admin, Director, Head of Studies or Quality admin are not limited.
- Tests: department scope unit tests and TestNoticeDepartmentChiefTour (as a department chief).


## New model ems.absence_cover and timetable-change fields on ems.notice:
- ems.absence_cover (mail.thread): one guard per absent teacher's class and period
  (constraint), read-only ACL for teachers; all writes go through board_assign()/board_release(),
  which re-check the hierarchy (hr.employee.tutor_scope_user_ids minus the employee's own user),
  the date, that the class still needs a guard and that the guard is a valid candidate.
- ems.notice gains absence_date/absence_group_id/absence_change_type/absence_change_hour
  (models/communications/notice_absence_change.py); board_propose_absence_change() creates or
  reopens the draft. A constraint keeps such a notice addressed to its own group only, and the
  form shows a banner and locks its groups.
- Department chiefs get ems.notice/ems.notice.line ACLs and record rules: read their own notices
  and those addressed to their department's groups, write only their own
  (rule_notice_department_chief_read/_own + line variants).
- ems.course gains the day/block logic (_get_group_day_blocks, _expected_absence_changes,
  _get_absence_change_states, _get_needed_absence_block, _get_guard_candidates,
  _get_board_absence_management); get_guard_duty_board_data() now also returns per-row cover /
  authorized / proposed / can_manage, per-line guard candidates and colours, and the day's
  pending actions. Teacher entries in the payload now carry their id.
- Tests: TestAbsenceCoverage (30 tests), TestAbsenceCoverageTour (as a department chief);
  TestGuardDutyBoard's fixtures extracted to a reusable GuardDutyBoardCase.
- Docs: "Managing absences from the board" in the guard duty board dev doc, notice dev doc
  access table, teachers' guard duty manual ("Organising an absence") and a pointer in the Head
  of Studies absences manual, in ca/es/en. Automatic mode planned in
  plans/absence_management_automation.md.

# Fixes:

## Guard duty board PDF: guard boxes lost their border:
- In the PDF, a guard's box combined a static class with a dynamic one, and QWeb replaces the
  static class instead of merging it, so every guard badge printed without its border. Both
  badges (timetable and absences table) now build the whole class list in one expression.

## Rich-text editor: the Catalan grave accent (à, è, ò) could not be typed:
- In every rich-text field (notices included), the dead key of the grave accent sends a "`" that is
  still being composed; Odoo's inline-code shortcut reacted to it, moved the selection and the
  browser cancelled the composition, so the accent never reached the letter (Firefox and Chrome).
  EMS now patches that shortcut to ignore a character still being composed; a plain backtick still
  makes inline code.
