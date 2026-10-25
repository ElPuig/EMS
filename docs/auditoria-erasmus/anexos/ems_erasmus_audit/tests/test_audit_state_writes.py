# -*- coding: utf-8 -*-
"""Can the Erasmus team skip a workflow's checks by writing a state, a result or a frozen value
directly (what an RPC call does), instead of using the actions? Each attempt is made as the mobility
technician, inside a savepoint that is rolled back, and only observed and logged (AUDIT_STATE) for
the documentation: nothing is asserted, nothing stays."""

import json
import logging

from odoo.tests.common import tagged

from odoo.addons.ems.tests.test_erasmus_records import ErasmusRecordsCase

from .test_audit_integrity import attempt

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestAuditStateWrites(ErasmusRecordsCase):

    def test_direct_state_writes(self):
        first, second = self._on_project()
        team = self.technician_user
        application = first.application_id
        first.with_user(team).write({'grant_amount': 1000})
        first.with_user(team).action_request_prefinancing()
        payment = first.payment_ids
        offer = application.offer_ids[:1]
        resolution = self.call.resolution_ids.filtered(lambda resolution: resolution.state == 'published')[:1]
        draft = self.env['ems.erasmus.resolution'].create({'call_id': self.call.id, 'kind': 'rectification'})
        claim = self.env['ems.erasmus.claim'].create({'application_id': application.id, 'description': 'Audit'})
        results = {}

        def run(name, record, vals):
            results[name] = attempt(lambda: record.with_user(team).write(vals))(self.env) if record else 'no record'

        run('call.state closed -> draft', self.call, {'state': 'draft'})
        run('application.state accepted -> selected', application, {'state': 'selected'})
        run('application.grade_average_ems (frozen)', application, {'grade_average_ems': 9.99})
        run('application.strike_count (frozen)', application, {'strike_count': 0})
        run('application.draw_order', application, {'draw_order': 7})
        run('mobility.state preparing -> done (skips return checks)', first, {'state': 'done'})
        run('mobility.proposal_state -> validated', second, {'proposal_state': 'validated'})
        run('offer.state accepted -> pending', offer, {'state': 'pending'})
        run('claim.state open -> resolved (no response)', claim, {'state': 'resolved'})
        run('payment.state to_pay -> paid', payment, {'state': 'paid'})
        run('resolution draft.state -> published (no checks)', draft, {'state': 'published'})
        run('published resolution.notes', resolution, {'notes': 'x'})
        _logger.info("AUDIT_STATE %s", json.dumps({'title': 'Individual', 'results': results}, sort_keys=True))
