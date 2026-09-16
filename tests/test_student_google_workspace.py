from datetime import date
from unittest.mock import Mock, patch

from dateutil.relativedelta import relativedelta

from odoo.addons.ems.models.shared.google_workspace_mixin import (
    GW_DEACTIVATION_DELAY_DAYS,
    GW_DELETION_DELAY_DAYS,
    HttpError,
)
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from .common import create_role_user, mock_outgoing_email, next_student_id


class TestStudentGoogleWorkspace(TransactionCase):
    """Backend tests for the student Google Workspace integration.

    Everything runs in dry-run so no real Google API call is performed, and the
    credential delivery (PDF render + email) is patched out to keep the tests
    isolated from wkhtmltopdf / mail. google_ws_state (all 3 states) and the
    google_ws_suspended migration backfill are already covered by
    tests/test_exit_management.py — not duplicated here.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            'google_ws_enabled': True,
            'google_ws_dry_run': True,
            'google_ws_domain': 'elpuig.xeill.net',
            'google_ws_ou_minor': '/alumnos',
            'google_ws_ou_adult': '/alumnos/+18',
            'google_ws_ou_suspended': '/alumnos/bajas',
        })

    def _new_student(self, **vals):
        base = {
            'name': 'Laia Puig Roca', 'firstname': 'Laia', 'lastname': 'Puig Roca',
            'contact_type': 'student', 'student_id': '1234567890',
            'email': 'laia.personal@example.com',
            'birth_date': date.today() - relativedelta(years=15),  # minor by default
        }
        base.update(vals)
        # A missing IDALU (issue #460) can no longer be created directly - only a legacy row
        # predating the rule can be in that state. Simulate it the same way
        # tests/test_contact.py's own _student_created_before_the_rule() does: create with a
        # real one, then null it out via SQL, bypassing the create()-time requirement on purpose.
        missing_student_id = base['student_id'] is False
        if missing_student_id:
            base['student_id'] = '0000000000'
        student = self.env['res.partner'].create(base)
        if missing_student_id:
            self.env.cr.execute("UPDATE res_partner SET student_id = NULL WHERE id = %s", [student.id])
            student.invalidate_recordset(['student_id'])
        return student

    # --- readiness -----------------------------------------------------

    def test_missing_fields_requires_idalu_and_email(self):
        student = self._new_student(student_id=False, email=False)
        missing = student._gw_missing_fields()
        self.assertIn('IDALU', missing)
        self.assertIn('Personal email', missing)

    def test_birth_date_not_required(self):
        # Deliberate: account creation must not wait for the birth date (GEDAC
        # import has none yet) — missing birth_date alone must not block readiness.
        student = self._new_student(birth_date=False)
        self.assertFalse(student._gw_missing_fields())
        self.assertTrue(student._gw_ready())

    def test_ready_with_required_fields(self):
        student = self._new_student()
        self.assertFalse(student._gw_missing_fields())
        self.assertTrue(student._gw_ready())

    def test_not_ready_for_non_student(self):
        applicant = self._new_student(contact_type='applicant')
        self.assertFalse(applicant._gw_ready())

    # --- email candidates -----------------------------------------------

    def test_email_candidates_strategy(self):
        student = self._new_student(
            firstname='Juan', lastname='Morote Puente',
            student_id='123456789', birth_date=date(2006, 1, 1),
        )
        candidates = student._gw_email_candidates()
        self.assertEqual(candidates[0], 'jmorote')
        self.assertEqual(candidates[1], 'jmorotep')
        self.assertIn('jmorotep06', candidates)
        self.assertIn('jmorotep89', candidates)
        self.assertIn('jmorotep6789', candidates)
        # dedup preserves order / no repeats
        self.assertEqual(len(candidates), len(set(candidates)))

    def test_email_candidates_single_surname(self):
        student = self._new_student(firstname='Ada', lastname='Lovelace', student_id='11')
        candidates = student._gw_email_candidates()
        self.assertEqual(candidates[0], 'alovelace')

    def test_email_used_by_other_student(self):
        self._new_student(student_id='2000001', student_email='taken@elpuig.xeill.net')
        student = self._new_student(student_id='2000002')
        self.assertTrue(student._gw_email_used_in_ems('taken@elpuig.xeill.net'))

    # --- creation flow ---------------------------------------------------

    def test_create_dry_run_sets_student_email(self):
        student = self._new_student()
        with patch.object(type(student), '_gw_deliver_credentials', return_value=(True, True)):
            student.action_create_google_account()
        self.assertTrue(student.student_email)
        self.assertTrue(student.student_email.endswith('@elpuig.xeill.net'))

    def test_create_minor_uses_minor_ou(self):
        student = self._new_student(birth_date=date.today() - relativedelta(years=15))
        with patch.object(type(student), '_gw_deliver_credentials', return_value=(True, True)):
            student.action_create_google_account()
        last_message = student.message_ids.sorted('id')[-1].body
        self.assertIn('/alumnos', last_message)

    def test_create_adult_uses_adult_ou(self):
        student = self._new_student(birth_date=date.today() - relativedelta(years=19))
        with patch.object(type(student), '_gw_deliver_credentials', return_value=(True, True)):
            student.action_create_google_account()
        last_message = student.message_ids.sorted('id')[-1].body
        self.assertIn('/alumnos/+18', last_message)

    def test_create_idempotent_when_email_already_set(self):
        student = self._new_student(student_email='already@elpuig.xeill.net')
        with patch.object(type(student), '_gw_deliver_credentials') as deliver:
            student.action_create_google_account()
        deliver.assert_not_called()
        self.assertEqual(student.student_email, 'already@elpuig.xeill.net')

    def test_create_missing_data_raises(self):
        student = self._new_student(student_id=False)
        with self.assertRaises(UserError):
            student.action_create_google_account()

    def test_create_non_student_is_noop(self):
        applicant = self._new_student(contact_type='applicant')
        with patch.object(type(applicant), '_gw_deliver_credentials') as deliver:
            applicant.action_create_google_account()
        deliver.assert_not_called()
        self.assertFalse(applicant.student_email)

    # --- suspend / reactivate --------------------------------------------

    def test_suspend_dry_run(self):
        student = self._new_student(student_email='laia@elpuig.xeill.net')
        student.action_suspend_google_account()
        self.assertTrue(student.google_ws_suspended)

    def test_suspend_is_idempotent(self):
        student = self._new_student(
            student_email='laia@elpuig.xeill.net', google_ws_suspended=True)
        student.action_suspend_google_account()
        self.assertTrue(student.google_ws_suspended)

    def test_reactivate_dry_run(self):
        student = self._new_student(
            student_email='laia@elpuig.xeill.net', google_ws_suspended=True)
        student.action_reactivate_google_account()
        self.assertFalse(student.google_ws_suspended)

    def test_reactivate_without_account_is_noop(self):
        student = self._new_student()
        student.action_reactivate_google_account()
        self.assertFalse(student.google_ws_suspended)

    # --- relocate (minor -> adult OU when birth_date arrives later) -------

    def test_relocate_dry_run_logs_target_ou(self):
        student = self._new_student(
            student_email='laia@elpuig.xeill.net',
            birth_date=date.today() - relativedelta(years=19),
        )
        # Must not raise — the only assertion is that it completes cleanly.
        student.action_relocate_google_account()

    def test_relocate_skips_suspended_account(self):
        student = self._new_student(
            student_email='laia@elpuig.xeill.net', google_ws_suspended=True,
        )
        # Would raise if it tried to call the (dry-run-skipped) service path;
        # completing without error confirms the early-return guard.
        student.action_relocate_google_account()

    def test_relocate_uses_shared_gw_helper(self):
        # Regression test for a real bug found during this DTON pass
        # (2026-07-28): action_relocate_google_account called the undefined
        # self._gw_get_service() directly instead of self._gw()._gw_get_service()
        # (the mixin). Only reachable outside dry-run, hence the manual toggle.
        student = self._new_student(
            student_email='laia@elpuig.xeill.net',
            birth_date=date.today() - relativedelta(years=19),
        )
        mock_service = Mock()
        self.company.google_ws_dry_run = False
        try:
            with patch(
                'odoo.addons.ems.models.shared.google_workspace_mixin.'
                'GoogleWorkspaceMixin._gw_get_service',
                return_value=mock_service,
            ):
                student.action_relocate_google_account()
        finally:
            self.company.google_ws_dry_run = True
        mock_service.users.return_value.patch.assert_called_once()
        _args, kwargs = mock_service.users.return_value.patch.call_args
        self.assertEqual(kwargs['userKey'], 'laia@elpuig.xeill.net')
        self.assertEqual(kwargs['body']['orgUnitPath'], '/alumnos/+18')

    # --- unlink ------------------------------------------------------------

    def test_unlink_suspends_google_account(self):
        student = self._new_student(student_email='laia@elpuig.xeill.net')
        with patch.object(type(student), 'action_suspend_google_account', autospec=True) as suspend:
            student.unlink()
        suspend.assert_called_once_with(student)

    def test_unlink_without_account_does_not_call_suspend(self):
        student = self._new_student()
        with patch.object(type(student), 'action_suspend_google_account', autospec=True) as suspend:
            student.unlink()
        suspend.assert_not_called()


class TestStudentGoogleWorkspaceLifecycle(TransactionCase):
    """Issue #388: archiving a student opens a 30-day grace period before the Google
    account is suspended, and a further 30 days before it is deleted.

    Everything runs in dry-run so no real Google API call is performed, and the
    warning email is patched out at the transport level.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            'google_ws_enabled': True,
            'google_ws_dry_run': True,
            'google_ws_domain': 'elpuig.xeill.net',
            'google_ws_ou_minor': '/alumnos',
            'google_ws_ou_adult': '/alumnos/+18',
            'google_ws_ou_suspended': '/alumnos/bajas',
        })
        patcher = patch(
            'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email')
        patcher.start()
        cls.addClassCleanup(patcher.stop)

    def _new_student(self, **vals):
        base = {
            'name': 'Laia Puig Roca', 'firstname': 'Laia', 'lastname': 'Puig Roca',
            'contact_type': 'student', 'student_id': '1234567890',
            'email': 'laia.personal@example.com',
            'student_email': 'lpuig@elpuig.xeill.net',
            'birth_date': date.today() - relativedelta(years=15),
        }
        base.update(vals)
        return self.env['res.partner'].create(base)

    # --- stage 1: scheduling on archive -----------------------------------

    def test_archive_schedules_deactivation_instead_of_suspending(self):
        student = self._new_student()
        student.write({'active': False})
        self.assertEqual(
            student.google_ws_deactivation_date,
            date.today() + relativedelta(days=GW_DEACTIVATION_DELAY_DAYS))
        self.assertFalse(student.google_ws_suspended)
        self.assertFalse(student.google_ws_deletion_date)

    def test_archive_sends_the_warning_email(self):
        student = self._new_student()
        with patch.object(type(self.env['mail.template']), 'send_mail') as send_mail:
            student.write({'active': False})
        send_mail.assert_called_once()

    def test_unarchive_cancels_the_schedule(self):
        student = self._new_student()
        student.write({'active': False})
        student.write({'active': True})
        self.assertFalse(student.google_ws_deactivation_date)

    def test_manual_cancel_button(self):
        student = self._new_student()
        student.write({'active': False})
        student.action_cancel_scheduled_deactivation()
        self.assertFalse(student.google_ws_deactivation_date)

    # --- stage 2: suspension schedules the deletion -----------------------

    def test_suspending_schedules_the_deletion(self):
        student = self._new_student()
        student.action_suspend_google_account()
        self.assertEqual(
            student.google_ws_deletion_date,
            date.today() + relativedelta(days=GW_DELETION_DELAY_DAYS))
        self.assertFalse(student.google_ws_deactivation_date)

    def test_reactivating_cancels_the_deletion(self):
        student = self._new_student()
        student.action_suspend_google_account()
        student.action_reactivate_google_account()
        self.assertFalse(student.google_ws_deletion_date)
        self.assertFalse(student.google_ws_suspended)

    # --- stage 3: deletion -------------------------------------------------

    def test_delete_dry_run_marks_the_account_deleted(self):
        student = self._new_student()
        student.action_suspend_google_account()
        student.action_delete_google_account()
        self.assertTrue(student.google_ws_deleted)
        self.assertFalse(student.google_ws_deletion_date)

    def test_delete_keeps_the_corporate_email_reserved(self):
        student = self._new_student()
        student.action_suspend_google_account()
        student.action_delete_google_account()
        self.assertEqual(student.student_email, 'lpuig@elpuig.xeill.net')
        # The address stays taken, so it is never handed to a different student.
        other = self._new_student(name='Pau Roca', student_id='9876543210',
                                  student_email=False)
        self.assertTrue(other._gw_email_used_in_ems('lpuig@elpuig.xeill.net'))

    def test_delete_refuses_an_account_that_is_not_suspended(self):
        student = self._new_student()
        student.action_delete_google_account()
        self.assertFalse(student.google_ws_deleted)

    def test_delete_is_idempotent(self):
        student = self._new_student()
        student.action_suspend_google_account()
        student.action_delete_google_account()
        student.google_ws_deletion_date = date.today()
        student.action_delete_google_account()
        self.assertTrue(student.google_ws_deleted)

    def test_delete_calls_the_directory_api(self):
        student = self._new_student()
        student.action_suspend_google_account()
        mock_service = Mock()
        self.company.google_ws_dry_run = False
        try:
            with patch(
                'odoo.addons.ems.models.shared.google_workspace_mixin.'
                'GoogleWorkspaceMixin._gw_get_service',
                return_value=mock_service,
            ):
                student.action_delete_google_account()
        finally:
            self.company.google_ws_dry_run = True
        mock_service.users.return_value.delete.assert_called_once_with(
            userKey='lpuig@elpuig.xeill.net')

    def test_reactivating_a_deleted_account_recreates_it(self):
        # Patching action_create_google_account is not an option here: queue_job
        # refuses a mock ("Job accepts only methods of Models"), so the real dry-run
        # creation runs and the assertion is on its outcome - a brand-new address.
        student = self._new_student()
        student.action_suspend_google_account()
        student.action_delete_google_account()
        student.action_reactivate_google_account()
        self.assertFalse(student.google_ws_deleted)
        self.assertFalse(student.google_ws_deletion_date)
        # The address itself may well come back the same: the candidates are derived
        # from the name, and it is no longer taken by anyone once the record released
        # it. Google is the one that decides, replying 409 while it still holds the
        # deleted address, in which case the next candidate is used.
        self.assertTrue(student.student_email)

    # --- the cron ----------------------------------------------------------

    def test_cron_does_nothing_before_the_dates(self):
        student = self._new_student()
        student.write({'active': False})
        with patch.object(type(student), 'action_suspend_google_account') as suspend:
            self.env['res.partner'].with_context(
            queue_job__no_delay=True)._gw_cron_process_lifecycle()
        suspend.assert_not_called()

    def test_cron_suspends_once_the_deactivation_date_is_reached(self):
        student = self._new_student()
        student.write({'active': False})
        student.google_ws_deactivation_date = date.today()
        self.env['res.partner'].with_context(
            queue_job__no_delay=True)._gw_cron_process_lifecycle()
        self.assertTrue(student.google_ws_suspended)
        self.assertEqual(
            student.google_ws_deletion_date,
            date.today() + relativedelta(days=GW_DELETION_DELAY_DAYS))

    def test_cron_deletes_once_the_deletion_date_is_reached(self):
        student = self._new_student()
        student.write({'active': False})
        student.google_ws_deactivation_date = date.today()
        self.env['res.partner'].with_context(
            queue_job__no_delay=True)._gw_cron_process_lifecycle()
        student.google_ws_deletion_date = date.today()
        self.env['res.partner'].with_context(
            queue_job__no_delay=True)._gw_cron_process_lifecycle()
        self.assertTrue(student.google_ws_deleted)

    def test_cron_never_deletes_an_account_without_a_deletion_date(self):
        # Students suspended before this feature existed have no deletion date:
        # the migration deliberately does not backfill one.
        student = self._new_student(google_ws_suspended=True)
        student.write({'active': False})
        self.env['res.partner'].with_context(
            queue_job__no_delay=True)._gw_cron_process_lifecycle()
        self.assertFalse(student.google_ws_deleted)

    def test_cron_ignores_active_students(self):
        student = self._new_student()
        student.google_ws_deactivation_date = date.today()
        self.env['res.partner'].with_context(
            queue_job__no_delay=True)._gw_cron_process_lifecycle()
        self.assertFalse(student.google_ws_suspended)

    # --- withdrawal / graduation path --------------------------------------

    def test_withdrawal_schedules_instead_of_suspending(self):
        student = self._new_student()
        student.sudo()._gw_schedule_deactivation()
        self.assertTrue(student.google_ws_deactivation_date)
        self.assertFalse(student.google_ws_suspended)

    def test_schedule_covers_ex_students(self):
        alumni = self._new_student(contact_type='alumni')
        alumni._gw_schedule_deactivation()
        self.assertTrue(alumni.google_ws_deactivation_date)

    # --- who may see the schedule ------------------------------------------

    def _teacher_user(self):
        return self.env['res.users'].create({
            'name': 'GW Lifecycle Teacher', 'login': 'gw.lifecycle.teacher',
            'email': 'gw.lifecycle.teacher@example.com', 'lang': 'en_US',
            'groups_id': [(6, 0, [self.env.ref('ems.group_teacher').id,
                                  self.env.ref('base.group_user').id])],
        })

    def test_schedule_is_hidden_from_teachers(self):
        # rule_contact_teacher gives the teacher role read access to every res.partner,
        # so the form's banners/columns must be restricted the same way its Google
        # buttons already are - a tutor opening a former student's file has no business
        # reading the account's schedule while being unable to act on it.
        teacher = self._teacher_user()
        arch = self.env['res.partner'].with_user(teacher).get_view(
            self.env.ref('ems.view_contact_form').id, 'form')['arch']
        self.assertNotIn('google_ws_deactivation_date', arch)
        self.assertNotIn('google_ws_deletion_date', arch)

    def test_schedule_is_visible_to_the_secretary(self):
        secretary = self.env['res.users'].create({
            'name': 'GW Lifecycle Secretary', 'login': 'gw.lifecycle.secretary',
            'email': 'gw.lifecycle.secretary@example.com', 'lang': 'en_US',
            'groups_id': [(6, 0, [self.env.ref('ems.group_secretary').id,
                                  self.env.ref('base.group_user').id])],
        })
        arch = self.env['res.partner'].with_user(secretary).get_view(
            self.env.ref('ems.view_contact_form').id, 'form')['arch']
        self.assertIn('google_ws_deactivation_date', arch)
        self.assertIn('google_ws_deletion_date', arch)

    def test_search_filters_are_hidden_from_teachers(self):
        teacher = self._teacher_user()
        arch = self.env['res.partner'].with_user(teacher).get_view(
            self.env.ref('ems.view_student_search').id, 'search')['arch']
        self.assertNotIn('gw_deactivation_pending', arch)
        self.assertNotIn('gw_deletion_pending', arch)

    # --- hard delete keeps the old immediate behaviour ---------------------

    def test_unlink_still_suspends_immediately(self):
        student = self._new_student()
        with patch.object(
                type(student), 'action_suspend_google_account', autospec=True) as suspend:
            student.unlink()
        suspend.assert_called_once()


