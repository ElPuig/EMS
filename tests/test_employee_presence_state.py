from datetime import datetime
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase

from odoo.addons.ems import _disable_login_presence_control, _fix_native_presence_translations

from .common import create_role_employee, create_role_user

# A past Monday (no school holiday): 07:00 UTC is 09:00 in Europe/Madrid (CEST).
MONDAY = datetime(2026, 9, 28)


class TestEmployeePresenceState(TransactionCase):
    """The presence dot on the Teachers/ASP screens ('hr_presence_state', issue #555).

    It follows only the attendance check-in/out and the employee's own schedule: hr's own
    version counts anyone with a slot within the next hour as "should be working now" (shown
    as Absent before the first class and in short gaps), and its login-based control showed as
    Present anyone who merely had EMS open in a browser, checked in or not."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.hr_presence_control_attendance = True
        _disable_login_presence_control(cls.env)
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_teacher_presence_state')
        cls.teacher = create_role_employee(cls, cls.teacher_user)
        cls.teacher.resource_calendar_id = cls.env['resource.calendar'].create({
            'name': 'Test Schedule (Presence State)',
            'attendance_ids': [
                (0, 0, {'name': 'Monday 1st class', 'dayofweek': '0', 'hour_from': 9.0, 'hour_to': 10.0}),
                (0, 0, {'name': 'Monday 2nd class', 'dayofweek': '0', 'hour_from': 10.5, 'hour_to': 11.5}),
            ],
        })

    def _presence_at(self, utc_hour, utc_minute=0, user=None):
        teacher = self.teacher.with_user(user) if user else self.teacher
        with patch.object(fields.Datetime, 'now', return_value=MONDAY.replace(hour=utc_hour, minute=utc_minute)):
            self.env.invalidate_all()
            return teacher.hr_presence_state, teacher.hr_icon_display

    def test_before_the_first_class_is_out_of_working_hours(self):
        # 08:30 local, half an hour before the first class: hr's one-hour look-ahead said Absent.
        self.assertEqual(self._presence_at(6, 30)[0], 'out_of_working_hour')

    def test_during_a_class_without_checking_in_is_absent(self):
        self.assertEqual(self._presence_at(7, 15)[0], 'absent')

    def test_gap_between_classes_is_out_of_working_hours(self):
        # 10:15 local, between the 09:00-10:00 and 10:30-11:30 classes.
        self.assertEqual(self._presence_at(8, 15)[0], 'out_of_working_hour')

    def test_after_the_last_class_is_out_of_working_hours(self):
        self.assertEqual(self._presence_at(9, 45)[0], 'out_of_working_hour')

    def test_checked_in_is_present(self):
        self.env['hr.attendance'].create({
            'employee_id': self.teacher.id,
            'check_in': MONDAY.replace(hour=6, minute=55),
        })
        self.assertEqual(self._presence_at(7, 15)[0], 'present')

    def test_a_checked_in_colleague_is_present_whoever_looks(self):
        """Issue #575: the state reads the last check-in, a field restricted to HR and attendance
        officers; computed as a teacher or a tutor it came back empty, so their colleague's form
        showed "out of working hours" (grey) while the Teachers kanban showed them present."""
        self.env['hr.attendance'].create({
            'employee_id': self.teacher.id,
            'check_in': MONDAY.replace(hour=6, minute=55),
        })
        for role in ('teacher', 'tutor'):
            viewer = create_role_user(self, role, f'test_{role}_viewer_presence_state')
            with self.subTest(role=role):
                self.assertEqual(self._presence_at(7, 15, user=viewer), ('present', 'presence_present'))

    def test_a_colleague_missing_class_is_absent_whoever_looks(self):
        viewer = create_role_user(self, 'tutor', 'test_tutor_viewer_absent_presence_state')
        self.assertEqual(self._presence_at(7, 15, user=viewer), ('absent', 'presence_absent'))

    def test_being_online_without_checking_in_is_not_present(self):
        with patch.object(type(self.env['res.users']), '_is_user_available', return_value=True):
            self.assertEqual(self._presence_at(7, 15)[0], 'absent')

    def test_login_presence_control_is_disabled_for_every_company(self):
        # Reuses the current company's calendar: Odoo would otherwise create a "Standard 40
        # hours/week" one, whose name is unique in EMS and already taken on a clean install.
        other_company = self.env['res.company'].create({
            'name': 'Test Company (Presence State)',
            'resource_calendar_id': self.env.company.resource_calendar_id.id,
        })
        self.assertTrue(other_company.hr_presence_control_login)
        _disable_login_presence_control(self.env)
        self.assertFalse(other_company.hr_presence_control_login)
        self.assertFalse(self.env.company.hr_presence_control_login)

    def test_native_presence_labels_are_translated(self):
        _fix_native_presence_translations(self.env)
        self.env.cr.execute("""
            SELECT field.model, field.name, selection.value, selection.name
              FROM ir_model_fields_selection selection
              JOIN ir_model_fields field ON field.id = selection.field_id
             WHERE field.model IN ('hr.employee', 'hr.employee.public')
               AND field.name IN ('hr_icon_display', 'hr_presence_state')
               AND selection.value IN ('presence_out_of_working_hour', 'out_of_working_hour',
                                       'presence_holiday_absent', 'presence_holiday_present')
        """)
        rows = self.env.cr.fetchall()
        # hr_icon_display + hr_presence_state's "out of working hours", plus hr_holidays' two, on both models.
        self.assertEqual(len(rows), 8)
        expected = {
            'presence_out_of_working_hour': ('ca_ES', "Fora de l'horari laboral"),
            'out_of_working_hour': ('ca_ES', "Fora de l'horari laboral"),
            'presence_holiday_absent': ('ca_ES', "De permís"),
            'presence_holiday_present': ('es_ES', "Presente pero con permiso"),
        }
        for model, field_name, value, name in rows:
            lang, label = expected[value]
            self.assertEqual(name[lang], label, f"{model}.{field_name} = {value}")
            self.assertTrue(name['en_US'], "the English source label must be kept")
