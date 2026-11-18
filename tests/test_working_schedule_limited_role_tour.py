from odoo.tests.common import HttpCase, tagged

from .common import create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestWorkingScheduleLimitedRoleTour(HttpCase):
    """Issue #846: the Schedule tab loads groups, subjects and rooms with the form, so a role that can't
    read them doesn't get the tab, and My Profile and the employee form still open."""

    def _schedule_tab_shown(self, user):
        employee = create_role_employee(self, user)
        employee.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8.0, 'hour_to': 9.0, 'day_period': 'morning', 'name': 'TT',
            'non_teaching': self.env.ref('ems.non_teaching_tt').id,
        }])
        arch = self.env['hr.employee'].with_user(user).get_view(self.env.ref('hr.view_employee_form').id, 'form')['arch']
        profile = user.with_user(user).web_read({'can_view_schedule': {}, 'schedule_attendance_ids': {}})[0]
        self.assertEqual('schedule_grid' in arch, profile['can_view_schedule'])
        self.assertEqual(len(profile['schedule_attendance_ids']), int(profile['can_view_schedule']))
        return profile['can_view_schedule']

    def test_schedule_tab_follows_the_roles_that_can_read_its_data(self):
        plain_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Limited plain user', 'login': 'test_twslr_plain',
            'groups_id': [(6, 0, self.env.ref('base.group_user').ids)],
        })
        self.assertFalse(self._schedule_tab_shown(plain_user))
        for role in ('quality', 'quality_admin', 'settings', 'settings_admin', 'erasmus', 'erasmus_coordinator'):
            with self.subTest(role=role):
                self.assertFalse(self._schedule_tab_shown(create_role_user(self, role, f'test_twslr_{role}')))
        for role in ('teacher', 'secretary', 'academic_admin'):
            with self.subTest(role=role):
                self.assertTrue(self._schedule_tab_shown(create_role_user(self, role, f'test_twslr_{role}')))

    def test_limited_role_opens_my_profile(self):
        user = create_role_user(self, 'quality', 'test_twslr_tour', name='Limited Role Tour User')
        create_role_employee(self, user, name='Limited Role Tour User')

        self.start_tour("/odoo", "ems_working_schedule_limited_role_profile", login=user.login)

    def test_limited_role_opens_an_employee_form(self):
        user = create_role_user(self, 'settings_admin', 'test_twslr_form', name='Limited Role Form User')
        create_role_employee(self, user, name='Limited Role Form User')

        self.start_tour("/odoo/action-ems.action_employee_kanban",
                        "ems_working_schedule_limited_role_form", login=user.login)
