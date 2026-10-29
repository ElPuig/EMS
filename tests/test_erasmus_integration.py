import csv
import io
import zipfile
from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import HttpCase, tagged

from .common import create_role_user
from .test_erasmus import PDF
from .test_erasmus_group_mobility import ErasmusGroupMobilityCase
from .test_erasmus_mobility import tick_signatures


class ErasmusGroupRecordsCase(ErasmusGroupMobilityCase):
    """A group mobility on the document records: the same categories, statuses and exports as the
    individual mobilities (docs/en/developers/erasmus/records.md)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.secretary_user = create_role_user(cls, 'secretary', 'test_group_secretary')

    def _student(self):
        return self.mobility.participant_ids.filtered(lambda participant: participant.role == 'student')[:1]

    def _line(self, lines, name):
        return lines.filtered(lambda line: line.name == name)

    def _upload(self, line, name='file.pdf', content=PDF):
        line._ems_add_files([(name, content)])
        return line

    def _confirm_destination(self):
        self.mobility.with_user(self.coordinator_user).write({'city': 'Berlin',
                                                              'country_id': self.env.ref('base.de').id})

    def _export(self, user, **vals):
        """Ask for an export as `user` and build its ZIP: (names, {name: bytes}, export)."""
        export = self.env['ems.erasmus.export'].with_user(user).create(vals)
        with export._ems_zip() as archive:
            bundle = zipfile.ZipFile(io.BytesIO(archive.read()))
        return bundle.namelist(), {name: bundle.read(name) for name in bundle.namelist()}, export

    def _csv(self, contents, name):
        return list(csv.DictReader(io.StringIO(contents[name].decode('utf-8-sig'))))


@tagged('post_install', '-at_install')
class TestErasmusGroupRecords(ErasmusGroupRecordsCase):
    """The group's documents in the record's categories, with the same status rules."""

    def test_group_documents_go_in_the_record_categories(self):
        self._approved()
        student = self._student()
        categories = {line.name: (line.file_category, line.confidential) for line in student.document_ids}
        self.assertEqual(categories['European Health Insurance Card'], ('01_Dades_i_autoritzacions', True),
                         "Health information: data and authorisations, confidential, as in the calls.")
        self.assertEqual(categories['Authorisation for minors to travel abroad'][0], '01_Dades_i_autoritzacions')
        self.assertEqual(categories['Insurance policy'][0], '02_Abans_de_la_mobilitat')
        self.assertEqual(categories['Europass mobility document'][0], '04_Despres_de_la_mobilitat')
        shared = {line.name: (line.file_category, line.confidential) for line in self.mobility.document_ids}
        self.assertEqual(shared['Group learning agreement'][0], '02_Abans_de_la_mobilitat')
        self.assertEqual(shared['Group travel documents'][0], '03_Durant_la_mobilitat')
        self.assertEqual(shared['Group inclusion documentation'], ('01_Dades_i_autoritzacions', True))
        teacher = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'leader')
        self.assertEqual(self._line(teacher.document_ids, 'Certificate of stay').file_category,
                         '04_Despres_de_la_mobilitat')

    def test_a_document_to_sign_is_never_complete_only_because_it_is_uploaded(self):
        self._approved()
        final_list = self._upload(self._line(self.mobility.document_ids,
                                             'Final list of participants and accompanying teachers'))
        self.assertEqual(final_list.file_state, 'complete', "Provided by the team, nobody signs it: once uploaded.")
        agreement = self._upload(self._line(self.mobility.document_ids, 'Group learning agreement'))
        self.assertEqual(agreement.file_state, 'to_review',
                         "Signed by the coordinator and the host: the team checks the signatures first.")
        self.assertEqual(self.mobility.documents_to_review, 1)
        tick_signatures(agreement)
        agreement.with_user(self.leader_user).action_mark_valid()
        self.assertEqual(agreement.file_state, 'complete')
        grant = self._upload(self._line(self._student().document_ids, 'Grant agreement'))
        self.assertEqual(grant.file_state, 'to_review')
        grant.with_user(self.technician_user).action_mark_needs_change()
        self.assertEqual(grant.file_state, 'needs_change')

    def test_ready_to_leave_only_with_every_document_complete_and_the_letter_final(self):
        self._approved()
        self._confirm_destination()
        student = self._student()
        student.action_sign_commitment(True, '10.0.0.1')
        self.assertFalse(student.preparation_complete, "Documents still missing.")
        for line in student.document_ids.filtered(lambda line: line.stage == 'preparation' and line.is_required):
            self._upload(line)
            if line.file_state == 'to_review':
                tick_signatures(line)
                line.with_user(self.technician_user).action_mark_valid()
        self.assertTrue(student.preparation_complete)
        self.assertEqual(student.record_missing, len(student.document_ids.filtered(
            lambda line: line.is_required and line.stage == 'return')))

    def test_files_kept_and_every_review_in_the_group_chatter(self):
        self._approved()
        grant = self._upload(self._line(self._student().document_ids, 'Grant agreement'))
        tick_signatures(grant)
        grant.with_user(self.technician_user).action_mark_valid()
        self.assertTrue(self.mobility.message_ids.filtered(
            lambda message: 'Grant agreement' in (message.body or '') and self._student().partner_id.name in
            (message.body or '')), "The review is written in the group mobility's chatter, with the participant.")
        with self.assertRaises(UserError):
            grant.with_user(self.technician_user).write({'attachment_ids': [(5, 0, 0)]})
        self.mobility.sudo().with_context(ems_erasmus_state=True).write({'state': 'done'})
        other = self._upload(self._line(self._student().document_ids, 'European Health Insurance Card'))
        with self.assertRaises(UserError):
            other.with_user(self.technician_user).write({'attachment_ids': [(5, 0, 0)]})

    def test_the_project_counts_the_group_records(self):
        self._approved()
        counts = self.project.read(['record_count', 'record_missing_count'])[0]
        self.assertEqual(counts['record_count'], 10, "Eight students and two teachers.")
        self.assertEqual(counts['record_missing_count'], self.env['ems.erasmus.export']._ems_group_missing(
            self.mobility))
        self.assertIn(self.mobility, self.project.group_mobility_ids)


@tagged('post_install', '-at_install')
class TestErasmusCommitmentVersions(ErasmusGroupRecordsCase):
    """The commitment letter: provisional while the destination is to be confirmed, a new version and
    a new acceptance when its conditions change, every accepted version kept as it was."""

    def test_accepted_with_the_destination_to_confirm_is_provisional(self):
        minor = self._approved_with_minor()
        minor.action_sign_commitment(True, '10.0.0.1')
        minor.action_sign_commitment(True, '10.0.0.2', guardian=True)
        self.assertIn('still to be confirmed', minor.commitment_signed_text)
        self.assertTrue(minor.commitment_provisional)
        self.assertFalse(minor.commitment_pending)
        self.assertFalse(minor.preparation_complete, "A provisional acceptance never lets the student leave.")

    def test_confirming_the_destination_asks_for_the_new_letter(self):
        minor = self._approved_with_minor()
        minor.action_sign_commitment(True, '10.0.0.1')
        minor.action_sign_commitment(True, '10.0.0.2', guardian=True)
        first_text = minor.commitment_signed_text
        self._confirm_destination()
        self.assertTrue(minor.commitment_pending)
        self.assertTrue(minor.commitment_guardian_pending)
        self.assertFalse(minor.commitment_provisional)
        version = minor.commitment_version_ids
        self.assertEqual(len(version), 1)
        self.assertEqual((version.number, version.text, version.signed_ip, version.guardian_signed_ip),
                         (1, first_text, '10.0.0.1', '10.0.0.2'), "The accepted letter is kept exactly as it was.")
        self.assertTrue(version.provisional)
        self.assertIn('Berlin', minor._ems_commitment_text())
        minor.action_sign_commitment(True, '10.0.0.3', guardian=True)
        self.assertTrue(minor.commitment_pending, "The student accepts the new letter too.")
        minor.action_sign_commitment(True, '10.0.0.4')
        self.assertIn('Berlin', minor.commitment_signed_text)
        self.assertEqual(minor.commitment_guardian_signed_ip, '10.0.0.3')
        self.assertFalse(minor.commitment_pending or minor.commitment_guardian_pending or minor.commitment_provisional)

    def test_a_change_of_dates_keeps_the_earlier_version(self):
        self._approved()
        self._confirm_destination()
        student = self._student()
        student.action_sign_commitment(True, '10.0.0.1')
        self.mobility.with_user(self.coordinator_user).write({'programme': '<p>Visits</p>', 'name': 'Renamed'})
        self.assertFalse(student.commitment_version_ids, "Neither the programme nor the name are in the letter.")
        self.mobility.with_user(self.coordinator_user).write(
            {'date_end': self.mobility.date_end + timedelta(days=2)})
        self.assertTrue(student.commitment_pending)
        self.assertEqual(student.commitment_version_ids.signed_ip, '10.0.0.1')
        with self.assertRaises(UserError):
            student.commitment_version_ids.sudo().write({'text': 'Changed'})
        with self.assertRaises(UserError):
            student.commitment_version_ids.sudo().unlink()

    def test_the_letter_never_replaces_the_official_authorisation(self):
        minor = self._approved_with_minor()
        self._confirm_destination()
        minor.action_sign_commitment(True, '10.0.0.1')
        minor.action_sign_commitment(True, '10.0.0.2', guardian=True)
        authorisation = self._line(minor.document_ids, 'Authorisation for minors to travel abroad')
        self.assertTrue(authorisation.is_required)
        self.assertEqual(authorisation.file_state, 'missing')
        self.assertFalse(minor.preparation_complete)
        self.assertIn('does not replace the official authorisation', minor.commitment_signed_text)

    def test_the_leader_never_reads_the_versions(self):
        self._approved()
        self._confirm_destination()
        student = self._student()
        student.action_sign_commitment(True, '10.0.0.1')
        self.mobility.with_user(self.coordinator_user).write({'city': 'Hamburg'})
        with self.assertRaises(AccessError):
            student.commitment_version_ids.with_user(self.leader_user).read(['text'])


@tagged('post_install', '-at_install')
class TestErasmusGroupExport(ErasmusGroupRecordsCase):
    """The group mobilities in the ZIPs: their common documents once, every participant's record,
    the selection's evidence; confidential and conduct data only in an audit export."""

    def _filled(self):
        self._approved()
        self._confirm_destination()
        self._upload(self._line(self.mobility.document_ids, 'Group learning agreement'), 'agreement.pdf')
        self._upload(self._line(self.mobility.document_ids, 'Group inclusion documentation'), 'inclusion.pdf')
        student = self._student()
        self._upload(self._line(student.document_ids, 'European Health Insurance Card'), 'health.pdf')
        self._upload(self._line(student.document_ids, 'Grant agreement'), 'grant.pdf')
        student.action_sign_commitment(True, '10.0.0.1')
        self.mobility.with_user(self.coordinator_user).write({'city': 'Hamburg'})
        student.action_sign_commitment(True, '10.0.0.2')
        self.env['ems.erasmus.group.log'].with_user(self.leader_user).create({
            'group_mobility_id': self.mobility.id, 'kind': 'evidence', 'name': 'Visit to the company',
            'attachment_ids': [(0, 0, {'name': 'photo.jpg', 'raw': b'jpeg'})]})
        return student

    def test_project_export_has_the_group_once_and_every_participant(self):
        student = self._filled()
        names, contents, export = self._export(self.technician_user, scope='project', project_id=self.project.id)
        root = names[0].split('/')[0]
        group = f"{root}/02_Mobilitats/GRUP{self.mobility.id:05d}_{self.mobility.name}"
        common = f"{group}/00_Documentacio_comuna"
        self.assertIn(f"{common}/02_Abans_de_la_mobilitat/Group learning agreement/v1_agreement.pdf", names)
        self.assertEqual(sum(name.endswith('agreement.pdf') for name in names), 1, "A shared document, once.")
        self.assertIn(f"{common}/03_Durant_la_mobilitat/Follow-up/{self.mobility.log_ids.date}_Visit to the company/"
                      "photo.jpg", names)
        folder = f"{group}/ALU{student.id:05d}_{student.partner_id.name}"
        self.assertIn(f"{folder}/02_Abans_de_la_mobilitat/Grant agreement/v1_grant.pdf", names)
        self.assertFalse(any(name.endswith(('health.pdf', 'inclusion.pdf')) for name in names),
                         "Confidential: only in an audit export.")
        letter = contents[f"{folder}/02_Abans_de_la_mobilitat/Commitment letter.html"].decode()
        self.assertIn('Hamburg', letter)
        self.assertIn('Earlier version 1', letter)
        self.assertIn('10.0.0.1', letter)
        index = list(csv.DictReader(io.StringIO(contents[f'{root}/index.csv'].decode('utf-8-sig'))))
        participants = {row['Participant'] for row in index if row['Mobility'] == f'GRUP{self.mobility.id:05d}'}
        self.assertEqual(len(participants - {self.mobility.name}), 10,
                         "Eight students and two teachers, each with their own record in the index.")
        shared = [row for row in index if row['Participant'] == student.partner_id.name
                  and row['Document'] == 'Group learning agreement']
        self.assertIn('Shared document', shared[0]['Notes'], "Each record references the shared document.")
        selection = self._csv(contents, f"{common}/01_Dades_i_autoritzacions/Selection.csv")
        self.assertEqual(len(selection), 10)
        self.assertNotIn('Conduct warnings this course', selection[0], "Conduct data only in an audit export.")
        self.assertEqual(export.missing_count, self.env['ems.erasmus.export']._ems_group_missing(self.mobility),
                         "The project has no individual mobility: only the group's documents are missing.")

    def test_audit_export_adds_the_confidential_and_conduct_data(self):
        self._filled()
        names, contents, _export = self._export(self.coordinator_user, scope='group',
                                                group_mobility_id=self.mobility.id, include_confidential=True,
                                                reason='SEPIE audit 2027')
        self.assertTrue(any(name.endswith('health.pdf') for name in names))
        self.assertTrue(any(name.endswith('inclusion.pdf') for name in names))
        root = names[0].split('/')[0]
        selection = self._csv(contents, f"{root}/00_Documentacio_comuna/01_Dades_i_autoritzacions/Selection.csv")
        self.assertIn('Conduct warnings this course', selection[0])

    def test_group_export_is_logged_in_its_chatter_and_only_for_exporters(self):
        self._filled()
        _names, _contents, export = self._export(self.secretary_user, scope='group',
                                                 group_mobility_id=self.mobility.id)
        self.assertEqual(export.state, 'done')
        self.assertTrue(self.mobility.message_ids.filtered(lambda message: 'exported' in (message.body or '')))
        for user in (self.leader_user, self.companion_user):
            with self.assertRaises(AccessError):
                self.env['ems.erasmus.export'].with_user(user).create(
                    {'scope': 'group', 'group_mobility_id': self.mobility.id})
            with self.assertRaises(AccessError):
                self.mobility.with_user(user).action_export_dossier()

    def test_draft_and_cancelled_groups_stay_out(self):
        draft = self.env['ems.erasmus.group.mobility'].with_user(self.coordinator_user).create(
            {'name': 'Draft group', 'project_id': self.project.id})
        names, _contents, _export = self._export(self.technician_user, scope='project', project_id=self.project.id)
        self.assertFalse(any(f'GRUP{draft.id:05d}' in name for name in names))


