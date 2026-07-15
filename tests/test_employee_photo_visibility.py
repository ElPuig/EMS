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

    def test_default_visibility_is_public(self):
        self.assertEqual(self.teacher_a.image_visibility, 'public')
        self.assertEqual(self.teacher_a_user.image_visibility, 'public')

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
        self.hos.with_user(self.hos_user).write({'image_private': self.photo})
        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'private'})
        self.teacher_a.invalidate_recordset()
        self.assertEqual(self.teacher_a.image_visibility, 'private')

    def test_teacher_cannot_set_own_photo(self):
        # The employee only ever controls image_visibility from "My Profile" now - the photo
        # itself can only be changed by directive staff and above (see
        # test_directive_staff_can_set_any_employee_photo).
        with self.assertRaises(AccessError):
            self.teacher_a_user.with_user(self.teacher_a_user).write({'image_private': self.photo})

    def test_directive_staff_can_set_any_employee_photo(self):
        # hr.employee ACL still denies write to everyone but admin - this is a narrow,
        # server-side bypass (employee.py's write()), not a broadened ACL: it only ever
        # applies when the vals dict contains image_private and NOTHING else.
        self.teacher_a.with_user(self.hos_user).write({'image_private': self.photo})
        self.teacher_a.invalidate_recordset()
        self.assertEqual(self.teacher_a.image_private, self.photo)

    def test_directive_staff_photo_bypass_does_not_extend_to_other_fields(self):
        with self.assertRaises(AccessError):
            self.teacher_a.with_user(self.hos_user).write({
                'image_private': self.photo, 'name': 'Hacked by HoS',
            })
        with self.assertRaises(AccessError):
            self.teacher_a.with_user(self.hos_user).write({'name': 'Hacked by HoS'})

    def test_plain_teacher_cannot_use_the_directive_bypass(self):
        with self.assertRaises(AccessError):
            self.teacher_b.with_user(self.teacher_a_user).write({'image_private': self.photo})

    def test_employee_photo_edit_syncs_to_linked_user(self):
        # Regression test: editing an employee's photo directly (the only way now, since
        # employees can't set their own) must still reach the linked res.users/res.partner -
        # Discuss/the top bar/the org chart/ems.notice.sent_by read from there, not from
        # hr.employee.
        self.teacher_a.with_user(self.hos_user).write({'image_private': self.photo})
        self.teacher_a.invalidate_recordset()
        partner = self.teacher_a_user.partner_id
        partner.invalidate_recordset()
        self.assertEqual(partner.image_1920, self.photo)

    def test_can_edit_photo(self):
        self.assertFalse(self.teacher_a.with_user(self.teacher_a_user).can_edit_photo)  # not even self
        self.assertFalse(self.teacher_a.with_user(self.teacher_b_user).can_edit_photo)
        self.assertTrue(self.teacher_a.with_user(self.hos_user).can_edit_photo)
        self.assertTrue(self.teacher_a.with_user(self.admin_user).can_edit_photo)

    def test_teacher_cannot_write_own_employee_record_directly(self):
        with self.assertRaises(AccessError):
            self.teacher_a.with_user(self.teacher_a_user).write({'name': 'Hacked'})

    def test_teacher_cannot_write_other_employee_record(self):
        with self.assertRaises(AccessError):
            self.teacher_b.with_user(self.teacher_a_user).write({'name': 'Hacked'})

    def test_teacher_cannot_write_visibility_of_other_user(self):
        with self.assertRaises(Exception):
            self.teacher_b_user.with_user(self.teacher_a_user).write({'image_visibility': 'public'})

    def test_admin_can_still_write_employee_record(self):
        # ACL check only (the point of this test) - written via sudo rather than with_user(admin)
        # to avoid an unrelated, pre-existing gap where hr.employee.write() also touches
        # resource.resource, which needs hr.group_hr_user (not granted to this test's bare
        # group_academic_admin user, same as every other test in this suite).
        self.teacher_a.sudo().write({'name': 'Renamed by admin'})
        self.assertEqual(self.teacher_a.name, 'Renamed by admin')
        self.assertTrue(self.teacher_a.with_user(self.admin_user).has_access('write'))

    def test_photo_visible_public_tier(self):
        self.assertTrue(self.teacher_a.with_user(self.teacher_b_user).photo_visible_to_current_user)

    def test_photo_visible_private_tier(self):
        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'private'})
        self.teacher_a.invalidate_recordset()
        self.assertTrue(self.teacher_a.with_user(self.teacher_a_user).photo_visible_to_current_user)
        self.assertFalse(self.teacher_a.with_user(self.teacher_b_user).photo_visible_to_current_user)
        self.assertTrue(self.teacher_a.with_user(self.hos_user).photo_visible_to_current_user)
        self.assertTrue(self.teacher_a.with_user(self.admin_user).photo_visible_to_current_user)

    def test_image_1920_becomes_placeholder_when_private_and_restores_when_public(self):
        self.teacher_a.with_user(self.hos_user).write({'image_private': self.photo})
        self.teacher_a.invalidate_recordset()
        self.assertEqual(self.teacher_a.image_1920, self.photo)

        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'private'})
        self.teacher_a.invalidate_recordset()
        self.assertTrue(self.teacher_a.image_1920)
        self.assertNotEqual(self.teacher_a.image_1920, self.photo)  # initials placeholder, not blank
        self.assertEqual(self.teacher_a.image_private, self.photo)  # real photo kept safe

        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'public'})
        self.teacher_a.invalidate_recordset()
        self.assertEqual(self.teacher_a.image_1920, self.photo)

    def test_no_photo_erases_permanently(self):
        self.teacher_a.with_user(self.hos_user).write({'image_private': self.photo})
        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'no_photo'})
        self.teacher_a.invalidate_recordset()
        self.teacher_a_user.invalidate_recordset()

        self.assertFalse(self.teacher_a.image_private)
        self.assertFalse(self.teacher_a_user.partner_id.image_private)
        self.assertTrue(self.teacher_a.image_1920)  # placeholder, not blank
        self.assertNotEqual(self.teacher_a.image_1920, self.photo)
        # Even a directive-staff viewer sees nothing to restore - the real photo is gone.
        self.assertFalse(self.teacher_a.effective_photo)

        # Switching back to 'public' does NOT resurrect the erased photo.
        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'public'})
        self.teacher_a.invalidate_recordset()
        self.assertFalse(self.teacher_a.image_1920)

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

    def test_remap_image_visibility_values(self):
        self.env.cr.execute(
            "UPDATE res_users SET image_visibility = 'directive' WHERE id = %s",
            (self.teacher_a_user.id,))
        self.env.cr.execute(
            "UPDATE res_users SET image_visibility = 'teachers' WHERE id = %s",
            (self.teacher_b_user.id,))

        migration = self._load_post_migrate_module()
        migration._remap_image_visibility_values(self.env.cr)
        self.teacher_a_user.invalidate_recordset()
        self.teacher_b_user.invalidate_recordset()

        self.assertEqual(self.teacher_a_user.image_visibility, 'private')
        self.assertEqual(self.teacher_b_user.image_visibility, 'public')

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
        self.teacher_b_user.partner_id.sudo().image_private = self.photo

        self.teacher_b.invalidate_recordset()
        self.assertEqual(self.teacher_b.effective_photo, self.photo)
        self.assertEqual(self.teacher_b.image_1920, self.photo)

        self.teacher_b_user.with_user(self.teacher_b_user).write({'image_visibility': 'private'})
        self.teacher_b.invalidate_recordset()
        self.assertNotEqual(self.teacher_b.image_1920, self.photo)
        self.assertEqual(self.teacher_b.effective_photo, self.photo)
        self.assertTrue(self.teacher_b.with_user(self.hos_user).photo_visible_to_current_user)
        self.assertFalse(self.teacher_b.with_user(self.teacher_a_user).photo_visible_to_current_user)

    def test_linked_user_receives_gated_photo(self):
        # The whole point of this iteration of the feature: the linked res.users/res.partner
        # avatar (Discuss, the top bar, the org chart, ems.notice.sent_by...) must be gated
        # exactly like hr.employee's own - never the real photo when not 'public'. The real
        # photo's source of truth here is employee.image_private (set by directive staff), so
        # it round-trips back correctly through employee.image_1920 once visibility returns to
        # 'public' - no separate copy needs to live on the partner for that to work (see
        # test_partner_backfill_preserves_preexisting_real_photo below for the case where the
        # partner's copy does matter).
        self.teacher_a.with_user(self.hos_user).write({'image_private': self.photo})
        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'private'})
        self.teacher_a.invalidate_recordset()
        self.teacher_a_user.invalidate_recordset()

        partner = self.teacher_a_user.partner_id
        self.assertEqual(partner.image_1920, self.teacher_a.image_1920)
        self.assertNotEqual(partner.image_1920, self.photo)

        self.teacher_a_user.with_user(self.teacher_a_user).write({'image_visibility': 'public'})
        self.teacher_a.invalidate_recordset()
        partner.invalidate_recordset()
        self.assertEqual(partner.image_1920, self.photo)

    def test_partner_backfill_preserves_preexisting_real_photo(self):
        # teacher_b's partner already has an independent real photo (e.g. uploaded outside
        # "My Profile", via Settings > Users) that hr.employee.image_private knows nothing
        # about. Toggling visibility - without touching image_private in this same write -
        # must still back it up into the partner's own image_private before image_1920 gets
        # overwritten with the placeholder, guarding the exact backfill this sync relies on.
        self.teacher_b.sudo().image_private = False
        self.teacher_b_user.partner_id.sudo().image_1920 = self.photo
        self.teacher_b_user.invalidate_recordset()

        self.teacher_b_user.with_user(self.teacher_b_user).write({'image_visibility': 'private'})
        partner = self.teacher_b_user.partner_id
        partner.invalidate_recordset()

        self.assertEqual(partner.image_private, self.photo)
        self.assertNotEqual(partner.image_1920, self.photo)
