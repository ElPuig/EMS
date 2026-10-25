# -*- coding: utf-8 -*-
"""The hypotheses of the independent review of the audit (2026-10-25), each tried on its own so
that one result never hides the next: a context sent by the client (ORM and real JSON-RPC), the
fewer-opportunities score deduced from what the Head of Studies reads, a file's content replaced or
moved to another record, roles held together or taken away. Every attempt runs inside a savepoint
that is rolled back and is only observed and logged (AUDIT_HYPOTHESES): run it on the audited code
and on the corrected one to compare. Nothing is asserted here; the guarantees are asserted by the
project's own tests (tests/test_erasmus_integrity.py)."""

import json
import logging

from odoo.exceptions import AccessError
from odoo.tests.common import HttpCase, tagged

from odoo.addons.ems.tests.common import create_role_user
from odoo.addons.ems.tests.test_erasmus import PDF
from odoo.addons.ems.tests.test_erasmus_integration import ErasmusGroupRecordsCase
from odoo.addons.ems.tests.test_erasmus_records import ErasmusRecordsCase

from .test_audit_integrity import attempt

_logger = logging.getLogger(__name__)
FORGED = {'ems_erasmus_state': True, 'ems_erasmus_payment_state': True, 'ems_erasmus_publish': True}


@tagged('post_install', '-at_install')
class TestAuditHypothesesIndividual(HttpCase, ErasmusRecordsCase):

    def test_hypotheses(self):
        first, second = self._on_project()
        team = self.technician_user
        results = {}

        def run(name, callback):
            results[name] = attempt(callback)(self.env)

        # 1. A context chosen by the client.
        first.with_user(team).write({'grant_amount': 1000})
        first.with_user(team).action_request_prefinancing()
        payment = first.payment_ids
        run('technician + forged context: application.state -> selected',
            lambda: first.application_id.with_user(team).with_context(**FORGED).write({'state': 'selected'}))
        run('technician + forged context: mobility.state -> done',
            lambda: first.with_user(team).with_context(**FORGED).write({'state': 'done'}))
        run('technician + forged context: payment.state -> paid (no Secretary, no receipt)',
            lambda: payment.with_user(team).with_context(**FORGED).write({'state': 'paid'}))
        published = self.call.resolution_ids.filtered(lambda resolution: resolution.state == 'published')[:1]
        run('coordinator + forged context: published resolution.notes',
            lambda: published.with_user(self.erasmus_user).with_context(**FORGED).write({'notes': 'Changed'}))
        run('Head of Studies + forged context: mobility.state -> done (JE has write on mobilities)',
            lambda: first.with_user(self.hos_user).with_context(**FORGED).write({'state': 'done'}))

        def rpc():
            self.authenticate(team.login, team.login)
            self.make_jsonrpc_request('/web/dataset/call_kw/ems.erasmus.mobility/write', {
                'model': 'ems.erasmus.mobility', 'method': 'write', 'args': [first.ids, {'state': 'done'}],
                'kwargs': {'context': FORGED}})
            first.invalidate_recordset()
            if first.state != 'done':
                raise AccessError('not written')
        results['JSON-RPC call_kw with the forged context: mobility.state -> done'] = attempt(rpc)(self.env)
        run('technician: forge the commitment letter acceptance of a mobility',
            lambda: first.with_user(team).write({'commitment_signed_date': '2026-01-01 10:00:00',
                                                 'commitment_signed_by_id': first.partner_id.user_ids[:1].id
                                                 or team.id}))
        run('technician: create a resolution already published', lambda: self.env['ems.erasmus.resolution']
            .with_user(team).create({'call_id': self.call.id, 'kind': 'rectification', 'state': 'published'}))

        # 2. The fewer-opportunities score (criterion D, hidden with groups=) deduced by difference.
        application = first.application_id
        application.sudo().write({'fewer_opportunities_check': 'yes'})  # D = 10, so the deduction is not trivial
        self.env.invalidate_all()
        visible = application.with_user(self.hos_user).read(
            ['score_total', 'score_a', 'score_b', 'score_c', 'score_e', 'score_f'])[0]
        deduced = round(visible['score_total'] - sum(visible[f'score_{letter}'] for letter in 'abcef'), 2)
        results['Head of Studies deduces score_d = total - (A+B+C+E+F)'] = (
            f"deduced {deduced}, actual {application.sudo().score_d}: "
            + ('equal (deducible)' if deduced == application.sudo().score_d else 'different'))

        # 3. A file of a valid document: its content replaced, or moved to another record.
        health = self._line(first, 'European Health Insurance Card')
        health._ems_add_files([('health.pdf', PDF)])
        health.action_mark_valid()
        attachment = health.attachment_ids
        other = self._line(first, 'OLS certificate')
        run('technician: replace the content of a valid line\'s file',
            lambda: attachment.with_user(team).write({'raw': b'%PDF-1.4 replaced'}))
        run('technician: move a valid line\'s file to another line (res_id)',
            lambda: attachment.with_user(team).write({'res_id': other.id}))
        run('technician: link a valid line\'s file to another line too (many2many)',
            lambda: other.with_user(team).write({'attachment_ids': [(4, attachment.id)]}))

        # 4. Roles held together and taken away.
        ols = other
        ols._ems_add_files([('ols.pdf', PDF)])
        self.hos_user.groups_id = [(4, self.env.ref('ems.group_erasmus_group_teacher').id)]
        run('Head of Studies who is also a group teacher: validate an individual document',
            lambda: ols.with_user(self.hos_user).write({'review_state': 'valid'}))
        interview = self.env['ems.erasmus.interview'].create({'application_id': application.id,
                                                              'evaluator_id': self.teacher_user.id})
        interview.with_user(self.erasmus_user).write({'evaluator_id': self.erasmus_user.id})

        def reassigned_reads():
            self.env.invalidate_all()
            interview.with_user(self.teacher_user).read(['motivation'])
        run('evaluator whose interview was reassigned reads it', reassigned_reads)
        _logger.info("AUDIT_HYPOTHESES %s", json.dumps({'title': 'Individual', 'results': results}, sort_keys=True))


