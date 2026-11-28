from odoo.tests.common import HttpCase, tagged

from .test_grade_claim import build_claim_fixture


@tagged('post_install', '-at_install')
class TestMinuteBoardTour(HttpCase):
    """Issue #880: the tutor fills in the evaluation board minute EMS created for the group."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        build_claim_fixture(cls)

    def test_minute_board_tour(self):
        self.grade_session.with_user(self.head_of_studies).write({'state': 'board'})
        minute = self.env['ems.minute'].search([('group_id', '=', self.group.id), ('grade_round', '=', '1')])
        self.start_tour(f"/odoo/action-ems.action_minute/{minute.id}", "ems_minute_board", login="test_claim_tutor")
        self.assertEqual(minute.board_student_ids[:1].family_comment, 'Keep working on RA2.')
