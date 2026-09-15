import base64
from datetime import date

import psycopg2
from dateutil.relativedelta import relativedelta

from odoo.addons.ems.models.contacts.contact import STUDENT_LIFECYCLE_TYPES
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from .common import create_level_study, create_level_study_group, mock_outgoing_email, next_student_id


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
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': self.group.id})
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

    def test_auth_flags_read_an_authorization_sent_during_the_course(self):
        """Issue #443: an authorization accepted mid-year, with no enrollment behind it,
        counts exactly as much as one accepted at enrollment time - before this it could
        not be seen at all, since the flags only ever walked the enrollment."""
        incoming = self._incoming_course()
        self.env.company.current_course_id = self.course     # outgoing still current
        student, _order = self._enrolled('LFC Auth Standalone', incoming)
        self.assertFalse(student.auth_trip)
        self.env['ems.authorization'].create({
            'partner_id': student.id,
            'course_id': incoming.id,
            'template_id': self._auth_template('trip').id,
            'status': 'yes',
        })
        self.assertTrue(student.auth_trip)

    def test_the_authorization_list_includes_the_ones_sent_during_the_course(self):
        incoming = self._incoming_course()
        self.env.company.current_course_id = self.course
        student, order = self._enrolled('LFC Auth Standalone List', incoming, 'image')
        standalone = self.env['ems.authorization'].create({
            'partner_id': student.id,
            'course_id': incoming.id,
            'template_id': self._auth_template('trip').id,
        })
        self.assertEqual(student.ems_authorization_ids,
                         order.ems_authorization_ids | standalone)

    def test_the_authorization_list_stays_scoped_to_the_course_in_force(self):
        """An authorization from another academic year does not belong next to badges
        that speak about this one."""
        incoming = self._incoming_course()
        self.env.company.current_course_id = self.course
        student, _order = self._enrolled('LFC Auth Other Year', incoming)
        other_year = self.env['ems.course'].create({'start': 2080, 'end': 2081})
        self.env['ems.authorization'].create({
            'partner_id': student.id,
            'course_id': other_year.id,
            'template_id': self._auth_template('health').id,
            'status': 'yes',
        })
        self.assertFalse(student.ems_authorization_ids)
        self.assertFalse(student.auth_healt)

    def test_auth_flags_are_false_without_an_enrollment(self):
        student = self.env['res.partner'].create({
            'name': 'LFC Auth None', 'contact_type': 'student', 'student_id': next_student_id(),
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
            'name': 'New Applicant', 'contact_type': 'applicant', 'student_id': next_student_id()})
        self.assertEqual(applicant.contact_type, 'applicant')

    def test_create_alumni_and_withdrawal(self):
        alumni = self.env['res.partner'].create({
            'name': 'Old Alumni', 'contact_type': 'alumni', 'student_id': next_student_id()})
        withdrawal = self.env['res.partner'].create({
            'name': 'Dropout', 'contact_type': 'withdrawal', 'student_id': next_student_id()})
        self.assertEqual(alumni.contact_type, 'alumni')
        self.assertEqual(withdrawal.contact_type, 'withdrawal')

    def test_has_graduated_defaults_false(self):
        student = self.env['res.partner'].create({
            'name': 'Fresh Student', 'contact_type': 'student', 'student_id': next_student_id()})
        self.assertFalse(student.has_graduated)

    # --- archived_reason_label / archived_reason_color (ems_archived_reason_ribbon widget) ---

    def test_archived_reason_blank_for_active_student(self):
        student = self.env['res.partner'].create({
            'name': 'Active Student (Archived Reason)', 'contact_type': 'student', 'student_id': next_student_id()})
        self.assertFalse(student.archived_reason_label)
        self.assertFalse(student.archived_reason_color)

    def test_archived_reason_alumni(self):
        alumni = self.env['res.partner'].create({
            'name': 'Alumni (Archived Reason)', 'contact_type': 'alumni', 'student_id': next_student_id()})
        self.assertEqual(alumni.archived_reason_label, 'Alumni')
        self.assertEqual(alumni.archived_reason_color, '#4C7A5D')

    def test_archived_reason_withdrawal(self):
        withdrawal = self.env['res.partner'].create({
            'name': 'Withdrawal (Archived Reason)', 'contact_type': 'withdrawal', 'student_id': next_student_id()})
        self.assertEqual(withdrawal.archived_reason_label, 'Withdrawal')
        self.assertEqual(withdrawal.archived_reason_color, '#C97B3D')

    def test_archived_reason_expelled_has_label_but_no_color(self):
        # No color constant on purpose - the widget falls back to its own default red,
        # the same severity-signalling reasoning as leaving hr.departure.reason's "Fired"
        # record uncolored (see docs/en/developers/contacts/contact.md).
        expelled = self.env['res.partner'].create({
            'name': 'Expelled (Archived Reason)', 'contact_type': 'expelled', 'student_id': next_student_id()})
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
            'name': 'Applicant Cat', 'contact_type': 'applicant', 'student_id': next_student_id()})
        self.assertIn(self.cat_applicant, applicant.category_id)
        # "student" doubles as the shared student-lifecycle marker.
        self.assertIn(self.cat_student, applicant.category_id)

    def test_sync_category_swaps_on_write(self):
        student = self.env['res.partner'].create({
            'name': 'Swap Student', 'contact_type': 'student', 'student_id': next_student_id()})
        self.assertIn(self.cat_student, student.category_id)
        student.write({'contact_type': 'alumni'})
        self.assertIn(self.cat_alumni, student.category_id)
        # The shared lifecycle marker survives the transition.
        self.assertIn(self.cat_student, student.category_id)

    # --- _ems_convert_to_ex_student -----------------------------------------

    def test_convert_to_ex_student_graduated_becomes_alumni(self):
        student = self.env['res.partner'].create({
            'name': 'Graduate', 'contact_type': 'student', 'student_id': next_student_id(),
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
            'name': 'Quitter', 'contact_type': 'student', 'student_id': next_student_id(),
            'has_graduated': False, 'main_group_id': self.group.id})
        student._ems_convert_to_ex_student()
        self.assertEqual(student.contact_type, 'withdrawal')
        self.assertFalse(student.main_group_id)
        self.assertIn(self.cat_withdrawal, student.category_id)

    def test_convert_to_ex_student_expulsion_kind_overrides_has_graduated(self):
        # Expulsion is never alumni, even for a student who already graduated once -
        # unlike the default (no kind) path, which defers entirely to has_graduated.
        student = self.env['res.partner'].create({
            'name': 'Expelled Graduate', 'contact_type': 'student', 'student_id': next_student_id(),
            'has_graduated': True, 'main_group_id': self.group.id})
        student._ems_convert_to_ex_student(kind='expulsion')
        self.assertEqual(student.contact_type, 'expelled')
        self.assertFalse(student.main_group_id)
        self.assertIn(self.env.ref('ems.partner_category_expelled'), student.category_id)

    # --- _ems_convert_to_student --------------------------------------------

    def test_convert_to_student_clears_exit_keeps_has_graduated(self):
        alumni = self.env['res.partner'].create({
            'name': 'Returning Alumni', 'contact_type': 'alumni', 'student_id': next_student_id(),
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
            'name': 'Admitted', 'contact_type': 'applicant', 'student_id': next_student_id()})
        applicant._ems_convert_to_student()
        self.assertEqual(applicant.contact_type, 'student')
        self.assertIn(self.cat_student, applicant.category_id)
        self.assertNotIn(self.cat_applicant, applicant.category_id)

    # --- create()'s parent_id-driven contact_type ---------------------------

    def test_create_child_of_student_becomes_family(self):
        student = self.env['res.partner'].create({
            'name': 'Parent Of Contact', 'contact_type': 'student', 'student_id': next_student_id()})
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
            'name': 'Uncategorized Applicant', 'contact_type': 'applicant', 'student_id': next_student_id()})
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
            'name': 'Adult Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'birth_date': date.today() - relativedelta(years=19),
        })
        self.assertTrue(student.is_adult)

    def test_is_adult_false_for_under_18(self):
        student = self.env['res.partner'].create({
            'name': 'Minor Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'birth_date': date.today() - relativedelta(years=15),
        })
        self.assertFalse(student.is_adult)

    def test_is_adult_false_without_birth_date(self):
        student = self.env['res.partner'].create({'name': 'No Birthdate Student', 'contact_type': 'student', 'student_id': next_student_id()})
        self.assertFalse(student.is_adult)

    # --- strike_count -----------------------------------------------------------

    def test_strike_count(self):
        teacher = self.env['hr.employee'].create({
            'name': 'Strike Count Teacher', 'employee_type': 'teacher'})
        student = self.env['res.partner'].create({'name': 'Struck Student', 'contact_type': 'student', 'student_id': next_student_id()})
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
            'name': 'Tutor Readonly Student', 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': self.group.id})

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
            'name': 'Valid Nuss Student', 'contact_type': 'student', 'student_id': next_student_id(), 'nuss': '123456789012'})
        self.assertEqual(student.nuss, '123456789012')

    def test_nuss_invalid_raises(self):
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': 'Invalid Nuss Student', 'contact_type': 'student', 'student_id': next_student_id(), 'nuss': '12345'})

    # --- _compute_group_data -----------------------------------------------------

    def test_group_data_synced_from_main_group_on_create(self):
        student = self.env['res.partner'].create({
            'name': 'Group Data Student', 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': self.group.id})
        self.assertEqual(student.level_id, self.level)
        self.assertEqual(student.study_id, self.study)

    def test_group_data_synced_from_study_on_create(self):
        student = self.env['res.partner'].create({
            'name': 'Study Only Student', 'contact_type': 'student', 'student_id': next_student_id(), 'study_id': self.study.id})
        self.assertEqual(student.level_id, self.level)

    def test_group_data_synced_from_main_group_on_write(self):
        student = self.env['res.partner'].create({'name': 'Later Group Student', 'contact_type': 'student', 'student_id': next_student_id()})
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
        student = self.env['res.partner'].create({'name': 'Auth Recompute Student', 'contact_type': 'student', 'student_id': next_student_id()})
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
            'name': 'Move Group Student', 'contact_type': 'student', 'student_id': next_student_id(),
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


class TestContactStudyChange(TransactionCase):
    """Changing 'study_id' regenerates the student's ems.enrollment rows from the enrollment
    template matching the new study + auto-picked group's course (secretary report: changing
    a student's study left their subject enrollments stale). See docs/en/developers/contacts/
    contact.md and res.partner._ems_refresh_enrollments_from_template()."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.old_level, cls.old_study, cls.old_group = create_level_study_group(
            cls, 'TSCO', level={'name': 'Test Study Change Old Level'}, study={
                'code': 'TSCO001', 'acronym': 'TSCOS', 'name': 'Test Study Change Old Study'})
        cls.old_subject = cls.env['ems.subject'].create({
            'code': 'TSCO001', 'acronym': 'TSCO', 'name': 'Test Study Change Old Subject',
            'study_ids': [(6, 0, [cls.old_study.id])],
        })

        cls.new_level, cls.new_study, cls.new_group_b = create_level_study_group(
            cls, 'TSCN', level={'name': 'Test Study Change New Level'}, study={
                'code': 'TSCN001', 'acronym': 'TSCNS', 'name': 'Test Study Change New Study'},
            group={'acronym': 'B'})
        # A second, alphabetically-earlier group for the same study+course, to prove the
        # auto-pick lands on the first one by name (see contact.py write()'s auto_group search).
        cls.new_group_a = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.new_level.id, 'study_id': cls.new_study.id,
        })
        cls.new_subject = cls.env['ems.subject'].create({
            'code': 'TSCN001', 'acronym': 'TSCN', 'name': 'Test Study Change New Subject',
            'study_ids': [(6, 0, [cls.new_study.id])],
        })
        cls.template = cls.env['sale.order.template'].create({
            'name': 'Test Study Change Template', 'ems_study_id': cls.new_study.id, 'study_year': 1,
            'sale_order_template_line_ids': [(0, 0, {'product_id': cls.new_subject.product_id.id})],
        })

        # A real (non-superuser) user: see TestContactMainGroupChange's own admin_user for why
        # (TransactionCase's self.env runs as SUPERUSER_ID, indistinguishable from the sudo()'d
        # system flows this feature must NOT touch).
        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Study Change)', 'login': 'test_admin_study_change',
            'email': 'test.admin.study.change@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_academic_admin').id)],
        })

    def _student(self):
        return self.env['res.partner'].create({
            'name': 'Study Change Student', 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': self.old_group.id})

    def _old_enrollment(self, student):
        return self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.old_group.id, 'subject_id': self.old_subject.id})

    def test_write_study_id_auto_picks_first_group_alphabetically(self):
        student = self._student()
        student.with_user(self.admin_user).write({'study_id': self.new_study.id})
        self.assertEqual(student.main_group_id, self.new_group_a)

    def test_write_study_id_creates_enrollment_from_template(self):
        student = self._student()
        student.with_user(self.admin_user).write({'study_id': self.new_study.id})
        enrollment = self.env['ems.enrollment'].search([('student_id', '=', student.id)])
        self.assertEqual(enrollment.subject_id, self.new_subject)
        self.assertEqual(enrollment.group_id, self.new_group_a)

    def test_write_study_id_removes_old_enrollment_without_grades(self):
        student = self._student()
        old_enrollment = self._old_enrollment(student)
        student.with_user(self.admin_user).write({'study_id': self.new_study.id})
        self.assertFalse(old_enrollment.exists())

    def test_write_study_id_keeps_old_enrollment_with_scored_grades(self):
        student = self._student()
        teacher = self.env['hr.employee'].create({'name': 'TSC Teacher', 'employee_type': 'teacher'})
        # The session must exist BEFORE the enrollment for _ems_sync_grade_session_add() (fired
        # by ems.enrollment.create()) to populate its lines - see TestContactMainGroupChange's
        # own test_write_raises_if_old_enrollment_has_scored_grades for the same ordering note.
        session = self.env['ems.grade_session'].create({
            'group_id': self.old_group.id, 'subject_id': self.old_subject.id, 'round': '1', 'teacher_id': teacher.id})
        old_enrollment = self._old_enrollment(student)
        line = session.grade_subject_line_ids.filtered(lambda l: l.student_id == student)
        line.write({'external_score': 8, 'external_is_scored': True})

        student.with_user(self.admin_user).write({'study_id': self.new_study.id})

        self.assertTrue(old_enrollment.exists())
        new_enrollment = self.env['ems.enrollment'].search([
            ('student_id', '=', student.id), ('subject_id', '=', self.new_subject.id)])
        self.assertTrue(new_enrollment)

    def test_write_study_id_kept_grades_note_is_translated(self):
        # Verifies the .po translation actually loaded and applies at runtime - a msgid
        # existing in the .po file is necessary but not sufficient (see CLAUDE.md's i18n
        # verification rule).
        student = self._student()
        teacher = self.env['hr.employee'].create({'name': 'TSC Teacher ES', 'employee_type': 'teacher'})
        session = self.env['ems.grade_session'].create({
            'group_id': self.old_group.id, 'subject_id': self.old_subject.id, 'round': '1', 'teacher_id': teacher.id})
        self._old_enrollment(student)
        line = session.grade_subject_line_ids.filtered(lambda l: l.student_id == student)
        line.write({'external_score': 8, 'external_is_scored': True})

        student.with_user(self.admin_user).with_context(lang='es_ES').write({'study_id': self.new_study.id})

        note = student.message_ids.filtered(lambda m: 'plantilla' in (m.body or ''))
        self.assertTrue(note)
        self.assertIn('ya tienen', note.body)

    def test_write_study_id_without_any_group_creates_nothing(self):
        empty_level, empty_study = create_level_study(self, 'TSCE', level={'name': 'Test Study Change Empty Level'}, study={
            'code': 'TSCE001', 'acronym': 'TSCES', 'name': 'Test Study Change Empty Study'})
        student = self._student()
        student.with_user(self.admin_user).write({'study_id': empty_study.id})
        self.assertFalse(student.main_group_id)
        self.assertFalse(self.env['ems.enrollment'].search([('student_id', '=', student.id)]))

    def test_write_study_id_with_explicit_group_on_existing_placement_skips_template_refresh(self):
        """An explicit main_group_id in the same write, for a student who ALREADY had a
        group (a genuine group change, not a first placement), is handled by the
        pre-existing group-change migration (TestContactMainGroupChange) instead - see
        contact.py write()'s 'not partner.main_group_id' escape hatch."""
        student = self._student()
        self._old_enrollment(student)
        student.with_user(self.admin_user).write({
            'study_id': self.new_study.id, 'main_group_id': self.new_group_b.id})

        self.assertEqual(student.main_group_id, self.new_group_b)
        moved = self.env['ems.enrollment'].search([('student_id', '=', student.id)])
        self.assertEqual(moved.subject_id, self.old_subject)
        self.assertEqual(moved.group_id, self.new_group_b)

    def test_write_study_id_with_explicit_group_on_first_placement_creates_enrollment_from_template(self):
        """A student with NO previous group has nothing for the group-change migration to
        move FROM, so setting study_id and main_group_id together still runs the template
        refresh - using the given group instead of auto-picking one. Found the hard way
        (issue #455 follow-up): filling Studies then Main Group before the very first save
        is the normal way to place a new/unplaced student, and used to silently produce
        zero enrollments."""
        student = self.env['res.partner'].create({'name': 'Study Change Unplaced Student', 'contact_type': 'student', 'student_id': next_student_id()})
        student.with_user(self.admin_user).write({
            'study_id': self.new_study.id, 'main_group_id': self.new_group_b.id})

        self.assertEqual(student.main_group_id, self.new_group_b)
        enrollment = self.env['ems.enrollment'].search([('student_id', '=', student.id)])
        self.assertEqual(enrollment.subject_id, self.new_subject)
        self.assertEqual(enrollment.group_id, self.new_group_b)

    def test_sudo_write_study_id_does_not_refresh_enrollments(self):
        """Mirrors TestContactMainGroupChange.test_sudo_write_does_not_migrate_enrollment:
        under sudo, main_group_id is written as given (untouched here) and nothing else
        about the student is inferred - the caller (a system flow acting on the student's
        behalf) is responsible for its own group/enrollments, exactly like
        sale.order._ems_apply_destination_placement() already is."""
        student = self._student()
        old_enrollment = self._old_enrollment(student)
        student.with_user(self.admin_user).sudo().write({'study_id': self.new_study.id})
        self.assertTrue(old_enrollment.exists())
        self.assertEqual(student.main_group_id, self.old_group)

    def test_write_study_id_on_non_student_contact_is_noop(self):
        applicant = self.env['res.partner'].create({
            'name': 'Study Change Applicant', 'contact_type': 'applicant', 'student_id': next_student_id()})
        applicant.with_user(self.admin_user).write({'study_id': self.new_study.id})
        self.assertFalse(applicant.main_group_id)
        self.assertFalse(self.env['ems.enrollment'].search([('student_id', '=', applicant.id)]))


class TestContactCreateWithStudy(TransactionCase):
    """Creating a student with 'study_id' already set (issue: a brand-new student never got
    the same auto-placement/enrollment-from-template treatment write() already gives an
    EXISTING student on a study change - see TestContactStudyChange). See docs/en/developers/
    contacts/contact.md and res.partner._ems_auto_group_for_study()/_ems_refresh_enrollments_from_template()."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group_b = create_level_study_group(
            cls, 'TCCS', level={'name': 'Test Create Study Level'}, study={
                'code': 'TCCS001', 'acronym': 'TCCSS', 'name': 'Test Create Study Study'},
            group={'acronym': 'B'})
        # A second, alphabetically-earlier group for the same study+course, to prove the
        # auto-pick lands on the first one by name (mirrors TestContactStudyChange).
        cls.group_a = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TCCS001', 'acronym': 'TCCS', 'name': 'Test Create Study Subject',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.template = cls.env['sale.order.template'].create({
            'name': 'Test Create Study Template', 'ems_study_id': cls.study.id, 'study_year': 1,
            'sale_order_template_line_ids': [(0, 0, {'product_id': cls.subject.product_id.id})],
        })

        # A real (non-superuser) user: see TestContactStudyChange's own admin_user for why.
        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Create Study)', 'login': 'test_admin_create_study',
            'email': 'test.admin.create.study@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_academic_admin').id)],
        })

    def _create(self, **values):
        return self.env['res.partner'].with_user(self.admin_user).create({
            'name': 'Create Study Student', 'contact_type': 'student', 'student_id': next_student_id(), **values})

    def test_create_with_study_id_auto_picks_first_group_alphabetically(self):
        student = self._create(study_id=self.study.id)
        self.assertEqual(student.main_group_id, self.group_a)

    def test_create_with_study_id_creates_enrollment_from_template(self):
        student = self._create(study_id=self.study.id)
        enrollment = self.env['ems.enrollment'].search([('student_id', '=', student.id)])
        self.assertEqual(enrollment.subject_id, self.subject)
        self.assertEqual(enrollment.group_id, self.group_a)

    def test_create_with_study_id_and_main_group_id_creates_enrollment_from_template(self):
        """A create() is always a first placement (no previous group to migrate FROM), so
        giving main_group_id explicitly alongside study_id still runs the template refresh
        - using the given group instead of auto-picking one. Mirrors
        TestContactStudyChange.test_write_study_id_with_explicit_group_on_first_placement_creates_enrollment_from_template.
        Found the hard way (issue #455 follow-up): filling Studies then Main Group before
        the very first save is the normal way to place a new student, and used to silently
        produce zero enrollments."""
        student = self._create(study_id=self.study.id, main_group_id=self.group_b.id)
        self.assertEqual(student.main_group_id, self.group_b)
        enrollment = self.env['ems.enrollment'].search([('student_id', '=', student.id)])
        self.assertEqual(enrollment.subject_id, self.subject)
        self.assertEqual(enrollment.group_id, self.group_b)

    def test_create_applicant_with_study_id_creates_no_enrollment(self):
        """Regression: mirrors applicant_import_wizard's own create() shape
        (contact_type='applicant', study_id set, no main_group_id)."""
        applicant = self.env['res.partner'].with_user(self.admin_user).create({
            'name': 'Create Study Applicant', 'contact_type': 'applicant', 'student_id': next_student_id(), 'study_id': self.study.id})
        self.assertFalse(applicant.main_group_id)
        self.assertFalse(self.env['ems.enrollment'].search([('student_id', '=', applicant.id)]))

    def test_create_with_main_group_id_only_creates_no_template_enrollment(self):
        """Regression: mirrors student_import_wizard's own create() shape (main_group_id set
        directly, study_id absent) - no template lookup should run at all."""
        student = self._create(main_group_id=self.group_b.id)
        self.assertEqual(student.study_id, self.study)
        self.assertFalse(self.env['ems.enrollment'].search([('student_id', '=', student.id)]))

    def test_sudo_create_with_study_id_does_not_refresh_enrollments(self):
        """Defensive regression, mirrors TestContactStudyChange.test_sudo_write_study_id_does_not_refresh_enrollments."""
        student = self.env['res.partner'].sudo().create({
            'name': 'Create Study Student Sudo', 'contact_type': 'student', 'student_id': next_student_id(), 'study_id': self.study.id})
        self.assertFalse(student.main_group_id)
        self.assertFalse(self.env['ems.enrollment'].search([('student_id', '=', student.id)]))

    def test_create_with_study_id_without_any_group_creates_nothing(self):
        empty_level, empty_study = create_level_study(
            self, 'TCCE', level={'name': 'Test Create Study Empty Level'}, study={
                'code': 'TCCE001', 'acronym': 'TCCES', 'name': 'Test Create Study Empty Study'})
        student = self._create(study_id=empty_study.id)
        self.assertFalse(student.main_group_id)
        self.assertFalse(self.env['ems.enrollment'].search([('student_id', '=', student.id)]))

    def test_create_with_study_id_without_matching_template_creates_no_enrollment(self):
        untemplated_level, untemplated_study, untemplated_group = create_level_study_group(
            self, 'TCCU', level={'name': 'Test Create Study Untemplated Level'}, study={
                'code': 'TCCU001', 'acronym': 'TCCUS', 'name': 'Test Create Study Untemplated Study'})
        student = self._create(study_id=untemplated_study.id)
        self.assertEqual(student.main_group_id, untemplated_group)
        self.assertFalse(self.env['ems.enrollment'].search([('student_id', '=', student.id)]))


class TestContactStudentId(TransactionCase):
    """Student ID (IDALU): unique across every contact, required for new students (issue #460)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']

    def _student(self, **values):
        return self.Partner.create({
            'name': 'IDALU Student', 'contact_type': 'student', 'student_id': next_student_id(),
            **values})

    def _student_created_before_the_rule(self):
        """A student created while the IDALU was still optional (production had some)."""
        student = self._student(name='IDALU Legacy Student')
        self.env.cr.execute("UPDATE res_partner SET student_id = NULL WHERE id = %s", [student.id])
        student.invalidate_recordset(['student_id'])
        return student

    # --- required ------------------------------------------------------------

    def test_every_student_lifecycle_type_requires_a_student_id_on_create(self):
        for contact_type in STUDENT_LIFECYCLE_TYPES:
            with self.subTest(contact_type=contact_type), self.assertRaises(ValidationError):
                self.Partner.create({'name': 'IDALU Missing', 'contact_type': contact_type})

    def test_the_students_action_default_type_requires_a_student_id(self):
        with self.assertRaises(ValidationError):
            self.Partner.with_context(default_contact_type='student').create({'name': 'IDALU From Action'})

    def test_family_provider_and_untyped_contacts_need_no_student_id(self):
        for contact_type in ('family', 'provider', False):
            with self.subTest(contact_type=contact_type):
                self.assertTrue(self.Partner.create({'name': 'IDALU Not A Student', 'contact_type': contact_type}))

    def test_contact_added_under_a_student_needs_no_student_id(self):
        """The student form's "Contacts & Addresses" tab creates it with the Students action's
        default_contact_type still in context; create() turns it into a family contact."""
        student = self._student()
        family = self.Partner.with_context(default_contact_type='student').create(
            {'name': 'IDALU Child Contact', 'parent_id': student.id})
        self.assertEqual(family.contact_type, 'family')

    def test_student_id_cannot_be_removed(self):
        student = self._student()
        for blank in (False, '', '   '):
            with self.subTest(blank=blank), self.assertRaises(ValidationError):
                student.write({'student_id': blank})

    def test_contact_cannot_become_a_student_without_a_student_id(self):
        contact = self.Partner.create({'name': 'IDALU Family', 'contact_type': 'family'})
        with self.assertRaises(ValidationError):
            contact.write({'contact_type': 'student'})
        contact.write({'contact_type': 'student', 'student_id': next_student_id()})
        self.assertEqual(contact.contact_type, 'student')

    def test_student_created_before_the_rule_can_still_be_edited_and_leave(self):
        student = self._student_created_before_the_rule()
        student.write({'name': 'IDALU Legacy Renamed', 'contact_type': 'withdrawal', 'active': False})
        self.assertEqual(student.contact_type, 'withdrawal')

    def test_student_created_before_the_rule_gets_its_student_id_later(self):
        student = self._student_created_before_the_rule()
        student_id = next_student_id()
        student.write({'student_id': student_id})
        self.assertEqual(student.student_id, student_id)

    # --- unique --------------------------------------------------------------

    def test_student_id_is_stripped_and_a_blank_one_is_empty(self):
        student_id = next_student_id()
        self.assertEqual(self._student(student_id=f'  {student_id} ').student_id, student_id)
        family = self.Partner.create({'name': 'IDALU Blank', 'contact_type': 'family', 'student_id': '   '})
        self.assertFalse(family.student_id)

    def test_duplicate_student_id_is_refused_naming_its_holder(self):
        holder = self._student(name='IDALU Holder')
        with self.assertRaisesRegex(ValidationError, 'IDALU Holder'):
            self._student(name='IDALU Duplicate', student_id=f' {holder.student_id}')

    def test_student_id_of_an_archived_former_student_is_taken(self):
        former = self._student(name='IDALU Former Student', contact_type='alumni', active=False)
        with self.assertRaisesRegex(ValidationError, 'IDALU Former Student'):
            self._student(student_id=former.student_id)

    def test_duplicate_student_id_is_refused_on_write(self):
        holder, other = self._student(), self._student()
        with self.assertRaises(ValidationError):
            other.write({'student_id': holder.student_id})

    def test_writing_a_student_its_own_student_id_again_is_allowed(self):
        student = self._student()
        student.write({'student_id': student.student_id, 'name': 'IDALU Renamed'})
        self.assertEqual(student.name, 'IDALU Renamed')

    def test_database_refuses_a_duplicate_student_id(self):
        first, second = self._student(), self._student()
        with self.assertRaises(psycopg2.IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            self.env.cr.execute(
                "UPDATE res_partner SET student_id = %s WHERE id = %s", [first.student_id, second.id])

    def test_copying_a_contact_does_not_copy_its_student_id(self):
        family = self.Partner.create({'name': 'IDALU Copy', 'contact_type': 'family', 'student_id': next_student_id()})
        self.assertFalse(family.copy().student_id)

    # --- merging a duplicate -------------------------------------------------

    def test_merge_hands_the_former_student_id_to_the_new_contact(self):
        """The duplicate a returning former student leaves behind: the archived record holds the
        IDALU, the new active one has none. Merging into the new one moves the IDALU over."""
        former = self._student(name='IDALU Merge Former', contact_type='alumni', active=False)
        student_id = former.student_id
        current = self._student_created_before_the_rule()
        self.env['base.partner.merge.automatic.wizard']._merge((former | current).ids, current)
        self.assertFalse(former.exists())
        self.assertEqual(current.student_id, student_id)

    def test_merge_into_the_former_contact_keeps_its_student_id(self):
        former = self._student(name='IDALU Merge Keep', contact_type='alumni', active=False)
        student_id = former.student_id
        current = self._student_created_before_the_rule()
        self.env['base.partner.merge.automatic.wizard']._merge((former | current).ids, former)
        self.assertFalse(current.exists())
        self.assertEqual(former.student_id, student_id)
