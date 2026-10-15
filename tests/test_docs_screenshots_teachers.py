# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Teachers user manuals.

Tagged '-standard' on purpose - see the NOTE in test_docs_screenshots.py for why. Run it by
hand when a documented screen changes its look:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsTeachers' --stop-after-init -c /etc/odoo/odoo.conf"

Batched one manual/test method at a time (see docs/en/developers/shared/testing.md, "DocsScreenshotMixin").
"""
import json
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo.tests.common import HttpCase, tagged

from .common import (
    shift_ems_clock,
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

    def test_capture_absence_atri_confirmation(self):
        """The teacher's own ATRI absence once their Head has validated it: the notice asking
        them to confirm it is requested in ATRI (issue #619)."""
        mock_outgoing_email(self)
        day = datetime(2027, 4, 12).date()
        leave = self.env['hr.leave'].create({
            'employee_id': self.teacher_employee.id,
            'holiday_status_id': self.env.ref('ems.leave_type_atri').id,
            'request_date_from': day, 'request_date_to': day,
            'ems_full_day': True, 'ems_submitted': True, 'ems_responsible_declaration': True,
        })
        leave.action_approve()
        action = self.env['ir.actions.act_window'].create({
            'name': 'Absències', 'res_model': 'hr.leave', 'view_mode': 'list,form',
            'domain': [('id', '=', leave.id)],
        })
        self._capture(
            '/odoo/action-%d/%d' % (action.id, leave.id),
            '.o_content', 'teachers-absences-atri-confirm.png',
            login='doc_shot_teacher', wait_for=".o_form_view .alert-warning a[href*='atriportal']",
            max_height=330,
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
            # The real menu opens with this removable filter on for a teacher (see
            # action_attendance_reports_open); the manual's step 1 refers to its facet.
            'context': {'search_default_my_subjects': 1},
        })
        # "Expand all" unfolds one row level per click (subject first, then student) - see the
        # manual's own step-by-step. tbody tr:nth-of-type(N) counts plain table rows (no
        # group-header/data-row class split like a list view has, so nth-of-type is safe here,
        # unlike the list-view gotcha elsewhere in this file): 1 (Total) -> 2 (+ subject) after
        # the first click -> 4 (+ both students) after the second.
        self._capture(
            '/odoo/action-%d' % pivot_action.id,
            # The whole action, not just '.o_pivot', so the "My subjects" facet in the search
            # bar shows up too.
            '.o_action_manager', 'informes-01-taula-dinamica.png',
            login='doc_shot_teacher', wait_for='.o_searchview_facet',
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
        today = shift_ems_clock(self).date()
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
        student_d = self._student(group, 'Iker Model')

        # The clock is set to 10:00 (shift_ems_clock), inside this whole-day slot: the schedule
        # is the current one whatever time this capture actually runs at.
        weekday = str(today.weekday())
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, self.teacher_employee.ids)], 'study_ids': [(6, 0, [study.id])],
            'subject_id': subject.id, 'group_ids': [(6, 0, [group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': weekday,
            'start_time': 0.0, 'end_time': 23.0, 'space_id': space.id,
            'student_ids': [(6, 0, (student_a + student_b + student_c + student_d).ids)],
        })
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': today,
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
            'start_date': datetime.combine(today, datetime.min.time()),
            'end_date': datetime.combine(today, datetime.max.time()),
            'notes': 'Visita mèdica',
        })
        line_c.write({'status_id': status_miss.id, 'attendance_justification_id': justification.id})
        # Removed from the roll-call (issue #537): greyed out, last in the list, restore button.
        lines.filtered(lambda line: line.student_id == student_d).active = False

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

    def _guard_board_calendar(self, name, rows):
        employee = self.env['hr.employee'].create({'name': name, 'employee_type': 'teacher'})
        calendar = self.env['resource.calendar'].create({'name': f'{name} Calendar', 'employee_id': employee.id})
        employee.resource_calendar_id = calendar
        calendar.apply_schedule_changes([{'dayofweek': '0', 'day_period': 'morning', **row} for row in rows])
        return employee

    def test_capture_guard_duty_schedule(self):
        """Both views of the board with two areas whose time frameworks differ (issue #637): ESO
        has its break at 10:00, vocational training at 11:00, so lessons, breaks and guards only
        line up by clock. Classes, a plain, a WC and two break guards, an approved absence, a
        pending one (with its break guard post to cover) and a class already covered. Every name
        and group is invented."""
        if not self.env.company.current_course_id:
            self.env.company.current_course_id = self.env['ems.course'].create({'start': 1998, 'end': 1999})
        mock_outgoing_email(self)

        Department = self.env['hr.department']
        area_eso = Department.create({'name': 'ESO / BTX (exemple)', 'is_top_level': True, 'top_level_area': 'academic'})
        area_fp = Department.create({'name': 'FP (exemple)', 'is_top_level': True, 'top_level_area': 'academic'})
        br = self.env.ref('ems.non_teaching_br').id
        guard = self.env.ref('ems.non_teaching_g').id
        guard_break = self.env.ref('ems.non_teaching_gb').id
        guard_wc = self.env.ref('ems.non_teaching_gwc').id

        def level_with_framework(acronym, name, periods, breaks):
            level = self.env['ems.level'].create({'acronym': acronym, 'name': name})
            framework = self.env['resource.calendar'].create({
                'name': f'Marc {acronym}', 'is_framework': True, 'level_id': level.id, 'full_time_required_hours': 24})
            for hour_from, hour_to in periods:
                self.env['resource.calendar.attendance'].create({
                    'calendar_id': framework.id, 'name': 'Classe', 'dayofweek': '0',
                    'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning'})
            for hour_from, hour_to in breaks:
                self.env['resource.calendar.attendance'].create({
                    'calendar_id': framework.id, 'name': 'BR: Pati', 'dayofweek': '0',
                    'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning', 'non_teaching': br})
            return level

        eso_periods = [(8, 9), (9, 10), (10 + 25 / 60, 11 + 25 / 60), (11 + 25 / 60, 12 + 25 / 60)]
        fp_periods = [(8, 9), (9, 10), (10, 11), (11 + 25 / 60, 12 + 25 / 60)]
        eso_break, fp_break = (10, 10 + 25 / 60), (11, 11 + 25 / 60)
        level_eso = level_with_framework('T637E', 'ESO exemple', eso_periods, [eso_break])
        level_fp = level_with_framework('T637F', 'FP exemple', fp_periods, [fp_break])

        def study(code, acronym, level, area):
            return self.env['ems.study'].create({
                'code': code, 'acronym': acronym, 'name': f'{acronym} exemple', 'level_id': level.id, 'date': '2026-01-01',
                'managing_department_id': area.id})

        study_eso = study('T637ESO', 'ESOX', level_eso, area_eso)
        study_dam = study('T637DAM', 'DAMX', level_fp, area_fp)
        study_smx = study('T637SMX', 'SMXX', level_fp, area_fp)

        def group(study, level, acronym):
            return self.env['ems.group'].create({
                'course': 1, 'acronym': acronym, 'level_id': level.id, 'study_id': study.id})

        eso_a, eso_b = group(study_eso, level_eso, 'A'), group(study_eso, level_eso, 'B')
        dam, smx = group(study_dam, level_fp, 'A'), group(study_smx, level_fp, 'A')

        subjects = {}
        for acronym, study_record in (('MAT', study_eso), ('CAT', study_eso), ('ANG', study_eso), ('TEC', study_eso),
                                      ('BD', study_dam), ('PRG', study_dam), ('SO', study_smx), ('XAR', study_smx)):
            subjects[acronym] = self.env['ems.subject'].create({
                'code': f'T637{acronym}', 'acronym': acronym, 'name': acronym, 'study_ids': [(6, 0, [study_record.id])]})

        def lesson(period, acronym, group_record):
            return {'hour_from': period[0], 'hour_to': period[1], 'subject_id': subjects[acronym].id,
                    'group_ids': [group_record.id], 'name': acronym}

        def duty(period, non_teaching):
            return {'hour_from': period[0], 'hour_to': period[1], 'non_teaching': non_teaching, 'name': 'Guàrdia'}

        p = eso_periods
        q = fp_periods
        absent = self._guard_board_calendar('0000 Anna Exemple', [lesson(p[0], 'MAT', eso_a), lesson(p[2], 'MAT', eso_b)])
        employees = absent
        employees |= self._guard_board_calendar('0000 Biel Prova', [lesson(p[1], 'CAT', eso_a), lesson(p[0], 'CAT', eso_b), lesson(p[3], 'CAT', eso_a)])
        employees |= self._guard_board_calendar('0000 Carla Mostra', [lesson(p[2], 'ANG', eso_a), lesson(p[1], 'ANG', eso_b)])
        dani = self._guard_board_calendar('0000 Dani Fictici', [lesson(p[3], 'TEC', eso_b), duty(eso_break, guard_break)])
        employees |= dani
        elna = self._guard_board_calendar('0000 Elna Exemple', [lesson(q[0], 'BD', dam), lesson(q[2], 'BD', dam), lesson(q[1], 'SO', smx)])
        employees |= elna
        employees |= self._guard_board_calendar('0000 Ferran Prova', [lesson(q[1], 'PRG', dam), lesson(q[0], 'XAR', smx), lesson(q[3], 'PRG', dam)])
        employees |= self._guard_board_calendar('0000 Gina Mostra', [lesson(q[2], 'XAR', smx), lesson(q[3], 'SO', smx), duty(fp_break, guard_break)])
        employees |= self._guard_board_calendar('0000 Hugo Fictici', [duty(p[0], guard), duty(p[1], guard), duty(eso_break, guard_break)])
        employees |= self._guard_board_calendar('0000 Irene Exemple', [duty(p[2], guard), duty(p[3], guard)])
        jordi = self._guard_board_calendar('0000 Jordi Prova', [duty(q[2], guard), duty(fp_break, guard_break)])
        employees |= jordi
        employees |= self._guard_board_calendar('0000 Laia Mostra', [duty(q[3], guard_wc)])

        today = self.env['ems.datetime_utils'].get_local_today()
        monday = today - timedelta(days=today.weekday())
        self.env['hr.leave'].create({
            'employee_id': absent.id, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': monday, 'request_date_to': monday,
            'ems_full_day': True, 'ems_submitted': True, 'ems_responsible_declaration': True,
        }).action_approve()
        self.env['hr.leave'].create({
            'employee_id': elna.id, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': monday, 'request_date_to': monday,
            'ems_full_day': True, 'ems_submitted': True, 'ems_responsible_declaration': True,
        }).action_approve()
        self.env['hr.leave'].create({
            'employee_id': dani.id, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': monday, 'request_date_to': monday,
            'ems_full_day': True, 'ems_submitted': True, 'ems_responsible_declaration': True,
        })
        self.env['ems.absence_cover'].create({
            'date': monday, 'hour_from': q[2][0], 'hour_to': q[2][1], 'absent_employee_id': elna.id,
            'group_id': dam.id, 'guard_employee_id': jordi.id})

        # The board is centre-wide by design (no domain to scope it by), so its aggregation is
        # narrowed to this fixture's teachers: the dev DB's real timetable, real names included,
        # must never reach a manual's screenshot.
        fixture_ids = employees.ids
        course_model = type(self.env['ems.course'])
        original = course_model._get_guard_duty_board_attendance_ids
        patcher = patch.object(course_model, '_get_guard_duty_board_attendance_ids',
                               lambda course, domain=(): original(course, domain).filtered(
                                   lambda attendance: attendance.calendar_id.employee_id.id in fixture_ids))
        patcher.start()
        self.addCleanup(patcher.stop)
        # Only the fixture's frameworks, so the real ones' breaks don't leak into the rows.
        framework_ids = self.env['resource.calendar'].search([('level_id', 'in', (level_eso | level_fp).ids)]).ids
        calendar_model = type(self.env['resource.calendar'])
        original_search = calendar_model.search

        def scoped_search(model, domain, *args, **kwargs):
            records = original_search(model, domain, *args, **kwargs)
            if ('is_framework', '=', True) in domain:
                records = records.filtered(lambda calendar: calendar.id in framework_ids)
            return records

        search_patcher = patch.object(calendar_model, 'search', scoped_search)
        search_patcher.start()
        self.addCleanup(search_patcher.stop)

        force_monday_morning = [
            "document.querySelector('.o_guard_board_tabs .nav-item:nth-of-type(1) .nav-link').click();",
            """(function () { var select = document.querySelector('.o_guard_board_shift_select');
                select.value = 'morning'; select.dispatchEvent(new Event('change')); })();""",
        ]
        wait = ['.o_guard_board_tabs .nav-item:nth-of-type(1) .nav-link.active', '.o_guard_board_guard_badge']
        self._capture(
            '/odoo/action-ems.action_guard_duty_board', '.o_guard_board', 'guard-duty-01-horari.png',
            login='doc_shot_teacher', wait_for='.o_guard_board_toolbar',
            run=force_monday_morning + [
                "document.querySelector('.o_guard_board_view_tabs .nav-item:nth-of-type(2) .nav-link').click();"],
            wait_after=wait + ['.o_guard_board_table:not(.o_guard_board_duty_table)'])
        self._capture(
            '/odoo/action-ems.action_guard_duty_board', '.o_guard_board', 'guard-duty-02-absencies.png',
            login='doc_shot_teacher', wait_for='.o_guard_board_toolbar',
            run=force_monday_morning, wait_after=wait + ['.o_guard_board_duty_table'])


    def _partial_cover_teacher(self, name, rows):
        employee = self.env['hr.employee'].create({'name': name, 'employee_type': 'teacher'})
        calendar = self.env['resource.calendar'].create({'name': f'{name} Calendar', 'employee_id': employee.id})
        employee.resource_calendar_id = calendar
        calendar.apply_schedule_changes([{'dayofweek': '0', 'day_period': 'morning', **row} for row in rows])
        return employee

    def test_capture_guard_duty_partial_cover(self):
        """A class covered by a guard whose duty only overlaps part of it (issue #637): the guard's
        part with dotted borders and the part still missing. Every name and group is invented."""
        if not self.env.company.current_course_id:
            self.env.company.current_course_id = self.env['ems.course'].create({'start': 1998, 'end': 1999})
        mock_outgoing_email(self)
        area = self.env['hr.department'].create({'name': 'ESO / BTX (exemple)', 'is_top_level': True, 'top_level_area': 'academic'})
        level = self.env['ems.level'].create({'acronym': 'T637P', 'name': 'ESO exemple'})
        study = self.env['ems.study'].create({'code': 'T637P', 'acronym': 'ESOX', 'name': 'ESO exemple', 'level_id': level.id,
                                              'date': '2026-01-01', 'managing_department_id': area.id})
        group = self.env['ems.group'].create({'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id})
        subject = self.env['ems.subject'].create({'code': 'T637PMAT', 'acronym': 'MAT', 'name': 'MAT', 'study_ids': [(6, 0, study.ids)]})
        guard = self.env.ref('ems.non_teaching_g').id
        lesson = (10 + 25 / 60, 11 + 25 / 60)
        anna = self._partial_cover_teacher('0000 Anna Exemple', [{'hour_from': lesson[0], 'hour_to': lesson[1], 'subject_id': subject.id,
                                                    'group_ids': [group.id], 'name': 'MAT'}])
        irene = self._partial_cover_teacher('0000 Irene Exemple', [{'hour_from': lesson[0], 'hour_to': lesson[1], 'non_teaching': guard, 'name': 'G'}])
        hugo = self._partial_cover_teacher('0000 Hugo Fictici', [{'hour_from': 10, 'hour_to': 11, 'non_teaching': guard, 'name': 'G'}])
        laia = self._partial_cover_teacher('0000 Laia Mostra', [{'hour_from': 11, 'hour_to': 12, 'non_teaching': guard, 'name': 'G'}])
        today = self.env['ems.datetime_utils'].get_local_today()
        monday = today + timedelta(days=7 - today.weekday())
        self.env['hr.leave'].create({
            'employee_id': anna.id, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': monday, 'request_date_to': monday,
            'ems_full_day': True, 'ems_submitted': True, 'ems_responsible_declaration': True,
        }).action_approve()
        # Only this fixture's rows, never the dev DB's real timetable (see test_capture_guard_duty_schedule).
        fixture_ids = (anna | irene | hugo | laia).ids
        course_model = type(self.env['ems.course'])
        original = course_model._get_guard_duty_board_attendance_ids
        patcher = patch.object(course_model, '_get_guard_duty_board_attendance_ids', lambda course, domain=(): original(course, domain).filtered(
            lambda attendance: attendance.calendar_id.employee_id.id in fixture_ids))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.env['ems.absence_cover'].board_assign(str(monday), lesson[0], lesson[1], anna.id, group.id, hugo.id, "Exercicis")

        url = f'/odoo/action-ems.action_guard_duty_board?date={monday}&shift=morning&view=table'
        self._capture(url, '.o_guard_board_table_wrap', 'guard-duty-08-cobertura-parcial.png', login='doc_shot_teacher',
                      wait_for='.o_guard_board_missing_tag')

    def test_capture_guard_duty_management(self):
        """Organising absences from the absences table (issues #539, #571, #581, #605), as the
        absent teachers' Department Chief, on next Monday (a past day is read-only): a late entry
        proposal, the possible arrangements, two classes covered by two guards (two colours), the
        guard dialog, the draft notice and the dialog offering the arrangements. Every name and
        group is invented."""
        if not self.env.company.current_course_id:
            self.env.company.current_course_id = self.env['ems.course'].create({'start': 1998, 'end': 1999})
        mock_outgoing_email(self)
        level, study, group_a = create_level_study_group(self, 'DOCMGMT', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCMGMT01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        group_b, group_c = (self.env['ems.group'].create({
            'course': 1, 'acronym': acronym, 'level_id': level.id, 'study_id': study.id}) for acronym in ('B', 'C'))
        subject = self.env['ems.subject'].create({
            'code': 'DOCMGMTSUB', 'acronym': 'BD', 'name': 'Bases de dades', 'study_ids': [(6, 0, [study.id])]})
        chief_user = create_role_user(self, 'department_chief', 'doc_shot_chief', lang='ca_ES', name='Cap Exemple')
        chief = create_role_employee(self, chief_user)
        # Under an area that manages the study, so the absences table heads its column with the area.
        area = self.env['hr.department'].create({'name': 'FP (exemple)', 'is_top_level': True, 'top_level_area': 'academic'})
        department = self.env['hr.department'].create({
            'name': 'Departament Exemple', 'manager_id': chief.id, 'parent_id': area.id})
        study.managing_department_id = department

        def teacher(name, periods, group=None, non_teaching=None):
            employee = self.env['hr.employee'].create({
                'name': name, 'employee_type': 'teacher', 'department_id': department.id})
            employee.parent_id = chief
            calendar = self.env['resource.calendar'].create({
                'name': f'{name} Calendar', 'employee_id': employee.id, 'attendance_ids': [(5, 0, 0)]})
            employee.resource_calendar_id = calendar
            calendar.apply_schedule_changes([{
                'dayofweek': '0', 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
                **({'non_teaching': non_teaching.id, 'name': 'Guàrdia'} if non_teaching else
                   {'subject_id': subject.id, 'group_ids': [group.id], 'name': 'DOCMGMT: BD'}),
            } for hour_from, hour_to in periods])
            return employee

        berta = teacher('0000 Berta Exemple', ((8, 9), (9, 10)), group_a)
        teacher('0000 Jordi Mostra', ((10, 11),), group_a)
        pau = teacher('0000 Pau Prova', ((9, 10),), group_b)
        teacher('0000 Anna Fictícia', ((8, 9), (10, 11)), group_b)
        laura = teacher('0000 Laura Exemple', ((9, 10),), group_c)
        teacher('0000 Iris Mostra', ((8, 9), (10, 11)), group_c)
        guard = self.env.ref('ems.non_teaching_g')
        marti = teacher('0000 Martí Mostra', ((8, 9), (9, 10), (10, 11)), non_teaching=guard)
        roger = teacher('0000 Roger Fictici', ((8, 9), (9, 10), (10, 11)), non_teaching=guard)
        teacher('0000 Clara Prova', ((8, 9), (9, 10), (10, 11)), non_teaching=guard)

        day = self.env['ems.datetime_utils'].get_local_today() + timedelta(days=1)
        while day.weekday() != 0:
            day += timedelta(days=1)
        for employee, hours in ((berta, (8, 10)), (pau, (9, 10)), (laura, (9, 10))):
            self.env['hr.leave'].create({
                'employee_id': employee.id, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
                'request_date_from': day, 'request_date_to': day, 'ems_full_day': False,
                'request_hour_from': hours[0], 'request_hour_to': hours[1],
                'ems_submitted': True, 'ems_responsible_declaration': True,
            }).action_approve()
        Cover = self.env['ems.absence_cover']
        Cover.board_assign(str(day), 9, 10, pau.id, group_b.id, marti.id, "Exercicis de la pàgina 12")
        Cover.board_assign(str(day), 9, 10, laura.id, group_c.id, roger.id, "Repàs del tema 3")

        # Only this fixture's rows, never the dev DB's real timetable (see test_capture_guard_duty_schedule).
        fixture_ids = department.member_ids.ids
        course_model = type(self.env['ems.course'])
        original = course_model._get_guard_duty_board_attendance_ids
        patcher = patch.object(course_model, '_get_guard_duty_board_attendance_ids', lambda course, domain=(): original(course, domain).filtered(
            lambda attendance: attendance.calendar_id.employee_id.id in fixture_ids))
        patcher.start()
        self.addCleanup(patcher.stop)

        # The board keeps its day, shift and view in the URL, so it opens straight on next Monday.
        url = f'/odoo/action-ems.action_guard_duty_board?date={day}&shift=morning&view=table'
        open_class = """[...document.querySelectorAll('.o_guard_board_duty_table td.o_guard_board_absence_cell')]
            .find((cell) => cell.querySelector('.o_guard_board_block_time').textContent.includes('%s'))
            .querySelector('.o_guard_board_absence_manageable:not(.o_guard_board_absence_struck)').click();"""
        self._capture(
            url, '.o_guard_board', 'guard-duty-03-organitzar.png', login='doc_shot_chief',
            wait_for='.o_guard_board_proposals .o_guard_board_action_option',
        )
        self._capture(
            url, '.modal-content', 'guard-duty-04-enviar-guardia.png', login='doc_shot_chief',
            wait_for='.o_guard_board_proposals .o_guard_board_action_option',
            run=[open_class % '09:00-10:00',
                 # The dialog opens on the first arrangement the board detected (issue #605): this
                 # shot is about sending a guard.
                 "document.querySelector('.o_guard_cover_mode_guard').click();",
                 # A closed <select> only shows its chosen option: pick the guard who has covered
                 # the fewest classes, so the shot shows the count next to the name (issue #600).
                 """(function () {
                    var select = document.querySelector('.o_guard_cover_guard_select');
                    select.selectedIndex = [...select.options].findIndex((option) => option.textContent.includes('Clara'));
                    select.dispatchEvent(new Event('change'));
                 })();"""],
            wait_after=['.o_guard_cover_mode_guard', '.o_guard_cover_guard_select', '.o_guard_cover_assign:enabled'],
        )
        self._capture(
            url, '.o_form_view .o_form_sheet', 'guard-duty-05-comunicat.png', login='doc_shot_chief',
            wait_for='.o_guard_board_proposals .o_guard_board_action_option',
            run=["document.querySelector('.o_guard_board_proposals .o_guard_board_action_button').click();"],
            wait_after=['.o_form_view .alert-info'], max_height=760,
        )
        # Issues #605, #645: the arrangement plans the board detected for the classes still left
        # without anybody, each with its steps to check (0000 Jordi Mostra can swap or move his
        # 10:00 lesson with the group), and the dialog of one of those classes, which offers them
        # above sending a guard.
        self._capture(
            url, '.o_guard_board_arrangements', 'guard-duty-06-reorganitzacions.png', login='doc_shot_chief',
            wait_for='.o_guard_board_arrangements .o_guard_board_plan_apply',
        )
        self._capture(
            url, '.modal-content', 'guard-duty-07-aplicar-reorganitzacio.png', login='doc_shot_chief',
            wait_for='.o_guard_board_arrangements .o_guard_board_plan_apply',
            run=[open_class % '08:00-09:00'], wait_after=['.o_guard_cover_option'],
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

    def test_capture_task_digest(self):
        # 1. Where to turn it off: the same Preferences tab as test_capture_photo_visibility,
        # with the "Notifications" option marked.
        self._capture(
            '/odoo', '.o_notebook_content', 'resum-tasques-01-preferencies.png',
            login='doc_shot_teacher', tour='ems_doc_shot_photo_visibility',
            marks=[(".o_field_widget[name='ems_task_digest']", '1', 'right')],
        )
        # 2. The email itself. A few pending tasks of different kinds on invented records, the
        # digest rendered exactly as the cron would send it (models/shared/task_digest.py), then
        # shown in the browser in place of the backend, under its subject line, to capture it.
        def records(names):
            return self.env['res.partner'].create([{'name': name} for name in names])
        today = self.env['ems.datetime_utils'].get_local_today()
        tasks = (
            ('ems.mail_activity_convalidation_review', records(
                ['Laia Serra Puig', 'Marc Vidal Roca', 'Nora Ferrer Soler']),
             "Sol·licitud de convalidació"),
            ('ems.mail_activity_absence_document_validate', records(['Jordi Exemple Mas']),
             "Validar el justificant"),
            ('ems.mail_activity_attendance_correction', records(['Anna Exemple Font']),
             "Correcció de fitxatge"),
        )
        for offset, (activity_type, partners, summary) in enumerate(tasks):
            for partner in partners:
                partner.activity_schedule(activity_type, user_id=self.teacher_user.id, summary=summary,
                                          date_deadline=today + timedelta(days=offset - 1))
        template = self.env.ref('ems.email_template_task_digest').with_context(lang='ca_ES')
        subject = template._render_field('subject', self.teacher_user.ids)[self.teacher_user.id]
        body = template._render_field('body_html', self.teacher_user.ids)[self.teacher_user.id]
        page = (
            '<div id="ems-digest" style="background:#fff;padding:24px;max-width:760px;">'
            '<div style="font-family:Arial,sans-serif;font-size:16px;font-weight:bold;'
            'padding-bottom:12px;margin-bottom:12px;border-bottom:1px solid #dadce0;">%s</div>%s</div>'
        ) % (subject, body)
        self._capture(
            '/odoo', '#ems-digest', 'resum-tasques-02-correu.png',
            login='doc_shot_teacher', wait_for='.o_main_navbar',
            run='document.body.innerHTML = %s;' % json.dumps(page), wait_after='#ems-digest',
        )

    def test_capture_strike(self):
        from datetime import date
        today = shift_ems_clock(self).date()

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

        # Same as test_capture_attendance_session: shifted clock, so the schedule is the current one
        # whenever the capture runs.
        weekday = str(today.weekday())
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
            'attendance_schedule_id': schedule.id, 'date': today,
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

    def test_capture_strike_standalone(self):
        # Issue #402: the "New strike" dialog of Coexistence > Strikes. Same as above, it only
        # opens the dialog and never sends, so no ems.strike (nor email) is created.
        self._capture(
            '/odoo/action-ems.action_strike_list',
            '.modal-content', 'strike-02-fora-de-classe.png',
            login='doc_shot_teacher', wait_for='.o_list_button_add_strike',
            click='.o_list_button_add_strike', wait_after='.modal .o_form_view',
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

    def test_capture_planning(self):
        level, study, group = create_level_study_group(self, 'DOCPLN', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCPLN01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        subjects = self.env['ems.subject'].create([{
            'code': 'DOCPLN%s' % acronym, 'acronym': acronym, 'name': name,
            'study_ids': [(6, 0, [study.id])],
        } for acronym, name in (('BD', 'Bases de dades'), ('PRG', 'Programació'))])
        self.env['ems.teaching'].create([{
            'teacher_id': self.teacher_employee.id, 'group_id': group.id, 'subject_id': subject.id,
        } for subject in subjects])
        current = self.env.company.current_course_id
        previous = self.env['ems.course'].search([('start', '=', current.start - 1)], limit=1) \
            or self.env['ems.course'].create({'start': current.start - 1, 'end': current.start})

        def planning(subject, course, internal, weights):
            outcomes = self.env['ems.outcome'].search([('subject_id', '=', subject.id)]) \
                or self.env['ems.outcome'].create([{
                    'code': '%s_0%dRA' % (subject.code, n), 'acronym': 'RA%d' % n,
                    'name': "Resultat d'aprenentatge %d" % n, 'subject_id': subject.id,
                } for n in range(1, len(weights) + 1)])
            return self.env['ems.planning'].create({
                'study_id': study.id, 'subject_id': subject.id, 'course_id': course.id,
                'internal_ponderation': internal, 'external_ponderation': 100.0 - internal,
                'planning_outcome_ids': [(0, 0, {'outcome_id': outcome.id, 'ponderation': weight})
                                         for outcome, weight in zip(outcomes, weights)],
            })
        shown = planning(subjects[0], current, 90.0, (35.0, 25.0, 25.0, 15.0))
        planning(subjects[1], current, 90.0, (40.0, 30.0, 30.0))
        # Last year's: hidden by the "current course" filter the list opens with.
        planning(subjects[0], previous, 85.0, (40.0, 20.0, 25.0, 15.0))

        url = '/odoo/action-ems.action_planning_tree'
        self._capture(url, '.o_web_client', 'programacions-01-llista.png', login='doc_shot_teacher',
                      wait_for='.o_data_row', max_height=260)
        self._capture('%s/%d' % (url, shown.id), '.o_form_sheet', 'programacions-02-formulari.png',
                      login='doc_shot_teacher', wait_for='.o_field_one2many .o_data_row')
