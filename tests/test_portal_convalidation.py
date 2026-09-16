from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email, next_student_id
from .test_convalidation import create_convalidation_fixtures

PDF = b'%PDF-1.4 test certificate'


def create_portal_convalidation_fixtures(cls):
    """create_convalidation_fixtures() plus a minor student sharing a family contact with the adult
    one, a student of a study that does not allow convalidations, and portal users for the adult
    student, the family and that other student (login doubles as password)."""
    create_convalidation_fixtures(cls)
    cls.minor, cls.family = cls.env['res.partner'].create([
        {'name': 'Convalidation Portal Minor', 'contact_type': 'student', 'student_id': next_student_id(),
         'main_group_id': cls.group.id, 'birth_date': '2020-01-01'},
        {'name': 'Convalidation Portal Family', 'contact_type': 'family',
         'email': 'convalidation.portal.family@example.com'},
    ])
    cls.env['res.partner.relation'].create({
        'left_partner_id': cls.family.id, 'type_id': cls.env.ref('ems.relation_type_father').id,
        'right_partner_id': cls.minor.id,
    })
    level = cls.env['ems.level'].create({'acronym': 'TCVE', 'name': 'Test Level (No Convalidation)'})
    study = cls.env['ems.study'].create({
        'code': 'TCVE001', 'acronym': 'TCVE', 'name': 'Test Study (No Convalidation)',
        'date': '2026-01-01', 'level_id': level.id,
    })
    group = cls.env['ems.group'].create({'course': 1, 'acronym': 'TCVE', 'level_id': level.id, 'study_id': study.id})
    cls.other_student = cls.env['res.partner'].create({
        'name': 'Convalidation Portal Other', 'contact_type': 'student', 'student_id': next_student_id(),
        'main_group_id': group.id,
    })
    cls.student_user, cls.family_user, cls.other_user = cls.env['res.users'].with_context(
        no_reset_password=True).create([{
            'name': partner.name, 'login': login, 'password': login, 'partner_id': partner.id,
            'lang': 'en_US', 'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        } for partner, login in (
            (cls.student, 'test_portal_convalidation_student'),
            (cls.family, 'test_portal_convalidation_family'),
            (cls.other_student, 'test_portal_convalidation_other'),
        )])


