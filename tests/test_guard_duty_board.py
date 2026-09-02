import json
from datetime import date

from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestGuardDutyBoard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher User (Guard Duty Board)',
            'login': 'test_teacher_for_guard_duty_board',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        # get_guard_duty_board_lines() is deliberately not course-scoped (see
        # models/attendance/guard_duty_board.py's own NOTE) - any ems.course record works to call
        # it on, this one is only ever used as that call target, never filtered against. Reusing
        # the dev DB's own current course avoids colliding with it on the unique_course_name
        # constraint (a freshly create()'d course defaults its start/end to this real year too).
        cls.course = cls.env.company.current_course_id
        if not cls.course:
            cls.course = cls.env['ems.course'].create({'start': 1999, 'end': 2000})
        # get_guard_duty_board_data()/get_current_course_data() read env.company.current_course_id
        # directly rather than taking a course argument (see guard_duty_board.py's own docstrings) -
        # a fresh DB (CI, unlike this box's own dev DB) has no "current course" configured at all,
        # so this must be set explicitly rather than assumed, matching every other test that needs
        # one (test_course_transition.py, test_year_record.py, test_em_grading_wizard.py...).
        cls.env.company.current_course_id = cls.course
        cls.level, cls.study = create_level_study(cls, 'TGDB', level={'name': 'Test Level (Guard Duty Board)'}, study={
            'code': 'TGDB001', 'name': 'Test Study (Guard Duty Board)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TGDB001',
            'acronym': 'TGDB',
            'name': 'Test Subject (Guard Duty Board)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TGDB-A',
            'name': 'Test Space (Guard Duty Board)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.space_b = cls.env['ems.space'].create({
            'code': 'TGDB-B',
            'name': 'Test Space B (Guard Duty Board)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.group_a = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TGDBA', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'space_id': cls.space.id, 'shift': 'morning',
        })
        cls.group_b = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TGDBB', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'space_id': cls.space_b.id, 'shift': 'morning',
        })
        cls.non_teaching_guard = cls.env.ref('ems.non_teaching_g')
        cls.non_teaching_break = cls.env.ref('ems.non_teaching_br')
        cls.teacher_a = cls.env['hr.employee'].create({'name': 'Test Teacher A (Guard Duty Board)', 'employee_type': 'teacher'})
        cls.teacher_b = cls.env['hr.employee'].create({'name': 'Test Teacher B (Guard Duty Board)', 'employee_type': 'teacher'})
        cls.teacher_guard = cls.env['hr.employee'].create({'name': 'Test Teacher Guard (Guard Duty Board)', 'employee_type': 'teacher'})

    def _new_calendar(self, teacher, name):
        calendar = self.env['resource.calendar'].create({'name': name})
        teacher.resource_calendar_id = calendar
        return calendar

    def test_is_guard_seeded_on_guard_non_teaching_type(self):
        self.assertTrue(self.non_teaching_guard.is_guard)
        self.assertFalse(self.non_teaching_break.is_guard)

    def test_attendance_ids_aggregate_across_teachers(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Aggregation)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Aggregation)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_b.id], 'name': 'TGDBB: TGDB',
        }])

        teaching = self.course._get_guard_duty_board_attendance_ids().filtered('subject_id')
        # Not assertEqual: this runs against the real dev DB, whose other real teachers/groups
        # also legitimately show up in this deliberately centre-wide (not course-scoped, see
        # models/attendance/guard_duty_board.py's own NOTE) aggregation - only assert OUR fixtures
        # are included, not that they're the only ones.
        self.assertLessEqual({self.teacher_a, self.teacher_b}, set(teaching.mapped('employee_id')))

    def test_attendance_ids_excludes_rows_on_an_archived_calendar(self):
        """Defense-in-depth (2026-09-01, see plans/course_transition_stale_teacher_assignments.md):
        a row can be active=True while its own parent calendar is archived - e.g. a leftover
        non-teaching commitment on a calendar that has since rolled over to a new one for a
        different course. Must never surface here regardless of the row's own active flag -
        deliberately reactivates the row AFTER archiving the calendar, so this test isolates
        the board's own filter from 'ems_working_schedule.action_archive()' 's cascade (covered
        separately in test_course_transition.py)."""
        calendar = self._new_calendar(self.teacher_guard, 'Test Calendar Archived (Aggregation)')
        guard_row = self.env['resource.calendar.attendance'].create({
            'calendar_id': calendar.id, 'name': 'Test Guard (Aggregation)',
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id,
        })
        calendar.action_archive()
        guard_row.action_unarchive()

        rows = self.course._get_guard_duty_board_attendance_ids()

        self.assertNotIn(guard_row, rows)

    def test_get_guard_duty_board_lines_groups_are_columns(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Columns)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Columns)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_b.id], 'name': 'TGDBB: TGDB',
        }])

        data = self.course.get_guard_duty_board_lines('0', 'morning')

        # Not assertEqual: real dev-DB groups with a Monday morning class legitimately show up
        # as columns too (see the NOTE in test_attendance_ids_aggregate_across_teachers).
        self.assertLessEqual({self.group_a.id, self.group_b.id}, set(data['groups'].mapped('id')))
        matching = [line for line in data['lines'] if line['time_label'] == '09:00-10:00']
        self.assertEqual(len(matching), 1)
        cell_by_group = {cell['group'].id: cell for cell in matching[0]['cells']}
        self.assertEqual(cell_by_group[self.group_a.id]['entries'].employee_id, self.teacher_a)
        self.assertEqual(cell_by_group[self.group_b.id]['entries'].employee_id, self.teacher_b)

    def test_get_guard_duty_board_lines_lists_guard_teachers_without_a_column(self):
        calendar_guard = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (Guard List)')
        calendar_guard.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard',
        }])

        data = self.course.get_guard_duty_board_lines('0', 'morning')

        matching = [line for line in data['lines'] if line['time_label'] == '09:00-10:00']
        self.assertEqual(len(matching), 1)
        self.assertIn(self.teacher_guard, matching[0]['guards'].mapped('employee_id'))
        # A guard-duty entry has no group of its own (see resource.calendar.attendance.group_ids'
        # own NOTE on non-teaching rows) - it must never show up in any group's cell either.
        cell_teachers = {teacher for cell in matching[0]['cells'] for teacher in cell['entries'].mapped('employee_id')}
        self.assertNotIn(self.teacher_guard, cell_teachers)

    def test_get_guard_duty_board_lines_respects_shift_window(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Shift Window)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 16, 'hour_to': 17, 'day_period': 'afternoon',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB (afternoon)',
        }])

        morning = self.course.get_guard_duty_board_lines('0', 'morning')
        afternoon = self.course.get_guard_duty_board_lines('0', 'afternoon')

        self.assertNotIn('16:00-17:00', {line['time_label'] for line in morning['lines']})
        self.assertIn('16:00-17:00', {line['time_label'] for line in afternoon['lines']})

    def test_get_guard_duty_board_lines_co_teaching_lists_every_teacher(self):
        """A co-taught cell (two teachers, same group, same period) must list BOTH names, not
        just whichever teacher's own resource.calendar.attendance row got filtered to first —
        each co-teacher has their own row for the shared class (see
        resource.calendar.attendance.employee_id's own NOTE), so naively picking cell['entries'][:1]
        would silently drop every co-teacher but one."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Co-teaching)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Co-teaching)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])

        data = self.course.get_guard_duty_board_lines('0', 'morning')

        matching_line = next(line for line in data['lines'] if line['time_label'] == '09:00-10:00')
        cell = next(cell for cell in matching_line['cells'] if cell['group'].id == self.group_a.id)
        self.assertEqual(set(cell['teachers'].mapped('display_name')), {self.teacher_a.display_name, self.teacher_b.display_name})

    def test_get_guard_duty_board_data_is_json_safe_and_matches_current_course(self):
        """get_guard_duty_board_data() is @api.model and resolves 'the current course' itself
        (env.company.current_course_id) rather than taking a course argument - see
        models/attendance/guard_duty_board.py's own docstring for why. Also verifies the data is
        JSON-safe (no stray recordsets), and that the short 'acronym' (not the full subject
        title) and every co-teacher's name are used, matching the compact cell layout."""
        current_course = self.env.company.current_course_id
        self.assertTrue(current_course, "This dev DB must have a current course configured for this test to be meaningful.")

        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (JSON)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])
        calendar_guard = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (JSON)')
        calendar_guard.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard',
        }])

        data = self.env['ems.course'].get_guard_duty_board_data('0', 'morning')
        json.dumps(data)  # raises TypeError if anything isn't JSON-safe (e.g. a stray recordset)

        matching_group = next(group for group in data['groups'] if group['id'] == self.group_a.id)
        self.assertIsInstance(matching_group['name'], str)
        matching_line = next(line for line in data['lines'] if line['time_label'] == '09:00-10:00')
        self.assertIn(self.teacher_guard.display_name, matching_line['guards'])
        cell = next(cell for cell in matching_line['cells'] if cell['group_id'] == self.group_a.id)
        self.assertEqual(cell['teachers'], [self.teacher_a.display_name])
        self.assertEqual(cell['subject'], self.subject.acronym)

    def test_get_current_course_data(self):
        current_course = self.env.company.current_course_id
        data = self.env['ems.course'].get_current_course_data()
        self.assertEqual(data, {'id': current_course.id, 'name': current_course.name})

    def test_teacher_can_call_board_methods(self):
        """A plain group_teacher user must be able to call every board method without an
        AccessError - colleagues' schedules aren't secret (see the developer's own feedback that
        drove this feature), and base Odoo's own ACL already grants every internal user read
        access to resource.calendar/resource.calendar.attendance; ems.course itself already
        grants group_teacher read access too (ems.access_ems_course_teacher in
        security/ir.model.access.csv) - no new ACL rows were needed for this feature at all."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Teacher Access)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])

        course = self.course.with_user(self.teacher_user)
        data = course.get_guard_duty_board_lines('0', 'morning')
        self.assertTrue(data['lines'])
        json_data = self.env['ems.course'].with_user(self.teacher_user).get_guard_duty_board_data('0', 'morning')
        self.assertTrue(json_data['lines'])

    def test_report_guard_duty_board_renders(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (PDF)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])
        calendar_guard = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (PDF)')
        calendar_guard.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard',
        }])

        content, content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_guard_duty_board', [self.course.id])

        self.assertTrue(content)
        self.assertIn(content_type, ('pdf', 'html'))
        self.assertIn(self.teacher_a.name.encode(), content)
        self.assertIn(self.teacher_guard.name.encode(), content)

    def test_report_guard_duty_board_scopes_to_one_day_via_context(self):
        """The "Download PDF" button (guard_duty_board.js) always passes a 'guard_duty_weekday'
        context key so the PDF only ever covers the day the user was looking at, not the whole
        week - confirmed here two ways: the requested day's teacher IS in the output, and a
        DIFFERENT day's teacher (created on Tuesday, while the PDF is requested for Monday) is
        NOT - proving the report doesn't fall back to rendering every weekday regardless."""
        calendar_monday = self._new_calendar(self.teacher_a, 'Test Calendar A (PDF Monday)')
        calendar_monday.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB (Monday)',
        }])
        calendar_tuesday = self._new_calendar(self.teacher_b, 'Test Calendar B (PDF Tuesday)')
        calendar_tuesday.apply_schedule_changes([{
            'dayofweek': '1', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB (Tuesday)',
        }])

        content, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0').\
            _render_qweb_pdf('ems.report_guard_duty_board', [self.course.id])

        self.assertIn(self.teacher_a.name.encode(), content)
        self.assertNotIn(self.teacher_b.name.encode(), content)

    def test_report_guard_duty_board_scopes_to_one_shift_via_context(self):
        """Same as the weekday-scoping test above, but for 'guard_duty_shift': the PDF button
        also passes whichever shift the dropdown had selected, so printing while looking at
        Morning must not also render the Afternoon table (and vice versa)."""
        calendar_morning = self._new_calendar(self.teacher_a, 'Test Calendar A (PDF Morning)')
        calendar_morning.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB (morning)',
        }])
        calendar_afternoon = self._new_calendar(self.teacher_b, 'Test Calendar B (PDF Afternoon)')
        calendar_afternoon.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 16, 'hour_to': 17, 'day_period': 'afternoon',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB (afternoon)',
        }])

        content, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0', guard_duty_shift='morning').\
            _render_qweb_pdf('ems.report_guard_duty_board', [self.course.id])

        self.assertIn(self.teacher_a.name.encode(), content)
        self.assertNotIn(self.teacher_b.name.encode(), content)
        self.assertNotIn(b'Afternoon', content)
