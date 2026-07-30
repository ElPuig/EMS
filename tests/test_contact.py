import base64
from datetime import date

from odoo.tests.common import TransactionCase


class TestContactLifecycle(TransactionCase):
    """Contact lifecycle categories: applicant -> student -> alumni/withdrawal."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cat_student = cls.env.ref('ems.partner_category_student')
        cls.cat_applicant = cls.env.ref('ems.partner_category_applicant')
        cls.cat_alumni = cls.env.ref('ems.partner_category_alumni')
        cls.cat_withdrawal = cls.env.ref('ems.partner_category_withdrawal')

        cls.level = cls.env['ems.level'].create({'acronym': 'LFC', 'name': 'Lifecycle Level'})
        cls.study = cls.env['ems.study'].create({
            'code': 'LFC001',
            'acronym': 'LFCS',
            'name': 'Lifecycle Study',
            'date': date.today(),
            'deprecated': False,
            'level_id': cls.level.id,
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1,
            'acronym': 'A',
            'level_id': cls.level.id,
            'study_id': cls.study.id,
        })
        cls.course = cls.env['ems.course'].create({'start': 2098, 'end': 2099})

    # --- authorization flags read the student's own enrollment ---------------

    def _incoming_course(self):
        """The course students are enrolling into. Only one may carry the flag, and
        this database already has one, so the existing holder is cleared first."""
        self.env['ems.course'].search([('is_enrollment_default', '=', True)]).write(
            {'is_enrollment_default': False})
        return self.env['ems.course'].create({
            'start': 2099, 'end': 2100, 'is_enrollment_default': True})

    def _auth_template(self, auth_type):
        return self.env['ems.authorization.template'].create({
            'name': 'LFC %s' % auth_type, 'auth_type': auth_type,
            'legal_text': '<p>text</p>'})

    def _enrolled(self, name, course, auth_type=None, status='yes', state='sale'):
        """A student holding an enrollment for 'course', with one authorization."""
        student = self.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'main_group_id': self.group.id})
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study.id,
            'ems_course_id': course.id, 'shift': 'morning'})
        order.state = state
        if auth_type:
            self.env['ems.authorization'].create({
                'enrollment_id': order.id,
                'template_id': self._auth_template(auth_type).id,
                'status': status})
        return student, order

    def test_auth_flags_read_the_enrollment_course_not_the_current_one(self):
        """During the summer the student's enrollment is already the incoming
        course while 'current' is still the outgoing one. Keying on 'current' left
        every signed authorization invisible: 122 of 122 SMX students after the
        first real transition."""
        incoming = self._incoming_course()
        self.env.company.current_course_id = self.course     # outgoing still current
        student, _order = self._enrolled('LFC Auth Incoming', incoming, 'image')
        self.assertTrue(student.auth_image)

    def test_auth_flags_survive_the_course_flip(self):
        """After the flip the enrollment default is cleared and the same course
        becomes current, so the fallback has to resolve to the very same order."""
        incoming = self._incoming_course()
        student, order = self._enrolled('LFC Auth Flip', incoming, 'trip')
        self.assertTrue(student.auth_trip)
        incoming.is_enrollment_default = False
        self.env.company.current_course_id = incoming
        student.invalidate_recordset(['auth_trip'])
        self.assertTrue(student.auth_trip)

    def test_auth_flags_prefer_the_running_course_over_the_one_being_enrolled(self):
        """Once the next year opens for enrolment halfway through this one, the flags
        must keep reading the year being taught — not a draft nobody has signed."""
        running = self.course
        self.env.company.current_course_id = running
        student, _running_order = self._enrolled('LFC Auth Running', running, 'image')
        self.assertTrue(student.auth_image)
        # The centre starts enrolling for the year after: a draft, nothing signed.
        future = self._incoming_course()
        self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study.id,
            'ems_course_id': future.id, 'shift': 'morning'})
        student.invalidate_recordset(['auth_image'])
        self.assertTrue(student.auth_image)

    def test_the_authorization_list_matches_the_flags(self):
        """The Secretary tab shows the list next to the badges: if they disagree the
        operator sees a green 'Yes' above an empty table, which is what happened —
        only the flags were fixed, the list kept filtering by the current course."""
        incoming = self._incoming_course()
        self.env.company.current_course_id = self.course     # outgoing still current
        student, order = self._enrolled('LFC Auth List', incoming, 'image')
        self.assertTrue(student.auth_image)
        self.assertEqual(student.ems_authorization_ids, order.ems_authorization_ids)

    def test_auth_flags_are_false_without_an_enrollment(self):
        student = self.env['res.partner'].create({
            'name': 'LFC Auth None', 'contact_type': 'student',
            'main_group_id': self.group.id})
        self.assertFalse(student.auth_image)
        self.assertFalse(student.auth_trip)

    def test_auth_flags_ignore_a_rejected_authorization(self):
        incoming = self._incoming_course()
        student, _o = self._enrolled('LFC Auth No', incoming, 'health', status='no')
        self.assertFalse(student.auth_healt)

    def test_auth_flags_recompute_when_the_authorization_is_accepted(self):
        """The value is stored, so the depends have to cover the whole chain."""
        incoming = self._incoming_course()
        student, order = self._enrolled('LFC Auth Later', incoming, 'share', status='pending')
        self.assertFalse(student.auth_share)
        # Staff may only change the status with the signed PDF attached (see
        # ems.authorization.write); the portal path writes both at once too.
        order.ems_authorization_ids.write({
            'status': 'yes', 'signed_document': base64.b64encode(b'signed')})
        self.assertTrue(student.auth_share)

    # --- creation of the new categories -------------------------------------

    def test_create_applicant(self):
        applicant = self.env['res.partner'].create({
            'name': 'New Applicant', 'contact_type': 'applicant'})
        self.assertEqual(applicant.contact_type, 'applicant')

    def test_create_alumni_and_withdrawal(self):
        alumni = self.env['res.partner'].create({
            'name': 'Old Alumni', 'contact_type': 'alumni'})
        withdrawal = self.env['res.partner'].create({
            'name': 'Dropout', 'contact_type': 'withdrawal'})
        self.assertEqual(alumni.contact_type, 'alumni')
        self.assertEqual(withdrawal.contact_type, 'withdrawal')

    def test_has_graduated_defaults_false(self):
        student = self.env['res.partner'].create({
            'name': 'Fresh Student', 'contact_type': 'student'})
        self.assertFalse(student.has_graduated)

    # --- category sync ------------------------------------------------------

    def test_sync_category_on_create(self):
        applicant = self.env['res.partner'].create({
            'name': 'Applicant Cat', 'contact_type': 'applicant'})
        self.assertIn(self.cat_applicant, applicant.category_id)
        # "student" doubles as the shared student-lifecycle marker.
        self.assertIn(self.cat_student, applicant.category_id)

    def test_sync_category_swaps_on_write(self):
        student = self.env['res.partner'].create({
            'name': 'Swap Student', 'contact_type': 'student'})
        self.assertIn(self.cat_student, student.category_id)
        student.write({'contact_type': 'alumni'})
        self.assertIn(self.cat_alumni, student.category_id)
        # The shared lifecycle marker survives the transition.
        self.assertIn(self.cat_student, student.category_id)

    # --- _ems_convert_to_ex_student -----------------------------------------

    def test_convert_to_ex_student_graduated_becomes_alumni(self):
        student = self.env['res.partner'].create({
            'name': 'Graduate', 'contact_type': 'student',
            'has_graduated': True, 'main_group_id': self.group.id})
        student._ems_convert_to_ex_student()
        self.assertEqual(student.contact_type, 'alumni')
        self.assertFalse(student.main_group_id)
        self.assertFalse(student.level_id)
        self.assertFalse(student.study_id)
        self.assertIn(self.cat_alumni, student.category_id)
        # The shared lifecycle marker survives graduation.
        self.assertIn(self.cat_student, student.category_id)

    def test_convert_to_ex_student_not_graduated_becomes_withdrawal(self):
        student = self.env['res.partner'].create({
            'name': 'Quitter', 'contact_type': 'student',
            'has_graduated': False, 'main_group_id': self.group.id})
        student._ems_convert_to_ex_student()
        self.assertEqual(student.contact_type, 'withdrawal')
        self.assertFalse(student.main_group_id)
        self.assertIn(self.cat_withdrawal, student.category_id)

    # --- _ems_convert_to_student --------------------------------------------

    def test_convert_to_student_clears_exit_keeps_has_graduated(self):
        alumni = self.env['res.partner'].create({
            'name': 'Returning Alumni', 'contact_type': 'alumni',
            'has_graduated': True, 'exit_type': 'graduation',
            'exit_course_id': self.course.id, 'exit_date': date.today(),
            'exit_reason': 'Finished studies'})
        alumni._ems_convert_to_student()
        self.assertEqual(alumni.contact_type, 'student')
        self.assertFalse(alumni.exit_type)
        self.assertFalse(alumni.exit_course_id)
        self.assertFalse(alumni.exit_date)
        self.assertFalse(alumni.exit_reason)
        # has_graduated is a permanent mark and must survive re-enrolment.
        self.assertTrue(alumni.has_graduated)
        self.assertIn(self.cat_student, alumni.category_id)
        self.assertNotIn(self.cat_alumni, alumni.category_id)

    def test_applicant_admission_to_student(self):
        applicant = self.env['res.partner'].create({
            'name': 'Admitted', 'contact_type': 'applicant'})
        applicant._ems_convert_to_student()
        self.assertEqual(applicant.contact_type, 'student')
        self.assertIn(self.cat_student, applicant.category_id)
        self.assertNotIn(self.cat_applicant, applicant.category_id)
