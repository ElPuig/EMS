from datetime import timedelta

from odoo import fields
from odoo.tests import tagged, HttpCase

from .common import create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestSpaceReservationTour(HttpCase):

    def test_space_reservation_tour(self):
        # The least-privileged role that reserves spaces: a teacher (docs/en/developers/facilities/space_reservation.md).
        teacher = create_role_user(self, 'teacher', 'test_teacher_space_reservation_tour')
        create_role_employee(self, teacher)
        busy = self.env['ems.space'].create({'code': 'TSRT-A', 'name': 'Tour Busy Space'})
        self.env['ems.space'].create({'code': 'TSRT-B', 'name': 'Tour Free Space'})
        # Holds the busy space around the moment the form opens with (now, one hour).
        self.env['ems.space_reservation'].create({
            'space_id': busy.id, 'user_id': teacher.id, 'reason': 'Tour held',
            'start_datetime': fields.Datetime.now() - timedelta(hours=1), 'duration': 4.0,
        })
        self.start_tour("/odoo", "ems_space_reservation", login="test_teacher_space_reservation_tour")
