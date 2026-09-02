from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group


class TestTeaching(TransactionCase):
    """sync_from_schedule() is already covered by test_ems_teaching_sync.py — this file
    covers the model's own CRUD/constraint/access behaviour."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Teaching)',
            'login': 'test_teacher_for_teaching',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Teaching)',
            'login': 'test_secretary_for_teaching',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teaching Teacher', 'employee_type': 'teacher',
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TST_TCH_SUBJ', 'acronym': 'TTS', 'name': 'Test Subject for Teaching',
        })
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TSTT', level={'name': 'Test Level (Teaching)'}, study={
            'code': 'TSTT01', 'name': 'Test Study (Teaching)',
        }, group={'acronym': 'TT1'})
        cls.test_teaching = cls.env['ems.teaching'].create({
            'teacher_id': cls.teacher.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id,
        })

    def test_create_valid(self):
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TT2', 'level_id': self.level.id, 'study_id': self.study.id,
        })
        teaching = self.env['ems.teaching'].create({
            'teacher_id': self.teacher.id, 'group_id': group.id, 'subject_id': self.subject.id,
        })
        self.assertTrue(teaching.id)

    def test_create_missing_teacher(self):
        with self.assertRaises(Exception):
            self.env['ems.teaching'].create({'group_id': self.group.id, 'subject_id': self.subject.id})

    def test_create_missing_group(self):
        with self.assertRaises(Exception):
            self.env['ems.teaching'].create({'teacher_id': self.teacher.id, 'subject_id': self.subject.id})

    def test_create_missing_subject(self):
        with self.assertRaises(Exception):
            self.env['ems.teaching'].create({'teacher_id': self.teacher.id, 'group_id': self.group.id})

    def test_duplicate_active_triple_blocked(self):
        with self.assertRaises(ValidationError):
            self.env['ems.teaching'].create({
                'teacher_id': self.teacher.id, 'group_id': self.group.id, 'subject_id': self.subject.id,
            })

    def test_archived_duplicate_allowed(self):
        self.test_teaching.active = False
        teaching = self.env['ems.teaching'].create({
            'teacher_id': self.teacher.id, 'group_id': self.group.id, 'subject_id': self.subject.id,
        })
        self.assertTrue(teaching.id)

    def test_display_name_is_subject_display_name(self):
        self.assertEqual(self.test_teaching.display_name, self.subject.display_name)

    def test_inuse_group_ids_excludes_other_subjects(self):
        other_subject = self.env['ems.subject'].create({
            'code': 'TST_TCH_SUBJ2', 'acronym': 'TTS2', 'name': 'Other Subject',
        })
        teaching = self.env['ems.teaching'].new({
            'teacher_id': self.teacher.id, 'subject_id': other_subject.id,
        })
        self.assertNotIn(self.group.id, teaching.inuse_group_ids.ids)

    def test_admin_can_unlink(self):
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TT3', 'level_id': self.level.id, 'study_id': self.study.id,
        })
        teaching = self.env['ems.teaching'].create({
            'teacher_id': self.teacher.id, 'group_id': group.id, 'subject_id': self.subject.id,
        })
        teaching_id = teaching.id
        teaching.unlink()
        self.assertFalse(self.env['ems.teaching'].search([('id', '=', teaching_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.teaching'].with_user(self.teacher_user).create({
                'teacher_id': self.teacher.id, 'group_id': self.group.id, 'subject_id': self.subject.id,
            })

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_teaching.with_user(self.teacher_user).write({'notes': 'x'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_teaching.with_user(self.teacher_user).unlink()

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.teaching'].with_user(self.secretary_user).create({
                'teacher_id': self.teacher.id, 'group_id': self.group.id, 'subject_id': self.subject.id,
            })

    # --- unlink() clearing a stale ems.group.tutor_id (2026-09-01) ---------------------------
    # See plans/course_transition_stale_teacher_assignments.md - a group's tutoring is itself
    # recorded as an ordinary ems.teaching row on the group's own tutoring subject
    # (subject_id.is_tutorship); losing that row must not leave tutor_id pointing at a teacher
    # who no longer actually holds the tutorship.

    def test_unlink_tutorship_teaching_clears_group_tutor(self):
        tutorship_subject = self.env['ems.subject'].create({
            'code': 'TST_TCH_TUT', 'acronym': 'TUTT', 'name': 'Test Tutorship Subject', 'is_tutorship': True,
        })
        group = self.env['ems.group'].create({
            'course': 5, 'acronym': 'TT9', 'level_id': self.level.id, 'study_id': self.study.id,
            'tutor_id': self.teacher.id,
        })
        teaching = self.env['ems.teaching'].create({
            'teacher_id': self.teacher.id, 'group_id': group.id, 'subject_id': tutorship_subject.id,
        })

        teaching.unlink()

        self.assertFalse(group.tutor_id)

    def test_unlink_non_tutorship_teaching_leaves_tutor_untouched(self):
        group = self.env['ems.group'].create({
            'course': 6, 'acronym': 'TT10', 'level_id': self.level.id, 'study_id': self.study.id,
            'tutor_id': self.teacher.id,
        })
        teaching = self.env['ems.teaching'].create({
            'teacher_id': self.teacher.id, 'group_id': group.id, 'subject_id': self.subject.id,
        })

        teaching.unlink()

        self.assertEqual(group.tutor_id, self.teacher)

    def test_unlink_tutorship_teaching_leaves_a_different_current_tutor_untouched(self):
        # A manual reassignment in between must never be clobbered by a stale unlink - the
        # cleanup only ever fires while 'tutor_id' still matches the teacher losing the row.
        tutorship_subject = self.env['ems.subject'].create({
            'code': 'TST_TCH_TUT2', 'acronym': 'TUTT2', 'name': 'Test Tutorship Subject 2', 'is_tutorship': True,
        })
        other_teacher = self.env['hr.employee'].create({
            'name': 'Test Teaching Teacher Other', 'employee_type': 'teacher',
        })
        group = self.env['ems.group'].create({
            'course': 7, 'acronym': 'TT11', 'level_id': self.level.id, 'study_id': self.study.id,
            'tutor_id': self.teacher.id,
        })
        teaching = self.env['ems.teaching'].create({
            'teacher_id': self.teacher.id, 'group_id': group.id, 'subject_id': tutorship_subject.id,
        })
        group.tutor_id = other_teacher.id

        teaching.unlink()

        self.assertEqual(group.tutor_id, other_teacher)
