import io
from unittest.mock import patch

from PIL import Image

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.pdf import PdfFileReader

from .common import (capture_template_emails, create_level_study_group, create_role_employee, create_role_user,
                     mock_outgoing_email, next_student_id)


def one_page_pdf(color='white'):
    """A real one-page PDF, built with Pillow."""
    output = io.BytesIO()
    Image.new('RGB', (200, 280), color).save(output, format='PDF')
    return output.getvalue()


def png_image():
    output = io.BytesIO()
    Image.new('RGB', (120, 160), 'blue').save(output, format='PNG')
    return output.getvalue()


def create_certificate_fixtures(cls, prefix='TCRT'):
    """A certificate type with the FCT circuit (complete, issue, approve) on positions of its own,
    each held by a fixture user: a VET coordinator, a secretary and a director; a teacher who holds
    none; a current student of a level that may request it, and a collaborating company. It requires
    two documents: the agreement, which anyone attaches and is appended to the certificate, and a
    training report only the first step's position attaches, not appended. Its details are FCT's
    (cls.type_fields by key): the school year, asked to the applicant; the company, the period and
    the hours, optional for the applicant and required by the first step; the agreement number,
    optional."""
    cls.level, cls.study, cls.group = create_level_study_group(cls, prefix)
    cls.coordinator = create_role_user(cls, 'vet_coordinator', f'test_{prefix.lower()}_coordinator',
                                       name=f'{prefix} Coordinator')
    cls.secretary = create_role_user(cls, 'secretary', f'test_{prefix.lower()}_secretary', name=f'{prefix} Secretary')
    cls.director = create_role_user(cls, 'director', f'test_{prefix.lower()}_director', name=f'{prefix} Director')
    cls.teacher = create_role_user(cls, 'teacher', f'test_{prefix.lower()}_teacher', name=f'{prefix} Teacher')
    roles = {}
    for key, user, employee_type in (('complete', cls.coordinator, 'teacher'), ('issue', cls.secretary, 'asp'),
                                     ('approve', cls.director, 'teacher')):
        employee = create_role_employee(cls, user, employee_type=employee_type)
        roles[key] = cls.env['ems.role'].create({
            'name': f'{prefix} {key} position', 'employee_type': employee_type,
            'employee_ids': [(6, 0, [employee.id])],
        })
    create_role_employee(cls, cls.teacher)
    cls.roles = roles
    cls.certificate_type = cls.env['ems.certificate.type'].create({
        'name': f'{prefix} FCT', 'requires_documents': True, 'level_ids': [(6, 0, cls.level.ids)],
        'document_ids': [
            (0, 0, {'sequence': 10, 'name': 'Agreement', 'append_to_certificate': True}),
            (0, 0, {'sequence': 20, 'name': 'Training report', 'role_ids': [(6, 0, roles['complete'].ids)],
                    'append_to_certificate': False}),
        ],
        'step_ids': [
            (0, 0, {'sequence': 10, 'name': 'Complete', 'role_ids': [(6, 0, roles['complete'].ids)], 'action': 'complete'}),
            (0, 0, {'sequence': 20, 'name': 'Issue', 'role_ids': [(6, 0, roles['issue'].ids)], 'action': 'issue'}),
            (0, 0, {'sequence': 30, 'name': 'Approve', 'role_ids': [(6, 0, roles['approve'].ids)], 'action': 'approve'}),
        ],
    })
    cls.steps = cls.certificate_type.step_ids.sorted('sequence')
    complete = cls.steps[0].id
    cls.certificate_type.write({
        'field_ids': [
            (0, 0, {'sequence': 10, 'name': 'School year', 'key': 'school_year', 'field_type': 'school_year',
                    'applicant_input': 'required'}),
            (0, 0, {'sequence': 20, 'name': 'Company', 'key': 'company', 'field_type': 'company',
                    'required_step_id': complete}),
            (0, 0, {'sequence': 30, 'name': 'From', 'key': 'start', 'field_type': 'date', 'required_step_id': complete}),
            (0, 0, {'sequence': 40, 'name': 'To', 'key': 'end', 'field_type': 'date', 'required_step_id': complete}),
            (0, 0, {'sequence': 50, 'name': 'Hours', 'key': 'hours', 'field_type': 'number',
                    'required_step_id': complete}),
            (0, 0, {'sequence': 60, 'name': 'Agreement number', 'key': 'agreement', 'field_type': 'char'}),
        ],
    })
    cls.certificate_type.certificate_text = (
        "That {name}, with identity document {document}, a student of {study}, did {hours} hours of workplace "
        "training in the school year {school_year} at the company {company}[, with VAT number {company_vat}], from "
        "{start} to {end}.\n\nSource: the training agreement[ registered with number {agreement}].")
    cls.type_fields = {field.key: field for field in cls.certificate_type.field_ids}
    cls.agreement_document, cls.report_document = cls.certificate_type.document_ids.sorted('sequence')
    cls.student = cls.env['res.partner'].create({
        'name': f'{prefix} Student', 'contact_type': 'student', 'student_id': next_student_id(),
        'main_group_id': cls.group.id, 'birth_date': '2000-01-01', 'document_id': '12345678Z',
        'email': f'{prefix.lower()}.student@example.com',
    })
    cls.company = cls.env['res.partner'].create({
        'name': f'{prefix} Company SL', 'contact_type': 'company', 'is_company': True, 'vat': 'B12345678',
    })


