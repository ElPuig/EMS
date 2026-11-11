from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email
from .test_erasmus import PDF, create_erasmus_fixtures
from .test_erasmus_staff import STAFF_PLAN, create_staff_call_fixtures


@tagged('post_install', '-at_install')
class TestErasmusSelectionListsTour(HttpCase):
    """Issue #781 - the lists used to value applications, as the Mobility technician."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_erasmus_fixtures(cls)
        cls.technician = create_role_user(cls, 'erasmus', 'test_lists_technician')
        cls.application = cls.env['ems.erasmus.application'].create({
            'call_id': cls.call.id, 'partner_id': cls.student.id, 'modality_id': cls.call.modality_ids.id,
            'state': 'admitted', 'scoring_frozen_date': fields.Datetime.now()})

    def test_application_list_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_application', 'ems_erasmus_list_applications',
                        login=self.technician.login)

    def test_ranking_menu_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_ranking', 'ems_erasmus_list_ranking_menu',
                        login=self.technician.login)

    def test_ranking_from_call_tour(self):
        self.call.state = 'closed'  # the ranking's button
        self.start_tour(f'/odoo/action-ems.action_erasmus_call/{self.call.id}', 'ems_erasmus_list_ranking_call',
                        login=self.technician.login)

    def test_mobility_documents_student_tour(self):
        self.env['ems.erasmus.call.document'].create({'call_id': self.call.id, 'name': 'Tour Agreement',
                                                      'stage': 'preparation'})
        # Issue #767: the Mobility block shows from the definitive resolution on.
        self.env['ems.erasmus.resolution'].create({'call_id': self.call.id, 'kind': 'definitive', 'state': 'published'})
        self.start_tour(f'/odoo/action-ems.action_erasmus_call/{self.call.id}', 'ems_erasmus_list_documents_student',
                        login=self.technician.login)

    def test_offer_list_tour(self):
        self.env['ems.erasmus.offer'].create({'application_id': self.application.id,
                                              'deadline': fields.Datetime.now() + timedelta(days=3)})
        self.start_tour('/odoo/action-ems.action_erasmus_offer', 'ems_erasmus_list_offers',
                        login=self.technician.login)

    def test_resolution_list_tour(self):
        self.env['ems.erasmus.resolution'].create({'call_id': self.call.id, 'kind': 'admission'})
        self.start_tour('/odoo/action-ems.action_erasmus_resolution', 'ems_erasmus_list_resolutions',
                        login=self.technician.login)


@tagged('post_install', '-at_install')
class TestErasmusStaffSelectionListsTour(HttpCase):
    """The staff call's lists, as the Mobility technician."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_staff_call_fixtures(cls)
        cls.technician = create_role_user(cls, 'erasmus', 'test_lists_staff_technician')

    def _rated(self):
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
        return application

    def test_plan_ratings_tour(self):
        application = self._rated()
        rating = application.plan_rating_ids[:1]
        rating.write({'relevance': '1', 'transfer': '1'})
        rating.sudo().with_user(rating.panel_member_id).action_submit()
        self.assertEqual(rating.rated_count, 1)
        self.assertEqual(rating.plan_mean, application.plan_score)
        self.start_tour('/odoo/action-ems.action_erasmus_plan_rating', 'ems_erasmus_list_plan_ratings',
                        login=self.technician.login)

    def test_mobility_documents_staff_tour(self):
        self.env['ems.erasmus.call.document'].create({'call_id': self.staff_call.id, 'name': 'Tour Agreement',
                                                      'stage': 'preparation'})
        self.env['ems.erasmus.resolution'].create({'call_id': self.staff_call.id, 'kind': 'definitive',
                                                   'state': 'published'})
        self.start_tour(f'/odoo/action-ems.action_erasmus_call/{self.staff_call.id}',
                        'ems_erasmus_list_documents_staff', login=self.technician.login)
