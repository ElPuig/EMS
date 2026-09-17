# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Teachers user manuals.

Tagged '-standard' on purpose - see the NOTE in test_docs_screenshots.py for why. Run it by
hand when a documented screen changes its look:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsTeachers' --stop-after-init -c /etc/odoo/odoo.conf"

Batched one manual/test method at a time (see plans/user_manual_screenshots.md).
"""
from datetime import datetime

from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, create_role_employee, create_role_user


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
