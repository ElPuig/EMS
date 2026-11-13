from odoo.tests.common import HttpCase, tagged

from .test_erasmus_satisfaction import ErasmusSatisfactionCase


@tagged('post_install', '-at_install')
class TestErasmusQualityDashboard(ErasmusSatisfactionCase):
    """Issue #793 - the quality panel: what is looked at, readable at a glance."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = cls.env['ems.course'].search([('start', '=', 2093)]) or cls.env['ems.course'].create(
            {'start': 2093, 'end': 2094})
        cls.Panel = cls.env['ems.erasmus.quality.panel'].with_user(cls.technician_user).with_context(lang='en_US')

    def _row(self, panel, name):
        return next(row for row in panel._ems_data()['indicators'] if row['name'] == name)

    def test_opens_on_the_current_course(self):
        """12.1: what is looked at almost every time, already chosen."""
        self.env.company.current_course_id = self.course
        action = self.Panel.action_open_panel()
        self.assertEqual(self.Panel.browse(action['res_id']).course_id, self.course)

    def test_columns_and_met_in_colour(self):
        """12.3: Indicator, Value, Target, Met (green or red) and Answers; the median only in the breakdown."""
        first, second = self._open()
        first._ems_portal_answer(10)
        second._ems_portal_answer(9)
        headers = self.Panel._ems_headers()
        self.assertEqual(headers['indicators'], ['Indicator', 'Value', 'Target', 'Met', 'Answers'])
        self.assertIn('Median', headers['by_type'])
        panel = self.Panel.create({'call_id': self.call.id})
        self.assertIn('<span class="badge text-bg-success">Yes</span>', panel.indicators_html,
                      "Satisfaction 9.5 is above 8.5.")
        second.sudo().score = 1
        self.assertIn('<span class="badge text-bg-danger">No</span>',
                      self.Panel.create({'call_id': self.call.id}).indicators_html)

    def test_diffusion_actions_against_their_target(self):
        """12.11: the diffusion actions of the course, at least 10 a year."""
        panel = self.Panel.create({'course_id': self.course.id})
        Diffusion = self.env['ems.erasmus.diffusion']
        Diffusion.create([{'name': f'Talk {index}', 'course_id': self.course.id} for index in range(9)])
        row = panel._ems_indicator_row(self._row(panel, 'Diffusion actions'))
        self.assertEqual(row[1:3], ['9', '≥ 10'])
        self.assertIn('text-bg-danger', row[3])
        Diffusion.create({'name': 'Talk 10', 'course_id': self.course.id})
        self.assertIn('text-bg-success', panel._ems_indicator_row(self._row(panel, 'Diffusion actions'))[3])
        self.assertIsNone(self._row(self.Panel.create({}), 'Diffusion actions')['value'],
                          "The target is per course: nothing to compare without one.")

    def test_interest_says_when_it_is_frozen(self):
        """C43: counted at the moment while the call is open, frozen with the definitive resolution."""
        help_text = self._row(self.Panel.create({}), 'Student interest')['help']
        self.assertIn('counted at the moment while the call is open', help_text)
        self.assertIn('frozen when its definitive resolution is published', help_text)


@tagged('post_install', '-at_install')
class TestErasmusQualityDashboardTour(HttpCase, ErasmusSatisfactionCase):
    """Issue #793 - the Erasmus technician opens the panel from the menu."""

    def test_quality_dashboard_tour(self):
        course = self.env['ems.course'].search([('start', '=', 2093)]) or self.env['ems.course'].create(
            {'start': 2093, 'end': 2094})
        self.env.company.current_course_id = course
        self.env['ems.erasmus.diffusion'].create({'name': 'Information session', 'course_id': course.id})
        self.technician_user.lang = 'en_US'
        self.start_tour('/odoo/action-ems.action_erasmus_quality_panel_open', 'ems_erasmus_polish_quality_dashboard',
                        login=self.technician_user.login)
