from lxml import etree

from odoo.tests.common import TransactionCase, tagged

from .common import mock_outgoing_email
from .test_erasmus import create_erasmus_fixtures
from .test_erasmus_staff import create_staff_call_fixtures


@tagged('post_install', '-at_install')
class TestErasmusSelectionLists(TransactionCase):
    """Issue #781 - the lists used to value applications. Presentation only: what each list shows
    and in which order, never what is stored or decided."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_erasmus_fixtures(cls)

    def _columns(self, xmlid):
        return [node.get('name') for node in etree.fromstring(self.env.ref(f'ems.{xmlid}').arch_db).iter('field')
                if node.getparent().tag == 'list']


    def test_ranking_has_no_row_colour(self):
        for xmlid in ('view_erasmus_ranking_list', 'view_erasmus_staff_ranking_list',
                      'view_erasmus_ranking_common_list', 'view_erasmus_offer_list'):
            arch = etree.fromstring(self.env.ref(f'ems.{xmlid}').arch_db)
            self.assertFalse([name for name in arch.keys() if name.startswith('decoration-')], xmlid)

    def test_a_group_never_adds_up_positions_or_points(self):
        """A rank or a score adds up to nothing: Odoo sums an integer or a float in a group's row.
        None, not False: the client only leaves out of a group's order a field with no aggregator
        in fields_get(), and False would reach the server and fail."""
        application = self.env['ems.erasmus.application']
        for name in ('rank', 'score_total', 'score_a', 'score_f', 'score_plan', 'score_internationalisation'):
            self.assertIsNone(application._fields[name].aggregator, name)

    def test_resolutions_of_a_call_in_chronological_order(self):
        call_form = etree.fromstring(self.env.ref('ems.view_erasmus_call_form').arch_db)
        lists = call_form.xpath(".//field[@name='resolution_ids']/list")
        self.assertTrue(lists[0].get('default_order').startswith('publish_date'))

    def test_mobility_documents_list_five_columns(self):
        call_form = etree.fromstring(self.env.ref('ems.view_erasmus_call_form').arch_db)
        rows = call_form.xpath(".//field[@name='preparation_document_ids']/list")[0]
        shown = [node.get('name') for node in rows.iter('field')
                 if not node.get('column_invisible') and node.get('optional') != 'hide'
                 and node.get('widget') != 'handle']
        self.assertEqual(shown, ['stage', 'name', 'requirement', 'due_basis', 'handled_by'])


    def test_results_tab_titles(self):
        for xmlid in ('view_erasmus_application_form', 'view_erasmus_application_staff_form'):
            arch = etree.fromstring(self.env.ref(f'ems.{xmlid}').with_context(lang='en_US').arch_db)
            titles = {node.get('string') for node in arch.iter('separator')}
            self.assertLessEqual({'Place offers', 'Claims'}, titles, xmlid)


@tagged('post_install', '-at_install')
class TestErasmusStaffSelectionLists(TransactionCase):
    """Issue #781 - the staff call's lists."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_staff_call_fixtures(cls)

    def test_staff_ranking_goes_by_position_alone(self):
        action = self.staff_call.action_view_ranking()
        self.assertEqual(action['views'][0][0], self.env.ref('ems.view_erasmus_staff_ranking_list').id)
        self.assertFalse(action['context'].get('group_by'))
        arch = etree.fromstring(self.env.ref('ems.view_erasmus_staff_ranking_list').arch_db)
        self.assertTrue(arch.get('default_order').startswith('rank'))

    def test_plan_ratings_group_by_applicant_with_the_mean(self):
        """The mean is the application's own plan score, not an average of the rows (where an
        abstention and a rating still to come would count as 0)."""
        Rating = self.env['ems.erasmus.plan_rating']
        self.assertEqual(Rating._fields['plan_mean'].aggregator, 'max')
        self.assertEqual(Rating._fields['rated_count'].aggregator, 'sum')
        action = self.env.ref('ems.action_erasmus_plan_rating')
        self.assertNotIn('pivot', action.view_mode)
        self.assertIn('search_default_group_applicant', action.context)
        self.assertFalse(self.env['ir.ui.view'].search([('model', '=', 'ems.erasmus.plan_rating'),
                                                        ('type', '=', 'pivot')]))