class TestStudentGooglePasswordReset(TransactionCase):
    """Issue #478: "Reset Google password" on the student form, for academic admin and TAC only.
    Dry-run unless a test switches it off, and the credentials delivery (PDF + email) is patched."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.company = cls.env.company
        cls.company.write({
            'google_ws_enabled': True, 'google_ws_dry_run': True, 'google_ws_domain': 'elpuig.xeill.net',
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Reset Password Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'student_email': 'reset.student@elpuig.xeill.net', 'email': 'reset.personal@example.com',
        })
        cls.old_credentials = cls.env['ems.student.document'].create({
            'partner_id': cls.student.id, 'doc_type': 'google_credentials', 'status': 'approved',
        })
        cls.tac = create_role_user(cls, 'tac', 'test_tac_gw_reset')

    def _reset(self, user):
        student = self.student.with_user(user)
        with patch.object(type(self.student), '_gw_deliver_credentials', autospec=True,
                          return_value=(True, True)) as deliver:
            student.action_reset_google_password()
        return deliver

    def test_tac_resets_password_and_delivers_new_credentials(self):
        deliver = self._reset(self.tac)
        deliver.assert_called_once()
        __, email, password = deliver.call_args.args
        self.assertEqual(email, 'reset.student@elpuig.xeill.net')
        self.assertGreaterEqual(len(password), 12)
        self.assertEqual(self.old_credentials.status, 'cancelled', "the old PDF holds a dead password")
        note = self.student.message_ids[:1]
        self.assertIn('reset.student@elpuig.xeill.net', note.body)
        self.assertEqual(note.author_id, self.tac.partner_id)

    def test_academic_admin_can_reset(self):
        admin = create_role_user(self, 'academic_admin', 'test_admin_gw_reset')
        self._reset(admin).assert_called_once()

    def test_other_roles_cannot_reset(self):
        for role in ('secretary', 'tutor', 'teacher'):
            with self.subTest(role=role), self.assertRaises(AccessError):
                self._reset(create_role_user(self, role, f'test_{role}_gw_reset'))
        self.assertEqual(self.old_credentials.status, 'approved')

    def test_reset_requires_an_active_account(self):
        self.student.google_ws_suspended = True
        with self.assertRaises(UserError):
            self._reset(self.tac)

    def test_reset_sends_the_password_to_google(self):
        mock_service = Mock()
        self.company.google_ws_dry_run = False
        with patch('odoo.addons.ems.models.shared.google_workspace_mixin.'
                   'GoogleWorkspaceMixin._gw_get_service', return_value=mock_service):
            deliver = self._reset(self.tac)
        __, kwargs = mock_service.users.return_value.patch.call_args
        self.assertEqual(kwargs['userKey'], 'reset.student@elpuig.xeill.net')
        self.assertEqual(kwargs['body'], {
            'password': deliver.call_args.args[2], 'changePasswordAtNextLogin': True,
        })

    def test_google_refusal_is_reported_and_keeps_old_credentials(self):
        mock_service = Mock()
        # HttpError falls back to a plain Exception when the Google libraries are missing.
        error = HttpError(Mock(status=403), b'Not Authorized') if HttpError is not Exception else HttpError('403')
        mock_service.users.return_value.patch.return_value.execute.side_effect = error
        self.company.google_ws_dry_run = False
        with patch('odoo.addons.ems.models.shared.google_workspace_mixin.'
                   'GoogleWorkspaceMixin._gw_get_service', return_value=mock_service), \
                self.assertRaises(UserError):
            self._reset(self.tac)
        self.assertEqual(self.old_credentials.status, 'approved')


class TestStudentGoogleWorkspaceTac(TransactionCase):
    """The TAC team creates and suspends student Google accounts too, from the form header, while
    only reading students (rule_contact_teacher). Dry-run; credentials delivery patched."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.env.company.write({
            'google_ws_enabled': True, 'google_ws_dry_run': True, 'google_ws_domain': 'elpuig.xeill.net',
            'google_ws_ou_minor': '/alumnos', 'google_ws_ou_adult': '/alumnos/+18',
            'google_ws_ou_suspended': '/alumnos/bajas',
        })
        cls.tac = create_role_user(cls, 'tac', 'test_tac_gw_account', email='tac.gw@example.com')
        cls.student = cls.env['res.partner'].create({
            'name': 'Tac Account Student', 'firstname': 'Tac', 'lastname': 'Account Student',
            'contact_type': 'student', 'student_id': next_student_id(), 'email': 'tac.account@example.com',
            'birth_date': date.today() - relativedelta(years=15),
        })

    def test_tac_creates_the_account(self):
        with patch.object(type(self.student), '_gw_deliver_credentials', return_value=(True, True)):
            self.student.with_user(self.tac).action_create_google_account()
        self.assertTrue(self.student.student_email)
        self.assertEqual(self.student.message_ids[:1].author_id, self.tac.partner_id)

    def test_tac_suspends_the_account(self):
        self.student.student_email = 'tac.account@elpuig.xeill.net'
        self.student.with_user(self.tac).action_suspend_google_account()
        self.assertEqual(self.student.google_ws_state, 'suspended')
        self.assertEqual(self.student.message_ids[:1].author_id, self.tac.partner_id)

    def test_tac_sees_the_create_and_suspend_buttons(self):
        arch = self.env['res.partner'].with_user(self.tac).get_view(
            self.env.ref('ems.view_contact_form').id, 'form')['arch']
        self.assertIn('action_create_google_account', arch)
        self.assertIn('action_suspend_google_account', arch)
        self.assertNotIn('action_reactivate_google_account', arch)

