import importlib.util
import os
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


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
            teacher.action_create_google_account()
        self.assertEqual(teacher.work_email, 'jdoe@elpuig.xeill.net')

    def test_create_dry_run_fallback_email(self):
        teacher = self._new_teacher(name='Ada Lovelace', private_email='ada@example.com')
        with patch.object(type(teacher), '_gw_deliver_credentials', return_value=(True, True)):
            teacher.action_create_google_account()
        self.assertEqual(teacher.work_email, 'alovelace@elpuig.xeill.net')

    def test_create_google_account_clears_pending_identification(self):
        teacher = self.env['hr.employee'].create({
            'name': 'Pending teacher (X9)',
            'employee_type': 'teacher',
            'schedule_import_code': 'X9',
        })
        self.assertTrue(teacher.pending_identification)

        teacher.write({'name': 'Ada Lovelace King', 'private_email': 'ada@example.com'})
        with patch.object(type(teacher), '_gw_deliver_credentials', return_value=(True, True)):
            teacher.action_create_google_account()

        self.assertFalse(teacher.schedule_import_code)
        self.assertFalse(teacher.pending_identification)
        self.assertTrue(any(
            'X9' in body for body in teacher.message_ids.mapped('body')
        ))

    def test_missing_personal_email_still_raises_for_pending_identification(self):
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

    # --- manual "mark as identified" ------------------------------------
    def test_mark_as_identified_clears_pending(self):
        teacher = self.env['hr.employee'].create({
            'name': 'Pending teacher (X12)',
            'employee_type': 'teacher',
            'schedule_import_code': 'X12',
        })
        self.assertTrue(teacher.pending_identification)

        teacher.action_mark_as_identified()

        self.assertFalse(teacher.schedule_import_code)
        self.assertFalse(teacher.pending_identification)
        self.assertTrue(any('X12' in body for body in teacher.message_ids.mapped('body')))

    def test_mark_as_identified_message_is_translated(self):
        teacher = self.env['hr.employee'].create({
            'name': 'Pending teacher (X13)',
            'employee_type': 'teacher',
            'schedule_import_code': 'X13',
        })
        teacher.with_context(lang='ca_ES').action_mark_as_identified()
        self.assertTrue(any(
            'Identitat confirmada manualment' in body for body in teacher.message_ids.mapped('body')
        ))

    def test_mark_as_identified_noop_when_not_pending(self):
        teacher = self._new_teacher(private_email='ada@example.com')
        self.assertFalse(teacher.pending_identification)
        count_before = len(teacher.message_ids)

        teacher.action_mark_as_identified()

        self.assertFalse(teacher.pending_identification)
        self.assertEqual(len(teacher.message_ids), count_before)

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
            'contact_type': 'student',
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
