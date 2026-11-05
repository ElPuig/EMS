# -*- coding: utf-8 -*-
"""Observations behind some of the audit's findings that were first read in the code: what the Head
of Studies reads of an individual application, whether a file can be removed from a line not
validated yet, whether a submitted interview can be deleted, whether a proposal accepts any file, and
whether a payment can be requested for a cancelled mobility. Only observed and logged (AUDIT_OBS),
each attempt inside a savepoint that is rolled back; nothing is asserted."""

import json
import logging

from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from odoo.addons.ems.tests.common import create_role_user
from odoo.addons.ems.tests.test_erasmus import PDF
from odoo.addons.ems.tests.test_erasmus_records import ErasmusRecordsCase

from .test_audit_integrity import attempt

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestAuditObservations(ErasmusRecordsCase):

    def test_observations(self):
        first, second = self._on_project()
        team = self.technician_user
        hos = create_role_user(self, 'head_of_studies', 'audit_obs_hos')
        application = first.application_id
        results = {}

        # R-05: what the Head of Studies reads of an individual application.
        for name in ('fewer_opportunities', 'strike_count', 'strike_ids', 'course_strike_count', 'exclusion_reason',
                     'fewer_opportunities_check'):
            self.env.invalidate_all()
            try:
                application.with_user(hos).read([name])
                results[f'Head of Studies reads application.{name}'] = 'allowed'
            except AccessError:
                results[f'Head of Studies reads application.{name}'] = 'refused: AccessError'
            except ValueError:
                results[f'Head of Studies reads application.{name}'] = 'refused: field not available'

        # R-03: a file removed from a line not validated yet (pending review).
        ols = self._line(first, 'OLS certificate')
        ols._ems_add_files([('audit_ols.pdf', PDF)])
        results['remove a file from a pending line (team)'] = attempt(
            lambda: ols.with_user(team).write({'attachment_ids': [(3, ols.attachment_ids[:1].id)]}))(self.env)

        # R-10: a submitted interview deleted by the team.
        interview = application.sudo().interview_ids.filtered(lambda interview: interview.state == 'submitted')[:1]
        results['delete a submitted interview (team)'] = attempt(
            lambda: interview.with_user(team).unlink())(self.env) if interview else 'no record'

        # R-11: a proposal accepts a file check_upload refuses elsewhere.
        def propose():
            second._ems_set_state('choosing', proposal_state=False)
            second._ems_portal_propose({'proposal_host': 'Audit host', 'proposal_country_id': self.env.ref('base.de').id},
                                       [('audit.html', b'<html><script>alert(1)</script></html>')])
            if not second.proposal_attachment_ids.filtered(lambda attachment: attachment.name == 'audit.html'):
                raise AccessError('not stored')
        results['proposal stores an .html file'] = attempt(propose)(self.env)

        # R-13: a payment requested for a cancelled mobility.
        def pay_cancelled():
            second.with_user(team).write({'cancel_reason': 'Audit', 'grant_amount': 500})
            second.with_user(team).action_cancel()
            second.with_user(team).action_request_prefinancing()
        results['request a payment for a cancelled mobility (team)'] = attempt(pay_cancelled)(self.env)
        _logger.info("AUDIT_OBS %s", json.dumps({'title': 'Observations', 'results': results}, sort_keys=True))
