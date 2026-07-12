from datetime import date

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestWorkingSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher User (Working Schedule)',
            'login': 'test_teacher_for_working_schedule',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.head_of_department_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Head of Department User (Working Schedule)',
            'login': 'test_hod_for_working_schedule',
            'groups_id': [(4, cls.env.ref('ems.group_head_of_department').id)],
        })
        cls.level = cls.env['ems.level'].create({'acronym': 'TWSL', 'name': 'Test Level (Working Schedule)'})
        cls.study = cls.env['ems.study'].create({
            'code': 'TWSL001',
            'acronym': 'TWSL',
            'name': 'Test Study (Working Schedule)',
            'date': date.today(),
            'deprecated': False,
            'level_id': cls.level.id,
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TWSL001',
            'acronym': 'TWSL',
            'name': 'Test Subject (Working Schedule)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TWSL-A',
            'name': 'Test Space (Working Schedule)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1,
            'acronym': 'TWSL',
            'level_id': cls.level.id,
            'study_id': cls.study.id,
            'space_id': cls.space.id,
        })
        cls.framework = cls.env['resource.calendar'].create({
            'name': 'Test Framework (Working Schedule)',
            'is_framework': True,
            'full_time_required_hours': 24,
        })
        cls.env['resource.calendar.attendance'].create({
            'calendar_id': cls.framework.id,
            'name': 'Free',
            'dayofweek': '0',
            'hour_from': 8,
            'hour_to': 9,
            'day_period': 'morning',
        })
        cls.env['resource.calendar.attendance'].create({
            'calendar_id': cls.framework.id,
            'name': 'BR: Break',
            'dayofweek': '0',
            'hour_from': 9,
            'hour_to': 9.5,
            'day_period': 'morning',
            'non_teaching': 'BR',
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Working Schedule)',
            'employee_type': 'teacher',
        })

    def test_non_teaching_selection_includes_break(self):
        selection = dict(self.env['resource.calendar.attendance']._fields['non_teaching'].selection)
        self.assertIn('BR', selection)

    def test_seed_from_framework_sets_source_and_writes_nothing(self):
        # NOTE: 'attendance_ids' is a stored compute field that auto-fills from the company's own
        # calendar when a create() call doesn't include it — passing (5, 0, 0) here keeps this fixture
        # a clean slate instead of inheriting the company's real rows (resource_calendar.py's
        # '_compute_attendance_ids'). 'seed_from_framework'/'apply_schedule_changes' are unaffected in
        # production since they always unlink weekday rows before doing anything else.
        calendar = self.env['resource.calendar'].create({
            'name': 'Test Seed Target (Working Schedule)',
            'attendance_ids': [(5, 0, 0), (0, 0, {
                'dayofweek': '1', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning', 'name': 'Old',
            })],
        })

        calendar.seed_from_framework(self.framework)

        self.assertEqual(calendar.source_framework_id, self.framework)
        # Unassigned/blank periods are never stored — seeding only points at the framework and clears
        # whatever weekday rows existed before, it does not copy the framework's own rows.
        self.assertFalse(calendar.attendance_ids.filtered(lambda a: a.dayofweek in ('0', '1', '2', '3', '4')))

    def test_apply_schedule_changes_writes_only_real_cells(self):
        calendar = self.env['resource.calendar'].create({'name': 'Test Apply (Working Schedule)'})
        cells = [{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'Test: Group',
        }]

        calendar.apply_schedule_changes(cells, source_framework_id=self.framework.id)

        self.assertEqual(len(calendar.attendance_ids), 1)
        self.assertEqual(calendar.source_framework_id, self.framework)

    def test_apply_schedule_changes_unlinks_previous_weekday_rows(self):
        calendar = self.env['resource.calendar'].create({
            'name': 'Test Apply Replace (Working Schedule)',
            'attendance_ids': [(5, 0, 0), (0, 0, {
                'dayofweek': '0', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning', 'name': 'Old',
            })],
        })

        calendar.apply_schedule_changes([{
            'dayofweek': '2', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning', 'non_teaching': 'BR', 'name': 'BR: Break',
        }])

        self.assertEqual(len(calendar.attendance_ids), 1)
        self.assertEqual(calendar.attendance_ids.dayofweek, '2')

    def test_apply_schedule_changes_syncs_teaching_and_attendance_template(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Apply Sync (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        cells = [{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'Test: Group',
        }]

        schedule.apply_schedule_changes(cells)

        teaching = self.env['ems.teaching'].search([
            ('teacher_id', '=', self.teacher.id),
            ('subject_id', '=', self.subject.id),
            ('group_id', '=', self.group.id),
        ])
        self.assertTrue(teaching)

        template = self.env['ems.attendance_template'].search([
            ('teacher_id', '=', self.teacher.id),
            ('subject_id', '=', self.subject.id),
        ])
        self.assertTrue(template)
        self.assertIn(self.group, template.group_ids)

    def test_get_schedule_report_lines_only_covers_real_entries(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Report Lines (Working Schedule)'})
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
        }])

        lines = schedule.get_schedule_report_lines()

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['time_label'], '09:00-10:00')
        monday, tuesday = lines[0]['cells'][0], lines[0]['cells'][1]
        self.assertEqual(monday['entry'].subject_id, self.subject)
        self.assertTrue(monday['color'])
        self.assertFalse(tuesday['entry'])
        self.assertFalse(tuesday['color'])

    def test_get_schedule_report_lines_same_item_gets_same_color_across_days(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Report Colors (Working Schedule)'})
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '2', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '1', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'non_teaching': 'BR', 'name': 'BR: Break',
            },
        ])

        lines = schedule.get_schedule_report_lines()

        monday, tuesday, wednesday = lines[0]['cells'][0], lines[0]['cells'][1], lines[0]['cells'][2]
        self.assertEqual(monday['color'], wednesday['color'])
        self.assertNotEqual(monday['color'], tuesday['color'])

    def test_get_schedule_hours_summary_groups_teaching_hours_by_level(self):
        other_level = self.env['ems.level'].create({'acronym': 'TWSL2', 'name': 'Test Level 2 (Working Schedule)'})
        other_study = self.env['ems.study'].create({
            'code': 'TWSL002', 'acronym': 'TWSL2', 'name': 'Test Study 2 (Working Schedule)',
            'date': date.today(), 'deprecated': False, 'level_id': other_level.id,
        })
        other_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TWSL2', 'level_id': other_level.id, 'study_id': other_study.id, 'space_id': self.space.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test Hours Summary (Working Schedule)'})
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '1', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '2', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [other_group.id], 'name': 'TWSL: TWSL2',
            },
        ])

        summary = schedule.get_schedule_hours_summary()

        teaching = {row['label']: row['hours'] for row in summary['teaching']['rows']}
        self.assertEqual(teaching[self.level.display_name], 2)
        self.assertEqual(teaching[other_level.display_name], 1)
        self.assertEqual(summary['teaching']['total'], 3)

    def test_get_schedule_hours_summary_excludes_break(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Hours Summary Break (Working Schedule)'})
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 9.5, 'day_period': 'morning',
            'non_teaching': 'BR', 'name': 'BR: Break',
        }])

        summary = schedule.get_schedule_hours_summary()

        self.assertFalse(summary['teaching']['rows'])
        self.assertFalse(summary['fixed']['rows'])
        self.assertEqual(summary['total'], 0)

    def test_get_schedule_hours_summary_guard_and_wednesday_coordination_go_to_fixed_column(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Hours Summary Fixed (Working Schedule)'})
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
                'non_teaching': 'G', 'name': 'G: Guard',
            },
            {
                'dayofweek': '2', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
                'non_teaching': 'CM', 'name': 'CM: Coordination Meeting',
            },
            {
                'dayofweek': '1', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
                'non_teaching': 'CM', 'name': 'CM: Coordination Meeting',
            },
            {
                'dayofweek': '3', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
                'non_teaching': 'SC', 'name': 'SC: School Council',
            },
        ])

        summary = schedule.get_schedule_hours_summary()

        fixed = {row['label']: row['hours'] for row in summary['fixed']['rows']}
        teaching = {row['label']: row['hours'] for row in summary['teaching']['rows']}
        self.assertEqual(fixed['Guard'], 1)
        self.assertEqual(fixed['Coordination Meeting'], 1)  # only the Wednesday one
        self.assertEqual(teaching['Coordination Meeting'], 1)  # Tuesday one, not fixed
        self.assertEqual(teaching['School Council'], 1)
        self.assertEqual(summary['fixed']['total'], 2)
        self.assertEqual(summary['teaching']['total'], 2)
        self.assertEqual(summary['total'], 4)

    def test_get_schedule_hours_summary_rounds_partial_hours_up(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Hours Summary Rounding (Working Schedule)'})
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 9.5, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
        }])

        summary = schedule.get_schedule_hours_summary()

        self.assertEqual(summary['teaching']['rows'][0]['hours'], 1)

    def test_report_working_schedule_renders(self):
        self.teacher.resource_calendar_id = self.framework
        self.teacher.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
        }])

        content, content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_working_schedule', [self.teacher.id])

        self.assertTrue(content)
        self.assertIn(content_type, ('pdf', 'html'))
        self.assertIn(b'TWSL', content)

    def test_report_working_schedule_includes_hours_summary(self):
        self.teacher.resource_calendar_id = self.framework
        self.teacher.resource_calendar_id.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '0', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
                'non_teaching': 'G', 'name': 'G: Guard',
            },
        ])

        content, _content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_working_schedule', [self.teacher.id])

        self.assertIn(b'Weekly teaching hours', content)
        self.assertIn(b'Other fixed-schedule hours', content)
        self.assertIn(b'Overall total', content)

    def test_get_report_role_lines_tutor_shows_tutored_group(self):
        role_tutor = self.env.ref('ems.role_tutor')
        self.teacher.write({'role_ids': [(4, role_tutor.id)], 'tutorship_ids': [(4, self.group.id)]})

        lines = self.teacher.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(self.group.name, lines[0])

    def test_get_report_role_lines_dchieff_shows_department(self):
        role_dchieff = self.env.ref('ems.role_dchieff')
        department = self.env['hr.department'].create({'name': 'Test Department (Working Schedule)'})
        self.teacher.write({'role_ids': [(4, role_dchieff.id)], 'department_id': department.id})

        lines = self.teacher.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(department.name, lines[0])

    def test_get_report_role_lines_plain_role_has_no_suffix(self):
        role_secretary = self.env.ref('ems.role_secretary')
        self.teacher.write({'role_ids': [(4, role_secretary.id)]})

        lines = self.teacher.get_report_role_lines()

        self.assertEqual(lines, [role_secretary.name])

    def test_get_report_role_lines_no_roles_returns_empty(self):
        self.assertEqual(self.teacher.get_report_role_lines(), [])

    def test_report_working_schedule_header_shows_department_and_roles(self):
        role_tutor = self.env.ref('ems.role_tutor')
        department = self.env['hr.department'].create({'name': 'Test Department Header (Working Schedule)'})
        self.teacher.write({
            'role_ids': [(4, role_tutor.id)], 'tutorship_ids': [(4, self.group.id)], 'department_id': department.id,
        })
        self.teacher.resource_calendar_id = self.framework
        # NOTE: create() without inline attendance_ids auto-fills from the company's own calendar
        # (see working_schedule.py's module docstring) — apply_schedule_changes() always unlinks
        # weekday rows first, which is what clears that contamination before we render.
        self.teacher.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
        }])

        content, _content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_working_schedule', [self.teacher.id])

        self.assertIn(department.name.encode(), content)
        self.assertIn(self.group.name.encode(), content)
        self.assertNotIn(b'ws-employee-title">Working Schedule', content)

    def test_get_report_label_translates_non_teaching_reason(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Report Label (Working Schedule)'})
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': 'G', 'name': 'G: Guard',
        }])
        attendance = schedule.attendance_ids

        self.assertEqual(attendance.with_context(lang='en_US').get_report_label(), 'Guard')
        self.assertEqual(attendance.with_context(lang='ca_ES').get_report_label(), 'Guàrdia')

    def test_report_working_schedule_translates_non_teaching_reason(self):
        self.teacher.resource_calendar_id = self.framework
        self.teacher.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': 'G', 'name': 'G: Guard',
        }])

        content, _content_type = self.env['ir.actions.report'].with_context(lang='ca_ES')._render_qweb_pdf(
            'ems.report_working_schedule', [self.teacher.id]
        )

        self.assertIn('Guàrdia'.encode(), content)

    def test_teacher_cannot_write_schedule_attendance(self):
        calendar = self.env['resource.calendar'].create({'name': 'Test ACL Teacher (Working Schedule)'})
        with self.assertRaises(AccessError):
            self.env['resource.calendar.attendance'].with_user(self.teacher_user).create({
                'calendar_id': calendar.id, 'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            })

    def test_head_of_department_can_write_schedule_attendance(self):
        calendar = self.env['resource.calendar'].create({'name': 'Test ACL HoD (Working Schedule)'})
        attendance = self.env['resource.calendar.attendance'].with_user(self.head_of_department_user).create({
            'calendar_id': calendar.id, 'name': 'Test', 'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
        })
        self.assertTrue(attendance.id)

    def test_can_edit_schedule_reflects_role(self):
        # NOTE: 'can_edit_schedule' is a non-stored compute — the transaction-level cache keys by
        # (field, record), not by the acting user, so switching user on the same record within one
        # test needs an explicit invalidation or the second read returns the first user's cached value.
        teacher_view = self.teacher.with_user(self.teacher_user)
        self.assertFalse(teacher_view.can_edit_schedule)

        self.teacher.invalidate_recordset(['can_edit_schedule'])
        hod_view = self.teacher.with_user(self.head_of_department_user)
        self.assertTrue(hod_view.can_edit_schedule)
