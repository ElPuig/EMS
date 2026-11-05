import base64
from datetime import timedelta

from odoo import fields
from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_erasmus import PDF, create_erasmus_fixtures, upload


def create_portal_erasmus_fixtures(cls):
    """create_erasmus_fixtures() plus portal users for the eligible student and the outsider
    (login doubles as password)."""
    create_erasmus_fixtures(cls)
    cls.student_user, cls.outsider_user = cls.env['res.users'].with_context(no_reset_password=True).create([{
        'name': partner.name, 'login': login, 'password': login, 'partner_id': partner.id,
        'lang': 'en_US', 'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
    } for partner, login in (
        (cls.student, 'test_portal_erasmus_student'),
        (cls.outsider, 'test_portal_erasmus_outsider'),
    )])


@tagged('post_install', '-at_install')
class TestPortalErasmus(HttpCase):
    """Issue #683 - the portal's Erasmus+ page (/my/erasmus): applying, uploading and submitting,
    always as the logged-in student."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_erasmus_fixtures(cls)

    def _login(self, user):
        self.authenticate(user.login, user.login)

    def _save(self, submit=False, **answers):
        data = {'csrf_token': Request.csrf_token(self), **answers}
        if submit:
            data['submit'] = '1'
        files = [(f'document_{self.cv.id}', ('cv.pdf', PDF, 'application/pdf'))]
        return self.url_open(f'/my/erasmus/call/{self.call.id}/save', data=data, files=files)

    def _application(self):
        return self.env['ems.erasmus.application'].search([
            ('call_id', '=', self.call.id), ('partner_id', '=', self.student.id)])

    def test_eligible_student_sees_the_call(self):
        self._login(self.student_user)
        response = self.url_open('/my/erasmus')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Test Erasmus Call', response.text)
        home = self.url_open('/my/home').text
        self.assertIn('/my/erasmus', home)
        self.assertIn('href="/my/erasmus" class="nav-link"', home, "The portal menu has an entry, like the card.")

    def test_student_of_another_level_is_sent_home(self):
        self._login(self.outsider_user)
        home = self.url_open('/my/home').text
        self.assertNotIn('/my/erasmus"', home, "Neither the card nor the portal menu entry.")
        response = self.url_open('/my/erasmus')
        self.assertTrue(response.url.endswith('/my/home'))
        response = self.url_open(f'/my/erasmus/call/{self.call.id}')
        self.assertTrue(response.url.endswith('/my/home'))

    def test_save_then_submit(self):
        self._login(self.student_user)
        self._save(applicant_notes='Summer only')
        application = self._application()
        self.assertEqual(application.state, 'draft')
        self.assertEqual(application.applicant_notes, 'Summer only')
        self.assertEqual(application.document_ids.attachment_ids.mapped('name'), ['cv.pdf'])
        response = self._save(submit=True, applicant_notes='Summer only')
        self.assertIn('submitted=1', response.url)
        self.assertEqual(application.state, 'submitted')

    def test_application_form_renders(self):
        self._login(self.student_user)
        response = self.url_open(f'/my/erasmus/call/{self.call.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('o_ems_erasmus_form', response.text)
        self.assertIn(f'document_{self.cv.id}', response.text)
        self.assertNotIn(f'document_{self.authorization.id}', response.text, "Minors-only document hidden to adults")

    def test_a_draft_shows_earlier_versions_and_removes_a_file_and_downloads_the_model(self):
        """The 2026-11-04 usage test: two files with the same name and no way to remove one."""
        self.certificate.write({'template_file': base64.b64encode(PDF), 'template_filename': 'model.pdf'})
        self.cv.single_file = True
        self._login(self.student_user)
        self._save()
        self._save()
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_earlier_version', page)
        self.assertIn('o_ems_erasmus_remove_file', page)
        self.assertIn(f'/my/erasmus/call/{self.call.id}/template/{self.certificate.id}', page)
        download = self.url_open(f'/my/erasmus/call/{self.call.id}/template/{self.certificate.id}')
        self.assertEqual(download.content, PDF)
        line = self._application().document_ids.filtered(lambda line: line.call_document_id == self.cv)
        first = line.attachment_ids.sorted('id')[:1]
        self.url_open(f'/my/erasmus/call/{self.call.id}/file/{first.id}/remove',
                      data={'csrf_token': Request.csrf_token(self)})
        self.assertEqual(len(line.attachment_ids), 1)
        self.assertNotIn('o_ems_erasmus_earlier_version', self.url_open(f'/my/erasmus/call/{self.call.id}').text)

    def test_the_family_of_a_minor_sees_the_application_read_only(self):
        """The 2026-11-04 usage test: the family saw nothing of Erasmus+ until the commitment letter."""
        family = self.env['res.partner'].create({'name': 'Erasmus Test Family', 'contact_type': 'family'})
        self.env['res.partner.relation'].create({
            'left_partner_id': family.id, 'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': self.minor.id})
        family_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': family.name, 'login': 'test_portal_erasmus_family', 'password': 'test_portal_erasmus_family',
            'partner_id': family.id, 'lang': 'en_US', 'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.authorization.write({'template_file': base64.b64encode(PDF), 'template_filename': 'model.pdf'})
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.call, self.minor)
        upload(application, self.cv)
        self._login(family_user)
        page = self.url_open('/my/erasmus').text
        self.assertIn('o_ems_erasmus_guardian_application', page)
        self.assertIn('Erasmus Test Minor', page)
        self.assertIn(self.authorization.name, page)
        self.assertNotIn(self.evidence.name, page, "Not a confidential document.")
        self.assertNotIn('/save', page, "Read only.")
        model = f'/my/erasmus/call/{self.call.id}/template/{self.authorization.id}'
        self.assertIn(model, page)
        self.assertEqual(self.url_open(model).content, PDF)

    def test_subsanation_only_offers_the_documents_asked_for(self):
        self._login(self.student_user)
        self._save(submit=True)
        application = self._application()
        application.document_ids.filtered(lambda line: line.call_document_id == self.cv).action_mark_needs_change()
        self.call.subsanation_deadline = fields.Datetime.now() + timedelta(days=10)
        application.action_request_subsanation()
        self.call.action_close()
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_subsanation', page)
        self.assertIn(f'name="document_{self.cv.id}"', page)
        self.assertNotIn(f'name="document_{self.certificate.id}"', page)
        self._save(submit=True)
        self.assertEqual(application.state, 'submitted')

    def test_closed_call_refuses_changes(self):
        self._login(self.student_user)
        self._save()
        self.call.date_close = fields.Datetime.now() - timedelta(hours=1)
        response = self._save(applicant_notes='Too late')
        self.assertIn('error=', response.url)
        self.assertFalse(self._application().applicant_notes)

    def test_rules_document_download(self):
        self.call.write({'rules_document': 'JVBERi0xLjQ=', 'rules_filename': 'call.pdf'})
        self._login(self.student_user)
        response = self.url_open(f'/my/erasmus/call/{self.call.id}/rules')
        self.assertEqual(response.content, b'%PDF-1.4')
        self._login(self.outsider_user)
        response = self.url_open(f'/my/erasmus/call/{self.call.id}/rules')
        self.assertNotEqual(response.content, b'%PDF-1.4')

    def test_admitted_applicant_sees_the_interview_call(self):
        """Issue #684: once called, the portal shows the interview's date and place."""
        self._login(self.student_user)
        self._save(submit=True)
        application = self._application()
        application._ems_set_state('admitted')
        application.write({'interview_date': fields.Datetime.now() + timedelta(days=3),
                           'interview_place': 'Room E12'})
        self.assertNotIn('o_ems_erasmus_interview', self.url_open(f'/my/erasmus/call/{self.call.id}').text)
        application.action_send_interview_call()
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_interview', page)
        self.assertIn('Room E12', page)

    # The issue-#682 review: the step bar and the "what to do now" box.

    def _progress(self, application):
        progress = application._ems_portal_progress()
        return [status for _label, status in progress['steps']], progress['next']

    def test_progress_follows_the_application(self):
        self._login(self.student_user)
        self._save()
        application = self._application()
        statuses, nxt = self._progress(application)
        self.assertEqual(statuses[:2], ['current', 'todo'])
        self.assertEqual((nxt['level'], nxt['deadline'], nxt['is_date']), ('warning', self.call.date_close, False))
        application._ems_set_state('subsanation')
        statuses, nxt = self._progress(application)
        self.assertEqual(statuses[:2], ['done', 'current'])
        self.assertEqual((nxt['level'], nxt['key']), ('warning', 'subsanation'))
        application._ems_set_state('admitted')
        statuses, nxt = self._progress(application)
        self.assertEqual(statuses[2], 'current', "The interview step.")
        self.assertEqual((nxt['level'], nxt['key']), ('info', ''), "Nothing to do until called.")
        application.write({'interview_date': fields.Datetime.now() + timedelta(days=3), 'interview_place': 'Room E12'})
        application.action_send_interview_call()
        _statuses, nxt = self._progress(application)
        self.assertEqual((nxt['level'], nxt['key'], nxt['deadline']), ('warning', 'interview', application.interview_date))
        self.assertIn('Room E12', nxt['text'])
        application._ems_set_state('reserve')
        statuses, nxt = self._progress(application)
        self.assertEqual(statuses[:5], ['done', 'done', 'done', 'done', 'current'])
        self.assertEqual(nxt['level'], 'info', "A reserve waits for a free place.")

    def test_progress_marks_where_an_application_ended(self):
        self._login(self.student_user)
        self._save(submit=True)
        application = self._application()
        application._ems_set_state('excluded')
        statuses, nxt = self._progress(application)
        self.assertEqual(statuses[:3], ['done', 'failed', 'todo'])
        self.assertEqual(nxt['level'], 'secondary')
        application._ems_set_state('not_selected')
        statuses, _nxt = self._progress(application)
        self.assertEqual(statuses[3], 'failed', "Not selected in the resolution step.")

    def test_page_groups_the_calls(self):
        """Own applications first, then the open calls; a closed call folded away."""
        self._login(self.student_user)
        page = self.url_open('/my/erasmus').text
        self.assertIn('o_ems_erasmus_section_open', page)
        self.assertNotIn('o_ems_erasmus_section_mine', page)
        date_close = self.call.date_close
        self.call.date_close = fields.Datetime.now() - timedelta(hours=1)
        page = self.url_open('/my/erasmus').text
        self.assertIn('o_ems_erasmus_section_other', page)
        self.assertNotIn('o_ems_erasmus_section_open', page)
        self.call.date_close = date_close
        self._save(submit=True)
        page = self.url_open('/my/erasmus').text
        self.assertIn('o_ems_erasmus_section_mine', page)
        self.assertIn('o_ems_erasmus_steps', page)
        self.assertIn('o_ems_erasmus_state_submitted', page)
        self.assertIn('text-bg-info', page, "A submitted application has its own colour.")
        self.assertNotIn('o_ems_erasmus_section_open', page)

    def test_sent_application_folds_away(self):
        self._login(self.student_user)
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_form_details" open="open"', page)
        self._save(submit=True)
        self.call.action_close()
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('<details class="mb-4 o_ems_erasmus_form_details">', page, "Folded once sent and closed.")
        self.assertIn('o_ems_erasmus_next', page)
