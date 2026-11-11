import importlib.util
from pathlib import Path

from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .test_erasmus_group_mobility import ErasmusGroupMobilityCase

MIGRATION = Path(__file__).parent.parent / 'migrations' / '18.0.0.48.0' / 'post-migrate.py'


@tagged('post_install', '-at_install')
class TestErasmusGroupRankingScore(ErasmusGroupMobilityCase):
    """Issue #773 (art. 16 of the students' rules): a group mobility ranks by a score, the record
    average +1 for fewer opportunities accredited, -0.5 per conduct warning this course (at most
    -1.5); ties by the accreditation, then the coordinator's draw."""

    def _scored(self):
        """Four students: 7.0 with fewer opportunities accredited (8.0), 8.5 with two warnings
        (7.5), 9.5 with five (capped: 8.0) and 7.8 with nothing (7.8)."""
        registrations = self._enrol(self.students[:1], fewer_opportunities=True) | self._enrol(self.students[1:4])
        self._strikes(self.students[1], 2)
        self._strikes(self.students[2], 5)
        self._close({self.students[0]: 7.0, self.students[1]: 8.5, self.students[2]: 9.5, self.students[3]: 7.8})
        registrations[0].with_user(self.technician_user).fewer_opportunities_check = 'yes'
        return registrations

    def test_the_score_adds_fewer_opportunities_and_takes_off_the_warnings(self):
        registrations = self._scored()
        self.assertEqual(registrations.mapped('score'), [8.0, 7.5, 8.0, 7.8])
        self.assertEqual(registrations.mapped('ranking_average'), [7.0, 8.5, 9.5, 7.8], "The average stays as it is.")

    def test_ranked_by_the_score_and_a_tie_by_the_accreditation(self):
        registrations = self._scored()
        # 8.0 twice: the one with fewer opportunities accredited goes first, no draw needed.
        self.assertEqual(registrations.mapped('rank'), [1, 4, 2, 3])
        self.assertFalse(self.mobility.needs_draw)

    def test_the_same_score_and_accreditation_is_a_tie_for_the_draw(self):
        registrations = self._enrol(self.students[:2])
        self._strikes(self.students[0], 1)
        self._close({self.students[0]: 8.0, self.students[1]: 7.5})
        self.assertEqual(registrations.mapped('score'), [7.5, 7.5])
        self.assertEqual(registrations.mapped('needs_draw'), [True, True])
        self.mobility.with_user(self.coordinator_user).action_draw_ties()
        self.assertEqual(self.mobility.draw_ids.score_total, 7.5, "The draw keeps the score they were tied on.")
        self.assertEqual(sorted(registrations.mapped('rank')), [1, 2])

    def test_an_average_entered_by_hand_counts_in_the_score(self):
        registrations = self._scored()
        registrations[3].with_user(self.technician_user).write(
            {'grade_manual': True, 'grade_average_manual': 9.0, 'grade_manual_reason': 'Academic record'})
        self.assertEqual(registrations[3].score, 9.0)
        self.assertEqual(registrations[3].rank, 1)

    def test_the_leader_sees_the_score_but_never_its_breakdown(self):
        registrations = self._scored()
        self.assertEqual(registrations[0].with_user(self.leader_user).read(['score'])[0]['score'], 8.0)
        for field in ('strike_count', 'fewer_opportunities_check'):
            with self.assertRaises(AccessError):
                registrations[0].with_user(self.leader_user).read([field])

    def test_the_published_list_shows_the_score(self):
        registrations = self._scored()
        self.mobility.with_user(self.leader_user).action_submit_proposal()
        self._publish_provisional()
        lines = self.mobility.resolution_ids.line_ids
        self.assertEqual({line.group_registration_id: line.score_total for line in lines},
                         dict(zip(registrations, registrations.mapped('score'))))

    def test_the_default_criteria_explain_the_score(self):
        self.assertIn("score", self.mobility.with_context(lang='en_US').tie_break)

    def test_a_mobility_ranked_before_keeps_the_average(self):
        """The upgrade (migration of issue #773): a mobility already past the enrolment is not
        ranked again by the score."""
        registrations = self._scored()
        spec = importlib.util.spec_from_file_location('ems_migration_773', MIGRATION)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self.env.flush_all()
        migration._keep_group_rankings_by_average(self.env.cr)
        self.mobility.invalidate_recordset(['rank_by_score'])
        self.assertFalse(self.mobility.rank_by_score)
        self.mobility._ems_rank()
        self.assertEqual(registrations.mapped('rank'), [4, 2, 1, 3], "By the average, as before.")
