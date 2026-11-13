from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .test_erasmus import PDF

from .test_erasmus_group_mobility import ErasmusGroupMobilityCase
from .test_erasmus_mobility import ErasmusMobilityCase, ErasmusStaffMobilityCase


@tagged('post_install', '-at_install')
class TestErasmusPolishAutomations(ErasmusMobilityCase):
    """Issue #788 - what EMS fills in or does on its own instead of the Erasmus team."""

    def _only_projects(self, kind, count):
        """Leave `count` active projects of `kind`, the dev database's archived."""
        Project = self.env['ems.erasmus.project']
        Project.search([('kind', '=', kind)]).write({'active': False})
        return Project.create([{'name': f'209{index}-1-ES01-{kind.upper().replace("_", "-")}-000000788'}
                               for index in range(count)])

    def test_the_only_project_of_the_kind_is_filled_in(self):
        """5.14, 8.4: a single active project of the modality's kind is the mobility's."""
        self.modality.project = 'ka121_vet'
        only = self._only_projects('ka121_vet', 1)
        first, _second = self._accepted()
        self.assertEqual(first.project_id, only)

    def test_two_projects_of_the_kind_are_left_to_the_team(self):
        """Two agreements of the same kind (two call years): the team chooses."""
        self.modality.project = 'ka121_vet'
        self._only_projects('ka121_vet', 2)
        first, _second = self._accepted()
        self.assertFalse(first.project_id)

    def test_kind_from_the_agreement_number(self):
        """10.8: the kind comes from the agreement number, like the short name."""
        Project = self.env['ems.erasmus.project']
        vet = Project.create({'name': '2095-1-ES01-KA121-VET-000000788'})
        hed = Project.create({'name': '2095-1-ES01-KA131-HED-000000788'})
        self.assertEqual((vet.kind, vet.code), ('ka121_vet', '2095-VET'))
        self.assertEqual((hed.kind, hed.code), ('ka131_hed', '2095-HED'))
        other = Project.create({'name': 'Agreement without a known number', 'kind': 'ka131_hed'})
        self.assertEqual(other.kind, 'ka131_hed', "A number that names no kind keeps the one chosen.")

    def test_call_documents_reach_the_mobilities_on_saving(self):
        """5.17: a document or step added to the call reaches the mobilities still going on."""
        first, _second = self._accepted()
        self.call.with_user(self.erasmus_user).write({
            'preparation_document_ids': [(0, 0, {'name': 'Document added later', 'stage': 'preparation'})],
            'task_ids': [(0, 0, {'name': 'Step added later'})]})
        self.assertIn('Document added later', first.document_ids.mapped('name'))
        self.assertIn('Step added later', first.task_ids.call_task_id.mapped('name'))
        first.sudo().state = 'cancelled'
        self.call.with_user(self.erasmus_user).write({
            'task_ids': [(0, 0, {'name': 'Step after cancelling'})]})
        self.assertNotIn('Step after cancelling', first.task_ids.call_task_id.mapped('name'))

    def test_removing_a_call_document(self):
        """5.17: a document nobody handed in is taken off the call with its empty lines; one a
        participant already handed in can't be, with a clear message, and their files stay."""
        first, second = self._accepted()
        (first | second).sudo().state = 'preparing'
        call = self.call.with_user(self.erasmus_user)
        call.write({'preparation_document_ids': [(0, 0, {'name': 'Document nobody hands in', 'stage': 'preparation'})]})
        document = call.preparation_document_ids.filtered(lambda document: document.name == 'Document nobody hands in')
        lines = (first | second).document_ids.filtered(lambda line: line.call_document_id == document)
        self.assertEqual(len(lines), 2)
        call.write({'preparation_document_ids': [(2, document.id)]})
        self.assertFalse(document.exists())
        self.assertFalse(lines.exists())

        call.write({'preparation_document_ids': [(0, 0, {'name': 'Document handed in', 'stage': 'preparation'})]})
        line = first.document_ids.filtered(lambda line: line.name == 'Document handed in')
        line.sudo()._ems_add_files([('handed-in.pdf', PDF)])
        files = line.attachment_ids
        self.assertTrue(files)
        with self.assertRaisesRegex(UserError, 'Document handed in'):
            call.write({'preparation_document_ids': [(2, line.call_document_id.id)]})
        self.assertTrue(line.call_document_id.exists())
        self.assertEqual(line.attachment_ids, files)
        self.assertTrue(second.document_ids.filtered(lambda other: other.call_document_id == line.call_document_id),
                        "The other participants' empty lines stay too.")

    def test_country_and_city_from_the_host_entity(self):
        """13.6: choosing the host entity fills the country and city still empty."""
        first, _second = self._accepted()
        first.sudo().state = 'preparing'
        host = self.env['res.partner'].create({'name': 'Test Host 788', 'is_company': True, 'is_erasmus_host': True,
                                               'country_id': self.env.ref('base.pt').id, 'city': 'Porto'})
        mobility = Form(first.with_user(self.erasmus_user))
        mobility.host_partner_id = host
        self.assertEqual((mobility.country_id, mobility.city), (self.env.ref('base.pt'), 'Porto'))
        mobility.city = 'Braga'
        mobility.host_partner_id = self.env['res.partner']
        mobility.host_partner_id = host
        self.assertEqual(mobility.city, 'Braga', "What is already written stays.")

    def test_rate_counts_participants_by_action(self):
        """13.9: KA121-VET counts by kind of mobility; KA131-HED, the whole project."""
        Rate = self.env['ems.erasmus.support.rate']
        vet, hed = Rate.create([{'call_year': 2095, 'kind': kind, 'amount': 100} for kind in ('ka121_vet', 'ka131_hed')])
        self.assertEqual((vet.band_scope, hed.band_scope), ('same', 'project'))


