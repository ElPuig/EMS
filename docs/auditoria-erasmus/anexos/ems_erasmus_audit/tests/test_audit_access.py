# -*- coding: utf-8 -*-
"""Who can read and change what in Erasmus+, role by role, on real records built with EMS's own
test fixtures (fictitious people). Each check is done as the user (ORM: read() and
check_access('write'); HTTP: the real routes), compared with what the audit expects, and the
whole observed matrix is logged as one JSON line (AUDIT_MATRIX) for the documentation. A
difference with what is expected fails the test and is listed, it is never hidden."""

import io
import json
import logging
import zipfile

from odoo.exceptions import AccessError, UserError
from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from odoo.addons.ems.tests.common import create_role_user
from odoo.addons.ems.tests.test_erasmus_integration import ErasmusGroupRecordsCase
from odoo.addons.ems.tests.test_erasmus_records import ErasmusRecordsCase

_logger = logging.getLogger(__name__)

# Unique contents, to find a file in a response or a ZIP.
HEALTH = b'%PDF-1.4 AUDIT-HEALTH-CARD'
INCLUSION = b'%PDF-1.4 AUDIT-INCLUSION'
EVIDENCE = b'%PDF-1.4 AUDIT-FEWER-OPPORTUNITIES'
OLS = b'%PDF-1.4 AUDIT-OLS'
BANK = b'%PDF-1.4 AUDIT-CONFIDENTIAL-PROJECT-DOC'
OPEN_DOC = b'%PDF-1.4 AUDIT-OPEN-PROJECT-DOC'
GROUP_HEALTH = b'%PDF-1.4 AUDIT-GROUP-HEALTH'
GROUP_GRANT = b'%PDF-1.4 AUDIT-GROUP-GRANT'
GROUP_INCLUSION = b'%PDF-1.4 AUDIT-GROUP-INCLUSION'
CONFIDENTIAL_MARKERS = (HEALTH, INCLUSION, EVIDENCE, BANK, GROUP_HEALTH, GROUP_INCLUSION)


def portal_user(env, partner, login):
    return env['res.users'].with_context(no_reset_password=True).create({
        'name': partner.name, 'login': login, 'password': login, 'partner_id': partner.id, 'lang': 'en_US',
        'groups_id': [(6, 0, [env.ref('base.group_portal').id])]})


class AuditMatrixMixin:
    """Collects observed vs expected results and reports every difference at once."""

    def _audit_start(self, title):
        self.audit_title = title
        self.observed = {}
        self.differences = []

    def _check(self, subject, role, observed, expected):
        self.observed.setdefault(subject, {})[role] = observed
        if expected is not None and observed != expected:
            self.differences.append(f"{subject} / {role}: observed {observed}, expected {expected}")

    def _can_read(self, record, user, fields=('display_name',)):
        if not record:
            return None  # nothing to check: a fixture problem, reported as a difference
        # Odoo checks an attachment's access when it fetches it: a value another user already
        # read stays in the ORM cache and would hide the check.
        self.env.invalidate_all()
        try:
            record.with_user(user).read(list(fields))
            return True
        except AccessError:
            return False

    def _can_write(self, record, user):
        if not record:
            return None
        try:
            record.with_user(user).check_access('write')
            return True
        except AccessError:
            return False

    def _matrix(self, subjects, users, allowed):
        """subjects: {name: (record, 'read'|'write'|fields tuple)}; allowed: {name: set of roles}."""
        for name, (record, operation) in subjects.items():
            for role, user in users.items():
                if operation == 'write':
                    result = self._can_write(record, user)
                elif operation == 'datas':
                    result = self._can_read(record, user, ('datas',))
                elif isinstance(operation, tuple):
                    result = self._can_read(record, user, operation)
                else:
                    result = self._can_read(record, user)
                self._check(name, role, result, role in allowed[name])

    def _http_get(self, user, url):
        if user:
            self.authenticate(user.login, user.login)
        else:
            self.authenticate(None, None)
        # The portal answers first with a redirect to the language's URL: follow it, and judge by
        # the content (a refused route ends on another page, with a 200 too).
        response = self.url_open(url)
        return response.status_code, response.content

    def _audit_end(self):
        _logger.info("AUDIT_MATRIX %s", json.dumps({'title': self.audit_title, 'matrix': self.observed},
                                                   sort_keys=True))
        if self.differences:
            _logger.warning("AUDIT_DIFFERENCES %s", json.dumps({'title': self.audit_title,
                                                                'differences': self.differences}))
        self.assertFalse(self.differences, "\n".join(self.differences))


