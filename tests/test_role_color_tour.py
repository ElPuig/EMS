from odoo.tests import tagged, HttpCase

from ..models.employees.employee import EMS_ROLE_SYNC_CONTEXT_KEY
from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestRoleColorTour(HttpCase):

    def test_role_list_and_form_render(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_role_color_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_role_color_smoke", login="admin")

    def test_employee_role_badge_renders(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_employee_role_badge_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_employee_role_badge_smoke", login="admin")

    def test_role_hierarchy_lock_renders(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # The tour checks the cards of the employees assigned to each role, so it needs its own:
        # a clean database (CI) has none, and the kanban then only holds its invisible
        # placeholder cards. Both roles are single-person, so each one is replaced rather than
        # added to. Head of Studies is hierarchy-managed (assigned from the department form), so
        # its fixture goes through the same sync context the department cascade uses.
        hos_employee, quality_employee = self.env['hr.employee'].create([
            {'name': '0000 Role Lock Head of Studies', 'employee_type': 'teacher'},
            {'name': '0000 Role Lock Quality', 'employee_type': 'teacher'},
        ])
        self.env.ref('ems.role_hos').with_context(**{EMS_ROLE_SYNC_CONTEXT_KEY: True}).write({
            'employee_ids': [(6, 0, hos_employee.ids)],
        })
        self.env.ref('ems.role_quality').write({'employee_ids': [(6, 0, quality_employee.ids)]})
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_role_hierarchy_lock_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_role_hierarchy_lock_smoke", login="admin")
