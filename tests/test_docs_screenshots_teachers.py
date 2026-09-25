# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Teachers user manuals.

Tagged '-standard' on purpose - see the NOTE in test_docs_screenshots.py for why. Run it by
hand when a documented screen changes its look:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsTeachers' --stop-after-init -c /etc/odoo/odoo.conf"

Batched one manual/test method at a time (see docs/en/developers/shared/testing.md, "DocsScreenshotMixin").
"""
import json
from datetime import datetime
from unittest.mock import patch

from odoo.tests.common import HttpCase, tagged

from .common import (
    DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user,
    mock_outgoing_email, next_student_id,
)


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsTeachers(DocsScreenshotMixin, HttpCase):
    allow_end_on_form = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = create_role_user(cls, 'teacher', 'doc_shot_teacher', lang='ca_ES',
                                            name='Professor Exemple', email='professor@example.com')
        cls.teacher_employee = create_role_employee(cls, cls.teacher_user, name='0000 Professor Exemple')

    def test_capture_acces_ems_google(self):
        # No fixture needed: the login screen is shown before anyone signs in, so this is the
        # one capture in the whole project that must NOT authenticate first (login=None).
        self._capture(
            '/web/login', '.o_login_auth', 'acces-google-boto.png',
            wait_for='.o_auth_oauth_providers a',
        )

    def test_capture_attendance_corrections(self):
        # A finished past day (both check-in and check-out set), so the correction form shows
        # both fields at once - the more informative shot vs. the still-clocked-in case, which
        # only shows Check-in (see the manual's own note about that narrower state).
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.teacher_employee.id,
            'check_in': datetime(2027, 3, 10, 8, 5), 'check_out': datetime(2027, 3, 10, 16, 0),
        })
        # Own request, native ir.rule (rule_attendance_correction_teacher_own) scopes both the
        # Overview and Correction Requests captures below to just this fixture's data.
        self.env['ems.attendance_correction'].with_user(self.teacher_user).with_context(
            default_attendance_id=attendance.id).create({
            'requested_check_in': 8.0,
            'reason': 'Vaig fitxar tard per un problema amb el lector.',
        })

        # A domain-scoped action of our own (same trick used throughout this project's other
        # per-role screenshot files) instead of the native hr_attendance_action directly: its
        # own context groups two levels deep (by month, then by employee name), and getting a
        # reliable automated click on the still-folded inner group header proved genuinely
        # unreliable (Chrome-dispatched clicks landed on the row and an attached test listener
        # confirmed they fired, but Owl's own toggle handler produced no visible change and no
        # RPC - not chased further). With only one employee/one record to show, the grouping
        # adds nothing anyway - a flat list is both simpler to capture and a fairer picture of
        # what matters here.
        overview_action = self.env['ir.actions.act_window'].create({
            'name': 'Assistència del personal',
            'res_model': 'hr.attendance',
            'view_mode': 'list,form',
            'domain': [('id', '=', attendance.id)],
        })
        self._capture(
            '/odoo/action-%d' % overview_action.id,
            '.o_list_table', 'assistencia-01-llistat.png',
            login='doc_shot_teacher', wait_for='.o_list_renderer .o_data_row',
        )
        # The button's name= is the numeric id of ems.action_attendance_correction_new (the
        # "%(xmlid)d" syntax in hr_attendance_form.xml is resolved to a literal at view-load
        # time) - more reliable here than a class selector, since the header's own
        # overtime-status statusbar widget renders its own buttons alongside it.
        request_correction_selector = '.o_form_statusbar button[name="%d"]' % self.env.ref(
            'ems.action_attendance_correction_new').id
        self._capture(
            '/odoo/action-%d/%d' % (overview_action.id, attendance.id),
            '.modal-content', 'assistencia-02-sol-licitar-correccio.png',
            login='doc_shot_teacher',
            wait_for=request_correction_selector,
            click=request_correction_selector,
            wait_after=".modal-content div[name='requested_check_in']",
        )
        self._capture(
            '/odoo/action-ems.action_attendance_correction_tree',
            '.o_list_table', 'assistencia-03-sol-licituds.png',
            login='doc_shot_teacher', wait_for='.o_list_renderer .o_data_row',
        )

    def test_capture_attendance_reports(self):
        level, study, group = create_level_study_group(self, 'DOCREP', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCREP01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        tutor = self.env['hr.employee'].create({'name': '0000 Tutora Exemple', 'employee_type': 'teacher'})
        group.tutor_id = tutor
        subject = self.env['ems.subject'].create({
            'code': 'DOCREPSUB', 'acronym': 'BD', 'name': 'Bases de dades',
            'study_ids': [(6, 0, [study.id])],
        })
        self.env['ems.teaching'].create({
            'teacher_id': self.teacher_employee.id, 'subject_id': subject.id, 'group_id': group.id,
        })
        space = self.env['ems.space'].create({
            'code': 'DOCREP-A', 'name': 'Aula Exemple',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, self.teacher_employee.ids)], 'study_ids': [(6, 0, [study.id])],
            'subject_id': subject.id, 'group_ids': [(6, 0, [group.id])],
            'start_date': datetime(2020, 1, 1).date(), 'end_date': datetime(2030, 12, 31).date(),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 9.0, 'end_time': 10.0, 'space_id': space.id,
        })
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': datetime(2027, 3, 9).date(),
            'mode': 'manual', 'session_teacher_id': self.teacher_employee.id,
        })
        status_attended = self.env.ref('ems.attendance_status_attended')
        status_miss = self.env.ref('ems.attendance_status_miss')
        student_a = self._student(group, 'Laia Exemple')
        student_b = self._student(group, 'Jordi Mostra')
        report_lines = self.env['ems.attendance_session_line'].create([
            {'student_id': student_a.id, 'status_id': status_attended.id, 'attendance_session_id': session.id},
            {'student_id': student_b.id, 'status_id': status_miss.id, 'attendance_session_id': session.id},
        ])

        pivot_view = self.env.ref('ems.view_attendance_report_analysis_pivot')
        pivot_action = self.env['ir.actions.act_window'].create({
            'name': "Informes d'assistència",
            'res_model': 'ems.attendance_session_line',
            'view_mode': 'pivot',
            'views': [(pivot_view.id, 'pivot')],
            'domain': [('id', 'in', report_lines.ids)],
        })
        # "Expand all" unfolds one row level per click (subject first, then student) - see the
        # manual's own step-by-step. tbody tr:nth-of-type(N) counts plain table rows (no
        # group-header/data-row class split like a list view has, so nth-of-type is safe here,
        # unlike the list-view gotcha elsewhere in this file): 1 (Total) -> 2 (+ subject) after
        # the first click -> 4 (+ both students) after the second.
        self._capture(
            '/odoo/action-%d' % pivot_action.id,
            '.o_pivot', 'informes-01-taula-dinamica.png',
            login='doc_shot_teacher', wait_for='.o_pivot table tbody tr',
            click=['.o_pivot_expand_button', '.o_pivot_expand_button'],
            wait_after=[
                '.o_pivot table tbody tr:nth-of-type(2)',
                '.o_pivot table tbody tr:nth-of-type(4)',
            ],
        )

        report_wizard_action = self.env['ir.actions.act_window'].create({
            'name': "Informe d'assistència",
            'res_model': 'ems.attendance_report_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_report_type': 'group', 'default_group_id': group.id},
        })
        self._capture(
            '/odoo/action-%d' % report_wizard_action.id,
            '.modal-content', 'informes-02-imprimir.png',
            login='doc_shot_teacher',
            # tutor_ids is a plain compute (not an onchange), so it's already correct as soon as
            # group_id is set from the context default - a more reliable "the wizard finished
            # loading" signal here than waiting on the onchange-filled from_date/to_date.
            wait_for=".modal-content div[name='tutor_ids'] .o_tag",
        )

    def test_capture_attendance_session(self):
        from datetime import date
        level, study, group = create_level_study_group(self, 'DOCSESS', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCSESS01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        subject = self.env['ems.subject'].create({
            'code': 'DOCSESSSUB', 'acronym': 'BD', 'name': 'Bases de dades',
            'study_ids': [(6, 0, [study.id])],
        })
        space = self.env['ems.space'].create({
            'code': 'DOCSESS-A', 'name': 'Aula Exemple',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        student_a = self._student(group, 'Marina Exemple')
        student_b = self._student(group, 'Pau Mostra')
        student_c = self._student(group, 'Nerea Prova')

        # Spans the whole day (same trick as test_attendance_session_tour.py): makes the schedule
        # "current" regardless of what time this capture actually runs at, no time-freezing needed.
        weekday = str(date.today().weekday())
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, self.teacher_employee.ids)], 'study_ids': [(6, 0, [study.id])],
            'subject_id': subject.id, 'group_ids': [(6, 0, [group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': weekday,
            'start_time': 0.0, 'end_time': 23.0, 'space_id': space.id,
            'student_ids': [(6, 0, (student_a + student_b + student_c).ids)],
        })
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date.today(),
            'mode': 'manual', 'session_teacher_id': self.teacher_employee.id,
        })
        status_attended = self.env.ref('ems.attendance_status_attended')
        status_miss = self.env.ref('ems.attendance_status_miss')
        lines = session.attendance_session_line_ids
        lines.filtered(lambda line: line.student_id == student_a).status_id = status_attended.id
        line_b = lines.filtered(lambda line: line.student_id == student_b)
        line_b.status_id = status_miss.id
        line_b.notes = 'Truca la família per confirmar.'
        # A justification makes the shield icon appear (isJustified in attendance_session_view.xml
        # checks attendance_justification_id/attendance_prevision_id directly) - set on the line
        # itself rather than through the justification's own _onchange_attendance_session_line_ids
        # (an @api.onchange, never fired by a plain ORM create()).
        line_c = lines.filtered(lambda line: line.student_id == student_c)
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher_employee.id, 'student_id': student_c.id,
            'start_date': datetime.combine(date.today(), datetime.min.time()),
            'end_date': datetime.combine(date.today(), datetime.max.time()),
            'notes': 'Visita mèdica',
        })
        line_c.write({'status_id': status_miss.id, 'attendance_justification_id': justification.id})

        self._capture(
            '/odoo/action-ems.action_attendance_passlist',
            '.ems-av-root', 'passlist-01-assistencia-actual.png',
            login='doc_shot_teacher', wait_for='.ems-av-line',
            # .ems-av-root stretches to fill the remaining viewport height (an empty-state
            # placeholder needs the room), so _trim's background-diff crop can't tell the real
            # content apart from that empty tail (same class of issue as the flex-stretch gotcha
            # documented in the plan file) - max_height caps the capture well above the real
            # content (header + a handful of rows) instead.
            max_height=400,
        )

        # Guard mode: a colleague's slot for today, not started yet (still "planned") - the
        # teacher covering it sees a "Start session" card, same as their own not-yet-started
        # slots in normal mode. Own session created above is correctly excluded from Guard
        # (Guard only ever shows OTHER teachers' sessions/slots).
        colleague = self.env['hr.employee'].create({'name': '0000 Companya Exemple', 'employee_type': 'teacher'})
        colleague_template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, colleague.ids)], 'study_ids': [(6, 0, [study.id])],
            'subject_id': subject.id, 'group_ids': [(6, 0, [group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': colleague_template.id, 'weekday': weekday,
            'start_time': 0.0, 'end_time': 23.0, 'space_id': space.id,
            'student_ids': [(6, 0, (student_a + student_b + student_c).ids)],
        })
        # The mode selector is a plain <select> reacting to its own 'change' event, not a click -
        # _capture()'s run= param exists for exactly this (see its docstring).
        self._capture(
            '/odoo/action-ems.action_attendance_passlist',
            '.ems-av-root', 'passlist-02-mode-guarida.png',
            login='doc_shot_teacher', wait_for='.ems-av-line',
            run="""
                (function () {
                    var select = document.querySelector('.ems-av-mode-wrap select');
                    select.value = 'guard';
                    select.dispatchEvent(new Event('change'));
                })();
            """,
            wait_after='.ems-av-planned-card',
            max_height=350,
        )

    def test_capture_guard_duty_schedule(self):
        from datetime import date, timedelta

        # get_current_course_data() raises a friendly error when unset - this dev DB already has
        # one configured, but a fresh CI DB doesn't (same guard as test_guard_duty_board_tour.py).
        if not self.env.company.current_course_id:
            self.env.company.current_course_id = self.env['ems.course'].create({'start': 1998, 'end': 1999})

        level, study, group = create_level_study_group(self, 'DOCGUARD', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCGUARD01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        subject = self.env['ems.subject'].create({
            'code': 'DOCGUARDSUB', 'acronym': 'BD', 'name': 'Bases de dades',
            'study_ids': [(6, 0, [study.id])],
        })
        space = self.env['ems.space'].create({
            'code': 'DOCGUARD-A', 'name': 'Aula Exemple',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })

        # The teaching teacher whose class fills a group column - also the one made absent below,
        # so their name shows struck in bold red both in this cell and in the Absences table.
        teaching_teacher = self.env['hr.employee'].create({'name': '0000 Berta Exemple', 'employee_type': 'teacher'})
        teaching_calendar = self.env['resource.calendar'].create({
            'name': '0000 Berta Exemple Calendar', 'employee_id': teaching_teacher.id})
        teaching_teacher.resource_calendar_id = teaching_calendar
        teaching_calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': subject.id, 'group_ids': [group.id], 'name': 'DOCGUARD: BD',
        }])

        # A plain guard duty, same time block - shows in the Guard duty column, never in a group's
        # own column (a guard slot has no group_ids/subject_id of its own).
        guard_teacher = self.env['hr.employee'].create({'name': '0000 Martí Mostra', 'employee_type': 'teacher'})
        guard_calendar = self.env['resource.calendar'].create({
            'name': '0000 Martí Mostra Calendar', 'employee_id': guard_teacher.id})
        guard_teacher.resource_calendar_id = guard_calendar
        guard_calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.env.ref('ems.non_teaching_g').id, 'name': 'Guàrdia',
        }])

        # A Guard (WC) duty, same time block - the manual specifically calls out its "(WC)" tag,
        # since it's the one guard subtype that can fall at any time of day.
        wc_guard_teacher = self.env['hr.employee'].create({'name': '0000 Clara Prova', 'employee_type': 'teacher'})
        wc_guard_calendar = self.env['resource.calendar'].create({
            'name': '0000 Clara Prova Calendar', 'employee_id': wc_guard_teacher.id})
        wc_guard_teacher.resource_calendar_id = wc_guard_calendar
        wc_guard_calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.env.ref('ems.non_teaching_gwc').id, 'name': 'Guàrdia (WC)',
        }])

        # A break-time ("patio") guard: a dedicated level whose own framework has only a break
        # period, no teaching entry - so the row it lands on shows the "Break" label with no cell
        # content of its own (same recipe as test_guard_duty_board_tour.py).
        patio_level = self.env['ems.level'].create({'acronym': 'DOCGUARDP', 'name': 'Nivell Pati Exemple'})
        patio_framework = self.env['resource.calendar'].create({
            'name': 'Marc Pati Exemple', 'is_framework': True, 'level_id': patio_level.id,
            'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': patio_framework.id, 'name': 'BR: Pati', 'dayofweek': '0',
            'hour_from': 8.9, 'hour_to': 9.6, 'day_period': 'morning',
            'non_teaching': self.env.ref('ems.non_teaching_br').id,
        })
        patio_guard_teacher = self.env['hr.employee'].create({'name': '0000 Roger Fictici', 'employee_type': 'teacher'})
        patio_guard_calendar = self.env['resource.calendar'].create({
            'name': '0000 Roger Fictici Calendar', 'employee_id': patio_guard_teacher.id})
        patio_guard_teacher.resource_calendar_id = patio_guard_calendar
        patio_guard_calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8.9, 'hour_to': 9.6, 'day_period': 'morning',
            'non_teaching': self.env.ref('ems.non_teaching_gb').id, 'name': 'Guàrdia de pati',
        }])

        # An approved whole-day absence for the teaching teacher, on the Monday of the CURRENT
        # week - the same Monday the board's own date picker resolves to (see mondayOf() in
        # guard_duty_board.js), so forcing the "Monday" tab below always lands on this absence
        # regardless of which real weekday the capture actually runs on.
        mock_outgoing_email(self)
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        self.env['hr.leave'].create({
            'employee_id': teaching_teacher.id,
            'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': monday, 'request_date_to': monday,
            'ems_full_day': True, 'ems_submitted': True, 'ems_responsible_declaration': True,
        }).action_approve()

        # This board has no domain to scope it by (get_guard_duty_board_data() is a plain RPC,
        # not a view/action with a 'domain' field) and its own aggregation is explicitly
        # centre-wide by design (_get_guard_duty_board_attendance_ids()'s own NOTE) - even WITH
        # a level filter applied, the Guard duty column still shows every REAL teacher on real
        # guard duty in the same time block, regardless of level (see
        # get_guard_duty_board_lines()'s own docstring: "once a time block is visible... every
        # guard on duty then is relevant, regardless of what they otherwise teach"). Found while
        # actually looking at the first capture attempt: it showed this dev DB's real timetable
        # (real teacher names, real group codes) for every group centre-wide, not just this
        # fixture's own "DAM1A" column - confirmed real personal data, not safe to publish (see
        # CLAUDE.md's "Screenshots must never expose real personal data"). Since there is no
        # domain-scoped action to substitute (the "create our own ir.actions.act_window" trick
        # used elsewhere in this file doesn't apply to a client action), the attendance
        # aggregation itself is patched for the duration of this test to only ever return this
        # fixture's own 4 teachers' rows - the same real method, just pre-filtered, so every
        # downstream computation (groups, periods, guards, absences) naturally narrows to fixture
        # data only. addCleanup (not addClassCleanup): this is a real, process-wide monkeypatch,
        # not a DB write - it must not leak into any other test in this class.
        fixture_employee_ids = (
            teaching_teacher | guard_teacher | wc_guard_teacher | patio_guard_teacher).ids
        course_model = type(self.env['ems.course'])
        original_get_attendance_ids = course_model._get_guard_duty_board_attendance_ids

        def _scoped_get_attendance_ids(course_record):
            return original_get_attendance_ids(course_record).filtered(
                lambda attendance: attendance.calendar_id.employee_id.id in fixture_employee_ids)

        patcher = patch.object(
            course_model, '_get_guard_duty_board_attendance_ids', _scoped_get_attendance_ids)
        patcher.start()
        self.addCleanup(patcher.stop)

        # The board defaults its day tab/shift to the browser's own real wall-clock time (see
        # getDefaultDayAndShift() in guard_duty_board.js) - every fixture above is keyed to Monday
        # morning regardless, so both captures force that combination explicitly via run= instead
        # of depending on when the capture actually happens to execute. A click on an already-
        # active tab/an unchanged <select> value is a harmless no-op (setActiveDay()/
        # onShiftChange() both early-return on no change), so this converges correctly either way.
        force_monday_morning = [
            "document.querySelector('.o_guard_board_tabs .nav-item:nth-of-type(1) .nav-link').click();",
            """
                (function () {
                    var select = document.querySelector('.o_guard_board_shift_select');
                    select.value = 'morning';
                    select.dispatchEvent(new Event('change'));
                })();
            """,
        ]
        force_monday_morning_wait = [
            '.o_guard_board_tabs .nav-item:nth-of-type(1) .nav-link.active',
            '.o_guard_board_guard_cell .o_guard_board_guard_badge',
        ]

        self._capture(
            '/odoo/action-ems.action_guard_duty_board',
            '.o_guard_board', 'guard-duty-01-horari.png',
            login='doc_shot_teacher', wait_for='.o_guard_board_toolbar',
            run=force_monday_morning, wait_after=force_monday_morning_wait,
        )
        self._capture(
            '/odoo/action-ems.action_guard_duty_board',
            '.o_guard_board', 'guard-duty-02-absencies.png',
            login='doc_shot_teacher', wait_for='.o_guard_board_toolbar',
            run=force_monday_morning + [
                "document.querySelector('.o_guard_board_view_tabs .nav-item:nth-of-type(2) .nav-link').click();",
            ],
            wait_after=force_monday_morning_wait + ['.o_guard_board_duty_table'],
        )

    def test_capture_photo_visibility(self):
        # "My Profile" (hr.res_users_action_my) has no stable action URL of its own - its res_id
        # is resolved dynamically per logged-in user, only when reached through the real user-menu
        # click (see static/tests/tours/user_profile_tour.js's own NOTE: navigating straight to
        # the action opens a blank "New" form instead). The capture opens the plain backend
        # ('/odoo') itself; the tour does the whole "open My Profile, go to Preferences" walk.
        # For an ordinary (non can_edit) user, EMS's own view inherit trims the Preferences tab
        # down to just "Disable profile picture" and "Language" (see user_profile_tour.js's
        # ordinary-user tour) - exactly this manual's own scope, so the whole tab's content is
        # safe and small enough to capture as-is, no finer-grained selector needed.
        self._capture(
            '/odoo', '.o_notebook_content', 'foto-01-preferencies.png',
            login='doc_shot_teacher', tour='ems_doc_shot_photo_visibility',
        )

    def test_capture_strike(self):
        from datetime import date

        level, study, group = create_level_study_group(self, 'DOCSTRIKE', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCSTRIKE01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        subject = self.env['ems.subject'].create({
            'code': 'DOCSTRIKESUB', 'acronym': 'BD', 'name': 'Bases de dades',
            'study_ids': [(6, 0, [study.id])],
        })
        space = self.env['ems.space'].create({
            'code': 'DOCSTRIKE-A', 'name': 'Aula Exemple',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        student = self._student(group, 'Nil Exemple')

        # Spans the whole day (same trick as test_capture_attendance_session) so the schedule is
        # "current" regardless of when the capture actually runs.
        weekday = str(date.today().weekday())
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, self.teacher_employee.ids)], 'study_ids': [(6, 0, [study.id])],
            'subject_id': subject.id, 'group_ids': [(6, 0, [group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': weekday,
            'start_time': 0.0, 'end_time': 23.0, 'space_id': space.id,
            'student_ids': [(6, 0, student.ids)],
        })
        self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date.today(),
            'mode': 'manual', 'session_teacher_id': self.teacher_employee.id,
        })

        # Only opens the dialog, never clicks Send - no ems.strike gets created, so no
        # notification email is ever triggered (see ems.strike.create()'s own _notify()/
        # _check_escalation() side effects) and mock_outgoing_email() isn't needed here.
        self._capture(
            '/odoo/action-ems.action_attendance_passlist',
            '.ems-av-strike-dialog[open]', 'strike-01-dialeg.png',
            login='doc_shot_teacher', wait_for='.ems-av-strike-btn',
            click='.ems-av-strike-btn', wait_after='.ems-av-strike-dialog[open]',
        )

    def test_capture_student_academic_data(self):
        level, study, group = create_level_study_group(self, 'DOCACAD', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCACAD01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        student = self._student(group, 'Roc Exemple')

        # Distinctive, unlikely-to-collide start years (same trick as
        # create_student_academic_file()'s own 2098/2099) - two rows so the tab shows real
        # history, not just a single-row table.
        course_prev = self.env['ems.course'].create({'start': 2094, 'end': 2095})
        course_curr = self.env['ems.course'].create({'start': 2095, 'end': 2096})
        # study_name/group_name/tutor_name are plain, denormalized snapshot chars (not computed
        # from study_id/group_id/tutor_id - those stay unset here), same fixture pattern already
        # used by TestDocsScreenshotsHeadOfStudies' own academic-history capture.
        self.env['ems.student.year_record'].create([
            {
                'student_id': student.id, 'course_id': course_prev.id,
                'study_name': study.name, 'group_name': group.name,
                'tutor_name': '0000 Tutora Exemple', 'academic_result': 'repeating',
                'attendance_rate': 82.5,
            },
            {
                'student_id': student.id, 'course_id': course_curr.id,
                'study_name': study.name, 'group_name': group.name,
                'tutor_name': '0000 Tutora Exemple', 'academic_result': 'full',
                'title_obtained': True, 'attendance_rate': 97.0,
            },
        ])

        # A domain-scoped action of our own, restricted to this single fixture student - the
        # "Academic history" tab itself needs no such scoping (year_record_ids is a plain
        # One2many keyed to student_id, naturally showing only this record's own rows), but
        # opening the student's form at all still needs SOME action to navigate through.
        student_action = self.env['ir.actions.act_window'].create({
            'name': 'Alumnes', 'res_model': 'res.partner',
            'view_mode': 'form', 'domain': [('id', '=', student.id)],
        })
        self._capture(
            '/odoo/action-%d/%d' % (student_action.id, student.id),
            '.o_notebook', 'historial-01-academic.png',
            login='doc_shot_teacher', wait_for='.o_notebook',
            click=".o_notebook .nav-link[name='studies']",
            wait_after=".o_field_widget[name='year_record_ids'] .o_data_row + .o_data_row",
        )

    def test_capture_student_list_my_groups(self):
        # Own group: teacher_employee gets a real ems.teaching link to it, which is exactly what
        # res.partner._ems_my_students_domain() / is_my_student key off (see
        # hr.employee._get_own_groups() - teaching_ids.group_id | tutorship_ids).
        level, study, group = create_level_study_group(self, 'DOCMYST', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCMYST01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        subject = self.env['ems.subject'].create({
            'code': 'DOCMYSTSUB', 'acronym': 'BD', 'name': 'Bases de dades',
            'study_ids': [(6, 0, [study.id])],
        })
        self.env['ems.teaching'].create({
            'teacher_id': self.teacher_employee.id, 'subject_id': subject.id, 'group_id': group.id,
        })
        student_own = self._student(group, 'Martina Exemple')

        # A second, unrelated group/student - teacher_employee has no teaching link to it at all,
        # so this one must NOT show once the "My students" filter applies, demonstrating the
        # manual's own claim rather than just asserting it in prose.
        _level2, _study2, group_other = create_level_study_group(self, 'DOCMYST2', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCMYST02', 'acronym': 'SMX', 'name': 'Altres estudis',
        }, group={'acronym': 'A', 'course': 1})
        student_other = self._student(group_other, 'Iu Altregrup')

        # A domain-scoped action of our own (same "actions of our own" trick used throughout this
        # plan) restricted to just these 2 fixture students - guarantees no real student can ever
        # render here regardless of what teacher_employee's own real-world groups might otherwise
        # be, on top of (not instead of) the "My students" filter's own restriction. Mirrors
        # ems.action_student_kanban's own search view/context, but view_mode is 'list,form' only -
        # never 'kanban,...' (the kanban student view has a known, real, un-root-caused client-side
        # stall - see project_role_smoke_student_kanban_hang in memory - not worth risking here).
        action = self.env['ir.actions.act_window'].create({
            'name': 'Alumnat', 'res_model': 'res.partner', 'view_mode': 'list,form',
            'search_view_id': self.env.ref('ems.view_student_search').id,
            'domain': [('id', 'in', (student_own | student_other).ids)],
            'context': {
                'default_contact_type': 'student', 'search_default_students_only': 1,
                'search_default_my_students': 1, 'active_test': False,
            },
        })
        # '.o_list_view' (the whole view root, NOT '.o_content') is needed here, not the usual
        # '.o_content'-only clip target used elsewhere in this project: web.Layout renders the
        # ControlPanel (breadcrumb + searchbar + the two filter chips this manual is actually
        # about) as a SIBLING before '.o_content', not inside it (confirmed by reading
        # web/static/src/search/layout.xml) - '.o_content' alone would silently crop the filter
        # chips out of the shot entirely. The view root flex-stretches to fill the remaining
        # viewport height same as every other flex-stretch case in this plan, hence max_height.
        self._capture(
            '/odoo/action-%d' % action.id,
            '.o_list_view', 'alumnat-01-els-meus-grups.png',
            login='doc_shot_teacher', wait_for='.o_list_renderer .o_data_row',
            max_height=220,
        )

    def test_capture_working_schedules(self):
        level, study, group = create_level_study_group(self, 'DOCSCHED', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCSCHED01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        subject = self.env['ems.subject'].create({
            'code': 'DOCSCHEDSUB', 'acronym': 'BD', 'name': 'Bases de dades',
            'study_ids': [(6, 0, [study.id])],
        })
        space = self.env['ems.space'].create({
            'code': 'DOCSCHED-A', 'name': 'Aula Exemple',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })

        # teacher_employee (employee_type='teacher') already got its own personal calendar
        # auto-created on create() (hr.employee._ems_create_personal_calendar()) - reuse it
        # directly rather than creating and reassigning a second one, since this IS the record
        # "My Profile" actually reads from for the logged-in doc_shot_teacher.
        calendar = self.teacher_employee.resource_calendar_id
        calendar.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning',
                'subject_id': subject.id, 'group_ids': [group.id], 'space_id': space.id,
                'name': 'DOCSCHED: BD',
            },
            # A break right after the teaching block - same non_teaching xmlid the widget uses to
            # tell a break apart visually (brown stripe, per schedule_grid_field.js's own NOTE),
            # set explicitly here rather than relying on the level's own bell-schedule framework
            # auto-fill mechanism (get_derived_break_attendance_data()) - both render identically
            # on the grid, and an explicit row is far simpler to fixture reliably.
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 9.25, 'day_period': 'morning',
                'non_teaching': self.env.ref('ems.non_teaching_br').id, 'name': 'Pati',
            },
        ])

        # Both blocks sit right at the top of the grid (08:00-09:25) so a modest max_height keeps
        # the shot tight without needing to fight the grid's own full-day (08:00-19:00) height -
        # same flex-stretch-style situation as every other big-widget capture in this plan.
        self._capture(
            '/odoo', ".o_field_widget[name='schedule_attendance_ids']", 'horari-01-setmanal.png',
            login='doc_shot_teacher', tour='ems_doc_shot_working_schedule', max_height=260,
        )

    def test_capture_student_notes(self):
        # Shot as the group's tutor, the one role that sees both notes tabs (issue #511).
        tutor_user = create_role_user(self, 'tutor', 'doc_shot_notes_tutor', lang='ca_ES', name='Tutora Exemple')
        __, __, group = create_level_study_group(self, 'DOCNOTES', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCNOTES01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1,
                  'tutor_id': create_role_employee(self, tutor_user, name='0000 Tutora Exemple').id})
        student = self._student(group, 'Roc Exemple')
        student.write({
            'comment': '<p>Treballa millor assegut a les primeres files.</p>',
            'private_notes': '<p>Reunió amb la família el 12/10: seguiment setmanal acordat.</p>',
        })
        student_action = self.env['ir.actions.act_window'].create({
            'name': 'Alumnes', 'res_model': 'res.partner',
            'view_mode': 'form', 'domain': [('id', '=', student.id)],
        })
        self._capture(
            '/odoo/action-%d/%d' % (student_action.id, student.id),
            '.o_notebook', 'notes-01-privades.png',
            login='doc_shot_notes_tutor', wait_for='.o_notebook',
            click=".o_notebook .nav-link[name='private_notes']",
            wait_after=".o_field_widget[name='private_notes'] .odoo-editor-editable p",
        )

    def _student(self, group, name):
        return self.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
        })

    def test_capture_grading(self):
        level, study, group = create_level_study_group(self, 'DOCGRD', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCGRD01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        other_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': level.id, 'study_id': study.id,
        })
        subject = self.env['ems.subject'].create({
            'code': 'DOCGRDSUB', 'acronym': 'BD', 'name': 'Bases de dades',
            'study_ids': [(6, 0, [study.id])],
        })
        outcomes = self.env['ems.outcome'].create([{
            'code': '%s_0%dRA' % (subject.code, n), 'acronym': 'RA%d' % n,
            'name': 'Resultat d\'aprenentatge %d' % n, 'subject_id': subject.id,
        } for n in (1, 2, 3, 4)])
        self.env['ems.planning'].create({
            'study_id': study.id, 'subject_id': subject.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': outcome.id, 'ponderation': weight})
                                     for outcome, weight in zip(outcomes, (35.0, 25.0, 25.0, 15.0))],
        })
        people = [('Laia', 'Casas Riera'), ('Marc', 'Exemple Vidal'), ('Aina', 'Ferrer Mas'),
                  ('Pol', 'Mostra Font'), ('Júlia', 'Puig Roca'), ('Nil', 'Serra Soler')]
        students = self.env['res.partner'].create([{
            'name': '%s %s' % (first, last), 'firstname': first, 'lastname': last,
            'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': group.id,
        } for first, last in people])
        self.env['ems.enrollment'].create([{
            'student_id': student.id, 'group_id': group.id, 'subject_id': subject.id,
        } for student in students])

        Session = self.env['ems.grade_session']
        def session(grade_group, grade_round):
            new = Session.create({'group_id': grade_group.id, 'subject_id': subject.id,
                                  'round': grade_round, 'teacher_id': self.teacher_employee.id})
            new.fill_students()
            return new
        # Round 1: RA1 and RA2 graded - a pass there carries over to round 2 locked.
        first_round = session(group, '1')
        scores = {'RA1': (6, 4, 8, 7, 3, 5), 'RA2': (7, 5, 2, 8, 6, 7)}
        for line in first_round.grade_outcome_line_ids:
            row = scores.get(line.outcome_id.acronym)
            if row:
                line.write({'score': row[students.ids.index(line.student_id.id)], 'is_scored': True})
        first_round.state = 'final'
        # Round 2 (open): carries round 1 over; RA3 graded for some, RA4 still pending, so the
        # internal grade is provisional.
        second_round = session(group, '2')
        for line in second_round.grade_outcome_line_ids.filtered(lambda l: l.outcome_id.acronym == 'RA3'):
            index = students.ids.index(line.student_id.id)
            if index < 4:
                line.write({'score': (7, 4, 6, 8)[index], 'is_scored': True})
        sessions = first_round | second_round | session(other_group, '1') | session(other_group, '2')

        # The native list, scoped to these fixtures for this (rolled-back) test.
        self.env.ref('ems.action_grade_session_tree').domain = str([('id', 'in', sessions.ids)])
        url = '/odoo/action-ems.action_grade_session_tree'
        click = "document.querySelector(%s).click();"
        self._capture(
            url, '.o_web_client', 'teachers-01-llista-sessions.png', login='doc_shot_teacher',
            wait_for='.o_group_header', max_height=360,
            click='.o_group_header', wait_after='.o_group_header.o_group_open + .o_group_header',
            marks=[(".o_main_navbar [data-menu-xmlid='ems.menu_grades']", '1', 'right'),
                   ('.o_group_header.o_group_open .o_group_name', '2', 'text-right'),
                   ('.o_group_header.o_group_open + .o_group_header .o_group_name', '3', 'text-right')],
        )
        form_url = '%s/%d' % (url, second_round.id)
        grid = '.o_grade_matrix tbody tr'
        self._capture(form_url, '.o_grade_matrix', 'teachers-02-graella.png',
                      login='doc_shot_teacher', wait_for=grid)
        # Editing a cell: the floating input a double-click opens, with a grade being typed.
        edit = ("(function () { var cell = document.querySelectorAll("
                "'.o_grade_matrix tbody tr:nth-child(2) td.o_grade_matrix_cell')[2];"
                " cell.dispatchEvent(new MouseEvent('dblclick', {bubbles: true})); })();")
        type_grade = ("(function () { var input = document.querySelector('input.o_grade_matrix_input');"
                      " input.focus(); input.value = '6'; input.dispatchEvent(new Event('input', {bubbles: true})); })();")
        self._capture(form_url, '.o_grade_matrix', 'teachers-03-edicio-cel-la.png',
                      login='doc_shot_teacher', wait_for=grid,
                      run=[edit, type_grade], wait_after=['input.o_grade_matrix_input', 'input.o_grade_matrix_input'],
                      max_height=260)
        # A locked outcome: passed in round 1, padlocked in round 2.
        self._capture(form_url, '.o_grade_matrix', 'teachers-04-ra-bloquejat.png',
                      login='doc_shot_teacher', wait_for=grid, max_height=200)
        self._capture(form_url, '.o_grade_matrix', 'teachers-05-columnes-nota.png',
                      login='doc_shot_teacher', wait_for=grid)
        # Pending changes: a cell edited and committed to the local draft, Apply enabled.
        commit = "document.querySelector('input.o_grade_matrix_input').blur();"
        self._capture(form_url, '.o_grade_matrix', 'teachers-06-aplicar-canvis.png',
                      login='doc_shot_teacher', wait_for=grid, max_height=260,
                      run=[edit, type_grade + commit],
                      wait_after=['input.o_grade_matrix_input', '.o_grade_matrix_toolbar button:not(:disabled)'])
        self._capture(form_url, '.o_form_statusbar .o_statusbar_status', 'teachers-07-estat.png',
                      login='doc_shot_teacher', wait_for='.o_form_statusbar .o_statusbar_status')

    def test_capture_absences_menu(self):
        # The apps menu opened (a trusted mouse click: it ignores a synthetic one), with
        # Employee Attendances - where absences live - marked.
        self._capture(
            '/odoo', '.o_web_client', 'teachers-06-menu-absencies.png', login='doc_shot_teacher',
            wait_for='.o_navbar_apps_menu button', max_height=220,
            click='mouse:.o_navbar_apps_menu button', wait_after='.o-dropdown--menu .dropdown-item',
            marks=[('.o_navbar_apps_menu button', '1', 'right'),
                   (".o-dropdown--menu [data-menu-xmlid='hr_attendance.menu_hr_attendance_root']", '2', 'text-right')],
        )
