import base64
import importlib.util
import os

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestEmployeePhotoVisibility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_academic_admin = cls.env.ref('ems.group_academic_admin')
        cls.group_internal_user = cls.env.ref('base.group_user')

        # 1x1 transparent PNG, so writes reach the real fields.Image validation/resize pipeline
        # (image_1920 on res.partner/res.users) instead of failing to decode.
        cls.photo = b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        cls.other_photo = b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='

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

        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Admin (Photo Visibility)',
            'login': 'test_photo_admin',
            'email': 'test_photo_admin@example.com',
            'groups_id': [(4, cls.group_academic_admin.id), (4, cls.group_internal_user.id)],
        })

        cls.employee_without_user = cls.env['hr.employee'].create({
            'name': 'No User (Photo Visibility)',
            'employee_type': 'asp',
        })

    def test_default_image_disabled_is_false(self):
        self.assertFalse(self.teacher_a_user.image_disabled)

    def test_upload_from_profile_syncs_to_employee(self):
        self.teacher_a_user.with_user(self.teacher_a_user).image_1920 = self.photo
        self.assertEqual(
            base64.b64decode(self.teacher_a.image_1920),
            base64.b64decode(self.photo),
        )

    def test_upload_from_employee_form_syncs_to_user(self):
        self.teacher_a.with_user(self.admin_user).image_1920 = self.other_photo
        self.assertEqual(
            base64.b64decode(self.teacher_a_user.partner_id.image_1920),
            base64.b64decode(self.other_photo),
        )

    def _attachment_mimetype(self, model, field, res_id):
        self.env.cr.execute(
            "SELECT mimetype FROM ir_attachment WHERE res_model = %s AND res_field = %s AND res_id = %s",
            (model, field, res_id))
        row = self.env.cr.fetchone()
        return row[0] if row else None

    def test_disabling_locks_photo_and_shows_placeholder_on_both(self):
        self.teacher_a.image_1920 = self.photo
        # Force image_1024/image_128 (store=True, related to image_1920) to actually
        # materialize as their own ir_attachment now - like the "Teachers" kanban or
        # employee form would when rendering this employee for the first time - so the
        # regression check below reflects the real scenario: an attachment that already
        # existed getting overwritten in place, not one being created fresh.
        self.teacher_a.image_1024, self.teacher_a.image_128  # noqa: B018
        self.teacher_a_user.partner_id.image_1024, self.teacher_a_user.partner_id.image_128  # noqa: B018

        self.teacher_a_user.with_user(self.teacher_a_user).image_disabled = True

        employee_content = base64.b64decode(self.teacher_a.image_1920)
        partner_content = base64.b64decode(self.teacher_a_user.partner_id.image_1920)
        self.assertTrue(employee_content.lstrip().startswith(b'<?xml'))
        self.assertTrue(partner_content.lstrip().startswith(b'<?xml'))
        self.assertEqual(employee_content, partner_content)

        # Force image_1024/image_128 to materialize again (e.g. the kanban rendering this
        # employee after the change) before inspecting the attachments directly - like
        # above, store=True related fields are computed lazily, only on actual ORM read.
        self.teacher_a.image_1024, self.teacher_a.image_128  # noqa: B018
        self.teacher_a_user.partner_id.image_1024, self.teacher_a_user.partner_id.image_128  # noqa: B018

        # Regression test: overwriting an existing ir_attachment's content in place does
        # NOT re-detect its mimetype (only Model.create() does) - a stale mimetype from
        # the previous real photo left on image_1024/image_128 makes the browser refuse
        # to render the new SVG placeholder, showing literal "Binary file" text instead.
        # write_photo() (employee.py) must clear the field first so a fresh attachment,
        # with a freshly detected mimetype, gets created on every write.
        for field in ('image_1920', 'image_1024', 'image_128'):
            self.assertEqual(
                self._attachment_mimetype('hr.employee', field, self.teacher_a.id),
                'image/svg+xml', f"stale mimetype on hr.employee.{field}")
            self.assertEqual(
                self._attachment_mimetype(
                    'res.partner', field, self.teacher_a_user.partner_id.id),
                'image/svg+xml', f"stale mimetype on res.partner.{field}")

        with self.assertRaises(UserError):
            self.teacher_a.with_user(self.admin_user).image_1920 = self.other_photo

        with self.assertRaises(UserError):
            self.teacher_a_user.with_user(self.admin_user).image_1920 = self.other_photo

    def test_disabling_then_enabling_does_not_restore_photo(self):
        self.teacher_a.image_1920 = self.photo
        self.teacher_a_user.image_disabled = True
        placeholder = base64.b64decode(self.teacher_a.image_1920)

        self.teacher_a_user.image_disabled = False

        self.assertEqual(base64.b64decode(self.teacher_a.image_1920), placeholder)
        self.assertEqual(base64.b64decode(self.teacher_a_user.partner_id.image_1920), placeholder)

    def test_upload_after_reenable_syncs_normally(self):
        self.teacher_a.image_1920 = self.photo
        self.teacher_a_user.image_disabled = True
        self.teacher_a_user.image_disabled = False

        self.teacher_a.with_user(self.admin_user).image_1920 = self.other_photo

        self.assertEqual(
            base64.b64decode(self.teacher_a_user.partner_id.image_1920),
            base64.b64decode(self.other_photo),
        )
        # Regression test: the field held the SVG placeholder just before this upload -
        # the new real photo's attachment must not keep that stale mimetype (see
        # test_disabling_locks_photo_and_shows_placeholder_on_both for the failure mode).
        self.assertEqual(
            self._attachment_mimetype('hr.employee', 'image_1920', self.teacher_a.id), 'image/png')
        self.assertEqual(
            self._attachment_mimetype(
                'res.partner', 'image_1920', self.teacher_a_user.partner_id.id), 'image/png')

    def test_reenable_and_upload_in_one_write(self):
        # A user re-enabling their photo and picking a new file in the same "My Profile"
        # save sends both 'image_disabled': False and 'image_1920': <photo> in a single
        # write() call - this must succeed in one step, not require unticking, saving,
        # then uploading and saving again.
        self.teacher_a.image_1920 = self.photo
        self.teacher_a_user.image_disabled = True

        self.teacher_a_user.with_user(self.teacher_a_user).write({
            'image_disabled': False,
            'image_1920': self.other_photo,
        })

        self.assertFalse(self.teacher_a_user.image_disabled)
        self.assertEqual(
            base64.b64decode(self.teacher_a_user.partner_id.image_1920),
            base64.b64decode(self.other_photo),
        )
        self.assertEqual(
            base64.b64decode(self.teacher_a.image_1920),
            base64.b64decode(self.other_photo),
        )

    def test_disabling_and_uploading_in_one_write_still_blocked(self):
        # The opposite combination - disabling and uploading in the same write - stays
        # blocked: disabling is meant to be an explicit, standalone action, and the
        # uploaded photo would just be immediately overwritten by the placeholder anyway.
        self.teacher_a.image_1920 = self.photo

        with self.assertRaises(UserError):
            self.teacher_a_user.with_user(self.teacher_a_user).write({
                'image_disabled': True,
                'image_1920': self.other_photo,
            })

    def test_employee_without_user_unaffected(self):
        self.employee_without_user.image_1920 = self.photo
        self.assertEqual(
            base64.b64decode(self.employee_without_user.image_1920),
            base64.b64decode(self.photo),
        )

    def test_no_infinite_recursion_on_sync(self):
        self.teacher_a.with_user(self.admin_user).image_1920 = self.photo
        self.assertEqual(
            base64.b64decode(self.teacher_a_user.partner_id.image_1920),
            base64.b64decode(self.photo),
        )

        self.teacher_a_user.with_user(self.teacher_a_user).image_1920 = self.other_photo
        self.assertEqual(
            base64.b64decode(self.teacher_a.image_1920),
            base64.b64decode(self.other_photo),
        )

    @classmethod
    def _load_post_migrate_module(cls):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'migrations', '18.0.0.21.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('ems_post_migrate_18_0_0_21_0', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_migration_sync_employee_photo_to_user(self):
        self.teacher_a.image_1920 = self.photo
        # Simulate the pre-migration state: user's photo not yet synced from the employee's.
        self.teacher_a_user.with_context(ems_syncing_photo=True).partner_id.image_1920 = self.other_photo
        self.assertNotEqual(
            base64.b64decode(self.teacher_a_user.partner_id.image_1920),
            base64.b64decode(self.photo),
        )

        migration = self._load_post_migrate_module()
        migration._sync_employee_photo_to_user(self.env.cr)
        self.teacher_a_user.invalidate_recordset()

        self.assertEqual(
            base64.b64decode(self.teacher_a_user.partner_id.image_1920),
            base64.b64decode(self.photo),
        )

    def test_migration_sync_employee_photo_to_user_avoids_stale_mimetype(self):
        # Regression test: a centre migrating to this version may have a teacher whose
        # user-side photo was uploaded independently (e.g. directly via Settings > Users,
        # before this feature existed) in a different format than their employee-side one.
        # The migration must not just overwrite the CONTENT in place - Odoo never
        # re-detects an existing ir_attachment's mimetype on an in-place update - or the
        # browser ends up being served the new bytes under the OLD, mismatched
        # Content-Type ("Binary file" instead of the picture).
        self.teacher_a.image_1920 = self.photo
        self.teacher_a_user.with_context(ems_syncing_photo=True).partner_id.image_1920 = self.other_photo
        self.env.cr.execute(
            "UPDATE ir_attachment SET mimetype = 'image/webp' "
            "WHERE res_model = 'res.partner' AND res_field = 'image_1920' AND res_id = %s",
            (self.teacher_a_user.partner_id.id,))

        migration = self._load_post_migrate_module()
        migration._sync_employee_photo_to_user(self.env.cr)

        self.assertEqual(
            self._attachment_mimetype(
                'res.partner', 'image_1920', self.teacher_a_user.partner_id.id),
            'image/png')

    def test_migration_does_not_touch_employee_without_user(self):
        self.employee_without_user.image_1920 = self.photo
        migration = self._load_post_migrate_module()
        # Must not raise for employees with no user_id.
        migration._sync_employee_photo_to_user(self.env.cr)

    # --- stale avatar placeholder on rename ------------------------------
    def _svg_initial(self, image_1920):
        # Odoo's _avatar_generate_svg() always places the initial right after the
        # opening <text ...> tag - e.g. "...sans-serif'>T</text>".
        svg = base64.b64decode(image_1920).decode()
        self.assertTrue(svg.lstrip().startswith('<?xml'), svg)
        return svg.split("font-family='sans-serif'>", 1)[1][0]

    def test_pending_teacher_placeholder_updates_after_rename(self):
        # Regression test for #378: native hr.employee.create() bakes a real SVG
        # into image_1920 for any new employee with no photo (models/hr/models/
        # hr_employee.py's create()) - a pending-identification teacher is always
        # created this way (placeholder name, no user_id yet) and always renamed
        # later, so this hits every single pending teacher, not an edge case.
        employee = self.env['hr.employee'].create({
            'name': 'Pending teacher (X_TEST)',
            'employee_type': 'teacher',
            'schedule_import_code': 'X_TEST',
        })
        self.assertEqual(self._svg_initial(employee.image_1920), 'P')

        employee.write({'name': 'Zoe'})

        self.assertEqual(self._svg_initial(employee.image_1920), 'Z')

    def test_disabled_photo_employee_placeholder_updates_after_rename(self):
        self.teacher_a_user.image_disabled = True
        self.assertEqual(self._svg_initial(self.teacher_a.image_1920), 'T')

        self.teacher_a.write({'name': 'Zoe Renamed'})

        self.assertEqual(self._svg_initial(self.teacher_a.image_1920), 'Z')
        self.assertEqual(self._svg_initial(self.teacher_a_user.partner_id.image_1920), 'Z')

    def test_real_photo_not_touched_by_rename(self):
        self.teacher_a.image_1920 = self.photo
        self.teacher_a.write({'name': 'Zoe Renamed'})
        self.assertEqual(base64.b64decode(self.teacher_a.image_1920), base64.b64decode(self.photo))

    def test_rename_without_linked_user_still_refreshes(self):
        # employee_without_user has no user_id at all (like a pending-identification
        # teacher) - the fix must not assume a linked user is available.
        self.assertEqual(self._svg_initial(self.employee_without_user.image_1920), 'N')

        self.employee_without_user.write({'name': 'Zoe Renamed'})

        self.assertEqual(self._svg_initial(self.employee_without_user.image_1920), 'Z')
