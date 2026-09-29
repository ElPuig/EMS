from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import (
    create_head_of_studies_branch, create_level_study_group, create_role_employee, create_role_user,
    next_student_id,
)


class TestTutorScope(TransactionCase):
    """Issue #483: hr.employee.tutor_scope_user_ids makes every chief above a tutor (Department
    Chief, Head of Studies, Director) that tutor's tutees' tutor too, for every tutor-scoped record
    rule and tutor check - along the real chain, not by role centre-wide."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_tutor_scope', name='TSC Tutor')
        cls.tutor = create_role_employee(cls, cls.tutor_user)
        create_head_of_studies_branch(cls, 'TSC', cls.tutor)
        __, __, group = create_level_study_group(cls, 'TSC', group={'tutor_id': cls.tutor.id})
        cls.student = cls.env['res.partner'].create({
            'name': 'Tutor Scope Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
        })
        cls.issue = cls.env['ems.attendance_issue_tutor'].create({
            'tutor_id': cls.tutor.id, 'issue_date': fields.Date.today(),
        })

    def _employees_tutored_by(self, user):
        return self.env['hr.employee'].search([('tutor_scope_user_ids', '=', user.id)])

    def test_scope_holds_tutor_and_chiefs_above(self):
        scope = self.tutor.tutor_scope_user_ids
        self.assertIn(self.tutor_user, scope)
        self.assertIn(self.department_chief, scope)
        self.assertIn(self.head_of_studies, scope)
        self.assertNotIn(self.other_department_chief, scope)
        self.assertNotIn(self.other_head_of_studies, scope)

    def test_seminar_chief_between_tutor_and_department_chief(self):
        seminar_user = create_role_user(self, 'department_chief', 'test_seminar_tutor_scope', name='TSC Seminar Chief')
        self.tutor.parent_id = create_role_employee(self, seminar_user, parent_id=self.tutor.parent_id.id)
        self.assertIn(seminar_user, self.tutor.tutor_scope_user_ids)
        self.assertIn(self.department_chief, self.tutor.tutor_scope_user_ids)
        self.assertIn(self.tutor, self._employees_tutored_by(self.department_chief))

    def test_scope_includes_director(self):
        director = create_role_user(self, 'director', 'test_director_tutor_scope', name='TSC Director')
        self.env.company.director_id = create_role_employee(self, director)
        self.assertIn(director, self.tutor.tutor_scope_user_ids)
        self.assertIn(self.tutor, self._employees_tutored_by(director))

    def test_search_matches_compute(self):
        self.assertIn(self.tutor, self._employees_tutored_by(self.head_of_studies))
        self.assertIn(self.tutor, self._employees_tutored_by(self.tutor_user))
        self.assertIn(self.tutor, self._employees_tutored_by(self.department_chief))
        self.assertNotIn(self.tutor, self._employees_tutored_by(self.other_head_of_studies))
        self.assertNotIn(self.tutor, self._employees_tutored_by(self.other_department_chief))

    def test_search_without_user_matches_nobody(self):
        self.assertFalse(self.env['hr.employee'].search([('tutor_scope_user_ids', '=', False)]))

    def test_chiefs_count_as_tutors(self):
        base = self.env['ems.base']
        for user, expected in ((self.department_chief, True), (self.head_of_studies, True),
                               (self.other_department_chief, False)):
            self.assertEqual(base.with_user(user).get_user_is_tutor(), expected)

    def test_justification_offers_branch_students(self):
        for user, expected in ((self.department_chief, True), (self.other_head_of_studies, False)):
            justification = self.env['ems.attendance_justification'].with_user(user).new(
                {'teacher_id': user.employee_id.id})
            justification._onchange_allowed_student_ids()
            self.assertEqual(self.student in justification.allowed_student_ids._origin, expected)

    def test_search_on_public_employee(self):
        public = self.env['hr.employee.public'].search([('tutor_scope_user_ids', 'in', [self.head_of_studies.id])])
        self.assertIn(self.tutor.id, public.ids)

    def test_hierarchy_change_applies_at_once(self):
        self.tutor.parent_id = self.other_head_of_studies.employee_id
        self.assertIn(self.other_head_of_studies, self.tutor.tutor_scope_user_ids)
        self.assertNotIn(self.head_of_studies, self.tutor.tutor_scope_user_ids)
        self.issue.with_user(self.other_head_of_studies).check_access('write')

    def test_record_rule_follows_hierarchy(self):
        for user in (self.tutor_user, self.department_chief, self.head_of_studies):
            self.issue.with_user(user).check_access('write')
        for user in (self.other_department_chief, self.other_head_of_studies):
            with self.assertRaises(AccessError):
                self.issue.with_user(user).check_access('write')

    def test_em_grading_picker_offers_branch_groups(self):
        Wizard = self.env['ems.em_grading_wizard']
        for user, expected in ((self.head_of_studies, True), (self.department_chief, True),
                               (self.other_department_chief, False), (self.other_head_of_studies, False)):
            groups = self.env['ems.group'].with_user(user).search(Wizard.with_user(user)._tutor_scope_domain())
            self.assertEqual(self.student.main_group_id in groups, expected)

    def test_tutor_checks_follow_hierarchy(self):
        for model in ('ems.portal.access.wizard', 'ems.graduation_wizard'):
            for user in (self.department_chief, self.head_of_studies):
                self.assertTrue(self.env[model].with_user(user)._user_can_manage(self.student))
            for user in (self.other_department_chief, self.other_head_of_studies):
                self.assertFalse(self.env[model].with_user(user)._user_can_manage(self.student))
