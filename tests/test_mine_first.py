# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase

from .common import create_level_study_group, create_role_employee, create_role_user


class TestMineFirst(TransactionCase):
    """Dropdowns of departments, workgroups and groups offer the user's own first, and departments
    read in the user's language (ems.mine_first_mixin)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('ca_ES')
        cls.stage = cls.env['hr.department'].create({'name': 'Zz Mine Stage'})
        cls.stage.with_context(lang='ca_ES').name = 'Zz Etapa Meva'
        cls.mine = cls.env['hr.department'].create({'name': 'Zz Mine Computing', 'parent_id': cls.stage.id})
        cls.mine.with_context(lang='ca_ES').name = 'Zz Informàtica Meva'
        cls.other = cls.env['hr.department'].create({'name': 'Aa Other Department'})
        cls.sibling = cls.env['hr.department'].create({'name': 'Zz Mine Sibling', 'parent_id': cls.stage.id})
        cls.user = create_role_user(cls, 'teacher', 'mine.first@example.com')
        cls.employee = create_role_employee(cls, cls.user, name='Mine First Teacher', department_id=cls.mine.id)

    def _ids(self, model, name=''):
        return [result[0] for result in self.env[model].with_user(self.user).name_search(name, limit=100)]

    def test_a_department_reads_in_the_user_language(self):
        self.assertEqual(self.mine.with_context(lang='ca_ES').display_name, 'Zz Etapa Meva / Zz Informàtica Meva')
        self.assertEqual(self.mine.with_context(lang='en_US').display_name, 'Zz Mine Stage / Zz Mine Computing')

    def test_my_department_comes_first_and_the_rest_by_path(self):
        Department = self.env['hr.department'].with_user(self.user).with_context(lang='ca_ES')
        results = Department.name_search('', limit=100)
        self.assertEqual(results[0][0], self.mine.id)
        rest = [label.casefold() for _id, label in results[3:]]
        self.assertEqual(rest, sorted(rest))

    def test_my_area_comes_right_after_my_department(self):
        ids = self._ids('hr.department')
        self.assertEqual(ids[0], self.mine.id)
        self.assertEqual(set(ids[1:3]), {self.stage.id, self.sibling.id})

    def test_typing_a_translated_name_finds_the_departments_under_it(self):
        found = [result[0] for result in self.env['hr.department'].with_context(lang='ca_ES').name_search('Etapa Meva')]
        self.assertEqual(set(found), {self.stage.id, self.mine.id, self.sibling.id})

    def test_my_workgroup_comes_first(self):
        theirs = self.env['ems.workgroup'].create({'name': 'Aa Not Mine Workgroup'})
        mine = self.env['ems.workgroup'].create({'name': 'Zz Mine Workgroup', 'employee_ids': [(4, self.employee.id)]})
        ids = self._ids('ems.workgroup')
        self.assertEqual(ids[0], mine.id)
        self.assertIn(theirs.id, ids)

    def test_the_groups_i_tutor_or_teach_come_first(self):
        _level, study, tutored = create_level_study_group(self, 'MFG', group={'tutor_id': self.employee.id})
        taught = self.env['ems.group'].create({'course': 2, 'acronym': 'A', 'level_id': study.level_id.id, 'study_id': study.id})
        subject = self.env['ems.subject'].create({
            'code': 'MFG001', 'acronym': 'MFG', 'name': 'MFG Subject', 'study_ids': [(6, 0, study.ids)]})
        self.env['ems.teaching'].create({'teacher_id': self.employee.id, 'group_id': taught.id, 'subject_id': subject.id})
        ids = self._ids('ems.group')
        self.assertEqual(set(ids[:2]), {tutored.id, taught.id})

    def test_ids_from_the_view_take_over_mine(self):
        Department = self.env['hr.department'].with_user(self.user).with_context(ems_first_ids=[self.other.id])
        self.assertEqual(Department.name_search('', limit=100)[0][0], self.other.id)
