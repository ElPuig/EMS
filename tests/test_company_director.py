from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestCompanyDirector(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role_director = cls.env.ref('ems.role_director')
        cls.group_director = cls.env.ref('ems.group_director')
        role_hos = cls.env.ref('ems.role_hos')
        role_dhos = cls.env.ref('ems.role_dhos')
        role_secretary = cls.env.ref('ems.role_secretary')
        # role_director/role_hos/role_dhos/role_secretary are unipersonal and may already be
        # assigned to a real employee in the working database; clear them so the tests are
        # self-contained.
        (cls.role_director + role_hos + role_dhos + role_secretary).sudo().with_context(ems_syncing_roles=True).write({'employee_ids': [(5, 0, 0)]})

    def _create_employee(self, name, department=False, with_user=False):
        vals = {'name': name, 'employee_type': 'teacher'}
        if department:
            vals['department_id'] = department.id
        if with_user:
            user = self.env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': name.lower().replace(' ', '_'),
            })
            vals['user_id'] = user.id
        return self.env['hr.employee'].create(vals)

    def test_setting_director_grants_role_and_group(self):
        director = self._create_employee('Test Director (Grant)', with_user=True)

        self.env.company.director_id = director.id

        self.assertIn(self.role_director, director.role_ids)
        self.assertIn(self.group_director, director.user_id.groups_id)

    def test_clearing_director_revokes_role_and_group(self):
        director = self._create_employee('Test Director (Revoke)', with_user=True)
        self.env.company.director_id = director.id

        self.env.company.director_id = False

        self.assertNotIn(self.role_director, director.role_ids)
        self.assertNotIn(self.group_director, director.user_id.groups_id)

    def test_reassigning_director_demotes_old_director(self):
        old_director = self._create_employee('Test Old Director (Reassign)', with_user=True)
        self.env.company.director_id = old_director.id
        new_director = self._create_employee('Test New Director (Reassign)', with_user=True)

        self.env.company.director_id = new_director.id

        self.assertNotIn(self.role_director, old_director.role_ids)
        self.assertIn(self.role_director, new_director.role_ids)

    def test_top_level_manager_gets_director_as_manager(self):
        director = self._create_employee('Test Director (Top Level Manager)')
        head = self._create_employee('Test Head (Top Level Manager)')
        self.env['hr.department'].create({
            'name': 'Test VET (Top Level Manager)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos', 'manager_id': head.id,
        })

        self.env.company.director_id = director.id

        self.assertEqual(head.parent_id, director)

    def test_director_heading_top_level_department_not_self_referenced(self):
        director = self._create_employee('Test Director (Self Reference)')
        self.env['hr.department'].create({
            'name': 'Test VET (Self Reference)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos', 'manager_id': director.id,
        })

        self.env.company.director_id = director.id

        self.assertNotEqual(director.parent_id, director)
        self.assertFalse(director.parent_id)

    def test_onchange_role_ids_blocks_manual_director_assignment(self):
        employee = self._create_employee('Test Employee (Onchange Director Add)')
        employee.with_context(ems_syncing_roles=True).role_ids = [(4, self.role_director.id)]

        result = employee._onchange_role_ids()

        self.assertNotIn(self.role_director, employee.role_ids)
        self.assertIn('warning', result)

    def test_onchange_role_ids_blocks_manual_director_removal(self):
        director = self._create_employee('Test Employee (Onchange Director Remove)')
        self.env.company.director_id = director.id
        director.with_context(ems_syncing_roles=True).role_ids = [(3, self.role_director.id)]

        result = director._onchange_role_ids()

        self.assertIn(self.role_director, director.role_ids)
        self.assertIn('warning', result)

    def test_write_role_ids_director_removal_with_backing_raises(self):
        # The real server-side barrier: a direct write() (bypassing the employee form's own
        # onchange) must be rejected too, not just reverted client-side.
        director = self._create_employee('Test Employee (Write Bypass Director Remove)')
        self.env.company.director_id = director.id

        with self.assertRaises(ValidationError):
            director.write({'role_ids': [(3, self.role_director.id)]})

    def test_get_report_role_lines_director_shows_company(self):
        director = self._create_employee('Test Director (Report Lines)')
        self.env.company.director_id = director.id

        lines = director.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(self.env.company.name, lines[0])

    def test_get_report_role_lines_tutor_shows_group(self):
        teacher = self._create_employee('Test Tutor (Report Lines)')
        level = self.env.ref('ems.level_cfgs')
        study = self.env['ems.study'].create({
            'code': 'RLT01', 'acronym': 'RLT', 'name': 'Test Study (Report Lines Tutor)',
            'date': '2026-01-01', 'deprecated': False, 'level_id': level.id,
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'RLT',
            'level_id': level.id, 'study_id': study.id,
        })
        group.write({'tutor_id': teacher.id})

        lines = teacher.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(group.name, lines[0])

    def test_get_report_role_lines_department_chief_shows_department(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Report Lines Chief)'})
        chief = self._create_employee('Test Chief (Report Lines)', department)
        department.write({'manager_id': chief.id})

        lines = chief.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(department.name, lines[0])

    def test_get_report_role_lines_seminar_chief_shows_department(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Report Lines Seminar)'})
        seminar_chief = self._create_employee('Test Seminar Chief (Report Lines)', department)
        department.write({'seminar_chief_id': seminar_chief.id})

        lines = seminar_chief.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(department.name, lines[0])

    def test_get_report_role_lines_hos_shows_top_level_department(self):
        head = self._create_employee('Test HoS (Report Lines)')
        department = self.env['hr.department'].create({
            'name': 'Test VET (Report Lines HoS)', 'is_top_level': True,
            'top_level_area': 'academic', 'top_level_role': 'hos', 'manager_id': head.id,
        })

        lines = head.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(department.name, lines[0])

    def test_get_report_role_lines_dhos_shows_top_level_department(self):
        deputy = self._create_employee('Test DHoS (Report Lines)')
        department = self.env['hr.department'].create({
            'name': 'Test VET (Report Lines DHoS)', 'is_top_level': True,
            'top_level_area': 'academic', 'top_level_role': 'dhos', 'manager_id': deputy.id,
        })

        lines = deputy.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(department.name, lines[0])

    def test_get_report_role_lines_secretary_shows_top_level_department(self):
        secretary = self._create_employee('Test Secretary (Report Lines)')
        department = self.env['hr.department'].create({
            'name': 'Test VET (Report Lines Secretary)', 'is_top_level': True,
            'top_level_area': 'asp', 'top_level_role': 'secretary', 'manager_id': secretary.id,
        })

        lines = secretary.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(department.name, lines[0])