@tagged('post_install', '-at_install')
class TestErasmusGroupDocumentAccess(HttpCase, ErasmusGroupRecordsCase):
    """Unauthorised access to the group's documents, through RPC, attachments and routes."""

    def test_confidential_documents_and_their_files_never_reach_the_teachers(self):
        self._approved()
        health = self._upload(self._line(self._student().document_ids, 'European Health Insurance Card'),
                              'health.pdf')
        attachment = health.attachment_ids
        for user in (self.leader_user, self.companion_user):
            with self.assertRaises(AccessError):
                health.with_user(user).read(['name'])
            with self.assertRaises(AccessError):
                attachment.with_user(user).read(['datas'])
        self.authenticate(self.companion_user.login, self.companion_user.login)
        response = self.url_open(f'/web/content/{attachment.id}?download=true')
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn(PDF, response.content)

    def test_another_teacher_reaches_no_document_nor_file(self):
        self._approved()
        grant = self._upload(self._line(self._student().document_ids, 'Grant agreement'))
        Line = self.env['ems.erasmus.application.document'].with_user(self.other_teacher_user)
        with self.assertRaises(AccessError):
            Line.search_count([('group_mobility_id', '=', self.mobility.id)])
        with self.assertRaises(AccessError):
            grant.attachment_ids.with_user(self.other_teacher_user).read(['datas'])
        self.authenticate(self.other_teacher_user.login, self.other_teacher_user.login)
        self.assertNotEqual(self.url_open(f'/web/content/{grant.attachment_ids.id}?download=true').status_code, 200)

    def test_a_student_never_downloads_another_students_file(self):
        self._approved()
        students = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'student')
        insurance = self._line(students[1].document_ids, 'Insurance policy')
        insurance.prepared_attachment_ids = [(0, 0, {'name': 'policy.pdf', 'raw': PDF, 'res_model': insurance._name,
                                                     'res_id': insurance.id})]
        user = self.env['res.users'].create({
            'name': students[0].partner_id.name, 'login': 'test_group_portal_student', 'password': 'test_group_portal_student',
            'partner_id': students[0].partner_id.id, 'groups_id': [(6, 0, self.env.ref('base.group_portal').ids)]})
        self.authenticate(user.login, user.login)
        response = self.url_open(
            f'/my/erasmus/group/{self.mobility.id}/file/{insurance.prepared_attachment_ids.id}', allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertNotIn(PDF, response.content)
        response = self.url_open(f'/web/content/{insurance.prepared_attachment_ids.id}?download=true')
        self.assertNotIn(PDF, response.content)

    def test_an_export_is_only_downloaded_by_its_requester(self):
        self._approved()
        export = self.env['ems.erasmus.export'].with_user(self.technician_user).create(
            {'scope': 'group', 'group_mobility_id': self.mobility.id})
        self.authenticate(self.leader_user.login, self.leader_user.login)
        self.assertEqual(self.url_open(f'/ems/erasmus/export/{export.id}').status_code, 404)
        self.authenticate(self.technician_user.login, self.technician_user.login)
        response = self.url_open(f'/ems/erasmus/export/{export.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/zip')
