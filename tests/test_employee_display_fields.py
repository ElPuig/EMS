from odoo.tests.common import TransactionCase

from .common import create_level_study


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
        cls.test_level, cls.test_study = create_level_study(cls, 'TSTD', level={'name': 'Test Level (Display Fields)'}, study={
            'code': 'TSTD01', 'name': 'Test Study (Display Fields)',
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
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TD1',
            'level_id': self.test_level.id, 'study_id': self.test_study.id,
            'tutor_id': self.employee.id,
        })
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
            'tutor_id': self.employee.id,
        })
        self.assertEqual(self.employee.tutorships, group.name)
        group.write({'tutor_id': False})
