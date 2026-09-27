# -*- coding: utf-8 -*-

import html
import json
import re
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.ems.models.meetings.presence import kiosk_short_name

from .common import create_role_employee, create_role_user, mock_outgoing_email


class MeetingPresenceFixtures:
    """Fictitious staff shared by the model tests and the controller tests: a teacher in a
    department, another in a child department, an ASP, an archived teacher and a workgroup."""

    @classmethod
    def _setup_fixtures(cls):
        # hr.employee.create() may post a chatter note that reaches real followers - see
        # CLAUDE.md's "Email safety in tests".
        mock_outgoing_email(cls)
        Employee = cls.env['hr.employee']
        cls.department = cls.env['hr.department'].create({'name': 'Test Presence Department'})
        cls.child_department = cls.env['hr.department'].create({
            'name': 'Test Presence Child Department', 'parent_id': cls.department.id,
        })
        cls.teacher = Employee.create({
            'name': 'Presence Teacher', 'employee_type': 'teacher',
            'barcode': 'TESTPRES001', 'department_id': cls.department.id,
        })
        cls.child_teacher = Employee.create({
            'name': 'Presence Child Teacher', 'employee_type': 'teacher',
            'barcode': 'TESTPRES002', 'department_id': cls.child_department.id,
        })
        cls.asp = Employee.create({
            'name': 'Presence ASP', 'employee_type': 'asp', 'barcode': 'TESTPRES003',
        })
        cls.archived_teacher = Employee.create({
            'name': 'Presence Archived Teacher', 'employee_type': 'teacher',
            'barcode': 'TESTPRES004', 'active': False,
        })
        cls.workgroup = cls.env['ems.workgroup'].create({
            'name': 'Test Presence Workgroup',
            'employee_ids': [(6, 0, [cls.teacher.id, cls.asp.id])],
        })

    def _public(self, employee):
        return self.env['hr.employee.public'].browse(employee.id)

    @classmethod
    def _session(cls, **vals):
        return cls.env['ems.meeting.presence'].create({'name': 'Test staff meeting', **vals})

    def _line(self, session, employee):
        return session.line_ids.filtered(lambda line: line.employee_id.id == employee.id)

    @contextmanager
    def _at(self, moment):
        """Freeze 'now' for whatever the scan reads it for. Only for the code that asks for it at
        call time: a field default keeps the function it was declared with, so a session that has
        to start at a given moment is created with an explicit 'date'."""
        with patch.object(fields.Datetime, 'now', return_value=fields.Datetime.to_datetime(moment)):
            yield


