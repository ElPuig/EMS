# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_student_walkout import create_walkout_fixtures, end_phase, open_walkout


@tagged('post_install', '-at_install')
class TestStudentWalkoutTour(HttpCase):
    """Issue #800: the Head of Studies (the least privileged role that rejects and justifies a
    walkout) rejects a call being voted with a reason and justifies a closed vote, list and form."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_walkout_fixtures(cls, 'WLT')
        cls.head_of_studies.lang = 'en_US'
        cls.walkout = open_walkout(cls)
        for student in (cls.delegate, cls.subdelegate):
            cls.walkout._ems_portal_vote(student, 'yes')
        cls.walkout._ems_portal_join(cls.delegate, True)
        end_phase(cls.walkout)  # the joining ended: closed
        cls.voting = open_walkout(cls, days=8)

    def test_head_of_studies_rejects_and_justifies(self):
        self.start_tour("/odoo", "ems_student_walkout", login=self.head_of_studies.login)
        self.assertEqual(self.voting.state, 'rejected')
        self.assertEqual(self.walkout.state, 'justified')
        self.assertEqual(self.walkout.justification_id.student_ids, self.delegate)
