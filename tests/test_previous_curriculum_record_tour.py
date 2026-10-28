# -*- coding: utf-8 -*-

import base64

from odoo.tests.common import HttpCase, tagged

from .common import build_previous_curriculum_pdf, create_role_user, next_student_id


@tagged('post_install', '-at_install')
class TestPreviousCurriculumRecordTour(HttpCase):
    """A previous curriculum record (issue #672) imported by the secretariat from the student form."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = cls.env['res.partner'].create({
            'name': 'Previous Curriculum Tour Student', 'contact_type': 'student',
            'student_id': next_student_id()})
        # create_role_user sets lang to en_US, which the English selectors of the tour need.
        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_previous_curriculum_tour')

    def test_previous_curriculum_record_tour(self):
        pdf = build_previous_curriculum_pdf(self.student.student_id, [
            ('001', 'MP1. Primer mòdul', 99, '7', 'Ord.', [('00101', 'UF1. Unitat', 99, '7', '1')]),
            ('002', 'MP2. Segon mòdul', 0, '', '', [('00201', 'UF1. Unitat pendent', 66, 'NP', '')]),
        ], curriculum=('CFPS ICT0', 'CFPS Cicle Tour (LOE)'))
        attachment = self.env['ir.attachment'].create({
            'name': 'historial.pdf', 'datas': base64.b64encode(pdf), 'public': True,
            'mimetype': 'application/pdf'})
        self.env['ir.model.data'].create({
            'module': 'ems', 'name': 'tour_previous_curriculum_document',
            'model': 'ir.attachment', 'res_id': attachment.id})
        self.start_tour(f"/odoo/action-ems.action_student_kanban/{self.student.id}",
                        "ems_previous_curriculum_record", login=self.secretary.login)
        record = self.student.previous_curriculum_record_ids
        self.assertEqual(record.curriculum_code, 'CFPS ICT0')
        unit = record.line_ids.filtered(lambda line: line.code == '00201')
        self.assertEqual(unit.grade, '6')
