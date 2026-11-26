from datetime import timedelta

from odoo.tests import tagged, HttpCase

from .common import create_role_employee, create_role_user, shift_ems_clock


@tagged('post_install', '-at_install')
class TestSpaceReservationTour(HttpCase):

    def test_space_reservation_tour(self):
        # The least-privileged role that reserves spaces: a teacher (docs/en/developers/facilities/space_reservation.md).
        teacher = create_role_user(self, 'teacher', 'test_teacher_space_reservation_tour')
        create_role_employee(self, teacher)
        busy = self.env['ems.space'].create({'code': 'TSRT-A', 'name': 'Tour Busy Space'})
        self.env['ems.space'].create({'code': 'TSRT-B', 'name': 'Tour Free Space'})
        # 08:00 company time, so the wizard's default (that day at 10:00, one hour) is still ahead
        # whenever the suite runs; the busy space is held across that hour.
        now = shift_ems_clock(self, hour=8.0)
        self.env['ems.space_reservation'].create({
            'space_id': busy.id, 'user_id': teacher.id, 'reason': 'Tour held', 'duration': 3.0,
            'start_datetime': self.env['ems.datetime_utils'].local_datetime_to_utc(now + timedelta(hours=1.5)).replace(tzinfo=None),
        })
        self.start_tour("/odoo", "ems_space_reservation", login="test_teacher_space_reservation_tour")
