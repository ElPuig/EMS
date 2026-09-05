from odoo.tests import tagged, HttpCase

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestStudentDocumentTour(HttpCase):

    def test_student_document_review_and_embed_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # "0000 " prefix: res.partner's _order is "name", so this seeded student sorts
        # first on the list's very first page among the ~1000+ real students already in
        # this DB (see test_withdrawal_tour.py for the same pattern).
        student = self.env['res.partner'].create({
            'name': '0000 Tour Doc Student', 'contact_type': 'student',
        })
        self.env['ems.student.document'].create({
            'partner_id': student.id, 'doc_type': 'dni',
        })
        self.env['ems.student.document'].create({
            'partner_id': student.id, 'doc_type': 'passport',
        })
        # To observe these tours in a real browser during development:
        #   self.start_tour("/odoo", "ems_student_document_review", login="admin", watch=True)
        self.start_tour("/odoo", "ems_student_document_review", login="admin", step_delay=300)
        self.start_tour("/odoo", "ems_student_document_embed_view", login="admin", step_delay=300)
