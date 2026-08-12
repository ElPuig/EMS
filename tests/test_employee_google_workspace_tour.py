from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestEmployeeGoogleWorkspaceTour(HttpCase):

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
        # google_ws_state (models/employees/google_workspace_integration.py) drives
        # which header button(s) show — a TransactionCase can assert the compute is
        # right, but only a real browser render catches an OWL/view-arch mistake in
        # the invisible expressions (e.g. two buttons showing at once, the original bug).
        # To watch this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_employee_google_workspace_state", login="admin", watch=True)
        self._seed_teacher('GW Tour None')
        self._seed_teacher('GW Tour Pending', work_email='gw.tour.pending@elpuig.xeill.net')
        active = self._seed_teacher('GW Tour Active', work_email='gw.tour.active@elpuig.xeill.net')
        active.action_create_ems_user()
        self._seed_teacher(
            'GW Tour Suspended', work_email='gw.tour.suspended@elpuig.xeill.net',
            google_ws_suspended=True)

        self.start_tour("/odoo", "ems_employee_google_workspace_state", login="admin")
