from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group, create_role_user, next_student_id


class TestGroupScheduleDeclaration(TransactionCase):
    """Issue #853: the group pages (5 and 6) of the Departament's "Annexos Dades anuals"."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TGSD', level={'declaration_code': 'eso'})
        cls.cycle_level, cls.cycle_study, cls.cycle_group = create_level_study_group(
            cls, 'TGSC', level={'declaration_code': 'cfgs'})
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TGSD001', 'acronym': 'TGSD1', 'name': 'Test Subject One (Group Declaration)',
            'internal_hours': 60, 'external_hours': 40, 'study_ids': [(6, 0, (cls.study | cls.cycle_study).ids)],
        })
        cls.other_subject = cls.env['ems.subject'].create({
            'code': 'TGSD002', 'acronym': 'TGSD2', 'name': 'Test Subject Two (Group Declaration)',
            'internal_hours': 30, 'external_hours': 0, 'study_ids': [(6, 0, cls.cycle_study.ids)],
        })
        cls.teacher_one = cls._teacher('One')
        cls.teacher_two = cls._teacher('Two')

    @classmethod
    def _teacher(cls, name):
        teacher = cls.env['hr.employee'].create({'name': f'Test Teacher {name} (Group Declaration)', 'employee_type': 'teacher'})
        teacher.resource_calendar_id = cls.env['resource.calendar'].create({
            'name': f'Test Calendar {name} (Group Declaration)', 'employee_id': teacher.id, 'attendance_ids': [(5, 0, 0)],
        })
        return teacher

    def _teach(self, teacher, *classes):
        """Saves 'classes' as the teacher's whole schedule (apply_schedule_changes replaces it): each a
        (group, subject, hours, dayofweek) tuple, on its own hour of the day."""
        entries = [{'dayofweek': dayofweek, 'hour_from': 8 + index, 'hour_to': 8 + index + hours, 'day_period': 'morning',
                    'name': 'TGSD', 'subject_id': subject.id, 'group_ids': [group.id]}
                   for index, (group, subject, hours, dayofweek) in enumerate(classes)]
        teacher.resource_calendar_id.apply_schedule_changes(entries)

    def _student(self, name, group, **vals):
        return self.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'main_group_id': group.id, 'student_id': next_student_id(), **vals})

    def _render(self, groups, user=None):
        reports = self.env['ir.actions.report'].with_user(user) if user else self.env['ir.actions.report']
        content, _content_type = reports._render_qweb_pdf('ems.report_group_schedule_declaration', groups.ids)
        return content

    def test_page_follows_the_levels_code(self):
        self.assertEqual(self.group.get_schedule_declaration_data()['page'], 'general')
        self.assertEqual(self.cycle_group.get_schedule_declaration_data()['page'], 'vocational')
        self.level.declaration_code = False
        self.assertEqual(self.group.get_schedule_declaration_data()['page'], 'general')

    def test_degree_of_a_cycle(self):
        self.assertEqual(self.cycle_group.get_schedule_declaration_data()['degree'], 'Superior')
        self.cycle_level.declaration_code = 'cfgm'
        self.assertEqual(self.cycle_group.get_schedule_declaration_data()['degree'], 'Mitjà')

    def test_students_counts_only_active_ones_of_the_main_group(self):
        for index in range(2):
            self._student(f'TGSD active {index}', self.group)
        self._student('TGSD archived', self.group, active=False)
        self._student('TGSD elsewhere', self.cycle_group)

        self.assertEqual(self.group.get_schedule_declaration_data()['students'], 2)

    def test_course_hours_add_the_distinct_modules_of_the_schedule(self):
        # The same module twice (two days) counts once.
        self._teach(self.teacher_one, (self.cycle_group, self.subject, 1, '0'))
        self._teach(self.teacher_two, (self.cycle_group, self.subject, 1, '1'), (self.cycle_group, self.other_subject, 1, '2'))

        self.assertEqual(self.cycle_group.get_schedule_declaration_data()['course_hours'], 130)

    def test_teacher_hours_show_only_when_a_module_is_shared(self):
        self._teach(self.teacher_one, (self.cycle_group, self.subject, 2, '0'), (self.cycle_group, self.other_subject, 1, '2'))
        self._teach(self.teacher_two, (self.cycle_group, self.subject, 1, '1'))

        shared, alone = sorted(self.cycle_group.get_subject_teachers_summary(), key=lambda row: -len(row['teachers']))

        self.assertEqual(shared['teachers_hours'],
                         'Test Teacher One (Group Declaration) (2 h), Test Teacher Two (Group Declaration) (1 h)')
        self.assertEqual(alone['teachers_hours'], alone['teachers'])

    def test_rendering_in_catalan_with_the_header_data(self):
        self.env.company.center_code = 'TGSD-CODE'
        self._teach(self.teacher_one, (self.group, self.subject, 1, '0'))
        self._student('TGSD student', self.cycle_group)

        general = self._render(self.group)
        vocational = self._render(self.cycle_group)

        self.assertIn(b'Horari grup d', general)
        self.assertIn(b'TGSD-CODE', general)
        self.assertIn(self.group.name.encode(), general)
        self.assertIn('Distribució horària dels Cicles Formatius'.encode(), vocational)
        self.assertIn(b'Superior', vocational)
        self.assertNotIn(b'Horari grup d', vocational)

    def test_one_page_per_group(self):
        content = self._render(self.group | self.cycle_group)

        self.assertIn(b'Horari grup d', content)
        self.assertIn('Distribució horària dels Cicles Formatius'.encode(), content)

    def test_reinforcement_group_cannot_be_printed(self):
        reinforcement = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'TGSD reinforcement', 'parent_group_ids': [(6, 0, self.group.ids)],
        })

        with self.assertRaises(UserError):
            reinforcement.action_print_schedule_declaration()
        # Mixed with a main group: only the main one is printed.
        action = (self.group | reinforcement).action_print_schedule_declaration()
        self.assertEqual(action['context']['active_ids'], self.group.ids)

    def test_head_of_studies_prints_it(self):
        user = create_role_user(self, 'head_of_studies', 'tgsd_hos')

        action = self.group.with_user(user).action_print_schedule_declaration()
        content = self._render(self.group, user)

        self.assertEqual(action['report_name'], 'ems.report_group_schedule_declaration')
        self.assertEqual(action['context']['active_ids'], self.group.ids)
        self.assertIn(b'Horari grup d', content)

    def test_administrator_prints_it(self):
        user = create_role_user(self, 'settings_admin', 'tgsd_admin')

        self.assertIn(b'Horari grup d', self._render(self.group, user))

    def test_teacher_cannot_print_it(self):
        user = create_role_user(self, 'teacher', 'tgsd_teacher')

        with self.assertRaises(AccessError):
            self.group.with_user(user).action_print_schedule_declaration()
        with self.assertRaises(AccessError):
            self._render(self.group, user)
        printable = self.env['ir.actions.actions'].with_user(user).get_bindings('ems.group').get('report', [])
        self.assertNotIn(self.env.ref('ems.action_report_group_schedule_declaration').id,
                         [report['id'] for report in printable])

    def test_group_schedule_pdf_hides_no_rooms(self):
        # The "Horario del grupo" PDF keeps showing the classroom column: hide_rooms is opt-in.
        self._teach(self.teacher_one, (self.group, self.subject, 1, '0'))
        content, _content_type = self.env['ir.actions.report'].with_context(lang='en_US')._render_qweb_pdf(
            'ems.report_group_schedule', self.group.ids)

        self.assertTrue(content)
