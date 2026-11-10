# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_student_walkout import create_walkout_fixtures, move_walkout, open_walkout


@tagged('post_install', '-at_install')
class TestStudentWalkoutTour(HttpCase):
    """Issue #800: the Head of Studies (the least privileged role that decides on and justifies a
    walkout) accepts a call, rejects another with a reason and justifies a closed vote, list and form."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_walkout_fixtures(cls, 'WLT')
        cls.head_of_studies.lang = 'en_US'
        cls.walkout = open_walkout(cls)
        for student in (cls.delegate, cls.subdelegate, cls.classmate):
            cls.walkout._ems_portal_vote(student, 'yes')
        cls.walkout._ems_portal_join(cls.delegate, True)
        move_walkout(cls.walkout, 0)  # the joining day ended: closed
        cls.pending = open_walkout(cls, days=5, accept=False) | open_walkout(cls, days=6, accept=False)

    def test_head_of_studies_decides_and_justifies(self):
        self.start_tour("/odoo", "ems_student_walkout", login=self.head_of_studies.login)
        self.assertEqual(sorted(self.pending.mapped('state')), ['rejected', 'voting'])
        self.assertEqual(self.walkout.state, 'justified')
        self.assertEqual(self.walkout.justification_id.student_ids, self.delegate)
