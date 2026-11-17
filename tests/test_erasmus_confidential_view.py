from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common import mock_outgoing_email
from .test_erasmus import PDF, create_erasmus_fixtures, upload


@tagged('post_install', '-at_install')
class TestErasmusConfidentialView(TransactionCase):
    """Issue #845: a confidential document's file is shown, never downloaded, and every opening is
    noted on the application's history (once per person and file within ten minutes)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        # Serving a file needs an HTTP request: what is under test is the check before it.
        patcher = patch('odoo.addons.base.models.ir_binary.IrBinary._get_stream_from', return_value='stream')
        patcher.start()
        cls.addClassCleanup(patcher.stop)
        create_erasmus_fixtures(cls)
        cls.application = cls.env['ems.erasmus.application']._ems_portal_get_or_create(cls.call, cls.student)
        upload(cls.application, cls.evidence, 'evidence.pdf')
        upload(cls.application, cls.cv, 'cv.pdf')
        lines = cls.application.document_ids
        cls.evidence_file = lines.filtered('confidential').attachment_ids
        cls.cv_file = lines.filtered(lambda line: not line.confidential and line.attachment_ids).attachment_ids

    def _stream(self, attachment, download, user=None):
        binary = self.env['ir.binary'].with_user(user or self.erasmus_user)
        return binary._get_stream_from(attachment.with_user(user or self.erasmus_user).with_context(
            download_attachments=download))

    def _notes(self):
        return self.application.message_ids.filtered(lambda message: 'evidence.pdf' in (message.body or ''))

    def test_confidential_file_is_not_served_as_a_download(self):
        with self.assertRaises(UserError):
            self._stream(self.evidence_file, True)

    def test_other_files_download_as_always(self):
        self.assertEqual(self._stream(self.cv_file, True), 'stream')
        self.assertFalse(self._notes(), "Only the confidential ones are noted")

    def test_applicant_portal_controllers_are_unaffected(self):
        """The portal streams without the 'download_attachments' key: the applicant gets their own file."""
        self.assertEqual(self.env['ir.binary']._get_stream_from(self.evidence_file), 'stream')

    def test_opening_is_noted_once_in_ten_minutes(self):
        self._stream(self.evidence_file, False)
        self._stream(self.evidence_file, False)
        notes = self._notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes.author_id, self.erasmus_user.partner_id)
        self.assertIn(self.erasmus_user.name, notes.body)

    def test_another_person_opening_is_noted_too(self):
        self._stream(self.evidence_file, False)
        self._stream(self.evidence_file, False, user=self.env.ref('base.user_admin'))
        self.assertEqual(len(self._notes()), 2)

    def test_project_document_is_noted_on_the_project(self):
        project = self.env['ems.erasmus.project'].search([], limit=1) or self.env['ems.erasmus.project'].create(
            {'name': 'Test project'})
        document = self.env['ems.erasmus.project.document'].create({
            'project_id': project.id, 'name': 'Bank details', 'confidential': True,
            'attachment_ids': [(0, 0, {'name': 'bank.pdf', 'raw': PDF})]})
        with self.assertRaises(UserError):
            self._stream(document.attachment_ids, True)
        self._stream(document.attachment_ids, False)
        self.assertTrue(project.message_ids.filtered(lambda message: 'bank.pdf' in (message.body or '')))
