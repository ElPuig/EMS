from datetime import timedelta
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from .common import (
    close_yearly_period, create_head_of_studies_branch, create_level_study_group, create_role_employee,
    create_role_user, next_student_id, open_yearly_period, set_yearly_period,
)


class TestPreenrollmentPeriod(TransactionCase):
    """Issue #654 - outside the yearly pre-enrollment period, Academic management > Enrollment
    (the enrollment proposals) is hidden from everyone but academic administration, the
    secretary's office, the Heads of Studies and above. The period's own open/closed arithmetic is
    shared with the convalidation one and covered by TestConvalidationPeriod."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.partner_id.tz = 'Europe/Madrid'
        cls.restricted_users = [
            create_role_user(cls, role, f'test_preenrollment_{role}')
            for role in ('tutor', 'department_chief', 'orientation', 'coexistence')
        ]
        cls.always_users = [
            create_role_user(cls, role, f'test_preenrollment_{role}')
            for role in ('academic_admin', 'secretary', 'head_of_studies', 'director')
        ] + [cls.env.ref('base.user_admin')]
        cls.tutor = cls.restricted_users[0]
        cls.secretary = cls.always_users[1]
        cls.proposal_menu = cls.env.ref('ems.menu_students_tutor')
        cls.enrollment_menu = cls.env.ref('ems.menu_ems_enrollment')
        cls.academic_menu = cls.env.ref('ems.menu_ems_academic_management')
        cls.action = cls.env.ref('ems.action_student_group_enrollment')

    def _visible(self, user):
        return self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()

    def test_defaults(self):
        defaults = self.env['res.company'].default_get([
            'preenrollment_start_day', 'preenrollment_start_month', 'preenrollment_start_time',
            'preenrollment_end_day', 'preenrollment_end_month', 'preenrollment_end_time'])
        self.assertEqual((defaults['preenrollment_start_day'], defaults['preenrollment_start_month'],
                          defaults['preenrollment_start_time']), (1, '5', 8.0))
        self.assertEqual((defaults['preenrollment_end_day'], defaults['preenrollment_end_month']),
                         (31, '7'))
        self.assertEqual(round(defaults['preenrollment_end_time'] * 60), 23 * 60 + 59)

    def test_period_is_validated(self):
        with self.assertRaises(ValidationError):
            set_yearly_period(self.env, 'preenrollment', (31, 4, 8.0), (31, 7, 23.5))

    def test_restricted_roles_see_enrollment_only_while_open(self):
        open_yearly_period(self.env, 'preenrollment')
        for user in self.restricted_users:
            with self.subTest(user=user.login):
                self.assertIn(self.proposal_menu.id, self._visible(user))
                self.assertIn(self.enrollment_menu.id, self._visible(user))
        close_yearly_period(self.env, 'preenrollment')
        for user in self.restricted_users:
            with self.subTest(user=user.login):
                visible = self._visible(user)
                self.assertNotIn(self.proposal_menu.id, visible)
                self.assertNotIn(self.enrollment_menu.id, visible, "an empty folder is left behind")

    def test_folders_above_stay_while_they_have_something_to_open(self):
        """A tutor keeps Academic management for the authorizations; guidance and coexistence had
        nothing else there, so it goes too."""
        close_yearly_period(self.env, 'preenrollment')
        self.assertIn(self.academic_menu.id, self._visible(self.tutor))
        self.assertIn(self.env.ref('ems.menu_ems_authorization_root').id, self._visible(self.tutor))
        for user in self.restricted_users[2:]:
            with self.subTest(user=user.login):
                self.assertNotIn(self.academic_menu.id, self._visible(user))

    def test_always_roles_see_enrollment_while_closed(self):
        close_yearly_period(self.env, 'preenrollment')
        for user in self.always_users:
            with self.subTest(user=user.login):
                self.assertIn(self.proposal_menu.id, self._visible(user))
                self.assertIn(self.enrollment_menu.id, self._visible(user))

    def test_menu_search_hides_it_too(self):
        """What the web client actually gets: ir.ui.menu's search filters by _visible_menu_ids."""
        close_yearly_period(self.env, 'preenrollment')
        self.assertNotIn(self.proposal_menu, self.env['ir.ui.menu'].with_user(self.tutor).search([]))

    def test_proposals_action_refused_while_closed(self):
        """The menu is hidden, but a bookmarked URL still runs the action."""
        close_yearly_period(self.env, 'preenrollment')
        with self.assertRaisesRegex(UserError, 'pre-enrollment period'):
            self.action.with_user(self.tutor).run()
        self.assertEqual(self.action.with_user(self.secretary).run()['res_model'], 'res.partner')
        open_yearly_period(self.env, 'preenrollment')
        self.assertEqual(self.action.with_user(self.tutor).run()['res_model'], 'res.partner')

    def test_sync_clears_the_menu_cache_only_on_a_change(self):
        """Menu visibility is ormcached: the opening and closing reach it by clearing the cache,
        only when the state really changed. The cron is woken a minute after the next change."""
        def stored_state():
            # Not get_param(): it is ormcached too, and the cache clearing is mocked below.
            return self.env['ir.config_parameter'].sudo().search(
                [('key', '=', 'ems.preenrollment_period_open')]).value

        open_yearly_period(self.env, 'preenrollment')
        self.assertEqual(stored_state(), 'True',
                         "saving the period syncs it straight away")
        cron = self.env.ref('ems.ir_cron_preenrollment_period')
        Trigger = self.env['ir.cron.trigger'].sudo()
        with patch.object(type(self.env.registry), 'clear_cache') as clear_cache:
            self.env['res.company']._cron_ems_preenrollment_period()
            clear_cache.assert_not_called()

            close_yearly_period(self.env, 'preenrollment')
            self.assertEqual(stored_state(), 'False')
            clear_cache.assert_called()
        opening = self.company._ems_yearly_period_next_change('preenrollment')
        self.assertTrue(Trigger.search_count([
            ('cron_id', '=', cron.id), ('call_at', '=', opening + timedelta(minutes=1))]))


class TestEnrollmentProposalScope(TransactionCase):
    """Issue #654: the enrollment proposals list follows the chain of command like every other
    tutor-scoped screen (hr.employee.tutor_scope_user_ids, issue #483): a tutor sees their own
    group's students, the Department/Seminar Chief above them those too, another chief none."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        open_yearly_period(cls.env, 'preenrollment')
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_proposal_scope_tutor')
        tutor = create_role_employee(cls, cls.tutor_user)
        create_head_of_studies_branch(cls, 'EPS', tutor)
        __, __, group = create_level_study_group(cls, 'EPS', group={'tutor_id': tutor.id})
        __, __, other_group = create_level_study_group(cls, 'EPO')
        Partner = cls.env['res.partner']
        cls.student = Partner.create({
            'name': 'EPS Tutored Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
        })
        cls.other_student = Partner.create({
            'name': 'EPS Other Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': other_group.id,
        })
        cls.action = cls.env.ref('ems.action_student_group_enrollment')

    def _listed(self, user):
        domain = self.action.with_user(user).run()['domain']
        return self.env['res.partner'].with_user(user).search(
            domain + [('id', 'in', (self.student | self.other_student).ids)])

    def test_tutor_sees_their_own_group(self):
        self.assertEqual(self._listed(self.tutor_user), self.student)

    def test_department_chief_sees_their_tutors_students(self):
        self.assertEqual(self._listed(self.department_chief), self.student)

    def test_another_department_chief_sees_none(self):
        self.assertFalse(self._listed(self.other_department_chief))

