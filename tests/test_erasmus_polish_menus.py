from odoo.tests.common import HttpCase, tagged

from .test_erasmus_satisfaction import ErasmusSatisfactionCase


def children(env, xmlid):
    """The names of a menu's entries, in the order the bar shows them."""
    menus = env.ref(xmlid).with_context(**{'ir.ui.menu.full_list': True}).child_id
    return menus.sorted(lambda menu: (menu.sequence, menu.id)).with_context(lang='en_US').mapped('name')


@tagged('post_install', '-at_install')
class TestErasmusPolishMenus(ErasmusSatisfactionCase):
    """Issue #789 - the Erasmus+ menus."""

    def test_menus_in_the_order_of_the_process(self):
        """1.1, 1.4, 10.1, 11.1, 1.7, 13.1, 8.15."""
        self.assertEqual(children(self.env, 'ems.menu_erasmus_section_calls'),
                         ['Calls', 'Applications', 'Ranking', 'Resolutions', 'Claims', 'Place offers'])
        bar = children(self.env, 'ems.menu_erasmus')
        self.assertEqual(bar[bar.index('Mobilities') + 1:bar.index('Financial management') + 1],
                         ['Projects', 'Financial management'])
        projects = self.env.ref('ems.menu_erasmus_projects')
        self.assertEqual(projects.action, self.env.ref('ems.action_erasmus_project'))
        self.assertEqual(children(self.env, 'ems.menu_erasmus_section_finances'),
                         ['Grant payments', 'Invoices', 'Expenses'])
        self.assertFalse(self.env.ref('ems.action_erasmus_economy_panel', raise_if_not_found=False))
        self.assertEqual(children(self.env, 'ems.menu_erasmus_section_config')[-1], 'Earlier course indicators')
        self.assertNotIn('Earlier courses', children(self.env, 'ems.menu_erasmus_section_quality'))
        mine = children(self.env, 'ems.menu_erasmus_section_mine')
        self.assertIn('Interviews to score', mine)
        self.assertIn('Plans to rate', mine)

    def test_projects_open_on_the_economic_figures(self):
        """10.1: list with the panel's amounts, the comparison by call, then the project."""
        action = self.env.ref('ems.action_erasmus_project')
        self.assertEqual(action.view_mode, 'list,pivot,form')
        self.assertEqual(action.view_ids.sorted('sequence').view_id[:1],
                         self.env.ref('ems.view_erasmus_economy_panel_list'))
        for user in (self.technician_user, self.env.ref('base.user_admin')):
            self.assertIn(self.env.ref('ems.menu_erasmus_projects').id,
                          self.env['ir.ui.menu'].with_user(user)._visible_menu_ids())

    def test_low_scores_from_the_quality_panel(self):
        """12.6: how many low scores, how many without an improvement action, and a link to them."""
        survey, other = self._open()
        survey._ems_portal_answer(5, what_failed='No tasks')
        other._ems_portal_answer(4, what_failed='No mentor')
        Panel = self.env['ems.erasmus.quality.panel'].with_user(self.technician_user).with_context(lang='en_US')
        self.technician_user.groups_id |= self.env.ref('ems.group_teacher')
        other.with_user(self.technician_user).action_create_improvement()
        panel = Panel.create({'call_id': self.call.id})
        self.assertEqual(panel.low_count, 2)
        self.assertEqual(panel.low_note, "Low scores: 2, 1 without an improvement action")
        action = panel.action_open_low_scores()
        self.assertEqual(self.env['ems.erasmus.satisfaction'].search(action['domain']), survey | other)
        self.assertEqual(action['context'], {'search_default_no_action': 1})
        self.assertFalse(Panel.create({'participant_type': 'staff'}).low_count)


@tagged('post_install', '-at_install')
class TestErasmusPolishMenusTour(HttpCase, ErasmusSatisfactionCase):
    """Issue #789 (12.6) - the coordinator goes from the panel to the low scores without an action."""

    def test_low_scores_link(self):
        survey, _other = self._open()
        survey._ems_portal_answer(3, what_failed='No mentor')
        self.technician_user.lang = 'en_US'
        self.start_tour('/odoo/action-ems.action_erasmus_quality_panel_open', 'ems_erasmus_polish_menus_low_scores',
                        login=self.technician_user.login)
