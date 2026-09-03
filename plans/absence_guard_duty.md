# Guard duty: covering the lessons an absence leaves uncovered

**Status: current as of 2026-09-03. Not implemented.** Split out of `plans/absence_management.md`
when the absence feature itself landed (branch `376-absence-management`); everything else in that
plan is implemented and documented in `docs/en/developers/employees/absence.md`.

**Deferred deliberately (2026-09-03), not abandoned.** Guard duty is still being designed at the
centre: several teachers are on guard in the same period, and nothing yet decides which of them
covers a given absence. Until that is settled there is no way to say who a notification should
even go to, so this waits for its own issue.

### What the exploration found, which invalidates the first sketch

- **Attendance sessions do not exist in advance.** An `ems.attendance_session_header` is created
  when somebody opens that lesson to take attendance
  (`ems.attendance_session_header.create_scheduled_session`). For a future absence there is
  nothing to flag, so the original idea of flipping affected sessions to `mode = 'guard'` cannot
  work. The state has to be derived at read time instead.
- **A guard mode already exists.** `get_guard_sessions(date)` and `get_guard_planned(date)` show
  a guard teacher everything happening that day that is not theirs - both already keyed by a
  concrete date. What is missing is only the distinction between "not my class" and "this class
  has no teacher today".
- The **guard duty board** (`models/attendance/guard_duty_board.py`) is weekday-based, with no
  concrete date, so surfacing absences there needs a date picker added first - a JS change to a
  screen already in use. The date-based guard screen is the cheaper and more natural home.

### The resolver, written and tested, then lifted out

Built and green against the real models, then removed from the module rather than shipped
unused. Drop it back into `models/employees/absence.py` (on `hr.leave`) and
`tests/test_absence.py` when the issue is picked up.

```python
    # --- Guard duty -------------------------------------------------------------------------

    def _ems_affected_schedules(self):
        """The lessons this absence leaves uncovered, as {date: ems.attendance_schedule}.

        Resolved on demand rather than written anywhere, because there is nothing to write to:
        an 'ems.attendance_session_header' only comes into existence when somebody opens that
        lesson to take attendance (see create_scheduled_session), so for a future absence the
        sessions simply do not exist yet. Guard mode already asks the same question of a date
        (get_guard_planned) - this answers which of those answers are uncovered rather than
        merely someone else's.

        Only approved absences count: a request still pending is not yet a reason for anyone to
        cover a class. sudo() because a guard teacher legitimately needs to see schedules that
        are not theirs, the same justification get_guard_sessions() carries.
        """
        self.ensure_one()
        if self.state != 'validate' or not self.employee_id or not self.request_date_from:
            return {}
        schedules_by_date = {}
        date_to = self.request_date_to or self.request_date_from
        for offset in range((date_to - self.request_date_from).days + 1):
            day = self.request_date_from + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            schedules = self.env['ems.attendance_schedule'].sudo().search([
                ('attendance_template_id.teacher_ids', 'in', self.employee_id.id),
                ('attendance_template_id.start_date', '<=', day),
                ('attendance_template_id.end_date', '>=', day),
                ('weekday', '=', str(day.weekday())),
            ])
            if not self.ems_full_day:
                # A partial absence only uncovers the lessons it actually overlaps: arriving an
                # hour late leaves the afternoon alone.
                schedules = schedules.filtered(
                    lambda schedule: (schedule.start_time < self.request_hour_to
                                      and schedule.end_time > self.request_hour_from))
            if schedules:
                schedules_by_date[day] = schedules
        return schedules_by_date

    @api.model
    def _ems_uncovered_schedule_ids(self, date):
        """The ids of the schedules left uncovered on `date` by an approved absence.

        The reverse of '_ems_affected_schedules', for the screens that start from a day and ask
        what is missing from it - the guard teacher's own list, and the guard duty board.
        """
        day = fields.Date.to_date(date)
        absences = self.sudo().search([
            ('state', '=', 'validate'),
            ('request_date_from', '<=', day),
            ('request_date_to', '>=', day),
        ])
        uncovered = set()
        for absence in absences:
            schedules = absence._ems_affected_schedules().get(day)
            if schedules:
                uncovered.update(schedules.ids)
        return sorted(uncovered)
```

