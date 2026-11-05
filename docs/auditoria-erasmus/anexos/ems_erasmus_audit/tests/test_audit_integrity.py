# -*- coding: utf-8 -*-
"""Can the evidence of a record be lost? Deleting or archiving the records that hold documents,
done as the Erasmus team (the only role with those rights). What EMS guards on purpose is
asserted; the rest is only observed and logged (AUDIT_INTEGRITY) for the documentation."""

import io
import json
import logging
import zipfile

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from odoo.addons.ems.tests.test_erasmus import PDF
from odoo.addons.ems.tests.test_erasmus_integration import ErasmusGroupRecordsCase
from odoo.addons.ems.tests.test_erasmus_records import ErasmusRecordsCase

_logger = logging.getLogger(__name__)
REFUSED = (AccessError, UserError, ValidationError)


def attempt(callback):
    """'allowed' or 'refused: <exception class>', inside a savepoint so nothing stays."""
    def run(env):
        try:
            with env.cr.savepoint():
                callback()
                env.flush_all()
                raise _Rollback()
        except _Rollback:
            return 'allowed'
        except REFUSED as error:
            return f'refused: {type(error).__name__}'
        except Exception as error:  # a database constraint (foreign key...)
            return f'refused: {type(error).__name__}'
        finally:
            env.invalidate_all()
    return run


class _Rollback(Exception):
    pass


@tagged('post_install', '-at_install')
class TestAuditIntegrityIndividual(ErasmusRecordsCase):

    def test_evidence_can_be_lost(self):
        first, second = self._on_project()
        health = self._line(first, 'European Health Insurance Card')
        health._ems_add_files([('health.pdf', PDF)])
        health.action_mark_valid()
        team = self.technician_user
        results = {}

        def run(name, callback):
            results[name] = attempt(callback)(self.env)

        run('remove a file from a valid document line', lambda: health.with_user(team).write(
            {'attachment_ids': [(3, health.attachment_ids.id)]}))
        run('delete a valid document line (confidential, with its file)', lambda: health.with_user(team).unlink())
        run('delete the file (ir.attachment) of a valid line', lambda: health.attachment_ids.with_user(team).unlink())
        run('delete a mobility in preparation, without payments', lambda: second.with_user(team).unlink())
        run('delete an accepted application with its mobility',
            lambda: second.application_id.with_user(team).unlink())
        run('archive a mobility in preparation', lambda: second.with_user(team).write({'active': False}))
        run('archive an application', lambda: second.application_id.with_user(team).write({'active': False}))
        run('delete a project document', lambda: self.env['ems.erasmus.project.document'].create(
            {'project_id': self.project.id, 'name': 'Audit doc'}).with_user(team).unlink())

        # An archived mobility in the project export.
        second.with_user(team).write({'active': False})
        export = self.env['ems.erasmus.export'].with_user(team).create(
            {'scope': 'project', 'project_id': self.project.id})
        with export._ems_zip() as archive:
            names = zipfile.ZipFile(io.BytesIO(archive.read())).namelist()
        folder = self.env['ems.erasmus.export']._ems_record_folder(second)
        results['archived mobility still in the project ZIP'] = any(f'/{folder}/' in name for name in names)
        results['archived mobility counted in the project records'] = self.project.record_count == 2
        second.with_user(team).write({'active': True})

        # What EMS guards on purpose.
        resolution = self.call.resolution_ids.filtered(lambda resolution: resolution.state == 'published')[:1]
        guarded = {
            'delete a published resolution': lambda: resolution.with_user(self.erasmus_user).unlink(),
            'change a published resolution': lambda: resolution.with_user(self.erasmus_user).write({'notes': 'x'}),
            'change an export log': lambda: export.with_user(team).write({'reason': 'x'}),
            'delete an export log': lambda: export.with_user(team).unlink(),
        }
        for name, callback in guarded.items():
            results[name] = attempt(callback)(self.env)
        first.with_user(team).write({'grant_amount': 500})
        first.with_user(team).action_request_prefinancing()
        payment = first.payment_ids
        self._transfer(payment, self.secretary_user)
        results['delete a paid grant payment'] = attempt(lambda: payment.with_user(self.erasmus_user).unlink())(self.env)
        results['change a paid grant payment'] = attempt(
            lambda: payment.with_user(self.erasmus_user).write({'amount': 1}))(self.env)
        _logger.info("AUDIT_INTEGRITY %s", json.dumps({'title': 'Individual', 'results': results}, sort_keys=True))
        for name in ('delete a published resolution', 'change a published resolution', 'change an export log',
                     'delete an export log', 'delete a paid grant payment', 'change a paid grant payment',
                     'remove a file from a valid document line'):
            self.assertTrue(results[name].startswith('refused'), f"{name}: {results[name]}")


@tagged('post_install', '-at_install')
class TestAuditIntegrityGroup(ErasmusGroupRecordsCase):

    def test_evidence_can_be_lost(self):
        self._approved()
        self._confirm_destination()
        student = self._student()
        student.action_sign_commitment(True, '10.0.0.1')
        # A change of the conditions keeps the accepted letter as a version.
        self.mobility.with_user(self.coordinator_user).write({'city': 'Hamburg'})
        version = student.commitment_version_ids[:1]
        draw_model = self.env['ems.erasmus.group.draw']
        team = self.coordinator_user
        results = {'a version was kept': bool(version)}
        results['change a commitment letter version'] = attempt(
            lambda: version.with_user(team).write({'reason': 'x'}))(self.env)
        results['delete a commitment letter version'] = attempt(lambda: version.sudo().unlink())(self.env)
        results['delete a participant file with its documents'] = attempt(
            lambda: student.with_user(team).unlink())(self.env)
        results['delete the group mobility'] = attempt(lambda: self.mobility.with_user(team).unlink())(self.env)
        results['archive the group mobility'] = attempt(
            lambda: self.mobility.with_user(team).write({'active': False}))(self.env)
        results['create a draw by hand'] = attempt(lambda: draw_model.with_user(team).create({
            'group_mobility_id': self.mobility.id, 'user_id': team.id, 'date': '2026-01-01 00:00:00'}))(self.env)
        _logger.info("AUDIT_INTEGRITY %s", json.dumps({'title': 'Group', 'results': results}, sort_keys=True))
        self.assertTrue(results['a version was kept'])
        for name in ('change a commitment letter version', 'delete a commitment letter version',
                     'create a draw by hand'):
            self.assertTrue(results[name].startswith('refused'), f"{name}: {results[name]}")
