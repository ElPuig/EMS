from lxml import etree

from odoo.tests.common import tagged

from .test_erasmus_mobility import ErasmusMobilityCase

@tagged('post_install', '-at_install')
class TestErasmusOtherLists(ErasmusMobilityCase):
    """Issue #782 - the lists of mobilities, groups, projects, economy and configuration. The new
    figures they show (who handles a document, what an export was, how many mobilities a host
    entity has) are computed and tested here. Which columns each list shows is checked in the
    browser by the tour (test_erasmus_polish_other_lists_tour.py); only what it does not assert
    stays here: the group's tab order and no red on a withdrawal."""

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
