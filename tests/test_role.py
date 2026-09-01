from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestRole(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role_hos = cls.env.ref('ems.role_hos')
        cls.role_quality = cls.env.ref('ems.role_quality')
        # Both may already be assigned to a real employee in the working database (role_hos
        # is unipersonal, role_quality too) - clear them so the tests are self-contained.
        cls.role_hos.sudo().with_context(ems_syncing_roles=True).write({'employee_ids': [(5, 0, 0)]})
        cls.role_quality.sudo().write({'employee_ids': [(5, 0, 0)]})

    def _create_employee(self, name):
        return self.env['hr.employee'].create({'name': name, 'employee_type': 'teacher'})

    def test_write_employee_ids_on_hierarchy_managed_role_raises(self):
        # ems.role's own form ('Assigned to' tab) is the other bypass this session's
        # investigation found for the 7 hierarchy-managed roles: writing employee_ids from
        # THIS side never went through the employee's own onchange guard at all.
        employee = self._create_employee('Test Employee (Role Form Bypass Add)')

        with self.assertRaises(ValidationError):
            self.role_hos.write({'employee_ids': [(4, employee.id)]})

    def test_write_employee_ids_removal_on_hierarchy_managed_role_raises(self):
        # Reproduces the real-world report exactly: a legitimately-assigned holder (real
        # backing department) removed from the ROLE's own 'Assigned to' tab instead of the
        # employee's form.
        head = self._create_employee('Test Employee (Role Form Bypass Remove)')
        self.env['hr.department'].create({
            'name': 'Test Department (Role Form Bypass Remove)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos', 'manager_id': head.id,
        })
        self.assertIn(head.id, self.role_hos.employee_ids.ids)

        with self.assertRaises(ValidationError):
            self.role_hos.write({'employee_ids': [(3, head.id)]})

    def test_write_employee_ids_on_minor_role_still_allowed(self):
        # Only the 7 hierarchy-managed roles are locked - every other ems.role (like this
        # unrelated one) keeps working exactly as before.
        employee = self._create_employee('Test Employee (Minor Role Still Editable)')

        self.role_quality.write({'employee_ids': [(4, employee.id)]})

        self.assertIn(employee.id, self.role_quality.employee_ids.ids)

    def test_create_default_color(self):
        role = self.env['ems.role'].create({'name': 'Test role default color'})
        self.assertEqual(role.color, '#3A8DDE')

    def test_create_valid_hex_color(self):
        role = self.env['ems.role'].create({'name': 'Test role valid color', 'color': '#112233'})
        self.assertEqual(role.color, '#112233')

    def test_invalid_color_raises(self):
        with self.assertRaises(Exception):
            self.env['ems.role'].create({'name': 'Test role invalid color', 'color': 'not-a-color'})

    def test_seed_roles_have_distinct_colors(self):
        roles = self.env['ems.role'].search([])
        colors = roles.mapped('color')
        self.assertEqual(len(colors), len(set(colors)), "Two or more roles share the exact same color.")