Its tests, which pin the rules worth keeping - a whole-day absence uncovers every lesson, a
partial one only what it overlaps (arriving an hour late leaves the afternoon alone), and a
request still pending uncovers nothing:

```python
    # --- Guard duty ------------------------------------------------------------------------

    def _create_lesson(self, teacher, day, start_time, end_time):
        """One weekly lesson for `teacher`, valid around `day` and on its weekday."""
        level, study, group = create_level_study_group(self, f'GD{int(start_time)}')
        subject = self.env['ems.subject'].create({
            'code': f'GDS{int(start_time)}', 'acronym': f'GD{int(start_time)}',
            'name': f'Test Guard Subject {start_time}',
            'study_ids': [Command.link(study.id)],
        })
        template = self.env['ems.attendance_template'].create({
            'start_date': day - timedelta(days=7),
            'end_date': day + timedelta(days=7),
            'teacher_ids': [Command.link(teacher.id)],
            'group_ids': [Command.link(group.id)],
            'study_ids': [Command.link(study.id)],
            'subject_id': subject.id,
        })
        return self.env['ems.attendance_schedule'].create({
            'weekday': str(day.weekday()),
            'start_time': start_time,
            'end_time': end_time,
            'space_id': self.env['ems.space'].create({
                'code': f'GDR{int(start_time)}', 'name': f'Test Room {start_time}',
                'space_type_id': self.env.ref('ems.space_type_classroom').id,
                'work_location_id': self.env.ref('ems.work_location_main').id,
            }).id,
            'attendance_template_id': template.id,
        })

    def test_an_approved_whole_day_absence_uncovers_every_lesson(self):
        monday = self._monday()
        morning = self._create_lesson(self.employee, monday, 9.0, 10.0)
        afternoon = self._create_lesson(self.employee, monday, 16.0, 17.0)
        leave = self._create_leave(self.type_justified, monday, ems_full_day=True)
        leave.action_approve()

        self.assertEqual(leave._ems_affected_schedules().get(monday), morning | afternoon)

    def test_a_partial_absence_only_uncovers_what_it_overlaps(self):
        """Arriving an hour late leaves the afternoon alone."""
        monday = self._monday()
        morning = self._create_lesson(self.employee, monday, 9.0, 10.0)
        self._create_lesson(self.employee, monday, 16.0, 17.0)
        leave = self._create_leave(self.type_justified, monday, hour_from=8.5, hour_to=10.5)
        leave.action_approve()

        self.assertEqual(leave._ems_affected_schedules().get(monday), morning)

    def test_a_request_still_pending_uncovers_nothing(self):
        """Nobody has to cover a class for an absence that has not been approved."""
        monday = self._monday()
        self._create_lesson(self.employee, monday, 9.0, 10.0)
        leave = self._create_leave(self.type_justified, monday, ems_full_day=True)

        self.assertEqual(leave.state, 'confirm')
        self.assertFalse(leave._ems_affected_schedules())

    def test_the_uncovered_lessons_of_a_day_can_be_asked_for_directly(self):
        monday = self._monday()
        lesson = self._create_lesson(self.employee, monday, 9.0, 10.0)
        leave = self._create_leave(self.type_justified, monday, ems_full_day=True)
        leave.action_approve()

        self.assertIn(lesson.id, self.env['hr.leave']._ems_uncovered_schedule_ids(monday))
        self.assertNotIn(lesson.id,
                         self.env['hr.leave']._ems_uncovered_schedule_ids(monday + timedelta(days=1)))
```

The test fixture needs `create_level_study_group` from `tests/common.py`, and a space built with
`ems.space_type_classroom` / `ems.work_location_main` - `ems.space` requires both.

