from odoo.tests.common import HttpCase, tagged

from .common import create_role_user
from .test_erasmus_mobility import ErasmusMobilityCase
from .test_erasmus_pocket_money import ErasmusPocketMoneyCase
from .test_erasmus_staff import ErasmusStaffCase


@tagged('post_install', '-at_install')
class TestErasmusFormHeadersTour(HttpCase, ErasmusMobilityCase):
    """Issues #783 and #784 - the call, application, mobility, offer, project and host entity forms,
    as the Mobility technician (the least privileged role of the Erasmus team)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.technician = create_role_user(cls, 'erasmus', 'test_form_headers_technician')
        # The host entity's form reads students' data: the Erasmus team are teachers too (#777).
        cls.technician.groups_id |= cls.env.ref('ems.group_teacher')

    def test_form_headers_tour(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        host = self.env['res.partner'].create({'name': 'Tour Header Host', 'is_company': True,
                                               'is_erasmus_host': True})
        first.host_partner_id = host
        project = self.env['ems.erasmus.project'].create({'name': 'TOUR-FORM-HEADERS', 'kind': 'ka121_vet'})
        login = self.technician.login
        for url, tour in ((f'action_erasmus_call/{self.call.id}', 'call'),
                          (f'action_erasmus_application/{first.application_id.id}', 'application'),
                          (f'action_erasmus_mobility/{first.id}', 'mobility'),
                          ('action_erasmus_offer', 'offers'),
                          (f'action_erasmus_project/{project.id}', 'project'),
                          (f'action_erasmus_host_entity/{host.id}', 'host')):
            with self.subTest(tour=tour):
                self.start_tour(f'/odoo/action-ems.{url}', f'ems_erasmus_form_headers_{tour}', login=login)


@tagged('post_install', '-at_install')
class TestErasmusFormHeadersGroupTour(HttpCase, ErasmusPocketMoneyCase):
    """Issue #784 (9.4, 9.15) - the group's dates and who pays, as the Mobility technician."""

    def test_group_tour(self):
        self._ready()
        self.technician_user.lang = 'en_US'
        self.start_tour(f'/odoo/action-ems.action_erasmus_group_mobility/{self.mobility.id}',
                        'ems_erasmus_form_headers_group', login=self.technician_user.login)


@tagged('post_install', '-at_install')
class TestErasmusFormHeadersStaffTour(HttpCase, ErasmusStaffCase):
    """Issue #783 (P01, P02, P07) - a teacher's staff call screens and the upload dialog."""

    def test_teacher_tour(self):
        self.staff_call.description = '<p>Tour information for applicants</p>'
        self._apply(0)
        self.start_tour('/odoo/action-ems.action_erasmus_staff_calls', 'ems_erasmus_form_headers_teacher',
                        login=self.staff_users[0].login)
