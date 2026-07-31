from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestLimesurveyHeaderTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.header = cls.env['ems.limesurvey_header'].create({
            'name': 'LimeSurvey Header Delete Tour', 'title': 'LimeSurvey Header Delete Tour',
            'description': 'LimeSurvey Header Delete Tour', 'target': 'students',
            'tsv_raw_text': 'placeholder', 'state': 'closed',
        })

    def test_limesurvey_header_delete_closed_confirmed_tour(self):
        self.start_tour("/odoo", "ems_limesurvey_header_delete_closed_confirmed", login="admin")
        self.assertFalse(self.header.exists())
