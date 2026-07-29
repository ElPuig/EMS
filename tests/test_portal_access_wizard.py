from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo.tests.common import TransactionCase

from .common import create_level_study_group


class TestPortalAccessWizard(TransactionCase):
    """ems.portal.access.wizard: bulk grant/revoke/resend of portal access for
    students (adults) or their family contacts (minors/applicants)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # action_grant_access()/action_invite_again() send a real portal-invitation
        # email (force_send=True) — neutralize real SMTP delivery (see CLAUDE.md).
        mail_server_patcher = patch(
            'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email',
            return_value='test-message-id',
        )
        mail_server_patcher.start()
        cls.addClassCleanup(mail_server_patcher.stop)

        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Portal Wizard)', 'login': 'test_admin_portal_wizard',
            'groups_id': [(4, cls.env.ref('ems.group_academic_admin').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Test Tutor (Portal Wizard)', 'employee_type': 'teacher',
        })
        cls.tutor_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Tutor User (Portal Wizard)', 'login': 'test_tutor_portal_wizard',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.tutor_employee.user_id = cls.tutor_user
        # A tutor of a DIFFERENT group: holds real ems.group_tutor access (needed just to
        # open the wizard at all — a plain, non-tutoring teacher can't create it, see
        # ir.model.access.csv), but is not the tutor of adult_student used below.
        cls.other_teacher_employee = cls.env['hr.employee'].create({
            'name': 'Test Other Teacher (Portal Wizard)', 'employee_type': 'teacher',
        })
        cls.other_teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Other Teacher (Portal Wizard)', 'login': 'test_other_teacher_portal_wizard',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.other_teacher_employee.user_id = cls.other_teacher_user

        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TPW', level={'name': 'Test Portal Wizard Level'}, study={
            'code': 'TPW001', 'acronym': 'TPWS', 'name': 'Test Portal Wizard Study',
        }, group={'tutor_id': cls.tutor_employee.id})
        cls.other_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.other_teacher_employee.id,
        })

        cls.adult_student = cls.env['res.partner'].create({
            'name': 'Adult Student (Portal Wizard)', 'contact_type': 'student',
            'main_group_id': cls.group.id, 'email': 'adult.student.pw@example.com',
            'birth_date': date.today() - relativedelta(years=19),
        })
        cls.minor_student = cls.env['res.partner'].create({
            'name': 'Minor Student (Portal Wizard)', 'contact_type': 'student',
            'main_group_id': cls.group.id,
            'birth_date': date.today() - relativedelta(years=15),
        })
        cls.family_contact = cls.env['res.partner'].create({
            'name': 'Family Contact (Portal Wizard)', 'contact_type': 'family',
            'email': 'family.pw@example.com',
        })
        cls.relation_father = cls.env.ref('ems.relation_type_father')
        cls.env['res.partner.relation'].create({
            'left_partner_id': cls.family_contact.id,
            'type_id': cls.relation_father.id,
            'right_partner_id': cls.minor_student.id,
        })
        cls.orphan_minor = cls.env['res.partner'].create({
            'name': 'Orphan Minor (Portal Wizard)', 'contact_type': 'student',
            'main_group_id': cls.group.id,
            'birth_date': date.today() - relativedelta(years=15),
        })
        cls.applicant = cls.env['res.partner'].create({
            'name': 'Applicant (Portal Wizard)', 'contact_type': 'applicant',
            'email': 'applicant.pw@example.com',
        })

    def _wizard(self, mode='grant', students=None, user=None):
        # Force English so assertions on the notification message text are stable
        # regardless of the current user's/DB's default language (this DB defaults to ca_ES).
        wizard = self.env['ems.portal.access.wizard'].with_user(user or self.admin_user).with_context(
            lang='en_US').create({
            'mode': mode,
            'student_ids': [(6, 0, (students or self.adult_student).ids)],
        })
        # create() (unlike the real form) never fires @api.onchange — rebuild the
        # preview explicitly so line_ids reflects the students just set, like the UI would.
        wizard._onchange_mode()
        return wizard

    def _simulate_login(self, user):
        # res.users.login_date is a related field onto log_ids (inverse of the magic
        # create_uid field) — the only real way to set it is to actually create a
        # res.users.log row authored by that user, not a direct field write.
        # with_user() forces su=False, so it must come BEFORE sudo(), not after, or the
        # ACL bypass is silently lost (portal users have no create rights on this model).
        self.env['res.users.log'].with_user(user).sudo().create({})

    # --- _user_can_manage -----------------------------------------------------

    def test_user_can_manage_admin_any_student(self):
        wizard = self._wizard()
        self.assertTrue(wizard._user_can_manage(self.adult_student))
        self.assertTrue(wizard._user_can_manage(self.minor_student))

    def test_user_can_manage_tutor_only_own_student(self):
        wizard = self._wizard(user=self.tutor_user)
        self.assertTrue(wizard._user_can_manage(self.adult_student))

    def test_user_cannot_manage_not_tutored_student(self):
        wizard = self._wizard(user=self.other_teacher_user)
        self.assertFalse(wizard._user_can_manage(self.adult_student))

    # --- _resolve_recipients ---------------------------------------------------

    def test_resolve_recipients_applicant_returns_self(self):
        wizard = self._wizard()
        self.assertEqual(wizard._resolve_recipients(self.applicant), self.applicant)

    def test_resolve_recipients_adult_student_returns_self(self):
        wizard = self._wizard()
        self.assertEqual(wizard._resolve_recipients(self.adult_student), self.adult_student)

    def test_resolve_recipients_minor_student_returns_family(self):
        wizard = self._wizard()
        self.assertEqual(wizard._resolve_recipients(self.minor_student), self.family_contact)

    def test_resolve_recipients_minor_without_family_is_empty(self):
        wizard = self._wizard()
        self.assertFalse(wizard._resolve_recipients(self.orphan_minor))

    # --- default_get / _build_lines --------------------------------------------

    def test_default_get_filters_by_manage_and_builds_lines(self):
        wizard = self.env['ems.portal.access.wizard'].with_user(self.tutor_user).with_context(
            active_ids=(self.adult_student | self.applicant).ids, lang='en_US').create({})
        # The applicant is not the tutor's tutorand: only the adult student passes.
        self.assertEqual(wizard.student_ids, self.adult_student)
        self.assertEqual(wizard.line_ids.recipient_id, self.adult_student)

    def test_build_lines_no_family_contact_note(self):
        wizard = self._wizard(students=self.orphan_minor)
        line = wizard.line_ids
        self.assertFalse(line.recipient_id)
        self.assertEqual(line.note, 'No family contact found')

    def test_build_lines_no_email_note(self):
        no_email_adult = self.env['res.partner'].create({
            'name': 'No Email Adult (Portal Wizard)', 'contact_type': 'student',
            'birth_date': date.today() - relativedelta(years=20),
        })
        wizard = self._wizard(students=no_email_adult)
        self.assertEqual(wizard.line_ids.note, 'Recipient without email')

    def test_build_lines_has_portal_and_connected_flags(self):
        portal_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal User (Portal Wizard)', 'login': 'adult.student.pw@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.adult_student.user_ids = [(4, portal_user.id)]
        wizard = self._wizard()
        self.assertTrue(wizard.line_ids.has_portal)
        self.assertFalse(wizard.line_ids.connected)

        self._simulate_login(portal_user)
        wizard._onchange_mode()
        self.assertTrue(wizard.line_ids.connected)

    def test_onchange_mode_resend_keeps_only_never_logged_in(self):
        portal_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Resend Portal User (Portal Wizard)', 'login': 'adult.student.pw@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.adult_student.user_ids = [(4, portal_user.id)]
        wizard = self._wizard()
        wizard.mode = 'resend'
        wizard._onchange_mode()
        self.assertEqual(wizard.line_ids.recipient_id, self.adult_student)

        self._simulate_login(portal_user)
        wizard._onchange_mode()
        self.assertFalse(wizard.line_ids)

    # --- action_apply: grant/revoke/resend --------------------------------------

    def test_action_apply_grant_creates_portal_user(self):
        wizard = self._wizard(mode='grant')
        wizard.action_apply()
        user = self.adult_student.user_ids
        self.assertTrue(user)
        self.assertTrue(user._is_portal())

    def test_action_apply_revoke_archives_portal_user(self):
        portal_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Revoke Portal User (Portal Wizard)', 'login': 'adult.student.pw@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.adult_student.user_ids = [(4, portal_user.id)]
        wizard = self._wizard(mode='revoke')
        wizard.action_apply()
        self.assertFalse(portal_user.active)

    def test_action_apply_resend_skips_already_connected(self):
        portal_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Connected Portal User (Portal Wizard)', 'login': 'adult.student.pw@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.adult_student.user_ids = [(4, portal_user.id)]
        self._simulate_login(portal_user)
        wizard = self._wizard(mode='resend')
        result = wizard.action_apply()
        self.assertIn('1 skipped', result['params']['message'])

    # --- action_apply: issues ---------------------------------------------------

    def test_action_apply_issue_not_your_student(self):
        wizard = self._wizard(user=self.other_teacher_user)
        # Bypass default_get's own filtering to reach action_apply's own guard directly.
        wizard.sudo().student_ids = self.adult_student
        result = wizard.action_apply()
        self.assertIn('not your student', result['params']['message'])

    def test_action_apply_issue_adult_student_without_email(self):
        no_email_adult = self.env['res.partner'].create({
            'name': 'No Email Adult 2 (Portal Wizard)', 'contact_type': 'student',
            'birth_date': date.today() - relativedelta(years=20),
        })
        wizard = self._wizard(students=no_email_adult)
        result = wizard.action_apply()
        self.assertIn('without main email', result['params']['message'])

    def test_action_apply_issue_no_family_contact(self):
        wizard = self._wizard(students=self.orphan_minor)
        result = wizard.action_apply()
        self.assertIn('no family contact to manage', result['params']['message'])

    # --- _sync_user_login --------------------------------------------------------

    def _portal_wizard_user(self, partner):
        # _sync_user_login expects a portal.wizard.user line (has .user_id/.partner_id),
        # not a bare res.users record — build one the same way _apply_one does.
        wizard = self.env['portal.wizard'].with_context(active_ids=partner.ids).sudo().create({})
        return wizard.user_ids.filtered(lambda u: u.partner_id.id == partner.id)[:1]

    def test_sync_user_login_resyncs_email_on_regrant(self):
        old_email = 'old.login.pw@example.com'
        portal_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Stale Login Portal User (Portal Wizard)', 'login': old_email, 'email': old_email,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])], 'active': False,
        })
        self.adult_student.user_ids = [(4, portal_user.id)]
        wu = self._portal_wizard_user(self.adult_student)
        wizard = self._wizard(mode='grant')
        wizard._sync_user_login(wu)
        self.assertEqual(portal_user.login, 'adult.student.pw@example.com')

    def test_sync_user_login_skips_on_login_conflict(self):
        old_email = 'old.login2.pw@example.com'
        portal_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Conflict Login Portal User (Portal Wizard)', 'login': old_email, 'email': old_email,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])], 'active': False,
        })
        # Another user already owns the target login.
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Login Owner (Portal Wizard)', 'login': 'adult.student.pw@example.com',
        })
        self.adult_student.user_ids = [(4, portal_user.id)]
        wu = self._portal_wizard_user(self.adult_student)
        wizard = self._wizard(mode='grant')
        wizard._sync_user_login(wu)
        self.assertEqual(portal_user.login, old_email)
