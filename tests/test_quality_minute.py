# -*- coding: utf-8 -*-

from datetime import datetime
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from .common import create_role_employee, create_role_user, mock_outgoing_email


class TestQualityMinute(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = cls.env['ems.course'].search([('is_current', '=', True)], limit=1)
        cls.department = cls.env['hr.department'].create({'name': 'Minute Test Department'})
        cls.type = cls.env.ref('__import__.minute_type_dep')
        cls.user = create_role_user(cls, 'teacher', 'minute.writer@example.com')
        cls.employee = create_role_employee(cls, cls.user, department_id=cls.department.id)
        cls.employee.work_email = 'minute.writer@example.com'
        # The call to a meeting is a real email: nothing leaves this box from a test.
        cls.mail_transport = mock_outgoing_email(cls)
        # The call and the PDF are written in the centre's language, which depends on what each
        # database has installed; the tests read them in the source language.
        centre_lang = patch.object(type(cls.env['ems.minute']), '_ems_centre_lang', lambda self: 'en_US')
        centre_lang.start()
        cls.addClassCleanup(centre_lang.stop)

    def _minute(self, **overrides):
        vals = {
            'type_id': self.type.id,
            'date': fields.Date.context_today(self.env['ems.minute']),
            'department_id': self.department.id,
            'course_id': self.course.id,
            'redactor_employee_id': self.env['hr.employee.public'].browse(self.employee.id).id,
        }
        vals.update(overrides)
        return self.env['ems.minute'].create(vals)

    def test_code_is_issued_per_scope(self):
        first = self._minute()
        second = self._minute()
        self.assertTrue(first.code.startswith('ACTA-'), first.code)
        self.assertIn(self.course.short_code, first.code)
        self.assertNotEqual(first.code, second.code)

    def test_sections_come_from_the_type(self):
        """The form is laid out by the type: that is what makes adding a type configuration."""
        minute = self._minute()
        self.assertEqual(len(minute.section_value_ids), len(self.type.section_ids))
        self.assertEqual(
            minute.section_value_ids.sorted('sequence').mapped('section_id'),
            self.type.section_ids.sorted('sequence').mapped('section_id'),
        )

    def test_an_evidence_record_does_not_get_a_meeting_layout(self):
        record_type = self.env['ems.minute.type'].create({
            'code': 'ZREC', 'name': 'Cash count', 'kind': 'record', 'scope_kind': 'centre',
            'section_ids': [(0, 0, {'section_id': self.env.ref('__import__.minute_section_record_data').id, 'sequence': 10}),
                            (0, 0, {'section_id': self.env.ref('__import__.minute_section_signature').id, 'sequence': 20})],
        })
        minute = self._minute(type_id=record_type.id, department_id=False, is_centre=True)
        self.assertEqual(minute.type_kind, 'record')
        self.assertEqual(len(minute.section_value_ids), 2,
                         "an evidence record shows its own sections, not a meeting's nine")

    def test_attendees_are_preloaded_from_the_department(self):
        """The single biggest saving of the feature: nobody types the attendee list again."""
        minute = self._minute()
        self.assertIn(self.employee.name, minute.attendee_ids.mapped('name'))

    def test_open_agreements_of_the_previous_minute_are_carried_over(self):
        previous = self._minute()
        open_agreement = self.env['ems.quality.action'].create({
            'name': 'Still open', 'type': 'agreement', 'minute_id': previous.id,
            'course_id': self.course.id, 'department_id': self.department.id,
        })
        closed_agreement = self.env['ems.quality.action'].create({
            'name': 'Already done', 'type': 'agreement', 'minute_id': previous.id,
            'course_id': self.course.id, 'department_id': self.department.id,
        })
        self.env['ems.quality.followup'].create({
            'action_id': closed_agreement.id, 'date': fields.Date.context_today(previous),
            'state': 'closed', 'description': 'Done',
        })
        previous.pending_topic_ids = [(0, 0, {'name': 'Still to discuss'}),
                                      (0, 0, {'name': 'Already discussed', 'is_done': True})]
        current = self._minute()
        self.assertEqual(current.previous_minute_id, previous)
        self.assertIn(open_agreement, current.followed_agreement_ids)
        self.assertNotIn(closed_agreement, current.followed_agreement_ids,
                         "a closed agreement is not carried over")
        self.assertEqual(current.pending_topic_ids.mapped('name'), ['Still to discuss'])
        self.assertEqual(current.pending_topic_ids.carried_from_minute_id, previous)

    def test_carry_over_does_not_cross_scopes(self):
        other_department = self.env['hr.department'].create({'name': 'Minute Other Department'})
        mine = self._minute()
        theirs = self._minute(department_id=other_department.id)
        self.assertFalse(theirs.previous_minute_id,
                         "the previous minute of another department is none of this one's business")
        self.assertTrue(mine)

    def test_approval_needs_a_writer_and_fills_the_required_sections(self):
        minute = self._minute(redactor_employee_id=False)
        minute.action_submit()
        with self.assertRaises(UserError):
            minute.action_approve()
        minute.redactor_employee_id = self.env['hr.employee.public'].browse(self.employee.id).id
        with self.assertRaises(UserError):
            minute.action_approve()  # the 'development' section is required by this type

    def test_approval_renders_the_pdf(self):
        minute = self._minute()
        self.assertEqual(minute.template_document_id, self.type.template_document_id,
                         "the minute takes its controlled template from the type, for the PDF footer")
        minute.section_value_ids.filtered(lambda value: value.required).content = "<p>Discussed.</p>"
        minute.action_submit()
        minute.action_approve()
        self.assertEqual(minute.state, 'approved')
        self.assertTrue(minute.pdf_attachment_id, "approving renders the PDF")
        self.assertTrue(minute.approval_date)

    def test_an_approved_minute_cannot_go_back_to_draft(self):
        minute = self._minute()
        minute.section_value_ids.filtered(lambda value: value.required).content = "<p>Discussed.</p>"
        minute.action_submit()
        minute.action_approve()
        with self.assertRaises(UserError):
            minute.action_back_to_draft()

    def test_legacy_type_column_stays_populated(self):
        """The old required column is kept in step instead of dropped: dropping the field would
        leave the NOT NULL column behind and break every insert."""
        self.assertEqual(self._minute().type, 'department')

    # --- Setting a meeting up: code, date and time, attendance --------------------------------

    def test_date_time_and_course_follow_from_the_start(self):
        """The start is stored in UTC; the minute states it as the centre reads it."""
        minute = self._minute(date=False, course_id=False, start_datetime=datetime(2027, 1, 14, 11, 30))
        self.assertEqual(str(minute.date), '2027-01-14')
        self.assertEqual(minute.time, '12:30', "11:30 UTC is 12:30 in Catalonia in winter")
        self.assertEqual(minute.course_id.start, 2026, "January 2027 belongs to the course that started in September 2026")
        minute.start_datetime = datetime(2027, 6, 30, 22, 30)
        self.assertEqual(str(minute.date), '2027-07-01', "22:30 UTC is already the next day in summer")
        self.assertEqual(minute.time, '00:30')

    def test_a_minute_dated_by_code_keeps_its_date(self):
        minute = self._minute(date='2026-09-15')
        self.assertEqual(str(minute.date), '2026-09-15')
        self.assertFalse(minute.start_datetime)

    def test_the_code_builds_up_as_the_minute_is_filled_in(self):
        Minute = self.env['ems.minute']
        self.assertEqual(Minute.new({}).code_preview, 'ACTA')
        self.assertEqual(Minute.new({'type_id': self.type.id}).code_preview, 'ACTA',
                         "a department minute is numbered under its department: no department, no code yet")
        draft = Minute.new({'type_id': self.type.id, 'department_id': self.department.id, 'course_id': self.course.id})
        self.assertEqual(draft.code_preview, f"ACTA-MINDEP-{self.course.short_code}-001")
        first = self._minute()
        self.assertEqual(first.code, f"ACTA-MINDEP-{self.course.short_code}-001", "the code issued is the one that was announced")
        self.assertEqual(first.code_preview, first.code)
        draft.invalidate_recordset(['code_preview'])
        self.assertEqual(draft.code_preview, f"ACTA-MINDEP-{self.course.short_code}-002")

    def test_a_generic_minute_takes_the_scope_chosen_for_it(self):
        generic = self.env.ref('__import__.minute_type_generic')
        Minute = self.env['ems.minute']
        self.assertEqual(Minute.new({'type_id': generic.id, 'course_id': self.course.id}).code_preview[:9], 'ACTA-GEN-')
        waiting = Minute.new({'type_id': generic.id, 'scope_choice': 'department', 'course_id': self.course.id})
        self.assertEqual(waiting.code_preview, 'ACTA')
        waiting.department_id = self.department
        self.assertEqual(waiting.code_preview[:12], 'ACTA-MINDEP-')

    def _nfc_minute(self, **overrides):
        vals = {'date': False, 'start_datetime': datetime(2027, 1, 14, 11, 30), 'duration': 1.5, 'attendance_mode': 'nfc'}
        vals.update(overrides)
        return self._minute(**vals).with_user(self.user)

    def test_attendance_with_the_tag_prepares_a_session_for_the_writer(self):
        """A teacher has no access to the attendance sessions, yet the one of their own minute
        is theirs to run: they convene it, with the people the minute preloaded."""
        minute = self.env['ems.minute'].with_user(self.user).create({
            'type_id': self.type.id, 'department_id': self.department.id,
            'start_datetime': datetime(2027, 1, 14, 11, 30), 'duration': 1.5, 'attendance_mode': 'nfc',
        })
        presence = minute.presence_id.sudo()
        self.assertTrue(presence)
        self.assertEqual(presence.state, 'draft')
        self.assertEqual(presence.date, datetime(2027, 1, 14, 11, 30))
        self.assertEqual(presence.duration, 1.5)
        self.assertEqual(presence.scope, 'department')
        self.assertEqual(presence.convener_id.id, self.employee.id)
        self.assertEqual(presence.line_ids.employee_id.ids, minute.attendee_ids.ids)
        self.assertIn(self.employee.id, presence.line_ids.employee_id.ids)

    def test_the_session_follows_the_minute_until_it_is_opened(self):
        minute = self._nfc_minute()
        presence = minute.presence_id.sudo()
        minute.write({'start_datetime': datetime(2027, 1, 15, 9, 0), 'duration': 2})
        self.assertEqual(presence.date, datetime(2027, 1, 15, 9, 0))
        self.assertEqual(presence.duration, 2)
        minute.attendance_mode = 'manual'
        self.assertFalse(presence.exists(), "a session nobody opened goes away with the choice that created it")
        self.assertFalse(minute.presence_id)

    def test_attendance_with_the_tag_needs_a_start(self):
        with self.assertRaises(UserError):
            self._minute(attendance_mode='nfc')

    def test_the_lists_are_filled_from_the_tags(self):
        colleague_user = create_role_user(self, 'teacher', 'minute.colleague@example.com', name='Minute Colleague')
        colleague = create_role_employee(self, colleague_user, department_id=self.department.id)
        minute = self._nfc_minute()
        action = minute.action_open_attendance_kiosk()
        presence = minute.presence_id.sudo()
        self.assertEqual(presence.state, 'open')
        self.assertEqual(action['url'], presence.kiosk_url)
        presence.line_ids.filtered(lambda line: line.employee_id.id == self.employee.id).state = 'present'
        presence.line_ids.filtered(lambda line: line.employee_id.id == colleague.id).write({'state': 'justified', 'notes': 'Medical visit'})
        minute.action_close_attendance()
        self.assertEqual(presence.state, 'closed')
        self.assertEqual(minute.attendee_ids.ids, [self.employee.id])
        self.assertIn(colleague.id, minute.absentee_ids.ids)
        self.assertIn('Medical visit', minute.absence_notes)

    def test_closing_the_session_from_its_own_screen_fills_the_minute_too(self):
        minute = self._nfc_minute()
        presence = minute.presence_id.sudo()
        presence.action_open()
        presence.line_ids.filtered(lambda line: line.employee_id.id == self.employee.id).state = 'present'
        presence.action_close()
        self.assertEqual(minute.attendee_ids.ids, [self.employee.id])

    def test_the_agenda_is_put_together_from_the_minute(self):
        """Only the items to discuss are typed in; the rest of the agenda follows from the minute."""
        section = lambda name: self.env.ref(f'__import__.minute_section_{name}').name
        first = self._minute(agenda_ids=[(0, 0, {'sequence': 20, 'name': 'Second item'}), (0, 0, {'sequence': 10, 'name': 'First <item>'})])
        self.assertEqual(first._ems_agenda_entries(), [(section('agenda'), ['First <item>', 'Second item']), (section('requests'), [])],
                         "the first minute of a department has no previous minute to approve nor agreements to follow up")
        self.assertIn('First &lt;item&gt;', first.agenda_html)
        second = self._minute()
        self.assertEqual([title for title, _items in second._ems_agenda_entries()],
                         [section('previous'), section('agenda'), section('requests')])
        self.env['ems.quality.action'].create({
            'name': 'Open agreement', 'type': 'agreement', 'course_id': self.course.id,
            'department_id': self.department.id, 'minute_id': second.id,
        })
        third = self._minute()
        self.assertEqual([title for title, _items in third._ems_agenda_entries()],
                         [section('previous'), section('agreement_followup'), section('agenda'), section('requests')])
        self.assertFalse(third.agenda_ids, "nothing is added to the items to discuss: they would show twice")

    def test_an_agreement_takes_the_scope_of_its_minute(self):
        """As the form saves it: only what its card shows, with the minute it belongs to."""
        chief = create_role_employee(self, create_role_user(self, 'teacher', 'minute.scope.chief@example.com', name='Minute Scope Chief'))
        self.department.manager_id = chief
        minute = self._minute()
        minute.write({'agreement_ids': [(0, 0, {'name': 'Buy the materials'})]})
        agreement = minute.agreement_ids
        self.assertEqual(agreement.department_id, self.department)
        self.assertEqual(agreement.course_id, minute.course_id)
        self.assertTrue(agreement.code.startswith('ACORD-MINDEP-'), agreement.code)
        self.assertEqual(agreement.responsible_employee_ids.ids, [chief.id], "and with it, its department's chief as responsible")

    def test_an_agreement_stays_on_the_table_until_it_is_closed(self):
        """Carried from the first minute to the second, and from there to the third: it was not
        taken in the second, only followed up, and must not drop out for that."""
        first = self._minute()
        agreement = self.env['ems.quality.action'].create({
            'name': 'Long-running agreement', 'type': 'agreement', 'course_id': self.course.id,
            'department_id': self.department.id, 'minute_id': first.id,
        })
        second = self._minute()
        self.assertIn(agreement, second.followed_agreement_ids)
        third = self._minute()
        self.assertIn(agreement, third.followed_agreement_ids)

    def test_the_pdf_opens_as_a_file_not_as_an_attachment_record(self):
        first = self._minute()
        with self.assertRaises(UserError):
            first.action_open_pdf()
        first.pdf_attachment_id = self.env['ir.attachment'].create({
            'name': 'minute.pdf', 'raw': b'%PDF-1.4', 'res_model': 'ems.minute', 'res_id': first.id, 'mimetype': 'application/pdf'})
        second = self._minute()
        action = second.with_user(self.user).action_open_previous_pdf()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['url'], f"/web/content/{first.pdf_attachment_id.id}?download=false")

    def test_the_numbering_does_not_depend_on_the_language_of_the_writer(self):
        """A department's name is translated; its minutes are one series all the same, coded from
        its Catalan name whoever saves them."""
        self.env['res.lang']._activate_lang('ca_ES')
        self.department.with_context(lang='ca_ES').name = 'Llengua Catalana'
        first = self._minute()
        second = self.env['ems.minute'].with_context(lang='ca_ES').create({
            'type_id': self.type.id, 'department_id': self.department.id, 'course_id': self.course.id,
            'date': fields.Date.context_today(self.env['ems.minute']),
        })
        self.assertEqual(first.code[:12], 'ACTA-LLECAT-')
        self.assertEqual(second.code, first.code[:-3] + '002')

    def test_scope_codes_are_short_unaccented_and_tell_departments_apart(self):
        from odoo.addons.ems.models.quality.common import scope_code
        Department = self.env['hr.department']
        codes = {name: scope_code(Department.new({'name': name})) for name in (
            'Informàtica', 'Llengua Castellana', 'Llengua Catalana', 'Física i Química', 'FOL', "Departament d'Orientació")}
        self.assertEqual(codes, {
            'Informàtica': 'INFOR', 'Llengua Castellana': 'LLECAS', 'Llengua Catalana': 'LLECAT',
            'Física i Química': 'FISQUI', 'FOL': 'FOL', "Departament d'Orientació": 'DEPORI',
        })

    def test_the_call_goes_to_everybody_convened_with_the_agenda(self):
        first = self._minute()
        minute = self._nfc_minute(attendance_mode='manual', agenda_ids=[(0, 0, {'sequence': 10, 'name': 'Budget for the workshop'})])
        self.mail_transport.reset_mock()
        minute.action_send_call()
        self.mail_transport.assert_called_once()
        mail = self.env['mail.mail'].sudo().search([('model', '=', 'ems.minute'), ('res_id', '=', minute.id)])
        self.assertEqual(mail.email_to, 'minute.writer@example.com')
        self.assertIn('Budget for the workshop', mail.body_html)
        self.assertIn('12:30', mail.body_html, "the time the centre reads, not UTC")
        self.assertIn(f"/odoo/action-ems.action_minute/{first.id}", mail.body_html, "a link to the previous minute, to read before approving it")
        self.assertNotIn('replaces the one sent before', mail.body_html)
        self.assertIn('calendar.google.com/calendar/render', mail.body_html)
        self.assertIn('dates=20270114T113000Z%2F20270114T130000Z', mail.body_html, "start and end in UTC: 11:30 plus an hour and a half")
        self.assertIn('Budget+for+the+workshop', mail.body_html)
        self.assertTrue(minute.call_sent_datetime)
        self.assertEqual(minute.call_recipient_count, 1)

    def test_the_call_is_signed_by_the_departments_chief_not_by_the_writer(self):
        chief = create_role_employee(self, create_role_user(self, 'teacher', 'minute.chief@example.com', name='Minute Department Chief'))
        self.department.manager_id = chief
        minute = self._nfc_minute(attendance_mode='manual')
        self.assertEqual(minute._ems_convener().id, chief.id)
        minute.action_send_call()
        mail = self.env['mail.mail'].sudo().search([('model', '=', 'ems.minute'), ('res_id', '=', minute.id)])
        self.assertIn('Minute Department Chief', mail.body_html)
        minute.approver_employee_id = False
        self.assertEqual(minute._ems_convener().id, self.employee.id, "nobody named to approve it: whoever writes it")

    def test_who_approves_is_proposed_from_the_scope_and_can_be_anybody(self):
        chief = create_role_employee(self, create_role_user(self, 'teacher', 'minute.approver.chief@example.com', name='Minute Approver Chief'))
        seminar = create_role_employee(self, create_role_user(self, 'teacher', 'minute.approver.seminar@example.com', name='Minute Approver Seminar'))
        self.department.write({'manager_id': chief.id, 'seminar_chief_id': seminar.id})
        minute = self._minute()
        self.assertEqual(minute.approver_candidate_ids.ids, [chief.id, seminar.id])
        self.assertEqual(minute.approver_employee_id.id, chief.id, "the department's chief by default")
        Employee = self.env['hr.employee.public'].with_context(ems_first_ids=minute.approver_candidate_ids.ids)
        offered = [result[0] for result in Employee.name_search('', limit=8)]
        self.assertEqual(offered[:2], [chief.id, seminar.id], "the scope's own people come first in the dropdown")
        self.assertGreater(len(offered), 2, "and everybody else follows, so anybody can still be chosen")
        self.assertEqual([result[0] for result in Employee.name_search('Minute Approver Seminar')], [seminar.id])
        minute.approver_employee_id = self.employee.id
        minute.with_user(self.user).action_start_meeting()
        self.assertEqual(minute.approver_employee_id.id, self.employee.id, "a choice made by hand is kept")

    def test_the_place_names_the_room_with_its_code(self):
        room = self.env['ems.space'].search([], limit=1)
        minute = self._minute(space_id=room.id, modality='hybrid', place_text='Video call')
        self.assertEqual(minute.place_name, f"{room.name} ({room.code}) - Video call")
        self.assertEqual(self._minute().place_name, "")

    def test_the_call_can_be_sent_again_and_says_so(self):
        minute = self._nfc_minute(attendance_mode='manual')
        minute.action_send_call()
        minute.write({'start_datetime': datetime(2027, 1, 15, 9, 0)})
        minute.action_send_call()
        mails = self.env['mail.mail'].sudo().search([('model', '=', 'ems.minute'), ('res_id', '=', minute.id)], order='id')
        self.assertEqual(len(mails), 2)
        self.assertIn('replaces the one sent before', mails[1].body_html)
        self.assertIn('10:00', mails[1].body_html)

    def test_no_call_once_sent_for_approval_or_without_recipients(self):
        self.employee.work_email = False
        minute = self._nfc_minute(attendance_mode='manual')
        with self.assertRaises(UserError):
            minute.action_send_call()
        self.mail_transport.reset_mock()
        self.employee.work_email = 'minute.writer@example.com'
        for state in ('to_approve', 'approved'):
            minute.sudo().state = state
            with self.assertRaises(UserError):
                minute.action_send_call()
        self.mail_transport.assert_not_called()

    # --- Deleting ---------------------------------------------------------------------------------

    def test_the_writer_deletes_a_draft_minute_with_its_attendance_session(self):
        minute = self._nfc_minute()
        presence = minute.presence_id.sudo()
        self.assertTrue(presence)
        minute.action_delete()
        self.assertFalse(minute.exists())
        self.assertFalse(presence.exists())

    def test_only_a_draft_minute_can_be_deleted(self):
        minute = self._minute()
        minute.state = 'meeting'
        with self.assertRaises(UserError):
            minute.unlink()

    def test_somebody_outside_the_minute_cannot_delete_it(self):
        outsider = create_role_user(self, 'teacher', 'minute.outsider@example.com')
        create_role_employee(self, outsider, name='Minute Outsider')
        minute = self._minute()
        with self.assertRaises(AccessError):
            minute.with_user(outsider).unlink()
        self.assertTrue(minute.exists())

    # --- Holding the meeting ---------------------------------------------------------------------

    def test_a_meeting_is_prepared_then_held_then_sent_for_approval(self):
        minute = self._minute().with_user(self.user)
        self.assertEqual(minute.state, 'draft')
        minute.action_start_meeting()
        self.assertEqual(minute.state, 'meeting')
        with self.assertRaises(UserError):
            minute.action_start_meeting()
        minute.action_back_to_draft()
        self.assertEqual(minute.state, 'draft')
        minute.action_start_meeting()
        minute.action_submit()
        self.assertEqual(minute.state, 'to_approve')
        minute.action_back_to_meeting()
        self.assertEqual(minute.state, 'meeting')

    def test_sending_for_approval_is_recorded_for_the_writers_stamp(self):
        """Who sent it and when is the writer's stamp in the PDF; going back to the meeting takes
        it back, since what is sent next is another text."""
        minute = self._minute().with_user(self.user)
        minute.action_start_meeting()
        minute.action_submit()
        self.assertEqual(minute.submitted_by_id, self.user)
        self.assertTrue(minute.submission_date)
        minute.action_back_to_meeting()
        self.assertFalse(minute.submission_date)
        self.assertFalse(minute.submitted_by_id)

    def test_the_draft_can_be_read_as_a_pdf_before_it_is_approved(self):
        minute = self._minute(agenda_ids=[(0, 0, {'sequence': 10, 'name': 'Only item', 'notes': '<p>Said about it.</p>'})]).with_user(self.user)
        minute.action_start_meeting()
        action = minute.action_open_draft_pdf()
        self.assertEqual(action['url'], f"/report/pdf/ems.report_minute/{minute.id}")
        html = self.env['ir.actions.report']._render_qweb_html('ems.action_report_minute', minute.ids)[0].decode()
        self.assertIn('Draft, not approved yet', html)
        self.assertIn('Said about it.', html, "what was written on each item is printed, without waiting for the approval to put it together")
        self.assertEqual(self.env['ems.minute']._ems_people_label(self.env['hr.employee.public'].browse(self.employee.id)), self.employee.name)

    def test_the_development_is_put_together_from_the_items(self):
        minute = self._minute(agenda_ids=[
            (0, 0, {'sequence': 20, 'name': 'Second item', 'notes': '<p>Said second.</p>'}),
            (0, 0, {'sequence': 10, 'name': 'First item', 'notes': '<p>Said <b>first</b>.</p>'}),
        ])
        development = minute.section_value_ids.filtered(lambda value: value.kind == 'development')
        self.assertFalse(development.is_written, "a minute with items does not ask for the development as a text of its own")
        self.assertTrue(minute.section_value_ids.filtered(lambda value: value.section_id.code == 'PRECS').is_written)
        minute.action_start_meeting()
        minute.action_submit()
        self.assertIn('1. First item', development.content)
        self.assertIn('<b>first</b>', development.content)
        self.assertLess(development.content.index('First item'), development.content.index('Second item'))
        minute.sudo().action_approve()
        self.assertEqual(minute.state, 'approved', "the development it requires is there")

    def test_reviewing_an_agreement_in_the_minute_follows_it_up(self):
        """What the meeting says about an open agreement lands in the agreement's own follow-up:
        the note, a new deadline, and whether it is closed."""
        first = self._minute()
        agreement = self.env['ems.quality.action'].create({
            'name': 'Hand in the plans', 'type': 'agreement', 'course_id': self.course.id,
            'department_id': self.department.id, 'minute_id': first.id, 'deadline_date': '2026-10-01',
        })
        second = self._minute().with_user(self.user)
        review = second.agreement_review_ids
        self.assertEqual(review.action_id, agreement)
        self.assertFalse(agreement.followup_ids, "nothing said yet: the agreement is left as it was")
        review.write({'note': 'Three are still missing', 'new_deadline_date': '2026-11-15'})
        self.assertEqual(agreement.followup_ids.description, 'Three are still missing')
        self.assertEqual(agreement.followup_ids.date, second.date)
        self.assertEqual(agreement.state, 'in_progress')
        self.assertEqual(str(agreement.deadline_date), '2026-11-15')
        review.note = 'All handed in'
        review.is_closed = True
        self.assertEqual(len(agreement.followup_ids), 1, "one entry per minute, kept in step with it")
        self.assertEqual(agreement.followup_ids.description, 'All handed in')
        self.assertEqual(agreement.state, 'closed')
        third = self._minute()
        self.assertFalse(third.agreement_review_ids, "a closed agreement is not brought to the next meeting")
        review.write({'note': False, 'is_closed': False})
        self.assertFalse(agreement.followup_ids, "taking back what was written takes the entry back too")
