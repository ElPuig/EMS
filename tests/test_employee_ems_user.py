# -*- coding: utf-8 -*-

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase


class TestEmployeeEmsUser(TransactionCase):
    """Backend tests for the automatic EMS user (res.users) creation that follows
    the Google Workspace corporate account creation for teachers/ASP (issue #342).

    Everything runs in dry-run so no real Google API call is performed. The SMTP
    transport is patched class-wide (this environment has real, credentialed
    outgoing mail servers configured) and the credential delivery (PDF + welcome
    email) is patched out per test.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mail_server_patcher = patch(
            'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email',
            return_value='test-message-id',
        )
        cls.mail_transport = mail_server_patcher.start()
        cls.addClassCleanup(mail_server_patcher.stop)

        cls.company = cls.env.company
        cls.company.write({
            'google_ws_enabled': True,
            'google_ws_dry_run': True,
            'google_ws_domain': 'elpuig.xeill.net',
            'google_ws_ou_teacher': '/claustro/doble-factor-autenticación',
            'google_ws_ou_asp': '/pas',
            'google_ws_ou_staff_suspended': '/claustro/bajas',
        })
        cls.google_provider = cls.env.ref('auth_oauth.provider_google')

    def _new_employee(self, **vals):
        base = {
            'name': 'Berta Cackleworth Quibble',
            'employee_type': 'teacher',
            'private_email': 'berta.cackleworth@example.com',
        }
        base.update(vals)
        return self.env['hr.employee'].create(base)

    def _create_account(self, employee):
        with patch.object(type(employee), '_gw_deliver_credentials',
                          return_value=(True, True)):
            employee.action_create_google_account()

    # --- user creation ---------------------------------------------------
    def test_creation_creates_ems_user(self):
        teacher = self._new_employee()
        self._create_account(teacher)
        self.assertTrue(teacher.user_id)
        self.assertEqual(teacher.user_id.login, teacher.work_email)
        self.assertEqual(teacher.user_id.email, teacher.work_email)
        self.assertTrue(teacher.user_id.active)

    def test_creation_copies_employee_photo(self):
        image_1x1_png = (
            b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk'
            b'+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        teacher = self._new_employee(image_1920=image_1x1_png)
        self._create_account(teacher)
        self.assertEqual(teacher.user_id.image_1920, teacher.image_1920)

    def test_teacher_user_groups(self):
        teacher = self._new_employee()
        self._create_account(teacher)
        self.assertTrue(teacher.user_id.has_group('base.group_user'))
        self.assertTrue(teacher.user_id.has_group('ems.group_teacher'))

    def test_asp_user_groups(self):
        asp = self._new_employee(
            name='Ulric Fandango Mopp', employee_type='asp',
            private_email='ulric.fandango@example.com')
        self._create_account(asp)
        self.assertTrue(asp.user_id.has_group('base.group_user'))
        self.assertFalse(asp.user_id.has_group('ems.group_teacher'))

    def test_user_partner_firstname_split(self):
        teacher = self._new_employee()
        self._create_account(teacher)
        given, family = teacher._gw_split_name()
        self.assertEqual(teacher.user_id.partner_id.firstname, given)
        self.assertEqual(teacher.user_id.partner_id.lastname, family)

    def test_work_email_preserved_after_link(self):
        # Writing user_id swaps work_contact_id to the user's partner; the stored
        # compute on work_email must not wipe the just-created corporate address.
        teacher = self._new_employee()
        self._create_account(teacher)
        corporate = teacher.user_id.login
        self.env.flush_all()
        self.assertEqual(teacher.work_email, corporate)
        self.assertTrue(corporate.endswith('@elpuig.xeill.net'))

    def test_no_invitation_email_sent(self):
        teacher = self._new_employee()
        self.mail_transport.reset_mock()
        self._create_account(teacher)
        self.assertTrue(teacher.user_id)
        self.mail_transport.assert_not_called()

    def test_idempotent_second_run(self):
        teacher = self._new_employee()
        self._create_account(teacher)
        user = teacher.user_id
        self._create_account(teacher)
        self.assertEqual(teacher.user_id, user)
        self.assertEqual(self.env['res.users'].with_context(active_test=False)
                         .search_count([('login', '=', user.login)]), 1)

    # --- adopt / manual paths ---------------------------------------------
    def test_adopt_corporate_email_creates_user(self):
        teacher = self._new_employee(work_email='berta.adopted@elpuig.xeill.net')
        with patch.object(type(teacher), '_gw_deliver_credentials') as deliver:
            teacher.action_create_google_account()
        deliver.assert_not_called()
        self.assertTrue(teacher.user_id)
        self.assertEqual(teacher.user_id.login, 'berta.adopted@elpuig.xeill.net')

    def test_non_corporate_work_email_creates_no_user(self):
        teacher = self._new_employee(work_email='berta@gmail.com')
        with patch.object(type(teacher), '_gw_deliver_credentials') as deliver:
            teacher.action_create_google_account()
        deliver.assert_not_called()
        self.assertFalse(teacher.user_id)

    # --- action_create_ems_user (header button) ----------------------------
    def test_action_create_ems_user_links_user_without_touching_google(self):
        teacher = self._new_employee(work_email='berta.button@elpuig.xeill.net')
        with patch.object(type(teacher), '_gw_deliver_credentials') as deliver, \
                patch.object(type(teacher), 'action_create_google_account') as create_account:
            teacher.action_create_ems_user()
        deliver.assert_not_called()
        create_account.assert_not_called()
        self.assertTrue(teacher.user_id)
        self.assertEqual(teacher.user_id.login, 'berta.button@elpuig.xeill.net')

    def test_action_create_ems_user_noop_without_work_email(self):
        teacher = self._new_employee()
        teacher.action_create_ems_user()
        self.assertFalse(teacher.user_id)

    def test_action_create_ems_user_idempotent(self):
        teacher = self._new_employee(work_email='berta.button2@elpuig.xeill.net')
        teacher.action_create_ems_user()
        user = teacher.user_id
        teacher.action_create_ems_user()
        self.assertEqual(teacher.user_id, user)

    def test_relink_archived_user_by_login(self):
        existing = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Berta Cackleworth Quibble',
            'login': 'berta.adopted@elpuig.xeill.net',
            'email': 'berta.adopted@elpuig.xeill.net',
            'active': False,
        })
        teacher = self._new_employee(work_email='berta.adopted@elpuig.xeill.net')
        with patch.object(type(teacher), '_gw_deliver_credentials'):
            teacher.action_create_google_account()
        self.assertEqual(teacher.user_id, existing)
        self.assertTrue(existing.active)
        self.assertTrue(existing.has_group('base.group_user'))
        self.assertTrue(existing.has_group('ems.group_teacher'))
        self.assertEqual(self.env['res.users'].with_context(active_test=False)
                         .search_count([('login', '=', existing.login)]), 1)

    # --- OAuth pre-link ----------------------------------------------------
    def test_oauth_prelink_fields(self):
        teacher = self._new_employee(work_email='berta.oauth@elpuig.xeill.net')
        teacher._ems_create_user(google_id='103000000000000000001')
        self.assertEqual(teacher.user_id.oauth_uid, '103000000000000000001')
        self.assertEqual(teacher.user_id.oauth_provider_id, self.google_provider)

    def test_oauth_uid_captured_from_insert_response(self):
        self.company.google_ws_dry_run = False
        service = MagicMock()
        service.users.return_value.insert.return_value.execute.return_value = {
            'id': '112233445566778899001',
        }
        teacher = self._new_employee()
        mixin_cls = type(self.env['google.workspace.mixin'])
        with patch.object(mixin_cls, '_gw_get_service', return_value=service):
            self._create_account(teacher)
        self.assertTrue(teacher.user_id)
        self.assertEqual(teacher.user_id.oauth_uid, '112233445566778899001')
        self.assertEqual(teacher.user_id.oauth_provider_id, self.google_provider)

    def test_dry_run_user_has_no_oauth_fields(self):
        teacher = self._new_employee()
        self._create_account(teacher)
        self.assertFalse(teacher.user_id.oauth_uid)

    def test_oauth_backfill_on_existing_linked_user(self):
        teacher = self._new_employee(work_email='berta.linked@elpuig.xeill.net')
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Berta Cackleworth Quibble',
            'login': 'berta.linked@elpuig.xeill.net',
            'email': 'berta.linked@elpuig.xeill.net',
        })
        teacher.user_id = user
        teacher._ems_create_user(google_id='103000000000000000002')
        self.assertEqual(teacher.user_id, user)
        self.assertEqual(user.oauth_uid, '103000000000000000002')
        self.assertEqual(user.oauth_provider_id, self.google_provider)

    # --- lifecycle ----------------------------------------------------------
    def test_archive_employee_archives_user(self):
        teacher = self._new_employee()
        self._create_account(teacher)
        user = teacher.user_id
        teacher.write({'active': False})
        self.assertFalse(user.active)

    def test_unarchive_employee_reactivates_user(self):
        teacher = self._new_employee()
        self._create_account(teacher)
        user = teacher.user_id
        teacher.write({'active': False})
        teacher.write({'active': True})
        self.assertTrue(user.active)

    def test_unlink_employee_archives_user(self):
        teacher = self._new_employee()
        self._create_account(teacher)
        user = teacher.user_id
        teacher.unlink()
        self.assertFalse(user.active)

    # --- security group sync -------------------------------------------------
    def test_role_group_synced_on_user_creation(self):
        role = self.env['ems.role'].create({
            'name': 'EMS User Test Role 342',
            'unipersonal': False,
            'employee_type': 'teacher',
            'group_id': self.env.ref('ems.group_quality').id,
        })
        teacher = self._new_employee(role_ids=[(4, role.id)])
        self._create_account(teacher)
        self.assertTrue(teacher.user_id.has_group('ems.group_quality'))