@tagged('post_install', '-at_install')
class TestAuditAccessIndividual(AuditMatrixMixin, HttpCase, ErasmusRecordsCase):
    """Internship and staff-style individual mobilities: application, mobility record, the call's
    confidential documents (health card, inclusion, fewer opportunities), project documents,
    payments and exports."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.director_user = create_role_user(cls, 'director', 'audit_ind_director')
        cls.admin_user = create_role_user(cls, 'academic_admin', 'audit_ind_admin')
        cls.student_user = portal_user(cls.env, cls.student, 'audit_ind_student')
        cls.second_user = portal_user(cls.env, cls.second, 'audit_ind_second')

    def _fixtures(self):
        first, second = self._on_project()
        # The first student becomes a minor once admitted (a minor applies with the family's
        # authorisation; the fixtures' application has none).
        family = self._minor_with_family()
        family_user = portal_user(self.env, family, 'audit_ind_family')
        application = first.application_id
        files = {}
        for name, content in (('European Health Insurance Card', HEALTH), ('Inclusion documentation', INCLUSION),
                              ('OLS certificate', OLS)):
            line = self._line(first, name)
            line._ems_add_files([(f'audit_{name}.pdf', content)])
            files[name] = line
        evidence = application.document_ids.filtered(lambda line: line.call_document_id == self.evidence)
        evidence._ems_add_files([('audit_evidence.pdf', EVIDENCE)])
        Document = self.env['ems.erasmus.project.document']
        confidential, public = Document.create([
            {'project_id': self.project.id, 'name': 'Audit bank data', 'category': '03_Economia',
             'confidential': True, 'mobility_ids': [(6, 0, first.ids)]},
            {'project_id': self.project.id, 'name': 'Audit dissemination', 'category': '04_Impacte_i_difusio'}])
        for document, content in ((confidential, BANK), (public, OPEN_DOC)):
            document.attachment_ids = [(0, 0, {'name': f'{document.name}.pdf', 'raw': content,
                                               'res_model': Document._name, 'res_id': document.id})]
        first.with_user(self.technician_user).write({'grant_amount': 1000})
        first.with_user(self.technician_user).action_request_prefinancing()
        return first, second, files, evidence, confidential, public, family_user

    def test_access_matrix(self):
        self._audit_start("Individual mobilities")
        first, second, files, evidence, confidential, public, family_user = self._fixtures()
        application = first.application_id
        self.assertIn(self.env.ref('ems.group_erasmus_evaluator'), self.evaluator_1.groups_id)
        users = {
            'coordinator': self.erasmus_user, 'technician': self.technician_user, 'academic_admin': self.admin_user,
            'director': self.director_user, 'head_of_studies': self.hos_user, 'secretary': self.secretary_user,
            'teacher': self.teacher_user, 'evaluator': self.evaluator_1,
            'portal_student_owner': self.student_user, 'portal_other_student': self.second_user,
            'portal_family': family_user,
        }
        team = {'coordinator', 'technician', 'academic_admin'}
        readers = team | {'director', 'head_of_studies'}
        health, inclusion, ols = (files[name] for name in (
            'European Health Insurance Card', 'Inclusion documentation', 'OLS certificate'))
        payment = first.payment_ids
        export = self.env['ems.erasmus.export'].with_user(self.technician_user).create(
            {'scope': 'record', 'mobility_id': first.id, 'project_id': self.project.id})
        subjects = {
            'mobility (read)': (first, 'read'),
            'application (read)': (application, 'read'),
            'application.support_needs (field)': (application, ('support_needs',)),
            'application.fewer_opportunities_check (field)': (application, ('fewer_opportunities_check',)),
            'application.score_d (field)': (application, ('score_d',)),
            'line OLS, not confidential (read)': (ols, 'read'),
            'file OLS (datas)': (ols.attachment_ids, 'datas'),
            'line health card, confidential (read)': (health, 'read'),
            'file health card (datas)': (health.attachment_ids, 'datas'),
            'line inclusion, confidential (read)': (inclusion, 'read'),
            'file inclusion (datas)': (inclusion.attachment_ids, 'datas'),
            'line fewer opportunities evidence, confidential (read)': (evidence, 'read'),
            'file fewer opportunities evidence (datas)': (evidence.attachment_ids, 'datas'),
            'line health card (write)': (health, 'write'),
            'line OLS (write)': (ols, 'write'),
            'project document, confidential (read)': (confidential, 'read'),
            'file project document, confidential (datas)': (confidential.attachment_ids, 'datas'),
            'project document, not confidential (read)': (public, 'read'),
            'file project document, not confidential (datas)': (public.attachment_ids, 'datas'),
            'project document, not confidential (write)': (public, 'write'),
            'project document, confidential (write)': (confidential, 'write'),
            'grant payment (read)': (payment, 'read'),
            'grant payment IBAN (field)': (payment, ('bank_account',)),
            "export log made by the technician (read)": (export, 'read'),
        }
        allowed = {
            'mobility (read)': readers, 'application (read)': readers,
            'application.support_needs (field)': team, 'application.fewer_opportunities_check (field)': team,
            'application.score_d (field)': team,
            'line OLS, not confidential (read)': readers, 'file OLS (datas)': readers,
            'line health card, confidential (read)': team, 'file health card (datas)': team,
            'line inclusion, confidential (read)': team, 'file inclusion (datas)': team,
            'line fewer opportunities evidence, confidential (read)': team,
            'file fewer opportunities evidence (datas)': team,
            'line health card (write)': team, 'line OLS (write)': team,
            'project document, confidential (read)': team, 'file project document, confidential (datas)': team,
            'project document, not confidential (read)': readers | {'secretary'},
            'file project document, not confidential (datas)': readers | {'secretary'},
            'project document, not confidential (write)': team | {'secretary'},
            'project document, confidential (write)': team,
            'grant payment (read)': team | {'secretary'}, 'grant payment IBAN (field)': team | {'secretary'},
            "export log made by the technician (read)": team,
        }
        self._matrix(subjects, users, allowed)

        # Who can ask for an export, and for an audit export with the confidential documents.
        Export = self.env['ems.erasmus.export']
        for audit in (False, True):
            subject = 'ask for a project export' + (' (audit, confidential)' if audit else '')
            expected = {'coordinator', 'academic_admin'} if audit else team | {'secretary'}
            for role, user in users.items():
                try:
                    request = Export.with_user(user).create({
                        'scope': 'project', 'project_id': self.project.id, 'include_confidential': audit,
                        'reason': audit and 'Audit check' or False})
                    request.with_user(user)._ems_check_request()
                    result = True
                except (AccessError, UserError):
                    result = False
                self._check(subject, role, result, role in expected)

        # What a non-audit project export carries, asked for by the Secretary, and an audit one.
        for role, user, audit in (('secretary', self.secretary_user, False), ('technician', self.technician_user, False),
                                  ('coordinator', self.erasmus_user, True)):
            request = Export.with_user(user).create({'scope': 'project', 'project_id': self.project.id,
                                                     'include_confidential': audit,
                                                     'reason': audit and 'Audit check' or False})
            with request.with_user(user)._ems_zip() as archive:
                bundle = zipfile.ZipFile(io.BytesIO(archive.read()))
            contents = b''.join(bundle.read(name) for name in bundle.namelist())
            leaked = [marker.decode() for marker in CONFIDENTIAL_MARKERS if marker in contents]
            subject = 'project ZIP carries confidential files' + (' (audit)' if audit else '')
            self._check(subject, role, bool(leaked), audit)
            self._check('project ZIP carries the OLS file', role, OLS in contents, True)
            self._check('project ZIP has index.csv, manifest.json, SHA256SUMS', role, all(
                any(name.endswith(suffix) for name in bundle.namelist())
                for suffix in ('/index.csv', '/manifest.json', '/SHA256SUMS')), True)

        # The same files through HTTP: /web/content, the portal routes, the downloads.
        health_file = health.attachment_ids
        for role, user in users.items():
            status, content = self._http_get(user, f'/web/content/{health_file.id}?download=true')
            self._check('HTTP /web/content health card', role, status == 200 and HEALTH in content, role in team)
            status, content = self._http_get(user, f'/web/content/{ols.attachment_ids.id}?download=true')
            self._check('HTTP /web/content OLS', role, status == 200 and OLS in content, role in readers)
        url = f'/my/erasmus/call/{self.call.id}/mobility/file/{health_file.id}'
        for role in ('portal_student_owner', 'portal_other_student', 'portal_family', 'teacher', 'head_of_studies'):
            status, content = self._http_get(users[role], url)
            self._check('HTTP portal mobility file: health card', role, status == 200 and HEALTH in content,
                        role == 'portal_student_owner')
        status, _content = self._http_get(None, f'/web/content/{health_file.id}?download=true')
        self._check('HTTP /web/content health card', 'anonymous', status == 200 and HEALTH in _content, False)
        for role in ('portal_family', 'portal_other_student'):
            status, content = self._http_get(users[role], '/my/erasmus')
            self._check('HTTP /my/erasmus shows the health card file name', role,
                        b'audit_European Health Insurance Card' in content, False)
            status, content = self._http_get(users[role], f'/my/erasmus/call/{self.call.id}')
            self._check("HTTP the other's call page shows their files", role, b'audit_OLS' in content, False)
        participants = f'/ems/erasmus/participants?application_ids={application.id}'
        for role in ('coordinator', 'technician', 'head_of_studies', 'secretary', 'teacher', 'portal_student_owner'):
            status, content = self._http_get(users[role], participants)
            self._check("HTTP participants' spreadsheet (IBAN)", role, status == 200 and content[:2] == b'PK',
                        role in ('coordinator', 'technician'))
        for role in ('coordinator', 'secretary', 'head_of_studies', 'technician'):
            status, _content = self._http_get(users[role], f'/ems/erasmus/export/{export.id}')
            self._check('HTTP download of an export asked for by the technician', role, status == 200,
                        role == 'technician')
        status, _content = self._http_get(self.technician_user, f'/ems/erasmus/export/{export.id}')
        self._check('HTTP second download of the same export', 'technician', status == 200, False)

        # The family of the minor signs the commitment letter on its own portal, never the student's files.
        self._check('family portal sees the guardian mobility', 'portal_family',
                    first in family_user.partner_id._ems_erasmus_guardian_mobilities(), None)
        self._audit_end()


@tagged('post_install', '-at_install')
class TestAuditAccessGroup(AuditMatrixMixin, HttpCase, ErasmusGroupRecordsCase):
    """Group mobilities: the group's shared documents, each participant's file, the enrolments
    (ranking) and the teachers who lead or accompany the group."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.director_user = create_role_user(cls, 'director', 'audit_grp_director')
        cls.hos_user = create_role_user(cls, 'head_of_studies', 'audit_grp_hos')
        cls.admin_user = create_role_user(cls, 'academic_admin', 'audit_grp_admin')

    def test_access_matrix(self):
        self._audit_start("Group mobilities")
        participant = self._approved_with_minor()
        family = self._family()
        family_user = portal_user(self.env, family, 'audit_grp_family')
        minor_user = portal_user(self.env, self.minor, 'audit_grp_minor')
        others = self.mobility.participant_ids.filtered(
            lambda other: other.role == 'student' and other != participant)
        other_user = portal_user(self.env, others[0].partner_id, 'audit_grp_other')
        health = self._upload(self._line(participant.document_ids, 'European Health Insurance Card'),
                              'audit_group_health.pdf', GROUP_HEALTH)
        grant = self._upload(self._line(participant.document_ids, 'Grant agreement'), 'audit_group_grant.pdf',
                             GROUP_GRANT)
        inclusion = self._upload(self._line(self.mobility.document_ids, 'Group inclusion documentation'),
                                 'audit_group_inclusion.pdf', GROUP_INCLUSION)
        learning = self._line(self.mobility.document_ids, 'Group learning agreement')
        registration = participant.registration_ids
        users = {
            'coordinator': self.coordinator_user, 'technician': self.technician_user, 'academic_admin': self.admin_user,
            'director': self.director_user, 'head_of_studies': self.hos_user, 'secretary': self.secretary_user,
            'leader': self.leader_user, 'companion': self.companion_user, 'other_teacher': self.other_teacher_user,
            'portal_student_owner': minor_user, 'portal_other_student': other_user, 'portal_family': family_user,
        }
        team = {'coordinator', 'technician', 'academic_admin'}
        overview = team | {'director', 'head_of_studies'}
        teachers = {'leader', 'companion'}
        subjects = {
            'group mobility (read)': (self.mobility, 'read'),
            'participant file (read)': (participant, 'read'),
            'enrolment with ranking (read)': (registration, 'read'),
            'enrolment.fewer_opportunities (field)': (registration, ('fewer_opportunities',)),
            'enrolment.strike_count (field)': (registration, ('strike_count',)),
            'line grant agreement, not confidential (read)': (grant, 'read'),
            'file grant agreement (datas)': (grant.attachment_ids, 'datas'),
            'line health card, confidential (read)': (health, 'read'),
            'file health card (datas)': (health.attachment_ids, 'datas'),
            'line group inclusion, confidential (read)': (inclusion, 'read'),
            'file group inclusion (datas)': (inclusion.attachment_ids, 'datas'),
            'line group learning agreement (read)': (learning, 'read'),
            "line student's grant agreement (write)": (grant, 'write'),
            'line group learning agreement (write)': (learning, 'write'),
            'line health card (write)': (health, 'write'),
        }
        allowed = {
            'group mobility (read)': overview | teachers, 'participant file (read)': overview | teachers,
            'enrolment with ranking (read)': overview | {'leader'},
            'enrolment.fewer_opportunities (field)': team, 'enrolment.strike_count (field)': team,
            'line grant agreement, not confidential (read)': overview | teachers,
            'file grant agreement (datas)': overview | teachers,
            'line health card, confidential (read)': team, 'file health card (datas)': team,
            'line group inclusion, confidential (read)': team, 'file group inclusion (datas)': team,
            'line group learning agreement (read)': overview | teachers,
            "line student's grant agreement (write)": team | {'leader'},
            'line group learning agreement (write)': team | {'leader'},
            'line health card (write)': team,
        }
        self._matrix(subjects, users, allowed)

        for role, user in users.items():
            status, content = self._http_get(user, f'/web/content/{health.attachment_ids.id}?download=true')
            self._check('HTTP /web/content group health card', role, status == 200 and GROUP_HEALTH in content,
                        role in team)
        for role in ('portal_student_owner', 'portal_other_student', 'portal_family'):
            status, content = self._http_get(users[role], f'/my/erasmus/group/{self.mobility.id}')
            self._check("HTTP group file page shows the minor's health card", role,
                        b'audit_group_health.pdf' in content, role == 'portal_student_owner')
            status, content = self._http_get(
                users[role], f'/my/erasmus/group/{self.mobility.id}/file/{inclusion.attachment_ids.id}')
            self._check('HTTP portal group file: confidential group inclusion', role,
                        status == 200 and GROUP_INCLUSION in content, False)
        # The family accepts the commitment letter for the minor, and only for them.
        accept = f'/my/erasmus/group/commitment/{participant.id}'
        self.authenticate(other_user.login, other_user.login)
        self.url_open(accept, data={'csrf_token': Request.csrf_token(self), 'accepted': 'on'})
        self._check('commitment accepted by another student for the minor', 'portal_other_student',
                    bool(participant.commitment_guardian_signed_date), False)
        self.authenticate(family_user.login, family_user.login)
        self.url_open(accept, data={'csrf_token': Request.csrf_token(self), 'accepted': 'on'})
        self._check('commitment accepted by the family for the minor', 'portal_family',
                    participant.commitment_guardian_signed_by_id == family_user, True)

        # A non-audit group export, asked for by the Secretary and by the technician.
        for role, user, audit in (('secretary', self.secretary_user, False), ('technician', self.technician_user, False),
                                  ('coordinator', self.coordinator_user, True)):
            names, contents, _export = self._export(user, scope='group', group_mobility_id=self.mobility.id,
                                                   include_confidential=audit, reason=audit and 'Audit check' or False)
            blob = b''.join(contents.values())
            leaked = [marker.decode() for marker in CONFIDENTIAL_MARKERS if marker in blob]
            self._check('group ZIP carries confidential files' + (' (audit)' if audit else ''), role,
                        bool(leaked), audit)
            self._check('group ZIP carries the grant agreement', role, GROUP_GRANT in blob, True)
            selection = next((name for name in names if name.endswith('Selection.csv')), None)
            header = contents[selection].decode('utf-8-sig').splitlines()[0] if selection else ''
            self._check('group ZIP selection.csv has the conduct warnings column', role,
                        'Conduct warnings' in header, audit)
        self._audit_end()
