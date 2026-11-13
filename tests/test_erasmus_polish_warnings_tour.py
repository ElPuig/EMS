from odoo.tests import HttpCase, tagged

from .test_erasmus_mobility import ErasmusStaffMobilityCase


@tagged('post_install', '-at_install')
class TestErasmusWarningsTour(HttpCase, ErasmusStaffMobilityCase):
    """Issue #787 - the teacher's and the team's mobility say what is missing."""

    def _mobility_with_a_step(self):
        mobility = self._accepted_staff()
        if not mobility.task_ids:
            self.env['ems.erasmus.call.task'].create({'call_id': self.staff_call.id, 'name': 'Test tour step'})
            mobility.action_sync_requirements()
        return mobility

    def test_teacher_steps_tour(self):
        mobility = self._mobility_with_a_step()
        self.start_tour(f'/odoo/action-ems.action_erasmus_my_mobilities/{mobility.id}',
                        'ems_erasmus_warnings_teacher_steps', login='test_erasmus_staff_1')
        self.assertTrue(mobility.task_ids.filtered('done'))

    def test_team_step_tour(self):
        mobility = self._accepted_staff()
        self.start_tour(f'/odoo/action-ems.action_erasmus_mobility/{mobility.id}', 'ems_erasmus_warnings_team_step',
                        login='test_erasmus_team')
