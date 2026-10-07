import base64
from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestEmployeeGooglePasswordResetTour(HttpCase):
    """Issue #595: a TAC member resets a teacher's Google password from the form's Actions
    dropdown and sees the new credentials PDF on the form. Dry-run; the PDF render and the
    outgoing email are mocked."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.env.company.write({
            'google_ws_enabled': True, 'google_ws_dry_run': True, 'google_ws_domain': 'elpuig.xeill.net',
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': '0000 GW Reset Tour Teacher', 'employee_type': 'teacher',
            'private_email': 'gw.reset.tour@example.com', 'work_email': 'gw.reset.tour@elpuig.xeill.net',
        })
        cls.teacher.action_create_ems_user()
        cls.teacher.write({
            'google_credentials_pdf': base64.b64encode(b'%PDF old'),
            'google_credentials_filename': 'old_credentials.pdf',
        })
        cls.tac = create_role_user(cls, 'tac', 'test_tac_gw_reset_tour')

    def test_employee_google_password_reset_tour(self):
        with patch('odoo.addons.base.models.ir_actions_report.IrActionsReport._render_qweb_pdf',
                   return_value=(b'%PDF new', 'pdf')):
            self.start_tour(f"/odoo/action-ems.action_employee_kanban/{self.teacher.id}",
                            "ems_employee_google_password_reset", login=self.tac.login)
        self.assertEqual(base64.b64decode(self.teacher.google_credentials_pdf), b'%PDF new')
