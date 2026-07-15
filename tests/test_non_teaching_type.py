from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestNonTeachingType(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.head_of_department_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Head of Department (Non-teaching Type)',
            'login': 'test_hod_for_non_teaching_type',
            'groups_id': [(4, cls.env.ref('ems.group_department_chief').id)],
        })
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Non-teaching Type)',
            'login': 'test_teacher_for_non_teaching_type',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.test_type = cls.env['ems.non_teaching_type'].create({
            'code': 'TST',
            'name': 'Test Type',
        })

    def test_create_valid(self):
        non_teaching_type = self.env['ems.non_teaching_type'].create({'code': 'T01', 'name': 'Test 01'})
        self.assertTrue(non_teaching_type.id)
        self.assertEqual(non_teaching_type.code, 'T01')
        self.assertEqual(non_teaching_type.name, 'Test 01')
        self.assertFalse(non_teaching_type.is_break)
        self.assertFalse(non_teaching_type.is_fixed)
        self.assertTrue(non_teaching_type.active)

    def test_create_missing_code(self):
        with self.assertRaises(Exception):
            self.env['ems.non_teaching_type'].create({'name': 'No Code'})

    def test_create_missing_name(self):
        with self.assertRaises(Exception):
            self.env['ems.non_teaching_type'].create({'code': 'T02'})

    def test_code_must_be_unique(self):
        self.env['ems.non_teaching_type'].create({'code': 'UNIQ', 'name': 'First'})
        with self.assertRaises(Exception):
            self.env['ems.non_teaching_type'].create({'code': 'UNIQ', 'name': 'Second'})

    def test_display_name(self):
        non_teaching_type = self.env['ems.non_teaching_type'].create({'code': 'T03', 'name': 'Guard'})
        self.assertEqual(non_teaching_type.display_name, 'Guard')

    def test_admin_can_create(self):
        non_teaching_type = self.env['ems.non_teaching_type'].with_user(self.head_of_department_user).create({
            'code': 'T04', 'name': 'Admin Test',
        })
        self.assertTrue(non_teaching_type.id)

    def test_admin_can_write(self):
        non_teaching_type = self.env['ems.non_teaching_type'].create({'code': 'T05', 'name': 'Before Write'})
        non_teaching_type.with_user(self.head_of_department_user).write({'name': 'After Write'})
        self.assertEqual(non_teaching_type.name, 'After Write')

    def test_admin_can_unlink(self):
        non_teaching_type = self.env['ems.non_teaching_type'].create({'code': 'T06', 'name': 'To Delete'})
        type_id = non_teaching_type.id
        non_teaching_type.with_user(self.head_of_department_user).unlink()
        self.assertFalse(self.env['ems.non_teaching_type'].search([('id', '=', type_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.non_teaching_type'].with_user(self.teacher_user).create({
                'code': 'T07', 'name': 'Teacher Attempt',
            })

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_type.with_user(self.teacher_user).write({'name': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_type.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        non_teaching_type = self.test_type.with_user(self.teacher_user)
        self.assertEqual(non_teaching_type.name, 'Test Type')
