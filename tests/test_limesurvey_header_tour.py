from odoo.tests.common import HttpCase, tagged

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestLimesurveyHeaderTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Created as the real 'admin' login (not the default superuser env) so it actually
        # shows up under the Surveys list's "Show only mine" default filter (search_default_
        # only_mine=1 on action_limesurvey_header_tree) - a record created via the superuser
        # env has create_uid=SUPERUSER_ID, which never matches admin's own uid, and the tour
        # (which logs in as admin) would otherwise find an empty list.
        cls.header = cls.env['ems.limesurvey_header'].with_user(cls.env.ref('base.user_admin')).create({
            'name': 'LimeSurvey Header Delete Tour', 'title': 'LimeSurvey Header Delete Tour',
            'description': 'LimeSurvey Header Delete Tour', 'target': 'students',
            'tsv_raw_text': 'placeholder', 'state': 'closed',
        })

    def test_limesurvey_header_delete_closed_confirmed_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_limesurvey_header_delete_closed_confirmed", login="admin")
        self.assertFalse(self.header.exists())
