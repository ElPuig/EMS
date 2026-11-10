# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_student_walkout import create_walkout_fixtures, open_walkout


@tagged('post_install', '-at_install')
class TestStudentWalkoutTour(HttpCase):
    """Issue #800: the Head of Studies (the least privileged role that justifies a walkout) reads a
    closed vote, list and form, and generates the justification."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.env.company.walkout_notice_days = 2
        create_walkout_fixtures(cls, 'WLT')
        cls.head_of_studies.lang = 'en_US'
        cls.walkout = open_walkout(cls)
        cls.walkout._ems_portal_vote(cls.delegate, 'yes', True)
        cls.walkout._ems_portal_close(cls.delegate)

    def test_head_of_studies_justifies_the_walkout(self):
        self.start_tour("/odoo", "ems_student_walkout", login=self.head_of_studies.login)
        self.assertEqual(self.walkout.state, 'justified')
        self.assertEqual(self.walkout.justification_id.student_ids, self.delegate)
