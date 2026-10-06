import importlib.util
import os
from unittest.mock import MagicMock, Mock, patch

from dateutil.relativedelta import relativedelta
from psycopg2.errors import LockNotAvailable

from odoo.addons.ems.models.shared.google_workspace_mixin import (
    GW_DEACTIVATION_DELAY_DAYS,
    HttpError,
)
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger
from .common import next_student_id


class TestEmployeeGoogleWorkspace(TransactionCase):
    """Backend tests for the staff (teachers/ASP) Google Workspace integration.

    Everything runs in dry-run so no real Google API call is performed, and the
    credential delivery (PDF render + email) is patched out to keep the tests
    isolated from wkhtmltopdf / mail.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            'google_ws_enabled': True,
            'google_ws_dry_run': True,
            'google_ws_domain': 'elpuig.xeill.net',
            'google_ws_ou_teacher': '/claustro/doble-factor-autenticación',
            'google_ws_ou_asp': '/pas',
            'google_ws_ou_staff_suspended': '/claustro/bajas',
        })

    def _new_teacher(self, **vals):
        base = {'name': 'Ada Lovelace King', 'employee_type': 'teacher'}
        base.update(vals)
        return self.env['hr.employee'].create(base)

    # --- readiness -----------------------------------------------------
    def test_missing_fields_requires_personal_email(self):
        teacher = self._new_teacher()
        self.assertIn('Personal email', teacher._gw_missing_fields())
        self.assertFalse(teacher._gw_ready())

    def test_ready_with_personal_email(self):
        teacher = self._new_teacher(private_email='ada@example.com')
        self.assertFalse(teacher._gw_missing_fields())
        self.assertTrue(teacher._gw_ready())

    def test_nif_is_optional(self):
        teacher = self._new_teacher(private_email='ada@example.com')
        self.assertFalse(teacher._gw_missing_fields())

    # --- google_ws_state (single source of truth for header buttons) ---
    def test_state_none_for_non_teaching_staff(self):
        # employee_type only accepts 'teacher'/'asp'; unset (False) covers any other staff.
        employee = self.env['hr.employee'].create({'name': 'Admin Staff'})
        self.assertEqual(employee.google_ws_state, 'none')

    def test_state_none_without_work_email(self):
        teacher = self._new_teacher(private_email='ada@example.com')
        self.assertEqual(teacher.google_ws_state, 'none')

    def test_state_manual_pending(self):
        teacher = self._new_teacher(google_ws_manual_email=True)
        self.assertEqual(teacher.google_ws_state, 'manual_pending')

    def test_state_pending_user_when_email_without_linked_user(self):
        teacher = self._new_teacher(work_email='ada.pending@elpuig.xeill.net')
        self.assertFalse(teacher.user_id)
        self.assertEqual(teacher.google_ws_state, 'pending_user')

    def test_state_active_once_user_linked(self):
        teacher = self._new_teacher(work_email='ada.active@elpuig.xeill.net')
        teacher.action_create_ems_user()
        self.assertTrue(teacher.user_id)
        self.assertEqual(teacher.google_ws_state, 'active')

    def test_state_suspended(self):
        teacher = self._new_teacher(
            work_email='ada.suspended@elpuig.xeill.net', google_ws_suspended=True)
        self.assertEqual(teacher.google_ws_state, 'suspended')

    # --- chatter notifications ------------------------------------------
    def test_create_without_personal_email_notifies_chatter(self):
        teacher = self._new_teacher()
        messages = teacher.message_ids.mapped('body')
        self.assertTrue(any('Personal email' in b for b in messages))

    def test_notification_not_duplicated_on_further_writes(self):
        teacher = self._new_teacher()
        count_before = len(teacher.message_ids)
        teacher.write({'name': 'Ada Lovelace King Jr.'})
        count_after = len(teacher.message_ids)
        self.assertEqual(count_before, count_after)

    def test_no_notification_once_ready(self):
        teacher = self._new_teacher()
        self.assertTrue(any('Personal email' in b for b in teacher.message_ids.mapped('body')))
        # queue_job__no_delay makes with_delay() run synchronously so the
        # write-triggered creation is directly observable in this test.
        with patch.object(type(teacher), '_gw_deliver_credentials', return_value=(True, True)):
            teacher.with_context(queue_job__no_delay=True).write({'private_email': 'ada@example.com'})
        # once ready, the account is created (work_email set) instead of re-notifying
        self.assertTrue(teacher.work_email)

    def test_no_notification_for_manual_email_employees(self):
        teacher = self._new_teacher(google_ws_manual_email=True)
        messages = teacher.message_ids.mapped('body')
        self.assertFalse(any('Personal email' in b for b in messages))

    # --- login candidates ---------------------------------------------
    def test_split_name(self):
        teacher = self._new_teacher(name='Ada Lovelace')
        self.assertEqual(teacher._gw_split_name(), ('Ada', 'Lovelace'))

    def test_login_candidates_suggested_first(self):
        teacher = self._new_teacher(google_ws_login='Ada.Lovelace')
        self.assertEqual(teacher._gw_login_candidates()[0], 'adalovelace')

    def test_login_candidates_accepts_domain(self):
        # A suggested value pasted WITH the domain keeps only the local part.
        teacher = self._new_teacher(google_ws_login='jdoe@elpuig.xeill.net')
        self.assertEqual(teacher._gw_login_candidates()[0], 'jdoe')

    def test_manual_email_blocks_autocreation(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', google_ws_manual_email=True)
        self.assertFalse(teacher._gw_ready())

    def test_login_candidates_fallback_from_name(self):
        teacher = self._new_teacher(name='Ada Lovelace King')
        candidates = teacher._gw_login_candidates()
        # initial(name)+surname1, +initial(surname2), then numeric differentiators
        self.assertEqual(candidates[0], 'alovelace')
        self.assertEqual(candidates[1], 'alovelacek')
        self.assertIn('alovelacek01', candidates)
        # dedup preserves order / no repeats
        self.assertEqual(len(candidates), len(set(candidates)))

    # --- creation flow -------------------------------------------------
    def test_create_dry_run_sets_work_email_from_suggested(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', google_ws_login='jdoe')
        with patch.object(type(teacher), '_gw_deliver_credentials', return_value=(True, True)):
            teacher._gw_create_account()
        self.assertEqual(teacher.work_email, 'jdoe@elpuig.xeill.net')

    def test_create_dry_run_fallback_email(self):
        teacher = self._new_teacher(name='Ada Lovelace', private_email='ada@example.com')
        with patch.object(type(teacher), '_gw_deliver_credentials', return_value=(True, True)):
            teacher._gw_create_account()
        self.assertEqual(teacher.work_email, 'alovelace@elpuig.xeill.net')

    def test_switching_a_vacancy_to_named_identifies_it_and_queues_the_account(self):
        teacher = self._new_vacancy('X9')
        self.assertFalse(self._creation_jobs(teacher))

        # What the form saves when the staffing type is switched and the person's data filled in.
        teacher.write({'staffing_type': 'named', 'name': 'Ada Lovelace King',
                       'private_email': 'ada@example.com'})

        self.assertFalse(teacher.schedule_import_code)
        self.assertFalse(teacher.pending_identification)
        self.assertEqual(teacher.staffing_type, 'named')
        self.assertTrue(any('X9' in body for body in teacher.message_ids.mapped('body')))
        self.assertEqual(len(self._creation_jobs(teacher)), 1)
        with patch.object(type(teacher), '_gw_deliver_credentials', return_value=(True, True)):
            teacher._gw_create_account()
        self.assertTrue(teacher.work_email)

    def test_button_refuses_a_vacancy(self):
        teacher = self.env['hr.employee'].create({
            'name': 'Pending teacher (X10)',
            'employee_type': 'teacher',
            'schedule_import_code': 'X10',
        })
        with self.assertRaises(UserError):
            teacher.action_create_google_account()
        self.assertTrue(teacher.pending_identification)

    def test_adopt_existing_corporate_email_does_nothing(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada.existing@elpuig.xeill.net')
        with patch.object(type(teacher), '_gw_deliver_credentials') as deliver:
            teacher.action_create_google_account()
        deliver.assert_not_called()
        self.assertEqual(teacher.work_email, 'ada.existing@elpuig.xeill.net')

    def test_adopt_existing_corporate_email_clears_pending_identification(self):
        # Bug found while investigating #378: action_create_google_account's "adopt"
        # branch (work_email already corporate) used to return via action_create_ems_user()
        # before ever reaching the schedule_import_code-clearing logic, leaving a pending
        # teacher stuck even though a real EMS account now exists for them.
        teacher = self.env['hr.employee'].create({
            'name': 'Pending teacher (X11)',
            'employee_type': 'teacher',
            'schedule_import_code': 'X11',
            'private_email': 'ada@example.com',
            'work_email': 'ada.adopted@elpuig.xeill.net',
        })
        self.assertTrue(teacher.pending_identification)

        teacher.action_create_google_account()

        self.assertTrue(teacher.user_id)
        self.assertFalse(teacher.schedule_import_code)
        self.assertFalse(teacher.pending_identification)
        self.assertTrue(any('X11' in body for body in teacher.message_ids.mapped('body')))

    # --- button vs automatic creation (#582) ----------------------------
    # The button used to create the account itself while the automatic job did the same, and
    # both ended up creating one each. Now there is one job, a hidden button while it lasts,
    # and a row lock before Google.
    def _creation_jobs(self, teacher):
        return self.env['queue.job'].search([('identity_key', '=', teacher._gw_create_job_key())])

    def test_button_queues_the_same_job_instead_of_creating(self):
        teacher = self._new_teacher(private_email='ada@example.com')
        self.assertEqual(len(self._creation_jobs(teacher)), 1)  # the automatic creation
        with patch.object(type(teacher), '_gw_deliver_credentials') as deliver:
            action = teacher.action_create_google_account()
            teacher.action_create_google_account()
        deliver.assert_not_called()
        self.assertFalse(teacher.work_email)
        self.assertEqual(len(self._creation_jobs(teacher)), 1)
        self.assertEqual(action['tag'], 'display_notification')

    def test_button_hidden_while_the_creation_is_queued_or_running(self):
        teacher = self._new_teacher(private_email='ada@example.com')
        job = self._creation_jobs(teacher)
        self.assertTrue(teacher.google_ws_creation_pending)
        # queue_job's own deduplication ignores a started job: the flag must not.
        for state, pending in (('started', True), ('failed', False), ('done', False)):
            with self.subTest(state=state):
                self.env.cr.execute("UPDATE queue_job SET state = %s WHERE id = %s", [state, job.id])
                teacher.invalidate_recordset(['google_ws_creation_pending'])
                self.assertEqual(teacher.google_ws_creation_pending, pending)

    def test_creation_stops_before_google_when_the_record_is_locked(self):
        teacher = self._new_teacher(private_email='ada@example.com')
        self.company.google_ws_dry_run = False
        mixin = type(self.env['google.workspace.mixin'])
        with patch.object(mixin, '_gw_lock_for_creation', side_effect=LockNotAvailable), \
                patch.object(mixin, '_gw_get_service') as service, \
                self.assertRaises(LockNotAvailable):
            teacher._gw_create_account()
        service.assert_not_called()
        self.assertFalse(teacher.work_email)

    def test_lock_for_creation_holds_the_row(self):
        # A committed row nothing else in this transaction touches, so a second connection
        # sees it and can only fail on the lock taken here.
        user = self.env.ref('base.public_user')
        self.env['google.workspace.mixin']._gw_lock_for_creation(user)
        with self.registry.cursor() as other_cr, mute_logger('odoo.sql_db'), \
                self.assertRaises(LockNotAvailable):
            other_cr.execute("SELECT 1 FROM res_users WHERE id = %s FOR UPDATE NOWAIT", [user.id])

    # --- vacancies pending identification (#584) -------------------------
    def _new_vacancy(self, code, **vals):
        # What the form creates with the staffing type set to a vacancy.
        base = {'name': 'Vacancy %s' % code, 'employee_type': 'teacher',
                'staffing_type': 'vacancy', 'schedule_import_code': code}
        base.update(vals)
        return self.env['hr.employee'].create(base)

    def test_vacancy_needs_no_personal_email_and_gets_no_account(self):
        teacher = self._new_vacancy('X12')
        self.assertTrue(teacher.pending_identification)
        self.assertEqual(teacher.staffing_type, 'vacancy')
        self.assertFalse(self._creation_jobs(teacher))
        # Missing data is expected on a vacancy: no "missing required data" note either.
        self.assertFalse(teacher.google_ws_missing_notice_sent)

    def test_vacancy_without_a_name_takes_its_code(self):
        # The form doesn't require a name on a vacancy; resource.resource does.
        teacher = self._new_vacancy(' X19 ', name=False)
        self.assertEqual(teacher.name, 'X19')

    def test_vacancy_with_a_personal_email_still_gets_no_account(self):
        teacher = self._new_vacancy('X13', private_email='someone@example.com')
        self.assertFalse(teacher._gw_ready())
        self.assertFalse(self._creation_jobs(teacher))

    def test_vacancy_needs_its_code(self):
        with self.assertRaises(ValidationError):
            self._new_vacancy(False)

    def test_only_teachers_can_be_vacancies(self):
        with self.assertRaises(ValidationError):
            self._new_vacancy('X14', employee_type='asp')

    def test_vacancy_code_is_unique_among_active_teachers(self):
        first = self._new_vacancy('X15')
        with self.assertRaises(ValidationError):
            self._new_vacancy(' x15 ')
        first.write({'active': False})
        second = self._new_vacancy(' x15 ')
        self.assertEqual(second.schedule_import_code, 'x15')

    def test_staffing_type_follows_the_code(self):
        # A schedule importer's placeholder only sets the code, never the staffing type.
        placeholder = self.env['hr.employee'].create({
            'name': 'Pending teacher (X16)', 'employee_type': 'teacher',
            'schedule_import_code': 'X16'})
        self.assertEqual(placeholder.staffing_type, 'vacancy')
        self.assertEqual(self._new_teacher().staffing_type, 'named')

    def test_schedule_importer_finds_a_vacancy_created_on_the_form(self):
        vacancy = self._new_vacancy('x17')
        importer = self.env['ems.working_schedules_import_wizard']
        self.assertEqual(importer._get_or_create_pending_teacher('X17'), vacancy)

    def test_identity_confirmation_is_translated(self):
        teacher = self._new_vacancy('X18')
        teacher.with_context(lang='ca_ES').write({'staffing_type': 'named'})
        self.assertTrue(any(
            'Identitat confirmada' in body for body in teacher.message_ids.mapped('body')))

    def test_switching_a_named_teacher_without_code_posts_nothing(self):
        teacher = self._new_teacher(private_email='ada@example.com')
        count_before = len(teacher.message_ids)
        teacher.write({'staffing_type': 'named'})
        self.assertEqual(len(teacher.message_ids), count_before)

    def test_named_teacher_cannot_become_a_vacancy(self):
        # The form hides the selector once the teacher is named; the server refuses it too.
        teacher = self._new_teacher(private_email='ada@example.com')
        with self.assertRaises(ValidationError):
            teacher.write({'staffing_type': 'vacancy', 'schedule_import_code': 'X20'})
        with self.assertRaises(ValidationError):
            teacher.write({'schedule_import_code': 'X20'})
        identified = self._new_vacancy('X21')
        identified.write({'staffing_type': 'named', 'private_email': 'grace@example.com'})
        with self.assertRaises(ValidationError):
            identified.write({'staffing_type': 'vacancy', 'schedule_import_code': 'X21'})

    def test_vacancy_code_can_still_be_changed(self):
        vacancy = self._new_vacancy('X22')
        vacancy.write({'schedule_import_code': 'X23'})
        self.assertEqual(vacancy.schedule_import_code, 'X23')

    def test_non_corporate_work_email_not_overwritten(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@gmail.com')
        with patch.object(type(teacher), '_gw_deliver_credentials') as deliver:
            teacher.action_create_google_account()
        deliver.assert_not_called()
        self.assertEqual(teacher.work_email, 'ada@gmail.com')

    def test_missing_personal_email_raises(self):
        teacher = self._new_teacher(name='Grace Hopper')
        with self.assertRaises(UserError):
            teacher.action_create_google_account()

    # --- collisions ----------------------------------------------------
    def test_email_used_by_other_employee(self):
        self._new_teacher(name='Other One', work_email='taken@elpuig.xeill.net')
        teacher = self._new_teacher(name='Second Two', private_email='s@example.com')
        self.assertTrue(teacher._gw_email_used_in_ems('taken@elpuig.xeill.net'))

    def test_email_used_by_student(self):
        self.env['res.partner'].create({
            'name': 'Student X',
            'contact_type': 'student', 'student_id': next_student_id(),
            'student_email': 'shared@elpuig.xeill.net',
        })
        teacher = self._new_teacher(private_email='s@example.com')
        self.assertTrue(teacher._gw_email_used_in_ems('shared@elpuig.xeill.net'))

    # --- suspend / reactivate -----------------------------------------
    def test_suspend_dry_run(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@elpuig.xeill.net')
        teacher.action_suspend_google_account()
        self.assertTrue(teacher.google_ws_suspended)

    def test_reactivate_dry_run(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@elpuig.xeill.net',
            google_ws_suspended=True)
        teacher.action_reactivate_google_account()
        self.assertFalse(teacher.google_ws_suspended)

    def test_suspend_is_idempotent(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@elpuig.xeill.net',
            google_ws_suspended=True)
        # already suspended: stays suspended, no error
        teacher.action_suspend_google_account()
        self.assertTrue(teacher.google_ws_suspended)

    def test_unlink_suspends_google_account(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@elpuig.xeill.net')
        with patch.object(type(teacher), 'action_suspend_google_account', autospec=True) as suspend:
            teacher.unlink()
        suspend.assert_called_once_with(teacher)

    def test_unlink_without_account_does_not_call_suspend(self):
        teacher = self._new_teacher(private_email='ada@example.com')
        with patch.object(type(teacher), 'action_suspend_google_account', autospec=True) as suspend:
            teacher.unlink()
        suspend.assert_not_called()

    # --- rename (issue #542) -------------------------------------------
    def _rename_calls(self, teacher, vals):
        """Write `vals` with the queue run synchronously; return the rename job's mock."""
        with patch.object(type(teacher), 'action_sync_google_account_name', autospec=True) as sync:
            teacher.with_context(queue_job__no_delay=True).write(vals)
        return sync

    def test_rename_syncs_the_google_account_name(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@elpuig.xeill.net')
        sync = self._rename_calls(teacher, {'name': 'Ada Byron King'})
        sync.assert_called_once_with(teacher)

    def test_rename_without_account_does_not_sync(self):
        # No personal email: not ready, so the write cannot create the account first.
        teacher = self._new_teacher()
        self._rename_calls(teacher, {'name': 'Ada Byron King'}).assert_not_called()

    def test_rename_with_non_corporate_email_does_not_sync(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@example.com')
        self._rename_calls(teacher, {'name': 'Ada Byron King'}).assert_not_called()

    def test_other_writes_do_not_sync_the_name(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@elpuig.xeill.net')
        self._rename_calls(teacher, {'mobile_phone': '600000000'}).assert_not_called()

    def test_rename_with_integration_disabled_does_not_sync(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@elpuig.xeill.net')
        self.company.google_ws_enabled = False
        self._rename_calls(teacher, {'name': 'Ada Byron King'}).assert_not_called()

    def _sync_name_with_service(self, teacher, service):
        self.company.google_ws_dry_run = False
        with patch.object(type(self.env['google.workspace.mixin']), '_gw_get_service',
                          return_value=service):
            teacher.action_sync_google_account_name()

    def test_sync_name_patches_given_and_family_name(self):
        teacher = self._new_teacher(
            name='Ada Byron King', private_email='ada@example.com',
            work_email='ada@elpuig.xeill.net')
        service = MagicMock()
        self._sync_name_with_service(teacher, service)
        __, kwargs = service.users.return_value.patch.call_args
        self.assertEqual(kwargs['userKey'], 'ada@elpuig.xeill.net')
        self.assertEqual(kwargs['body'], {
            'name': {'givenName': 'Ada', 'familyName': 'Byron King'}})

    def test_sync_name_on_a_missing_account_is_reported_not_raised(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@elpuig.xeill.net')
        service = MagicMock()
        service.users.return_value.patch.return_value.execute.side_effect = HttpError(
            Mock(status=404), b'Not Found')
        self._sync_name_with_service(teacher, service)
        self.assertIn('could not be renamed', teacher.message_ids[0].body)

    def test_sync_name_message_is_translated(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@elpuig.xeill.net')
        self._sync_name_with_service(teacher.with_context(lang='ca_ES'), MagicMock())
        self.assertIn("S'ha canviat el nom del compte", teacher.message_ids[0].body)

    def test_sync_name_dry_run_calls_no_service(self):
        teacher = self._new_teacher(
            private_email='ada@example.com', work_email='ada@elpuig.xeill.net')
        with patch.object(type(self.env['google.workspace.mixin']), '_gw_get_service') as service:
            teacher.action_sync_google_account_name()
        service.assert_not_called()

    # --- permissions ---------------------------------------------------
    def test_teacher_cannot_manage_employees(self):
        teacher_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Plain Teacher (GW)',
            'login': 'plain_teacher_gw',
            'groups_id': [(4, self.env.ref('ems.group_teacher').id)],
        })
        with self.assertRaises(AccessError):
            self.env['hr.employee'].with_user(teacher_user).create({
                'name': 'Nope', 'employee_type': 'teacher',
            })

    # --- migration: backfill google_ws_suspended (18.0.0.22.0) ---------------

    @classmethod
    def _load_post_migrate_module(cls):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'migrations', '18.0.0.22.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('ems_post_migrate_18_0_0_22_0', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_migration_backfills_suspended_for_archived_employee(self):
        archived = self._new_teacher(
            name='Migration GW Archived', private_email='migration.gw@example.com',
            work_email='migration.gw@elpuig.xeill.net', active=False)
        # Still active: must be left untouched.
        active_teacher = self._new_teacher(
            name='Migration GW Active', private_email='migration.gw2@example.com',
            work_email='migration.gw2@elpuig.xeill.net')
        # Archived but never had a corporate email: nothing to mark.
        no_email = self._new_teacher(
            name='Migration GW No Email', private_email='migration.gw3@example.com', active=False)

        migration = self._load_post_migrate_module()
        migration._backfill_google_ws_suspended(self.env)
        for employee in (archived, active_teacher, no_email):
            employee.invalidate_recordset()

        self.assertTrue(archived.google_ws_suspended)
        self.assertFalse(active_teacher.google_ws_suspended)
        self.assertFalse(no_email.google_ws_suspended)


class TestEmployeeGoogleWorkspaceLifecycle(TransactionCase):
    """Issue #388: archiving a member of staff opens a 30-day grace period before
    the Google account is suspended, instead of suspending it straight away.

    Everything runs in dry-run so no real Google API call is performed, and the
    warning email is patched out at the template level.
    """

    def _today(self):
        """The company-local day the code schedules lifecycle dates from (context_today), not
        date.today(), which is UTC in Odoo and is a day behind right after local midnight."""
        return self.env['ems.datetime_utils'].get_local_today()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            'google_ws_enabled': True,
            'google_ws_dry_run': True,
            'google_ws_domain': 'elpuig.xeill.net',
            'google_ws_ou_teacher': '/claustro/doble-factor-autenticación',
            'google_ws_ou_staff_suspended': '/claustro/bajas',
        })
        # No real SMTP: the grace-period warning goes through a mail.template.
        patcher = patch(
            'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email')
        patcher.start()
        cls.addClassCleanup(patcher.stop)

    def _new_teacher(self, **vals):
        base = {
            'name': 'Ada Lovelace King',
            'employee_type': 'teacher',
            'private_email': 'ada@example.com',
            'work_email': 'alovelace@elpuig.xeill.net',
        }
        base.update(vals)
        return self.env['hr.employee'].create(base)

    # --- scheduling on archive -------------------------------------------

    def test_archive_schedules_deactivation_instead_of_suspending(self):
        teacher = self._new_teacher()
        teacher.write({'active': False})
        self.assertEqual(
            teacher.google_ws_deactivation_date,
            self._today() + relativedelta(days=GW_DEACTIVATION_DELAY_DAYS))
        self.assertFalse(
            teacher.google_ws_suspended,
            "Archiving must not suspend the account before the grace period ends")

    def test_archive_sends_the_warning_email(self):
        teacher = self._new_teacher()
        with patch.object(type(self.env['mail.template']), 'send_mail') as send_mail:
            teacher.write({'active': False})
        send_mail.assert_called_once()

    def test_archive_without_account_schedules_nothing(self):
        teacher = self._new_teacher(work_email=False)
        teacher.write({'active': False})
        self.assertFalse(teacher.google_ws_deactivation_date)

    def test_archive_twice_keeps_the_first_date(self):
        teacher = self._new_teacher()
        teacher.write({'active': False})
        first = teacher.google_ws_deactivation_date
        teacher.google_ws_deactivation_date = first - relativedelta(days=5)
        teacher.write({'active': False})
        self.assertEqual(teacher.google_ws_deactivation_date, first - relativedelta(days=5))

    # --- cancelling -------------------------------------------------------

    def test_unarchive_cancels_the_schedule(self):
        teacher = self._new_teacher()
        teacher.write({'active': False})
        teacher.write({'active': True})
        self.assertFalse(teacher.google_ws_deactivation_date)

    def test_manual_cancel_button(self):
        teacher = self._new_teacher()
        teacher.write({'active': False})
        teacher.action_cancel_scheduled_deactivation()
        self.assertFalse(teacher.google_ws_deactivation_date)

    def test_suspending_clears_the_schedule(self):
        teacher = self._new_teacher()
        teacher.write({'active': False})
        teacher.action_suspend_google_account()
        self.assertTrue(teacher.google_ws_suspended)
        self.assertFalse(teacher.google_ws_deactivation_date)

    # --- the cron ---------------------------------------------------------

    def test_cron_suspends_only_when_the_date_has_arrived(self):
        teacher = self._new_teacher()
        teacher.write({'active': False})
        with patch.object(type(teacher), 'action_suspend_google_account') as suspend:
            self.env['hr.employee'].with_context(
            queue_job__no_delay=True)._gw_cron_process_lifecycle()
        suspend.assert_not_called()

    def test_cron_suspends_once_the_date_is_reached(self):
        teacher = self._new_teacher()
        teacher.write({'active': False})
        teacher.google_ws_deactivation_date = self._today()
        self.env['hr.employee'].with_context(
            queue_job__no_delay=True)._gw_cron_process_lifecycle()
        self.assertTrue(teacher.google_ws_suspended)

    def test_cron_ignores_active_employees(self):
        teacher = self._new_teacher()
        teacher.google_ws_deactivation_date = self._today()
        self.env['hr.employee'].with_context(
            queue_job__no_delay=True)._gw_cron_process_lifecycle()
        self.assertFalse(teacher.google_ws_suspended)

    def test_cron_is_idempotent(self):
        teacher = self._new_teacher()
        teacher.write({'active': False})
        teacher.google_ws_deactivation_date = self._today()
        self.env['hr.employee'].with_context(
            queue_job__no_delay=True)._gw_cron_process_lifecycle()
        with patch.object(type(teacher), 'action_suspend_google_account') as suspend:
            self.env['hr.employee'].with_context(
            queue_job__no_delay=True)._gw_cron_process_lifecycle()
        suspend.assert_not_called()

    # --- hard delete keeps the old immediate behaviour --------------------

    def test_unlink_still_suspends_immediately(self):
        teacher = self._new_teacher()
        with patch.object(
                type(teacher), 'action_suspend_google_account', autospec=True) as suspend:
            teacher.unlink()
        suspend.assert_called_once()
