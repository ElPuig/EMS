from odoo.tests.common import TransactionCase


class TestSpace(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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

    def test_new_space_defaults_to_main_building_classroom(self):
        space = self.env['ems.space'].new({})
        self.assertEqual(space.work_location_id, self.env.ref('ems.work_location_main'))
        self.assertEqual(space.space_type_id, self.env.ref('ems.space_type_classroom'))

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
