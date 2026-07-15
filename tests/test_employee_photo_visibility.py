import importlib.util
import os

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

    def test_profile_form_view_combines_in_every_inheriting_tree(self):
        # Regression test: base.view_users_form_simple_modif is also the base of a SEPARATE
        # mode="primary" view (hr.res_users_view_form_simple_modif, embedded in the employee
        # form) which removes the native image_1920 field from its own combined tree. An
        # ems view extending base.view_users_form_simple_modif gets applied to BOTH trees, so
        # an xpath anchored on image_1920 breaks get_view() for res.users entirely as soon as
        # it's requested through the employee-embedded tree, not just "My Profile" - exercise
        # both to catch that class of bug.
        self.env['res.users'].get_view(view_type='form')
        self.env['res.users'].get_view(
            view_id=self.env.ref('hr.res_users_view_form_simple_modif').id, view_type='form')

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

    def _load_post_migrate_module(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'migrations', '18.0.0.21.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('ems_post_migrate_18_0_0_21_0', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_migration_backfills_image_private_before_recomputing(self):
        # Regression test for a real incident: an earlier version of
        # migrations/18.0.0.21.0/post-migrate.py's _recompute_employee_image_1920 recomputed
        # image_1920 without first backfilling image_private from each employee's legacy
        # image_1920 value. For an employee with their own photo but no linked user (so no
        # fallback either), that silently WIPED the photo (Binary field writes of a falsy value
        # delete the underlying ir_attachment) - and it was unrecoverable, since Odoo's own
        # filestore GC had already purged the orphaned file by the time it was noticed. This
        # must never regress.
        employee = self.env['hr.employee'].create({
            'name': 'Legacy Photo Employee (Photo Visibility)',
            'employee_type': 'asp',
        })
        employee.image_private = self.photo
        employee.invalidate_recordset()
        self.assertFalse(employee.user_id)
        self.assertEqual(employee.image_1920, self.photo)

        # Simulate the real pre-migration DB state: image_private didn't exist as a concept
        # yet, only the legacy image_1920 attachment did. Done via raw SQL, not the ORM -
        # writing image_private=False through the ORM would also recompute image_1920 via the
        # model's own (already correct) dependency graph, masking exactly the gap this
        # migration step exists to cover.
        self.env.cr.execute(
            "DELETE FROM ir_attachment WHERE res_model = 'hr.employee' "
            "AND res_field = 'image_private' AND res_id = %s", (employee.id,))
        employee.invalidate_recordset()
        self.assertFalse(employee.image_private)
        self.assertEqual(employee.image_1920, self.photo)

        migration = self._load_post_migrate_module()
        migration._recompute_employee_image_1920(self.env.cr)
        employee.invalidate_recordset()

        self.assertEqual(employee.image_private, self.photo)
        self.assertEqual(employee.image_1920, self.photo)

    def test_effective_photo_falls_back_to_linked_user_photo(self):
        # Regression test: an employee can have a photo only on their linked res.users/
        # res.partner record (e.g. set directly via Settings > Users, or from before this
        # feature existed) and never have uploaded one to hr.employee.image_private - core
        # Odoo's own avatar_* fields already fall back to the user's photo in that case
        # (hr.employee._compute_avatar), and this feature must not regress that.
        # image_private isn't empty out of the box here: hr.employee's own creation flow
        # (_sync_user) generates an SVG initials placeholder and assigns it via image_1920,
        # which our _inverse_image_1920 dutifully copies into image_private - clear it first
        # to reproduce the real case this guards (an employee who predates this feature and
        # never had their own hr.employee photo at all, e.g. imported via CSV).
        self.teacher_b.sudo().image_private = False
        self.teacher_b_user.partner_id.sudo().image_1920 = self.photo

        self.teacher_b.invalidate_recordset()
        self.assertEqual(self.teacher_b.effective_photo, self.photo)
        self.assertEqual(self.teacher_b.image_1920, self.photo)

        self.teacher_b_user.with_user(self.teacher_b_user).write({'image_visibility': 'teachers'})
        self.teacher_b.invalidate_recordset()
        self.assertFalse(self.teacher_b.image_1920)
        self.assertEqual(self.teacher_b.effective_photo, self.photo)
        self.assertTrue(self.teacher_b.with_user(self.teacher_a_user).photo_visible_to_current_user)

    def test_linked_user_receives_unfiltered_photo(self):
        self.teacher_a_user.with_user(self.teacher_a_user).write({
            'image_visibility': 'teachers',
            'image_private': self.photo,
        })
        self.teacher_a.invalidate_recordset()
        self.teacher_a_user.invalidate_recordset()
        self.assertFalse(self.teacher_a.image_1920)
        self.assertEqual(self.teacher_a_user.image_1920, self.photo)
