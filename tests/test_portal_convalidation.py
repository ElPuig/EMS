from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email, next_student_id
from .test_convalidation import close_convalidation_period, create_convalidation_fixtures

PDF = b'%PDF-1.4 test certificate'


def create_portal_convalidation_fixtures(cls):
    """create_convalidation_fixtures() plus a minor student with a family contact, an adult student
    of a study that does not allow convalidations, and portal users for the adult student, the
    family, that other student and the minor himself (login doubles as password)."""
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
        'main_group_id': group.id, 'birth_date': '2000-01-01',
    })
    cls.student_user, cls.family_user, cls.other_user, cls.minor_user = cls.env['res.users'].with_context(
        no_reset_password=True).create([{
            'name': partner.name, 'login': login, 'password': login, 'partner_id': partner.id,
            'lang': 'en_US', 'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        } for partner, login in (
            (cls.student, 'test_portal_convalidation_student'),
            (cls.family, 'test_portal_convalidation_family'),
            (cls.other_student, 'test_portal_convalidation_other'),
            (cls.minor, 'test_portal_convalidation_minor'),
        )])


@tagged('post_install', '-at_install')
class TestPortalConvalidation(HttpCase):
    """Issues #276 and #529 - the portal's Convalidations page (/my/convalidaciones): listing,
    submitting and cancelling requests, always for the student the portal user speaks for."""

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
        self.assertIn('id="convalidation_new_body" class="collapse "', response.text)

    def test_form_opens_after_a_validation_error(self):
        self._login(self.student_user)
        page = self.url_open('/my/convalidaciones?error=no_subjects').text
        self.assertIn('id="convalidation_new_body" class="collapse show"', page)

    def test_form_opens_on_request(self):
        self._login(self.student_user)
        page = self.url_open('/my/convalidaciones?new=1').text
        self.assertIn('id="convalidation_new_body" class="collapse show"', page)

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

    def test_documents_are_optional(self):
        """A student of this centre has nothing to attach: their record is looked up here. The
        Head of Studies asks for documents afterwards when they are actually needed."""
        self._login(self.student_user)
        response = self._submit(self.subject, with_file=False)
        self.assertIn('submitted=1', response.url)
        request = self._requests(self.student)
        self.assertEqual(request.line_ids.subject_id, self.subject)
        self.assertFalse(request.attachment_ids)

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
        self.assertEqual(request.state, 'pending')

    def test_communications_page_records_the_request_and_its_resolution(self):
        self._login(self.student_user)
        self._submit(self.subject)
        self._close(self._requests(self.student), granted=False)
        page = self.url_open('/my/comunicaciones').text
        self.assertIn('Convalidation request submitted', page)
        self.assertIn('Convalidation request resolved', page)
        self.assertIn(self.subject.name, page)

    def _close(self, request, granted=True):
        """Decide every subject, then take the request through the Director and the secretariat."""
        request = request.sudo()
        if granted:
            request.line_ids.action_grant()
        else:
            request.line_ids.write({'state': 'rejected', 'rejection_reason': 'Not equivalent'})
        request.action_propose()
        request.action_resolve()
        request.action_complete()

    def _resolved_request(self, grade=7):
        request = self.env['ems.convalidation'].create({
            'student_id': self.student.id, 'study_id': self.study.id, 'course_id': self.course.id,
            'resolution_notes': 'Bring the original certificate',
            'line_ids': [(0, 0, {'subject_id': self.subject.id, 'state': 'granted', 'grade': grade,
                                 'resolution_notes': 'Same module in SMX'})],
        })
        request.sudo().action_propose()
        request.sudo().action_resolve()
        return request

    def test_resolved_request_hides_the_grade_until_the_secretariat_completes(self):
        request = self._resolved_request()
        self.assertEqual(request.state, 'in_progress')
        self._login(self.student_user)
        page = self.url_open('/my/convalidaciones').text
        self.assertIn('The secretariat is now registering it in your record', page)
        self.assertNotIn('<th>Grade</th>', page)
        self.assertNotIn(f'/my/convalidaciones/cancel/{request.id}', page)

    def test_completed_requests_show_their_resolution_and_grade(self):
        request = self._resolved_request()
        request.sudo().action_complete()
        self._login(self.student_user)
        page = self.url_open('/my/convalidaciones').text
        self.assertIn('Same module in SMX', page)
        self.assertIn('Bring the original certificate', page)
        self.assertIn('Convalidated', page)
        self.assertIn('<th>Grade</th>', page)
        self.assertIn('<strong>7</strong>', page)
        self.assertNotIn(f'/my/convalidaciones/cancel/{request.id}', page)
        # The official resolution can be downloaded.
        self.assertIn(f'/my/convalidaciones/resolution/{request.id}', page)
        response = self.url_open(f'/my/convalidaciones/resolution/{request.id}')
        self.assertEqual(response.content, request.resolution_pdf_id.raw)

    def test_resolution_is_not_downloadable_before_it_is_registered(self):
        request = self._resolved_request()
        self._login(self.student_user)
        response = self.url_open(f'/my/convalidaciones/resolution/{request.id}')
        self.assertTrue(response.url.endswith('/my/convalidaciones'))
        self._login(self.other_user)
        request.sudo().action_complete()
        response = self.url_open(f'/my/convalidaciones/resolution/{request.id}')
        self.assertNotEqual(response.content, request.resolution_pdf_id.raw)

    def test_ministry_requests_cannot_be_cancelled_but_can_be_answered(self):
        self._login(self.student_user)
        self._submit(self.subject, with_file=False)
        request = self._requests(self.student)
        request.sudo().action_send_to_ministry()
        page = self.url_open('/my/convalidaciones').text
        self.assertIn('o_ems_convalidation_ministry', page)
        self.assertNotIn(f'/my/convalidaciones/cancel/{request.id}', page)
        self.assertIn(f'/my/convalidaciones/reply/{request.id}', page)
        self.url_open(f'/my/convalidaciones/cancel/{request.id}', data={'csrf_token': Request.csrf_token(self)})
        self.assertEqual(request.state, 'ministry')

    def test_student_answers_a_request_for_information(self):
        self._login(self.student_user)
        self._submit(self.subject, with_file=False)
        request = self._requests(self.student)
        self.env['ems.convalidation.info_wizard'].create({
            'convalidation_id': request.id, 'message': 'Attach the SMX certificate'}).action_send()
        page = self.url_open('/my/convalidaciones').text
        self.assertIn('o_ems_convalidation_info_request', page)
        self.assertIn('Attach the SMX certificate', page)
        response = self.url_open(f'/my/convalidaciones/reply/{request.id}', data={
            'csrf_token': Request.csrf_token(self), 'message': 'Here is the certificate',
        }, files=[('documents', ('smx.pdf', PDF, 'application/pdf'))])
        self.assertIn('replied=1', response.url)
        self.assertEqual(request.attachment_ids.mapped('name'), ['smx.pdf'])
        self.assertEqual(request.attachment_ids.res_id, request.id)
        self.assertTrue(request.message_ids.filtered(
            lambda message: 'Here is the certificate' in (message.body or '')))
        # It reaches the student's own Communications page, like every other message.
        self.assertIn('Documentation added by the applicant', self.url_open('/my/comunicaciones').text)

    def test_empty_answers_and_closed_requests_are_refused(self):
        self._login(self.student_user)
        self._submit(self.subject, with_file=False)
        request = self._requests(self.student)
        response = self.url_open(f'/my/convalidaciones/reply/{request.id}',
                                 data={'csrf_token': Request.csrf_token(self), 'message': '  '})
        self.assertIn('error=no_reply', response.url)
        request.sudo().line_ids.action_grant()
        request.sudo().action_propose()
        self.url_open(f'/my/convalidaciones/reply/{request.id}', data={
            'csrf_token': Request.csrf_token(self), 'message': 'Too late',
        }, files=[('documents', ('late.pdf', PDF, 'application/pdf'))])
        self.assertFalse(request.attachment_ids)

    def test_nobody_answers_someone_elses_request(self):
        request = self.env['ems.convalidation'].create({
            'student_id': self.student.id, 'study_id': self.study.id, 'course_id': self.course.id,
            'line_ids': [(0, 0, {'subject_id': self.subject.id})],
        })
        self._login(self.other_user)
        self.url_open(f'/my/convalidaciones/reply/{request.id}', data={
            'csrf_token': Request.csrf_token(self), 'message': 'Not mine',
        }, files=[('documents', ('other.pdf', PDF, 'application/pdf'))])
        self.assertFalse(request.attachment_ids)

    # --- Request period (the fixtures leave it open all year long) ---

    def _backend_request(self, student):
        return self.env['ems.convalidation'].create({
            'student_id': student.id, 'study_id': self.study.id, 'course_id': self.course.id,
            'line_ids': [(0, 0, {'subject_id': self.subject.id})],
        })

    def test_open_period_shows_when_it_closes(self):
        """In the centre's local time, whatever the visitor's own time zone (none here)."""
        self.env.company.partner_id.tz = 'Europe/Madrid'
        self.student_user.tz = False
        self._login(self.student_user)
        page = self.url_open('/my/convalidaciones').text
        self.assertIn('o_ems_convalidation_deadline', page)
        self.assertIn('31 December', page)
        self.assertIn('23:59', page)
        self.assertNotIn('o_ems_convalidation_closed', page)

    def test_closed_period_hides_the_form(self):
        close_convalidation_period(self.env)
        self._login(self.student_user)
        page = self.url_open('/my/convalidaciones').text
        self.assertIn('o_ems_convalidation_closed', page)
        self.assertNotIn('convalidation_new_body', page)

    def test_closed_period_refuses_submissions(self):
        close_convalidation_period(self.env)
        self._login(self.student_user)
        response = self._submit(self.subject)
        self.assertIn('error=closed', response.url)
        self.assertFalse(self._requests(self.student))

    def test_closed_period_still_allows_answering_and_cancelling(self):
        answered, cancelled = self._backend_request(self.student), self._backend_request(self.student)
        close_convalidation_period(self.env)
        self._login(self.student_user)
        page = self.url_open('/my/convalidaciones').text
        self.assertIn(f'/my/convalidaciones/reply/{answered.id}', page)
        response = self.url_open(f'/my/convalidaciones/reply/{answered.id}', data={
            'csrf_token': Request.csrf_token(self), 'message': 'Here is the certificate',
        }, files=[('documents', ('smx.pdf', PDF, 'application/pdf'))])
        self.assertIn('replied=1', response.url)
        self.assertEqual(answered.attachment_ids.mapped('name'), ['smx.pdf'])
        self.url_open(f'/my/convalidaciones/cancel/{cancelled.id}', data={'csrf_token': Request.csrf_token(self)})
        self.assertEqual(cancelled.state, 'cancelled')

    # --- Who files requests (issue #529): an adult student himself, and his family only when he
    # authorized sharing with it; always the family of a minor, never the minor himself ---

    def _assert_cannot_file(self, user, student):
        request = self._backend_request(student)
        self._login(user)
        page = self.url_open('/my/convalidaciones').text
        self.assertNotIn('convalidation_new_body', page)
        self.assertNotIn(f'/my/convalidaciones/cancel/{request.id}', page)
        self.assertNotIn(f'/my/convalidaciones/reply/{request.id}', page)
        self._submit(self.other_subject)
        self.assertEqual(self._requests(student), request)
        self.url_open(f'/my/convalidaciones/reply/{request.id}', data={
            'csrf_token': Request.csrf_token(self), 'message': 'Not allowed',
        }, files=[('documents', ('other.pdf', PDF, 'application/pdf'))])
        self.assertFalse(request.attachment_ids)
        self.url_open(f'/my/convalidaciones/cancel/{request.id}', data={'csrf_token': Request.csrf_token(self)})
        self.assertEqual(request.state, 'pending')
        return page

    def test_a_minor_follows_but_does_not_file_his_requests(self):
        """His family files them; he reads them from his own account."""
        page = self._assert_cannot_file(self.minor_user, self.minor)
        self.assertIn('o_ems_convalidation_family_files', page)
        self.assertIn(self.subject.name, page)

    def test_a_minor_without_family_cannot_have_requests_filed(self):
        """Not even the GEDAC applicant with no family on file, who acts for himself everywhere
        else: he is told to fill in his family's contact details first."""
        applicant = self.env['res.partner'].create({
            'name': 'Convalidation Portal GEDAC Minor', 'contact_type': 'applicant',
            'student_id': next_student_id(), 'birth_date': '2020-01-01', 'main_group_id': self.group.id,
        })
        self.assertTrue(applicant._ems_portal_can_act_for(applicant))
        self.assertFalse(applicant._ems_convalidation_can_request(applicant))
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': applicant.name, 'login': 'test_portal_convalidation_gedac',
            'password': 'test_portal_convalidation_gedac', 'partner_id': applicant.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        page = self._assert_cannot_file(user, applicant)
        self.assertIn('o_ems_convalidation_no_family', page)
        self.assertIn('href="/my/account"', page)

    def test_the_family_of_an_adult_student_needs_his_authorization(self):
        """Without it, the family no longer sees him on the portal at all
        (res.partner.get_portal_students): the page sends it back to the portal home."""
        self.minor.birth_date = '2000-01-01'
        self._login(self.family_user)
        self.assertTrue(self.url_open('/my/convalidaciones').url.endswith('/my/home'))
        self.assertFalse(self.family._ems_convalidation_can_request(self.minor))

    def test_the_family_of_an_adult_student_files_with_his_authorization(self):
        """He authorized sharing with his family: the family files requests for him, although
        the rest of the portal is view-only for it, and so can he."""
        self.minor.birth_date = '2000-01-01'
        # auth_share is a stored compute read from an accepted 'share' authorization.
        self.env.flush_all()
        self.env.cr.execute("UPDATE res_partner SET auth_share = TRUE WHERE id = %s", (self.minor.id,))
        self.minor.invalidate_recordset(['auth_share'])
        self.assertTrue(self.family._ems_portal_is_view_only())
        self._login(self.family_user)
        self._submit(self.subject)
        request = self._requests(self.minor)
        self.assertEqual(request.requester_id, self.family)
        self.assertIn('Convalidation request submitted', self.url_open('/my/comunicaciones').text)
        self.assertTrue(self.minor._ems_convalidation_can_request(self.minor))
