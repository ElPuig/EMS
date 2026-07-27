from odoo.tests.common import TransactionCase


class TestEmployeeDisplayFields(TransactionCase):
    """Covers hr.employee.base fields not already exercised by
    test_employee_role_group_sync.py (role_ids -> groups_id sync) or
    test_employee_schedule_lifecycle.py (calendar lifecycle): the read_only,
    roles and tutorships display-only computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Display Fields)',
            'login': 'test_teacher_for_display_fields',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee (Display Fields)',
            'employee_type': 'teacher',
        })
        cls.test_level = cls.env['ems.level'].create({
            'acronym': 'TSTD',
            'name': 'Test Level (Display Fields)',
        })
        cls.test_study = cls.env['ems.study'].create({
            'code': 'TSTD01',
            'acronym': 'TSTD',
            'name': 'Test Study (Display Fields)',
            'date': '2026-01-01',
            'deprecated': False,
            'level_id': cls.test_level.id,
        })

    def test_read_only_false_for_admin(self):
        self.assertFalse(self.employee.read_only)

    def test_read_only_true_for_teacher(self):
        employee = self.employee.with_user(self.teacher_user)
        self.assertTrue(employee.read_only)

    def test_roles_empty_by_default(self):
        self.assertEqual(self.employee.roles, "")

    def test_roles_single_via_tutorship(self):
        role_tutor = self.env.ref('ems.role_tutor')
        # ems.group.update_tutor_role() only fires from write() (see group.py), not
        # create() — assigning tutor_id at creation time doesn't sync the role. Known gap,
        # left for ems.group's own DTON pass; write() is the tested/working path here.
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TD1',
            'level_id': self.test_level.id, 'study_id': self.test_study.id,
        })
        group.write({'tutor_id': self.employee.id})
        self.assertIn(role_tutor, self.employee.role_ids)
        self.assertEqual(self.employee.roles, role_tutor.name)
        group.write({'tutor_id': False})

    def test_roles_joins_multiple_with_comma(self):
        role_a = self.env['ems.role'].create({'name': 'Test Role A (Display Fields)', 'employee_type': 'teacher'})
        role_b = self.env['ems.role'].create({'name': 'Test Role B (Display Fields)', 'employee_type': 'teacher'})
        self.employee.role_ids = [(4, role_a.id), (4, role_b.id)]
        self.assertEqual(self.employee.roles, f"{role_a.name}, {role_b.name}")

    def test_tutorships_empty_by_default(self):
        self.assertEqual(self.employee.tutorships, "")

    def test_tutorships_lists_tutored_groups(self):
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TD2',
            'level_id': self.test_level.id, 'study_id': self.test_study.id,
        })
        group.write({'tutor_id': self.employee.id})
        self.assertEqual(self.employee.tutorships, group.name)
        group.write({'tutor_id': False})
