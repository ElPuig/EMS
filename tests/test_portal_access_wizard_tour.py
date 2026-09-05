from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, force_user_language_to_english, mock_outgoing_email


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
            'name': 'Portal Wizard Tour Student', 'contact_type': 'student',
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
