from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


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
        cls.test_level = cls.env['ems.level'].create({
            'acronym': 'TSTG',
            'name': 'Test Level (Group)',
        })
        cls.test_study = cls.env['ems.study'].create({
            'code': 'TSTG01',
            'acronym': 'TSTG',
            'name': 'Test Study (Group)',
            'date': '2026-01-01',
            'deprecated': False,
            'level_id': cls.test_level.id,
        })
        cls.test_group = cls.env['ems.group'].create({
            'course': 1,
            'acronym': 'A',
            'level_id': cls.test_level.id,
            'study_id': cls.test_study.id,
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
