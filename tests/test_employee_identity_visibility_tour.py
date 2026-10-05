from odoo.tests.common import HttpCase, tagged

from .common import create_role_employee, create_role_user, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestEmployeeIdentityVisibilityTour(HttpCase):
    """Browser side of test_employee_identity_visibility.py: a real Department Chief session
    sees, read-only, the identity document and social security number in the "Private
    Information" tab of a teacher of their own department, and no tab on another department's
    teacher; a real secretariat session edits them on an ASP."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Saving an employee can post a chatter note (_gw_notify_missing_fields) - see CLAUDE.md's
        # "Email safety in tests".
        mock_outgoing_email(cls)
        # Logged in as the Department Chief, not admin: admin would see both teachers' data.
        cls.chief_user = create_role_user(cls, 'department_chief', 'test_identity_chief_tour', name='IDV Tour Chief')
        chief = create_role_employee(cls, cls.chief_user)
        other_chief = create_role_employee(cls, create_role_user(
            cls, 'department_chief', 'test_identity_other_chief_tour', name='IDV Tour Other Chief'))
        # "0000 " prefix: sorts first on the list's first page (see create_role_employee).
        cls.env['hr.employee'].create({
            'name': '0000 IDV Own Teacher', 'employee_type': 'teacher', 'parent_id': chief.id,
            'identification_id': '11111111H', 'ssnid': '081234567890',
        })
        cls.env['hr.employee'].create({
            'name': '0000 IDV Other Teacher', 'employee_type': 'teacher', 'parent_id': other_chief.id,
            'identification_id': '22222222J', 'ssnid': '089876543210',
        })

        cls.asp = cls.env['hr.employee'].create({'name': '0000 IDV ASP', 'employee_type': 'asp'})
        create_role_user(cls, 'secretary', 'test_identity_secretary_tour', name='IDV Tour Secretary')

    def test_employee_identity_visibility_tour(self):
        # To watch this tour in a real browser during development, add watch=True below.
        self.start_tour("/odoo", "ems_employee_identity_visibility", login='test_identity_chief_tour')

    def test_employee_identity_secretary_edit_tour(self):
        self.start_tour("/odoo", "ems_employee_identity_secretary_edit", login='test_identity_secretary_tour')
        self.assertEqual(self.asp.identification_id, '44444444A')
        self.assertEqual(self.asp.ssnid, '080000000002')
