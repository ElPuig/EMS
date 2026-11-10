from lxml import etree

from odoo.tests.common import tagged

from .test_erasmus_mobility import ErasmusMobilityCase


@tagged('post_install', '-at_install')
class TestErasmusOtherLists(ErasmusMobilityCase):
    """Issue #782 - the lists of mobilities, groups, projects, economy and configuration. Mostly
    presentation; the new figures they show (who handles a document, what an export was, how many
    mobilities a host entity has) are computed and tested here."""

    def _arch(self, xmlid):
        return etree.fromstring(self.env.ref(f'ems.{xmlid}').arch_db)

    def _shown(self, lst):
        """The columns a list shows by default."""
        return [node.get('name') for node in lst.iterchildren('field')
                if not node.get('column_invisible') and node.get('optional') != 'hide']

    # --- behaviour ----------------------------------------------------------------------------

    def test_who_handles_each_document_apart_from_its_state(self):
        """8.7: the record says who handles a document in a word, and its state without who."""
        first, _second = self._accepted()
        for line in first.document_ids:
            self.assertEqual(line.responsible, line.handled_by)
        labels = dict(self.env['ems.erasmus.application.document']._fields['todo_state']._description_selection(
            self.env))
        self.assertEqual(labels['waiting_team'], "Waiting for the team")

    def test_an_export_says_what_and_whose(self):
        """10.12: the log line names the participant of a record, not only its kind."""
        first, _second = self._accepted()
        project = self.env['ems.erasmus.project'].create({'name': 'TEST-EXPORT-LOG', 'kind': 'ka121_vet'})
        Export = self.env['ems.erasmus.export'].sudo()
        record = Export.create({'scope': 'record', 'mobility_id': first.id, 'project_id': project.id})
        whole = Export.create({'scope': 'project', 'project_id': project.id})
        self.assertIn(first.partner_id.name, record.subject)
        self.assertTrue(record.subject.startswith("Participant's record"))
        self.assertEqual(whole.subject, "Whole project")

    def test_host_entity_counts_its_mobilities_not_the_cancelled_ones(self):
        """13.4: individual and group mobilities hosted, in one count per model for the whole list."""
        first, second = self._accepted()
        host, other = self.env['res.partner'].create([
            {'name': 'Test Host Count', 'is_company': True, 'is_erasmus_host': True},
            {'name': 'Test Host Unused', 'is_company': True, 'is_erasmus_host': True}])
        (first | second).write({'host_partner_id': host.id})
        second.sudo().state = 'cancelled'
        project = self.env['ems.erasmus.project'].create({'name': 'TEST-HOST-COUNT', 'kind': 'ka121_vet'})
        self.env['ems.erasmus.group.mobility'].create({'name': 'Test group hosted', 'host_partner_id': host.id,
                                                      'project_id': project.id})
        (host | other).invalidate_recordset(['erasmus_mobility_count'])
        self.assertEqual(host.erasmus_mobility_count, 2)
        self.assertEqual(other.erasmus_mobility_count, 0)

    def test_a_year_is_never_added_up(self):
        """13.8: grouped by year, the group row never sums the years."""
        for model in ('ems.erasmus.support.rate', 'ems.erasmus.project'):
            self.assertIsNone(self.env[model]._fields['call_year'].aggregator, model)
        for name in ('band_from', 'band_to', 'min_days', 'amount'):
            self.assertIsNone(self.env['ems.erasmus.support.rate']._fields[name].aggregator, name)

    # --- what each list shows -----------------------------------------------------------------

    def test_mobility_list_record_and_short_headers(self):
        """5.1, 8.12: the record's progress, the proposal hidden, Students / Staff filters."""
        lst = self._arch('view_erasmus_mobility_list')
        shown = self._shown(lst)
        self.assertIn('record_progress', shown)
        self.assertNotIn('proposal_state', shown)
        search = self._arch('view_erasmus_mobility_search')
        self.assertTrue(search.xpath("//filter[@name='students']") and search.xpath("//filter[@name='staff']"))
        self.assertTrue(search.xpath("//filter[@name='group_call']"))

    def test_mobilities_kanban_by_phase(self):
        """5.2: the menu also offers cards, one column per phase."""
        action = self.env.ref('ems.action_erasmus_mobility')
        self.assertIn('kanban', action.view_mode)
        self.assertEqual(self._arch('view_erasmus_mobility_kanban').get('default_group_by'), 'state')

    def test_pending_validation_shows_what_was_proposed(self):
        """5.18: the same list for the Direction and the Erasmus team."""
        action = self.env.ref('ems.action_erasmus_mobility_to_validate')
        self.assertEqual(action.view_ids[0].view_id, self.env.ref('ems.view_erasmus_mobility_to_validate_list'))
        self.assertEqual(self._shown(self._arch('view_erasmus_mobility_to_validate_list')),
                         ['partner_id', 'proposal_host', 'proposal_country_id', 'proposal_date_start',
                          'proposal_date_end', 'proposal_date'])

    def test_record_table_who_and_state_apart(self):
        """5.8, 8.7: Who and Status apart; every version hidden; the team's files on its own rows."""
        lst = self._arch('view_erasmus_mobility_form').xpath("//field[@name='document_ids']/list")[0]
        shown = self._shown(lst)
        self.assertLess(shown.index('responsible'), shown.index('todo_state'))
        self.assertNotIn('attachment_ids', shown)
        team_files = lst.xpath("field[@name='prepared_attachment_ids']")[0]
        self.assertEqual(team_files.get('invisible'), "handled_by == 'participant'")

    def test_group_selection_table_first(self):
        """9.8: the students' table before the dates of each step, with the ranking's columns."""
        page = self._arch('view_erasmus_group_mobility_form').xpath("//page[@name='selection']")[0]
        children = [node.get('name') for node in page.iterchildren() if node.tag in ('field', 'group')]
        self.assertLess(children.index('registration_ids'), children.index('selection_history'))
        shown = self._shown(page.xpath("field[@name='registration_ids']/list")[0])
        self.assertLessEqual({'partner_id', 'group_id', 'ranking_average', 'proposed_result', 'result'}, set(shown))
        self.assertNotIn('strike_count', shown)

    def test_group_participants_seven_columns_no_red_on_withdrawals(self):
        """9.10"""
        lst = self._arch('view_erasmus_group_mobility_form').xpath("//field[@name='participant_ids']/list")[0]
        self.assertEqual(self._shown(lst), ['role', 'partner_id', 'group_id', 'is_minor', 'documents_missing',
                                            'preparation_complete', 'state'])
        missing = lst.xpath("field[@name='documents_missing']")[0]
        self.assertIn("state != 'withdrawn'", missing.get('decoration-danger'))

    def test_project_list_without_archive_switch(self):
        """10.9, 10.11: archived from Actions; the mobility tables with a title."""
        lst = self._arch('view_erasmus_project_list')
        self.assertFalse(lst.xpath("//field[@widget='boolean_toggle']"))
        form = self._arch('view_erasmus_project_form')
        page = form.xpath("//page[@name='mobilities']")[0]
        self.assertEqual(page.xpath("field[@name='mobility_ids']")[0].get('invisible'), 'not mobility_ids')
        self.assertEqual(len(page.xpath('separator')), 2)

    def test_exports_log_columns(self):
        """10.12"""
        lst = self._arch('view_erasmus_project_form').xpath("//field[@name='export_ids']/list")[0]
        self.assertEqual(self._shown(lst), ['date', 'requester_id', 'subject', 'include_confidential',
                                            'file_count'])

    def test_economy_comparison_three_measures(self):
        """11.4"""
        measures = self._arch('view_erasmus_economy_panel_pivot').xpath("//field[@type='measure']/@name")
        self.assertEqual(measures, ['grant_current', 'committed_amount', 'available_amount'])

    def test_expenses_one_amount(self):
        """11.5: the amount that counts, under the name Amount."""
        for lst in (self._arch('view_erasmus_expense_list'),
                    self._arch('view_erasmus_project_form_economy').xpath("//field[@name='expense_ids']/list")[0]):
            shown = self._shown(lst)
            self.assertIn('counted_amount', shown)
            self.assertNotIn('amount', shown)

    def test_no_survey_pivot(self):
        """12.9: the quality panel already breaks the satisfaction down."""
        self.assertNotIn('pivot', self.env.ref('ems.action_erasmus_satisfaction').view_mode)
        self.assertFalse(self.env['ir.ui.view'].search([('model', '=', 'ems.erasmus.satisfaction'),
                                                        ('type', '=', 'pivot')]))

    def test_host_entities_own_list_without_side_panel(self):
        """13.4"""
        action = self.env.ref('ems.action_erasmus_host_entity')
        self.assertEqual(action.view_ids[0].view_id, self.env.ref('ems.view_partner_erasmus_host_list'))
        self.assertEqual(action.search_view_id, self.env.ref('ems.view_partner_erasmus_host_search'))
        self.assertFalse(self._arch('view_partner_erasmus_host_search').xpath('//searchpanel'))
        self.assertEqual(self._shown(self._arch('view_partner_erasmus_host_list')),
                         ['name', 'country_id', 'city', 'erasmus_oid', 'erasmus_mobility_count'])

    def test_rates_grouped_by_year(self):
        """13.8"""
        self.assertIn('search_default_group_call_year', self.env.ref('ems.action_erasmus_support_rate').context)
