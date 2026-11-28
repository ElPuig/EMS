from odoo.tests.common import HttpCase, tagged

from .test_grade_claim import build_claim_fixture


@tagged('post_install', '-at_install')
class TestGradeClaimTour(HttpCase):
    """Issue #879: filing a claim from the portal, and answering it in the backend as the teacher."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        build_claim_fixture(cls)
        cls.grade_session.state = 'published'

    def test_grade_claim_portal_tour(self):
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Claim Student', 'login': 'test_claim_student', 'password': 'test_claim_student',
            'partner_id': self.student.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.start_tour("/my/calificaciones", "ems_grade_claim_portal", login="test_claim_student")
        claim = self.env['ems.grade_claim'].search([('student_id', '=', self.student.id)])
        self.assertEqual((claim.kind, claim.outcome_line_id, claim.state), ('outcome', self.line1, 'teacher'))

    def test_grade_claim_answer_tour(self):
        claim = self.env['ems.grade_claim'].ems_file_from_portal(
            self.student, self.student, f'outcome-{self.line1.id}', 'RA1 left out my second project')
        self.start_tour("/odoo", "ems_grade_claim_answer", login="test_claim_teacher")
        self.assertEqual((claim.state, self.line1.score), ('accepted', 6))
