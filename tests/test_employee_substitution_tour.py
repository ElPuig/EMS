from odoo.tests.common import HttpCase, tagged

from .common import create_role_employee, create_role_user, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestEmployeeSubstitutionTour(HttpCase):
    """Issue #748, browser side: the Head of Studies declares a substitution from the substitute's
    form (see static/tests/tours/employee_substitution_tour.js)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Saving a teacher may post to the chatter - see CLAUDE.md's "Email safety in tests".
        mock_outgoing_email(cls)
        cls.hos_user = create_role_user(cls, 'head_of_studies', 'test_748_hos_tour', name='TSUBT Head of Studies')
        create_role_employee(cls, cls.hos_user)
        # "0000 " prefix: first page of the Teachers list among the dev DB's own teachers.
        cls.titular = cls.env['hr.employee'].create({'name': '0000 TSUBT Titular', 'employee_type': 'teacher'})
        cls.substitute = cls.env['hr.employee'].create({'name': '0000 TSUBT Substitute', 'employee_type': 'teacher'})
        cls.titular.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning',
            'non_teaching': cls.env.ref('ems.non_teaching_g').id, 'name': 'Guard',
        }])

    def test_employee_substitution_tour(self):
        self.start_tour("/odoo", "ems_employee_substitution", login='test_748_hos_tour')
        self.assertEqual(self.substitute.substitute_of_id, self.titular)
        self.assertTrue(self.substitute.resource_calendar_id.attendance_ids.filtered(
            lambda block: block.non_teaching == self.env.ref('ems.non_teaching_g')))