@tagged('post_install', '-at_install')
class TestAuditHypothesesGroup(ErasmusGroupRecordsCase):

    def test_hypotheses(self):
        registrations = self._ranked()
        results = {}

        def run(name, callback):
            results[name] = attempt(callback)(self.env)

        run('leader + forged context: group mobility state -> done', lambda: self.mobility.with_user(
            self.leader_user).with_context(**FORGED).write({'state': 'done'}))
        run('leader + forged context: override a result (coordinator only)', lambda: registrations[-1].with_user(
            self.leader_user).with_context(**FORGED).write({'result_override': 'selected',
                                                            'override_reason': 'Forged'}))
        run('companion + forged context: change the destination (companions only write the follow-up)',
            lambda: self.mobility.with_user(self.companion_user).with_context(**FORGED).write({'city': 'Forged'}))
        hos = create_role_user(self, 'head_of_studies', 'audit_hypotheses_hos')
        hos.groups_id = [(4, self.env.ref('ems.group_erasmus_group_teacher').id)]
        log = self.env['ems.erasmus.group.log'].create({'group_mobility_id': self.mobility.id, 'name': 'Audit'})
        run('Head of Studies who is also a group teacher (of another group): edit this group\'s follow-up',
            lambda: log.with_user(hos).write({'name': 'Changed'}))
        self.mobility.with_user(self.coordinator_user).write({'leader_id': self.other_teacher.id})

        def old_leader_reads():
            self.env.invalidate_all()
            self.mobility.with_user(self.leader_user).read(['name'])
        run('replaced leader reads the group mobility', old_leader_reads)
        _logger.info("AUDIT_HYPOTHESES %s", json.dumps({'title': 'Group', 'results': results}, sort_keys=True))
