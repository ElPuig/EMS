from odoo.tests.common import HttpCase, tagged

from .common import (create_level_study_group, create_role_employee, create_role_user,
                     mock_outgoing_email, next_student_id)


@tagged('post_install', '-at_install')
class TestEnrollmentCloseWizardTour(HttpCase):
    """Issue #643: the close-unconfirmed-enrollments wizard from the Matrícules Action menu and
    from the Pre-inscripció header, driven by a secretary - who closes enrollments - rather than
    by admin, so the menus, the bindings and the access line up for them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_close_tour',
                                         name='Test Secretary (Close Tour)',
                                         email='secretary.closetour@example.com')
        create_role_employee(cls, cls.secretary, employee_type='asp')
        cls.course = cls.env['ems.course'].search([('is_current', '=', True)], limit=1) \
            or cls.env['ems.course'].create({'start': 2096, 'end': 2097, 'is_current': True})
        _level, cls.study, _group = create_level_study_group(cls, 'ECWT', study={
            'code': 'ECWT01', 'acronym': 'ECWTS', 'name': 'Close Tour Study',
        })

    def _applicant(self, name):
        return self.env['res.partner'].create({
            'name': name, 'contact_type': 'applicant', 'student_id': next_student_id(),
            'study_id': self.study.id,
        })

    def _offer(self, applicant):
        order = self.env['sale.order'].create({
            'partner_id': applicant.id, 'ems_course_id': self.course.id,
            'ems_study_id': self.study.id,
        })
        order.write({'state': 'sent'})
        return order

    def test_close_from_enrollments(self):
        applicant = self._applicant('Close Tour Applicant')
        order = self._offer(applicant)
        self.start_tour("/odoo", "ems_enrollment_close_from_enrollments", login=self.secretary.login)
        self.assertFalse(applicant.exists())
        self.assertFalse(order.exists())

    def test_close_from_applicants(self):
        never = self._applicant('Close Tour Never Offered')
        offered = self._applicant('Close Tour Offered')
        self._offer(offered)
        self.start_tour("/odoo", "ems_enrollment_close_from_applicants", login=self.secretary.login)
        self.assertFalse(never.exists())
        self.assertTrue(offered.exists())
