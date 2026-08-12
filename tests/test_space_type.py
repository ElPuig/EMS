from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSpaceType(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Space Type)',
            'login': 'test_teacher_for_space_type',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Space Type)',
            'login': 'test_secretary_for_space_type',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.test_space_type = cls.env['ems.space_type'].create({'name': 'Test Space Type'})

    def test_create_valid(self):
        space_type = self.env['ems.space_type'].create({'name': 'Test 01'})
        self.assertTrue(space_type.id)
        self.assertEqual(space_type.name, 'Test 01')

    def test_create_missing_name(self):
        with self.assertRaises(Exception):
            self.env['ems.space_type'].create({})

    def test_admin_can_write(self):
        space_type = self.env['ems.space_type'].create({'name': 'Before'})
        space_type.write({'name': 'After'})
        self.assertEqual(space_type.name, 'After')

    def test_admin_can_unlink(self):
        space_type = self.env['ems.space_type'].create({'name': 'To Delete'})
        space_type_id = space_type.id
        space_type.unlink()
        self.assertFalse(self.env['ems.space_type'].search([('id', '=', space_type_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.space_type'].with_user(self.teacher_user).create({'name': 'Teacher Attempt'})

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_space_type.with_user(self.teacher_user).write({'name': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_space_type.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        space_type = self.test_space_type.with_user(self.teacher_user)
        self.assertEqual(space_type.name, 'Test Space Type')

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.space_type'].with_user(self.secretary_user).create({'name': 'Secretary Attempt'})

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_space_type.with_user(self.secretary_user).write({'name': 'Secretary Write'})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_space_type.with_user(self.secretary_user).unlink()
