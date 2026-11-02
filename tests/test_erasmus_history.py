from odoo.tests.common import tagged

from .common import create_role_user
from .test_erasmus_group_mobility import ErasmusGroupMobilityCase
from .test_erasmus_mobility import ErasmusMobilityCase


def history(partner):
    """The person's Erasmus+ history as the SQL view reads it, after flushing the ORM's writes."""
    partner.env.flush_all()
    partner.env.invalidate_all()
    return partner.erasmus_history_ids


@tagged('post_install', '-at_install')
class TestErasmusHistoryIndividual(ErasmusMobilityCase):
    """The issue-#682 review: the individual mobilities in the person's Erasmus+ history."""

    def test_accepted_place_is_a_planned_participation(self):
        first, second = self._accepted()
        lines = history(first.partner_id)
        self.assertEqual(len(lines), 1)
        self.assertEqual((lines.kind, lines.role, lines.name, lines.state),
                         ('individual', 'student', self.call.name, 'planned'))
        self.assertEqual(first.application_id.erasmus_history_ids, lines,
                         "The application shows it, for the team checking First mobility.")
        second.action_renounce()
        self.assertFalse(history(second.partner_id), "A cancelled mobility is not a participation.")

    def test_any_teacher_reads_it_without_the_erasmus_app(self):
        first, _second = self._accepted()
        teacher = create_role_user(self, 'teacher', 'test_erasmus_history_teacher')
        history(first.partner_id)
        lines = first.partner_id.with_user(teacher).erasmus_history_ids
        self.assertEqual(lines.mapped('name'), [self.call.name])


@tagged('post_install', '-at_install')
class TestErasmusHistoryGroup(ErasmusGroupMobilityCase):
    """The issue-#682 review: the group mobilities in the person's Erasmus+ history."""

    def test_group_participants_until_the_mobility_is_cancelled(self):
        self._approved()
        student = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'student')[:1]
        leader = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'leader')
        lines = history(student.partner_id)
        self.assertEqual((lines.kind, lines.role, lines.name, lines.project, lines.state),
                         ('group', 'student', self.mobility.name, 'ka121_vet', 'planned'))
        self.assertEqual(history(leader.partner_id).role, 'leader')
        self.mobility.cancel_reason = "Test: the trip is called off."
        self.mobility.with_user(self.coordinator_user).action_cancel()
        self.assertFalse(history(student.partner_id))
