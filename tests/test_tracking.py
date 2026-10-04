from odoo.tests.common import TransactionCase
from .common import next_student_id


class TestTracking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Tracking Teacher', 'employee_type': 'teacher',
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Test Tracking Student', 'contact_type': 'student', 'student_id': next_student_id(),
        })

    def test_create_valid(self):
        tracking = self.env['ems.tracking'].create({
            'notes': 'Test note', 'teacher_id': self.teacher.id, 'student_id': self.student.id,
        })
        self.assertTrue(tracking.id)
        self.assertEqual(tracking.notes, 'Test note')

    def test_create_with_no_fields_at_all(self):
        # Every field is optional at the model level.
        tracking = self.env['ems.tracking'].create({})
        self.assertTrue(tracking.id)

    def test_most_recent_first(self):
        first = self.env['ems.tracking'].create({'notes': 'First'})
        second = self.env['ems.tracking'].create({'notes': 'Second'})
        records = self.env['ems.tracking'].search([('id', 'in', [first.id, second.id])])
        self.assertEqual(records[0], second)
