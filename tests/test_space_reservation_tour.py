from datetime import timedelta

from odoo.tests import tagged, HttpCase

from .common import create_role_employee, create_role_user, shift_ems_clock


@tagged('post_install', '-at_install')
class TestSpaceReservationTour(HttpCase):

    def test_space_reservation_tour(self):
        # The least-privileged role that reserves spaces: a teacher (docs/en/developers/facilities/space_reservation.md).
        teacher = create_role_user(self, 'teacher', 'test_teacher_space_reservation_tour')
        create_role_employee(self, teacher)
        busy = self.env['ems.space'].create({'code': 'TSRT-A', 'name': '000 Tour Busy Space'})
        self.env['ems.space'].create({'code': 'TSRT-B', 'name': '000 Tour Free Space'})
        # The first tour reserves the free space: the third one chooses this one.
        self.env['ems.space'].create({'code': 'TSRT-C', 'name': '000 Tour Spare Space'})
        # 08:00 company time, so the wizard's default (that day at 10:00, one hour) is still ahead
        # whenever the suite runs; the busy space is held across that hour.
        now = shift_ems_clock(self, hour=8.0)
        self.env['ems.space_reservation'].create({
            'space_id': busy.id, 'user_id': teacher.id, 'reason': 'Tour held', 'duration': 3.0,
            'start_datetime': self.env['ems.datetime_utils'].local_datetime_to_utc(now + timedelta(hours=1.5)).replace(tzinfo=None),
        })
        self.start_tour("/odoo", "ems_space_reservation", login="test_teacher_space_reservation_tour")
        self.start_tour("/odoo", "ems_space_reservation_by_space", login="test_teacher_space_reservation_tour")
        self.start_tour("/odoo", "ems_space_reservation_search_again", login="test_teacher_space_reservation_tour")
        # Someone else's reservation opens read only (the teacher may not change it).
        colleague = create_role_user(self, 'teacher', 'test_colleague_space_reservation_tour', name='Tour Colleague')
        others = self.env['ems.space'].create({'code': 'TSRT-D', 'name': '000 Tour Others Space'})
        self.env['ems.space_reservation'].create({
            'space_id': others.id, 'user_id': colleague.id, 'reason': 'Tour colleague reason', 'duration': 1.0,
            'start_datetime': self.env['ems.datetime_utils'].local_datetime_to_utc(now + timedelta(hours=8)).replace(tzinfo=None),
        })
        self.start_tour("/odoo", "ems_space_reservation_others_read_only", login="test_teacher_space_reservation_tour")

    def test_space_reservation_now_line_tour(self):
        teacher = create_role_user(self, 'teacher', 'test_teacher_space_reservation_now')
        create_role_employee(self, teacher)
        self.env['ems.space'].create({'code': 'TSRT-N', 'name': '000 Tour Free Space'})
        # 12:00 company time of a school day, so today's column is on the grid with the line in the
        # middle of it (the clock keeps running from there).
        shift_ems_clock(self, hour=12.0, weekdays=(0, 1, 2, 3, 4))
        # The tour ends on the wizard with a time chosen and nothing reserved, on purpose.
        self.allow_end_on_form = True
        self.start_tour("/odoo", "ems_space_reservation_now_line", login="test_teacher_space_reservation_now")
