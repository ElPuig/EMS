import json
from datetime import date, timedelta

from odoo.tests.common import TransactionCase

from .common import create_level_study, create_level_study_group, mock_outgoing_email


class TestGuardDutyBoard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Approving an absence posts to the chatter and notifies its followers - see
        # CLAUDE.md's 'Email safety in tests'.
        mock_outgoing_email(cls)
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
        cls.non_teaching_guard_wc = cls.env.ref('ems.non_teaching_gwc')
        cls.teacher_a = cls.env['hr.employee'].create({'name': 'Test Teacher A (Guard Duty Board)', 'employee_type': 'teacher'})
        cls.teacher_b = cls.env['hr.employee'].create({'name': 'Test Teacher B (Guard Duty Board)', 'employee_type': 'teacher'})
        cls.teacher_guard = cls.env['hr.employee'].create({'name': 'Test Teacher Guard (Guard Duty Board)', 'employee_type': 'teacher'})
        # A second, distinct level/study/group (issue #390's level filter) - deliberately its own
        # brand-new 'ems.level', never shared with the real dev DB's own data, so filtering tests
        # below can assert strict exclusion rather than the "assertLessEqual" style the rest of
        # this centre-wide-aggregation test class needs (see e.g. test_attendance_ids_aggregate_
        # across_teachers' own NOTE).
        cls.level2, cls.study2, cls.group_c = create_level_study_group(
            cls, 'TGDB2', level={'name': 'Test Level 2 (Guard Duty Board)'},
            study={'name': 'Test Study 2 (Guard Duty Board)', 'date': date.today()},
            group={'course': 1, 'acronym': 'TGDBC', 'space_id': cls.space_b.id, 'shift': 'morning'},
        )
        cls.teacher_c = cls.env['hr.employee'].create({'name': 'Test Teacher C (Guard Duty Board, Level 2)', 'employee_type': 'teacher'})
        # A subject of its own, valid for 'study2' only - 'self.subject' is only valid for
        # 'self.study' (see 'ems.attendance_template._check_subject_valid_for_all_studies'), so a
        # teaching entry for 'group_c' needs a subject actually taught in study2.
        cls.subject2 = cls.env['ems.subject'].create({
            'code': 'TGDB2001', 'acronym': 'TGDB2', 'name': 'Test Subject 2 (Guard Duty Board)',
            'study_ids': [(6, 0, [cls.study2.id])],
        })

    def _new_calendar(self, teacher, name):
        # 'employee_id' (matching how every real personal calendar is created - see
        # hr.employee.create()/course_transition_wizard.py's own 'resource.calendar' creates)
        # is what '_get_guard_duty_board_attendance_ids' now uses to tell a teacher's own
        # working schedule apart from Odoo's generic default calendar (e.g. "Standard 40
        # hours/week", 'employee_id' False) - omitting it here made every fixture in this class
        # indistinguishable from that generic calendar to the board's own aggregation. Clearing
        # 'attendance_ids' also mirrors 'seed_from_framework()' - a plain create() with no
        # attendance_ids auto-populates default Mon-Fri 8-12/13-17 rows (Odoo's own
        # 'resource.calendar' default), which would otherwise leak into the board's centre-wide
        # aggregation as noise even before any of this test's own schedule is applied (found
        # 2026-09-08 via CI on a clean install, where that generic calendar's rows exist and
        # this dev DB's own history happens not to have any).
        calendar = self.env['resource.calendar'].create({
            'name': name, 'employee_id': teacher.id, 'attendance_ids': [(5, 0, 0)],
        })
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
        # Every teacher is reported as {'name', 'absence'}, never a bare name - see
        # _guard_duty_teacher_data(). With no date asked for, nobody can be absent.
        self.assertIn(self.teacher_guard.display_name,
                      [guard['name'] for guard in matching_line['guards']])
        cell = next(cell for cell in matching_line['cells'] if cell['group_id'] == self.group_a.id)
        self.assertEqual(cell['teachers'], [{'name': self.teacher_a.display_name, 'absence': False, 'is_wc': False}])
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

    def test_get_guard_duty_board_lines_merges_a_guard_absorbed_by_a_longer_guard_period(self):
        """Regression for issue #410: a teacher's own personal schedule can end a guard-duty slot
        early (e.g. a shorter working day that block) while a colleague's guard for the same
        start time runs the full period - found in production as a guard ending 13:25-14:00
        sitting right next to another one ending 13:25-14:25. Before the fix this rendered as two
        rows, the short one nearly empty (no cells, one guard); the short period must fold into
        the long one's row instead of getting a row of its own."""
        calendar_guard = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (Absorbed)')
        calendar_guard.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 9.5, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard (short)',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Absorbed)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard (full)',
        }])

        data = self.course.get_guard_duty_board_lines('0', 'morning')

        time_labels = {line['time_label'] for line in data['lines']}
        self.assertNotIn('09:00-09:30', time_labels)
        matching = [line for line in data['lines'] if line['time_label'] == '09:00-10:00']
        self.assertEqual(len(matching), 1)
        # Not assertEqual: this dev DB's own real guards for Monday 9:00-10:00 legitimately show
        # up here too (this board is centre-wide, not scoped to this test's fixtures - see the
        # other tests' own NOTE) - only assert our two fixtures are included, not that they're
        # the only ones.
        self.assertLessEqual({self.teacher_guard, self.teacher_b}, set(matching[0]['guards'].mapped('employee_id')))

    def test_get_guard_duty_board_lines_merges_a_non_guard_period_absorbed_by_a_teaching_period(self):
        """Same containment bug, but for a non-teaching, non-guard entry (e.g. a coordination
        duty, 'CT'/'AC' in real data) - it has neither a group (so it never becomes a
        teaching_entries cell) nor non_teaching_is_guard (so it never becomes a guards entry
        either), so before the fix its own short period rendered as a row with absolutely
        nothing in it - worse than the guard case above, since it showed no guard name either.
        Must fold into the containing teaching period's row instead of appearing at all."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Absorbed Non-Guard)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 9.5, 'day_period': 'morning',
            'non_teaching': self.non_teaching_break.id, 'name': 'Break (short)',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Absorbed Non-Guard)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_b.id], 'name': 'TGDBB: TGDB',
        }])

        data = self.course.get_guard_duty_board_lines('0', 'morning')

        time_labels = {line['time_label'] for line in data['lines']}
        self.assertNotIn('09:00-09:30', time_labels)
        self.assertEqual(len([line for line in data['lines'] if line['time_label'] == '09:00-10:00']), 1)

    def test_get_guard_duty_board_lines_keeps_an_uncontained_period_as_its_own_row(self):
        """The containment merge must not eat a genuinely isolated period that doesn't fall
        inside any larger one - regression guard against an over-eager merge swallowing
        legitimate standalone rows. Uses a guard entry (not a plain break) so the row also
        survives the separate "hide a period with nothing in it" rule added below - a period
        with a guard is never content-less. Uses a deliberately unusual, wide time span
        (08:06-09:54, wider than any real bell-schedule period and starting off the usual
        on-the-hour/on-the-25 marks) so it can't accidentally be absorbed by this dev DB's own
        real, unrelated schedule data - this board is centre-wide, not scoped to this test's own
        fixtures (see the other tests' own NOTE)."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Isolated)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8.1, 'hour_to': 9.9, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard (isolated)',
        }])

        data = self.course.get_guard_duty_board_lines('0', 'morning')

        self.assertIn('08:06-09:54', {line['time_label'] for line in data['lines']})

    def test_get_guard_duty_board_lines_hides_a_period_with_no_teaching_and_no_guards(self):
        """Follow-up to issue #410 (developer request, 2026-09-07): a period where literally
        nothing is scheduled anywhere in the centre - no group's class, no guard - adds no
        information and must not render as a row at all. Found in production as the Wednesday
        coordination-time slots (13:25-14:00 and 14:00-15:00): every teacher is either in a short
        coordination duty or the coordination meeting itself, and nobody is on guard duty through
        it. A non-teaching, non-guard entry (CT/AC/CM...) with nothing else running at the same
        time must disappear entirely instead of showing an empty row. Reuses the exact same
        08:06-09:54 span as the "keeps an uncontained period" test above (already confirmed there
        not to be absorbed by any of this dev DB's own real data) so this test genuinely exercises
        the "hide, don't merge" path instead of accidentally passing because the period got
        silently absorbed into some unrelated real period - which is exactly what happened with an
        earlier, narrower version of this test (08:09-08:39 turned out to sit inside a real
        08:00-09:00 entry, making the assertion pass for the wrong reason)."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Truly Blank)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8.1, 'hour_to': 9.9, 'day_period': 'morning',
            'non_teaching': self.non_teaching_break.id, 'name': 'CT (isolated, no guard)',
        }])

        data = self.course.get_guard_duty_board_lines('0', 'morning')

        self.assertNotIn('08:06-09:54', {line['time_label'] for line in data['lines']})

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

    def test_get_guard_duty_board_lines_level_filter_narrows_teaching_but_shows_any_guard_on_duty(self):
        """Level filter (issue #390): the filter only ever controls which time blocks (rows) are
        visible, built purely from the selected level's own classes - see
        docs/en/developers/attendance/guard_duty_board.md's own "Level filter" section. Once a row
        is visible, EVERY guard on duty then shows, regardless of what level (if any) that guard's
        own teacher otherwise teaches - developer feedback (2026-09-07), replacing an earlier
        version that tried deriving a guard's "own level" from their other classes that day and
        got it backwards for a guard with no teaching entry of their own at all: "no tenemos forma
        de saber si un docente es de un nivel o de otro, pero es indiferente, porque está de
        guardia y eso es lo que manda". Neither guard below teaches anything this day at all -
        both are relevant purely because their guard duty coincides with a row group_a's own
        class makes visible."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Level Filter)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])
        calendar_c = self._new_calendar(self.teacher_c, 'Test Calendar C (Level Filter, Other Level)')
        calendar_c.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject2.id, 'group_ids': [self.group_c.id], 'name': 'TGDBC: TGDB2',
        }])
        calendar_guard = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (Level Filter)')
        calendar_guard.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Level Filter, Other Guard)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard (also no teaching today)',
        }])

        data = self.course.get_guard_duty_board_lines('0', 'morning', level_ids=[self.level.id])

        self.assertIn(self.group_a, data['groups'])
        self.assertNotIn(self.group_c, data['groups'])
        matching = [line for line in data['lines'] if line['time_label'] == '09:00-10:00']
        self.assertEqual(len(matching), 1)
        guard_teachers = set(matching[0]['guards'].mapped('employee_id'))
        self.assertIn(self.teacher_guard, guard_teachers)
        self.assertIn(self.teacher_b, guard_teachers)
        cell_by_group = {cell['group'].id: cell for cell in matching[0]['cells']}
        self.assertIn(self.group_a.id, cell_by_group)
        self.assertNotIn(self.group_c.id, cell_by_group)

    def test_get_guard_duty_board_lines_level_filter_hides_a_guard_with_no_matching_row_or_break(self):
        """A guard whose own slot neither overlaps any row of the filtered level nor falls
        inside that level's own break window simply isn't relevant to this level's view -
        developer decision (2026-09-07): it stays visible under "All levels", just not here."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (No Match)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])
        calendar_guard = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (No Match)')
        calendar_guard.apply_schedule_changes([
            {'dayofweek': '0', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning',
             'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB (early)'},
            {'dayofweek': '0', 'hour_from': 12, 'hour_to': 13, 'day_period': 'morning',
             'non_teaching': self.non_teaching_guard.id, 'name': 'Guard (unrelated hour)'},
        ])

        data = self.course.get_guard_duty_board_lines('0', 'morning', level_ids=[self.level.id])

        self.assertNotIn('12:00-13:00', {line['time_label'] for line in data['lines']})

    def test_get_guard_duty_board_lines_selecting_every_level_matches_all_levels(self):
        """Checking every existing level in the filter dropdown must produce the exact same
        result as checking none at all ("All levels") - developer report (2026-09-07): a guard
        with no teaching entry that day at all (a guard-only shift, real example: Joan Sánchez
        Escudero's Monday 8h guard) was silently dropped even with every level checked. Guard
        visibility is purely time-based now (see "...narrows_teaching_but_shows_any_guard_on_duty"
        above), so this specific symptom can no longer recur - but a level-filtered view still
        only ever builds its rows from teaching entries, never from a guard-only period the way
        the unfiltered path's own periods (built from every entry) do. Checking every level is
        meant to mean "show everything", the same as checking none - unlike a real partial
        selection (e.g. the test above), which must keep hiding every row/group of the levels
        left unchecked."""
        calendar_guard = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (Every Level)')
        calendar_guard.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard (no teaching at all today)',
        }])
        all_level_ids = self.env['ems.level'].search([]).ids

        unfiltered = self.course.get_guard_duty_board_lines('0', 'morning')
        every_level_selected = self.course.get_guard_duty_board_lines('0', 'morning', level_ids=all_level_ids)

        unfiltered_guards = {teacher for line in unfiltered['lines'] for teacher in line['guards'].mapped('employee_id')}
        every_level_guards = {teacher for line in every_level_selected['lines'] for teacher in line['guards'].mapped('employee_id')}
        self.assertIn(self.teacher_guard, unfiltered_guards)
        self.assertEqual(unfiltered_guards, every_level_guards)
        self.assertEqual(
            {group.id for group in unfiltered['groups']},
            {group.id for group in every_level_selected['groups']},
        )

    def test_get_guard_duty_board_lines_level_filter_shows_break_time_guard_as_patio_row(self):
        """A guard duty scheduled specifically during a level's own break ("Patio") has no
        overlapping class of that level at all - without special handling it would just vanish
        once the level filter restricts rows to teaching-only periods (see "Break ('Patio')
        labelling" in docs/en/developers/attendance/guard_duty_board.md). It must instead render
        as its own row, marked 'is_break', once that level's own framework identifies the period
        as a break.

        Under "All levels" this same guard already has a normal row of its own (guard-only
        periods aren't restricted to teaching entries the way a level-filtered view is - see
        'get_guard_duty_board_lines' itself) - it must ALSO carry 'is_break': True there
        (2026-09-11, developer request: make a patio guard visually obvious without needing the
        level filter), since nothing else is scheduled in that same period for any group either.

        Deliberately off-grid hours (08:54-09:36, ~42min, straddling the real 08:00-09:00/
        09:00-10:00 boundary this dev DB happens to be densely scheduled around) for the
        guard/break period itself - same centre-wide-aggregation caution as
        "test_get_guard_duty_board_lines_keeps_an_uncontained_period_as_its_own_row" above, but
        cutting both ways this time: too narrow and fully inside one real hour-long class risks
        this period being silently absorbed (contained) INTO that unrelated class's own row (the
        original, pre-2026-09-11 concern); too wide (e.g. spanning a full real class rather than
        just straddling its edge) risks the reverse - this period absorbing that unrelated class
        INTO itself, which would make its own cells non-empty and wrongly suppress 'is_break' (see
        the new safety check in 'get_guard_duty_board_lines' itself). Straddling one real
        boundary without fully covering either side dodges both directions at once."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Patio)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8.1, 'hour_to': 8.9, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])
        framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (Patio)', 'is_framework': True, 'level_id': self.level.id,
            'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 8.9, 'hour_to': 9.6, 'day_period': 'morning', 'non_teaching': self.non_teaching_break.id,
        })
        calendar_guard = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (Patio)')
        calendar_guard.apply_schedule_changes([
            {'dayofweek': '0', 'hour_from': 8.1, 'hour_to': 8.9, 'day_period': 'morning',
             'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB (early)'},
            {'dayofweek': '0', 'hour_from': 8.9, 'hour_to': 9.6, 'day_period': 'morning',
             'non_teaching': self.non_teaching_guard.id, 'name': 'Patio Guard'},
        ])

        unfiltered = self.course.get_guard_duty_board_lines('0', 'morning')
        filtered = self.course.get_guard_duty_board_lines('0', 'morning', level_ids=[self.level.id])

        unfiltered_patio = [line for line in unfiltered['lines'] if line['time_label'] == '08:54-09:36']
        self.assertEqual(len(unfiltered_patio), 1)
        self.assertTrue(unfiltered_patio[0].get('is_break'))

        filtered_patio = [line for line in filtered['lines'] if line['time_label'] == '08:54-09:36']
        self.assertEqual(len(filtered_patio), 1)
        self.assertTrue(filtered_patio[0].get('is_break'))
        self.assertIn(self.teacher_guard, filtered_patio[0]['guards'].mapped('employee_id'))
        for cell in filtered_patio[0]['cells']:
            self.assertFalse(cell['entries'])

    def test_get_guard_duty_board_lines_break_flag_ignores_a_period_with_a_real_class(self):
        """The safety half of the 'is_break' rule described in get_guard_duty_board_lines' own
        docstring: under "All levels", a period that happens to coincide with one level's own
        break window must NOT be marked 'is_break' when a DIFFERENT level's group genuinely has a
        class running then - two levels can have different break hours (confirmed against this
        dev DB), so a shared clock-time slot is not by itself proof that nobody is teaching."""
        framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (Break Flag Safety)', 'is_framework': True,
            'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 12.08, 'hour_to': 13.92, 'day_period': 'morning', 'non_teaching': self.non_teaching_break.id,
        })
        # 'level2'/'group_c' (a DIFFERENT level, see setUpClass) has a genuine class at the exact
        # same clock time as 'level's own break above.
        calendar_c = self._new_calendar(self.teacher_c, 'Test Calendar C (Break Flag Safety)')
        calendar_c.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 12.08, 'hour_to': 13.92, 'day_period': 'morning',
            'subject_id': self.subject2.id, 'group_ids': [self.group_c.id], 'name': 'TGDBC: TGDB2',
        }])

        data = self.course.get_guard_duty_board_lines('0', 'morning')

        matching = [line for line in data['lines'] if line['time_label'] == '12:05-13:55']
        self.assertEqual(len(matching), 1)
        self.assertFalse(matching[0].get('is_break'))

    def test_get_guard_duty_board_data_passes_level_ids_and_is_break(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Data Level Filter)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])
        calendar_c = self._new_calendar(self.teacher_c, 'Test Calendar C (Data Level Filter, Other Level)')
        calendar_c.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject2.id, 'group_ids': [self.group_c.id], 'name': 'TGDBC: TGDB2',
        }])

        data = self.env['ems.course'].get_guard_duty_board_data('0', 'morning', level_ids=[self.level.id])
        json.dumps(data)  # raises TypeError if anything isn't JSON-safe

        self.assertIn(self.group_a.id, [group['id'] for group in data['groups']])
        self.assertNotIn(self.group_c.id, [group['id'] for group in data['groups']])
        self.assertTrue(all('is_break' in line for line in data['lines']))

    def test_get_guard_duty_board_data_flags_a_wc_guard(self):
        """'Guard (WC)' is the one guard subtype that can fall at any time of day - unlike
        'Guard (Break)', it's never redundant with the row's own 'is_break' flag - so it gets its
        own per-teacher 'is_wc' flag in the guard column, and only there: a plain 'Guard' duty in
        the exact same period must not be flagged."""
        calendar_wc = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (WC)')
        calendar_wc.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard_wc.id, 'name': 'Guard (WC)',
        }])
        calendar_plain = self._new_calendar(self.teacher_a, 'Test Calendar A (Plain Guard)')
        calendar_plain.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard',
        }])

        data = self.env['ems.course'].get_guard_duty_board_data('0', 'morning')
        json.dumps(data)  # raises TypeError if anything isn't JSON-safe

        line = next(line for line in data['lines'] if line['time_label'] == '09:00-10:00')
        guards_by_name = {guard['name']: guard for guard in line['guards']}
        self.assertTrue(guards_by_name[self.teacher_guard.display_name]['is_wc'])
        self.assertFalse(guards_by_name[self.teacher_a.display_name]['is_wc'])

    def test_report_guard_duty_board_marks_a_wc_guard(self):
        """Regression (developer report 2026-09-11): the printed PDF calls
        get_guard_duty_board_lines() directly, not the JSON-safe get_guard_duty_board_data()
        wrapper the screen uses (see that method's own 'is_wc' flag, tested above) - so it never
        got the "(WC)" marker the screen shows next to a WC guard's name. Both a WC guard AND a
        plain guard in the exact same period print their name either way (the PDF was never
        missing the teacher, only the distinguishing marker - see this file's own docstring for
        the mechanism), but only the WC one must carry '(WC)'. Covers both of the board's two
        tabs (schedule and "Absences table", issue #442), since the fix is duplicated in the
        template once per tab."""
        calendar_wc = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (PDF WC)')
        calendar_wc.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard_wc.id, 'name': 'Guard (WC)',
        }])
        calendar_plain = self._new_calendar(self.teacher_a, 'Test Calendar A (PDF Plain Guard)')
        calendar_plain.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard',
        }])

        schedule_content, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0').\
            _render_qweb_pdf('ems.report_guard_duty_board', [self.course.id])
        table_content, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0', guard_duty_view='table').\
            _render_qweb_pdf('ems.report_guard_duty_board', [self.course.id])

        for content in (schedule_content, table_content):
            self.assertIn(self.teacher_guard.name.encode(), content)
            self.assertIn(self.teacher_a.name.encode(), content)
            wc_marker_index = content.find(self.teacher_guard.name.encode())
            self.assertIn(b'(WC)', content[wc_marker_index:wc_marker_index + 200])
            plain_marker_index = content.find(self.teacher_a.name.encode())
            self.assertNotIn(b'(WC)', content[plain_marker_index:plain_marker_index + 200])

    def test_get_guard_duty_board_levels(self):
        data = self.env['ems.course'].get_guard_duty_board_levels()

        self.assertIn({'id': self.level.id, 'name': self.level.name}, data)
        self.assertIn({'id': self.level2.id, 'name': self.level2.name}, data)

    def test_report_guard_duty_board_scopes_to_levels_via_context(self):
        """Same pattern as the weekday/shift context-scoping tests above, but for
        'guard_duty_level_ids': the PDF button also forwards whichever level(s) the dropdown had
        checked, so printing while filtered to level 1 must not also render level 2's group."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (PDF Level Filter)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])
        calendar_c = self._new_calendar(self.teacher_c, 'Test Calendar C (PDF Level Filter, Other Level)')
        calendar_c.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject2.id, 'group_ids': [self.group_c.id], 'name': 'TGDBC: TGDB2',
        }])

        content, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0', guard_duty_shift='morning', guard_duty_level_ids=[self.level.id]).\
            _render_qweb_pdf('ems.report_guard_duty_board', [self.course.id])

        self.assertIn(self.group_a.name.encode(), content)
        self.assertNotIn(self.group_c.name.encode(), content)

    # --- Absences on the board --------------------------------------------------------------
    #
    # The board is keyed by weekday, absences by real date, so every one of these has to hand
    # 'get_guard_duty_board_lines' a concrete Monday for the two to meet - see the 'day'
    # argument's own docstring in models/attendance/guard_duty_board.py.

    def _monday(self):
        """A Monday inside the current course's window, matching the '0' weekday these fixtures
        use. Inside the window because the absence form's own health-allowance computation
        filters on it (see hr.leave._compute_ems_health_allowance)."""
        window = self.env.company.current_course_id.date_range()
        day = window[0] + timedelta(days=30)
        while day.weekday() != 0:
            day += timedelta(days=1)
        return day

    def _absence(self, employee, day, hour_from=None, hour_to=None, approve=True):
        vals = {
            'employee_id': employee.id,
            'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': day,
            'request_date_to': day,
            # What the "Send request" button does - a request that was never sent cannot be
            # saved at all (see hr.leave._check_ems_submitted).
            'ems_submitted': True,
            'ems_responsible_declaration': True,
        }
        if hour_from is None:
            # 'leave_type_justified' does not seed 'Whole day?' on its own (its
            # ems_full_day_default is False), and a request that is neither a whole day nor a
            # span of hours is worth zero - which hr_holidays itself refuses to approve.
            vals['ems_full_day'] = True
        else:
            vals.update({'ems_full_day': False,
                         'request_hour_from': hour_from, 'request_hour_to': hour_to})
        leave = self.env['hr.leave'].create(vals)
        if approve:
            leave.action_approve()
        return leave

    def _teaching_line(self, day, hour_from=9, hour_to=10):
        """The board row for one period of `day`'s weekday, morning shift."""
        data = self.course.get_guard_duty_board_lines(str(day.weekday()), 'morning', day=day)
        label = '%02d:00-%02d:00' % (hour_from, hour_to)
        return next(line for line in data['lines'] if line['time_label'] == label)

    def _schedule_class(self, teacher, group, name, periods=((9, 10),), dayofweek='0'):
        """One calendar for `teacher` holding exactly `periods` as lessons of `group`.

        Every period in one call: apply_schedule_changes() replaces the calendar's whole Mon-Fri
        week each time it runs (it is fed the schedule grid's full buffer, see its own
        docstring), so calling it twice would leave only the second period behind.
        """
        calendar = self._new_calendar(teacher, name)
        calendar.apply_schedule_changes([{
            'dayofweek': dayofweek, 'hour_from': hour_from, 'hour_to': hour_to,
            'day_period': 'morning', 'subject_id': self.subject.id,
            'group_ids': [group.id], 'name': f'{group.acronym}: TGDB',
        } for hour_from, hour_to in periods])
        return calendar

    def test_without_a_date_no_absence_is_resolved_at_all(self):
        """The PDF still calls this with no date (see reports/attendance/report_guard_duty_board.xml),
        and a weekday on its own can never say who is absent - the board has to keep working,
        marking nobody, rather than guessing a date of its own."""
        monday = self._monday()
        self._schedule_class(self.teacher_a, self.group_a, 'Test Calendar A (No Date)')
        self._absence(self.teacher_a, monday)

        data = self.course.get_guard_duty_board_lines('0', 'morning')

        line = next(line for line in data['lines'] if line['time_label'] == '09:00-10:00')
        cell = next(cell for cell in line['cells'] if cell['group'].id == self.group_a.id)
        self.assertEqual(cell['absences'], {})
        self.assertEqual(line['absences'], [])

    def test_an_approved_whole_day_absence_marks_the_teacher_in_their_own_cell(self):
        monday = self._monday()
        self._schedule_class(self.teacher_a, self.group_a, 'Test Calendar A (Whole Day)')
        self._absence(self.teacher_a, monday)

        line = self._teaching_line(monday)

        cell = next(cell for cell in line['cells'] if cell['group'].id == self.group_a.id)
        self.assertEqual(cell['absences'], {self.teacher_a.id: 'approved'})

    def test_a_partial_absence_only_marks_the_periods_it_overlaps(self):
        """Arriving an hour late leaves the rest of the morning covered."""
        monday = self._monday()
        self._schedule_class(self.teacher_a, self.group_a, 'Test Calendar A (Partial)',
                             periods=((9, 10), (11, 12)))
        self._absence(self.teacher_a, monday, hour_from=8.5, hour_to=10.5)

        missed = self._teaching_line(monday, 9, 10)
        covered = self._teaching_line(monday, 11, 12)

        missed_cell = next(cell for cell in missed['cells'] if cell['group'].id == self.group_a.id)
        covered_cell = next(cell for cell in covered['cells'] if cell['group'].id == self.group_a.id)
        self.assertEqual(missed_cell['absences'], {self.teacher_a.id: 'approved'})
        self.assertEqual(covered_cell['absences'], {})

    def test_a_request_still_pending_is_marked_apart_from_an_approved_one(self):
        """Whoever plans the guards wants to see what is coming, but must not confuse a request
        nobody has decided on yet with an absence that is going to happen."""
        monday = self._monday()
        self._schedule_class(self.teacher_a, self.group_a, 'Test Calendar A (Pending)')
        leave = self._absence(self.teacher_a, monday, approve=False)

        self.assertEqual(leave.state, 'confirm')
        line = self._teaching_line(monday)

        cell = next(cell for cell in line['cells'] if cell['group'].id == self.group_a.id)
        self.assertEqual(cell['absences'], {self.teacher_a.id: 'pending'})

    def test_a_refused_request_marks_nobody(self):
        monday = self._monday()
        self._schedule_class(self.teacher_a, self.group_a, 'Test Calendar A (Refused)')
        leave = self._absence(self.teacher_a, monday, approve=False)
        leave.action_refuse()

        line = self._teaching_line(monday)

        cell = next(cell for cell in line['cells'] if cell['group'].id == self.group_a.id)
        self.assertEqual(cell['absences'], {})

    def test_an_absent_guard_teacher_is_marked_in_the_guard_column(self):
        """The one who was going to cover for somebody else is the one missing - the column has
        to say so, or the period looks staffed when it is not."""
        monday = self._monday()
        calendar = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (Absent)')
        calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard',
        }])
        self._absence(self.teacher_guard, monday)

        line = self._teaching_line(monday)

        self.assertEqual(line['guard_absences'].get(self.teacher_guard.id), 'approved')

    def test_the_absence_rows_carry_the_class_that_needs_covering(self):
        """The second tab's whole point: not just who is missing, but what has to be covered -
        group, subject and room, so a guard can be sent without opening another screen."""
        monday = self._monday()
        self._schedule_class(self.teacher_a, self.group_a, 'Test Calendar A (Rows)')
        self._absence(self.teacher_a, monday)

        line = self._teaching_line(monday)

        row = next(row for row in line['absences'] if row['teacher'] == self.teacher_a)
        self.assertEqual(row['state'], 'approved')
        self.assertEqual(row['group'], self.group_a)
        self.assertEqual(row['subject'], self.subject)
        self.assertEqual(row['room'], self.space)

    def _co_teach(self, room_b=None):
        """teacher_a and teacher_b both teach group_a on Monday 9-10, each on their own calendar,
        teacher_b in `room_b` when given (a group split across two rooms) or the group's own."""
        self._schedule_class(self.teacher_a, self.group_a, 'Test Calendar A (Co-teaching)')
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Co-teaching)')
        vals = {'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB'}
        if room_b:
            vals['space_id'] = room_b.id
        calendar_b.apply_schedule_changes([vals])

    def _absence_row(self, line, teacher):
        return next(row for row in line['absences'] if row['teacher'] == teacher)

    def test_a_co_taught_class_with_one_teacher_in_is_covered(self):
        """Still listed, so everyone knows who is away, but marked as needing no guard."""
        monday = self._monday()
        self._co_teach()
        self._absence(self.teacher_a, monday)

        line = self._teaching_line(monday)

        self.assertTrue(self._absence_row(line, self.teacher_a)['covered'])
        self.assertNotIn(self.teacher_b, [row['teacher'] for row in line['absences']])

    def test_a_co_taught_class_with_both_teachers_away_is_not_covered(self):
        monday = self._monday()
        self._co_teach()
        self._absence(self.teacher_a, monday)
        self._absence(self.teacher_b, monday, approve=False)

        line = self._teaching_line(monday)

        self.assertFalse(self._absence_row(line, self.teacher_a)['covered'])
        self.assertFalse(self._absence_row(line, self.teacher_b)['covered'])

    def test_a_group_split_across_two_rooms_is_not_covered(self):
        """Each teacher has half of the group in their own room: the absent teacher's half is
        left without anyone, whatever the other half's teacher is doing."""
        monday = self._monday()
        self._co_teach(room_b=self.space_b)
        self._absence(self.teacher_a, monday)

        line = self._teaching_line(monday)

        self.assertFalse(self._absence_row(line, self.teacher_a)['covered'])

    def test_report_strikes_through_a_covered_row(self):
        monday = self._monday()
        self._co_teach()
        self._absence(self.teacher_a, monday)

        html, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday=str(monday.weekday()), guard_duty_date=str(monday), guard_duty_view='table').\
            _render_qweb_html('ems.report_guard_duty_board', [self.course.id])

        self.assertIn(b'gdb-absence-row gdb-absence-covered', html)

    def test_a_single_teacher_class_is_not_covered(self):
        monday = self._monday()
        self._schedule_class(self.teacher_a, self.group_a, 'Test Calendar A (Not Covered)')
        self._absence(self.teacher_a, monday)

        self.assertFalse(self._absence_row(self._teaching_line(monday), self.teacher_a)['covered'])

    def test_a_guard_teacher_absence_produces_no_row_to_cover(self):
        """An absent guard has nothing for anyone to cover - they are missing from the guard
        column (tested above), not a class left without a teacher."""
        monday = self._monday()
        calendar = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (No Row)')
        calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard',
        }])
        self._absence(self.teacher_guard, monday)

        line = self._teaching_line(monday)

        self.assertNotIn(self.teacher_guard, [row['teacher'] for row in line['absences']])

    def test_get_guard_duty_board_data_is_json_safe_with_absences(self):
        monday = self._monday()
        self._schedule_class(self.teacher_a, self.group_a, 'Test Calendar A (JSON Absences)')
        calendar_guard = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (JSON Absences)')
        calendar_guard.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard',
        }])
        self._absence(self.teacher_a, monday)

        data = self.env['ems.course'].get_guard_duty_board_data(
            str(monday.weekday()), 'morning', day=str(monday))
        json.dumps(data)  # raises TypeError if anything isn't JSON-safe (e.g. a stray recordset)

        line = next(line for line in data['lines'] if line['time_label'] == '09:00-10:00')
        cell = next(cell for cell in line['cells'] if cell['group_id'] == self.group_a.id)
        absent = next(teacher for teacher in cell['teachers']
                      if teacher['name'] == self.teacher_a.display_name)
        self.assertEqual(absent['absence'], 'approved')
        guard = next(guard for guard in line['guards']
                     if guard['name'] == self.teacher_guard.display_name)
        self.assertFalse(guard['absence'])
        row = next(row for row in line['absences']
                   if row['teacher'] == self.teacher_a.display_name)
        self.assertEqual(row['group'], self.group_a.name)
        self.assertEqual(row['subject'], self.subject.acronym)
        self.assertEqual(row['room'], self.space.display_name)
        self.assertIs(row['covered'], False)

    def test_report_guard_duty_board_prints_the_absences_table_via_context(self):
        """Issue #442: the PDF must print whichever of the board's two tabs was actually on
        screen when "PDF" was clicked - not always the plain timetable regardless of what the
        "Absences table" tab (guard_duty_board.js's own VIEWS) was showing. 'guard_duty_view'
        (falsy/absent = the original, still-default 'schedule' behaviour) is the context key
        guard_duty_board.js's onPdfClick() forwards for this - see its own NOTE."""
        monday = self._monday()
        self._schedule_class(self.teacher_a, self.group_a, 'Test Calendar A (View Context)')
        self._absence(self.teacher_a, monday)

        schedule_content, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday=str(monday.weekday()), guard_duty_date=str(monday)).\
            _render_qweb_pdf('ems.report_guard_duty_board', [self.course.id])
        table_content, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday=str(monday.weekday()), guard_duty_date=str(monday), guard_duty_view='table').\
            _render_qweb_pdf('ems.report_guard_duty_board', [self.course.id])

        # 'gdb-duty-table' only ever appears as the printed table's own class attribute in the
        # absences-table branch (never inside the shared <style> block above, unlike plain
        # "Absences" - which the CSS comments also mention on their own, making it too fragile a
        # marker to assert against directly) - a clean, branch-conditional way to tell the two
        # renders apart.
        self.assertNotIn(b'gdb-duty-table', schedule_content)
        self.assertIn(b'gdb-duty-table', table_content)
        # Whoever needs covering is still named on the table tab, same as the live screen.
        self.assertIn(self.teacher_a.name.encode(), table_content)
