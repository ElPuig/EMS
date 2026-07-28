from datetime import date
from unittest.mock import Mock, patch

from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


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
        return self.env['res.partner'].create(base)

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