class TestMeetingPresence(MeetingPresenceFixtures, TransactionCase):
    """Issue #521: attendance to a meeting confirmed with the NFC tag. See
    docs/en/developers/meetings/meeting_presence.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_fixtures()

    # -- convened list -------------------------------------------------------------------

    def test_all_teachers_scope_convenes_active_teachers_only(self):
        session = self._session(scope='all_teachers')
        convened = session.line_ids.employee_id
        self.assertIn(self._public(self.teacher), convened)
        self.assertIn(self._public(self.child_teacher), convened)
        self.assertNotIn(self._public(self.asp), convened)
        self.assertNotIn(self._public(self.archived_teacher), convened)
        self.assertTrue(all(line.state == 'pending' and line.is_convened for line in session.line_ids))

    def test_all_staff_scope_includes_asp(self):
        convened = self._session(scope='all_staff').line_ids.employee_id
        self.assertIn(self._public(self.teacher), convened)
        self.assertIn(self._public(self.asp), convened)
        self.assertNotIn(self._public(self.archived_teacher), convened)

    def test_department_scope_includes_child_departments(self):
        session = self._session(scope='department', department_id=self.department.id)
        self.assertEqual(session.line_ids.employee_id,
                         self._public(self.teacher) | self._public(self.child_teacher))

    def test_workgroup_scope_convenes_its_members(self):
        session = self._session(scope='workgroup', workgroup_id=self.workgroup.id)
        self.assertEqual(session.line_ids.employee_id, self._public(self.teacher) | self._public(self.asp))

    def test_manual_scope_starts_empty(self):
        self.assertFalse(self._session(scope='manual').line_ids)

    def test_scope_target_is_required(self):
        with self.assertRaises(ValidationError):
            self._session(scope='department')
        with self.assertRaises(ValidationError):
            self._session(scope='workgroup')

    def test_load_convened_only_adds_never_removes(self):
        session = self._session(scope='department', department_id=self.department.id)
        # Someone convened by hand, who is not in the scope, and a scan already made.
        extra = self.env['ems.meeting.presence.line'].create({
            'presence_id': session.id, 'employee_id': self.asp.id,
        })
        self._line(session, self.teacher).state = 'present'
        # The scope grows: a new teacher joins the department.
        newcomer = self.env['hr.employee'].create({
            'name': 'Presence Newcomer', 'employee_type': 'teacher', 'department_id': self.department.id,
        })
        session.action_load_convened()
        self.assertIn(self._public(newcomer), session.line_ids.employee_id)
        self.assertIn(extra, session.line_ids)
        self.assertEqual(self._line(session, self.teacher).state, 'present')
        self.assertEqual(len(session.line_ids.filtered(lambda line: line.employee_id.id == self.teacher.id)), 1)

    def test_employee_is_unique_per_session(self):
        session = self._session(scope='manual')
        Line = self.env['ems.meeting.presence.line']
        Line.create({'presence_id': session.id, 'employee_id': self.teacher.id})
        with self.assertRaises(Exception):
            Line.create({'presence_id': session.id, 'employee_id': self.teacher.id})

    # -- time window ---------------------------------------------------------------------

    def test_a_new_session_lasts_two_hours_by_default(self):
        session = self._session(scope='manual', date='2026-10-01 17:00:00')
        self.assertEqual(session.duration, 2.0)
        self.assertEqual(session.date_end, datetime(2026, 10, 1, 19, 0, 0))

    def test_end_and_duration_follow_each_other(self):
        session = self._session(scope='manual', date='2026-10-01 17:00:00', date_end='2026-10-01 20:30:00')
        self.assertEqual(session.duration, 3.5)
        session.duration = 1.5
        self.assertEqual(session.date_end, datetime(2026, 10, 1, 18, 30, 0))
        # Moving the start moves the whole window: the meeting keeps its length.
        session.date = '2026-10-02 09:00:00'
        self.assertEqual((session.date_end, session.duration), (datetime(2026, 10, 2, 10, 30, 0), 1.5))
        session.date_end = '2026-10-02 12:00:00'
        self.assertEqual(session.duration, 3.0)

    def test_the_meeting_must_end_after_it_starts(self):
        with self.assertRaises(ValidationError):
            self._session(scope='manual', date='2026-10-01 17:00:00', date_end='2026-10-01 16:00:00')
        session = self._session(scope='manual')
        with self.assertRaises(ValidationError):
            session.duration = 0

    def test_the_form_keeps_start_end_and_duration_consistent(self):
        with Form(self.env['ems.meeting.presence']) as form:
            form.name = 'Form meeting'
            form.scope = 'manual'
            form.date = '2026-10-01 17:00:00'
            self.assertEqual(form.date_end, datetime(2026, 10, 1, 19, 0, 0))
            form.duration = 3.0
            self.assertEqual(form.date_end, datetime(2026, 10, 1, 20, 0, 0))
            form.date_end = '2026-10-01 18:30:00'
            self.assertEqual(form.duration, 1.5)
            form.date = '2026-10-05 09:00:00'
            self.assertEqual(form.date_end, datetime(2026, 10, 5, 10, 30, 0))
        session = form.record
        self.assertEqual((session.date, session.date_end, session.duration),
                         (datetime(2026, 10, 5, 9, 0, 0), datetime(2026, 10, 5, 10, 30, 0), 1.5))

    def test_the_kiosk_only_takes_tags_inside_the_window(self):
        session = self._session(scope='department', department_id=self.department.id,
                                date='2026-10-01 17:00:00', date_end='2026-10-01 19:00:00')
        session.action_open()
        with self._at('2026-10-01 16:59:59'):
            self.assertEqual(session._ems_kiosk_status(), 'not_open')
            self.assertEqual(session._ems_register_scan('TESTPRES001')['status'], 'not_open')
        self.assertFalse(session.line_ids.filtered(lambda line: line.state == 'present'))
        with self._at('2026-10-01 17:00:00'):
            self.assertEqual(session._ems_kiosk_status(), 'open')
            self.assertEqual(session._ems_register_scan('TESTPRES001')['status'], 'ok')
        with self._at('2026-10-01 19:00:00'):
            self.assertEqual(session._ems_register_scan('TESTPRES002')['status'], 'ok')
        with self._at('2026-10-01 19:00:01'):
            self.assertEqual(session._ems_kiosk_status(), 'closed')
            self.assertEqual(session._ems_register_scan('TESTPRES003')['status'], 'closed')
        self.assertEqual(session.present_count, 2)
        self.assertFalse(self._line(session, self.asp))

    def test_the_window_does_not_open_a_draft_or_reopen_a_closed_session(self):
        session = self._session(scope='manual', date='2026-10-01 17:00:00')
        with self._at('2026-10-01 18:00:00'):
            self.assertEqual(session._ems_kiosk_status(), 'not_open')
            session.action_open()
            self.assertEqual(session._ems_kiosk_status(), 'open')
            session.action_close()
            self.assertEqual(session._ems_kiosk_status(), 'closed')

    def test_marking_by_hand_ignores_the_window(self):
        session = self._session(scope='department', department_id=self.department.id,
                                date='2026-10-01 17:00:00', date_end='2026-10-01 19:00:00')
        with self._at('2026-10-02 10:00:00'):
            self._line(session, self.teacher).state = 'present'
        self.assertEqual(self._line(session, self.teacher).state, 'present')

    def test_the_kiosk_window_label_uses_the_local_time(self):
        session = self._session(scope='manual', date='2026-10-01 15:00:00', date_end='2026-10-01 17:00:00')
        # 15:00 UTC is 17:00 in Madrid (CEST).
        self.assertEqual(session.with_context(tz='Europe/Madrid')._ems_window_label(), '17:00 - 19:00')
        overnight = self._session(scope='manual', date='2026-10-01 20:00:00', date_end='2026-10-02 06:30:00')
        self.assertEqual(overnight.with_context(tz='Europe/Madrid')._ems_window_label(), '01/10 22:00 - 02/10 08:30')

    # -- who is in and who is missing ----------------------------------------------------

    def _names(self, items):
        return [item['name'] for item in items]

    def test_the_kiosk_lists_who_is_expected_and_who_is_in(self):
        session = self._open()
        progress = session._ems_kiosk_progress()
        self.assertEqual(self._names(progress['convened']), ['Presence Child', 'Presence Teacher'])
        self.assertEqual(progress['attendees'], [])

        session._ems_register_scan('TESTPRES002')
        progress = session._ems_kiosk_progress()
        self.assertEqual(self._names(progress['convened']), ['Presence Teacher'])
        self.assertEqual(self._names(progress['attendees']), ['Presence Child'])
        self.assertEqual((progress['present_count'], progress['pending_count']), (1, 1))
        # Every scan's answer carries the same picture, so the page updates without asking again.
        answer = session._ems_register_scan('TESTPRES001')
        self.assertEqual(answer['convened'], [])
        self.assertEqual(self._names(answer['attendees']), ['Presence Teacher', 'Presence Child'])

    def test_the_latest_arrival_comes_first_and_carries_the_local_time(self):
        session = self._session(scope='manual', date='2026-10-01 17:00:00', date_end='2026-10-01 19:00:00')
        session.line_ids = [(0, 0, {'employee_id': employee.id}) for employee in (self.teacher, self.child_teacher)]
        session.action_open()
        with self._at('2026-10-01 17:30:00'):
            session._ems_register_scan('TESTPRES001')
        with self._at('2026-10-01 17:45:00'):
            session._ems_register_scan('TESTPRES003')  # the ASP: not convened
        attendees = session.with_context(tz='Europe/Madrid')._ems_kiosk_progress()['attendees']
        self.assertEqual([(item['name'], item['time'], item['not_convened']) for item in attendees],
                         [('Presence ASP', '19:45', True), ('Presence Teacher', '19:30', False)])

    def test_someone_justified_is_neither_expected_nor_in(self):
        session = self._open()
        self._line(session, self.teacher).write({'state': 'justified'})
        progress = session._ems_kiosk_progress()
        self.assertEqual(self._names(progress['convened']), ['Presence Child'])
        self.assertEqual(progress['attendees'], [])

    def test_names_are_sorted_ignoring_accents_and_case(self):
        session = self._session(scope='manual')
        for name in ('Zoe Presence', 'àlex Presence', 'Bea Presence'):
            employee = self.env['hr.employee'].create({'name': name, 'employee_type': 'teacher'})
            session.line_ids = [(0, 0, {'employee_id': employee.id})]
        self.assertEqual(self._names(session._ems_kiosk_progress()['convened']),
                         ['àlex Presence', 'Bea Presence', 'Zoe Presence'])

    # -- short names ---------------------------------------------------------------------

    def test_short_name_drops_the_last_surname_only_when_it_is_certain(self):
        for name, short in (
            ('Juan Morote', 'Juan Morote'),  # nothing to drop
            ('Ada Alsina Pla', 'Ada Alsina'),
            ('Maria del Carmen Fernández Rodríguez', 'Maria del Carmen Fernández'),
            ('Fernando del Olmo Fernández', 'Fernando del Olmo'),  # "del Olmo" is one surname
            ('Josep Maria Vila i Serra', 'Josep Maria Vila'),  # "Vila i Serra" are two
            ("Joan d'Arenys Puig", "Joan d'Arenys"),
            ('Juan Manuel Cañas Serrano', 'Juan Manuel Cañas'),
            ('Susana Alonso Ruano', 'Susana Alonso'),
            # In doubt the whole name stays: a longer name is never a wrong one.
            ('Maribel del Tío', 'Maribel del Tío'),  # the only surname
            ('Olga de la Morena', 'Olga de la Morena'),
            ('Gerardo Jesús Nicolau', 'Gerardo Jesús Nicolau'),  # two given names, one surname
            ('Josep Manel Cos', 'Josep Manel Cos'),
            ('Ana  Belén   Ruiz', 'Ana Belén Ruiz'),  # only the spaces are tidied
            ('', ''),
            (False, ''),
        ):
            self.assertEqual(kiosk_short_name(name), short, name)

    def test_the_lists_show_the_short_name_and_the_card_the_whole_one(self):
        session = self._open()
        self.assertEqual(self._names(session._ems_kiosk_progress()['convened']), ['Presence Child', 'Presence Teacher'])
        answer = session._ems_register_scan('TESTPRES002')
        self.assertEqual(answer['employee_name'], 'Presence Child Teacher')
        self.assertEqual(self._names(answer['attendees']), ['Presence Child'])

    def test_two_people_who_would_look_the_same_keep_their_whole_names(self):
        first = self.env['hr.employee'].create({'name': 'Ana Puig Vila', 'employee_type': 'teacher'})
        self.env['hr.employee'].create({'name': 'Ana Puig Soler', 'employee_type': 'teacher'})
        other = self.env['hr.employee'].create({'name': 'Bea Roca Mas', 'employee_type': 'teacher'})
        session = self._session(scope='manual')
        # Only one of the two is in the meeting: the name is the same whoever else comes, so it
        # does not change under the eyes of the people in the queue.
        session.line_ids = [(0, 0, {'employee_id': first.id}), (0, 0, {'employee_id': other.id})]
        self.assertEqual(self._names(session._ems_kiosk_progress()['convened']), ['Ana Puig Vila', 'Bea Roca'])

    def test_the_lists_are_sorted_by_the_name_they_show(self):
        session = self._session(scope='manual')
        for name in ('Zoe Ruiz Mas', 'Bea Zamora Vila', 'Bea Alba Puig'):
            employee = self.env['hr.employee'].create({'name': name, 'employee_type': 'teacher'})
            session.line_ids = [(0, 0, {'employee_id': employee.id})]
        self.assertEqual(self._names(session._ems_kiosk_progress()['convened']),
                         ['Bea Alba', 'Bea Zamora', 'Zoe Ruiz'])

    # -- the box for typing a code -------------------------------------------------------

    def test_the_code_box_is_a_testing_aid_only_shown_outside_production(self):
        session = self._session(scope='manual')
        params = self.env['ir.config_parameter'].sudo()
        # Undeclared (a clean database, CI) and development: shown.
        params.search([('key', '=', 'ems.environment_type')]).unlink()
        self.assertTrue(session._ems_show_code_box())
        params.set_param('ems.environment_type', 'dev')
        self.assertTrue(session._ems_show_code_box())
        params.set_param('ems.environment_type', 'production')
        self.assertFalse(session._ems_show_code_box())

    # -- kiosk scan ----------------------------------------------------------------------

    def _open(self, **vals):
        session = self._session(scope='department', department_id=self.department.id, **vals)
        session.action_open()
        return session

    def test_scan_marks_a_convened_person_present(self):
        session = self._open()
        result = session._ems_register_scan('TESTPRES001')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['employee_name'], 'Presence Teacher')
        self.assertTrue(result['employee_avatar'])
        line = self._line(session, self.teacher)
        self.assertEqual((line.state, line.method), ('present', 'nfc'))
        self.assertTrue(line.checkin_time)
        self.assertEqual((result['present_count'], result['pending_count']), (1, 1))

    def test_scan_twice_reports_already_and_changes_nothing(self):
        session = self._open()
        session._ems_register_scan('TESTPRES001')
        first_time = self._line(session, self.teacher).checkin_time
        result = session._ems_register_scan('TESTPRES001')
        self.assertEqual(result['status'], 'already')
        self.assertEqual(result['employee_name'], 'Presence Teacher')
        self.assertEqual(self._line(session, self.teacher).checkin_time, first_time)
        self.assertEqual(len(session.line_ids), 2)

    def test_scan_of_a_tag_nobody_owns_is_unknown(self):
        session = self._open()
        for barcode in ('NOSUCHTAG', '', None, '   '):
            self.assertEqual(session._ems_register_scan(barcode)['status'], 'unknown')
        self.assertFalse(session.line_ids.filtered(lambda line: line.state == 'present'))

    def test_scan_strips_surrounding_whitespace(self):
        session = self._open()
        self.assertEqual(session._ems_register_scan('  TESTPRES001\n')['status'], 'ok')

    def test_scan_of_someone_not_convened_adds_them_flagged(self):
        session = self._open()
        result = session._ems_register_scan('TESTPRES003')
        self.assertEqual(result['status'], 'not_convened')
        line = self._line(session, self.asp)
        self.assertEqual((line.state, line.method, line.is_convened), ('present', 'nfc', False))
        self.assertEqual(session._ems_register_scan('TESTPRES003')['status'], 'already')
        self.assertEqual(len(self._line(session, self.asp)), 1)

    def test_scan_of_an_absent_or_justified_person_turns_them_present(self):
        session = self._open()
        line = self._line(session, self.teacher)
        line.state = 'justified'
        self.assertEqual(session._ems_register_scan('TESTPRES001')['status'], 'ok')
        self.assertEqual(line.state, 'present')

    def test_scan_is_refused_unless_the_session_is_open(self):
        session = self._session(scope='department', department_id=self.department.id)
        self.assertEqual(session._ems_register_scan('TESTPRES001')['status'], 'not_open')
        session.action_open()
        session.action_close()
        self.assertEqual(session._ems_register_scan('TESTPRES001')['status'], 'closed')
        self.assertFalse(session.line_ids.filtered(lambda line: line.state == 'present'))

    def test_scan_ignores_employees_of_another_company(self):
        other_company = self.env['res.company'].create({'name': 'Test Presence Other Company'})
        stranger = self.env['hr.employee'].create({
            'name': 'Presence Stranger', 'employee_type': 'teacher',
            'barcode': 'TESTPRES099', 'company_id': other_company.id,
        })
        session = self._open()
        self.assertEqual(session._ems_register_scan(stranger.barcode)['status'], 'unknown')

    # -- states --------------------------------------------------------------------------

    def test_states_flow_draft_open_closed_and_reopen(self):
        session = self._session(scope='manual')
        self.assertEqual(session.state, 'draft')
        session.action_open()
        self.assertEqual(session.state, 'open')
        session.action_close()
        self.assertEqual(session.state, 'closed')
        session.action_reopen()
        self.assertEqual(session.state, 'open')

    def test_transitions_out_of_order_are_refused(self):
        session = self._session(scope='manual')
        with self.assertRaises(UserError):
            session.action_close()
        with self.assertRaises(UserError):
            session.action_reopen()
        session.action_open()
        with self.assertRaises(UserError):
            session.action_open()

    def test_closing_turns_pending_into_absent_and_keeps_justified(self):
        session = self._open()
        self._line(session, self.teacher).state = 'justified'
        session.action_close()
        self.assertEqual(self._line(session, self.teacher).state, 'justified')
        self.assertEqual(self._line(session, self.child_teacher).state, 'absent')
        self.assertEqual(
            (session.present_count, session.justified_count, session.absent_count, session.pending_count),
            (0, 1, 1, 0))

    def test_closed_session_locks_its_lines(self):
        session = self._open()
        session.action_close()
        line = self._line(session, self.teacher)
        with self.assertRaises(UserError):
            line.state = 'present'
        with self.assertRaises(UserError):
            line.unlink()
        with self.assertRaises(UserError):
            self.env['ems.meeting.presence.line'].create({
                'presence_id': session.id, 'employee_id': self.asp.id,
            })
        with self.assertRaises(UserError):
            session.action_load_convened()
        session.action_reopen()
        line.state = 'present'
        self.assertEqual(line.state, 'present')

    def test_only_a_draft_session_can_be_deleted(self):
        session = self._open()
        with self.assertRaises(UserError):
            session.unlink()
        draft = self._session(scope='manual')
        draft.unlink()
        self.assertFalse(draft.exists())

    # -- manual marking ------------------------------------------------------------------

    def test_marking_present_by_hand_stamps_time_and_method(self):
        session = self._open()
        line = self._line(session, self.teacher)
        line.state = 'present'
        self.assertEqual(line.method, 'manual')
        self.assertTrue(line.checkin_time)
        line.state = 'pending'
        self.assertFalse(line.method)
        self.assertFalse(line.checkin_time)

    def test_marking_present_again_does_not_overwrite_a_scan(self):
        session = self._open()
        session._ems_register_scan('TESTPRES001')
        line = self._line(session, self.teacher)
        scanned_at = line.checkin_time
        line.state = 'present'
        self.assertEqual((line.method, line.checkin_time), ('nfc', scanned_at))

    def test_a_present_line_cannot_be_deleted(self):
        session = self._open()
        session._ems_register_scan('TESTPRES001')
        with self.assertRaises(UserError):
            self._line(session, self.teacher).unlink()
        self._line(session, self.teacher).state = 'pending'
        self._line(session, self.teacher).unlink()

    # -- token and url -------------------------------------------------------------------

    def test_token_is_unique_random_and_not_copied(self):
        first, second = self._session(scope='manual'), self._session(scope='manual')
        self.assertGreaterEqual(len(first.access_token), 20)
        self.assertNotEqual(first.access_token, second.access_token)
        self.assertNotEqual(first.copy().access_token, first.access_token)

    def test_kiosk_url_carries_the_token(self):
        session = self._session(scope='manual')
        self.assertTrue(session.kiosk_url.endswith(f'/ems/presence/{session.access_token}'))
        action = session.action_open_kiosk()
        self.assertEqual((action['type'], action['url']), ('ir.actions.act_url', session.kiosk_url))

    # -- report --------------------------------------------------------------------------

    def test_report_lists_each_state_under_its_own_heading(self):
        session = self._open()
        session._ems_register_scan('TESTPRES001')
        session._ems_register_scan('TESTPRES003')
        line = self._line(session, self.child_teacher)
        line.write({'state': 'justified', 'notes': 'Medical visit'})
        html = self.env['ir.actions.report']._render_qweb_html(
            'ems.report_meeting_presence', session.ids)[0].decode()
        for text in ('Test staff meeting', 'Presence Teacher', 'Presence Child Teacher', 'Medical visit',
                     'Presence ASP', '(not convened)', 'Justified absences'):
            self.assertIn(text, html)
        self.assertNotIn('Pending (', html)

    # -- access --------------------------------------------------------------------------

    def test_the_roles_that_convene_can_manage_sessions_and_a_teacher_cannot(self):
        for role in ('head_of_studies', 'director', 'secretary', 'academic_admin'):
            user = create_role_user(self, role, f'test_presence_{role}')
            session = self.env['ems.meeting.presence'].with_user(user).create({
                'name': f'Meeting by {role}', 'scope': 'manual',
            })
            session.action_open()
            self.assertEqual(session.state, 'open', role)
        teacher = create_role_user(self, 'teacher', 'test_presence_teacher')
        with self.assertRaises(AccessError):
            self.env['ems.meeting.presence'].with_user(teacher).search([])
        with self.assertRaises(AccessError):
            self.env['ems.meeting.presence'].with_user(teacher).create({'name': 'Nope', 'scope': 'manual'})

    def test_a_secretary_without_hr_rights_can_convene_and_load_people(self):
        # ems.group_secretary does not imply hr.group_hr_user: the convened list must be
        # resolved through hr.employee.public, not through hr.employee.
        secretary = create_role_user(self, 'secretary', 'test_presence_secretary_load')
        session = self.env['ems.meeting.presence'].with_user(secretary).create({
            'name': 'Staff meeting', 'scope': 'department', 'department_id': self.department.id,
        })
        self.assertEqual(session.line_ids.employee_id,
                         self._public(self.teacher) | self._public(self.child_teacher))


@tagged('post_install', '-at_install')
class TestMeetingPresenceController(MeetingPresenceFixtures, HttpCase):
    """The public kiosk routes, called the way the page does: anonymous, token in the URL."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_fixtures()
        cls.presence = cls._session(scope='department', department_id=cls.department.id)
        cls.presence.action_open()

    def _scan(self, barcode, token=None):
        return self.make_jsonrpc_request(
            f'/ems/presence/{token or self.presence.access_token}/scan', {'barcode': barcode})

    def test_kiosk_page_is_public_and_shows_the_session(self):
        self.authenticate(None, None)
        response = self.url_open(f'/ems/presence/{self.presence.access_token}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('owl-component', response.text)
        self.assertIn('ems.meeting_presence_kiosk', response.text)
        self.assertIn('Test staff meeting', response.text)
        self.assertIn('windowLabel', response.text)

    def _kiosk_props(self):
        """The props the page hands to the kiosk component, as the browser will read them."""
        response = self.url_open(f'/ems/presence/{self.presence.access_token}')
        return json.loads(html.unescape(re.search(r'props="([^"]*)"', response.text).group(1)))

    def test_kiosk_page_tells_whether_to_show_the_code_box(self):
        self.authenticate(None, None)
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('ems.environment_type', 'dev')
        self.assertTrue(self._kiosk_props()['showCodeBox'])
        params.set_param('ems.environment_type', 'production')
        self.assertFalse(self._kiosk_props()['showCodeBox'])

    def test_unknown_token_is_a_404(self):
        self.assertEqual(self.url_open('/ems/presence/not-a-token').status_code, 404)

    def test_scan_route_marks_present_and_reports_counters(self):
        self.authenticate(None, None)
        result = self._scan('TESTPRES001')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['employee_name'], 'Presence Teacher')
        self.assertEqual(self._line(self.presence, self.teacher).state, 'present')
        self.assertEqual(self._scan('TESTPRES001')['status'], 'already')
        self.assertEqual(self._scan('NOSUCHTAG')['status'], 'unknown')

    def test_scan_route_with_a_wrong_token_does_nothing(self):
        self.authenticate(None, None)
        self.assertEqual(self._scan('TESTPRES001', token='not-a-token'), {'status': 'invalid'})
        self.assertFalse(self.presence.line_ids.filtered(lambda line: line.state == 'present'))

    def test_status_route_reports_the_session_and_who_is_in(self):
        self.authenticate(None, None)
        route = f'/ems/presence/{self.presence.access_token}/status'
        result = self.make_jsonrpc_request(route)
        self.assertEqual((result['status'], result['present_count'], result['pending_count']), ('open', 0, 2))
        self.assertEqual([item['name'] for item in result['convened']], ['Presence Child', 'Presence Teacher'])
        self.assertEqual(result['attendees'], [])
        self._scan('TESTPRES001')
        result = self.make_jsonrpc_request(route)
        self.assertEqual([item['name'] for item in result['convened']], ['Presence Child'])
        self.assertEqual([item['name'] for item in result['attendees']], ['Presence Teacher'])
        self.presence.action_close()
        self.assertEqual(self.make_jsonrpc_request(route)['status'], 'closed')
        self.assertEqual(self.make_jsonrpc_request('/ems/presence/not-a-token/status'), {'status': 'invalid'})

    def test_scan_route_after_closing_is_refused(self):
        self.authenticate(None, None)
        self.presence.action_close()
        self.assertEqual(self._scan('TESTPRES001')['status'], 'closed')
        self.assertFalse(self.presence.line_ids.filtered(lambda line: line.state == 'present'))
