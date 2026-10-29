import base64

from odoo.tests import tagged, HttpCase

from .common import (
    create_head_of_studies_branch, create_level_study_group, create_role_employee, create_role_user, force_user_language_to_english,
    next_student_id,
)


@tagged('post_install', '-at_install')
class TestStudentDocumentTour(HttpCase):

    def test_student_document_review_and_embed_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # "0000 " prefix: res.partner's _order is "name", so this seeded student sorts
        # first on the list's very first page among the ~1000+ real students already in
        # this DB (see test_withdrawal_tour.py for the same pattern).
        student = self.env['res.partner'].create({
            'name': '0000 Tour Doc Student', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        self.env['ems.student.document'].create({
            'partner_id': student.id, 'doc_type': 'dni',
        })
        self.env['ems.student.document'].create({
            'partner_id': student.id, 'doc_type': 'passport',
        })
        # To observe these tours in a real browser during development:
        #   self.start_tour("/odoo", "ems_student_document_review", login="admin", watch=True)
        self.start_tour("/odoo", "ems_student_document_review", login="admin", step_delay=300)
        self.start_tour("/odoo", "ems_student_document_embed_view", login="admin", step_delay=300)

    def test_student_document_secretary_upload_tour(self):
        # Issue #717: logged in as the secretary's office, the role the change is for.
        secretary = create_role_user(self, 'secretary', 'test_secretary_document_upload_tour',
                                     name='Secretary Document Upload Tour', email='secretary.tour@example.com')
        student = self.env['res.partner'].create({
            'name': '0000 Secretary Upload Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        self.start_tour(f"/odoo/res.partner/{student.id}", "ems_student_document_secretary_upload",
                        login=secretary.login)
        document = student.document_ids
        self.assertEqual(document.status, 'approved')
        self.assertTrue(student.bank_ids.allow_out_payment)

    def test_student_document_tutor_credentials_tour(self):
        # Issue #478: logged in as the student's tutor, the role the change is for.
        tutor_user = create_role_user(self, 'tutor', 'test_tutor_document_tour', name='Tutor Document Tour')
        tutor = create_role_employee(self, tutor_user)
        __, __, group = create_level_study_group(self, 'TSDC', group={'tutor_id': tutor.id})
        student = self.env['res.partner'].create({
            'name': '0000 Tutor Doc Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
        })
        self.env['ems.student.document'].create({
            'partner_id': student.id, 'doc_type': 'google_credentials', 'status': 'approved',
            'doc_file': base64.b64encode(b'credentials-pdf'), 'doc_file_name': 'credentials.pdf',
        })
        self.env['ems.student.document'].create({
            'partner_id': student.id, 'doc_type': 'dni', 'status': 'approved',
        })
        self.start_tour(f"/odoo/res.partner/{student.id}", "ems_student_document_tutor_credentials",
                        login=tutor_user.login)

    def test_student_document_head_of_studies_tour(self):
        # Issue #654: Academic management > Student Documents as the Head of Studies above the
        # student's tutor: every document of their chain's students, read only.
        tutor_user = create_role_user(self, 'tutor', 'test_tutor_hos_document_tour', name='Tutor HoS Document Tour')
        tutor = create_role_employee(self, tutor_user)
        create_head_of_studies_branch(self, 'HSDC', tutor)
        __, __, group = create_level_study_group(self, 'HSDC', group={'tutor_id': tutor.id})
        __, __, other_group = create_level_study_group(self, 'HSDO')
        Partner = self.env['res.partner']
        student = Partner.create({
            'name': '0000 HoS Doc Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
        })
        other_student = Partner.create({
            'name': '0000 HoS Doc Tour Other Student', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': other_group.id,
        })
        # Pending, the list's default filter.
        for partner in (student, other_student):
            self.env['ems.student.document'].create({
                'partner_id': partner.id, 'doc_type': 'dni', 'status': 'pending',
                'doc_file': base64.b64encode(b'dni-pdf'), 'doc_file_name': 'dni.pdf',
            })
        self.start_tour("/odoo/action-ems.action_student_document", "ems_student_document_head_of_studies",
                        login=self.head_of_studies.login)

    def test_google_credentials_download_tour(self):
        # Issue #478: logged in as a tutor, the least-privileged role the action is bound for.
        tutor_user = create_role_user(self, 'tutor', 'test_tutor_gc_download_tour', name='Tutor GC Download Tour')
        tutor = create_role_employee(self, tutor_user)
        __, __, group = create_level_study_group(self, 'TGCD', group={'tutor_id': tutor.id})
        self.env['res.partner'].create({
            'name': '0000 GCT No Credentials', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
        })
        self.start_tour("/odoo", "ems_google_credentials_download", login=tutor_user.login)

    def test_google_credentials_download_form_tour(self):
        # On the student's own form the download is an Actions dropdown entry, offered only when
        # there are credentials the tutor may read.
        tutor_user = create_role_user(self, 'tutor', 'test_tutor_gc_download_form_tour',
                                      name='Tutor GC Download Form Tour')
        tutor = create_role_employee(self, tutor_user)
        __, __, group = create_level_study_group(self, 'TGCF', group={'tutor_id': tutor.id})
        with_credentials, without_credentials = self.env['res.partner'].create([{
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
        } for name in ('0000 GCT Credentials Form', '0000 GCT No Credentials Form')])
        self.env['ems.student.document'].create({
            'partner_id': with_credentials.id, 'doc_type': 'google_credentials', 'status': 'approved',
            'doc_file': base64.b64encode(b'credentials-pdf'), 'doc_file_name': 'credentials.pdf',
        })
        self.start_tour(f"/odoo/res.partner/{with_credentials.id}", "ems_google_credentials_download_form",
                        login=tutor_user.login)
        self.start_tour(f"/odoo/res.partner/{without_credentials.id}",
                        "ems_google_credentials_download_form_none", login=tutor_user.login)