@tagged('post_install', '-at_install')
class TestPortalConvalidation(HttpCase):
    """Issue #276 - the portal's Convalidations page (/my/convalidaciones): listing, submitting and
    cancelling requests, always for the student the portal user speaks for."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_convalidation_fixtures(cls)

    def _login(self, user):
        self.authenticate(user.login, user.login)

    def _submit(self, subjects, basis='prior_studies', with_file=True, **extra):
        data = {
            'csrf_token': Request.csrf_token(self),
            'subject_ids': [str(subject.id) for subject in subjects],
            'basis': basis,
            'student_notes': 'I passed these in SMX',
            **extra,
        }
        files = [('documents', ('certificate.pdf', PDF, 'application/pdf'))] if with_file else None
        return self.url_open('/my/convalidaciones/submit', data=data, files=files)

    def _requests(self, student):
        return self.env['ems.convalidation'].search([('student_id', '=', student.id)])

    def test_page_lists_the_requestable_subjects(self):
        self._login(self.student_user)
        response = self.url_open('/my/convalidaciones')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.subject.name, response.text)
        self.assertIn(self.other_subject.name, response.text)
        self.assertNotIn(self.tutorship.name, response.text)

    def test_student_submits_a_request(self):
        self._login(self.student_user)
        response = self._submit(self.subject)
        self.assertEqual(response.status_code, 200)
        self.assertIn('submitted=1', response.url)
        request = self._requests(self.student)
        self.assertEqual(len(request), 1)
        self.assertEqual(request.line_ids.subject_id, self.subject)
        self.assertEqual(request.study_id, self.study)
        self.assertEqual(request.requester_id, self.student)
        self.assertEqual(request.student_notes, 'I passed these in SMX')
        self.assertEqual(request.attachment_ids.mapped('name'), ['certificate.pdf'])
        self.assertEqual(request.attachment_ids.res_id, request.id)
        # The page now shows it, and the subject is no longer offered.
        page = self.url_open('/my/convalidaciones').text
        self.assertIn('o_ems_convalidation_request', page)
        self.assertNotIn(f'value="{self.subject.id}"', page)

    def test_foreign_and_tutorship_subjects_are_ignored(self):
        foreign = self.env['ems.subject'].create({'code': 'TCVP01', 'acronym': 'TCVP', 'name': 'Foreign'})
        self._login(self.student_user)
        self._submit(self.other_subject | foreign | self.tutorship)
        self.assertEqual(self._requests(self.student).line_ids.subject_id, self.other_subject)

    def test_nothing_is_created_without_subjects(self):
        self._login(self.student_user)
        response = self._submit(self.env['ems.subject'])
        self.assertIn('error=no_subjects', response.url)
        self.assertFalse(self._requests(self.student))

    def test_nothing_is_created_without_documents(self):
        self._login(self.student_user)
        response = self._submit(self.subject, with_file=False)
        self.assertIn('error=no_documents', response.url)
        self.assertFalse(self._requests(self.student))

    def test_nothing_is_created_with_an_unknown_basis(self):
        self._login(self.student_user)
        response = self._submit(self.subject, basis='bribe')
        self.assertIn('error=no_basis', response.url)
        self.assertFalse(self._requests(self.student))

    def test_family_submits_for_the_selected_child(self):
        self._login(self.family_user)
        page = self.url_open('/my/convalidaciones').text
        self.assertIn(self.minor.name, page)
        self._submit(self.subject)
        request = self._requests(self.minor)
        self.assertEqual(request.line_ids.subject_id, self.subject)
        self.assertEqual(request.requester_id, self.family)
        self.assertFalse(self._requests(self.family))

    def test_study_without_convalidations(self):
        self._login(self.other_user)
        page = self.url_open('/my/convalidaciones').text
        self.assertNotIn('o_ems_convalidation_new', page)
        response = self._submit(self.subject)
        self.assertIn('error=no_study', response.url)
        self.assertFalse(self._requests(self.other_student))

    def test_student_cancels_their_own_request(self):
        self._login(self.student_user)
        self._submit(self.subject)
        request = self._requests(self.student)
        self.url_open(f'/my/convalidaciones/cancel/{request.id}', data={'csrf_token': Request.csrf_token(self)})
        self.assertEqual(request.state, 'cancelled')

    def test_nobody_cancels_someone_elses_request(self):
        request = self.env['ems.convalidation'].create({
            'student_id': self.student.id, 'study_id': self.study.id, 'course_id': self.course.id,
            'line_ids': [(0, 0, {'subject_id': self.subject.id})],
        })
        self._login(self.other_user)
        self.url_open(f'/my/convalidaciones/cancel/{request.id}', data={'csrf_token': Request.csrf_token(self)})
        self.assertEqual(request.state, 'submitted')

    def test_resolved_requests_show_their_resolution(self):
        request = self.env['ems.convalidation'].create({
            'student_id': self.student.id, 'study_id': self.study.id, 'course_id': self.course.id,
            'resolution_notes': 'Bring the original certificate',
            'line_ids': [(0, 0, {'subject_id': self.subject.id, 'state': 'granted',
                                 'resolution_notes': 'Same module in SMX'})],
        })
        self.assertEqual(request.state, 'resolved')
        self._login(self.student_user)
        page = self.url_open('/my/convalidaciones').text
        self.assertIn('Same module in SMX', page)
        self.assertIn('Bring the original certificate', page)
        self.assertIn('Convalidated', page)
        self.assertNotIn(f'/my/convalidaciones/cancel/{request.id}', page)
