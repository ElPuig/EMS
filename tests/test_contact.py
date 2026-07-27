from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo.exceptions import ValidationError
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

    # --- create()'s parent_id-driven contact_type ---------------------------

    def test_create_child_of_student_becomes_family(self):
        student = self.env['res.partner'].create({
            'name': 'Parent Of Contact', 'contact_type': 'student'})
        child = self.env['res.partner'].create({
            'name': 'Auto Family Contact', 'parent_id': student.id})
        self.assertEqual(child.contact_type, 'family')

    def test_create_child_of_provider_becomes_provider(self):
        provider = self.env['res.partner'].create({
            'name': 'Parent Provider', 'contact_type': 'provider'})
        child = self.env['res.partner'].create({
            'name': 'Auto Provider Contact', 'parent_id': provider.id})
        self.assertEqual(child.contact_type, 'provider')

    # --- _ems_resync_lifecycle_categories ------------------------------------

    def test_resync_lifecycle_categories_heals_applicant(self):
        applicant = self.env['res.partner'].create({
            'name': 'Uncategorized Applicant', 'contact_type': 'applicant'})
        applicant.category_id = [(5, 0, 0)]
        self.assertFalse(applicant.category_id)
        self.env['res.partner']._ems_resync_lifecycle_categories()
        applicant.invalidate_recordset(['category_id'])
        self.assertIn(self.cat_applicant, applicant.category_id)
        self.assertIn(self.cat_student, applicant.category_id)


class TestContactFields(TransactionCase):
    """EMS-specific res.partner fields not covered by exit-management, enrollment
    or enrollment-benefit tests (see test_exit_management.py / test_enrollment_benefit.py
    for transition_status, graduation/withdrawal and benefit_status coverage)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ems.strike sends real emails synchronously on create() (see CLAUDE.md).
        mail_server_patcher = patch(
            'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email',
            return_value='test-message-id',
        )
        mail_server_patcher.start()
        cls.addClassCleanup(mail_server_patcher.stop)

        cls.level = cls.env['ems.level'].create({'acronym': 'TCF', 'name': 'Test Contact Fields Level'})
        cls.study = cls.env['ems.study'].create({
            'code': 'TCF001', 'acronym': 'TCFS', 'name': 'Test Contact Fields Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })

    # --- is_adult -------------------------------------------------------------

    def test_is_adult_true_for_over_18(self):
        student = self.env['res.partner'].create({
            'name': 'Adult Student', 'contact_type': 'student',
            'birth_date': date.today() - relativedelta(years=19),
        })
        self.assertTrue(student.is_adult)

    def test_is_adult_false_for_under_18(self):
        student = self.env['res.partner'].create({
            'name': 'Minor Student', 'contact_type': 'student',
            'birth_date': date.today() - relativedelta(years=15),
        })
        self.assertFalse(student.is_adult)

    def test_is_adult_false_without_birth_date(self):
        student = self.env['res.partner'].create({'name': 'No Birthdate Student', 'contact_type': 'student'})
        self.assertFalse(student.is_adult)

    # --- strike_count -----------------------------------------------------------

    def test_strike_count(self):
        teacher = self.env['hr.employee'].create({
            'name': 'Strike Count Teacher', 'employee_type': 'teacher'})
        student = self.env['res.partner'].create({'name': 'Struck Student', 'contact_type': 'student'})
        self.assertEqual(student.strike_count, 0)
        self.env['ems.strike'].create({'student_id': student.id, 'teacher_id': teacher.id})
        self.env['ems.strike'].create({'student_id': student.id, 'teacher_id': teacher.id})
        self.assertEqual(student.strike_count, 2)

    # --- _check_nuss ------------------------------------------------------------

    def test_nuss_valid_12_digits(self):
        student = self.env['res.partner'].create({
            'name': 'Valid Nuss Student', 'contact_type': 'student', 'nuss': '123456789012'})
        self.assertEqual(student.nuss, '123456789012')

    def test_nuss_invalid_raises(self):
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': 'Invalid Nuss Student', 'contact_type': 'student', 'nuss': '12345'})

    # --- _compute_group_data -----------------------------------------------------

    def test_group_data_synced_from_main_group_on_create(self):
        student = self.env['res.partner'].create({
            'name': 'Group Data Student', 'contact_type': 'student', 'main_group_id': self.group.id})
        self.assertEqual(student.level_id, self.level)
        self.assertEqual(student.study_id, self.study)

    def test_group_data_synced_from_study_on_create(self):
        student = self.env['res.partner'].create({
            'name': 'Study Only Student', 'contact_type': 'student', 'study_id': self.study.id})
        self.assertEqual(student.level_id, self.level)

    def test_group_data_synced_from_main_group_on_write(self):
        student = self.env['res.partner'].create({'name': 'Later Group Student', 'contact_type': 'student'})
        student.write({'main_group_id': self.group.id})
        self.assertEqual(student.level_id, self.level)
        self.assertEqual(student.study_id, self.study)

    # --- _onchange_level_id / _onchange_study_id ---------------------------------

    def test_onchange_level_id_clears_study(self):
        student = self.env['res.partner'].new({'study_id': self.study.id})
        student._onchange_level_id()
        self.assertFalse(student.study_id)

    def test_onchange_study_id_clears_main_group(self):
        student = self.env['res.partner'].new({'main_group_id': self.group.id})
        student._onchange_study_id()
        self.assertFalse(student.main_group_id)
