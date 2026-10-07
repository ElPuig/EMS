# What's new:

## Managing absences from the guard duty board's absences table (issues #539, #571, #581):
- The absent teacher's chain of command (their Seminar/Department Chief, then Head of Studies or
  Deputy, then Direction; never every holder of those roles, never the absent teacher) organises
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
  first or last of the group's whole day, tags those lines ("Could start at 10:00") and offers
  "Propose notice" in a new "Pending actions for this day" box. It opens a pre-filled draft
  ems.notice for that group's students and families, sent from the notice's own form; once sent
  or scheduled, those lines are struck out ("Starts at 10:00") and need no guard.
- Nothing is automatic. When an absence changes afterwards (refused, cancelled, shortened, or a
  co-teacher turns out to be in), the pending-actions box offers "Release guard" for a guard no
  longer needed, and "Propose correction" for a sent notice that no longer matches (a new draft
  with the corrected time, or back to the usual timetable).
- Coverage and communications are keyed by teacher + date + period + group, never by the absence
  record: what was organised on an expected absence (ems.absence_pending) stays when the teacher
  files the real request, and only the extra days/hours it adds come up as new lines.
- A day already over can no longer be managed.

# Internal changes:

## New model ems.absence_cover and timetable-change fields on ems.notice:
- ems.absence_cover (mail.thread): one guard per absent teacher's class and period
  (constraint), read-only ACL for teachers; all writes go through board_assign()/board_release(),
  which re-check the hierarchy (hr.employee.tutor_scope_user_ids minus the employee's own user),
  the date, that the class still needs a guard and that the guard is a valid candidate.
- ems.notice gains absence_date/absence_group_id/absence_change_type/absence_change_hour
  (models/communications/notice_absence_change.py); board_propose_absence_change() creates or
  reopens the draft. A constraint keeps such a notice addressed to its own group only, and the
  form shows a banner and locks its groups.
- Department chiefs get ems.notice/ems.notice.line ACLs plus record rules limited to their own
  timetable-change notices; the Communications menu stays hidden from them.
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
