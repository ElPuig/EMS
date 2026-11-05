from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .test_erasmus import PDF
from .test_erasmus_mobility import ErasmusStaffMobilityCase
from .test_erasmus_staff import STAFF_PLAN


@tagged('post_install', '-at_install')
class TestErasmusStaffBackend(ErasmusStaffMobilityCase):
    """The 2026-11-04 review: staff apply to a staff call, follow their application and prepare
    their mobility in the backend, reading only their own records; the portal is for students and
    families only."""

    def _as(self, index=0):
        return self.env(user=self.staff_users[index])

    def _wizard(self, env, model, values=None, **defaults):
        return env[model].with_context(**{f'default_{key}': value for key, value in defaults.items()}).create(
            values or {})

    def _apply_in_backend(self, index=0):
        env = self._as(index)
        action = env['ems.erasmus.call'].browse(self.staff_call.id).action_staff_apply()
        return env['ems.erasmus.application'].browse(action['res_id'])

    def test_a_teacher_sees_the_published_staff_calls_open_to_them(self):
        Call = self._as()['ems.erasmus.call']
        self.assertEqual(Call.search([('staff_mine', '=', True)]), self.staff_call)
        draft = self.env['ems.erasmus.call'].create({**self.staff_call.copy_data()[0], 'name': 'Test Draft Staff Call'})
        visible = Call.search([])
        self.assertIn(self.staff_call, visible)
        self.assertFalse((self.call | draft) & visible, "Neither the students' call nor a staff call in draft.")
        self.assertFalse(self.env(user=self.panel_teacher)['ems.erasmus.call'].search([('staff_mine', '=', True)]),
                         "No employee file that can apply.")
        # Their groups' rules add up: the Head of Studies (also a teacher) and the team still read every call.
        for user in (self.hos_user, self.erasmus_user):
            self.assertIn(self.call, self.env(user=user)['ems.erasmus.call'].search([]))

    def test_apply_fill_in_and_submit_from_the_backend(self):
        application = self._apply_in_backend()
        self.assertEqual((application.state, application.partner_id), ('draft', self.staff_users[0].partner_id))
        self.assertEqual(self._apply_in_backend(), application, "The same application, opened again.")
        self.assertTrue(application.staff_editable)
        self.assertEqual(application.staff_next_level, 'warning')
        env = self._as()
        wizard = self._wizard(env, 'ems.erasmus.staff.application.wizard', application_id=application.id)
        wizard.write({**STAFF_PLAN, 'declared_centre_start_date': date(2015, 9, 17), 'support_needs': 'Test need',
                      'declared_language_level': 'c1'})
        wizard.action_save()
        self.assertEqual(application.sudo().support_needs, 'Test need')
        self.assertEqual(application.staff_support_needs, 'Test need', "The applicant reads their own answer.")
        self.assertEqual(application.declared_centre_start_date, date(2015, 9, 1), "The month counts.")
        with self.assertRaises(UserError):
            application.action_staff_submit()  # the identity document is required
        line = application.document_ids.filtered(lambda line: line.call_document_id == self.id_document)
        self.assertTrue(line.staff_can_upload)
        upload = self._wizard(env, 'ems.erasmus.staff.document.wizard', line_id=line.id)
        upload.attachment_ids = env['ir.attachment'].create({'name': 'id.pdf', 'raw': PDF})
        upload.action_confirm()
        self.assertEqual(line.attachment_ids.mapped('name'), ['id.pdf'])
        self._wizard(env, 'ems.erasmus.staff.application.wizard', application_id=application.id).action_save_submit()
        self.assertEqual(application.state, 'submitted')

    def test_a_teacher_reads_and_changes_only_their_own_application(self):
        mine, other = self._apply_in_backend(0), self._apply_in_backend(1)
        env = self._as(0)
        self.assertEqual(env['ems.erasmus.application'].search([]), mine)
        with self.assertRaises(AccessError):
            env['ems.erasmus.application'].browse(other.id).call_id
        for action in ('action_staff_edit', 'action_staff_submit', 'action_staff_claim'):
            with self.assertRaises(AccessError):
                getattr(env['ems.erasmus.application'].browse(other.id), action)()
        with self.assertRaises(AccessError):
            self._wizard(env, 'ems.erasmus.staff.application.wizard', application_id=other.id)
        with self.assertRaises(AccessError):
            env['ems.erasmus.application'].browse(mine.id).proposal_a = 'Written by hand'
        with self.assertRaises(AccessError):
            env['ems.erasmus.application'].browse(mine.id).action_admit()
        # Rules add up across groups: the Head of Studies, also a teacher, still reads them all.
        self.assertEqual(self.env(user=self.hos_user)['ems.erasmus.application'].search(
            [('call_id', '=', self.staff_call.id)]), mine | other)

    def test_results_offer_and_mobility_from_the_backend(self):
        applications = self._admitted(0), self._admitted(1)
        self.staff_call.action_close()
        self.staff_call.action_send_to_panel()
        for application, last in zip(applications, ('never', 'older')):
            self._rate(application, '1', '1')
            self._complete(application, last=last, seniority='y2' if last == 'older' else 'y5')
        for kind in ('admission', 'provisional', 'definitive'):
            resolution = self.env['ems.erasmus.resolution'].with_user(self.erasmus_user).create({
                'call_id': self.staff_call.id, 'kind': kind})
            resolution.action_prepare()
            resolution.action_publish()
        env = self._as()
        application = env['ems.erasmus.application'].browse(applications[0].id)
        self.assertEqual(len(application.resolution_line_ids), 3, "The published lists they are on.")
        self.assertEqual(env['ems.erasmus.resolution.line'].search([]), application.resolution_line_ids,
                         "Never the other applicants' lines.")
        download = application.resolution_line_ids[:1].action_staff_download()
        self.assertTrue(download['url'].startswith('/ems/erasmus/resolution/'))
        self.assertTrue(application.staff_offer_id)
        application.action_staff_accept_offer()
        self.assertEqual(application.state, 'accepted')
        mobility = env['ems.erasmus.mobility'].browse(application.staff_mobility_id.id)
        self.assertEqual(env['ems.erasmus.mobility'].search([]), mobility)
        self.assertTrue(mobility.staff_can_propose)
        proposal = self._wizard(env, 'ems.erasmus.staff.proposal.wizard', {
            'proposal_activity': 'course', 'proposal_host': 'Test Course Provider',
            'proposal_country_id': self.env.ref('base.mt').id, 'proposal_date_start': date(2027, 7, 5),
            'proposal_date_end': date(2027, 7, 9)}, mobility_id=mobility.id)
        with self.assertRaises(UserError):
            proposal.action_confirm()  # the responsible declaration
        proposal.leave_declaration = True
        proposal.action_confirm()
        self.assertEqual((mobility.proposal_state, mobility.proposal_host), ('pending', 'Test Course Provider'))
        self.assertFalse(mobility.staff_can_propose, "Waiting for the Direction.")
        with self.assertRaises(AccessError):
            self._as(1)['ems.erasmus.mobility'].browse(mobility.id).action_staff_renounce()
        self._wizard(env, 'ems.erasmus.staff.renounce.wizard', mobility_id=mobility.id,
                     reason='Test reason').action_confirm()
        self.assertEqual((mobility.state, application.state), ('cancelled', 'renounced'))

    def test_staff_never_use_the_portal(self):
        self._apply_in_backend()
        partner = self.staff_users[0].partner_id
        self.assertFalse(partner._ems_erasmus_portal_visible(), "No Erasmus+ card nor entry on the portal.")
        self.assertTrue(self.student._ems_erasmus_portal_visible())

    def test_staff_emails_and_tasks_open_the_backend(self):
        application = self._apply_in_backend()
        self.assertTrue(application._ems_mail_url().endswith(
            f'/odoo/action-ems.action_erasmus_my_applications/{application.id}'))
        self.assertEqual(application.with_context(lang='en_US')._ems_mail_place(), 'in EMS')
        self.assertTrue(self.staff_call._ems_mail_url().endswith(
            f'/odoo/action-ems.action_erasmus_staff_calls/{self.staff_call.id}'))
        self.assertTrue(self.call._ems_mail_url().endswith(f'/my/erasmus/call/{self.call.id}'),
                        "A students' call still links to the portal.")
        self.assertEqual(application.get_formview_id(access_uid=self.staff_users[0].id),
                         self.env.ref('ems.view_erasmus_application_staff_form').id)
        self.assertNotEqual(application.get_formview_id(access_uid=self.erasmus_user.id),
                            self.env.ref('ems.view_erasmus_application_staff_form').id)
