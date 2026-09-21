# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Head of Studies user manuals.

Tagged '-standard' on purpose - see the identical NOTE in test_docs_screenshots.py (this file
is the "second consumer" that note already anticipates). Run it by hand:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsHeadOfStudies' --stop-after-init -c /etc/odoo/odoo.conf"

Writes PNGs to /tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR); copy them into
docs/assets/head_of_studies/ by hand afterwards. See test_docs_screenshots.py's own module
docstring for the full rationale (rolled-back transaction, made-up people, one element per shot).
"""
from datetime import datetime

from odoo.tests.common import HttpCase, tagged

from .common import (
    DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user,
    next_student_id,
)


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsHeadOfStudies(HttpCase, DocsScreenshotMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hos_user = create_role_user(cls, 'head_of_studies', 'doc_shot_hos', lang='ca_ES',
                                        name='Cap Estudis', email='cap.estudis@example.com')
        cls.hos_employee = create_role_employee(cls, cls.hos_user, name='0000 Cap Estudis')

        # --- Absences (Management > Absences) ---
        cls.other_employee = cls.env['hr.employee'].create({
            'name': '0000 Marta Exemple', 'employee_type': 'teacher',
        })
        cls.leave_type_health = cls.env.ref('ems.leave_type_health')
        cls.leave_type_justified = cls.env.ref('ems.leave_type_justified')
        cls.leave_pending = cls.env['hr.leave'].create({
            'employee_id': cls.other_employee.id, 'holiday_status_id': cls.leave_type_justified.id,
            'request_date_from': datetime(2027, 3, 8).date(), 'request_date_to': datetime(2027, 3, 8).date(),
            'ems_submitted': True, 'ems_responsible_declaration': True,
        })
        cls.leave_health = cls.env['hr.leave'].create({
            'employee_id': cls.hos_employee.id, 'holiday_status_id': cls.leave_type_health.id,
            'request_date_from': datetime(2027, 3, 15).date(), 'request_date_to': datetime(2027, 3, 15).date(),
            'ems_submitted': True, 'ems_responsible_declaration': True,
        })
        cls.leave_health.sudo().action_approve()
        # A third one approved by both, so the list shows the three stages of the double
        # approval: pending for both, approved by the Head only, and approved by both.
        cls.leave_done = cls.env['hr.leave'].create({
            'employee_id': cls.other_employee.id, 'holiday_status_id': cls.leave_type_justified.id,
            'request_date_from': datetime(2027, 3, 1).date(), 'request_date_to': datetime(2027, 3, 1).date(),
            'ems_full_day': True, 'ems_submitted': True, 'ems_responsible_declaration': True,
        })
        cls.leave_done.sudo().action_approve()
        cls.leave_done.sudo().action_ems_direction_done()
        cls.absence_action = cls.env['ir.actions.act_window'].create({
            'name': 'Absències',
            'res_model': 'hr.leave',
            'view_mode': 'list,form',
            'domain': [('id', 'in', [cls.leave_pending.id, cls.leave_health.id, cls.leave_done.id])],
            'context': {'hide_employee_name': 0},
        })

        # --- Academic history ---
        # The native action_year_record_list has no domain of its own (relies on
        # group_student_data_reader access, not view scoping) - HoS can see every real
        # student's history through it, so it would leak real production data/counts into
        # the screenshot. Use our own domain-scoped action instead, same trick as
        # absence_action/pivot_action below.
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'DHOS',
            level={'name': 'Formació professional'}, study={'name': 'Estudi DHOS'})
        cls.course_2526 = cls.env['ems.course'].search([('start', '=', 2025)], limit=1) \
            or cls.env['ems.course'].create({'start': 2025, 'end': 2026})
        year_records = cls.env['ems.student.year_record']
        for name, result, rate in (('Laia Exemple', 'full', 96.5), ('Jordi Mostra', 'repeating', 78.2)):
            student = cls._student(name)
            year_records |= cls.env['ems.student.year_record'].create({
                'student_id': student.id, 'course_id': cls.course_2526.id,
                'study_name': cls.study.name, 'group_name': cls.group.name,
                'academic_result': result, 'attendance_rate': rate,
            })
        cls.year_record_action = cls.env['ir.actions.act_window'].create({
            'name': 'Historial acadèmic',
            'res_model': 'ems.student.year_record',
            'view_mode': 'list,form',
            'domain': [('id', 'in', year_records.ids)],
            'context': {'search_default_group_by_course': 1},
        })

        # --- Attendance correction ---
        cls.correction_employee = cls.env['hr.employee'].create({
            'name': '0000 Anna Exemple', 'employee_type': 'teacher',
        })
        cls.attendance = cls.env['hr.attendance'].create({
            'employee_id': cls.correction_employee.id,
            'check_in': datetime(2027, 3, 10, 8, 5), 'check_out': datetime(2027, 3, 10, 16, 0),
        })
        cls.correction = cls.env['ems.attendance_correction'].create({
            'attendance_id': cls.attendance.id,
            'requested_check_in': 8.0, 'reason': "Vaig fitxar tard per un problema amb el lector.",
        })

        # --- Attendance reports pivot ---
        cls.subject = cls.env['ems.subject'].create({
            'code': 'DHOS01', 'acronym': 'DHS', 'name': 'Assignatura Exemple',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'DHOS-A', 'name': 'Aula Exemple',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.other_employee.id])], 'study_ids': [(6, 0, [cls.study.id])],
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group.id])],
            'start_date': datetime(2020, 1, 1).date(), 'end_date': datetime(2030, 12, 31).date(),
        })
        schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 9.0, 'end_time': 10.0, 'space_id': cls.space.id,
        })
        session = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': datetime(2027, 3, 9).date(),
            'mode': 'manual', 'session_teacher_id': cls.other_employee.id,
        })
        status_attended = cls.env.ref('ems.attendance_status_attended')
        status_miss = cls.env.ref('ems.attendance_status_miss')
        report_student_a = cls._student('Oriol Exemple')
        report_student_b = cls._student('Nuria Mostra')
        cls.report_lines = cls.env['ems.attendance_session_line'].create([
            {'student_id': report_student_a.id, 'status_id': status_attended.id, 'attendance_session_id': session.id},
            {'student_id': report_student_b.id, 'status_id': status_miss.id, 'attendance_session_id': session.id},
        ])
        pivot_view = cls.env.ref('ems.view_attendance_report_analysis_pivot')
        cls.pivot_action = cls.env['ir.actions.act_window'].create({
            'name': 'Informes d\'assistència',
            'res_model': 'ems.attendance_session_line',
            'view_mode': 'pivot',
            'views': [(pivot_view.id, 'pivot')],
            'domain': [('id', 'in', cls.report_lines.ids)],
        })

        # --- Notices ---
        cls.notice_a = cls.env['ems.notice'].with_user(cls.hos_user).create({
            'subject': 'Reunió de nivell', 'message': '<p>Recordatori de la reunió de nivell.</p>',
            'recipient_type': 'both', 'group_ids': [(6, 0, [cls.group.id])],
        })
        cls.notice_b = cls.env['ems.notice'].with_user(cls.hos_user).create({
            'subject': 'Sortida cultural', 'message': '<p>Informació sobre la sortida.</p>',
            'recipient_type': 'families', 'group_ids': [(6, 0, [cls.group.id])],
        })

        # --- Staff management (fresh teacher, no Google account yet) ---
        # No work_email on purpose: google_ws_state only computes to 'none' (the state that
        # shows "Create Google account") when work_email is unset - setting one flips it
        # straight to 'pending_user' ("Create EMS User" shown instead).
        cls.new_teacher = cls.env['hr.employee'].create({
            'name': '0000 Teacher Exemple', 'employee_type': 'teacher',
        })

        # --- Strike ---
        cls.strike_student = cls._student('Pol Exemple')
        cls.strike_reason = cls.env.ref('ems.strike_reason_other', raise_if_not_found=False) \
            or cls.env['ems.strike.reason'].create({'name': 'Altres'})
        cls.strike = cls.env['ems.strike'].create({
            'student_id': cls.strike_student.id, 'teacher_id': cls.hos_employee.id,
            'reason_id': cls.strike_reason.id, 'kicked_out': True,
            'notes': 'Comportament disruptiu reiterat a classe.',
        })

    @classmethod
    def _student(cls, name):
        return cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
        })

    def test_capture_head_of_studies_screenshots(self):
        self._capture(
            '/odoo/action-%d' % self.absence_action.id,
            # Not '.o_content'/'.o_list_renderer': both stretch to fill the remaining
            # viewport height via flex, and their own left edge stays solid white the whole
            # way down - the trim's background-color reference (grey, sampled from the
            # bottom-right corner) never matches that white strip, so it's never cropped off
            # and the empty run below the real rows survives into the final image. '.o_list_table'
            # is the actual <table>, sized to its own rows only - no flex-stretch, nothing
            # left for _trim to even need to do. Same fix applied to academic-history below.
            '.o_list_table', 'hos-absences-list.png',
            login='doc_shot_hos', wait_for='.o_list_renderer .o_data_row',
        )
        self._capture(
            '/odoo/action-%d' % self.year_record_action.id,
            # '.o_content', not '.o_list_table' here (unlike the absences capture above):
            # this capture clicks to expand a group first, and '.o_list_table's own
            # getBoundingClientRect() was read before the table had relaid-out for the
            # second row - even after the click's wait_after already confirmed that row
            # exists in the DOM (found by actually looking at the resulting PNG: consistently
            # 104px tall, one row short, regardless of which wait_after selector was tried).
            # '.o_content' doesn't race the same way - its own box doesn't depend on the
            # table's just-updated height - and _trim's pixel-diff crop (run against the
            # already-painted screenshot, strictly after that layout settles) still produces
            # a tight, single-margin crop here since this view has no left sidebar to trip it.
            '.o_content', 'hos-academic-history-list.png',
            login='doc_shot_hos', wait_for='.o_list_renderer .o_group_header',
            # wait_after must confirm BOTH fixture rows, not just the first - a plain
            # '.o_data_row' wait_after fired as soon as the first one appeared. ':nth-of-type(2)'
            # does NOT fix it either: nth-of-type counts position among ALL sibling <tr>
            # regardless of class, and the preceding o_group_header row is itself a <tr> - so
            # ':nth-of-type(2)' actually matches the FIRST data row (position 2 counting the
            # group header), not the second. The adjacent-sibling combinator below correctly
            # requires two o_data_row in a row.
            click='.o_list_renderer .o_group_header',
            wait_after='.o_list_renderer .o_data_row + .o_data_row',
        )
        self._capture(
            '/odoo/action-ems.action_attendance_correction_tree',
            '.o_content', 'hos-attendance-correction-list.png',
            login='doc_shot_hos', wait_for='.o_list_renderer .o_data_row',
        )
        self._capture(
            '/odoo/action-%d' % self.pivot_action.id,
            '.o_content', 'hos-attendance-reports-pivot.png',
            login='doc_shot_hos', wait_for='.o_pivot_view table',
        )
        self._capture(
            '/odoo/action-ems.action_communication_list',
            '.o_content', 'hos-notice-only-mine.png',
            login='doc_shot_hos', wait_for='.o_list_renderer .o_data_row',
        )
        self._capture(
            '/odoo/action-ems.action_employee_kanban/%d' % self.new_teacher.id,
            # Not '.o_form_statusbar' alone: the employee form has two <header> blocks (the
            # native one, its own button hidden via xpath, plus EMS's own with the real
            # buttons) so plain querySelector('.o_form_statusbar') grabs the first (empty,
            # near-zero-height) one instead of ours - target the button itself instead.
            '.o_form_statusbar button[name="action_create_google_account"]',
            'hos-staff-management-create-account.png',
            login='doc_shot_hos', wait_for='.o_form_statusbar button[name="action_create_google_account"]',
        )
        self._capture(
            '/odoo/action-ems.action_strike_list/%d' % self.strike.id,
            '.o_form_sheet', 'hos-strike-kicked-out.png',
            login='doc_shot_hos', wait_for=".o_form_sheet div[name='kicked_out']",
        )
