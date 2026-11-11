from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email
from .test_erasmus import create_erasmus_fixtures


@tagged('post_install', '-at_install')
class TestErasmusDatesNumbersTour(HttpCase):
    """Issue #778 - dates without a time and blank zeros, each screen driven by the least privileged
    role that uses it: the Mobility technician, and the coordinator for the earlier courses, which
    only the coordination can type in."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_erasmus_fixtures(cls)
        cls.technician = create_role_user(cls, 'erasmus', 'test_dates_technician')

    def test_call_dates_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_call', 'ems_erasmus_call_dates',
                        login=self.technician.login)

    def test_offer_dates_tour(self):
        application = self.env['ems.erasmus.application'].create({
            'call_id': self.call.id, 'partner_id': self.student.id, 'modality_id': self.call.modality_ids.id})
        self.env['ems.erasmus.offer'].create({'application_id': application.id,
                                              'deadline': fields.Datetime.now() + timedelta(days=3)})
        self.start_tour('/odoo/action-ems.action_erasmus_offer', 'ems_erasmus_offer_dates',
                        login=self.technician.login)

    def test_support_rate_blank_zero_tour(self):
        rate = self.env['ems.erasmus.support.rate'].create({'call_year': 2098, 'kind': 'ka121_vet', 'amount': 350})
        self.start_tour('/odoo/action-ems.action_erasmus_support_rate', 'ems_erasmus_rate_blank_zero',
                        login=self.technician.login)
        self.assertEqual((rate.band_to, rate.min_days), (0, 5))

    def test_diffusion_blank_zero_tour(self):
        diffusion = self.env['ems.erasmus.diffusion'].create({
            'name': 'Test Diffusion Session', 'date': fields.Date.today(), 'channel': 'other'})
        self.start_tour('/odoo/action-ems.action_erasmus_diffusion', 'ems_erasmus_diffusion_blank_zero',
                        login=self.technician.login)
        self.assertEqual(diffusion.recipient_count, 25)

    def test_history_blank_zero_tour(self):
        self.env['ems.erasmus.quality.history'].create({
            'course_name': '2001-2002', 'student_applicants': 7, 'student_target': 20, 'source': 'Test source'})
        self.start_tour('/odoo/action-ems.action_erasmus_quality_history', 'ems_erasmus_history_blank_zero',
                        login=self.erasmus_user.login)
