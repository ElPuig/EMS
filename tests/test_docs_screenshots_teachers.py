# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Teachers user manuals.

Tagged '-standard' on purpose - see the NOTE in test_docs_screenshots.py for why. Run it by
hand when a documented screen changes its look:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsTeachers' --stop-after-init -c /etc/odoo/odoo.conf"

Batched one manual/test method at a time (see plans/user_manual_screenshots.md).
"""
from datetime import datetime

from odoo.tests.common import HttpCase, tagged

from .common import (
    DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user,
    next_student_id,
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

    def _student(self, group, name):
        return self.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
        })
