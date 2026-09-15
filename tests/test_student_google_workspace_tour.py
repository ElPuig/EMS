from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo.tests import tagged, HttpCase

from .common import force_user_language_to_english, next_student_id


@tagged('post_install', '-at_install')
class TestStudentGoogleWorkspaceTour(HttpCase):
    """Browser coverage for the leaving lifecycle banners/buttons on the student form.

    The two date fields drive their own banners and buttons independently of
    google_ws_state, so nothing in the TransactionCase suites renders them.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Deleting the account goes through the (dry-run) Directory API path, and the
        # seeding below can post chatter notes: never let a test reach Google or SMTP.
        mail_patcher = patch(
            'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email')
        mail_patcher.start()
        cls.addClassCleanup(mail_patcher.stop)

    def _seed_student(self, name, **vals):
        # "0000 " prefix: res.partner's _order is "name", so the seeded students sort
        # first on the list's very first page among the real ones already in this DB.
        base = {
            'name': '0000 %s' % name,
            'contact_type': 'student', 'student_id': next_student_id(),
            'email': '%s@example.com' % name.lower().replace(' ', '.'),
        }
        base.update(vals)
        return self.env['res.partner'].create(base)

    def test_student_google_workspace_lifecycle_tour(self):
        # The tour asserts on literal English banner text, which only renders for the
        # real 'admin' login if admin's own language is en_US - not guaranteed on every
        # dev box. See CLAUDE.md's "Tour tests and language" convention.
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.env.company.write({
            'google_ws_enabled': True,
            'google_ws_dry_run': True,
            'google_ws_domain': 'elpuig.xeill.net',
        })
        scheduled = self._seed_student(
            'GW Student Scheduled', student_id='9990000001',
            student_email='gw.scheduled@elpuig.xeill.net')
        scheduled.write({'active': False})
        scheduled.google_ws_deactivation_date = date.today() + relativedelta(days=30)

        suspended = self._seed_student(
            'GW Student Suspended', student_id='9990000002',
            student_email='gw.suspended@elpuig.xeill.net',
            google_ws_suspended=True)
        suspended.write({'active': False})
        suspended.google_ws_deletion_date = date.today() + relativedelta(days=30)

        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_student_google_workspace_lifecycle",
        #                   login="admin", watch=True)
        self.start_tour(
            "/odoo", "ems_student_google_workspace_lifecycle", login="admin")
