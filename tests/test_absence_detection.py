from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from .common import (
    create_role_employee, create_role_user, make_working_day, mock_outgoing_email, shift_ems_clock)

PERIODS = ((9.0, 10.0), (10.0, 11.0), (12.0, 13.0))


class TestAbsenceDetection(TransactionCase):
    """Issue #696: missing check-ins become detected absences at the end of the day, and every
    detected absence (also the ones entered by hand) reminds the teacher to request it when their
    working day starts, then reports it to their Head of Studies."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        # 10:00 of a Tuesday to Friday: "yesterday" is a school day too.
        cls.today = shift_ems_clock(cls, hour=10.0, weekdays=(1, 2, 3, 4)).date()
        cls.yesterday = cls.today - timedelta(days=1)
        for day in (cls.yesterday, cls.today):
            make_working_day(cls, day)
        cls.Pending = cls.env['ems.absence_pending']
        cls.area = cls.env['hr.department'].create({'name': 'TAD Area'})
        cls.department = cls.env['hr.department'].create({'name': 'TAD Department', 'parent_id': cls.area.id})
        cls.outside_department = cls.env['hr.department'].create({'name': 'TAD Department Of Another Area'})
        cls.env.company.ems_absence_circuit_area_ids = cls.area
        cls.head_of_studies = create_role_user(cls, 'head_of_studies', 'test_hos_tad', name='TAD Head of Studies')
        cls.head = cls._teacher('TAD Head', user=cls.head_of_studies)
        cls.other_head_of_studies = create_role_user(
            cls, 'head_of_studies', 'test_other_hos_tad', name='TAD Other Head of Studies')
        cls._teacher('TAD Other Head', user=cls.other_head_of_studies)
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_teacher_tad', name='TAD Teacher')
        cls.teacher = cls._teacher('TAD Teacher', user=cls.teacher_user)
        # Somebody in the circuit checked in yesterday: it was a school day.
        cls.present = cls._teacher('TAD Present Teacher')
        cls._check_in(cls.present, cls.yesterday, 8.9)
        cls.env['ir.config_parameter'].sudo().set_param('ems.missing_check_in_last_day', False)

    @classmethod
    def _teacher(cls, name, user=None, periods=PERIODS, department=None):
        """A teacher of the circuit's area under the Head of Studies (when there is one yet),
        with `periods` every weekday."""
        if user:
            employee = create_role_employee(cls, user, name=name)
        else:
            employee = cls.env['hr.employee'].create({'name': name, 'employee_type': 'teacher'})
        employee.department_id = department or cls.department
        employee.parent_id = getattr(cls, 'head', cls.env['hr.employee'])
        calendar = cls.env['resource.calendar'].create({
            'name': name, 'employee_id': employee.id,
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'name': f'{name} {weekday} {start}', 'dayofweek': str(weekday),
                        'hour_from': start, 'hour_to': stop})
                for weekday in range(5) for start, stop in periods],
        })
        employee.resource_calendar_id = calendar
        return employee

    @classmethod
    def _utc(cls, day, hour):
        return cls.Pending._utc_bounds(day, 0.0, hour)[1]

    @classmethod
    def _check_in(cls, employee, day, hour, in_mode='manual'):
        return cls.env['hr.attendance'].create({
            'employee_id': employee.id, 'check_in': cls._utc(day, hour),
            'check_out': cls._utc(day, 14.0), 'in_mode': in_mode,
        })

    def _detected(self, employee=None):
        return self.Pending.search([('employee_id', '=', (employee or self.teacher).id), ('origin', '=', 'check_in')])

    def _hours(self, absence):
        return tuple(self.Pending.time_to_float(self.Pending._to_local(value)) for value in (absence.date_from, absence.date_to))

    def _run_cron_on(self, day, hour=10.0):
        """The scheduled action at `hour` of `day`, company time."""
        utils = self.env['ems.datetime_utils']
        now = utils.datetime_to_odoo(utils.time_float_to_utc_datetime(day, hour))
        with patch.object(type(utils), 'get_local_today', return_value=day), \
                patch.object(fields.Datetime, 'now', return_value=now):
            self.Pending._cron_ems_detected_absences()

    def _messages_to(self, absence, user, text):
        return absence.message_ids.filtered(lambda message: user.partner_id in message.partner_ids and text in message.body)

    # --- Detection ------------------------------------------------------------------------------

    def test_a_day_without_any_check_in_is_detected(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)

        absence = self._detected()
        self.assertEqual(len(absence), 1)
        self.assertEqual(absence.state, 'pending')
        self.assertEqual(self._hours(absence), (9.0, 13.0), 'from the first period to the last one')
        self.assertFalse(self._detected(self.present))

    def test_a_late_arrival_is_detected_until_the_check_in(self):
        self._check_in(self.teacher, self.yesterday, 10.5)
        self.Pending._ems_detect_missing_check_ins(self.yesterday)

        self.assertEqual(self._hours(self._detected()), (9.0, 10.5))

    def test_arriving_during_the_first_period_is_no_absence(self):
        self._check_in(self.teacher, self.yesterday, 9.3)
        self.Pending._ems_detect_missing_check_ins(self.yesterday)

        self.assertFalse(self._detected())

    def test_a_technical_attendance_is_no_check_in(self):
        """Odoo's own absence detection creates them: they are no presence."""
        self._check_in(self.teacher, self.yesterday, 0.0, in_mode='technical')
        self.Pending._ems_detect_missing_check_ins(self.yesterday)

        self.assertEqual(len(self._detected()), 1)

    def test_nothing_on_a_day_nobody_checked_in(self):
        """A day off the calendar does not know about (the summer, a school holiday)."""
        self.env['hr.attendance'].search([('employee_id', '=', self.present.id)]).unlink()
        self.Pending._ems_detect_missing_check_ins(self.yesterday)

        self.assertFalse(self._detected())

    def test_nothing_on_a_public_holiday(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'TAD Holiday', 'date_from': self._utc(self.yesterday, 0.0), 'date_to': self._utc(self.yesterday, 23.9)})
        self.Pending._ems_detect_missing_check_ins(self.yesterday)

        self.assertFalse(self._detected())

    def test_an_absence_already_known_is_not_detected_again(self):
        requested = self._teacher('TAD Teacher With A Request')
        self.env['hr.leave'].create({
            'employee_id': requested.id, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': self.yesterday, 'request_date_to': self.yesterday,
            'ems_submitted': True, 'ems_responsible_declaration': True,
            'ems_full_day': False, 'request_hour_from': 9.0, 'request_hour_to': 11.0,
        })
        informed = self._teacher('TAD Teacher Already Informed')
        self.Pending.create({'employee_id': informed.id, 'date_from': self._utc(self.yesterday, 12.0),
                             'date_to': self._utc(self.yesterday, 13.0)})
        self.Pending._ems_detect_missing_check_ins(self.yesterday)

        self.assertFalse(self._detected(requested))
        self.assertFalse(self._detected(informed))
        self.assertTrue(self._detected())

    def test_only_the_teachers_of_the_chosen_areas(self):
        outside = self._teacher('TAD Teacher Of Another Area', department=self.outside_department)
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        self.assertFalse(self._detected(outside))
        self.assertTrue(self._detected())

    def test_no_area_switches_the_circuit_off(self):
        self.env.company.ems_absence_circuit_area_ids = False
        self._run_cron_on(self.today)

        self.assertFalse(self._detected())

    def test_the_scheduled_action_catches_up_and_never_detects_twice(self):
        before = self.yesterday - timedelta(days=1)
        while before.weekday() > 4:
            before -= timedelta(days=1)
        make_working_day(self, before)
        self._check_in(self.present, before, 8.9)
        self.env['ir.config_parameter'].sudo().set_param(
            'ems.missing_check_in_last_day', fields.Date.to_string(before - timedelta(days=1)))

        self._run_cron_on(self.today)
        self._run_cron_on(self.today, hour=10.5)

        detected = self._detected()
        self.assertEqual(sorted(self.Pending._to_local(absence.date_from).date() for absence in detected),
                         [before, self.yesterday])
        self.assertFalse(detected.filtered(lambda absence: self.Pending._to_local(absence.date_from).date() == self.today),
                         'today is not over yet')

    def test_the_first_run_does_not_reach_into_the_past(self):
        self._run_cron_on(self.today)

        self.assertFalse(self._detected().filtered(lambda absence: absence.date_from < self._utc(self.yesterday, 0.0)))

    # --- A check-in recorded afterwards ---------------------------------------------------------

    def test_a_later_check_in_discards_it(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()

        self._check_in(self.teacher, self.yesterday, 8.9)

        self.assertEqual(absence.state, 'discarded')
        with self.assertRaises(ValidationError):
            absence.date_to = self._utc(self.yesterday, 12.0)

    def test_a_later_but_earlier_check_in_shortens_it(self):
        attendance = self._check_in(self.teacher, self.yesterday, 12.5)
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        self.assertEqual(self._hours(absence), (9.0, 12.5))

        attendance.check_in = self._utc(self.yesterday, 10.5)

        self.assertEqual(absence.state, 'pending')
        self.assertEqual(self._hours(absence), (9.0, 10.5))

    def test_a_check_in_of_another_day_leaves_it_alone(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        self._check_in(self.teacher, self.today, 8.9)

        self.assertEqual(self._detected().state, 'pending')

    # --- The teacher ----------------------------------------------------------------------------

    def test_the_teacher_reads_their_own_but_not_the_note(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        informed = self.Pending.create({
            'employee_id': self.teacher.id, 'note': 'Known in advance',
            'date_from': self._utc(self.today, 12.0), 'date_to': self._utc(self.today, 13.0)})
        theirs = self.Pending.create({
            'employee_id': self.present.id, 'date_from': self._utc(self.today, 12.0),
            'date_to': self._utc(self.today, 13.0)})
        mine = self._detected() | informed

        self.assertEqual(self.Pending.with_user(self.teacher_user).search([('id', 'in', (mine | theirs).ids)]), mine)
        with self.assertRaises(AccessError):
            informed.with_user(self.teacher_user).read(['note'])
        with self.assertRaises(AccessError):
            informed.with_user(self.teacher_user).write({'date_to': self._utc(self.today, 12.5)})

    def test_requesting_it_opens_a_request_that_links_it(self):
        self._check_in(self.teacher, self.yesterday, 10.5)
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected().with_user(self.teacher_user)
        self.assertTrue(absence.can_request)
        self.assertFalse(absence.with_user(self.head_of_studies).can_request, 'only the teacher themselves')

        context = absence.action_request_absence()['context']
        self.assertEqual(context['default_request_date_from'], self.yesterday)
        self.assertEqual((context['default_request_hour_from'], context['default_request_hour_to']), (9.0, 10.5))
        # What the form saves: its defaults, plus what the teacher fills in.
        leave = self.env['hr.leave'].create({
            **{key.removeprefix('default_'): value for key, value in context.items()},
            'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'ems_submitted': True, 'ems_responsible_declaration': True,
        })

        self.assertEqual(absence.state, 'linked')
        self.assertEqual(absence.leave_id, leave)
        self.assertFalse(absence.can_request)

    # --- Reminders ------------------------------------------------------------------------------

    def test_the_teacher_is_told_once_their_working_day_starts(self):
        late_user = create_role_user(self, 'teacher', 'test_late_teacher_tad', name='TAD Late Teacher')
        late = self._teacher('TAD Late Teacher', user=late_user, periods=((12.0, 13.0),))
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence, late_absence = self._detected(), self._detected(late)

        self._run_cron_on(self.today, hour=8.0)
        self.assertFalse(self._messages_to(absence, self.teacher_user, 'No check-in'), 'their day starts at 9:00')
        self._run_cron_on(self.today, hour=10.0)
        self._run_cron_on(self.today, hour=10.5)
        self.assertEqual(len(self._messages_to(absence, self.teacher_user, 'No check-in')), 1, 'once a day')
        self.assertFalse(self._messages_to(late_absence, late_user, 'No check-in'), 'their day starts at 12:00')
        self._run_cron_on(self.today, hour=12.5)
        self.assertEqual(len(self._messages_to(late_absence, late_user, 'No check-in')), 1)

    def test_an_informed_absence_tells_the_teacher_something_else(self):
        informed = self.Pending.create({'employee_id': self.teacher.id, 'date_from': self._utc(self.yesterday, 9.0),
                                        'date_to': self._utc(self.yesterday, 11.0)})
        self._run_cron_on(self.today)

        self.assertEqual(len(self._messages_to(informed, self.teacher_user, 'was announced')), 1)
        self.assertFalse(self._messages_to(informed, self.teacher_user, 'No check-in'))

    def test_nothing_while_the_absence_is_still_going_on(self):
        informed = self.Pending.create({'employee_id': self.teacher.id, 'date_from': self._utc(self.today, 9.0),
                                        'date_to': self._utc(self.today, 11.0)})
        self._run_cron_on(self.today, hour=12.0)

        self.assertFalse(informed.message_ids.filtered(lambda message: self.teacher_user.partner_id in message.partner_ids))

    def test_reminded_again_and_reported_once_to_their_own_head_of_studies(self):
        self.env.company.write({'ems_absence_document_reminder_days': 2, 'ems_absence_document_escalation_days': 3})
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        school_days = [day for day in (self.today + timedelta(days=offset) for offset in range(10)) if day.weekday() < 5]
        for day in school_days:
            make_working_day(self, day)
        reminders = lambda: self._messages_to(absence, self.teacher_user, 'No check-in')
        reported = lambda user: self._messages_to(absence, user, 'has still not requested')

        for day in school_days:
            self._run_cron_on(day)
            expected, last = 0, None
            for reminder_day in school_days[:school_days.index(day) + 1]:
                if last is None or (reminder_day - last).days >= 2:
                    expected, last = expected + 1, reminder_day
            self.assertEqual(len(reminders()), expected, f'every two days ({day})')
            self.assertEqual(bool(reported(self.head_of_studies)), (day - self.yesterday).days >= 3,
                             f'reported three days after the absence ({day})')
        self.assertEqual(len(reported(self.head_of_studies)), 1, 'reported once')
        self.assertFalse(reported(self.other_head_of_studies), 'not to a Head of Studies of another branch')
        activity = absence.activity_ids.filtered(
            lambda activity: activity.activity_type_id == self.env.ref('ems.mail_activity_absence_not_requested'))
        self.assertEqual(activity.user_id, self.head_of_studies)

        self._check_in(self.teacher, self.yesterday, 8.9)
        self.assertEqual(absence.state, 'discarded')
        self.assertFalse(absence.activity_ids, 'nothing left to follow up')

    def test_the_old_reminders_are_left_alone_outside_the_areas(self):
        outside_user = create_role_user(self, 'teacher', 'test_outside_teacher_tad', name='TAD Outside Teacher')
        outside = self._teacher('TAD Outside Teacher', user=outside_user, department=self.outside_department)
        informed = self.Pending.create({'employee_id': outside.id, 'date_from': self._utc(self.yesterday, 9.0),
                                        'date_to': self._utc(self.yesterday, 11.0)})
        self._run_cron_on(self.today)

        self.assertFalse(self._messages_to(informed, outside_user, 'was announced'))
