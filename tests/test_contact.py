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
