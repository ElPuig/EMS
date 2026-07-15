from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestEmployeePhotoVisibility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_head_of_studies = cls.env.ref('ems.group_head_of_studies')
        cls.group_academic_admin = cls.env.ref('ems.group_academic_admin')
        cls.group_internal_user = cls.env.ref('base.group_user')

        # 1x1 transparent PNG, so writes reach the real fields.Image validation/resize pipeline
        # (image_1920 on res.partner/res.users) instead of failing to decode.
        cls.photo = b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='

        cls.teacher_a_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Teacher A (Photo Visibility)',
            'login': 'test_photo_teacher_a',
            'email': 'test_photo_teacher_a@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.group_internal_user.id)],
        })
        cls.teacher_a = cls.env['hr.employee'].create({
            'name': 'Teacher A (Photo Visibility)',
            'employee_type': 'teacher',
            'user_id': cls.teacher_a_user.id,
        })

        cls.teacher_b_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Teacher B (Photo Visibility)',
            'login': 'test_photo_teacher_b',
            'email': 'test_photo_teacher_b@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.group_internal_user.id)],
        })
        cls.teacher_b = cls.env['hr.employee'].create({
            'name': 'Teacher B (Photo Visibility)',
            'employee_type': 'teacher',
            'user_id': cls.teacher_b_user.id,
        })

        cls.hos_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Head of Studies (Photo Visibility)',
            'login': 'test_photo_hos',
            'email': 'test_photo_hos@example.com',
            'groups_id': [(4, cls.group_head_of_studies.id), (4, cls.group_internal_user.id)],
        })
        cls.hos = cls.env['hr.employee'].create({
            'name': 'Head of Studies (Photo Visibility)',
            'employee_type': 'teacher',
            'user_id': cls.hos_user.id,
        })

        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Admin (Photo Visibility)',
            'login': 'test_photo_admin',
            'email': 'test_photo_admin@example.com',
            'groups_id': [(4, cls.group_academic_admin.id), (4, cls.group_internal_user.id)],
        })

    def test_default_visibility_is_all(self):
        self.assertEqual(self.teacher_a.image_visibility, 'all')
        self.assertEqual(self.teacher_a_user.image_visibility, 'all')

    def test_teacher_can_set_own_visibility_via_profile(self):
        self.teacher_a_user.with_user(self.teacher_a_user).write({
            'image_visibility': 'teachers',
            'image_private': self.photo,
        })
        self.teacher_a.invalidate_recordset()
        self.assertEqual(self.teacher_a.image_visibility, 'teachers')
        self.assertEqual(self.teacher_a.image_private, self.photo)

    def test_teacher_cannot_write_own_employee_record_directly(self):
        with self.assertRaises(AccessError):
            self.teacher_a.with_user(self.teacher_a_user).write({'name': 'Hacked'})

    def test_teacher_cannot_write_other_employee_record(self):
        with self.assertRaises(AccessError):
            self.teacher_b.with_user(self.teacher_a_user).write({'name': 'Hacked'})

    def test_teacher_cannot_write_visibility_of_other_user(self):
        with self.assertRaises(Exception):
            self.teacher_b_user.with_user(self.teacher_a_user).write({'image_visibility': 'all'})

    def test_admin_can_still_write_employee_record(self):
        # ACL check only (the point of this test) - written via sudo rather than with_user(admin)
        # to avoid an unrelated, pre-existing gap where hr.employee.write() also touches
        # resource.resource, which needs hr.group_hr_user (not granted to this test's bare
        # group_academic_admin user, same as every other test in this suite).
        self.teacher_a.sudo().write({'name': 'Renamed by admin'})
        self.assertEqual(self.teacher_a.name, 'Renamed by admin')
        self.assertTrue(self.teacher_a.with_user(self.admin_user).has_access('write'))

    def test_photo_visible_teachers_tier(self):
        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'teachers'})
        self.teacher_a.invalidate_recordset()
        self.assertTrue(self.teacher_a.with_user(self.teacher_a_user).photo_visible_to_current_user)
        self.assertTrue(self.teacher_a.with_user(self.teacher_b_user).photo_visible_to_current_user)
        self.assertTrue(self.teacher_a.with_user(self.hos_user).photo_visible_to_current_user)
        self.assertTrue(self.teacher_a.with_user(self.admin_user).photo_visible_to_current_user)

    def test_photo_visible_directive_tier(self):
        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'directive'})
        self.teacher_a.invalidate_recordset()
        self.assertTrue(self.teacher_a.with_user(self.teacher_a_user).photo_visible_to_current_user)
        self.assertFalse(self.teacher_a.with_user(self.teacher_b_user).photo_visible_to_current_user)
        self.assertTrue(self.teacher_a.with_user(self.hos_user).photo_visible_to_current_user)
        self.assertTrue(self.teacher_a.with_user(self.admin_user).photo_visible_to_current_user)

    def test_photo_visible_all_tier(self):
        self.assertTrue(self.teacher_a.with_user(self.teacher_b_user).photo_visible_to_current_user)

    def test_image_1920_blanked_and_restored_by_visibility(self):
        self.teacher_a_user.with_user(self.teacher_a_user).write({
            'image_visibility': 'all',
            'image_private': self.photo,
        })
        self.teacher_a.invalidate_recordset()
        self.assertEqual(self.teacher_a.image_1920, self.photo)

        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'teachers'})
        self.teacher_a.invalidate_recordset()
        self.assertFalse(self.teacher_a.image_1920)
        self.assertEqual(self.teacher_a.image_private, self.photo)

        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'all'})
        self.teacher_a.invalidate_recordset()
        self.assertEqual(self.teacher_a.image_1920, self.photo)

    def test_linked_user_receives_unfiltered_photo(self):
        self.teacher_a_user.with_user(self.teacher_a_user).write({
            'image_visibility': 'teachers',
            'image_private': self.photo,
        })
        self.teacher_a.invalidate_recordset()
        self.teacher_a_user.invalidate_recordset()
        self.assertFalse(self.teacher_a.image_1920)
        self.assertEqual(self.teacher_a_user.image_1920, self.photo)
