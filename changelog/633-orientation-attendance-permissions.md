# Changes

## Attendance reports: the pivot and the PDFs share one scope, escalating by hierarchy (issue #633):
- The "Reports" screen (pivot/graph, also opened from a student's form) and the attendance PDF
  wizard now decide what each user sees with a single method,
  ems.attendance_session_line._get_reports_domain(). Before, the wizard scoped its dropdowns with
  ems.teaching and its lines with the session headers' record rules, while the pivot used the
  attendance templates: Guidance (Marina) could see a student in the pivot but not pick them in the
  PDF wizard.
- The scope escalates by the chain of command, never by role alone: a teacher sees the subjects
  they teach (the attendance templates they are a teacher of; a roll-call taken on guard duty
  belongs to the template's teacher, not to whoever took it), a tutor every subject of their
  students, and the Department/Seminar Chief and Head of Studies/Deputy above the tutor the same
  (tutor_scope_user_ids, #483). A Department/Seminar Chief, and the Head of Studies/Deputy of the
  area (as the area department's manager, child_of), also see every student of the studies their
  department manages (ems.study.managing_department_id, #622) - the same two ways the guard duty
  board already uses. Director (and the administrator), Guidance, Coexistence and Secretariat see
  the whole centre.
- Behaviour change: Head of Studies/Deputy no longer see the whole centre on these two screens, only
  their area (they keep reading every student's file elsewhere, #448). ESO and Batxillerat have no
  managing department yet in the dev DB: production needs the "ESO / BTX" area set as their managing
  department for its Head of Studies to see them through the studies.
- The wizard's dropdowns (students, groups, subjects) are derived from the lines in scope
  (_read_group), its PDFs print exactly those lines (searched as the user, rendered under sudo), and
  the by-subject report now filters by each student's own group, like the by-group one. Current
  course only for everyone. The old teacher-scoping helpers (_get_teacher_*_ids,
  _get_tutor_group_ids, _search_scoped_lines, _get_sessions, the employee id <= 1 "admin" bypass)
  are gone.
- Secretariat can now create the wizard (its ⚙ entry on the pivot raised an AccessError before).
- Shared helpers: hr.department._headed_by(users) and ems.group._managed_by_departments_domain(),
  now also used by the notices' department scope instead of its hand-written copy.

## Schedule topics are separate subjects in attendance (issue #633):
- In CFGB, Physical Education and English are taught inside modules (Ciències aplicades I,
  Comunicació i ciències socials I) by teachers of other departments; the schedule blocks already
  tell them apart with their topic (#428), but attendance merged them under the module, so the
  pivot showed no Physical Education or English row (Marina's first report).
- The topic is now part of the attendance template's identity: the schedule sync keys templates by
  (subject, topic, groups), the uniqueness check includes it, and a topic change archives the old
  template and creates a new one, so past sessions keep their topic. Existing templates got their
  topic from their linked schedule blocks when the column was created (stored compute with no
  dependencies; no migration).
- Sessions and lines carry the topic, and lines a stored subject_label ("ACR: Subject - Topic");
  the pivot, the graph and the PDFs group by it, and the by-subject wizard offers each label as its
  own subject. The template's display name shows the topic too.

## Attendance reports screen: print button, and no list opening on a cell click (issue #633):
- A printer button, right after the pivot's download one (and last in the graph's toolbar), opens the
  PDF report wizard: teachers never found it in the ⚙ menu, which keeps it as well. Done with a
  js_class on the pivot and graph views that only swaps their toolbar template and renderer, loaded in
  web.assets_backend_lazy like the views it extends.
- Clicking a pivot cell or a graph bar no longer opens the bare attendance lines in a default list
  (disable_linking).
- The three manual screenshots showing the pivot toolbar were regenerated.

# Internal changes

## Attendance reports tests and docs (issue #633):
- New TestAttendanceReportScopeLadder: the chain of command for 13 profiles and a parity test (for
  every profile, the wizard's students/groups/subjects are those of the pivot's lines, and the
  by-student PDFs add up to exactly those lines); a mutation check (Head of Studies seeing the whole
  centre) makes it fail as expected. Topic sync tests in TestEmployeeSyncScheduleFromCalendar.
  Existing report tests adapted to the line-based dropdowns and the subject label.
- Developer doc attendance_reports.md rewritten to describe the current behaviour; topic section in
  attendance_template.md; teachers, tutors, Head of Studies and Secretariat manuals updated in the
  three languages (what the lists offer, topics, area scope); admin manuals for studies (managing
  department) and working schedules (topics).
