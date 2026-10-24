import base64
import csv
import hashlib
import io
import json
import zipfile

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import HttpCase, tagged

from .common import create_role_user
from .test_erasmus import PDF
from .test_erasmus_grant import ErasmusGrantCase


class ErasmusRecordsCase(ErasmusGrantCase):
    """Both students are preparing their mobility, charged to a KA121-VET project."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.technician_user = create_role_user(cls, 'erasmus', 'test_erasmus_technician')
        cls.project = cls.env['ems.erasmus.project'].create({'name': 'TEST-KA121-VET-REC', 'kind': 'ka121_vet'})

    def _on_project(self):
        first, second = self._preparing()
        self.modality.project = 'ka121_vet'
        (first | second).project_id = self.project
        return first, second

    def _line(self, mobility, name):
        return mobility.document_ids.filtered(lambda line: line.name == name)

    def _export(self, user, **vals):
        """Ask for an export as `user` and build its ZIP: (names, {name: bytes}, export)."""
        export = self.env['ems.erasmus.export'].with_user(user).create(vals)
        with export._ems_zip() as archive:
            bundle = zipfile.ZipFile(io.BytesIO(archive.read()))
        return bundle.namelist(), {name: bundle.read(name) for name in bundle.namelist()}, export

    def _index(self, contents, root):
        return list(csv.DictReader(io.StringIO(contents[f'{root}/index.csv'].decode('utf-8-sig'))))


@tagged('post_install', '-at_install')
class TestErasmusRecords(ErasmusRecordsCase):
    """The participants' records: categories, state of each document, history kept."""

    def test_documents_go_in_their_category_from_the_call(self):
        first, _second = self._on_project()
        categories = {line.name: line.file_category for line in first.document_ids}
        self.assertEqual(categories['European Health Insurance Card'], '01_Dades_i_autoritzacions')
        self.assertEqual(categories['Grant agreement'], '02_Abans_de_la_mobilitat', "Before leaving, by default.")
        self.assertEqual(categories['Tickets or boarding passes'], '03_Durant_la_mobilitat')
        self.assertEqual(categories['Europass mobility document'], '04_Despres_de_la_mobilitat', "On return, by default.")
        application_lines = first.application_id.document_ids.filtered(lambda line: line.stage == 'application')
        self.assertEqual(set(application_lines.mapped('file_category')), {'01_Dades_i_autoritzacions'})
        self.assertEqual(first.application_document_ids, application_lines, "Part of the record too.")

    def test_a_signed_document_is_complete_only_once_valid(self):
        first, _second = self._on_project()
        agreement = self._line(first, 'Grant agreement')
        self.assertEqual(agreement.file_state, 'missing')
        agreement.prepared_attachment_ids = self.env['ir.attachment'].create({'name': 'to_sign.pdf', 'raw': PDF})
        first._ems_portal_upload({agreement.call_document_id.id: [('signed.pdf', PDF)]})
        self.assertEqual(agreement.file_state, 'to_review', "Uploaded is not complete: the signatures are checked.")
        agreement.action_mark_needs_change()
        self.assertEqual(agreement.file_state, 'needs_change')
        agreement.action_mark_valid()
        self.assertEqual(agreement.file_state, 'complete')
        policy = self._line(first, 'Insurance policy')
        policy.prepared_attachment_ids = self.env['ir.attachment'].create({'name': 'policy.pdf', 'raw': PDF})
        self.assertEqual(policy.file_state, 'complete', "Provided by the team: complete once uploaded.")
        minors = first.document_ids.filtered(lambda line: line.call_document_id.requirement == 'minor')
        self.assertEqual(set(minors.mapped('file_state')), {'not_applicable'}, "The student is an adult.")
        self.assertEqual(self._line(first, 'Inclusion documentation').file_state, 'optional')

    def test_record_progress_counts_the_required_documents_left(self):
        first, _second = self._on_project()
        required = first._ems_record_lines().filtered('is_required')
        self.assertEqual(first.record_missing, len(required.filtered(lambda line: line.file_state != 'complete')))
        before = first.record_missing
        self._complete_stage(first, 'preparation')
        self.assertLess(first.record_missing, before)
        self.assertEqual(first.record_progress, f"{len(required) - first.record_missing} / {len(required)}")
        self.assertEqual(self.project.record_count, 2)
        self.assertEqual(self.project.record_missing_count, first.record_missing + _second.record_missing)

    def test_files_of_a_valid_document_or_a_closed_mobility_are_kept(self):
        first, _second = self._on_project()
        ols = self._line(first, 'OLS certificate')
        first._ems_portal_upload({ols.call_document_id.id: [('ols.pdf', PDF)]})
        ols.action_mark_valid()
        with self.assertRaises(UserError):
            ols.attachment_ids = [(5, 0, 0)]
        first._ems_portal_upload({self._line(first, 'European Health Insurance Card').call_document_id.id: [
            ('card_v1.pdf', PDF)]})
        card = self._line(first, 'European Health Insurance Card')
        first._ems_portal_upload({card.call_document_id.id: [('card_v2.pdf', PDF)]})
        self.assertEqual(card.attachment_ids.mapped('name'), ['card_v1.pdf', 'card_v2.pdf'],
                         "A new upload is a new version: the earlier one is kept.")

    def test_every_review_change_is_written_in_the_mobility_chatter(self):
        first, _second = self._on_project()
        ols = self._line(first, 'OLS certificate')
        first._ems_portal_upload({ols.call_document_id.id: [('ols.pdf', PDF)]})
        ols.with_user(self.erasmus_user).action_mark_valid()
        message = first.message_ids.filtered(lambda message: 'OLS certificate' in (message.body or ''))[:1]
        self.assertIn('Valid', message.body)
        self.assertEqual(message.author_id, self.erasmus_user.partner_id)

    def test_uploads_keep_only_the_file_name_and_refuse_programs(self):
        first, _second = self._on_project()
        ols = self._line(first, 'OLS certificate')
        first._ems_portal_upload({ols.call_document_id.id: [('../../etc/ols.pdf', PDF)]})
        self.assertEqual(ols.attachment_ids.name, 'ols.pdf')
        for name in ('virus.exe', 'page.HTML', 'script.svg'):
            with self.assertRaises(UserError):
                first._ems_portal_upload({ols.call_document_id.id: [(name, b'x')]})

    def test_a_project_document_is_only_about_its_own_participants(self):
        first, _second = self._on_project()
        other = self.env['ems.erasmus.project'].create({'name': 'TEST-OTHER', 'kind': 'ka121_vet'})
        with self.assertRaises(ValidationError):
            self.env['ems.erasmus.project.document'].create({
                'project_id': other.id, 'name': 'Elsewhere', 'mobility_ids': [(6, 0, first.ids)]})

    def test_confidential_project_documents_only_for_the_erasmus_team(self):
        Document = self.env['ems.erasmus.project.document']
        public = Document.create({'project_id': self.project.id, 'name': 'Budget follow-up', 'category': '03_Economia'})
        hidden = Document.create({'project_id': self.project.id, 'name': 'Bank details', 'confidential': True})
        self.assertEqual(Document.with_user(self.secretary_user).search([('project_id', '=', self.project.id)]), public)
        self.assertEqual(Document.with_user(self.technician_user).search([('project_id', '=', self.project.id)]),
                         public | hidden)

    def test_keeping_period_counts_from_the_final_payment(self):
        self.project.write({'date_end': '2027-05-31', 'budget': 75000})
        self.assertFalse(self.project.keep_until, "No date without the final payment.")
        self.project.final_payment_date = '2027-12-15'
        self.assertEqual(str(self.project.keep_until), '2032-12-15', "Above 60,000 €: kept 5 years.")
        self.project.budget = 50000
        self.assertEqual(str(self.project.keep_until), '2030-12-15')


