from odoo.tests.common import HttpCase, tagged

from .common import create_role_user
from .test_erasmus_group_mobility import ErasmusGroupMobilityCase
from .test_erasmus_mobility import ErasmusMobilityCase


@tagged('post_install', '-at_install')
class TestErasmusOtherListsTour(HttpCase, ErasmusMobilityCase):
    """Issue #782 - the mobilities, projects, economy and configuration lists, as the Mobility
    technician (the least privileged role of the Erasmus team), every view mode of each action."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.technician = create_role_user(cls, 'erasmus', 'test_other_lists_technician')
        # The host entity's form reads students' data: the Erasmus team are teachers too (#777).
        cls.technician.groups_id |= cls.env.ref('ems.group_teacher')

    def test_mobilities_tour(self):
        first, _second = self._accepted()
        host = self.env['res.partner'].create({'name': 'Tour Host Entity', 'is_company': True,
                                               'is_erasmus_host': True, 'city': 'Tour City',
                                               'country_id': self.env.ref('base.de').id, 'erasmus_oid': 'E10TOUR1'})
        first.write({'host_partner_id': host.id, 'proposal_state': 'pending', 'proposal_host': 'Tour Proposed Host'})
        # The team's files column is only for a document the team hands over. The list only draws a
        # cell when there is a file to show, so each kind of document holds one: a participant's
        # document must still show nothing there.
        team_line, participant_line = first.document_ids[:2]
        team_line.call_document_id.sudo().handled_by = 'team'
        for line in (team_line, participant_line):
            line.sudo().prepared_attachment_ids = self.env['ir.attachment'].create({
                'name': 'team-file.pdf', 'raw': b'%PDF-1.4 tour', 'res_model': line._name, 'res_id': line.id})
        project = self.env['ems.erasmus.project'].create({'name': 'TOUR-OTHER-LISTS', 'kind': 'ka121_vet'})
        first.project_id = project
        self.env['ems.erasmus.export'].sudo().create({'scope': 'record', 'mobility_id': first.id,
                                                      'project_id': project.id})
        self.env['ems.erasmus.expense'].create({'project_id': project.id, 'concept': 'Tour expense', 'amount': 50})
        self.env['ems.erasmus.payment'].sudo().create({'mobility_id': first.id, 'kind': 'single', 'amount': 100})
        for action, tour in (('action_erasmus_mobility', 'mobilities'), ('action_erasmus_mobility_to_validate',
                                                                          'to_validate'),
                             ('action_erasmus_project', 'projects'), ('action_erasmus_economy_panel', 'panel'),
                             ('action_erasmus_expense', 'expenses'), ('action_erasmus_payment', 'payments'),
                             ('action_erasmus_host_entity', 'config'), ('action_erasmus_support_rate', 'rates'),
                             ('action_erasmus_satisfaction', 'surveys')):
            with self.subTest(tour=tour):
                self.start_tour(f'/odoo/action-ems.{action}', f'ems_erasmus_other_lists_{tour}',
                                login=self.technician.login)


@tagged('post_install', '-at_install')
class TestErasmusOtherListsGroupTour(HttpCase, ErasmusGroupMobilityCase):
    """Issue #782 (9.8, 9.10) - the group mobility's Selection and Participants tabs, as its leader."""

    def test_group_tour(self):
        self._approved()
        self.start_tour('/odoo/action-ems.action_erasmus_my_group_mobility', 'ems_erasmus_other_lists_group',
                        login=self.leader_user.login)
