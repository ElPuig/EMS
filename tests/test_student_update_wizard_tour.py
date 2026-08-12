from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestStudentUpdateWizardTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = cls.env['res.partner'].create({
            'name': 'Old Tour Name', 'contact_type': 'student', 'student_id': '9999999999',
        })

    def test_student_update_wizard_apply_tour(self):
        self.start_tour("/odoo", "ems_student_update_wizard_apply", login="admin")

        self.assertEqual(self.student.name, 'Updated Tour Name')
