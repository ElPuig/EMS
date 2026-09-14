from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, create_role_employee, create_role_user, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestAuthorizationSendWizardTour(HttpCase):
    """The backend screens of issue #443: the authorizations follow-up list (both of its
    declared view modes) and the assistant that sends new ones during the course.

    Driven by a secretary, not by admin: that is who does this, and it is the only way the
    tour proves the menus, the action and the record rules line up for them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_auth_tour',
                                         name='Test Secretary (Auth Tour)',
                                         email='secretary.authtour@example.com')
        create_role_employee(cls, cls.secretary, employee_type='asp')

        Course = cls.env['ems.course']
        cls.course = Course.search([('is_current', '=', True)], limit=1) \
            or Course.create({'start': 2096, 'end': 2097, 'is_current': True})
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TAWT', study={
            'code': 'TAWT01', 'acronym': 'TAWTS', 'name': 'Tour Send Wizard Study',
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Tour Send Wizard Student', 'contact_type': 'student',
            'main_group_id': cls.group.id, 'email': 'tour.send.wizard@example.com',
            'birth_date': date.today() - relativedelta(years=19),
        })
        cls.env['sale.order'].create({
            'partner_id': cls.student.id, 'ems_study_id': cls.study.id,
            'ems_course_id': cls.course.id,
        })
        cls.template = cls.env['ems.authorization.template'].create({
            'name': 'Tour Send Wizard Authorization', 'legal_text': '<p>Mid-year text</p>',
            'apply_on_enrollment': False, 'sendable_during_course': True,
        })
        # One authorization already on file, so the follow-up list has something to open on
        # a clean database too. A template of its own, so the send tour below still has
        # something left to send to this student.
        cls.existing_template = cls.env['ems.authorization.template'].create({
            'name': 'Tour Existing Authorization', 'legal_text': '<p>Already sent</p>',
            'apply_on_enrollment': False, 'sendable_during_course': True,
        })
        cls.existing_authorization = cls.env['ems.authorization'].create({
            'partner_id': cls.student.id, 'course_id': cls.course.id,
            'template_id': cls.existing_template.id,
        })

    def _tutor_fixtures(self):
        """A tutor of the tour group, plus a student in a group they do not tutor who also
        holds an authorization - so the follow-up can prove it only shows the tutor's own."""
        tutor = create_role_user(self, 'tutor', 'test_tutor_auth_tour',
                                 name='Test Tutor (Auth Tour)', email='tutor.authtour@example.com')
        self.group.tutor_id = create_role_employee(self, tutor)
        _level, _study, other_group = create_level_study_group(self, 'TAWO', study={
            'code': 'TAWO01', 'acronym': 'TAWOS', 'name': 'Tour Other Study',
        })
        other = self.env['res.partner'].create({
            'name': 'Tour Other Student', 'contact_type': 'student',
            'main_group_id': other_group.id, 'email': 'tour.other@example.com',
            'birth_date': date.today() - relativedelta(years=19),
        })
        self.env['ems.authorization'].create({
            'partner_id': other.id, 'course_id': self.course.id,
            'template_id': self.existing_template.id,
        })
        return tutor

    def test_tutor_follow_up_tour(self):
        """Issue #443 testing: tutors follow up their own students' answers, nobody else's."""
        self._tutor_fixtures()
        self.start_tour("/odoo", "ems_authorization_tutor_follow_up", login="test_tutor_auth_tour")

    def test_tutor_send_wizard_tour(self):
        """Issue #443 testing: tutors send forms from the catalogue to their own groups."""
        self._tutor_fixtures()
        self.start_tour("/odoo", "ems_authorization_tutor_send", login="test_tutor_auth_tour")
        authorization = self.env['ems.authorization'].search([
            ('partner_id', '=', self.student.id), ('template_id', '=', self.template.id)])
        self.assertEqual(len(authorization), 1)
        self.assertFalse(authorization.enrollment_id)

    def test_authorization_list_tour(self):
        self.start_tour("/odoo", "ems_authorization_list",
                        login="test_secretary_auth_tour")

    def test_authorization_send_wizard_tour(self):
        self.start_tour("/odoo", "ems_authorization_send_wizard",
                        login="test_secretary_auth_tour")
        authorization = self.env['ems.authorization'].search([
            ('partner_id', '=', self.student.id),
            ('template_id', '=', self.template.id),
        ])
        self.assertEqual(len(authorization), 1)
        self.assertEqual(authorization.status, 'pending')
        self.assertFalse(authorization.enrollment_id)
        self.assertEqual(authorization.course_id, self.course)
