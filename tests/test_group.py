from odoo.exceptions import AccessError, RedirectWarning, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval

from .common import create_level_study_group, create_role_user, next_student_id


class TestGroup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Group)',
            'login': 'test_teacher_for_group',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.test_level, cls.test_study, cls.test_group = create_level_study_group(cls, 'TSTG', level={'name': 'Test Level (Group)'}, study={
            'code': 'TSTG01', 'name': 'Test Study (Group)',
        })

    def _main_student(self, name, group=None):
        return self.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': (group or self.test_group).id,
        })

    def test_create_valid(self):
        group = self.env['ems.group'].create({
            'course': 1,
            'acronym': 'B',
            'level_id': self.test_level.id,
            'study_id': self.test_study.id,
        })
        self.assertTrue(group.id)
        self.assertEqual(group.name, f"{self.test_study.acronym}1B")

    def test_create_reinforcement_group(self):
        other_study = self.env['ems.study'].create({
            'code': 'TSTG02',
            'acronym': 'TSTB',
            'name': 'Test Other Study (Group)',
            'date': '2026-01-01',
            'deprecated': False,
            'level_id': self.test_level.id,
        })
        other_group = self.env['ems.group'].create({
            'course': 1,
            'acronym': 'A',
            'level_id': self.test_level.id,
            'study_id': other_study.id,
        })
        student_a = self.env['res.partner'].create({
            'name': 'Reinforcement Student A', 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': self.test_group.id,
        })
        student_b = self.env['res.partner'].create({
            'name': 'Reinforcement Student B', 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': other_group.id,
        })
        group = self.env['ems.group'].create({
            'group_type': 'reinforcement',
            'name': 'REF-MATHS',
        })
        subject = self._enrollment_subject('REF')
        self.env['ems.enrollment'].create({'student_id': student_a.id, 'group_id': group.id, 'subject_id': subject.id})
        self.env['ems.enrollment'].create({'student_id': student_b.id, 'group_id': group.id, 'subject_id': subject.id})
        group.invalidate_recordset(['enrolled_student_ids'])
        self.assertTrue(group.id)
        self.assertEqual(group.name, 'REF-MATHS')
        self.assertEqual(group.enrolled_student_ids, student_a | student_b)

    def test_main_group_without_study_raises(self):
        with self.assertRaises(ValidationError):
            self.env['ems.group'].create({
                'course': 1,
                'acronym': 'D',
                'level_id': self.test_level.id,
            })

    def test_reinforcement_group_with_level_raises(self):
        with self.assertRaises(ValidationError):
            self.env['ems.group'].create({
                'group_type': 'reinforcement',
                'name': 'REF-INVALID',
                'level_id': self.test_level.id,
            })

    def test_reinforcement_group_with_subdelegate_raises(self):
        student = self._main_student('Sub-delegate (Reinforcement)')
        with self.assertRaises(ValidationError):
            self.env['ems.group'].create({
                'group_type': 'reinforcement',
                'name': 'REF-SUBDELEGATE',
                'subdelegate_id': student.id,
            })

    def test_delegate_and_subdelegate_must_differ(self):
        """Issue #574: the sub-delegate stands in for the delegate, so it can't be the same student."""
        student = self._main_student('Delegate and Sub-delegate')
        self.test_group.delegate_id = student
        with self.assertRaises(ValidationError):
            self.test_group.subdelegate_id = student

    def test_subdelegate_domain_excludes_the_delegate(self):
        delegate = self._main_student('Delegate (Domain)')
        other = self._main_student('Classmate (Domain)')
        self.test_group.delegate_id = delegate
        domain = safe_eval(self.test_group._fields['subdelegate_id'].domain,
                           {'id': self.test_group.id, 'delegate_id': delegate.id})
        candidates = self.env['res.partner'].search(domain)
        self.assertIn(other, candidates)
        self.assertNotIn(delegate, candidates)

    def test_clear_stale_delegate_clears_only_the_leaving_students_role(self):
        """A student who leaves the group stops being its delegate or its sub-delegate, and only that."""
        delegate = self._main_student('Delegate (Stale)')
        subdelegate = self._main_student('Sub-delegate (Stale)')
        self.test_group.write({'delegate_id': delegate.id, 'subdelegate_id': subdelegate.id})
        subdelegate._ems_clear_stale_delegate(self.test_group)
        self.assertEqual(self.test_group.delegate_id, delegate)
        self.assertFalse(self.test_group.subdelegate_id)
        delegate._ems_clear_stale_delegate(self.test_group)
        self.assertFalse(self.test_group.delegate_id)

    def test_switching_main_group_with_students_to_reinforcement_raises(self):
        self.env['res.partner'].create({
            'name': 'Main Student (Group)', 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': self.test_group.id,
        })
        # '_sanitize_group_type_vals' clears every 'main'-only field on this same write() — the
        # still-enrolled main student alone (a res.partner, not a field of this record) is what must
        # block the switch here.
        with self.assertRaises(ValidationError):
            self.test_group.write({'group_type': 'reinforcement', 'name': 'REF-CONVERTED'})

    def test_switching_main_group_to_reinforcement_clears_incompatible_fields(self):
        # Regression test: converting an existing 'main' group used to keep failing
        # '_check_group_type_fields' because only the client-side onchange cleared these fields —
        # a plain write() with just 'group_type' (what a real Save sends when nothing else changed)
        # never touched them. '_sanitize_group_type_vals' (write()) must clear them itself.
        group = self.env['ems.group'].create({
            'course': 1,
            'acronym': 'E',
            'level_id': self.test_level.id,
            'study_id': self.test_study.id,
        })
        delegate = self._main_student('Delegate (Switch)', group)
        subdelegate = self._main_student('Sub-delegate (Switch)', group)
        group.write({'delegate_id': delegate.id, 'subdelegate_id': subdelegate.id})
        # Students out of the group first: with them still in it the switch is refused (above).
        (delegate | subdelegate).main_group_id = False
        group.write({'group_type': 'reinforcement', 'name': 'REF-EMPTY'})
        self.assertFalse(group.delegate_id)
        self.assertFalse(group.subdelegate_id)
        self.assertEqual(group.group_type, 'reinforcement')
        self.assertFalse(group.level_id)
        self.assertFalse(group.study_id)
        self.assertFalse(group.course)
        self.assertFalse(group.acronym)

    def test_create_with_tutor_already_set_syncs_role(self):
        # Regression test: create() used to skip the Tutor-role/security-group sync that
        # write() already did on tutor_id changes — a group created with tutor_id passed
        # directly in the create() vals (rather than assigned via a later write()) left the
        # tutorship_ids relation correct (it's just the inverse of tutor_id) but never
        # granted ems.role_tutor or synced the employee's security groups, until someone
        # happened to re-save the tutor field later.
        role_tutor = self.env.ref('ems.role_tutor')
        teacher = self.env['hr.employee'].create({
            'name': 'Test Tutor (Group Create Sync)', 'employee_type': 'teacher',
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'F',
            'level_id': self.test_level.id, 'study_id': self.test_study.id,
            'tutor_id': teacher.id,
        })
        self.assertIn(group, teacher.tutorship_ids)
        self.assertIn(role_tutor, teacher.role_ids)

    def test_enrolled_student_ids_from_enrollment_lines(self):
        student = self.env['res.partner'].create({
            'name': 'Test Enrolled Student (Group)', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.test_group.id, 'subject_id': self._enrollment_subject().id,
        })
        self.assertIn(student, self.test_group.enrolled_student_ids)

    def test_enrollment_view_ids_aggregates_subjects_per_student(self):
        student = self.env['res.partner'].create({
            'name': 'Test Enrollment View Student (Group)', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        subject_a = self._enrollment_subject('A')
        subject_b = self._enrollment_subject('B')
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.test_group.id, 'subject_id': subject_a.id,
        })
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.test_group.id, 'subject_id': subject_b.id,
        })

        lines = self.test_group.enrollment_view_ids
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.student_id, student)
        self.assertEqual(lines.subject_ids, subject_a | subject_b)

    def test_enrollment_view_ids_refreshes_on_recompute(self):
        # Regression-style check for the compute's own delete+recreate side effect: stale
        # rows from a prior computation must not linger once the underlying enrollments change.
        student = self.env['res.partner'].create({
            'name': 'Test Enrollment Refresh Student (Group)', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        enrollment = self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.test_group.id, 'subject_id': self._enrollment_subject().id,
        })
        self.assertEqual(len(self.test_group.enrollment_view_ids), 1)

        enrollment.unlink()
        self.test_group.invalidate_recordset(['enrollment_view_ids'])
        self.assertFalse(self.test_group.enrollment_view_ids)

    def test_enrollment_view_ids_readable_by_a_plain_teacher(self):
        # Regression (found 2026-09-06): the compute's own delete+recreate of ems.enrollment_view
        # rows used to run as whoever opened the group's form. ems.enrollment_view's ACL grants
        # teacher/tutor only perm_read (by design - it's a read-only helper view), so a plain
        # teacher/tutor got an AccessError from simply reading enrollment_view_ids at all, on
        # ANY group - not something specific to this test's own data.
        student = self.env['res.partner'].create({
            'name': 'Test Enrollment View Teacher Student (Group)', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.test_group.id, 'subject_id': self._enrollment_subject().id,
        })
        self.test_group.invalidate_recordset(['enrollment_view_ids'])

        lines = self.test_group.with_user(self.teacher_user).enrollment_view_ids

        self.assertEqual(lines.student_id, student)

    def _enrollment_subject(self, suffix=''):
        return self.env['ems.subject'].create({
            'code': f'TSTG-ENR{suffix}', 'acronym': f'TGE{suffix}', 'name': f'Test Enrollment Subject {suffix}',
        })

    def test_active_defaults_true(self):
        self.assertTrue(self.test_group.active)

    def test_can_archive_group(self):
        self.test_group.active = False
        self.assertFalse(self.test_group.active)

    def test_create_with_archived_duplicate_name_raises_and_creates_nothing(self):
        # A group not running this course may come back in a future one - archiving it (instead
        # of deleting it) must mean re-creating the exact same name later offers to reactivate
        # it, rather than silently creating a second record with the same name.
        name = self.test_group.name
        self.test_group.active = False
        with self.assertRaises(RedirectWarning):
            self.env['ems.group'].create({
                'course': 1, 'acronym': 'A',
                'level_id': self.test_level.id, 'study_id': self.test_study.id,
            })
        self.assertEqual(
            self.env['ems.group'].with_context(active_test=False).search_count([('name', '=', name)]), 1,
        )

    def test_write_rename_into_archived_duplicate_name_raises_and_reverts(self):
        # Renaming an existing active group (via course/acronym, which 'name' is computed from)
        # into an archived group's name is the same duplicate-by-rename risk as create() above -
        # the write() must be rolled back entirely, not leave the rename half-applied.
        other = self.env['ems.group'].create({
            'course': 9, 'acronym': 'Z',
            'level_id': self.test_level.id, 'study_id': self.test_study.id,
        })
        other.active = False
        with self.assertRaises(RedirectWarning):
            self.test_group.write({'course': 9, 'acronym': 'Z'})
        self.assertEqual(self.test_group.course, 1)
        self.assertEqual(self.test_group.acronym, 'A')

    def test_archive_group_with_active_main_students_raises_confirmation(self):
        self.env['res.partner'].create({
            'name': 'Active Main Student (Group Archive)', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.test_group.id,
        })
        with self.assertRaises(RedirectWarning):
            self.test_group.write({'active': False})
        self.assertTrue(self.test_group.active)

    def test_archive_group_with_active_reinforcement_students_raises_confirmation(self):
        student = self.env['res.partner'].create({
            'name': 'Active Reinforcement Student (Group Archive)', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        reinforcement_group = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'REF-ARCHIVE-TEST',
        })
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': reinforcement_group.id, 'subject_id': self._enrollment_subject('ARCH1').id,
        })
        reinforcement_group.invalidate_recordset(['enrolled_student_ids'])
        with self.assertRaises(RedirectWarning):
            reinforcement_group.write({'active': False})
        self.assertTrue(reinforcement_group.active)

    def test_archive_group_ignores_already_archived_reinforcement_students(self):
        student = self.env['res.partner'].create({
            'name': 'Archived Reinforcement Student (Group Archive)', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        reinforcement_group = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'REF-ARCHIVE-TEST-2',
        })
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': reinforcement_group.id, 'subject_id': self._enrollment_subject('ARCH2').id,
        })
        reinforcement_group.invalidate_recordset(['enrolled_student_ids'])
        student.active = False
        reinforcement_group.write({'active': False})
        self.assertFalse(reinforcement_group.active)

    def test_archive_empty_group_does_not_raise(self):
        group = self.env['ems.group'].create({
            'course': 8, 'acronym': 'Y',
            'level_id': self.test_level.id, 'study_id': self.test_study.id,
        })
        group.write({'active': False})
        self.assertFalse(group.active)

    def test_action_confirm_archive_actually_archives(self):
        self.env['res.partner'].create({
            'name': 'Active Main Student (Group Confirm Archive)', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.test_group.id,
        })
        self.test_group.action_confirm_archive()
        self.assertFalse(self.test_group.active)

    def test_get_archive_confirmation_message_false_when_no_active_students(self):
        self.assertFalse(self.test_group.get_archive_confirmation_message())

    def test_get_archive_confirmation_message_mentions_the_count(self):
        self.env['res.partner'].create({
            'name': 'Active Main Student (Group Archive Message)', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.test_group.id,
        })
        message = self.test_group.get_archive_confirmation_message()
        self.assertIn('1', message)
        self.assertIn('archive this group anyway', message)

    def test_action_reactivate_sets_active_and_returns_form_action(self):
        self.test_group.active = False
        action = self.test_group.action_reactivate()
        self.assertTrue(self.test_group.active)
        self.assertEqual(action['res_model'], 'ems.group')
        self.assertEqual(action['res_id'], self.test_group.id)
        self.assertEqual(action['type'], 'ir.actions.act_window')

    def test_compute_name_leaves_blank_for_incomplete_main_group(self):
        # Regression test: '_compute_name' used to build "%s%s%s" % (study_id.acronym, course, acronym)
        # unconditionally for 'main' groups, rendering the literal "False0False" whenever those fields
        # were still empty — exactly the transient state seen live in the form (before Save enforces
        # '_check_group_type_fields') right after switching a reinforcement group back to 'main', since
        # a reinforcement group never has study/course/acronym set. This exercises the compute directly,
        # the same way it runs during that in-form editing (constraints don't apply until Save).
        group = self.env['ems.group'].new({'group_type': 'main'})
        group._compute_name()
        self.assertFalse(group.name)

    # Main groups of a reinforcement group filled from its enrolled students (issue #645 follow-up).

    def _reinforcement_with_students(self):
        """A reinforcement group with two enrolled students of test_group and one of another main
        group, and an archived student of a third one."""
        other = self.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'level_id': self.test_level.id, 'study_id': self.test_study.id})
        third = self.env['ems.group'].create({
            'course': 2, 'acronym': 'B', 'level_id': self.test_level.id, 'study_id': self.test_study.id})
        group = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'REF-PARENTS'})
        subject = self._enrollment_subject('PAR')
        students = (self._main_student('Parents Student 1') | self._main_student('Parents Student 2')
                    | self._main_student('Parents Student 3', other))
        archived = self._main_student('Parents Student 4', third)
        for student in students | archived:
            self.env['ems.enrollment'].create({'student_id': student.id, 'group_id': group.id, 'subject_id': subject.id})
        archived.active = False
        group.invalidate_recordset()
        return group, other, third

    def test_a_reinforcement_group_lists_its_students_main_groups_not_set(self):
        group, other, _third = self._reinforcement_with_students()

        self.assertEqual(group.missing_parent_group_ids, self.test_group | other,
                         "an archived student's main group is not one to add")
        group.parent_group_ids = self.test_group
        self.assertEqual(group.missing_parent_group_ids, other)
        self.assertFalse(self.test_group.missing_parent_group_ids, "a main group has no main groups")

    def test_filling_the_main_groups_adds_those_of_its_students_and_keeps_the_rest(self):
        group, other, third = self._reinforcement_with_students()
        group.parent_group_ids = third
        chief = create_role_user(self, 'department_chief', 'test_parents_chief')
        with self.assertRaises(AccessError):
            group.with_user(self.teacher_user).action_fill_parent_groups()

        group.with_user(chief).action_fill_parent_groups()

        self.assertEqual(group.parent_group_ids, self.test_group | other | third,
                         "a main group set by hand (its students not enrolled yet, say) stays")
        self.assertFalse(group.missing_parent_group_ids)

    def test_joins_with_is_mutual(self):
        """Issue #676: setting a group's other halves on one of them sets it on the others, on
        create and on write, and removing one removes it from both."""
        half_b, half_c = self.env['ems.group'].create([{'group_type': 'reinforcement', 'name': f'Test Half {half}'}
                                                       for half in 'BC'])
        self.test_group.joinable_group_ids = half_b | half_c

        self.assertEqual((half_b.joinable_group_ids, half_c.joinable_group_ids), (self.test_group, self.test_group))
        half_b.joinable_group_ids = False
        self.assertEqual(self.test_group.joinable_group_ids, half_c)
        new = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'Test Half D',
                                            'joinable_group_ids': [(6, 0, half_c.ids)]})
        self.assertEqual(half_c.joinable_group_ids, self.test_group | new)
