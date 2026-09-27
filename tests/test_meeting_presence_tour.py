# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestMeetingPresenceTour(HttpCase):
    """Issue #521, in a real browser: the manager's screens (as a secretary) and the anonymous
    kiosk page. See docs/en/developers/meetings/meeting_presence.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # hr.employee.create() may post a chatter note that reaches real followers - see
        # CLAUDE.md's "Email safety in tests".
        mock_outgoing_email(cls)
        # create_role_user() sets lang en_US: the manager tour asserts on English labels. The
        # "0000 " prefix sorts the fixture first in the convened list, whatever the real staff.
        cls.secretary = create_role_user(cls, 'secretary', 'test_presence_tour_secretary',
                                         name='Presence Tour Secretary')
        cls.tour_teacher = cls.env['hr.employee'].create({
            'name': '0000 Tour Presence Teacher', 'employee_type': 'teacher', 'barcode': 'TESTTOUR001',
        })

    def test_meeting_presence_manage_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_meeting_presence_manage", login="test_presence_tour_secretary", watch=True)
        self.start_tour("/odoo", "ems_meeting_presence_manage", login="test_presence_tour_secretary")

    def _run_kiosk_tour(self, login=None):
        teacher = self.env['hr.employee'].create({
            'name': 'Kiosk Tour Teacher', 'employee_type': 'teacher', 'barcode': 'TESTKIOSK001',
        })
        self.env['hr.employee'].create({
            'name': 'Kiosk Tour Guest', 'employee_type': 'asp', 'barcode': 'TESTKIOSK002',
        })
        presence = self.env['ems.meeting.presence'].create({
            'name': 'Kiosk tour meeting', 'scope': 'manual', 'kiosk_lang': 'en_US',
            'line_ids': [(0, 0, {'employee_id': teacher.id})],
        })
        presence.action_open()
        self.start_tour(f"/ems/presence/{presence.access_token}", "ems_meeting_presence_kiosk", login=login)
        self.assertEqual(presence.present_count, 2)
        self.assertEqual(presence.line_ids.filtered(lambda line: not line.is_convened).employee_id.name, 'Kiosk Tour Guest')

    def test_meeting_presence_kiosk_tour(self):
        # No login: the laptop at the door may have nobody signed in.
        self._run_kiosk_tour()

    def test_meeting_presence_kiosk_tour_signed_in(self):
        # "Open kiosk" opens a new tab of the manager's own browser, so the kiosk is just as often
        # served to a signed-in user: the page must not depend on being anonymous.
        self._run_kiosk_tour(login="test_presence_tour_secretary")

    def test_meeting_presence_kiosk_crowd_tour(self):
        """A staff meeting: 110 people with long names, 40 already in. Both lists show every name
        without scrolling and without cutting any (the tour measures them)."""
        first_names = ('Maria del Carmen', 'Josep', 'Anna', 'Francisco Javier', 'Montserrat', 'Jordi',
                       'Ana Belén', 'Pere', 'Concepció', 'Juan Antonio', 'Laia', 'Xavier')
        surnames = ('Fernández Rodríguez', 'Puig', 'García de la Torre', 'Vila Serra', 'Martínez',
                    'Casas i Ferrer', 'Rodríguez-Villanueva', 'Soler', 'Domínguez Hernández', 'Roca')
        employees = self.env['hr.employee'].create([{
            'name': f'{first_names[index % len(first_names)]} {surnames[index // len(first_names) % len(surnames)]} {index}',
            'employee_type': 'teacher',
            'barcode': f'TESTCROWD{index:03d}',
        } for index in range(110)])
        presence = self.env['ems.meeting.presence'].create({
            'name': 'Crowd tour meeting', 'scope': 'manual', 'kiosk_lang': 'en_US',
            'line_ids': [(0, 0, {'employee_id': employee.id}) for employee in employees],
        })
        presence.action_open()
        for employee in employees[:40]:
            presence._ems_register_scan(employee.barcode)
        self.assertEqual((presence.present_count, presence.pending_count), (40, 70))
        self.start_tour(f"/ems/presence/{presence.access_token}", "ems_meeting_presence_kiosk_crowd")

    def test_meeting_presence_kiosk_in_production_takes_only_a_readers_keys_tour(self):
        """In production the kiosk works like the clock-in kiosk: no box to type in, and only keys
        that come at a reader's speed count. The tour plays the reader, and a person typing."""
        self.env['ir.config_parameter'].sudo().set_param('ems.environment_type', 'production')
        Employee = self.env['hr.employee']
        teachers = Employee.create([
            {'name': 'Reader Tour Teacher', 'employee_type': 'teacher', 'barcode': 'TESTREADER01'},
            {'name': 'Reader Tour Second', 'employee_type': 'teacher', 'barcode': 'TESTREADER02'},
        ])
        presence = self.env['ems.meeting.presence'].create({
            'name': 'Reader tour meeting', 'scope': 'manual', 'kiosk_lang': 'en_US',
            'line_ids': [(0, 0, {'employee_id': teacher.id}) for teacher in teachers],
        })
        presence.action_open()
        self.start_tour(f"/ems/presence/{presence.access_token}", "ems_meeting_presence_kiosk_reader")
        self.assertEqual(presence.present_count, 2)
        self.assertEqual(set(presence.line_ids.mapped('method')), {'nfc'})
