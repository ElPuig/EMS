from odoo import fields
from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email
from .test_erasmus import PDF, create_erasmus_fixtures
from .test_erasmus_staff import STAFF_PLAN, create_staff_call_fixtures


@tagged('post_install', '-at_install')
class TestErasmusLabelsTour(HttpCase):
    """Issue #779 - labels with some behaviour of their own, driven by the Mobility technician, and
    by the coordinator for the earlier courses, which only the coordination can type in."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_erasmus_fixtures(cls)
        cls.technician = create_role_user(cls, 'erasmus', 'test_labels_technician')

    def test_student_points_tour(self):
        application = self.env['ems.erasmus.application'].create({
            'call_id': self.call.id, 'partner_id': self.student.id, 'modality_id': self.call.modality_ids.id,
            'fewer_opportunities_check': 'yes', 'first_mobility': 'yes', 'state': 'admitted',
            'scoring_frozen_date': fields.Datetime.now()})
        self.start_tour(f'/odoo/action-ems.action_erasmus_application/{application.id}',
                        'ems_erasmus_student_points', login=self.technician.login)

    def test_rate_headers_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_support_rate', 'ems_erasmus_rate_headers',
                        login=self.technician.login)

    def test_history_form_tour(self):
        history = self.env['ems.erasmus.quality.history'].create({
            'course_name': '2001-2002', 'student_applicants': 7, 'student_target': 20, 'source': 'Test source'})
        self.start_tour('/odoo/action-ems.action_erasmus_quality_history', 'ems_erasmus_history_form',
                        login=self.erasmus_user.login)
        self.assertEqual(history.staff_target, 9)

    def test_project_downloads_tour(self):
        project = self.env['ems.erasmus.project'].create({'name': '2099-1-ES01-KA121-VET-000779779',
                                                          'kind': 'ka121_vet'})
        self.start_tour(f'/odoo/action-ems.action_erasmus_project/{project.id}', 'ems_erasmus_project_downloads',
                        login=self.technician.login)


@tagged('post_install', '-at_install')
class TestErasmusStaffLabelsTour(HttpCase):
    """The staff call's labels, as the Mobility technician."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_staff_call_fixtures(cls)

    def test_staff_labels_tour(self):
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(
            self.staff_call, self.staff_users[0].partner_id)
        application._ems_portal_save(
            {'declared_never_staff_mobility': True, 'declared_centre_start_date': '2015-09-01', **STAFF_PLAN},
            {self.id_document.id: [('id.pdf', PDF)]})
        application.action_submit()
        application.requirements_check = 'met'
        application.document_ids.filtered('attachment_ids').action_mark_valid()
        application.action_admit()
        self.staff_call.action_close()
        self.staff_call.action_send_to_panel()
        technician = create_role_user(self, 'erasmus', 'test_labels_staff_technician')
        self.start_tour(f'/odoo/action-ems.action_erasmus_application/{application.id}',
                        'ems_erasmus_staff_labels', login=technician.login)
        self.assertFalse(application.seniority, "The placeholder is not a value.")
