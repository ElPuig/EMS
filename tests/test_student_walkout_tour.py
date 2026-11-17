# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email
from .test_student_walkout import create_walkout_fixtures, end_phase, open_walkout


@tagged('post_install', '-at_install')
class TestStudentWalkoutTour(HttpCase):
    """Issue #800: the group's tutor (the least privileged role that aborts a walkout call) aborts a
    call being voted with a reason; the Head of Studies (the one who validates) validates a closed
    one. List and form."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_walkout_fixtures(cls, 'WLT')
        cls.head_of_studies.lang = 'en_US'
        cls.tutor.lang = 'en_US'
        cls.walkout = open_walkout(cls)
        for student in (cls.delegate, cls.subdelegate):
            cls.walkout._ems_portal_vote(student, 'yes')
        cls.walkout._ems_portal_join(cls.delegate, True)
        cls.walkout._ems_portal_join(cls.classmate, True)  # a minor: its family must ratify it
        end_phase(cls.walkout)  # the joining ended: closed
        cls.voting = open_walkout(cls, days=8)

    def test_tutor_aborts(self):
        self.start_tour("/odoo", "ems_student_walkout_abort", login=self.tutor.login)
        self.assertEqual((self.voting.state, self.voting.rejected_by_id), ('rejected', self.tutor))
        self.assertEqual(self.walkout.state, 'closed')

    def test_tutor_extends_the_joining(self):
        """Issue #838: a closed call reopens for one phase more."""
        self.start_tour("/odoo", "ems_student_walkout_extend", login=self.tutor.login)
        self.assertEqual((self.walkout.state, self.walkout.delegate_extended), ('joining', False))

    def test_tutor_ratifies_by_hand(self):
        """Issue #840: the family of a minor cannot use the portal; the tutor marks its ratification."""
        self.start_tour("/odoo", "ems_student_walkout_ratify_by_hand", login=self.tutor.login)
        line = self.walkout.line_ids.filtered(lambda line: line.student_id == self.classmate)
        self.assertEqual((line.ratification, line.ratified_by_id, line.ratified_manually),
                         ('ratified', self.tutor.partner_id, True))

    def test_head_of_studies_validates(self):
        self.start_tour("/odoo", "ems_student_walkout_validate", login=self.head_of_studies.login)
        self.assertEqual(self.walkout.state, 'justified')
        self.assertEqual(self.walkout.justification_id.student_ids, self.delegate)

    def test_settings_admin_sets_the_levels(self):
        settings_admin = create_role_user(self, 'settings_admin', 'test_walkout_tour_settings_admin')
        self.start_tour("/odoo", "ems_student_walkout_levels", login=settings_admin.login)
        self.assertEqual(self.level.walkout_course_from, 2)

    def test_settings_admin_sees_the_calendar_example(self):
        """Issue #828: the count's controls and their example, in Settings."""
        settings_admin = create_role_user(self, 'settings_admin', 'test_walkout_tour_calendar_admin')
        self.start_tour("/odoo", "ems_student_walkout_calendar", login=settings_admin.login)
