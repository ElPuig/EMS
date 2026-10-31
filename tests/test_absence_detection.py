from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
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
        cls.head_of_studies = create_role_user(
            cls, 'head_of_studies', 'test_hos_tad', name='TAD Head of Studies', email='tad.hos@example.com')
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

    def _asked(self, absences):
        """The Head of Studies asks for a justification (issue #707): the reminders start."""
        absences.with_user(self.head_of_studies).action_request_justification()
        return absences

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

    def test_a_teacher_without_a_schedule_is_never_detected(self):
        """Nothing to compare the check-ins with: asking them to check in would be no control at all."""
        unscheduled = self.env['hr.employee'].create({'name': 'TAD Unscheduled Teacher', 'employee_type': 'teacher'})
        unscheduled.department_id = self.department
        self.Pending._ems_detect_missing_check_ins(self.yesterday)

        self.assertFalse(unscheduled.resource_calendar_id.attendance_ids)
        self.assertFalse(self._detected(unscheduled))
        self.assertTrue(self._detected(), 'the scheduled ones still are')

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

    def _attendance(self, day, hour_from, hour_to):
        return self.env['hr.attendance'].create({
            'employee_id': self.teacher.id, 'check_in': self._utc(day, hour_from),
            'check_out': self._utc(day, hour_to), 'in_mode': 'manual'})

    def test_a_check_in_outside_its_hours_leaves_it_alone(self):
        """Issue #731: the reviewer narrowed it to the hours the teacher really missed and asked
        them for it; recording the attendance of the hours before must not discard it."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        absence.with_user(self.head_of_studies).date_from = self._utc(self.yesterday, 10.0)
        self._create_absence(absence, self.head_of_studies)

        self._attendance(self.yesterday, 9.0, 10.0)

        self.assertEqual(absence.state, 'absence_prepared')
        self.assertEqual(self._hours(absence), (10.0, 13.0))

    def test_a_check_out_cuts_it_from_the_start(self):
        """Present until 10:30: only the rest, a whole period still missed, stays."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected())

        self._attendance(self.yesterday, 8.9, 10.5)

        self.assertEqual(absence.state, 'justification_requested')
        self.assertEqual(self._hours(absence), (10.5, 13.0))

    def test_an_attendance_in_the_middle_splits_it(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected())
        justification_date = absence.justification_date

        self._attendance(self.yesterday, 10.0, 11.0)

        parts = self._detected()
        self.assertEqual(len(parts), 2)
        self.assertEqual(sorted(self._hours(part) for part in parts), [(9.0, 10.0), (11.0, 13.0)])
        self.assertEqual(self._hours(absence), (9.0, 10.0), 'the entry keeps the first part')
        rest = parts - absence
        self.assertEqual((rest.state, rest.origin, rest.justification_date),
                         ('justification_requested', 'check_in', justification_date))
        self.assertFalse(self._review_activities(rest), 'already reviewed')
        self.assertTrue(rest.message_ids.filtered(lambda message: 'Split from' in message.body))

    def test_an_open_check_in_covers_it_to_the_end(self):
        """Checked in from the guard duty board and not out yet: present from then on."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()

        self.env['hr.attendance'].create({'employee_id': self.teacher.id, 'check_in': self._utc(self.yesterday, 10.5)})

        self.assertEqual(self._hours(absence), (9.0, 10.5))

    def test_a_later_check_out_reviews_it_too(self):
        """A check-out corrected afterwards counts as much as a check-in."""
        attendance = self._attendance(self.yesterday, 8.9, 9.5)
        absence = self.Pending.create({'employee_id': self.teacher.id, 'origin': 'check_in',
                                       'date_from': self._utc(self.yesterday, 9.5), 'date_to': self._utc(self.yesterday, 13.0)})

        attendance.check_out = self._utc(self.yesterday, 11.5)

        self.assertEqual(self._hours(absence), (11.5, 13.0))

    def test_a_part_shorter_than_a_period_is_no_absence(self):
        """The rule of the detection: arriving during a period is no absence."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()

        self._attendance(self.yesterday, 9.25, 10.75)
        self._attendance(self.yesterday, 11.0, 13.0)

        self.assertEqual(absence.state, 'discarded')

    # --- The teacher ----------------------------------------------------------------------------

    def test_the_teacher_reads_their_own_but_not_the_note(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        informed = self.Pending.create({
            'employee_id': self.teacher.id, 'note': 'Known in advance',
            'date_from': self._utc(self.today, 12.0), 'date_to': self._utc(self.today, 13.0)})
        theirs = self.Pending.create({
            'employee_id': self.present.id, 'date_from': self._utc(self.today, 12.0),
            'date_to': self._utc(self.today, 13.0)})
        mine = self._asked(self._detected() | informed)

        self.assertEqual(self.Pending.with_user(self.teacher_user).search([('id', 'in', (mine | theirs).ids)]), mine)
        with self.assertRaises(AccessError):
            informed.with_user(self.teacher_user).read(['note'])
        with self.assertRaises(AccessError):
            informed.with_user(self.teacher_user).write({'date_to': self._utc(self.today, 12.5)})

    def test_requesting_it_opens_a_request_that_links_it(self):
        self._check_in(self.teacher, self.yesterday, 10.5)
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected()).with_user(self.teacher_user)
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
        # Issue #735: nor a check-in correction, once the absence is requested.
        self.assertFalse(absence.can_request_correction)
        with self.assertRaises(UserError):
            absence.action_request_check_in_correction()

    # --- Reminders ------------------------------------------------------------------------------

    def test_the_teacher_is_told_once_their_working_day_starts(self):
        late_user = create_role_user(self, 'teacher', 'test_late_teacher_tad', name='TAD Late Teacher')
        late = self._teacher('TAD Late Teacher', user=late_user, periods=((12.0, 13.0),))
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence, late_absence = self._asked(self._detected()), self._asked(self._detected(late))

        self._run_cron_on(self.today, hour=8.0)
        self.assertFalse(self._messages_to(absence, self.teacher_user, 'No check-in'), 'their day starts at 9:00')
        self._run_cron_on(self.today, hour=10.0)
        self._run_cron_on(self.today, hour=10.5)
        self.assertEqual(len(self._messages_to(absence, self.teacher_user, 'No check-in')), 1, 'once a day')
        self.assertFalse(self._messages_to(late_absence, late_user, 'No check-in'), 'their day starts at 12:00')
        self._run_cron_on(self.today, hour=12.5)
        self.assertEqual(len(self._messages_to(late_absence, late_user, 'No check-in')), 1)

    def test_the_teacher_is_told_in_their_own_language(self):
        """The scheduled action runs as OdooBot: the message must not come out in its language."""
        if not self.env['res.lang']._lang_get('ca_ES'):
            self.skipTest('Catalan is not installed')
        self.teacher_user.lang = 'ca_ES'
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected())
        self._run_cron_on(self.today)

        self.assertTrue(self._messages_to(absence, self.teacher_user, 'No consta cap fitxatge'))
        self.assertFalse(absence.message_ids.filtered(lambda message: 'created' in (message.body or '')),
                         'no "created" line in the language of the scheduled action')

    def test_an_informed_absence_tells_the_teacher_something_else(self):
        informed = self._asked(self.Pending.create({
            'employee_id': self.teacher.id, 'date_from': self._utc(self.yesterday, 9.0),
            'date_to': self._utc(self.yesterday, 11.0)}))
        self._run_cron_on(self.today)

        self.assertEqual(len(self._messages_to(informed, self.teacher_user, 'was announced')), 1)
        self.assertFalse(self._messages_to(informed, self.teacher_user, 'No check-in'))

    def test_nothing_while_the_absence_is_still_going_on(self):
        informed = self._asked(self.Pending.create({
            'employee_id': self.teacher.id, 'date_from': self._utc(self.today, 9.0),
            'date_to': self._utc(self.today, 11.0)}))
        self._run_cron_on(self.today, hour=12.0)

        self.assertFalse(informed.message_ids.filtered(lambda message: self.teacher_user.partner_id in message.partner_ids))

    def test_reminded_again_and_reported_once_to_their_own_head_of_studies(self):
        """Both delays count from the day the justification was requested (issue #707)."""
        self.env.company.write({'ems_absence_document_reminder_days': 2, 'ems_absence_document_escalation_days': 3})
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        self._run_cron_on(self.today)
        self.assertFalse(self._messages_to(absence, self.teacher_user, 'No check-in'), 'not before it is asked')
        self._asked(absence)
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
            self.assertEqual(bool(reported(self.head_of_studies)), (day - self.today).days >= 3,
                             f'reported three days after the request ({day})')
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
        informed.sudo().write({'state': 'justification_requested', 'justification_date': self.yesterday})
        self._run_cron_on(self.today)

        self.assertFalse(self._messages_to(informed, outside_user, 'was announced'))

    # --- Review by the Head of Studies (issue #707) -----------------------------------------------

    def _review_activities(self, absence):
        return absence.activity_ids.filtered(
            lambda activity: activity.activity_type_id == self.env.ref('ems.mail_activity_absence_pending_review'))

    def _late_absence(self):
        """Yesterday, the teacher arrived at 10:30: detected from 9:00 to 10:30."""
        attendance = self._check_in(self.teacher, self.yesterday, 10.5)
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        return self._detected(), attendance

    def _teacher_messages(self, record):
        return record.message_ids.filtered(lambda message: self.teacher_user.partner_id in message.partner_ids)

    def test_detection_tells_only_the_reviewer(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        self._run_cron_on(self.today)
        self._run_cron_on(self.today + timedelta(days=7))

        self.assertEqual(absence.state, 'pending')
        self.assertFalse(self._teacher_messages(absence), 'the teacher hears nothing')
        self.assertFalse(absence.escalated)
        self.assertEqual(self._review_activities(absence).user_id, self.head_of_studies)
        self.assertFalse(self.Pending.with_user(self.teacher_user).search([('id', '=', absence.id)]),
                         'nor sees it on their own screens')

    def test_without_head_of_studies_the_administrators_review(self):
        admin = create_role_user(self, 'academic_admin', 'test_admin_tad', name='TAD Administrator')
        orphan_user = create_role_user(self, 'teacher', 'test_orphan_tad', name='TAD Orphan Teacher')
        orphan = self._teacher('TAD Orphan Teacher', user=orphan_user)
        orphan.parent_id = False
        self.Pending._ems_detect_missing_check_ins(self.yesterday)

        self.assertIn(admin, self._review_activities(self._detected(orphan)).user_id)

    def test_an_informed_absence_is_reviewed_too(self):
        """Even when its own Head of Studies entered it (developer's decision)."""
        informed = self.Pending.with_user(self.head_of_studies).create({
            'employee_id': self.teacher.id, 'date_from': self._utc(self.yesterday, 9.0),
            'date_to': self._utc(self.yesterday, 11.0)})
        self._run_cron_on(self.today)

        self.assertEqual(informed.state, 'pending')
        self.assertEqual(self._review_activities(informed).user_id, self.head_of_studies)
        self.assertFalse(self._teacher_messages(informed))

    def test_request_justification(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected())

        self.assertEqual(absence.state, 'justification_requested')
        self.assertEqual(absence.justification_date, self.today)
        self.assertFalse(self._review_activities(absence), 'reviewed: off the task list')
        self.assertTrue(absence.message_ids.filtered(lambda message: 'Action requested by' in message.body))
        self.assertEqual(self.Pending.with_user(self.teacher_user).search([('id', '=', absence.id)]), absence)
        self.assertEqual(self.env['ems.course']._get_guard_duty_absence_intervals(self.yesterday, self.teacher),
                         {self.teacher.id: [(9.0, 13.0, 'pending')]}, 'still unresolved for the board')

    def test_correct_check_in_of_a_whole_day(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        absence.with_user(self.head_of_studies).action_correct_check_in()

        attendance = self.env['hr.attendance'].search([('employee_id', '=', self.teacher.id)])
        self.assertEqual((attendance.check_in, attendance.check_out), (absence.date_from, absence.date_to))
        self.assertEqual(attendance.ems_checked_in_by_id, self.head_of_studies)
        self.assertEqual(absence.state, 'corrected', 'not discarded by the check-in it caused')
        self.assertFalse(self._review_activities(absence))
        self.assertTrue(absence.message_ids.filtered(lambda message: 'Check-in corrected by' in message.body))
        self.assertFalse(self._teacher_messages(absence) | self._teacher_messages(attendance),
                         'nobody is told')

    def test_correct_check_in_of_a_late_arrival_keeps_the_real_arrival(self):
        absence, arrival = self._late_absence()
        absence.with_user(self.head_of_studies).action_correct_check_in()

        attendances = self.env['hr.attendance'].search([('employee_id', '=', self.teacher.id)], order='check_in')
        self.assertEqual(attendances[1], arrival)
        self.assertEqual(arrival.check_in, self._utc(self.yesterday, 10.5), 'left as it was')
        self.assertEqual((attendances[0].check_in, attendances[0].check_out),
                         (self._utc(self.yesterday, 9.0), self._utc(self.yesterday, 10.5)))
        self.assertEqual(absence.state, 'corrected')

    def test_correct_check_in_fills_only_the_gaps(self):
        """An informed absence the teacher was partly present for: only what no attendance covers."""
        self._check_in(self.teacher, self.yesterday, 8.9).check_out = self._utc(self.yesterday, 10.0)
        self.env['hr.attendance'].create({'employee_id': self.teacher.id, 'check_in': self._utc(self.yesterday, 11.0),
                                          'check_out': self._utc(self.yesterday, 12.0)})
        informed = self.Pending.create({'employee_id': self.teacher.id, 'date_from': self._utc(self.yesterday, 9.0),
                                        'date_to': self._utc(self.yesterday, 13.0)})
        informed.with_user(self.head_of_studies).action_correct_check_in()

        created = self.env['hr.attendance'].search([('ems_checked_in_by_id', '=', self.head_of_studies.id)], order='check_in')
        self.assertEqual([(attendance.check_in, attendance.check_out) for attendance in created], [
            (self._utc(self.yesterday, 10.0), self._utc(self.yesterday, 11.0)),
            (self._utc(self.yesterday, 12.0), self._utc(self.yesterday, 13.0))])
        self.assertEqual(informed.state, 'corrected')

    def test_no_check_in_corrected_for_a_time_still_to_come(self):
        informed = self.Pending.create({'employee_id': self.teacher.id, 'date_from': self._utc(self.today, 12.0),
                                        'date_to': self._utc(self.today, 13.0)})
        reviewer = informed.with_user(self.head_of_studies)

        self.assertTrue(reviewer.can_review)
        self.assertFalse(reviewer.can_correct_check_in)
        with self.assertRaises(UserError):
            reviewer.action_correct_check_in()

    def _correct_check_in(self, absence, hour_from, hour_to, user=None):
        """The reviewer corrects the check-in of part of the entry (issue #731)."""
        day = self.Pending._to_local(absence.date_from).date()
        action = absence.with_user(user or self.head_of_studies).action_open_correct_check_in()
        wizard = self.env[action['res_model']].with_user(user or self.head_of_studies).with_context(
            action['context']).create({'date_from': self._utc(day, hour_from), 'date_to': self._utc(day, hour_to)})
        return wizard.action_confirm()

    def test_correct_check_in_of_a_part_leaves_the_rest_to_review(self):
        """Issue #731: present from 9:00 to 10:00, absent afterwards."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()

        self._correct_check_in(absence, 9.0, 10.0)

        attendance = self.env['hr.attendance'].search([('employee_id', '=', self.teacher.id)])
        self.assertEqual((attendance.check_in, attendance.check_out),
                         (self._utc(self.yesterday, 9.0), self._utc(self.yesterday, 10.0)))
        self.assertEqual(absence.state, 'pending', 'the rest is still to review')
        self.assertEqual(self._hours(absence), (10.0, 13.0))
        self.assertEqual(self._review_activities(absence).user_id, self.head_of_studies)
        self.assertTrue(absence.message_ids.filtered(lambda message: 'Check-in corrected by' in message.body))

        self._asked(absence)
        self.assertEqual(absence.state, 'justification_requested')

    def test_correct_check_in_of_the_middle_splits_it(self):
        informed = self.Pending.create({'employee_id': self.teacher.id, 'date_from': self._utc(self.yesterday, 9.0),
                                        'date_to': self._utc(self.yesterday, 13.0)})

        self._correct_check_in(informed, 10.0, 11.5)

        parts = self.Pending.search([('employee_id', '=', self.teacher.id)])
        self.assertEqual(sorted(self._hours(part) for part in parts), [(9.0, 10.0), (11.5, 13.0)])
        self.assertEqual(set(parts.mapped('state')), {'pending'})
        self.assertEqual(set(parts.mapped('origin')), {'informed'})
        self.assertEqual(len(self._review_activities(parts - informed)), 1, 'the new part is reviewed too')

    def _review_part(self, absence, method, hour_from, hour_to, **values):
        """The reviewer's decision on part of the entry, from its form's dialog (issue #735)."""
        day = self.Pending._to_local(absence.date_from).date()
        action = getattr(absence.with_user(self.head_of_studies), method)()
        wizard = self.env[action['res_model']].with_user(self.head_of_studies).with_context(
            action['context']).create({'date_from': self._utc(day, hour_from), 'date_to': self._utc(day, hour_to), **values})
        return wizard.action_confirm()

    def test_request_action_on_part_leaves_the_rest_to_review(self):
        """Issue #735: the teacher is asked about 11:00 to 13:00 only; 9:00 to 11:00 waits for the
        reviewer, unknown to the teacher."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()

        self._review_part(absence, 'action_open_request_action', 11.0, 13.0)

        rest = self._detected() - absence
        self.assertEqual((absence.state, self._hours(absence)), ('justification_requested', (11.0, 13.0)))
        self.assertTrue(absence.justification_date)
        self.assertFalse(self._review_activities(absence))
        self.assertTrue(absence.message_ids.filtered(lambda message: 'Action requested by' in message.body))
        self.assertEqual((rest.state, self._hours(rest)), ('pending', (9.0, 11.0)))
        self.assertFalse(rest.justification_date, 'nobody was asked about it')
        self.assertEqual(self._review_activities(rest).user_id, self.head_of_studies)
        self.assertTrue(absence.with_user(self.teacher_user).can_request)

    def test_prepare_justification_of_the_middle_splits_it(self):
        """Issue #735: the absence request is prepared for the hours chosen only."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        justified = self.env.ref('ems.leave_type_justified')

        self._review_part(absence, 'action_open_prepare_justification', 10.0, 11.5, holiday_status_id=justified.id)

        parts = self._detected() - absence
        self.assertEqual((absence.state, absence.leave_type_id, self._hours(absence)),
                         ('absence_prepared', justified, (10.0, 11.5)))
        self.assertEqual((absence._ems_leave_values()['request_hour_from'], absence._ems_leave_values()['request_hour_to']),
                         (10.0, 11.5), 'the request prepared covers the hours chosen')
        self.assertEqual(sorted(self._hours(part) for part in parts), [(9.0, 10.0), (11.5, 13.0)])
        self.assertEqual(set(parts.mapped('state')), {'pending'})
        self.assertFalse(parts.leave_type_id)

    def test_review_dialog_checks(self):
        """The hours stay within the entry, and a justification is prepared with a type."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        with self.assertRaises(ValidationError):
            self._review_part(absence, 'action_open_request_action', 8.0, 10.0)
        with self.assertRaises(ValidationError):
            self._review_part(absence, 'action_open_prepare_justification', 9.0, 10.0)
        self._review_part(absence, 'action_open_request_action', 9.0, 13.0)
        self.assertEqual((absence.state, len(self._detected())), ('justification_requested', 1), 'the whole entry, unsplit')

    def test_correct_check_in_of_the_whole_entry_from_the_dialog(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()

        self._correct_check_in(absence, 9.0, 13.0)

        self.assertEqual(absence.state, 'corrected')
        self.assertEqual(len(self._detected()), 1)

    def test_correct_check_in_only_within_the_entry(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        with self.assertRaises(ValidationError):
            self._correct_check_in(absence, 8.0, 10.0)
        with self.assertRaises(UserError):
            self._correct_check_in(absence, 9.0, 10.0, user=self.other_head_of_studies)

    def test_wrongly_discarded_entries_are_reopened(self):
        """Migration 18.0.0.42.1 (issue #731): the entries a check-in outside their hours
        discarded come back as they were, the reminders counting from today; those still covered
        and those a reviewer discarded stay as they are."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        wrong = self._detected()
        wrong.date_from = self._utc(self.yesterday, 10.0)
        self._create_absence(wrong, self.head_of_studies)
        wrong.justification_date = self.yesterday
        self._attendance(self.yesterday, 9.0, 10.0)
        wrong.state = 'discarded'  # what the check-in did before #731
        other_user = create_role_user(self, 'teacher', 'test_covered_tad', name='TAD Covered Teacher')
        covered_teacher = self._teacher('TAD Covered Teacher', user=other_user)
        covered = self.Pending.create({'employee_id': covered_teacher.id, 'origin': 'check_in',
                                       'date_from': self._utc(self.yesterday, 9.0), 'date_to': self._utc(self.yesterday, 13.0)})
        self._check_in(covered_teacher, self.yesterday, 8.9)
        self.assertEqual(covered.state, 'discarded')
        by_reviewer = self.Pending.create({'employee_id': self.teacher.id, 'origin': 'check_in',
                                           'date_from': self._utc(self.today - timedelta(days=2), 9.0),
                                           'date_to': self._utc(self.today - timedelta(days=2), 13.0)})
        by_reviewer.with_user(self.head_of_studies).action_discard()

        self.Pending._ems_reopen_wrongly_discarded()

        self.assertEqual(wrong.state, 'absence_prepared')
        self.assertEqual(self._hours(wrong), (10.0, 13.0))
        self.assertEqual(wrong.justification_date, self.today, 'reminded afresh, not reported at once')
        self.assertTrue(wrong.message_ids.filtered(lambda message: 'Reopened' in message.body))
        self.assertEqual(covered.state, 'discarded')
        self.assertEqual(by_reviewer.state, 'discarded')

    def test_a_wrongly_discarded_entry_to_review_gets_its_task_back(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        absence.date_from = self._utc(self.yesterday, 10.0)
        self._attendance(self.yesterday, 9.0, 10.0)
        absence.state = 'discarded'
        self.assertFalse(self._review_activities(absence))

        self.Pending._ems_reopen_wrongly_discarded()

        self.assertEqual(absence.state, 'pending')
        self.assertFalse(absence.justification_date, 'nobody was asked yet')
        self.assertEqual(self._review_activities(absence).user_id, self.head_of_studies)

    def _create_absence(self, absences, user):
        wizard = self.env['ems.absence_pending.leave_wizard'].with_user(user).with_context(
            active_model='ems.absence_pending', active_ids=absences.ids).create({
                'holiday_status_id': self.env.ref('ems.leave_type_justified').id})
        return wizard.action_confirm()

    def test_create_absence_prepares_it_for_the_teacher_to_send(self):
        """Never filed nor approved on the teacher's behalf: they check it, accept the responsible
        declaration and send it themselves (developer's decision)."""
        absence, _arrival = self._late_absence()
        justified = self.env.ref('ems.leave_type_justified')
        self._create_absence(absence, self.head_of_studies)

        self.assertEqual(absence.state, 'absence_prepared')
        self.assertEqual(absence.leave_type_id, justified)
        self.assertFalse(absence.leave_id)
        self.assertFalse(self.env['hr.leave'].search([('employee_id', '=', self.teacher.id)]), 'nothing filed yet')
        self.assertFalse(self._review_activities(absence))

        self._run_cron_on(self.today)
        self.assertEqual(len(self._messages_to(absence, self.teacher_user, 'has been prepared for you')), 1)

        mine = absence.with_user(self.teacher_user)
        self.assertTrue(mine.can_request)
        context = mine.action_request_absence()['context']
        self.assertEqual(context['default_holiday_status_id'], justified.id)
        self.assertEqual((context['default_request_hour_from'], context['default_request_hour_to']), (9.0, 10.5))
        values = {key.removeprefix('default_'): value for key, value in context.items()}
        Leave = self.env['hr.leave'].with_user(self.teacher_user)
        with self.assertRaises(ValidationError):
            Leave.create({**values, 'ems_submitted': True})
        leave = Leave.create({**values, 'ems_submitted': True, 'ems_responsible_declaration': True})

        self.assertEqual(absence.state, 'linked')
        self.assertEqual(absence.leave_id, leave)
        self.assertEqual(leave.state, 'confirm', 'waits for its approver, as any request')
        # Only where EMS's Catalan is loaded: CI's clean database can have the language active
        # (another test switches it on) without the module's translations.
        if self.env(context={'lang': 'ca_ES'})._("%(person)s on %(leave_type)s") != "%(person)s on %(leave_type)s":
            # hr_holidays' display_name does not depend on the language in the cache: drop the
            # one already computed in English (a request reads it in a single language).
            leave.invalidate_recordset(['display_name'])
            catalan_name = leave.with_context(lang='ca_ES').display_name
            self.assertNotIn(' on ', catalan_name, 'translated (hr_holidays has no Catalan)')
            self.assertIn('TAD Teacher, ', catalan_name)

    def test_an_administrator_reviews_too(self):
        """The administrator sits above the whole hierarchy, though outside it."""
        admin = create_role_user(self, 'academic_admin', 'test_admin_tad', name='TAD Administrator')
        absence, _arrival = self._late_absence()
        self.assertTrue(absence.with_user(admin).can_review)
        self._create_absence(absence, admin)

        self.assertEqual(absence.state, 'absence_prepared')

    def test_discard(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        absence.with_user(self.head_of_studies).action_discard()

        self.assertEqual(absence.state, 'discarded')
        self.assertFalse(absence.active)
        self.assertFalse(self._detected(), 'out of the default list')
        self.assertEqual(self.Pending.with_context(active_test=False).search([('id', '=', absence.id)]), absence)
        self.assertTrue(absence.message_ids.filtered(lambda message: 'Discarded by' in message.body))
        self.assertTrue(self.Pending.fields_get(['active'])['active']['readonly'],
                        'no Archive/Unarchive of its own: Discard is the way')
        self.assertFalse(self._teacher_messages(absence))
        self.assertFalse(self.env['hr.attendance'].search([('employee_id', '=', self.teacher.id)]))
        self.assertFalse(absence.leave_id)

    def test_bulk_skips_what_is_not_waiting_or_not_theirs(self):
        second_user = create_role_user(self, 'teacher', 'test_second_teacher_tad', name='TAD Second Teacher')
        second = self._teacher('TAD Second Teacher', user=second_user)
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        waiting, already = self._detected(), self._asked(self._detected(second))

        result = (waiting | already).with_user(self.head_of_studies).action_discard()

        self.assertEqual(waiting.state, 'discarded')
        self.assertEqual(already.state, 'justification_requested')
        self.assertEqual(result['params']['type'], 'warning')
        self.assertIn('Done for 1', result['params']['message'])
        self.assertIn('1 no longer waiting for review', result['params']['message'])
        with self.assertRaises(UserError):
            already.with_user(self.head_of_studies).action_request_justification()

    def test_a_department_chief_reads_but_does_not_review(self):
        chief_user = create_role_user(self, 'department_chief', 'test_chief_tad', name='TAD Department Chief')
        chief = create_role_employee(self, chief_user)
        chief.parent_id = self.head
        self.teacher.parent_id = chief
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected().with_user(chief_user)

        self.assertFalse(absence.can_review)
        with self.assertRaisesRegex(UserError, 'not yours to review'):
            absence.action_discard()
        self.assertEqual(absence.state, 'pending')

    def test_bulk_create_absence_prepares_each_entry(self):
        second_user = create_role_user(self, 'teacher', 'test_second_teacher_tad', name='TAD Second Teacher')
        second = self._teacher('TAD Second Teacher', user=second_user)
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absences = self._detected() | self._detected(second)
        self._create_absence(absences, self.head_of_studies)

        self.assertEqual(set(absences.mapped('state')), {'absence_prepared'})
        self.assertEqual(absences.leave_type_id, self.env.ref('ems.leave_type_justified'))

    def test_another_branch_cannot_review(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()

        self.assertFalse(self.teacher._ems_is_attendance_approver(self.other_head_of_studies))
        with self.assertRaises(UserError):
            absence.sudo().with_user(self.other_head_of_studies).action_discard()
        self.assertEqual(absence.state, 'pending')

    def test_the_teacher_resolves_it_at_every_stage(self):
        """Their own check-in or absence still closes it, reviewed or not."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        self._check_in(self.teacher, self.yesterday, 8.9)
        self.assertEqual(absence.state, 'discarded')
        self.assertTrue(absence.active, 'discarded by the system, not archived')
        self.assertFalse(self._review_activities(absence))

        informed = self._asked(self.Pending.create({
            'employee_id': self.teacher.id, 'date_from': self._utc(self.today, 12.0),
            'date_to': self._utc(self.today, 13.0)}))
        self.env['hr.leave'].create({
            'employee_id': self.teacher.id, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': self.today, 'request_date_to': self.today, 'ems_full_day': True,
            'ems_submitted': True, 'ems_responsible_declaration': True})
        self.assertEqual(informed.state, 'linked')


    def test_a_late_check_in_discards_a_prepared_absence_too(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        self._create_absence(absence, self.head_of_studies)
        self._check_in(self.teacher, self.yesterday, 8.9)

        self.assertEqual(absence.state, 'discarded')

    def test_existing_entries_join_the_review(self):
        """Migration 18.0.0.41.0: the ones already reminded go on as asked to justify them."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        reminded, untouched = self._detected(), self.Pending.create({
            'employee_id': self.teacher.id, 'date_from': self._utc(self.today, 12.0),
            'date_to': self._utc(self.today, 13.0)})
        reminded.reminder_date = self.today
        (reminded | untouched).activity_ids.unlink()

        self.Pending._ems_start_review_circuit()

        self.assertEqual(reminded.state, 'justification_requested')
        self.assertEqual(reminded.justification_date, self.yesterday, 'as if asked when the absence ended')
        self.assertFalse(self._review_activities(reminded))
        self.assertEqual(untouched.state, 'pending')
        self.assertEqual(self._review_activities(untouched).user_id, self.head_of_studies)

    def test_the_review_speaks_the_reviewer_language(self):
        """Notes and notices come out in the reviewer's language (code strings, issue #707)."""
        if not self.env['res.lang']._lang_get('ca_ES'):
            self.skipTest('Catalan is not installed')
        self.head_of_studies.lang = 'ca_ES'
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        absence.with_user(self.head_of_studies).with_context(lang='ca_ES').action_discard()

        self.assertTrue(absence.message_ids.filtered(lambda message: 'Descartada per' in message.body))
        with self.assertRaisesRegex(UserError, 'sense revisió pendent'):
            absence.with_context(active_test=False).with_user(self.head_of_studies).with_context(
                lang='ca_ES').action_request_justification()


    # --- Conversation with the teacher (issue #698) ---------------------------------------------

    def _followers(self, absence):
        return absence.message_partner_ids

    def _notified(self, message):
        return message.notification_ids.res_partner_id

    def test_the_teacher_follows_it_once_asked(self):
        """Never while it waits for review (issue #707), from the moment they are asked on."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        asked = self._detected()
        informed = self.Pending.create({
            'employee_id': self.teacher.id, 'date_from': self._utc(self.today, 12.0),
            'date_to': self._utc(self.today, 13.0)})
        self.assertNotIn(self.teacher_user.partner_id, self._followers(asked) | self._followers(informed))

        self._asked(asked)
        self._create_absence(informed, self.head_of_studies)

        self.assertIn(self.teacher_user.partner_id, self._followers(asked))
        self.assertIn(self.teacher_user.partner_id, self._followers(informed))

    def test_the_teacher_does_not_follow_what_they_are_never_told(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        corrected = self._detected()
        discarded = self.Pending.create({
            'employee_id': self.teacher.id, 'date_from': self._utc(self.today, 12.0),
            'date_to': self._utc(self.today, 13.0)})
        corrected.with_user(self.head_of_studies).action_correct_check_in()
        discarded.with_user(self.head_of_studies).action_discard()

        self.assertNotIn(self.teacher_user.partner_id, self._followers(corrected))
        self.assertNotIn(self.teacher_user.partner_id,
                         self._followers(discarded.with_context(active_test=False)))

    def test_the_reviewer_and_the_teacher_talk_on_it(self):
        """A message of the reviewer reaches the teacher, who answers on it with read access only."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected())
        self.teacher_user.email = 'tad.teacher@example.com'

        question = absence.with_user(self.head_of_studies).message_post(
            body="Were you ill?", message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertIn(self.teacher_user.partner_id, self._notified(question))

        answer = absence.with_user(self.teacher_user).message_post(
            body="Yes, I will send the certificate.", message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertIn(self.head_of_studies.partner_id, self._notified(answer))
        with self.assertRaises(AccessError):
            absence.with_user(self.teacher_user).write({'date_to': self._utc(self.yesterday, 12.0)})

    def test_the_teacher_cannot_write_on_one_still_to_review(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        self.teacher_user.email = 'tad.teacher@example.com'

        with self.assertRaises(AccessError):
            absence.with_user(self.teacher_user).message_post(
                body="Hello", message_type='comment', subtype_xmlid='mail.mt_comment')

    def test_teachers_already_asked_follow_their_entries(self):
        """Migration of issue #698: the entries asked before it get their teacher as follower."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        asked, waiting = self._detected(), self.Pending.create({
            'employee_id': self.teacher.id, 'date_from': self._utc(self.today, 12.0),
            'date_to': self._utc(self.today, 13.0)})
        asked.write({'state': 'justification_requested', 'justification_date': self.today})

        self.Pending._ems_follow_asked_teachers()

        self.assertIn(self.teacher_user.partner_id, self._followers(asked))
        self.assertNotIn(self.teacher_user.partner_id, self._followers(waiting))

    # --- Check-in correction requested by the teacher (issue #735) --------------------------------

    def _request_correction(self, absence, **values):
        """What the teacher's button opens, saved with `values`."""
        action = absence.with_user(self.teacher_user).action_request_check_in_correction()
        return self.env['ems.attendance_correction'].with_user(self.teacher_user).with_context(
            action['context']).create({'reason': 'I was at the centre.', **values})

    def test_teacher_requests_a_check_in_without_any_attendance(self):
        """Both answers are offered; a day without attendance gets one when accepted, and the
        entry is corrected, not discarded."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected()).with_user(self.teacher_user)
        self.assertTrue(absence.can_request)
        self.assertTrue(absence.can_request_correction)
        self.assertNotIn('default_attendance_id', absence.action_request_check_in_correction()['context'])

        correction = self._request_correction(absence)
        self.assertFalse(correction.attendance_id)
        self.assertEqual(correction.employee_id, self.teacher)
        self.assertEqual((correction.requested_check_in, correction.requested_check_out), (9.0, 13.0),
                         "the entry's own hours")
        self.assertFalse(absence.can_request_correction, 'one pending at a time')
        self.assertFalse(absence.can_request, 'they said they were at the centre: no absence meanwhile')
        with self.assertRaises(UserError):
            absence.action_request_absence()
        self.assertTrue(absence.message_ids.filtered(lambda message: 'Check-in correction requested' in message.body))

        correction.with_user(self.head_of_studies).action_accept()
        self.assertEqual(correction.state, 'accepted')
        self.assertEqual((correction.attendance_id.check_in, correction.attendance_id.check_out),
                         (self._utc(self.yesterday, 9.0), self._utc(self.yesterday, 13.0)))
        self.assertEqual(absence.state, 'corrected')
        # The approver corrects their decision: the attendance it recorded goes, the entry is back.
        attendance = correction.attendance_id
        correction.with_user(self.head_of_studies).action_reject()
        self.assertFalse(attendance.exists())
        self.assertEqual(absence.sudo().state, 'pending', 'back to the review, which the teacher does not see')

    def test_teacher_requests_a_correction_of_a_late_check_in(self):
        """The teacher's attendance of that day is the one corrected; a part still missed stays
        asked."""
        attendance = self._check_in(self.teacher, self.yesterday, 12.5)
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected())
        self.assertEqual(self._hours(absence), (9.0, 12.5))
        action = absence.with_user(self.teacher_user).action_request_check_in_correction()
        self.assertEqual(action['context']['default_attendance_id'], attendance.id)

        correction = self._request_correction(absence, requested_check_in=10.0)
        self.assertEqual(correction.attendance_id, attendance)
        correction.with_user(self.head_of_studies).action_accept()

        self.assertEqual(attendance.check_in, self._utc(self.yesterday, 10.0))
        # Issue #735: the part corrected stays the entry the correction answered; the rest is asked.
        rest = self._detected() - absence
        self.assertEqual((absence.state, self._hours(absence)), ('corrected', (10.0, 12.5)))
        self.assertEqual((rest.state, self._hours(rest)), ('justification_requested', (9.0, 10.0)), '9:00 to 10:00 still missed')

    def test_correction_request_checks(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        with self.assertRaises(UserError, msg='not asked yet'):
            absence.with_user(self.teacher_user).action_request_check_in_correction()
        self._asked(absence)
        with self.assertRaises(UserError, msg="only the teacher themselves"):
            absence.with_user(self.head_of_studies).action_request_check_in_correction()
        with self.assertRaises(ValidationError, msg='a time of the day'):
            self._request_correction(absence, requested_check_in=1400.0)
        with self.assertRaises(ValidationError, msg='without attendance, a check-out after the check-in'):
            self._request_correction(absence, requested_check_in=12.0, requested_check_out=11.0)
        other = self.env['hr.attendance'].search([('employee_id', '=', self.present.id)], limit=1)
        # Never the teacher's choice, whatever the client sends: they have none that day.
        self.assertFalse(self._request_correction(absence, attendance_id=other.id).attendance_id)

    def test_no_reminder_while_the_correction_is_pending(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected())
        correction = self._request_correction(absence)
        reminders = lambda: self._messages_to(absence, self.teacher_user, 'No check-in')
        self._run_cron_on(self.today)
        self.assertFalse(reminders(), 'waiting for the decision')

        correction.with_user(self.head_of_studies).action_reject()
        self.assertEqual(absence.state, 'pending', 'rejected: back to the review')
        self.assertIn(self.env.ref('ems.mail_activity_absence_pending_review'), absence.activity_ids.activity_type_id)
        self._run_cron_on(self.today)
        self.assertFalse(reminders(), 'the teacher hears nothing until asked again')

    def test_teacher_requests_the_red_attendance_of_a_day_without_check_in(self):
        """The technical attendance Odoo's absence detection leaves on a day without check-in (in
        red) is the one corrected, as teachers have always done; rejecting restores it."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected())
        red = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id, 'check_in': self._utc(self.yesterday, 0.0),
            'check_out': self._utc(self.yesterday, 0.0) + timedelta(seconds=1),
            'in_mode': 'technical', 'out_mode': 'technical',
        })
        self.assertEqual(absence.with_user(self.teacher_user).action_request_check_in_correction()['context'][
            'default_attendance_id'], red.id)

        correction = self._request_correction(absence)
        self.assertEqual(correction.attendance_id, red)
        self.assertTrue(correction.original_technical)
        self.assertEqual((correction.requested_check_in, correction.requested_check_out), (9.0, 13.0),
                         "the entry's own hours, not the red one's midnight")

        correction.with_user(self.head_of_studies).action_accept()
        self.assertEqual((red.check_in, red.check_out, red.in_mode),
                         (self._utc(self.yesterday, 9.0), self._utc(self.yesterday, 13.0), 'manual'))
        self.assertEqual(absence.state, 'corrected')

        correction.with_user(self.head_of_studies).action_reject()
        self.assertEqual((red.check_in, red.in_mode, red.out_mode), (self._utc(self.yesterday, 0.0), 'technical', 'technical'),
                         'a day without check-in again')
        self.assertEqual(absence.state, 'pending', 'claimed again')

    def test_the_status_bar_follows_each_circuit(self):
        """Issue #735: the steps each entry went through, ending in its state; the teacher never
        sees the review."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        paths = lambda: (absence.with_user(self.head_of_studies).status_path,
                         absence.with_user(self.teacher_user).status_path)
        self.assertEqual(absence.with_user(self.head_of_studies).status_path,
                         'pending,justification_requested,linked,justified')
        self._asked(absence)
        self.assertEqual(paths(), ('pending,justification_requested,linked,justified',
                                   'justification_requested,linked,justified'))
        correction = self._request_correction(absence)
        self.assertEqual(paths(), ('pending,justification_requested,correction_requested,corrected',
                                   'justification_requested,correction_requested,corrected'))
        correction.with_user(self.head_of_studies).action_accept()
        self.assertEqual(paths(), ('pending,justification_requested,correction_requested,corrected',
                                   'justification_requested,correction_requested,corrected'))
        absence.sudo().write({'state': 'justified', 'leave_type_id': self.env.ref('ems.leave_type_justified').id})
        self.assertEqual(paths(), ('pending,absence_prepared,linked,justified', 'absence_prepared,linked,justified'))
        absence.sudo().write({'state': 'discarded', 'justification_date': False, 'leave_type_id': False})
        self.assertEqual(paths(), ('pending,discarded', 'discarded'), 'discarded straight from the review')


    def test_an_informed_absence_is_corrected_by_the_teacher_request(self):
        """Issue #735: an informed entry is left alone by the attendance review; the accepted
        request corrects it once the attendance covers it."""
        informed = self.Pending.with_user(self.head_of_studies).create({
            'employee_id': self.teacher.id, 'date_from': self._utc(self.yesterday, 9.0),
            'date_to': self._utc(self.yesterday, 11.0)})
        self._asked(informed)
        correction = self._request_correction(informed)
        correction.with_user(self.head_of_studies).action_accept()
        self.assertEqual(informed.state, 'corrected')

    def test_a_chief_only_reads_their_own_detected_absence(self):
        """Issue #735: a Head of Studies is a teacher too; their own entry they read and
        regularize, never edit, while they still edit their teachers'."""
        own = self.Pending.create({'employee_id': self.head.id, 'date_from': self._utc(self.yesterday, 9.0),
                                   'date_to': self._utc(self.yesterday, 11.0)})
        own.sudo().write({'state': 'justification_requested', 'justification_date': self.yesterday})
        mine = own.with_user(self.head_of_studies)
        self.assertTrue(mine.can_request)
        with self.assertRaises(AccessError):
            mine.write({'date_to': self._utc(self.yesterday, 10.0)})
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        self._detected().with_user(self.head_of_studies).write({'date_to': self._utc(self.yesterday, 12.0)})

    def test_requesting_the_absence_withdraws_a_pending_correction(self):
        """Issue #735: filed from My Time Off while the correction waits, the absence answers the
        entry and the correction is rejected on its own."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected())
        correction = self._request_correction(absence)
        context = absence.sudo()._ems_leave_values()
        leave = self.env['hr.leave'].create({
            **context, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'ems_submitted': True, 'ems_responsible_declaration': True,
        })
        self.assertEqual(absence.state, 'linked')
        self.assertEqual(absence.leave_id, leave)
        self.assertEqual(correction.state, 'rejected')
        self.assertFalse(correction.approver_id, "nobody's decision")
        self.assertFalse(correction.activity_ids, 'off the approver task list')

    # --- The whole circuit (issue #735) ----------------------------------------------------------

    def _leave(self, day, hour_from=None, hour_to=None, employee=None):
        values = {'employee_id': (employee or self.teacher).id, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
                  'request_date_from': day, 'request_date_to': day,
                  'ems_submitted': True, 'ems_responsible_declaration': True}
        if hour_from is None:
            values['ems_full_day'] = True
        else:
            values.update({'ems_full_day': False, 'request_hour_from': hour_from, 'request_hour_to': hour_to})
        return self.env['hr.leave'].create(values)

    def test_a_correction_asked_from_the_attendance_answers_the_entry(self):
        """The classic Request Correction, on the red attendance: same effect as the button."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        self.assertEqual(absence.state, 'pending')
        red = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id, 'check_in': self._utc(self.yesterday, 0.0),
            'check_out': self._utc(self.yesterday, 0.0) + timedelta(seconds=1),
            'in_mode': 'technical', 'out_mode': 'technical'})
        correction = self.env['ems.attendance_correction'].with_user(self.teacher_user).with_context(
            default_attendance_id=red.id).create({'reason': 'Forgot to check in.', 'requested_check_in': 9.0,
                                                  'requested_check_out': 13.0})
        self.assertEqual(correction.absence_pending_id, absence)
        self.assertEqual(absence.state, 'correction_requested', 'the teacher is already answering it')
        self.assertFalse(self._review_activities(absence), 'off the review')
        self.assertFalse(absence.with_user(self.teacher_user).can_request, 'nothing more to do but wait')
        self._run_cron_on(self.today)
        self.assertFalse(self._messages_to(absence, self.teacher_user, 'No check-in'), 'no reminder meanwhile')

        correction.with_user(self.head_of_studies).action_accept()
        self.assertEqual(absence.state, 'corrected')

    def test_a_refused_request_of_a_past_day_is_detected_after_all(self):
        """Filed beforehand, the request kept the day out of the detection; refused, it is
        detected then, to the review."""
        leave = self._leave(self.yesterday)
        self._teacher('TAD Absent Teacher')
        self._run_cron_on(self.today)
        self.assertFalse(self._detected(), 'covered by the request')

        leave.action_refuse()
        absence = self._detected()
        self.assertEqual(absence.state, 'pending')
        self.assertEqual(self._hours(absence), (9.0, 13.0))
        self.assertTrue(self._review_activities(absence))

    def test_a_request_covering_part_resolves_that_part(self):
        """The part the request covers is linked to it; what still holds a period is claimed. If
        the request falls through, only its part is back to the review."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected())
        leave = self._leave(self.yesterday, 9.0, 11.0)

        rest = self._detected() - absence
        self.assertEqual((absence.state, absence.leave_id, self._hours(absence)), ('linked', leave, (9.0, 11.0)))
        self.assertEqual((rest.state, self._hours(rest)), ('justification_requested', (11.0, 13.0)))

        leave.action_refuse()
        self.assertEqual((absence.state, self._hours(absence)), ('pending', (9.0, 11.0)))
        self.assertEqual(rest.state, 'justification_requested', 'untouched')

    def test_a_correction_covering_part_and_its_rectification(self):
        """Corrected only for the hours requested; rejecting it afterwards reopens just those."""
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._asked(self._detected())
        correction = self._request_correction(absence, requested_check_in=9.0, requested_check_out=11.0)
        correction.with_user(self.head_of_studies).action_accept()

        rest = self._detected() - absence
        self.assertEqual((absence.state, self._hours(absence)), ('corrected', (9.0, 11.0)))
        self.assertEqual((rest.state, self._hours(rest)), ('justification_requested', (11.0, 13.0)))

        correction.with_user(self.head_of_studies).action_reject()
        self.assertEqual((absence.state, self._hours(absence)), ('pending', (9.0, 11.0)))
        self.assertEqual(rest.state, 'justification_requested')

    def test_the_migration_reopens_the_entries_of_dropped_requests(self):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        absence = self._detected()
        absence.sudo().write({'state': 'linked'})

        self.Pending._ems_reopen_dropped_requests()
        self.assertEqual(absence.state, 'pending')

