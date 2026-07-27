from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestTracking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Tracking)',
            'login': 'test_teacher_for_tracking',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Tracking)',
            'login': 'test_secretary_for_tracking',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Tracking Teacher', 'employee_type': 'teacher',
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Test Tracking Student', 'contact_type': 'student',
        })
        cls.test_tracking = cls.env['ems.tracking'].create({
            'notes': 'Initial note', 'teacher_id': cls.teacher.id, 'student_id': cls.student.id,
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

    def test_admin_can_write(self):
        tracking = self.env['ems.tracking'].create({'notes': 'Before'})
        tracking.write({'notes': 'After'})
        self.assertEqual(tracking.notes, 'After')

    def test_admin_can_unlink(self):
        tracking = self.env['ems.tracking'].create({'notes': 'To delete'})
        tracking_id = tracking.id
        tracking.unlink()
        self.assertFalse(self.env['ems.tracking'].search([('id', '=', tracking_id)]))

    def test_most_recent_first(self):
        first = self.env['ems.tracking'].create({'notes': 'First'})
        second = self.env['ems.tracking'].create({'notes': 'Second'})
        records = self.env['ems.tracking'].search([('id', 'in', [first.id, second.id])])
        self.assertEqual(records[0], second)

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.tracking'].with_user(self.teacher_user).create({'notes': 'Teacher Attempt'})

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_tracking.with_user(self.teacher_user).write({'notes': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_tracking.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        tracking = self.test_tracking.with_user(self.teacher_user)
        self.assertEqual(tracking.notes, 'Initial note')

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.tracking'].with_user(self.secretary_user).create({'notes': 'Secretary Attempt'})

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_tracking.with_user(self.secretary_user).write({'notes': 'Secretary Write'})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_tracking.with_user(self.secretary_user).unlink()
