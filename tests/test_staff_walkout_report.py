# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import create_role_user, make_working_day, mock_outgoing_email, shift_ems_clock

PERIODS = ((8.0, 9.0), (9.0, 10.0), (10.0, 11.0), (12.0, 13.0))


class TestStaffWalkoutReport(TransactionCase):
    """Issue #813: the staff on walkout so far on a day, per staff type and contract type, as
    pivot lines: one per period already started and per member of staff expected to work by then."""

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
        cls.civil_servant, cls.interim = cls.env['hr.contract.type'].create([
            {'name': 'TSSR Civil servant', 'sequence': 1}, {'name': 'TSSR Interim', 'sequence': 2}])
        cls.director = create_role_user(cls, 'director', 'test_director_tssr')

    @classmethod
    def _employee(cls, name, periods=PERIODS, **values):
        employee = cls.env['hr.employee'].create({'name': name, 'employee_type': 'teacher', **values})
        employee.resource_calendar_id = cls.env['resource.calendar'].create({
            'name': name, 'employee_id': employee.id,
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'name': f'{name} {weekday} {start}', 'dayofweek': str(weekday),
                        'hour_from': start, 'hour_to': stop})
                for weekday in range(5) for start, stop in periods],
        })
        return employee

    def _check_in(self, employee, hour, day=None):
        day = day or self.yesterday
        self.env['hr.attendance'].create({
            'employee_id': employee.id, 'check_in': self.Pending._utc_bounds(day, 0.0, hour)[1],
            'check_out': self.Pending._utc_bounds(day, 0.0, 14.0)[1]})

    def _leave(self, employee, state='confirm', hours=None):
        partial = {'ems_full_day': False, 'request_hour_from': hours[0], 'request_hour_to': hours[1]} \
            if hours else {'ems_full_day': True}
        leave = self.env['hr.leave'].create({
            'employee_id': employee.id, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': self.yesterday, 'request_date_to': self.yesterday,
            'ems_submitted': True, 'ems_responsible_declaration': True, **partial})
        leave.sudo().state = state
        return leave

    def _lines(self, day=None):
        """`{employee: {start: on_walkout}}` of the report for `day`, opened as the Director, each line
        keyed by the start of its period (the periods of this database's own staff split them too)."""
        report = self.env['ems.staff_walkout_report'].with_user(self.director).create({'date': day or self.yesterday})
        action = report.action_open_report()
        lines = self.env[action['res_model']].with_user(self.director).search(action['domain'])
        result = {}
        for line in lines:
            result.setdefault(line.employee_id, {})[line.period[:5]] = line.on_walkout
        return result

    def test_who_never_checks_in_counts_from_their_first_period_on(self):
        walker = self._employee('TSSR Walker', contract_type_id=self.civil_servant.id)
        afternoon = self._employee('TSSR Afternoon', periods=((12.0, 13.0),), contract_type_id=self.interim.id)

        lines = self._lines()

        self.assertEqual(min(lines[walker]), '08:00')
        self.assertEqual(set(lines[walker].values()), {1})
        # Still counted in a gap of their schedule and after it: the figure is cumulative.
        self.assertEqual(lines[walker]['11:00'], 1)
        # Not expected before their first period: no line until then.
        self.assertEqual(min(lines[afternoon]), '12:00')

    def test_checking_in_at_any_time_is_no_walkout(self):
        """Arriving late may be because of the walkout, which is no walkout: they are expected but
        never counted, not even in the periods before their arrival."""
        late = self._employee('TSSR Late')
        self._check_in(late, 10.5)

        self.assertEqual(set(self._lines()[late].values()), {0})

    def test_each_cell_has_the_walkers_the_others_and_the_percentage(self):
        walker = self._employee('TSSR Percentage Walker')
        present = self._employee('TSSR Percentage Present')
        self._check_in(present, 8.0)

        report = self.env['ems.staff_walkout_report'].with_user(self.director).create({'date': self.yesterday})
        report.action_open_report()
        groups = self.env['ems.staff_walkout_report.line']._read_group(
            [('id', 'in', report.line_ids.ids), ('employee_id', 'in', (walker | present).ids),
             ('period', '=like', '08:00%')],
            [], ['on_walkout:sum', 'not_on_walkout:sum', 'expected:sum', 'walkout_percentage:avg'])

        self.assertEqual(groups, [(1, 1, 2, 50.0)])

    def test_an_absence_request_is_no_walkout_in_its_periods(self):
        """Whoever is on a justified absence is expected to work and counts as not on walkout."""
        whole_day = self._employee('TSSR Sick Leave')
        self._leave(whole_day, state='validate')
        first_period = self._employee('TSSR Doctor')
        self._leave(first_period, hours=(8.0, 9.0))
        refused = self._employee('TSSR Refused')
        self._leave(refused, state='refuse')

        lines = self._lines()

        self.assertEqual(min(lines[whole_day]), '08:00')
        self.assertEqual(set(lines[whole_day].values()), {0})
        # Waiting for approval counts as much as approved: on walkout only from 9:00.
        self.assertEqual((lines[first_period]['08:00'], lines[first_period]['09:00']), (0, 1))
        self.assertEqual(lines[refused]['08:00'], 1)

    def test_a_detected_absence_does_not_take_its_periods_out(self):
        """The day of a walkout, the absence detected for a missing check-in is the walkout itself."""
        detected = self._employee('TSSR Detected')
        self.Pending.create({
            'employee_id': detected.id, 'origin': 'check_in',
            'date_from': self.Pending._utc_bounds(self.yesterday, 0.0, 8.0)[1],
            'date_to': self.Pending._utc_bounds(self.yesterday, 0.0, 13.0)[1]})

        self.assertEqual(self._lines()[detected]['08:00'], 1)

    def test_staff_type_and_contract_type_are_on_each_line(self):
        staff = self._employee('TSSR Concierge', employee_type='asp', contract_type_id=self.interim.id)
        vacancy = self._employee('TSSR Vacancy', schedule_import_code='TSSR1')

        report = self.env['ems.staff_walkout_report'].with_user(self.director).create({'date': self.yesterday})
        report.action_open_report()

        line = report.line_ids.filtered(lambda line: line.employee_id == staff)[:1]
        self.assertEqual((line.employee_type, line.contract_type_id), ('asp', self.interim))
        # A vacancy has a schedule but nobody to walk out.
        self.assertNotIn(vacancy, report.line_ids.employee_id)

    def test_today_only_counts_the_periods_already_started(self):
        walker = self._employee('TSSR Walker Today')

        lines = self._lines(self.today)
        # Reloading the page shows the same lines again: the title says when they were read.
        report = self.env['ems.staff_walkout_report'].with_user(self.director).create({'date': self.today})
        self.assertRegex(report.action_open_report()['name'], r' 10:\d\d$')

        # 10:00 on the shifted clock: the 10:00 period has just started, the 12:00 one has not.
        self.assertEqual((min(lines[walker]), max(lines[walker])), ('08:00', '10:00'))

    def test_no_report_for_a_day_to_come_or_without_anyone_expected(self):
        report = self.env['ems.staff_walkout_report'].with_user(self.director)
        with self.assertRaises(UserError):
            report.create({'date': self.today + timedelta(days=1)}).action_open_report()
        # A Sunday: nobody has a period.
        sunday = self.yesterday - timedelta(days=self.yesterday.weekday() + 1)
        with self.assertRaises(UserError):
            report.create({'date': sunday}).action_open_report()

    def test_no_report_on_a_public_holiday(self):
        self._employee('TSSR Holiday Teacher')
        utils = self.env['ems.datetime_utils']
        self.env['resource.calendar.leaves'].create({
            'name': 'TSSR Holiday',
            'date_from': utils.datetime_to_odoo(utils.time_float_to_utc_datetime(self.yesterday, 0.0)),
            'date_to': utils.datetime_to_odoo(utils.time_float_to_utc_datetime(self.yesterday, 23.9)),
        })
        report = self.env['ems.staff_walkout_report'].with_user(self.director).create({'date': self.yesterday})
        with self.assertRaisesRegex(UserError, 'TSSR Holiday'):
            report.action_open_report()
