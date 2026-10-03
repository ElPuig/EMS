from datetime import date

from odoo.tests import tagged, HttpCase

from .common import create_role_user, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestStudyTour(HttpCase):

    def test_study_crud_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_study_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_study_crud", login="admin")

    def test_study_teacher_attachment_tour(self):
        # A teacher only reads studies: the files attached to one must show for them too
        # (issue #553).
        teacher_user = create_role_user(self, 'teacher', 'tour_teacher_study_attachment')
        self.env['ems.study'].create({
            'code': 'TOUR_STUDY_ATT', 'acronym': 'TSAT', 'name': 'Study Attachment Tour Study',
            'date': date(2024, 9, 1),
            'attachment_ids': [(0, 0, {
                'name': 'Tour curriculum.pdf', 'raw': b'curriculum', 'res_model': 'ems.study',
            })],
        })
        self.start_tour("/odoo", "ems_study_teacher_attachment", login=teacher_user.login)
