# -*- coding: utf-8 -*-

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import create_role_employee, create_role_user


class TestQualityMinute(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = cls.env['ems.course'].search([('is_current', '=', True)], limit=1)
        cls.department = cls.env['hr.department'].create({'name': 'Minute Test Department'})
        cls.type = cls.env.ref('__import__.minute_type_dep_ccff')
        cls.user = create_role_user(cls, 'teacher', 'minute.writer@example.com')
        cls.employee = create_role_employee(cls, cls.user, department_id=cls.department.id)

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
