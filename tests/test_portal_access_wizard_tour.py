from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .common import (
    create_level_study_group, create_role_employee, create_role_user, force_user_language_to_english,
    mock_outgoing_email, next_student_id,
)


@tagged('post_install', '-at_install')
class TestPortalAccessWizardTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # action_grant_access()/action_invite_again() send a real portal-invitation email
        # (force_send=True) - neutralize real SMTP delivery even though this tour only exercises
        # 'revoke' (which doesn't send mail), for consistency with the rest of this wizard's
        # test coverage (see CLAUDE.md's "Email safety in tests").
        mock_outgoing_email(cls)

        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'TPAWT',
            level={'name': 'Test Level (Portal Access Wizard Tour)'},
            study={'code': 'TPAWT001', 'name': 'Test Study (Portal Access Wizard Tour)', 'date': date.today()},
        )
        cls.student = cls.env['res.partner'].create({
            'name': 'Portal Wizard Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id, 'email': 'portal.wizard.tour.student@example.com',
            'birth_date': date.today() - relativedelta(years=19),
        })
        cls.portal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal Wizard Tour Student', 'login': 'portal.wizard.tour.student@example.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.student.user_ids = [(4, cls.portal_user.id)]

    def test_portal_access_wizard_revoke_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.assertTrue(self.portal_user.active)

        self.start_tour("/odoo", "ems_portal_access_wizard_revoke", login="admin")

        self.assertFalse(self.portal_user.active)

    def test_portal_access_wizard_form_action_tour(self):
        # Issue #482: the same action must also be offered from the student's own form.
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour(f"/odoo/res.partner/{self.student.id}",
                        "ems_portal_access_wizard_form", login="admin")

    def test_portal_access_wizard_shared_email_tour(self):
        """Issue #833, as the student's tutor: the form warns that the main email is the
        family's, and granting gives the student the corporate email as login."""
        tutor = create_role_user(self, 'tutor', 'test_tutor_shared_email_tour',
                                 email='tutor.shared.tour@example.com')
        self.group.tutor_id = create_role_employee(self, tutor)
        student = self.env['res.partner'].create({
            'name': 'Shared Email Tour Student', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': self.group.id,
            'email': 'home.tour@example.com', 'student_email': 'shared.tour@shared-tour.example.com',
            'birth_date': date.today() - relativedelta(years=15),
        })
        family = self.env['res.partner'].create({
            'name': 'Shared Email Tour Family', 'contact_type': 'family', 'email': 'family.tour@example.com',
        })
        self.env['res.partner.relation'].create({
            'left_partner_id': family.id, 'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': student.id,
        })
        # A pair sharing the email can no longer be saved (issue #842); it is the legacy state
        # this tour is about, so the family's email is set under the constraint's feet.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE res_partner SET email = 'home.tour@example.com', "
            "email_normalized = 'home.tour@example.com' WHERE id = %s", (family.id,))
        self.env['res.partner'].invalidate_model(['email', 'email_normalized'])
        self.start_tour(f"/odoo/res.partner/{student.id}", "ems_portal_access_wizard_shared_email",
                        login=tutor.login)
        self.assertEqual(student.with_context(active_test=False).user_ids.login,
                         'shared.tour@shared-tour.example.com')
        self.assertEqual(family.with_context(active_test=False).user_ids.login, 'home.tour@example.com')

    def test_portal_email_change_dialog_tour(self):
        """Issue #842, as the student's tutor: changing the main email of a student without
        portal access asks whether to give it, and answering yes sends the invitation to the
        new email."""
        tutor = create_role_user(self, 'tutor', 'test_tutor_email_dialog_tour',
                                 email='tutor.dialog.tour@example.com')
        self.group.tutor_id = create_role_employee(self, tutor)
        student = self.env['res.partner'].create({
            'name': 'Email Dialog Tour Student', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': self.group.id,
            'email': 'before.dialog.tour@example.com',
            'birth_date': date.today() - relativedelta(years=19),
        })
        self.start_tour(f"/odoo/res.partner/{student.id}", "ems_portal_email_change_dialog",
                        login=tutor.login)
        self.assertEqual(student.email, 'after.dialog.tour@example.com')
        self.assertEqual(student.with_context(active_test=False).user_ids.login,
                         'after.dialog.tour@example.com')