@tagged('post_install', '-at_install')
class TestErasmusPolishAutomationsStaff(ErasmusStaffMobilityCase):
    """Issue #788 - a staff mobility, on its call's single project."""

    def test_the_call_single_project_is_filled_in(self):
        self.staff_call.project_place_ids.filtered(
            lambda line: line.project_id == self.staff_hed_project).unlink()
        mobility = self._accepted_staff()
        self.assertEqual(mobility.project_id, self.staff_vet_project)

    def test_validating_the_proposal_leaves_the_host_entity_to_the_team(self):
        """8.3 dropped (adriamt, 2026-11-13): the name the teacher writes is only a guide."""
        mobility = self._accepted_staff()
        self._send_proposal(mobility)
        mobility.with_user(self.director_user).action_validate_proposal()
        self.assertFalse(mobility.host_partner_id)


@tagged('post_install', '-at_install')
class TestErasmusPolishAutomationsGroup(ErasmusGroupMobilityCase):
    """Issue #788 (5.17) - the group's files get the documents added on saving."""

    def test_documents_asked_for_reach_the_files_on_saving(self):
        self._approved()
        participants = self.mobility.participant_ids
        lines = participants.document_ids
        self.mobility.with_user(self.coordinator_user).write({'requirement_ids': [(0, 0, {
            'name': 'Group document added later', 'stage': 'preparation', 'group_audience': 'student'})]})
        added = participants.document_ids - lines
        self.assertTrue(added)
        self.assertEqual(set(added.mapped('name')), {'Group document added later'})
        # Taken off again before anybody hands it in: the empty lines go with it.
        coordinator = self.mobility.with_user(self.coordinator_user)
        coordinator.write({'requirement_ids': [(2, added.call_document_id.id)]})
        self.assertFalse(added.exists())

    def test_a_document_handed_in_stays_in_the_group_mobility(self):
        """Taking a document off the group mobility never removes a file already handed in."""
        self._approved()
        coordinator = self.mobility.with_user(self.coordinator_user)
        coordinator.write({'requirement_ids': [(0, 0, {
            'name': 'Group document handed in', 'stage': 'preparation', 'group_audience': 'student'})]})
        line = self.mobility.participant_ids.document_ids.filtered(lambda line: line.name == 'Group document handed in')[:1]
        line.sudo()._ems_add_files([('handed-in.pdf', PDF)])
        files = line.attachment_ids
        with self.assertRaisesRegex(UserError, 'Group document handed in'):
            coordinator.write({'requirement_ids': [(2, line.call_document_id.id)]})
        self.assertEqual(line.exists().attachment_ids, files)
