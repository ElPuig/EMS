from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged

from .common import create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestEmployeePresenceTour(HttpCase):
    """The presence dot looks the same on the Teachers kanban and on the form, for a tutor
    (issue #575) - see ems_employee_base's hr_presence_state."""

    def test_employee_presence_tour(self):
        colleague = create_role_employee(
            self, create_role_user(self, 'teacher', 'presence_tour_colleague'), name='0000 Presence Colleague')
        self.env['hr.attendance'].create({
            'employee_id': colleague.id, 'check_in': fields.Datetime.now() - timedelta(hours=1)})
        create_role_user(self, 'tutor', 'presence_tour_tutor')

        self.start_tour("/odoo", "ems_employee_presence", login="presence_tour_tutor")
