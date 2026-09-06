import base64
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group, mock_outgoing_email


class TestContactLifecycle(TransactionCase):
    """Contact lifecycle categories: applicant -> student -> alumni/withdrawal."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cat_student = cls.env.ref('ems.partner_category_student')
        cls.cat_applicant = cls.env.ref('ems.partner_category_applicant')
        cls.cat_alumni = cls.env.ref('ems.partner_category_alumni')
        cls.cat_withdrawal = cls.env.ref('ems.partner_category_withdrawal')

        cls.level, cls.study, cls.group = create_level_study_group(cls, 'LFC', level={'name': 'Lifecycle Level'}, study={
            'code': 'LFC001', 'acronym': 'LFCS', 'name': 'Lifecycle Study',
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

    # --- archived_reason_label / archived_reason_color (ems_archived_reason_ribbon widget) ---

    def test_archived_reason_blank_for_active_student(self):
        student = self.env['res.partner'].create({
            'name': 'Active Student (Archived Reason)', 'contact_type': 'student'})
        self.assertFalse(student.archived_reason_label)
        self.assertFalse(student.archived_reason_color)

    def test_archived_reason_alumni(self):
        alumni = self.env['res.partner'].create({
            'name': 'Alumni (Archived Reason)', 'contact_type': 'alumni'})
        self.assertEqual(alumni.archived_reason_label, 'Alumni')
        self.assertEqual(alumni.archived_reason_color, '#4C7A5D')

    def test_archived_reason_withdrawal(self):
        withdrawal = self.env['res.partner'].create({
            'name': 'Withdrawal (Archived Reason)', 'contact_type': 'withdrawal'})
        self.assertEqual(withdrawal.archived_reason_label, 'Withdrawal')
        self.assertEqual(withdrawal.archived_reason_color, '#C97B3D')

    def test_archived_reason_expelled_has_label_but_no_color(self):
        # No color constant on purpose - the widget falls back to its own default red,
        # the same severity-signalling reasoning as leaving hr.departure.reason's "Fired"
        # record uncolored (see docs/en/developers/contacts/contact.md).
        expelled = self.env['res.partner'].create({
            'name': 'Expelled (Archived Reason)', 'contact_type': 'expelled'})
        self.assertEqual(expelled.archived_reason_label, 'Expelled')
        self.assertFalse(expelled.archived_reason_color)

    def test_archived_reason_blank_for_family(self):
        # Not a lifecycle-ribbon-worthy contact_type - keeps the native generic "Archived"
        # ribbon instead (see contact/form.xml's own comment).
        family = self.env['res.partner'].create({
            'name': 'Family (Archived Reason)', 'contact_type': 'family'})
        self.assertFalse(family.archived_reason_label)

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

    def test_convert_to_ex_student_expulsion_kind_overrides_has_graduated(self):
        # Expulsion is never alumni, even for a student who already graduated once -
        # unlike the default (no kind) path, which defers entirely to has_graduated.
        student = self.env['res.partner'].create({
            'name': 'Expelled Graduate', 'contact_type': 'student',
            'has_graduated': True, 'main_group_id': self.group.id})
        student._ems_convert_to_ex_student(kind='expulsion')
        self.assertEqual(student.contact_type, 'expelled')
        self.assertFalse(student.main_group_id)
        self.assertIn(self.env.ref('ems.partner_category_expelled'), student.category_id)

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
        mock_outgoing_email(cls)

        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TCF', level={'name': 'Test Contact Fields Level'}, study={
            'code': 'TCF001', 'acronym': 'TCFS', 'name': 'Test Contact Fields Study',
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

    # --- tutor_id ---------------------------------------------------------------

    def test_tutor_id_write_does_not_reassign_the_group_tutor(self):
        # Regression (found 2026-09-06): 'tutor_id' is related="main_group_id.tutor_id" with no
        # explicit readonly - Odoo only skips auto-generating a write-through inverse when the
        # field (or its target) is already readonly, neither of which was true here. Without
        # readonly=True, writing "Tutor" from a STUDENT's own form would silently reassign that
        # student's WHOLE GROUP's tutor (affecting every other student in it), not just a
        # display value scoped to this one student.
        other_teacher = self.env['hr.employee'].create({'name': 'Other Teacher (TCF)', 'employee_type': 'teacher'})
        student = self.env['res.partner'].create({
            'name': 'Tutor Readonly Student', 'contact_type': 'student', 'main_group_id': self.group.id})

        # A readonly related field with no inverse is silently ignored by write(), not
        # rejected with an exception - it only ends up staged in this recordset's own
        # in-memory cache (a compute field with no inverse has nowhere to persist a write to),
        # so the actual guarantee to verify is that the group's own tutor - the field's real
        # source of truth - never changes, and that a fresh (recomputed) read reflects that.
        student.write({'tutor_id': other_teacher.id})

        self.assertNotEqual(self.group.tutor_id, other_teacher)
        student.invalidate_recordset(['tutor_id'])
        self.assertEqual(student.tutor_id, self.group.tutor_id)

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

    # --- ems_authorization_ids ---------------------------------------------------

    def test_ems_authorization_ids_recomputes_within_same_transaction(self):
        """Regression test: _compute_ems_authorization_ids had no @api.depends,
        so within a single transaction its cached (non-stored) value could go
        stale after a new enrollment/authorization was created for the same
        student — fixed in the authorization.py DTON pass, see
        docs/en/developers/enrollment/authorization.md."""
        course = self.env['ems.course'].search([('is_current', '=', True)], limit=1) \
            or self.env['ems.course'].create({'start': 2098, 'end': 2099, 'is_current': True})
        student = self.env['res.partner'].create({'name': 'Auth Recompute Student', 'contact_type': 'student'})
        template = self.env['ems.authorization.template'].create({
            'name': 'Recompute Template', 'legal_text': '<p>Text</p>'})

        self.assertFalse(student.ems_authorization_ids)

        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study.id, 'ems_course_id': course.id,
        })
        order.apply_authorizations()

        self.assertIn(template, student.ems_authorization_ids.mapped('template_id'))


class TestContactMainGroupChange(TransactionCase):
    """Changing 'main_group_id' cascades to the student's ems.enrollment rows (issue #395:
    a tutor moving a tutorand from one group to another). See docs/en/developers/contacts/
    contact.md and models/contacts/enrollment.py's '_ems_move_group'."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TMG', level={'name': 'Test Move Group Level'}, study={
            'code': 'TMG001', 'acronym': 'TMGS', 'name': 'Test Move Group Study',
        })
        cls.other_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TMG001', 'acronym': 'TMG', 'name': 'Test Move Group Subject',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        # A real (non-superuser) admin user: TransactionCase's own self.env already runs as
        # SUPERUSER_ID (env.su == True), which would make every plain write() below
        # indistinguishable from the sudo()-driven system flows this feature must NOT touch
        # (see contact.py write()'s env.su guard). with_user() is what actually sets
        # env.su = False, mirroring a real tutor/admin/secretary editing the form - same
        # reason test_enrollment.py's own default_get admin/non-admin tests use with_user().
        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Move Group)', 'login': 'test_admin_move_group',
            'groups_id': [(4, cls.env.ref('ems.group_academic_admin').id)],
        })

    def _student(self, group):
        return self.env['res.partner'].create({
            'name': 'Move Group Student', 'contact_type': 'student',
            'main_group_id': group.id if group else False})

    def _enrollment(self, student, group):
        return self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': group.id, 'subject_id': self.subject.id})

    def test_write_moves_enrollment_to_new_group(self):
        student = self._student(self.group)
        enrollment = self._enrollment(student, self.group)

        student.with_user(self.admin_user).write({'main_group_id': self.other_group.id})

        self.assertFalse(enrollment.exists())
        moved = self.env['ems.enrollment'].search([('student_id', '=', student.id)])
        self.assertEqual(moved.group_id, self.other_group)

    def test_write_leaves_enrollment_in_a_different_group_untouched(self):
        third_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'C', 'level_id': self.level.id, 'study_id': self.study.id})
        student = self._student(self.group)
        untouched = self._enrollment(student, third_group)

        student.with_user(self.admin_user).write({'main_group_id': self.other_group.id})

        self.assertTrue(untouched.exists())
        self.assertEqual(untouched.group_id, third_group)

    def test_write_same_group_does_not_touch_enrollment(self):
        student = self._student(self.group)
        enrollment = self._enrollment(student, self.group)

        student.with_user(self.admin_user).write({'main_group_id': self.group.id})

        self.assertTrue(enrollment.exists())
        self.assertEqual(enrollment.group_id, self.group)

    def test_write_from_no_group_does_not_raise(self):
        student = self._student(False)
        student.with_user(self.admin_user).write({'main_group_id': self.group.id})
        self.assertEqual(student.main_group_id, self.group)

    def test_sudo_write_does_not_migrate_enrollment(self):
        """Mirrors sale.order._ems_apply_destination_placement()'s own sudo() write - course
        transition/enrollment placement moves a student to a new group ON PURPOSE without
        touching the old group's enrollments (they are the outgoing year's history). Excluding
        env.su is what keeps that flow unaffected by this cascade - see CLAUDE.md and
        ems.enrollment.default_get's own use of the same env.su vs. env.user distinction."""
        student = self._student(self.group)
        enrollment = self._enrollment(student, self.group)

        student.with_user(self.admin_user).sudo().write({'main_group_id': self.other_group.id})

        self.assertTrue(enrollment.exists())
        self.assertEqual(enrollment.group_id, self.group)
        self.assertEqual(student.main_group_id, self.other_group)

    def test_write_raises_if_old_enrollment_has_scored_grades(self):
        student = self._student(self.group)
        teacher = self.env['hr.employee'].create({'name': 'TMG Teacher', 'employee_type': 'teacher'})
        # The session must exist BEFORE the enrollment for _ems_sync_grade_session_add() (fired
        # by ems.enrollment.create()) to populate its lines - creating it after would leave the
        # session with no line for this student to score at all.
        session = self.env['ems.grade_session'].create({
            'group_id': self.group.id, 'subject_id': self.subject.id, 'round': '1', 'teacher_id': teacher.id})
        enrollment = self._enrollment(student, self.group)
        # This subject has no outcomes, so grade_outcome_line_ids stays empty -
        # grade_subject_line_ids (always created, one per student) is what carries a score here.
        line = session.grade_subject_line_ids.filtered(lambda l: l.student_id == student)
        line.write({'external_score': 8, 'external_is_scored': True})

        with self.assertRaises(UserError):
            student.with_user(self.admin_user).write({'main_group_id': self.other_group.id})

        self.assertTrue(enrollment.exists())
        self.assertEqual(enrollment.group_id, self.group)

    # --- main_group_pending_change (the Studies tab's pre-save warning) ---------------

    def test_main_group_pending_change_reflects_an_unsaved_edit(self):
        # A virtual record with 'origin' set is exactly how Odoo represents an on-screen,
        # not-yet-saved form edit (the same mechanism the form/onchange machinery itself uses -
        # see test_enrollment.py's own note on NewId(origin=...)): 'main_group_id' below is only
        # ever set on the virtual record, never written/persisted on 'student' itself.
        student = self._student(self.group)
        virtual = self.env['res.partner'].new({}, origin=student)
        self.assertFalse(virtual.main_group_pending_change)

        virtual.main_group_id = self.other_group
        self.assertTrue(virtual.main_group_pending_change)

        virtual.main_group_id = self.group
        self.assertFalse(virtual.main_group_pending_change)
        self.assertEqual(student.main_group_id, self.group)

    def test_main_group_pending_change_false_without_a_previous_group(self):
        student = self._student(False)
        virtual = self.env['res.partner'].new({}, origin=student)

        virtual.main_group_id = self.group

        self.assertFalse(virtual.main_group_pending_change)
