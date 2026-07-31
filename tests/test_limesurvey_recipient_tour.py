from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestLimesurveyRecipientTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # state='computed' set directly (not via action_compute) - only the "Recipients" tab's
        # own rendering/interaction is under test here, already-covered elsewhere is the
        # state-machine's business logic for how a header actually reaches this state.
        cls.header = cls.env['ems.limesurvey_header'].create({
            'name': 'LimeSurvey Recipient Tour Header', 'title': 'LimeSurvey Recipient Tour Header',
            'description': 'LimeSurvey Recipient Tour Header', 'target': 'students',
            'tsv_raw_text': 'placeholder', 'state': 'computed',
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'LimeSurvey Recipient Tour Student', 'contact_type': 'student',
        })

    def test_limesurvey_recipient_add_student_tour(self):
        self.start_tour("/odoo", "ems_limesurvey_recipient_add_student", login="admin")

        recipient = self.env['ems.limesurvey_recipient'].search([
            ('limesurvey_header_id', '=', self.header.id), ('student_id', '=', self.student.id),
        ])
        self.assertEqual(len(recipient), 1)
