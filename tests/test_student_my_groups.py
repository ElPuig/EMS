# -*- coding: utf-8 -*-
"""Issue #421 - the Students action opens filtered to the current user's own groups.

See docs/en/developers/contacts/contact.md, "is_my_student / _search_is_my_student".
"""

from odoo.tests.common import TransactionCase

from .common import create_level_study_group, next_student_id


class TestStudentMyGroups(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']

        cls.level, cls.study, cls.taught_group = create_level_study_group(
            cls, 'MYG', group={'acronym': 'A'})
        cls.other_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.tutored_group = cls.env['ems.group'].create({
            'course': 2, 'acronym': 'C', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.reinforcement_group = cls.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'Test Reinforcement Group (My Groups)',
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'MYG001', 'acronym': 'MYG', 'name': 'Test Subject (My Groups)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        # Taught in the same groups, but by somebody else.
        cls.other_subject = cls.env['ems.subject'].create({
            'code': 'MYG002', 'acronym': 'MYG2', 'name': 'Test Other Subject (My Groups)',
            'study_ids': [(6, 0, [cls.study.id])],
        })

        # The students. 'own_student' is in the taught group; 'other_student' is in a group
        # nobody in this test teaches; 'reinforcement_student' keeps 'other_group' as their main
        # group and reaches the reinforcement one only through an ems.enrollment row - the case
        # a plain main_group_id domain misses.
        cls.own_student = cls.Partner.create({
            'name': 'Test Own Student (My Groups)', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.taught_group.id,
        })
        cls.other_student = cls.Partner.create({
            'name': 'Test Other Student (My Groups)', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.other_group.id,
        })
        cls.tutored_student = cls.Partner.create({
            'name': 'Test Tutored Student (My Groups)', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.tutored_group.id,
        })
        cls.reinforcement_student = cls.Partner.create({
            'name': 'Test Reinforcement Student (My Groups)', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.other_group.id,
        })
        cls.env['ems.enrollment'].create({
            'student_id': cls.reinforcement_student.id, 'group_id': cls.reinforcement_group.id,
            'subject_id': cls.subject.id,
        })

        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (My Groups)', 'login': 'test_teacher_my_groups',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (My Groups)', 'employee_type': 'teacher',
            'user_id': cls.teacher_user.id,
        })
        cls.env['ems.teaching'].create({
            'teacher_id': cls.teacher.id, 'group_id': cls.taught_group.id,
            'subject_id': cls.subject.id,
        })

        # A user with an employee but no groups at all: the administration/secretariat case.
        cls.staff_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Staff (My Groups)', 'login': 'test_staff_my_groups',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.staff = cls.env['hr.employee'].create({
            'name': 'Test Staff (My Groups)', 'user_id': cls.staff_user.id,
        })

    def _search_as(self, user, extra_domain=None):
        """The students the 'My students' facet would show 'user', restricted to this test's
        own fixtures so the ~1000 real students in the dev DB can't mask a wrong result."""
        domain = [('is_my_student', '=', True), ('name', 'like', '(My Groups)')]
        return self.Partner.with_user(user).search(domain + (extra_domain or []))

    def test_teacher_sees_only_their_taught_group(self):
        students = self._search_as(self.teacher_user)
        self.assertIn(self.own_student, students)
        self.assertNotIn(self.other_student, students)

    def test_teacher_sees_reinforcement_group_students(self):
        # The student's main_group_id is a group this teacher does NOT teach: only their
        # ems.enrollment in the reinforcement group puts them in scope.
        self.env['ems.teaching'].create({
            'teacher_id': self.teacher.id, 'group_id': self.reinforcement_group.id,
            'subject_id': self.subject.id,
        })
        students = self._search_as(self.teacher_user)
        self.assertIn(self.reinforcement_student, students)
        self.assertNotIn(self.other_student, students)

    def test_teacher_sees_hand_assigned_tutored_group(self):
        # tutor_id set directly on the group form, with no ems.teaching row backing it.
        self.tutored_group.tutor_id = self.teacher
        students = self._search_as(self.teacher_user)
        self.assertIn(self.tutored_student, students)
        self.assertIn(self.own_student, students)
        self.assertNotIn(self.other_student, students)

    def test_repeater_enrolled_in_someone_elses_subject_is_excluded(self):
        # Found in production 2026-09-09: a repeater from a higher course carries a failed
        # subject down into one of my groups. They are only mine if the subject is one I
        # actually teach there - matching on the group alone showed a teacher of SMX1A/SMX1B
        # 19 students of SMX2A/SMX2B on the strength of another teacher's subject.
        repeater = self.Partner.create({
            'name': 'Test Repeater Student (My Groups)', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.other_group.id,
        })
        self.env['ems.enrollment'].create({
            'student_id': repeater.id, 'group_id': self.taught_group.id,
            'subject_id': self.other_subject.id,
        })
        self.assertNotIn(repeater, self._search_as(self.teacher_user))
        # ...and is picked up as soon as they take a subject this teacher does teach there.
        self.env['ems.enrollment'].create({
            'student_id': repeater.id, 'group_id': self.taught_group.id,
            'subject_id': self.subject.id,
        })
        self.assertIn(repeater, self._search_as(self.teacher_user))

    def test_user_without_groups_is_not_filtered(self):
        # The whole point of the empty-domain branch: administration/secretariat keep seeing
        # everyone even though the default facet is applied to them too.
        students = self._search_as(self.staff_user)
        self.assertIn(self.own_student, students)
        self.assertIn(self.other_student, students)

    def test_filter_combines_with_students_only(self):
        # The two facets must AND: an alumni of the taught group is 'mine' but not a student.
        alumni = self.Partner.create({
            'name': 'Test Own Alumni (My Groups)', 'contact_type': 'alumni', 'student_id': next_student_id(),
            'main_group_id': self.taught_group.id,
        })
        mine = self._search_as(self.teacher_user)
        self.assertIn(alumni, mine)
        mine_and_students_only = self._search_as(
            self.teacher_user, [('contact_type', '=', 'student')])
        self.assertNotIn(alumni, mine_and_students_only)
        self.assertIn(self.own_student, mine_and_students_only)

    def test_compute_matches_search(self):
        self.assertTrue(self.own_student.with_user(self.teacher_user).is_my_student)
        self.assertFalse(self.other_student.with_user(self.teacher_user).is_my_student)

    def test_unsupported_operator_raises(self):
        with self.assertRaises(NotImplementedError):
            self.Partner.search([('is_my_student', 'like', 'whatever')])
