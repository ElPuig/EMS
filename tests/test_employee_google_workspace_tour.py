from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo.tests import tagged, HttpCase

from .common import cancel_google_account_creation, force_user_language_to_english, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestEmployeeGoogleWorkspaceTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # This box's ir.mail_server rows point at real, credentialed servers and the
        # seeding below posts to the chatter, and archiving a teacher now sends the
        # grace-period warning (#388) - see CLAUDE.md's "Email safety in tests".
        mock_outgoing_email(cls)

    def _seed_teacher(self, name, **vals):
        # "0000 " prefix: hr.employee's default _order is "name", so these sort first
        # on the list's very first page among the pre-existing teachers in this DB.
        base = {
            'name': '0000 %s' % name,
            'employee_type': 'teacher',
            'private_email': '%s@example.com' % name.lower().replace(' ', '.'),
        }
        base.update(vals)
        return self.env['hr.employee'].create(base)

    def test_employee_google_workspace_state_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # google_ws_state (models/employees/google_workspace_integration.py) drives
        # which header button(s) show — a TransactionCase can assert the compute is
        # right, but only a real browser render catches an OWL/view-arch mistake in
        # the invisible expressions (e.g. two buttons showing at once, the original bug).
        # To watch this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_employee_google_workspace_state", login="admin", watch=True)
        cancel_google_account_creation(self._seed_teacher('GW Tour None'))
        self._seed_teacher('GW Tour Pending', work_email='gw.tour.pending@elpuig.xeill.net')
        active = self._seed_teacher('GW Tour Active', work_email='gw.tour.active@elpuig.xeill.net')
        relink = self._seed_teacher('GW Tour Relink', work_email='gw.tour.relink@elpuig.xeill.net')
        self._seed_teacher(
            'GW Tour Suspended', work_email='gw.tour.suspended@elpuig.xeill.net',
            google_ws_suspended=True)
        # Grace period (#388): archived, with the suspension already scheduled - the
        # state the form's banner and "Cancel scheduled deactivation" button react to.
        scheduled = self._seed_teacher(
            'GW Tour Scheduled', work_email='gw.tour.scheduled@elpuig.xeill.net')
        scheduled.write({'active': False})
        scheduled.google_ws_deactivation_date = date.today() + relativedelta(days=30)
        self.env['hr.employee'].create({
            'name': '0000 GW Tour Pending Identification',
            'employee_type': 'teacher',
            'schedule_import_code': 'X_TOUR',
        })

        employee_cls = type(self.env['hr.employee'])
        # The Google user id is patched for the whole test: seeding the two 'active'
        # teachers and pressing the repair button all go through the Directory API,
        # and a test must never reach the centre's real Google Workspace.
        with patch.object(employee_cls, '_gw_google_user_id',
                          return_value='103000000000000000020'):
            active.action_create_ems_user()
        # ... whereas this one is exactly the broken state the repair button exists for:
        # an EMS user that lost its OAuth data, so the tour can press the button itself.
        with patch.object(employee_cls, '_gw_google_user_id', return_value=False):
            relink.action_create_ems_user()
        self.assertTrue(active.user_id.oauth_uid)
        self.assertFalse(relink.user_id.oauth_uid)

        with patch.object(employee_cls, '_gw_google_user_id',
                          return_value='103000000000000000021'):
            self.start_tour("/odoo", "ems_employee_google_workspace_state", login="admin")

        self.assertEqual(relink.user_id.oauth_uid, '103000000000000000021')
