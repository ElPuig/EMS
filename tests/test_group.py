from odoo.exceptions import AccessError, RedirectWarning, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group


class TestGroup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Group)',
            'login': 'test_teacher_for_group',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.department_chief_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Department Chief (Group)',
            'login': 'test_department_chief_for_group',
            'groups_id': [(4, cls.env.ref('ems.group_department_chief').id)],
        })
        cls.head_of_studies_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Head of Studies (Group)',
            'login': 'test_head_of_studies_for_group',
            'groups_id': [(4, cls.env.ref('ems.group_head_of_studies').id)],
        })
        cls.test_level, cls.test_study, cls.test_group = create_level_study_group(cls, 'TSTG', level={'name': 'Test Level (Group)'}, study={
            'code': 'TSTG01', 'name': 'Test Study (Group)',
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

    def test_department_chief_can_write(self):
        self.test_group.with_user(self.department_chief_user).write({'course': 2})
        self.assertEqual(self.test_group.course, 2)

    def test_head_of_studies_can_write(self):
        self.test_group.with_user(self.head_of_studies_user).write({'course': 2})
        self.assertEqual(self.test_group.course, 2)

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_group.with_user(self.teacher_user).write({'course': 2})

    def test_teacher_can_read(self):
        group = self.test_group.with_user(self.teacher_user)
        self.assertEqual(group.acronym, 'A')

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.group'].with_user(self.teacher_user).create({
                'course': 1,
                'acronym': 'C',
                'level_id': self.test_level.id,
                'study_id': self.test_study.id,
            })

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_group.with_user(self.teacher_user).unlink()

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
            'name': 'Reinforcement Student A', 'contact_type': 'student', 'main_group_id': self.test_group.id,
        })
        student_b = self.env['res.partner'].create({
            'name': 'Reinforcement Student B', 'contact_type': 'student', 'main_group_id': other_group.id,
        })
        group = self.env['ems.group'].create({
            'group_type': 'reinforcement',
            'name': 'REF-MATHS',
            'reinforcement_student_ids': [(6, 0, [student_a.id, student_b.id])],
        })
        self.assertTrue(group.id)
        self.assertEqual(group.name, 'REF-MATHS')
        self.assertEqual(group.reinforcement_student_ids, student_a | student_b)

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

    def test_switching_main_group_with_students_to_reinforcement_raises(self):
        self.env['res.partner'].create({
            'name': 'Main Student (Group)', 'contact_type': 'student', 'main_group_id': self.test_group.id,
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
        group.write({'group_type': 'reinforcement', 'name': 'REF-EMPTY'})
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
            'name': 'Test Enrolled Student (Group)', 'contact_type': 'student',
        })
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.test_group.id, 'subject_id': self._enrollment_subject().id,
        })
        self.assertIn(student, self.test_group.enrolled_student_ids)

    def test_enrollment_view_ids_aggregates_subjects_per_student(self):
        student = self.env['res.partner'].create({
            'name': 'Test Enrollment View Student (Group)', 'contact_type': 'student',
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
            'name': 'Test Enrollment Refresh Student (Group)', 'contact_type': 'student',
        })
        enrollment = self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.test_group.id, 'subject_id': self._enrollment_subject().id,
        })
        self.assertEqual(len(self.test_group.enrollment_view_ids), 1)

        enrollment.unlink()
        self.test_group.invalidate_recordset(['enrollment_view_ids'])
        self.assertFalse(self.test_group.enrollment_view_ids)

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
            'name': 'Active Main Student (Group Archive)', 'contact_type': 'student',
            'main_group_id': self.test_group.id,
        })
        with self.assertRaises(RedirectWarning):
            self.test_group.write({'active': False})
        self.assertTrue(self.test_group.active)

    def test_archive_group_with_active_reinforcement_students_raises_confirmation(self):
        student = self.env['res.partner'].create({
            'name': 'Active Reinforcement Student (Group Archive)', 'contact_type': 'student',
        })
        reinforcement_group = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'REF-ARCHIVE-TEST',
            'reinforcement_student_ids': [(6, 0, [student.id])],
        })
        with self.assertRaises(RedirectWarning):
            reinforcement_group.write({'active': False})
        self.assertTrue(reinforcement_group.active)

    def test_archive_group_ignores_already_archived_reinforcement_students(self):
        student = self.env['res.partner'].create({
            'name': 'Archived Reinforcement Student (Group Archive)', 'contact_type': 'student',
        })
        reinforcement_group = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'REF-ARCHIVE-TEST-2',
            'reinforcement_student_ids': [(6, 0, [student.id])],
        })
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
            'name': 'Active Main Student (Group Confirm Archive)', 'contact_type': 'student',
            'main_group_id': self.test_group.id,
        })
        self.test_group.action_confirm_archive()
        self.assertFalse(self.test_group.active)

    def test_get_archive_confirmation_message_false_when_no_active_students(self):
        self.assertFalse(self.test_group.get_archive_confirmation_message())

    def test_get_archive_confirmation_message_mentions_the_count(self):
        self.env['res.partner'].create({
            'name': 'Active Main Student (Group Archive Message)', 'contact_type': 'student',
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

    def test_custom_data_records_are_frozen_against_future_upgrades(self):
        # 'data/custom/ems.group.csv' seeds the centre's real groups only once: an admin renaming
        # a group or reassigning its classroom through the app is 'living' data, not config this
        # repo's CSV should keep re-pushing on every upgrade (see CLAUDE.md's "Data folder
        # conventions"). '_ems_freeze_living_custom_data' (models/settings/company.py) already ran
        # as part of this test run's own module (re)load via '_register_hook()', so every
        # '__import__'-owned 'ems.group' xmlid must already be noupdate=True by the time tests execute.
        custom_group_data = self.env['ir.model.data'].sudo().search([
            ('module', '=', '__import__'), ('model', '=', 'ems.group'),
        ])
        self.assertTrue(custom_group_data)
        self.assertTrue(all(custom_group_data.mapped('noupdate')))

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