@tagged('post_install', '-at_install')
class TestErasmusExport(ErasmusRecordsCase):
    """The ZIP exports: a participant's record and a whole project, with index, manifest and hashes."""

    def _filled(self):
        first, second = self._on_project()
        ols = self._line(first, 'OLS certificate')
        first._ems_portal_upload({ols.call_document_id.id: [('ols.pdf', PDF)]})
        first._ems_portal_upload({ols.call_document_id.id: [('ols.pdf', PDF + b'2')]})
        inclusion = self._line(first, 'Inclusion documentation')
        first._ems_portal_upload({inclusion.call_document_id.id: [('evidence.pdf', PDF)]})
        return first, second

    def test_record_export_in_four_categories_with_versions_index_and_hashes(self):
        first, second = self._filled()
        names, contents, export = self._export(self.erasmus_user, scope='record', mobility_id=first.id)
        root = names[0].split('/')[0]
        self.assertTrue(root.startswith(f'ALU{first.id:05d}_'))
        prefix = f'{root}/02_Abans_de_la_mobilitat/OLS certificate'
        self.assertIn(f'{prefix}/v1_ols.pdf', names)
        self.assertIn(f'{prefix}/v2_ols.pdf', names, "Every version, numbered.")
        self.assertEqual(contents[f'{prefix}/v1_ols.pdf'], PDF, "The original file, unchanged.")
        self.assertFalse(any(second.partner_id.name in name for name in names), "Only this mobility.")
        self.assertFalse(any('evidence.pdf' in name for name in names), "Confidential: only in an audit export.")
        sums = dict(reversed(line.split('  ', 1)) for line in contents[f'{root}/SHA256SUMS'].decode().splitlines())
        self.assertEqual(sums['02_Abans_de_la_mobilitat/OLS certificate/v1_ols.pdf'], hashlib.sha256(PDF).hexdigest())
        index = self._index(contents, root)
        grant = [row for row in index if row['Document'] == 'Grant agreement']
        self.assertEqual(grant[0]['Status'], 'Missing', "The index lists what is still missing.")
        self.assertFalse(grant[0]['Path'])
        manifest = json.loads(contents[f'{root}/manifest.json'])
        self.assertEqual(manifest['requested_by'], self.erasmus_user.name)
        self.assertFalse(manifest['audit'])
        self.assertTrue(manifest['not_complete'])
        self.assertEqual(export.state, 'done')
        self.assertEqual(export.file_count, len(sums))
        self.assertEqual(export.missing_count, first.record_missing)
        self.assertTrue(first.message_ids.filtered(lambda message: 'exported' in (message.body or '')))

    def test_audit_export_includes_confidential_documents_with_a_reason(self):
        first, _second = self._filled()
        with self.assertRaises(UserError):
            self._export(self.erasmus_user, scope='record', mobility_id=first.id, include_confidential=True)
        names, _contents, export = self._export(self.erasmus_user, scope='record', mobility_id=first.id,
                                                include_confidential=True, reason='SEPIE check 2027')
        self.assertTrue(any(name.endswith('evidence.pdf') for name in names))
        self.assertTrue(export.include_confidential)
        with self.assertRaises(AccessError):
            self._export(self.technician_user, scope='record', mobility_id=first.id, include_confidential=True,
                         reason='Not the coordinator')

    def test_project_export_in_five_categories_with_every_record(self):
        first, second = self._filled()
        Document = self.env['ems.erasmus.project.document']
        Document.create({'project_id': self.project.id, 'name': 'Grant agreement with SEPIE', 'category': '01_Projecte',
                         'attachment_ids': [(0, 0, {'name': 'sepie.pdf', 'raw': PDF})]})
        Document.create({'project_id': self.project.id, 'name': 'Group programme', 'category': '02_Mobilitats',
                         'participant_category': '02_Abans_de_la_mobilitat',
                         'mobility_ids': [(6, 0, (first | second).ids)],
                         'attachment_ids': [(0, 0, {'name': 'programme.pdf', 'raw': PDF})]})
        invoice = self._invoice(first | second, 600, project_id=self.project.id, document=base64.b64encode(PDF),
                                document_filename='flights.pdf')
        self._transfer(invoice, self.secretary_user)
        names, contents, _export = self._export(self.secretary_user, scope='project', project_id=self.project.id)
        root = 'TEST-KA121-VET-REC'
        self.assertIn(f'{root}/01_Projecte/Grant agreement with SEPIE/v1_sepie.pdf', names)
        common = '02_Mobilitats/00_Documentacio_comuna/Group programme/v1_programme.pdf'
        self.assertIn(f'{root}/{common}', names)
        self.assertEqual(sum(name.endswith('programme.pdf') for name in names), 1, "Shared: one copy only.")
        record = f'{root}/02_Mobilitats/ALU{first.id:05d}_{first.partner_id.name}'
        self.assertIn(f'{record}/02_Abans_de_la_mobilitat/OLS certificate/v1_ols.pdf', names)
        self.assertIn(f'{root}/03_Economia/Invoices/F-TEST-1/flights.pdf', names)
        self.assertFalse(any(name.endswith('evidence.pdf') for name in names), "No confidential files.")
        shared = [row for row in self._index(contents, root)
                  if row['Document'] == 'Group programme' and row['Participant'] == first.partner_id.name]
        self.assertIn(common, shared[0]['Notes'], "The record points to the shared document.")
        self.assertFalse(any(name.endswith('/') for name in names), "No empty folders.")

    def test_record_and_project_of_another_project_never_leak(self):
        first, second = self._filled()
        other = self.env['ems.erasmus.project'].create({'name': 'TEST-OTHER-PRJ', 'kind': 'ka121_vet'})
        second.project_id = other
        names, _contents, _export = self._export(self.erasmus_user, scope='project', project_id=self.project.id)
        self.assertFalse(any(second.partner_id.name in name for name in names))

    def test_only_exporters_ask_and_only_the_requester_downloads_once(self):
        first, _second = self._filled()
        with self.assertRaises(AccessError):
            self.env['ems.erasmus.export'].with_user(self.teacher_user).create(
                {'scope': 'record', 'mobility_id': first.id})
        export = self.env['ems.erasmus.export'].with_user(self.erasmus_user).create(
            {'scope': 'record', 'mobility_id': first.id})
        with self.assertRaises(AccessError):
            export.with_user(self.technician_user)._ems_zip()
        export._ems_zip().close()
        with self.assertRaises(AccessError):
            export._ems_zip()
        self.assertEqual(export.requester_id, self.erasmus_user)
        Export = self.env['ems.erasmus.export']
        own = Export.with_user(self.secretary_user).create({'scope': 'project', 'project_id': self.project.id})
        self.assertEqual(Export.with_user(self.secretary_user).search([]), own, "The Secretary sees their own.")

    def test_names_never_climb_out_of_their_folder(self):
        first, _second = self._on_project()
        self.env['ems.erasmus.project.document'].create({
            'project_id': self.project.id, 'name': '../../etc', 'category': '05_Informe_final_i_auditoria',
            'attachment_ids': [(0, 0, {'name': '../passwd', 'raw': b'x'})]})
        names, _contents, _export = self._export(self.erasmus_user, scope='project', project_id=self.project.id)
        self.assertFalse(any('..' in part for name in names for part in name.split('/')))
        self.assertTrue(all(name.startswith('TEST-KA121-VET-REC/') for name in names))


@tagged('post_install', '-at_install')
class TestErasmusExportDownload(HttpCase, ErasmusRecordsCase):

    def test_download_streams_the_zip_for_the_requester_only(self):
        export = self.env['ems.erasmus.export'].with_user(self.secretary_user).create(
            {'scope': 'project', 'project_id': self.project.id})
        self.authenticate(self.teacher_user.login, self.teacher_user.login)
        self.assertEqual(self.url_open(f'/ems/erasmus/export/{export.id}').status_code, 404)
        self.authenticate(self.secretary_user.login, self.secretary_user.login)
        response = self.url_open(f'/ems/erasmus/export/{export.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/zip')
        self.assertIn('TEST-KA121-VET-REC/index.csv', zipfile.ZipFile(io.BytesIO(response.content)).namelist())
        self.assertEqual(self.url_open(f'/ems/erasmus/export/{export.id}').status_code, 404, "Only once.")
