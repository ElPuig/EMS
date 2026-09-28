from datetime import date

from odoo.exceptions import AccessError
from odoo.service.model import get_public_method
from odoo.tests.common import TransactionCase

from .common import create_level_study, create_role_employee, create_role_user


class TestScheduleEditRoles(TransactionCase):
    """Issue #531: every role allowed to edit a teacher's schedule must be able to complete a real
    Schedule-tab save ('resource.calendar.apply_schedule_changes') end to end, as themselves (no
    sudo), including the derived records that save rebuilds (ems.teaching, attendance templates,
    a group's tutor). Added after this broke for Head of Studies/Deputy three times: each earlier
    fix only granted the rights on ems.teaching that one scenario needed, while the save itself
    also deletes teaching rows whenever a subject or group is dropped from the grid."""

    EDITOR_ROLES = ('department_chief', 'head_of_studies', 'director', 'tac')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TSER', level={'name': 'Test Level (Schedule Edit Roles)'}, study={
            'code': 'TSER001', 'name': 'Test Study (Schedule Edit Roles)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TSER001', 'acronym': 'TSER', 'name': 'Test Subject (Schedule Edit Roles)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.tutorship = cls.env['ems.subject'].create({
            'code': 'TSER002', 'acronym': 'TSERT', 'name': 'Test Tutorship (Schedule Edit Roles)',
            'study_ids': [(6, 0, [cls.study.id])], 'is_tutorship': True,
        })
        cls.group_a = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'SERA', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.group_b = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'SERB', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Schedule Edit Roles)', 'employee_type': 'teacher',
        })
        cls.editors = {}
        for role in cls.EDITOR_ROLES:
            user = create_role_user(cls, role, f'test_ser_{role}')
            create_role_employee(cls, user)
            cls.editors[role] = user

    def _cell(self, subject, group, dayofweek='0', hour_from=8.0):
        return {
            'dayofweek': dayofweek, 'hour_from': hour_from, 'hour_to': hour_from + 1, 'day_period': 'morning',
            'subject_id': subject.id, 'group_ids': [group.id], 'name': f'TSER: {subject.acronym}',
        }

    def _save(self, user, cells):
        calendar = self.teacher.resource_calendar_id.with_user(user)
        calendar.apply_schedule_changes(cells)

    def _teachings(self):
        return self.env['ems.teaching'].search([('teacher_id', '=', self.teacher.id)])

    def test_editor_can_add_change_and_clear_a_schedule(self):
        for role, user in self.editors.items():
            with self.subTest(role=role):
                self._save(user, [self._cell(self.subject, self.group_a)])
                self.assertEqual(self._teachings().group_id, self.group_a)

                # Moving the class to another group drops the old teaching row.
                self._save(user, [self._cell(self.subject, self.group_b)])
                self.assertEqual(self._teachings().group_id, self.group_b)

                self._save(user, [])
                self.assertFalse(self._teachings())

    def test_editor_can_drop_a_tutorship(self):
        for role, user in self.editors.items():
            with self.subTest(role=role):
                self._save(user, [self._cell(self.tutorship, self.group_a)])
                self.group_a.tutor_id = self.teacher

                self._save(user, [self._cell(self.subject, self.group_a)])
                self.assertEqual(self._teachings().subject_id, self.subject)
                self.assertFalse(self.group_a.tutor_id)
                self._save(user, [])

    def test_teacher_cannot_edit_a_schedule(self):
        teacher_user = create_role_user(self, 'teacher', 'test_ser_teacher')
        with self.assertRaises(Exception):
            self._save(teacher_user, [self._cell(self.subject, self.group_a)])

    def test_derived_sync_is_not_callable_over_rpc(self):
        # The derived sync runs with sudo(), trusting that its caller already wrote the calendar
        # with its own rights - so none of it may be reachable over JSON-RPC, where any user with
        # read access to the model could call it directly (regenerating every template in the
        # centre, for '_regenerate_all_from_calendars').
        for model, method in (
            ('ems.teaching', '_sync_from_schedule'),
            ('ems.attendance_template', '_sync_from_schedule'),
            ('ems.attendance_template', '_sync_from_schedule_batch'),
            ('ems.attendance_template', '_regenerate_all_from_calendars'),
        ):
            with self.subTest(model=model, method=method), self.assertRaises(AccessError):
                get_public_method(self.env[model], method)