def create_other_type(case, name, field_commands, text):
    """A type besides the fixture's FCT one, for its levels: only an issuing step, no documents, the
    given details and text."""
    return case.env['ems.certificate.type'].create({
        'name': name, 'level_ids': [(6, 0, case.level.ids)], 'field_ids': field_commands, 'certificate_text': text,
        'step_ids': [(0, 0, {'name': 'Issue', 'role_ids': [(6, 0, case.roles['issue'].ids)], 'action': 'issue'})],
    })


@tagged('post_install', '-at_install')
class TestCertificate(TransactionCase):
    """Issue #835 - certificate requests and their approval circuit."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_certificate_fixtures(cls)

    def setUp(self):
        super().setUp()
        # Odoo renders reports as HTML under test: a real one-page PDF instead, so the annex
        # merge can be checked page by page.
        patcher = patch('odoo.addons.base.models.ir_actions_report.IrActionsReport._render_qweb_pdf',
                        return_value=(one_page_pdf(), 'pdf'))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _submitted(self, details=None, **vals):
        certificate = self.env['ems.certificate'].create({
            'type_id': self.certificate_type.id, 'student_id': self.student.id, 'origin': 'portal',
            'student_name': self.student.name, 'student_document': '12345678Z', 'study_id': self.study.id, **vals,
        })
        certificate._ems_set_values({'school_year': '2025-2026', **(details or {})})
        certificate._ems_submit()
        return certificate

    def _value(self, certificate, key):
        return certificate.value_ids.filtered(lambda line: line.field_id.key == key)

    def _complete_training(self, certificate, user=None):
        """The details the first step requires, written by its holder."""
        for key, vals in (('company', {'value_company_id': self.company.id}), ('start', {'value_date': '2026-03-01'}),
                          ('end', {'value_date': '2026-06-15'}), ('hours', {'value_number': 400}),
                          ('agreement', {'value_char': '2026178505'})):
            self._value(certificate, key).with_user(user or self.coordinator).write(vals)

    def _form(self, **post):
        """A posted request form: the common details, and the type's by key (input field_<id>)."""
        values = {'student_name': 'Former Student', 'student_document': 'X1234567L', 'study_id': str(self.study.id)}
        for key, value in post.items():
            if key in self.type_fields:
                values[f'field_{self.type_fields[key].id}'] = value
            elif key == 'company_vat':
                values[f"field_{self.type_fields['company'].id}_vat"] = value
            else:
                values[key] = value
        return values

    def _attach(self, certificate, document, user=None, name='a.pdf', raw=None, mimetype='application/pdf'):
        """Attach a file to one of the request's required documents, as `user` (default: superuser)."""
        line = certificate.document_ids.filtered(lambda line: line.type_document_id == document)
        attachment = self.env['ir.attachment'].create({
            'name': name, 'raw': raw or one_page_pdf(), 'mimetype': mimetype,
            'res_model': 'ems.certificate.document', 'res_id': line.id,
        })
        line.with_user(user or self.env.user).write({'attachment_ids': [(4, attachment.id)]})
        return attachment

    def _attach_required(self, certificate):
        for document in (self.agreement_document, self.report_document):
            self._attach(certificate, document)

    # --- the circuit -----------------------------------------------------------

    def test_full_circuit(self):
        sent = capture_template_emails(self)
        certificate = self._submitted()
        self.assertEqual((certificate.state, certificate.step_id), ('in_progress', self.steps[0]))
        self.assertFalse(certificate.name, "The number is given when the certificate is issued.")
        self.assertIn(self.coordinator, certificate.activity_ids.user_id, "The first step's holder gets the task.")

        # The coordinator cannot hand it over without the details their step requires; a company the
        # applicant only wrote does not count until its contact is linked.
        self._value(certificate, 'company').write({'value_char': 'Written SL'})
        with self.assertRaisesRegex(UserError, 'Company, From, To, Hours'):
            certificate.with_user(self.coordinator).action_done_step()
        self.assertTrue(self._value(certificate, 'hours').is_pending)
        self.assertFalse(self._value(certificate, 'agreement').is_pending, "Never required.")
        self._complete_training(certificate)
        self.assertFalse(certificate.value_ids.filtered('is_pending'))
        certificate.with_user(self.coordinator).action_done_step()
        self.assertEqual(certificate.step_id, self.steps[1])
        self.assertEqual(certificate.activity_ids.user_id, self.secretary, "The previous task closes.")

        # The secretary cannot issue it without the required documents. Anyone attaches the
        # agreement; only the first step's position the training report.
        self.assertEqual(certificate.document_ids.type_document_id, self.agreement_document | self.report_document)
        with self.assertRaises(UserError):
            certificate.with_user(self.secretary).action_done_step()
        self._attach(certificate, self.agreement_document, self.secretary, 'agreement.pdf', one_page_pdf('gray'))
        self._attach(certificate, self.agreement_document, self.secretary, 'page2.png', png_image(), 'image/png')
        with self.assertRaises(UserError):
            certificate.with_user(self.secretary).action_done_step()
        with self.assertRaises(AccessError):
            self._attach(certificate, self.report_document, self.secretary, 'report.pdf')
        with self.assertRaises(UserError):
            certificate.document_ids[:1].with_user(self.secretary).write({'type_document_id': self.report_document.id})
        self._attach(certificate, self.report_document, self.coordinator, 'report.pdf')
        # Optional documentation, never added to the certificate.
        certificate.with_user(self.secretary).other_attachment_ids = [(0, 0, {
            'name': 'note.pdf', 'raw': one_page_pdf(), 'mimetype': 'application/pdf'})]
        certificate.with_user(self.secretary).action_done_step()
        course = self.env['ems.course'].search([('is_current', '=', True)], limit=1)
        self.assertTrue(certificate.name.startswith(f'CERT-{course.start}-'))
        self.assertEqual(certificate.course_id, course)

        certificate.with_user(self.director).action_done_step()
        self.assertEqual(certificate.state, 'issued')
        self.assertFalse(certificate.activity_ids)
        self.assertEqual(certificate.stamp_ids.mapped('user_id'), self.coordinator | self.secretary | self.director)
        # The certificate, then the agreement's PDF page and the image as one more page: neither the
        # training report (not appended) nor the optional documentation.
        reader = PdfFileReader(io.BytesIO(certificate.certificate_pdf_id.raw))
        self.assertEqual(len(reader.pages), 3)
        self.assertIn(('ems.email_template_certificate_issued', certificate.id, None), sent())

    def test_only_the_step_holder_or_the_administrator_acts(self):
        certificate = self._submitted()
        self._complete_training(certificate)
        for user in (self.secretary, self.director):
            with self.subTest(user=user.name), self.assertRaises(AccessError):
                certificate.with_user(user).action_done_step()
        admin = create_role_user(self, 'academic_admin', 'test_tcrt_admin')
        certificate.with_user(admin).action_done_step()
        self.assertEqual(certificate.step_id, self.steps[1])

    def test_step_with_several_positions(self):
        """Holders of any of the step's positions get its task and may do it; the first to do it
        closes everybody's task. The new secretary technician position brings the secretariat group."""
        technician = create_role_user(self, 'teacher', 'test_tcrt_technician', name='TCRT Technician')
        technician.groups_id = [(3, self.env.ref('ems.group_teacher').id)]
        role = self.env.ref('ems.role_secretary_technician')
        role.employee_ids = [(4, create_role_employee(self, technician, employee_type='asp').id)]
        self.assertTrue(technician.has_group('ems.group_secretary'))
        self.steps[0].role_ids = [(4, role.id)]
        with self.assertRaises(ValidationError):
            self.steps[0].role_ids = [(5, 0, 0)]

        certificate = self._submitted()
        note = certificate.message_ids.filtered(lambda message: 'Request submitted' in (message.body or ''))
        self.assertIn(self.roles['complete'].name, note.body)
        self.assertIn(role.name, note.body)
        self.assertEqual(certificate.activity_ids.user_id, self.coordinator | technician)
        self.assertTrue(certificate.with_user(technician).is_pending_for_me)
        self.assertIn(certificate, self.env['ems.certificate'].with_user(technician).search(
            [('is_pending_for_me', '=', True)]))
        self._complete_training(certificate)
        certificate.with_user(technician).action_done_step()
        self.assertEqual(certificate.step_id, self.steps[1])
        self.assertEqual(certificate.activity_ids.user_id, self.secretary, "Both tasks of the first step close.")

    def test_issuer_issues_it_now_skipping_earlier_steps(self):
        certificate = self._submitted()
        self.assertTrue(certificate.with_user(self.secretary).can_issue_now)
        for user in (self.coordinator, self.director):
            with self.subTest(user=user.name):
                self.assertFalse(certificate.with_user(user).can_issue_now)
                with self.assertRaises(AccessError):
                    certificate.with_user(user).action_issue_now()
        # Every mandatory detail is checked as when issuing: the details the earlier steps require,
        # then every required document; nothing changes while one is missing.
        with self.assertRaisesRegex(UserError, 'certificate details'):
            certificate.with_user(self.secretary).action_issue_now()
        self._complete_training(certificate)
        with self.assertRaisesRegex(UserError, 'required documentation'):
            certificate.with_user(self.secretary).action_issue_now()
        self.assertEqual(certificate.step_id, self.steps[0])
        self._attach_required(certificate)
        certificate.with_user(self.secretary).action_issue_now()
        self.assertEqual(certificate.step_id, self.steps[2])
        self.assertTrue(certificate.name)
        self.assertEqual(certificate.stamp_ids.mapped('action'), ['issue'], "No stamp for the skipped step.")
        self.assertEqual(certificate.activity_ids.user_id, self.director, "The coordinator's task is closed.")
        self.assertTrue(certificate.message_ids.filtered(lambda message: 'skipping: Complete' in message.body),
                        "A note names the skipped step.")
        self.assertFalse(certificate.with_user(self.secretary).can_issue_now, "Only before the issuing step.")
        certificate.with_user(self.director).action_done_step()
        self.assertEqual(certificate.state, 'issued')

    def test_issue_now_from_a_draft(self):
        """A request the secretariat registers with every detail goes straight to issuing."""
        certificate = self.env['ems.certificate'].create({
            'type_id': self.certificate_type.id, 'student_id': self.student.id, 'student_name': self.student.name,
            'student_document': '12345678Z', 'study_id': self.study.id,
        })
        certificate._ems_set_values({'school_year': '2025-2026'})
        self._complete_training(certificate, self.secretary)
        self._attach_required(certificate)
        admin = create_role_user(self, 'academic_admin', 'test_tcrt_admin_now')
        self.assertTrue(certificate.with_user(admin).can_issue_now)
        certificate.with_user(admin).action_issue_now()
        self.assertEqual((certificate.state, certificate.step_id), ('in_progress', self.steps[2]))
        self.assertTrue(certificate.submission_date)
        self.assertNotIn(self.coordinator, certificate.activity_ids.user_id)

    def test_return_undoes_the_previous_stamp(self):
        certificate = self._submitted()
        self._complete_training(certificate)
        certificate.with_user(self.coordinator).action_done_step()
        with self.assertRaises(UserError):
            certificate.with_user(self.coordinator)._ems_return("Too early")
        self.env['ems.certificate.wizard'].with_user(self.secretary).create({
            'certificate_id': certificate.id, 'mode': 'return', 'message': 'The hours are wrong',
        }).action_confirm()
        self.assertEqual(certificate.step_id, self.steps[0])
        self.assertEqual(certificate.return_reason, 'The hours are wrong')
        self.assertFalse(certificate.stamp_ids)
        self.assertIn(self.coordinator, certificate.activity_ids.user_id)

    def test_documentation_round_trip(self):
        sent = capture_template_emails(self)
        certificate = self._submitted()
        self.env['ems.certificate.wizard'].with_user(self.coordinator).create({
            'certificate_id': certificate.id, 'mode': 'info', 'message': 'Attach the agreement',
        }).action_confirm()
        self.assertEqual(certificate.state, 'documentation')
        self.assertFalse(certificate.activity_ids)
        self.assertIn(('ems.email_template_certificate_info_request', certificate.id, None), sent())
        certificate.sudo()._ems_portal_answer("Here it is", {})
        self.assertEqual((certificate.state, certificate.step_id), ('in_progress', self.steps[0]))
        self.assertIn(self.coordinator, certificate.activity_ids.user_id)

        # The documentation arrived some other way: the secretariat (or the step's holder) says
        # so and the request goes back to its step; nobody else can.
        self.env['ems.certificate.wizard'].with_user(self.coordinator).create({
            'certificate_id': certificate.id, 'mode': 'info', 'message': 'The signed copy',
        }).action_confirm()
        with self.assertRaises(AccessError):
            certificate.with_user(self.director).action_documentation_received()
        certificate.with_user(self.secretary).action_documentation_received()
        self.assertEqual((certificate.state, certificate.step_id), ('in_progress', self.steps[0]))
        self.assertIn(self.coordinator, certificate.activity_ids.user_id)

    def test_reject_and_cancel(self):
        sent = capture_template_emails(self)
        certificate = self._submitted()
        self.env['ems.certificate.wizard'].with_user(self.secretary).create({
            'certificate_id': certificate.id, 'mode': 'reject', 'message': 'No training on record',
        }).action_confirm()
        self.assertEqual(certificate.state, 'rejected')
        self.assertIn(('ems.email_template_certificate_rejected', certificate.id, None), sent())
        with self.assertRaises(UserError):
            self._value(certificate, 'hours').with_user(self.secretary).write({'value_number': 10})

        # Cancellable until issued: afterwards it has a number of the registry.
        other = self._submitted()
        self._complete_training(other)
        other.with_user(self.coordinator).action_done_step()
        self._attach_required(other)
        other.with_user(self.secretary).action_done_step()
        with self.assertRaises(UserError):
            other.with_user(self.secretary)._ems_cancel("Duplicate")

        # Cancelled before being issued, the secretariat reopens it on the first step.
        third = self._submitted()
        self.env['ems.certificate.wizard'].with_user(self.secretary).create({
            'certificate_id': third.id, 'mode': 'cancel', 'message': 'Duplicate',
        }).action_confirm()
        self.assertEqual((third.state, third.cancel_reason, third.activity_ids), ('cancelled', 'Duplicate', self.env['mail.activity']))
        with self.assertRaises(AccessError):
            third.with_user(self.coordinator).action_reopen()
        third.with_user(self.secretary).action_reopen()
        self.assertEqual((third.state, third.step_id, third.cancel_reason), ('in_progress', self.steps[0], False))
        self.assertIn(self.coordinator, third.activity_ids.user_id)

    def test_former_student_form(self):
        """The secretariat registers a former student's request and sends the form by link."""
        sent = capture_template_emails(self)
        certificate = self.env['ems.certificate'].with_user(self.secretary).create({
            'type_id': self.certificate_type.id, 'student_id': self.student.id,
        })
        self.assertEqual((certificate.state, certificate.origin), ('draft', 'secretariat'))
        with self.assertRaises(UserError):
            certificate.with_user(self.secretary).action_send_form()
        certificate.with_user(self.secretary).applicant_email = 'former.student@example.com'
        certificate.with_user(self.secretary).action_send_form()
        self.assertIn(('ems.email_template_certificate_form', certificate.id, None), sent())
        self.assertIn('access_token=', certificate._ems_form_url())
        self.assertEqual(certificate._ems_recipients(), [('former.student@example.com', self.student.lang)])

        _values, _details, missing = certificate._ems_parse_portal_form({'student_name': 'Former Student'})
        self.assertEqual(missing, ['Identity document', 'Study', 'School year'],
                         "The common details and the type's required ones are mandatory.")
        values, details, missing = certificate._ems_parse_portal_form(self._form(
            school_year='2019-2020', hours='many', start='not a date', company='Written SL', company_vat='B1'))
        self.assertFalse(missing)
        self.assertEqual((details['hours'], details['start']), ({'value_number': 0}, {'value_date': False}))
        self.assertEqual(details['company'], {'value_char': 'Written SL', 'value_vat': 'B1'})
        certificate.sudo()._ems_portal_fill(values, details, {})
        self.assertEqual((certificate.state, certificate.step_id), ('in_progress', self.steps[0]))
        self.assertEqual(self._value(certificate, 'school_year').value_char, '2019-2020')

    def test_former_student_not_in_ems(self):
        """A former student who is not in EMS: no contact, only their email; the form, the circuit
        and the certificate work from the details they write."""
        sent = capture_template_emails(self)
        # Their full name and email are enough to open it; without either, it cannot be opened.
        for vals in ({'student_name': 'Unknown Former'}, {'applicant_email': 'unknown.former@example.com'}):
            with self.subTest(vals=vals), self.assertRaises(ValidationError):
                self.env['ems.certificate'].with_user(self.secretary).create({'type_id': self.certificate_type.id, **vals})
        certificate = self.env['ems.certificate'].with_user(self.secretary).create({
            'type_id': self.certificate_type.id, 'student_name': 'Unknown Former',
            'applicant_email': 'unknown.former@example.com',
        })
        self.assertFalse(certificate.student_id)
        certificate.with_user(self.secretary).action_send_form()
        self.assertIn(('ems.email_template_certificate_form', certificate.id, None), sent())
        self.assertEqual(certificate._ems_recipients(), [('unknown.former@example.com', self.env.company.ems_lang)])
        values, details, _missing = certificate._ems_parse_portal_form(self._form(
            student_name='Unknown Former', student_document='Y7654321G', school_year='2015-2016'))
        certificate.sudo()._ems_portal_fill(values, details, {})
        self.assertIn('Unknown Former', certificate.display_name)
        self.assertIn('Unknown Former', certificate.activity_ids.summary)
        self._complete_training(certificate)
        certificate.with_user(self.coordinator).action_done_step()
        self._attach_required(certificate)
        certificate.with_user(self.secretary).action_done_step()
        certificate.with_user(self.director).action_done_step()
        self.assertEqual(certificate.state, 'issued')
        self.assertIn(('ems.email_template_certificate_issued', certificate.id, None), sent())

    def test_send_form_with_every_detail_starts_the_circuit(self):
        """The secretariat wrote every mandatory detail: sending the form also hands the request to
        the first step, and the applicant may complete it until the centre changes or acts on it."""
        sent = capture_template_emails(self)
        certificate = self.env['ems.certificate'].with_user(self.secretary).create({
            'type_id': self.certificate_type.id, 'student_name': 'Complete Former', 'student_document': 'Z1234567R',
            'study_id': self.study.id, 'applicant_email': 'complete.former@example.com',
        })
        certificate._ems_set_values({'school_year': '2020-2021'})
        certificate.with_user(self.secretary).action_send_form()
        self.assertIn(('ems.email_template_certificate_form', certificate.id, None), sent())
        self.assertEqual((certificate.state, certificate.step_id), ('in_progress', self.steps[0]))
        self.assertIn(self.coordinator, certificate.activity_ids.user_id)
        self.assertTrue(certificate.applicant_form_open)

        values, details, _missing = certificate._ems_parse_portal_form(self._form(
            student_name='Complete Former', student_document='Z1234567R', school_year='2020-2021', hours='350',
            company='Written SL'))
        certificate.sudo()._ems_portal_fill(values, details, {})
        self.assertEqual((certificate.state, certificate.step_id, self._value(certificate, 'hours').value_number),
                         ('in_progress', self.steps[0], 350))
        self.assertTrue(certificate._ems_portal_can_edit())

        # The coordinator changes one of its details: the applicant's form closes.
        self._value(certificate, 'company').with_user(self.coordinator).write({'value_company_id': self.company.id})
        self.assertFalse(certificate.applicant_form_open)
        with self.assertRaises(UserError):
            certificate.sudo()._ems_portal_fill(values, details, {})

    def test_study_of_the_type_levels_only(self):
        _level, other_study, _group = create_level_study_group(self, 'TCRX')
        with self.assertRaises(ValidationError):
            self._submitted(study_id=other_study.id)
        values, _details, missing = self.env['ems.certificate']._ems_parse_portal_form(
            self._form(study_id=str(other_study.id), school_year='X'), self.certificate_type)
        self.assertFalse(values['study_id'])
        self.assertEqual(len(missing), 1, "A study outside the type's levels counts as not chosen.")

    def test_create_company_from_the_applicant(self):
        written = {'company': {'value_char': 'New Training Company', 'value_vat': 'B87654321'}}
        line = self._value(self._submitted(written), 'company')
        line.with_user(self.coordinator).action_create_company()
        company = line.value_company_id
        self.assertEqual((company.name, company.contact_type), ('New Training Company', 'company'))
        self.assertIn(self.env.ref('ems.partner_category_company'), company.category_id)
        # The same VAT number links the existing company instead of creating another one.
        again = self._value(self._submitted(written), 'company')
        again.with_user(self.coordinator).action_create_company()
        self.assertEqual(again.value_company_id, company)

    # --- records the staff see ------------------------------------------------

    def test_record_rules(self):
        certificate = self._submitted()
        Certificate = self.env['ems.certificate']
        for user in (self.coordinator, self.secretary, self.director):
            self.assertEqual(Certificate.with_user(user).search([('id', '=', certificate.id)]), certificate)
        self.assertFalse(Certificate.with_user(self.teacher).search([('id', '=', certificate.id)]),
                         "A teacher who holds no position of the circuit does not see it.")
        self.assertEqual(Certificate.with_user(self.coordinator).search([('is_pending_for_me', '=', True)]), certificate)
        self.assertFalse(Certificate.with_user(self.director).search([('is_pending_for_me', '=', True),
                                                                      ('id', '=', certificate.id)]))
        # Rejecting and cancelling: the secretariat and whoever does the current step, nobody else.
        self.assertTrue(certificate.with_user(self.secretary).can_manage)
        self.assertTrue(certificate.with_user(self.coordinator).can_manage)
        self.assertFalse(certificate.with_user(self.director).can_manage)
        with self.assertRaises(AccessError):
            certificate.with_user(self.director)._ems_reject("Not mine to reject")

    def test_vet_coordinator_edits_collaborating_companies_only(self):
        self.company.with_user(self.coordinator).write({'phone': '930000000'})
        self.assertTrue(self.company.with_user(self.coordinator).can_edit_company)
        with self.assertRaises(AccessError):
            self.student.with_user(self.coordinator).write({'phone': '930000000'})

    # --- configuration --------------------------------------------------------

    def test_documents_follow_the_type(self):
        """Without Required attached documentation ticked the type requires nothing, and it cannot
        be ticked with no document listed."""
        self.assertFalse(self.certificate_type.copy({'requires_documents': False})._ems_required_documents())
        with self.assertRaises(ValidationError):
            self.env['ems.certificate.type'].create({
                'name': 'TCRT no documents', 'requires_documents': True,
                'step_ids': [(0, 0, {'name': 'Issue', 'role_ids': [(6, 0, self.roles['issue'].ids)], 'action': 'issue'})],
            })
        self.assertEqual(self._submitted().document_ids.mapped('uploaders'), ['Anyone', 'TCRT complete position'])

    def test_circuit_constraints(self):
        with self.assertRaises(ValidationError):
            self.certificate_type.write({'step_ids': [(2, self.steps[1].id)]})
        with self.assertRaises(ValidationError):
            self.certificate_type.write({'step_ids': [(1, self.steps[2].id, {'sequence': 5})]})

    def test_portal_visibility(self):
        self.assertTrue(self.student._ems_certificate_portal_visible())
        self.assertEqual(self.env['ems.certificate']._ems_portal_types(self.student), self.certificate_type)
        self.certificate_type.level_ids = False
        self.assertFalse(self.student._ems_certificate_portal_visible())

    def test_report_content(self):
        """The certificate's text, rendered for real (HTML under test)."""
        certificate = self._submitted()
        self._complete_training(certificate)
        certificate.with_user(self.coordinator).action_done_step()
        self._attach_required(certificate)
        certificate.with_user(self.secretary).action_done_step()
        html = self.env['ir.actions.report'].with_context(lang='en_US')._render_qweb_html(
            'ems.action_report_certificate', certificate.ids)[0].decode()
        for text in (certificate.name, self.student.name, '12345678Z', self.company.name, 'B12345678', '400',
                     '2026178505', '01/03/2026', 'registered with number', self.secretary.name):
            self.assertIn(text, html)
        footer = html[html.index('o_ems_footer_note'):]
        self.assertIn('PC3.02.01 Model de certificat (EMS)', footer[:300], "the ISO document goes in the layout's footer")
        self.assertIn('Revisió: 17/11/2026', footer[:300])

    # --- the type's details and text (issue #851) ------------------------------

    def test_render_text(self):
        """Every {key} in bold and escaped; a [part] only when its details have a value; a blank
        line, a new paragraph."""
        render = self.env['ems.certificate']._ems_render_text
        paragraphs = render("That {name} did {hours} hours[ at {company}].\n\nSource[ number {agreement}].",
                            {'name': '<Ann>', 'hours': '40', 'company': False, 'agreement': '7'})
        self.assertEqual([str(paragraph) for paragraph in paragraphs], [
            'That <strong>&lt;Ann&gt;</strong> did <strong>40</strong> hours.',
            'Source number <strong>7</strong>.',
        ])

    def test_text_checks_its_keys(self):
        certificate_type = self.certificate_type
        for text in ("Unknown {grade}.", "Unbalanced [part.", "Nested [a [b] c]."):
            with self.subTest(text=text), self.assertRaises(ValidationError), self.env.cr.savepoint():
                certificate_type.certificate_text = text
        certificate_type.certificate_text = "{name}, {document}, {study}, {company_vat}."
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            certificate_type.write({'field_ids': [(2, self.type_fields['company'].id)]})
        self.assertIn('<code>{company_vat}</code>', certificate_type.placeholder_help)

    def test_detail_keys(self):
        Field = self.env['ems.certificate.type.field']
        for key in ('name', 'Hours', '2nd', 'total_vat', 'hours'):
            with self.subTest(key=key), self.assertRaises(Exception), self.env.cr.savepoint():
                Field.create({'type_id': self.certificate_type.id, 'name': 'X', 'key': key})

    def test_renamed_key_follows_in_every_language(self):
        """Renaming a key from the form in one language rewrites it in the text of every language
        (the company's _vat key included), so the save is not refused for the others."""
        certificate_type = self.certificate_type
        certificate_type.certificate_text = "In {company}[, VAT {company_vat}], {hours} hours."
        certificate_type.with_context(lang='ca_ES').certificate_text = "A {company}[, NIF {company_vat}], {hours} hores."
        certificate_type.with_context(lang='ca_ES').write({'field_ids': [
            (1, self.type_fields['company'].id, {'key': 'empresa'}),
            (1, self.type_fields['hours'].id, {'key': 'hores'}),
        ]})
        self.assertEqual(certificate_type.with_context(lang='en_US').certificate_text,
                         "In {empresa}[, VAT {empresa_vat}], {hores} hours.")
        self.assertEqual(certificate_type.with_context(lang='ca_ES').certificate_text,
                         "A {empresa}[, NIF {empresa_vat}], {hores} hores.")

    def test_new_detail_reaches_open_requests(self):
        """A detail added to a type appears on its open requests, not on the closed ones."""
        open_request = self._submitted()
        closed = self._submitted()
        closed.sudo()._ems_cancel()
        field = self.env['ems.certificate.type.field'].create({
            'type_id': self.certificate_type.id, 'name': 'Tutor', 'key': 'tutor', 'field_type': 'char',
        })
        self.assertIn(field, open_request.value_ids.field_id)
        self.assertNotIn(field, closed.value_ids.field_id)

    def test_another_type_with_details_of_its_own(self):
        """Nothing is specific to FCT: a type asking for a long text and a yes/no prints them."""
        certificate_type = create_other_type(self, 'TCRT Attendance', [
            (0, 0, {'sequence': 10, 'name': 'Reason', 'key': 'reason', 'field_type': 'text',
                    'applicant_input': 'required'}),
            (0, 0, {'sequence': 20, 'name': 'Full time', 'key': 'full_time', 'field_type': 'boolean'}),
        ], "That {name} needs it for: {reason}. Full time: {full_time}.")
        certificate = self.env['ems.certificate'].create({
            'type_id': certificate_type.id, 'student_id': self.student.id, 'student_name': self.student.name,
            'student_document': '12345678Z', 'study_id': self.study.id,
        })
        self.assertEqual(certificate.value_ids.field_id, certificate_type.field_ids)
        with self.assertRaisesRegex(UserError, 'Reason'):
            certificate._ems_submit()
        values, details, missing = certificate._ems_parse_portal_form(self._form(**{
            f'field_{certificate_type.field_ids[0].id}': 'A scholarship',
            f'field_{certificate_type.field_ids[1].id}': 'on'}))
        self.assertFalse(missing)
        certificate.sudo()._ems_portal_fill(values, details, {})
        paragraphs = certificate._ems_render_text(certificate_type.certificate_text, certificate._ems_placeholder_values())
        self.assertIn('<strong>A scholarship</strong>', str(paragraphs[0]))
        self.assertIn('<strong>Yes</strong>', str(paragraphs[0]))

    def test_type_change_in_draft_follows_the_details(self):
        certificate = self.env['ems.certificate'].create({
            'type_id': self.certificate_type.id, 'student_name': 'X', 'applicant_email': 'x@example.com'})
        other = create_other_type(self, 'TCRT Other', [(0, 0, {'name': 'Reason', 'key': 'reason'})], "{reason}")
        certificate.type_id = other
        self.assertEqual(certificate.value_ids.field_id, other.field_ids)
        self.assertFalse(certificate.document_ids, "Nor any document of the previous type.")

    def test_detail_values_input_display_and_pending(self):
        """A wrong number or date from the form is left out; each data type is displayed as such;
        what the current step requires is pending until filled in; a closed request is read-only."""
        values, details, missing = self.env['ems.certificate']._ems_parse_portal_form(
            self._form(hours='forty', start='31/02/2026', end='2026-06-15', company='ACME', company_vat='B1'),
            self.certificate_type)
        self.assertEqual((details['hours'], details['start'], details['end']),
                         ({'value_number': 0}, {'value_date': False}, {'value_date': fields.Date.to_date('2026-06-15')}))
        self.assertEqual(details['company'], {'value_char': 'ACME', 'value_vat': 'B1'})
        self.assertIn('School year', missing)
        certificate = self._submitted()
        hours, start, company = (self._value(certificate, key) for key in ('hours', 'start', 'company'))
        self.assertTrue(hours.is_pending and start.is_pending and company.is_pending)
        self.assertFalse(self._value(certificate, 'agreement').is_pending, "Required by no step.")
        self._complete_training(certificate)
        self.assertFalse((hours | start | company).filtered('is_pending'))
        self.assertEqual((hours.with_context(lang='en_US').display_value, start.with_context(lang='en_US').display_value,
                          company.display_value), ('400', '03/01/2026', self.company.name))
        # Numbers take decimals: written with a comma or a point, shown with the language's separator.
        detail = self.type_fields['hours']
        for raw, expected in (('7,45', 7.45), ('7.5', 7.5), ('-3', 0), ('nan', 0), ('inf', 0)):
            with self.subTest(raw=raw):
                self.assertEqual(self.env['ems.certificate.value']._ems_parse_input(detail, {f'field_{detail.id}': raw}),
                                 {'value_number': expected})
        hours.value_number = 7.45
        self.assertEqual((hours.with_context(lang='ca_ES').display_value, hours.with_context(lang='en_US').display_value),
                         ('7,45', '7.45'))
        certificate.sudo()._ems_cancel()
        with self.assertRaises(UserError):
            hours.with_user(self.coordinator).write({'value_number': 1})

    def test_copy_keeps_its_details_on_its_own_steps(self):
        copy = self.certificate_type.copy({'name': 'TCRT Copy'})
        self.assertEqual(copy.field_ids.mapped('key'), self.certificate_type.field_ids.mapped('key'))
        self.assertEqual(copy.field_ids.required_step_id, copy.step_ids.sorted('sequence')[0])
        self.assertEqual(copy.certificate_text, self.certificate_type.certificate_text)

