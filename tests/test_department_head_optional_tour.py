from odoo.tests.common import HttpCase, tagged

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestDepartmentHeadOptionalTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env['hr.employee'].create({
            'name': 'Department Head Optional Tour Manager', 'employee_type': 'teacher',
        })
        cls.department = cls.env['hr.department'].create({
            'name': 'Department Head Optional Tour Department',
            'manager_id': cls.manager.id,
        })

    def test_department_head_can_be_removed_and_saved(self):
        # The tour removes the default filter by its English label (see CLAUDE.md's "Tour tests
        # and language"): admin's own language varies from box to box.
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_department_head_optional", login="admin")
