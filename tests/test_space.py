from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSpace(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Space)',
            'login': 'test_teacher_for_space',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Space)',
            'login': 'test_secretary_for_space',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.space_type = cls.env['ems.space_type'].create({'name': 'Test Space Type (Space)'})
        cls.work_location = cls.env.ref('ems.work_location_main')
        cls.other_work_location = cls.env['hr.work.location'].create({
            'name': 'Test Other Work Location (Space)',
            'address_id': cls.env.company.partner_id.id,
        })
        cls.test_space = cls.env['ems.space'].create({
            'code': 'TST-SPACE-01', 'name': 'Test Space',
            'space_type_id': cls.space_type.id, 'work_location_id': cls.work_location.id,
        })

    def test_create_valid(self):
        space = self.env['ems.space'].create({
            'code': 'TST-SPACE-02', 'name': 'Test 01',
            'space_type_id': self.space_type.id, 'work_location_id': self.work_location.id,
        })
        self.assertTrue(space.id)

    def test_create_missing_code(self):
        with self.assertRaises(Exception):
            self.env['ems.space'].create({
                'name': 'No Code', 'space_type_id': self.space_type.id,
                'work_location_id': self.work_location.id,
            })

    def test_create_missing_space_type(self):
        with self.assertRaises(Exception):
            self.env['ems.space'].create({
                'code': 'TST-SPACE-03', 'name': 'No Type', 'work_location_id': self.work_location.id,
            })

    def test_create_missing_work_location(self):
        with self.assertRaises(Exception):
            self.env['ems.space'].create({
                'code': 'TST-SPACE-04', 'name': 'No Location', 'space_type_id': self.space_type.id,
            })

    def test_code_must_be_unique_per_work_location(self):
        with self.assertRaises(Exception):
            self.env['ems.space'].create({
                'code': 'TST-SPACE-01', 'name': 'Duplicate Code',
                'space_type_id': self.space_type.id, 'work_location_id': self.work_location.id,
            })

    def test_same_code_allowed_in_different_work_location(self):
        space = self.env['ems.space'].create({
            'code': 'TST-SPACE-01', 'name': 'Same Code Other Location',
            'space_type_id': self.space_type.id, 'work_location_id': self.other_work_location.id,
        })
        self.assertTrue(space.id)

    def test_display_name_includes_code(self):
        self.assertEqual(self.test_space.display_name, 'Test Space (TST-SPACE-01)')

    def test_display_name_without_code_falls_back_to_name(self):
        space = self.env['ems.space'].new({'name': 'No Code Space'})
        space._compute_display_name()
        self.assertEqual(space.display_name, 'No Code Space')

    def test_admin_can_write(self):
        self.test_space.write({'name': 'Renamed'})
        self.assertEqual(self.test_space.name, 'Renamed')

    def test_admin_can_unlink(self):
        space = self.env['ems.space'].create({
            'code': 'TST-SPACE-05', 'name': 'To Delete',
            'space_type_id': self.space_type.id, 'work_location_id': self.work_location.id,
        })
        space_id = space.id
        space.unlink()
        self.assertFalse(self.env['ems.space'].search([('id', '=', space_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.space'].with_user(self.teacher_user).create({
                'code': 'TST-SPACE-06', 'name': 'Teacher Attempt',
                'space_type_id': self.space_type.id, 'work_location_id': self.work_location.id,
            })

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_space.with_user(self.teacher_user).write({'name': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_space.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        space = self.test_space.with_user(self.teacher_user)
        self.assertEqual(space.name, 'Test Space')

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.space'].with_user(self.secretary_user).create({
                'code': 'TST-SPACE-07', 'name': 'Secretary Attempt',
                'space_type_id': self.space_type.id, 'work_location_id': self.work_location.id,
            })

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_space.with_user(self.secretary_user).write({'name': 'Secretary Write'})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_space.with_user(self.secretary_user).unlink()
