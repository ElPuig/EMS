from odoo.tests.common import HttpCase, tagged

from .test_erasmus_staff import STAFF_PLAN, ErasmusStaffCase


@tagged('post_install', '-at_install')
class TestErasmusActionsTeacherTour(HttpCase, ErasmusStaffCase):
    """Issue #786 - the teacher's application keeps its next step in view, the rest in Actions."""

    def test_teacher_next_step_tour(self):
        Application = self.env['ems.erasmus.application']
        empty = Application._ems_portal_get_or_create(self.staff_call, self.staff_users[0].partner_id)
        answered = Application._ems_portal_get_or_create(self.staff_call, self.staff_users[1].partner_id)
        answered._ems_portal_save({'declared_never_staff_mobility': True, **STAFF_PLAN}, {})
        for application, user, tour in ((empty, self.staff_users[0], 'fill'), (answered, self.staff_users[1], 'submit')):
            with self.subTest(tour=tour):
                self.start_tour(f'/odoo/action-ems.action_erasmus_my_applications/{application.id}',
                                f'ems_erasmus_actions_teacher_{tour}', login=user.login)
