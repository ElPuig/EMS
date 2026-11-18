from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_erasmus import upload
from .test_portal_erasmus import create_portal_erasmus_fixtures


def minimal_pdf():
    """A valid one-page PDF: the file viewer renders it with pdf.js, which logs an error (and fails the tour
    on the browser's console) for the invented bytes the other Erasmus+ tests upload."""
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>']
    out = b'%PDF-1.4\n'
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b'%d 0 obj\n%s\nendobj\n' % (number, body)
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1)
    out += b''.join(b'%010d 00000 n \n' % offset for offset in offsets)
    return out + b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objects) + 1, xref)


@tagged('post_install', '-at_install')
class TestErasmusFileViewerTour(HttpCase):
    """Issue #845 - as the Erasmus team: a file is viewed in Odoo's file viewer, and a confidential
    document's file has neither a download button nor the viewer's Download and Print."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        # In test mode the request's cursor only simulates a read-only one and can't open the read/write
        # one the note of an opening is written in (models/erasmus/binary.py); a real server can.
        cls.registry.test_readonly_enabled = False
        cls.addClassCleanup(setattr, cls.registry, 'test_readonly_enabled', True)
        create_portal_erasmus_fixtures(cls)
        cls.application = cls.env['ems.erasmus.application']._ems_portal_get_or_create(cls.call, cls.student)
        upload(cls.application, cls.cv, content=minimal_pdf())
        upload(cls.application, cls.evidence, 'evidence.pdf', content=minimal_pdf())

    def test_file_viewer_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_application', 'ems_erasmus_file_viewer',
                        login='test_erasmus_team')
        notes = self.application.message_ids.filtered(lambda message: 'evidence.pdf' in (message.body or ''))
        self.assertTrue(notes, "Opening the confidential file is noted on the application")
