from datetime import date

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestPlanningAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Planning)',
            'login': 'test_teacher_for_planning',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Planning) Employee', 'user_id': cls.teacher_user.id, 'employee_type': 'teacher',
        })

        cls.level = cls.env['ems.level'].create({'acronym': 'TPL', 'name': 'Test Planning Level'})
        cls.study = cls.env['ems.study'].create({
            'code': 'TPLSTD', 'acronym': 'TPS', 'name': 'Test Planning Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })

        cls.subject_taught = cls._make_subject('TPLSB1', 'TPB1', 'Taught Subject')
        cls.subject_other = cls._make_subject('TPLSB2', 'TPB2', 'Other Subject')
        cls.planning_taught = cls._make_planning(cls.subject_taught)
        cls.planning_other = cls._make_planning(cls.subject_other)

        # The teacher only teaches subject_taught.
        cls.env['ems.teaching'].create({
            'teacher_id': cls.teacher_employee.id, 'group_id': cls.group.id, 'subject_id': cls.subject_taught.id,
        })

    @classmethod
    def _make_subject(cls, code, acronym, name):
        subject = cls.env['ems.subject'].create({
            'code': code, 'acronym': acronym, 'name': name, 'study_ids': [(4, cls.study.id)],
        })
        cls.env['ems.outcome'].create({
            'code': code + '_01RA', 'acronym': 'RA1', 'name': 'Outcome', 'subject_id': subject.id,
        })
        return subject

    @classmethod
    def _make_planning(cls, subject):
        return cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': subject.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': subject.outcome_ids[0].id, 'ponderation': 100.0})],
        })

    def test_teacher_sees_only_taught_plannings(self):
        visible = self.env['ems.planning'].with_user(self.teacher_user).search([
            ('id', 'in', [self.planning_taught.id, self.planning_other.id]),
        ])
        self.assertIn(self.planning_taught, visible)
        self.assertNotIn(self.planning_other, visible)

    def test_teacher_cannot_write_planning(self):
        with self.assertRaises(AccessError):
            self.planning_taught.with_user(self.teacher_user).write({
                'internal_ponderation': 80.0, 'external_ponderation': 20.0,
            })

    def test_teacher_cannot_read_untaught_planning(self):
        with self.assertRaises(AccessError):
            self.planning_other.with_user(self.teacher_user).read(['name'])

    def test_admin_can_write_planning(self):
        self.planning_taught.write({'internal_ponderation': 80.0, 'external_ponderation': 20.0})
        self.assertEqual(self.planning_taught.internal_ponderation, 80.0)
