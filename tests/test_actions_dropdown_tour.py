from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from .common import (
    create_level_study_group, create_role_employee, create_role_user, force_user_language_to_english,
    next_student_id,
)


@tagged('post_install', '-at_install')
class TestActionsDropdownTour(HttpCase):
    """The student form's "Actions" dropdown (static/src/js/backend/actions_dropdown.js), driven
    by a tutor - the least-privileged role with entries in it: which entries a real render offers
    per student, that none is left loose in the header, and that no dropdown shows when nothing
    applies. Only a browser render catches these, since the entries are compiled client-side."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Nothing here should send mail, but never let a test reach SMTP.
        mail_patcher = patch('odoo.addons.base.models.ir_mail_server.IrMailServer.send_email')
        mail_patcher.start()
        cls.addClassCleanup(mail_patcher.stop)
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_tutor_actions_dropdown_tour',
                                          name='Tutor Actions Dropdown Tour')
        tutor = create_role_employee(cls, cls.tutor_user)
        __, __, cls.group = create_level_study_group(cls, 'TADT', group={'tutor_id': tutor.id})

    def test_student_actions_dropdown_tour(self):
        student = self.env['res.partner'].create({
            'name': '0000 Actions Dropdown Student', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': self.group.id,
            'student_email': 'actions.dropdown@elpuig.xeill.net',
        })
        self.start_tour(f"/odoo/res.partner/{student.id}", "ems_actions_dropdown_student",
                        login=self.tutor_user.login)

    def test_family_no_actions_dropdown_tour(self):
        family = self.env['res.partner'].create({
            'name': '0000 Actions Dropdown Family', 'contact_type': 'family',
        })
        self.start_tour(f"/odoo/res.partner/{family.id}", "ems_actions_dropdown_family",
                        login=self.tutor_user.login)

    def test_employee_actions_dropdown_tour(self):
        # Administrator: "Deduct Extra Hours" needs hr_holidays' officer group, and the label the
        # tour matches it on is English.
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        employee = self.env['hr.employee'].create({
            'name': '0000 Actions Dropdown Teacher', 'employee_type': 'teacher',
        })
        self.env['hr.attendance.overtime'].create({
            'employee_id': employee.id, 'duration': 2.0, 'adjustment': True,
        })
        self.start_tour(f"/odoo/hr.employee/{employee.id}", "ems_actions_dropdown_employee", login="admin")

    def test_employee_no_archive_for_tutor_tour(self):
        colleague = self.env['hr.employee'].create({
            'name': '0000 Actions Dropdown Colleague', 'employee_type': 'teacher',
        })
        self.start_tour(f"/odoo/hr.employee/{colleague.id}", "ems_actions_dropdown_employee_no_archive",
                        login=self.tutor_user.login)

    def test_foreign_student_no_actions_dropdown_tour(self):
        other_tutor = create_role_employee(self, create_role_user(
            self, 'tutor', 'test_other_tutor_actions_dropdown_tour', name='Other Tutor Actions Dropdown'))
        __, __, other_group = create_level_study_group(self, 'TADO', group={'tutor_id': other_tutor.id})
        student = self.env['res.partner'].create({
            'name': '0000 Actions Dropdown Foreign', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': other_group.id,
        })
        self.start_tour(f"/odoo/res.partner/{student.id}", "ems_actions_dropdown_foreign_student",
                        login=self.tutor_user.login)
