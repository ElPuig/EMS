from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestDepartment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role_dchieff = cls.env.ref('ems.role_dchieff')
        cls.role_seminar = cls.env.ref('ems.role_seminar')
        cls.role_hos = cls.env.ref('ems.role_hos')
        cls.role_dhos = cls.env.ref('ems.role_dhos')
        cls.role_secretary = cls.env.ref('ems.role_secretary')
        cls.group_department_chief = cls.env.ref('ems.group_department_chief')
        cls.group_head_of_studies = cls.env.ref('ems.group_head_of_studies')
        cls.group_secretary = cls.env.ref('ems.group_secretary')
        # role_hos/role_dhos/role_secretary are unipersonal and may already be assigned to a
        # real employee in the working database; clear them so the tests are self-contained.
        (cls.role_hos + cls.role_dhos + cls.role_secretary).sudo().write({'employee_ids': [(5, 0, 0)]})
        # The company may already have a real Director configured (e.g. set by hand while
        # trying out the feature) - clear it too so the top-level "no Director set" fallback
        # tests stay self-contained.
        cls.env.company.director_id = False

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

    def test_seminar_chief_becomes_manager_of_other_members(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Seminar Cascade)'})
        head = self._create_employee('Test Head (Seminar Cascade)', department)
        seminar_chief = self._create_employee('Test Seminar Chief (Seminar Cascade)', department)
        regular = self._create_employee('Test Regular (Seminar Cascade)', department)
        department.write({'manager_id': head.id, 'seminar_chief_id': seminar_chief.id})

        self.assertEqual(regular.parent_id, seminar_chief)

    def test_department_head_excluded_from_cascade(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Head Excluded)'})
        head = self._create_employee('Test Head (Head Excluded)', department)
        seminar_chief = self._create_employee('Test Seminar Chief (Head Excluded)', department)
        department.write({'manager_id': head.id, 'seminar_chief_id': seminar_chief.id})

        self.assertFalse(head.parent_id)

    def test_seminar_chief_manager_is_department_head(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Seminar Manager)'})
        head = self._create_employee('Test Head (Seminar Manager)', department)
        seminar_chief = self._create_employee('Test Seminar Chief (Seminar Manager)', department)
        department.write({'manager_id': head.id, 'seminar_chief_id': seminar_chief.id})

        self.assertEqual(seminar_chief.parent_id, head)

    def test_self_reference_guarded(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Self Reference)'})
        head = self._create_employee('Test Head (Self Reference)', department)
        department.write({'manager_id': head.id, 'seminar_chief_id': head.id})

        self.assertNotEqual(head.parent_id, head)

    def test_changing_department_manager_recascades_existing_members(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Manager Recascade)'})
        seminar_chief = self._create_employee('Test Seminar Chief (Manager Recascade)', department)
        regular = self._create_employee('Test Regular (Manager Recascade)', department)
        department.seminar_chief_id = seminar_chief.id
        old_head = self._create_employee('Test Old Head (Manager Recascade)', department)
        new_head = self._create_employee('Test New Head (Manager Recascade)', department)
        department.manager_id = old_head.id

        department.manager_id = new_head.id

        self.assertEqual(seminar_chief.parent_id, new_head)
        self.assertEqual(regular.parent_id, seminar_chief)

    def test_changing_seminar_chief_recascades_members(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Seminar Recascade)'})
        head = self._create_employee('Test Head (Seminar Recascade)', department)
        regular = self._create_employee('Test Regular (Seminar Recascade)', department)
        old_seminar_chief = self._create_employee('Test Old Seminar Chief (Seminar Recascade)', department)
        new_seminar_chief = self._create_employee('Test New Seminar Chief (Seminar Recascade)', department)
        department.write({'manager_id': head.id, 'seminar_chief_id': old_seminar_chief.id})

        department.seminar_chief_id = new_seminar_chief.id

        self.assertEqual(regular.parent_id, new_seminar_chief)
        self.assertEqual(old_seminar_chief.parent_id, new_seminar_chief)

    def test_department_head_role_auto_assigned_and_removed(self):
        head = self._create_employee('Test Head (Role Assign)', with_user=True)
        department = self.env['hr.department'].create({'name': 'Test Department (Role Assign)', 'manager_id': head.id})

        self.assertIn(self.role_dchieff, head.role_ids)
        self.assertIn(self.group_department_chief, head.user_id.groups_id)

        department.manager_id = False

        self.assertNotIn(self.role_dchieff, head.role_ids)
        self.assertNotIn(self.group_department_chief, head.user_id.groups_id)

    def test_department_head_role_survives_other_headed_department(self):
        head = self._create_employee('Test Head (Multi Department)', with_user=True)
        department_a = self.env['hr.department'].create({'name': 'Test Department A (Multi)', 'manager_id': head.id})
        department_b = self.env['hr.department'].create({'name': 'Test Department B (Multi)', 'manager_id': head.id})

        department_a.manager_id = False

        self.assertIn(self.role_dchieff, head.role_ids)
        self.assertEqual(head.headed_department_ids, department_b)

    def test_seminar_chief_role_auto_assigned_and_removed(self):
        seminar_chief = self._create_employee('Test Seminar Chief (Role Assign)', with_user=True)
        department = self.env['hr.department'].create({
            'name': 'Test Department (Seminar Role Assign)', 'seminar_chief_id': seminar_chief.id,
        })

        self.assertIn(self.role_seminar, seminar_chief.role_ids)
        self.assertIn(self.group_department_chief, seminar_chief.user_id.groups_id)

        department.seminar_chief_id = False

        self.assertNotIn(self.role_seminar, seminar_chief.role_ids)
        self.assertNotIn(self.group_department_chief, seminar_chief.user_id.groups_id)

    def test_employee_changing_department_recomputes_manager(self):
        department_a = self.env['hr.department'].create({'name': 'Test Department A (Move)'})
        department_b = self.env['hr.department'].create({'name': 'Test Department B (Move)'})
        seminar_chief_a = self._create_employee('Test Seminar Chief A (Move)', department_a)
        seminar_chief_b = self._create_employee('Test Seminar Chief B (Move)', department_b)
        department_a.seminar_chief_id = seminar_chief_a.id
        department_b.seminar_chief_id = seminar_chief_b.id
        employee = self._create_employee('Test Employee (Move)', department_a)
        self.assertEqual(employee.parent_id, seminar_chief_a)

        employee.department_id = department_b.id

        self.assertEqual(employee.parent_id, seminar_chief_b)

    def test_onchange_role_ids_blocks_manual_department_head_assignment(self):
        employee = self._create_employee('Test Employee (Onchange Dchieff)')
        employee.role_ids = [(4, self.role_dchieff.id)]

        result = employee._onchange_role_ids()

        self.assertNotIn(self.role_dchieff, employee.role_ids)
        self.assertIn('warning', result)

    def test_onchange_role_ids_blocks_manual_seminar_chief_assignment(self):
        employee = self._create_employee('Test Employee (Onchange Seminar)')
        employee.role_ids = [(4, self.role_seminar.id)]

        result = employee._onchange_role_ids()

        self.assertNotIn(self.role_seminar, employee.role_ids)
        self.assertIn('warning', result)

    def test_reassigning_department_head_demotes_old_head(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Demote Head)'})
        old_head = self._create_employee('Test Old Head (Demote Head)', department, with_user=True)
        department.manager_id = old_head.id
        new_head = self._create_employee('Test New Head (Demote Head)', department, with_user=True)

        department.manager_id = new_head.id

        self.assertNotIn(self.role_dchieff, old_head.role_ids)
        self.assertNotIn(self.group_department_chief, old_head.user_id.groups_id)
        self.assertIn(self.role_dchieff, new_head.role_ids)

    def test_reassigning_seminar_chief_demotes_old_seminar_chief(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Demote Seminar)'})
        old_seminar_chief = self._create_employee('Test Old Seminar Chief (Demote Seminar)', department, with_user=True)
        department.seminar_chief_id = old_seminar_chief.id
        new_seminar_chief = self._create_employee('Test New Seminar Chief (Demote Seminar)', department, with_user=True)

        department.seminar_chief_id = new_seminar_chief.id

        self.assertNotIn(self.role_seminar, old_seminar_chief.role_ids)
        self.assertNotIn(self.group_department_chief, old_seminar_chief.user_id.groups_id)
        self.assertIn(self.role_seminar, new_seminar_chief.role_ids)

    def test_onchange_role_ids_blocks_manual_department_head_removal(self):
        head = self._create_employee('Test Employee (Onchange Remove Dchieff)')
        department = self.env['hr.department'].create({'name': 'Test Department (Onchange Remove Dchieff)', 'manager_id': head.id})
        head.role_ids = [(3, self.role_dchieff.id)]

        result = head._onchange_role_ids()

        self.assertIn(self.role_dchieff, head.role_ids)
        self.assertIn('warning', result)

    def test_onchange_role_ids_blocks_manual_seminar_chief_removal(self):
        seminar_chief = self._create_employee('Test Employee (Onchange Remove Seminar)')
        department = self.env['hr.department'].create({
            'name': 'Test Department (Onchange Remove Seminar)', 'seminar_chief_id': seminar_chief.id,
        })
        seminar_chief.role_ids = [(3, self.role_seminar.id)]

        result = seminar_chief._onchange_role_ids()

        self.assertIn(self.role_seminar, seminar_chief.role_ids)
        self.assertIn('warning', result)

    def test_no_seminar_chief_falls_back_to_department_chief(self):
        department = self.env['hr.department'].create({'name': 'Test Department (No Seminar Fallback)'})
        head = self._create_employee('Test Head (No Seminar Fallback)', department)
        regular = self._create_employee('Test Regular (No Seminar Fallback)', department)
        department.manager_id = head.id

        self.assertEqual(regular.parent_id, head)

    def test_onchange_is_top_level_clears_parent_and_seminar_chief(self):
        parent = self.env['hr.department'].create({'name': 'Test Parent (Top Level Onchange)'})
        seminar_chief = self._create_employee('Test Seminar Chief (Top Level Onchange)')
        department = self.env['hr.department'].create({
            'name': 'Test Department (Top Level Onchange)', 'parent_id': parent.id, 'seminar_chief_id': seminar_chief.id,
        })
        department.is_top_level = True

        department._onchange_is_top_level()

        self.assertFalse(department.parent_id)
        self.assertFalse(department.seminar_chief_id)

    def test_onchange_is_top_level_unchecked_clears_role(self):
        department = self.env['hr.department'].create({
            'name': 'Test Department (Top Level Uncheck)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos',
        })
        department.is_top_level = False

        department._onchange_is_top_level()

        self.assertFalse(department.top_level_role)

    def test_create_top_level_without_parent_or_seminar_chief_in_vals_succeeds(self):
        # The sanitize only fills in parent_id/seminar_chief_id when they're ABSENT from vals
        # (the real onchange-then-save UI flow already clears them client-side beforehand) -
        # explicitly providing a conflicting combination in the same call is a genuine error,
        # caught by the constrain instead (see test_top_level_with_parent_raises), not silently
        # overridden here.
        department = self.env['hr.department'].create({
            'name': 'Test Department (Sanitize Create)', 'is_top_level': True,
        })

        self.assertFalse(department.parent_id)
        self.assertFalse(department.seminar_chief_id)

    def test_create_top_level_with_explicit_parent_raises(self):
        parent = self.env['hr.department'].create({'name': 'Test Parent (Sanitize Create Conflict)'})

        with self.assertRaises(ValidationError):
            self.env['hr.department'].create({
                'name': 'Test Department (Sanitize Create Conflict)', 'is_top_level': True, 'parent_id': parent.id,
            })

    def test_top_level_with_parent_raises(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Top Level Parent Guard)', 'is_top_level': True})
        parent = self.env['hr.department'].create({'name': 'Test Parent (Top Level Parent Guard)'})

        with self.assertRaises(ValidationError):
            department.write({'parent_id': parent.id})

    def test_top_level_role_on_non_top_level_department_raises(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Role Guard)'})

        with self.assertRaises(ValidationError):
            department.write({'top_level_area': 'academic', 'top_level_role': 'hos'})

    def test_top_level_manager_gets_hos_role_not_dchieff(self):
        head = self._create_employee('Test Head (HOS Role)', with_user=True)
        self.env['hr.department'].create({
            'name': 'Test Department (HOS Role)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos', 'manager_id': head.id,
        })

        self.assertIn(self.role_hos, head.role_ids)
        self.assertNotIn(self.role_dchieff, head.role_ids)
        self.assertIn(self.group_head_of_studies, head.user_id.groups_id)

    def test_top_level_manager_gets_dhos_role(self):
        head = self._create_employee('Test Head (DHOS Role)', with_user=True)
        department = self.env['hr.department'].create({
            'name': 'Test Department (DHOS Role)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'dhos', 'manager_id': head.id,
        })

        self.assertIn(self.role_dhos, head.role_ids)

        department.manager_id = False

        self.assertNotIn(self.role_dhos, head.role_ids)

    def test_unipersonal_hos_conflict_raises(self):
        head_a = self._create_employee('Test Head A (Unipersonal HOS)', with_user=True)
        head_b = self._create_employee('Test Head B (Unipersonal HOS)', with_user=True)
        self.env['hr.department'].create({
            'name': 'Test Department A (Unipersonal HOS)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos', 'manager_id': head_a.id,
        })

        with self.assertRaises(ValidationError):
            self.env['hr.department'].create({
                'name': 'Test Department B (Unipersonal HOS)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos', 'manager_id': head_b.id,
            })

    def test_onchange_role_ids_blocks_manual_hos_assignment(self):
        employee = self._create_employee('Test Employee (Onchange HOS Add)')
        employee.role_ids = [(4, self.role_hos.id)]

        result = employee._onchange_role_ids()

        self.assertNotIn(self.role_hos, employee.role_ids)
        self.assertIn('warning', result)

    def test_onchange_role_ids_blocks_manual_hos_removal(self):
        head = self._create_employee('Test Employee (Onchange HOS Remove)')
        self.env['hr.department'].create({
            'name': 'Test Department (Onchange HOS Remove)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos', 'manager_id': head.id,
        })
        head.role_ids = [(3, self.role_hos.id)]

        result = head._onchange_role_ids()

        self.assertIn(self.role_hos, head.role_ids)
        self.assertIn('warning', result)

    def test_onchange_role_ids_blocks_manual_dhos_assignment(self):
        employee = self._create_employee('Test Employee (Onchange DHOS Add)')
        employee.role_ids = [(4, self.role_dhos.id)]

        result = employee._onchange_role_ids()

        self.assertNotIn(self.role_dhos, employee.role_ids)
        self.assertIn('warning', result)

    def test_onchange_role_ids_blocks_manual_dhos_removal(self):
        head = self._create_employee('Test Employee (Onchange DHOS Remove)')
        self.env['hr.department'].create({
            'name': 'Test Department (Onchange DHOS Remove)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'dhos', 'manager_id': head.id,
        })
        head.role_ids = [(3, self.role_dhos.id)]

        result = head._onchange_role_ids()

        self.assertIn(self.role_dhos, head.role_ids)
        self.assertIn('warning', result)

    def test_child_department_chief_manager_is_parent_department_chief(self):
        parent = self.env['hr.department'].create({'name': 'Test Parent (Chief Cascade)'})
        parent_chief = self._create_employee('Test Parent Chief (Chief Cascade)')
        parent.manager_id = parent_chief.id
        child_chief = self._create_employee('Test Child Chief (Chief Cascade)')
        child = self.env['hr.department'].create({
            'name': 'Test Child (Chief Cascade)', 'parent_id': parent.id, 'manager_id': child_chief.id,
        })

        self.assertEqual(child_chief.parent_id, parent_chief)

    def test_child_department_chief_untouched_when_parent_has_no_manager(self):
        parent = self.env['hr.department'].create({'name': 'Test Parent (No Manager Cascade)'})
        child_chief = self._create_employee('Test Child Chief (No Manager Cascade)')
        self.env['hr.department'].create({
            'name': 'Test Child (No Manager Cascade)', 'parent_id': parent.id, 'manager_id': child_chief.id,
        })

        self.assertFalse(child_chief.parent_id)

    def test_changing_parent_manager_recascades_child_chiefs(self):
        parent = self.env['hr.department'].create({'name': 'Test Parent (Recascade Children)'})
        old_parent_chief = self._create_employee('Test Old Parent Chief (Recascade Children)')
        parent.manager_id = old_parent_chief.id
        child_chief = self._create_employee('Test Child Chief (Recascade Children)')
        self.env['hr.department'].create({
            'name': 'Test Child (Recascade Children)', 'parent_id': parent.id, 'manager_id': child_chief.id,
        })
        new_parent_chief = self._create_employee('Test New Parent Chief (Recascade Children)')

        parent.manager_id = new_parent_chief.id

        self.assertEqual(child_chief.parent_id, new_parent_chief)

    def test_reparenting_department_recascades_own_chief(self):
        parent_a = self.env['hr.department'].create({'name': 'Test Parent A (Reparent)'})
        parent_a.manager_id = self._create_employee('Test Parent A Chief (Reparent)').id
        parent_b = self.env['hr.department'].create({'name': 'Test Parent B (Reparent)'})
        parent_b_chief = self._create_employee('Test Parent B Chief (Reparent)')
        parent_b.manager_id = parent_b_chief.id
        child_chief = self._create_employee('Test Child Chief (Reparent)')
        child = self.env['hr.department'].create({
            'name': 'Test Child (Reparent)', 'parent_id': parent_a.id, 'manager_id': child_chief.id,
        })

        child.parent_id = parent_b.id

        self.assertEqual(child_chief.parent_id, parent_b_chief)

    def test_department_chief_heading_elsewhere_excluded_from_own_department_cascade(self):
        # Replicates the real scenario this feature exists for: an employee's own
        # 'department_id' cascade must not sweep them up just because they happen to chief a
        # DIFFERENT department entirely (e.g. a teacher nominally in "Computer Science" who is
        # actually the Head of Studies of "VET").
        cs = self.env['hr.department'].create({'name': 'Test Computer Science (Fernando Case)'})
        fernando = self._create_employee('Test Fernando (Fernando Case)', cs)
        victor = self._create_employee('Test Victor (Fernando Case)', cs)
        other = self._create_employee('Test Other Seminar Chief (Fernando Case)', cs)
        cs.write({'manager_id': victor.id, 'seminar_chief_id': other.id})

        # Before Fernando heads anything: he's a plain member of Computer Science.
        self.assertEqual(fernando.parent_id, other)

        vet = self.env['hr.department'].create({
            'name': 'Test VET (Fernando Case)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'dhos', 'manager_id': fernando.id,
        })

        # Once Fernando heads VET, he's excluded from Computer Science's own cascade entirely -
        # his own parent_id is no longer forced by Computer Science's seminar chief/chief.
        self.assertNotEqual(fernando.parent_id, other)
        self.assertNotEqual(fernando.parent_id, victor)
        # VET has no parent department, so rule 4 doesn't apply to Fernando either (still out of
        # scope pending a future "Direction" department) - Victor, however, IS cascaded.
        self.assertFalse(fernando.parent_id)

        cs.parent_id = vet.id

        self.assertEqual(victor.parent_id, fernando)
        self.assertFalse(fernando.parent_id)

    def test_find_head_of_studies_via_top_level_cascade(self):
        vet = self.env['hr.department'].create({'name': 'Test VET (Find HOS)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos'})
        fernando = self._create_employee('Test Fernando (Find HOS)', with_user=True)
        vet.manager_id = fernando.id
        cs = self.env['hr.department'].create({'name': 'Test Computer Science (Find HOS)', 'parent_id': vet.id})
        victor = self._create_employee('Test Victor (Find HOS)')
        cs.manager_id = victor.id
        teacher = self._create_employee('Test Teacher (Find HOS)', cs)

        self.assertEqual(teacher.find_head_of_studies(), fernando)

    def test_get_report_role_lines_hos_shows_department(self):
        head = self._create_employee('Test Head (Report Lines HOS)')
        department = self.env['hr.department'].create({
            'name': 'Test Department (Report Lines HOS)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos', 'manager_id': head.id,
        })

        lines = head.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(department.name, lines[0])

    def test_top_level_manager_gets_secretary_role_not_dchieff(self):
        head = self._create_employee('Test Head (Secretary Role)', with_user=True)
        self.env['hr.department'].create({
            'name': 'Test Department (Secretary Role)', 'is_top_level': True, 'top_level_area': 'asp', 'top_level_role': 'secretary', 'manager_id': head.id,
        })

        self.assertIn(self.role_secretary, head.role_ids)
        self.assertNotIn(self.role_dchieff, head.role_ids)
        self.assertNotIn(self.role_hos, head.role_ids)
        self.assertNotIn(self.role_dhos, head.role_ids)
        self.assertIn(self.group_secretary, head.user_id.groups_id)

    def test_reassigning_secretary_area_manager_demotes_old_holder(self):
        department = self.env['hr.department'].create({
            'name': 'Test Department (Reassign Secretary)', 'is_top_level': True, 'top_level_area': 'asp', 'top_level_role': 'secretary',
        })
        old_head = self._create_employee('Test Old Secretary (Reassign)', with_user=True)
        department.manager_id = old_head.id
        new_head = self._create_employee('Test New Secretary (Reassign)', with_user=True)

        department.manager_id = new_head.id

        self.assertNotIn(self.role_secretary, old_head.role_ids)
        self.assertIn(self.role_secretary, new_head.role_ids)

    def test_unipersonal_secretary_conflict_raises(self):
        head_a = self._create_employee('Test Head A (Unipersonal Secretary)', with_user=True)
        head_b = self._create_employee('Test Head B (Unipersonal Secretary)', with_user=True)
        self.env['hr.department'].create({
            'name': 'Test Department A (Unipersonal Secretary)', 'is_top_level': True, 'top_level_area': 'asp', 'top_level_role': 'secretary', 'manager_id': head_a.id,
        })

        with self.assertRaises(ValidationError):
            self.env['hr.department'].create({
                'name': 'Test Department B (Unipersonal Secretary)', 'is_top_level': True, 'top_level_area': 'asp', 'top_level_role': 'secretary', 'manager_id': head_b.id,
            })

    def test_onchange_role_ids_blocks_manual_secretary_assignment(self):
        employee = self._create_employee('Test Employee (Onchange Secretary Add)')
        employee.role_ids = [(4, self.role_secretary.id)]

        result = employee._onchange_role_ids()

        self.assertNotIn(self.role_secretary, employee.role_ids)
        self.assertIn('warning', result)

    def test_onchange_role_ids_blocks_manual_secretary_removal(self):
        head = self._create_employee('Test Employee (Onchange Secretary Remove)')
        self.env['hr.department'].create({
            'name': 'Test Department (Onchange Secretary Remove)', 'is_top_level': True, 'top_level_area': 'asp', 'top_level_role': 'secretary', 'manager_id': head.id,
        })
        head.role_ids = [(3, self.role_secretary.id)]

        result = head._onchange_role_ids()

        self.assertIn(self.role_secretary, head.role_ids)
        self.assertIn('warning', result)

    def test_secretary_top_level_cascades_to_child_department_chief(self):
        asp = self.env['hr.department'].create({
            'name': 'Test ASP (Secretary Cascade)', 'is_top_level': True, 'top_level_area': 'asp', 'top_level_role': 'secretary',
        })
        secretary_head = self._create_employee('Test Secretary Head (Secretary Cascade)')
        asp.manager_id = secretary_head.id
        child_chief = self._create_employee('Test Child Chief (Secretary Cascade)')
        self.env['hr.department'].create({
            'name': 'Test Secretariat (Secretary Cascade)', 'parent_id': asp.id, 'manager_id': child_chief.id,
        })

        self.assertEqual(child_chief.parent_id, secretary_head)

    def test_get_report_role_lines_secretary_shows_department(self):
        head = self._create_employee('Test Head (Report Lines Secretary)')
        department = self.env['hr.department'].create({
            'name': 'Test Department (Report Lines Secretary)', 'is_top_level': True, 'top_level_area': 'asp', 'top_level_role': 'secretary', 'manager_id': head.id,
        })

        lines = head.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(department.name, lines[0])

    def test_top_level_area_role_mismatch_raises(self):
        with self.assertRaises(ValidationError):
            self.env['hr.department'].create({
                'name': 'Test Department (Area Mismatch HOS)', 'is_top_level': True,
                'top_level_area': 'asp', 'top_level_role': 'hos',
            })

    def test_top_level_area_role_mismatch_secretary_raises(self):
        with self.assertRaises(ValidationError):
            self.env['hr.department'].create({
                'name': 'Test Department (Area Mismatch Secretary)', 'is_top_level': True,
                'top_level_area': 'academic', 'top_level_role': 'secretary',
            })

    def test_top_level_area_on_non_top_level_department_raises(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Area Guard)'})

        with self.assertRaises(ValidationError):
            department.write({'top_level_area': 'academic'})

    def test_shares_manager_with_parent_clears_own_manager_id(self):
        parent = self.env['hr.department'].create({'name': 'Test Parent (Shares Clear)'})
        head = self._create_employee('Test Head (Shares Clear)')
        department = self.env['hr.department'].create({
            'name': 'Test Department (Shares Clear)', 'parent_id': parent.id, 'manager_id': head.id,
        })
        department.shares_manager_with_parent = True

        department._onchange_shares_manager_with_parent()

        self.assertFalse(department.manager_id)

    def test_shares_manager_with_parent_requires_parent(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Shares No Parent)'})

        with self.assertRaises(ValidationError):
            department.write({'shares_manager_with_parent': True})

    def test_shares_manager_with_parent_and_manager_id_conflict_raises(self):
        parent = self.env['hr.department'].create({'name': 'Test Parent (Shares Conflict)'})
        head = self._create_employee('Test Head (Shares Conflict)')
        department = self.env['hr.department'].create({
            'name': 'Test Department (Shares Conflict)', 'parent_id': parent.id,
        })
        department.shares_manager_with_parent = True

        with self.assertRaises(ValidationError):
            department.write({'manager_id': head.id})

    def test_top_level_cannot_share_manager_with_parent(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Top Level No Share)', 'is_top_level': True})

        with self.assertRaises(ValidationError):
            department.write({'shares_manager_with_parent': True})

    def test_department_with_no_manager_and_no_sharing_leaves_members_unmanaged(self):
        parent = self.env['hr.department'].create({'name': 'Test Parent (No Sharing)'})
        parent.manager_id = self._create_employee('Test Parent Chief (No Sharing)').id
        department = self.env['hr.department'].create({'name': 'Test Department (No Sharing)', 'parent_id': parent.id})
        regular = self._create_employee('Test Regular (No Sharing)', department)

        self.assertFalse(regular.parent_id)

    def test_shares_manager_with_parent_uses_parent_manager(self):
        parent = self.env['hr.department'].create({'name': 'Test Parent (Shares Basic)'})
        parent_chief = self._create_employee('Test Parent Chief (Shares Basic)')
        parent.manager_id = parent_chief.id
        department = self.env['hr.department'].create({
            'name': 'Test Department (Shares Basic)', 'parent_id': parent.id, 'shares_manager_with_parent': True,
        })
        regular = self._create_employee('Test Regular (Shares Basic)', department)

        self.assertEqual(regular.parent_id, parent_chief)

    def test_shares_manager_with_parent_climbs_multiple_levels(self):
        grandparent = self.env['hr.department'].create({
            'name': 'Test Grandparent (Shares Multi)', 'is_top_level': True,
            'top_level_area': 'academic', 'top_level_role': 'hos',
        })
        grandparent_chief = self._create_employee('Test Grandparent Chief (Shares Multi)')
        grandparent.manager_id = grandparent_chief.id
        parent = self.env['hr.department'].create({
            'name': 'Test Parent (Shares Multi)', 'parent_id': grandparent.id, 'shares_manager_with_parent': True,
        })
        department = self.env['hr.department'].create({
            'name': 'Test Department (Shares Multi)', 'parent_id': parent.id, 'shares_manager_with_parent': True,
        })
        regular = self._create_employee('Test Regular (Shares Multi)', department)

        self.assertEqual(regular.parent_id, grandparent_chief)

    def test_chief_of_child_department_of_own_top_level_area_not_self_referenced(self):
        # Replicates the exact real-world bug found: the same employee is both a top-level
        # department's Area Manager AND the Department Chief of one of ITS OWN child
        # departments - their own parent_id must never end up pointing at themselves.
        area = self.env['hr.department'].create({
            'name': 'Test ASP (Self Reference Child)', 'is_top_level': True,
            'top_level_area': 'asp', 'top_level_role': 'secretary',
        })
        manager = self._create_employee('Test Manager (Self Reference Child)')
        area.manager_id = manager.id
        child = self.env['hr.department'].create({
            'name': 'Test Secretariat (Self Reference Child)', 'parent_id': area.id, 'manager_id': manager.id,
        })

        self.assertNotEqual(manager.parent_id, manager)
        self.assertIn(self.role_secretary, manager.role_ids)
        self.assertIn(self.role_dchieff, manager.role_ids)
