from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestEnrollmentPlacement(TransactionCase):
    """Fase 4: destination group, applicant admission on confirm, placement helper
    and the enrollment-proposal group suggestion. Also covers the cross-study
    proposal (enrolling a current student into a study other than its own)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Course = cls.env['ems.course']
        cls.course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2099, 'end': 2100, 'is_enrollment_default': True})
        cls.level, cls.study = create_level_study(cls, 'PLV', level={'name': 'Placement Level'}, study={
            'code': 'PLC001', 'acronym': 'PLST', 'name': 'Placement Study',
        })
        # First-course groups (A and B morning, A afternoon) and a second-course A.
        cls.g1a = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'shift': 'morning',
            'level_id': cls.level.id, 'study_id': cls.study.id})
        cls.g1b = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'shift': 'morning',
            'level_id': cls.level.id, 'study_id': cls.study.id})
        cls.g1a_aft = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'shift': 'afternoon',
            'level_id': cls.level.id, 'study_id': cls.study.id})
        cls.g2a = cls.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'shift': 'morning',
            'level_id': cls.level.id, 'study_id': cls.study.id})
        # Two subjects, each auto-creating its linked product.
        cls.subject1 = cls.env['ems.subject'].create({
            'code': 'PLSUB1', 'acronym': 'PS1', 'name': 'Placement Subject 1',
            'study_ids': [(6, 0, [cls.study.id])]})
        cls.subject2 = cls.env['ems.subject'].create({
            'code': 'PLSUB2', 'acronym': 'PS2', 'name': 'Placement Subject 2',
            'study_ids': [(6, 0, [cls.study.id])]})
        cls.template1 = cls.env['sale.order.template'].create({
            'name': 'Placement Template C1', 'ems_study_id': cls.study.id, 'study_year': 1})
        cls.template2 = cls.env['sale.order.template'].create({
            'name': 'Placement Template C2', 'ems_study_id': cls.study.id, 'study_year': 2})
        cls.Wizard = cls.env['ems.enrollment_proposal_wizard']

        # A second study (the cross-study destination) with its own first-course
        # groups, and a third one with no template at all: the situation a GEDAC
        # internal continuer lands in.
        cls.study2 = cls.env['ems.study'].create({
            'code': 'PLC002', 'acronym': 'PLS2', 'name': 'Placement Study 2',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id})
        cls.study_no_template = cls.env['ems.study'].create({
            'code': 'PLC003', 'acronym': 'PLS3', 'name': 'Placement Study 3',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id})
        cls.s2_g1a = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'shift': 'morning',
            'level_id': cls.level.id, 'study_id': cls.study2.id})
        cls.s2_g1a_aft = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'shift': 'afternoon',
            'level_id': cls.level.id, 'study_id': cls.study2.id})
        cls.template_s2 = cls.env['sale.order.template'].create({
            'name': 'Placement Template S2 C1', 'ems_study_id': cls.study2.id,
            'study_year': 1})

        # Only the secretary (and the academic admin) may cross studies; the tutor
        # keeps proposing same-study renewals.
        cls.secretary = cls._ems_user('plc_secretary', 'ems.group_secretary')
        cls.tutor = cls._ems_user('plc_tutor', 'ems.group_tutor')

    @classmethod
    def _ems_user(cls, login, group_xmlid):
        return cls.env['res.users'].create({
            'name': login,
            'login': login,
            'groups_id': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref(group_xmlid).id),
            ],
        })

    def _order(self, partner, group=False, shift='morning', lines=True):
        vals = {
            'partner_id': partner.id,
            'ems_study_id': self.study.id,
            'ems_course_id': self.course.id,
            'shift': shift,
        }
        if group:
            vals['ems_group_id'] = group.id
        order = self.env['sale.order'].create(vals)
        if lines:
            order.order_line = [
                (0, 0, {'product_id': self.subject1.product_id.id}),
                (0, 0, {'product_id': self.subject2.product_id.id}),
            ]
        return order

    # --- admission (applicant -> student) -----------------------------------

    def test_admit_converts_applicant(self):
        applicant = self.env['res.partner'].create({
            'name': 'Adm Applicant', 'contact_type': 'applicant', 'study_id': self.study.id})
        order = self._order(applicant, group=self.g1a)
        order._ems_admit_student()
        # Converted to student; study still active -> no placement yet (bulk later).
        self.assertEqual(applicant.contact_type, 'student')
        self.assertFalse(applicant.main_group_id)
        self.assertFalse(applicant.enrollment_ids)

    def test_admit_student_keeps_group(self):
        student = self.env['res.partner'].create({
            'name': 'Adm Student', 'contact_type': 'student', 'main_group_id': self.g2a.id})
        order = self._order(student, group=self.g1a)
        order._ems_admit_student()
        self.assertEqual(student.contact_type, 'student')
        self.assertEqual(student.main_group_id, self.g2a)

    # --- destination placement helper ---------------------------------------

    def test_placement_creates_enrollments_idempotent(self):
        student = self.env['res.partner'].create({
            'name': 'Plc Student', 'contact_type': 'student'})
        order = self._order(student, group=self.g1a)
        order._ems_apply_destination_placement()
        self.assertEqual(student.main_group_id, self.g1a)
        subjects = student.enrollment_ids.mapped('subject_id')
        self.assertIn(self.subject1, subjects)
        self.assertIn(self.subject2, subjects)
        self.assertEqual(len(student.enrollment_ids), 2)
        # Second run must not duplicate the ternary rows.
        order._ems_apply_destination_placement()
        self.assertEqual(len(student.enrollment_ids), 2)

    def test_placement_without_group_is_noop(self):
        student = self.env['res.partner'].create({
            'name': 'Plc NoGroup', 'contact_type': 'student'})
        order = self._order(student, group=False)
        order._ems_apply_destination_placement()
        self.assertFalse(student.main_group_id)
        self.assertFalse(student.enrollment_ids)

    # --- group mismatch warning ---------------------------------------------

    def test_group_shift_mismatch_warns(self):
        student = self.env['res.partner'].create({
            'name': 'Warn Student', 'contact_type': 'student'})
        order = self._order(student, group=self.g1a_aft, shift='morning')
        res = order._onchange_ems_group_id()
        self.assertTrue(res and 'warning' in res)

    # --- proposal group suggestion ------------------------------------------

    def test_suggested_group_continuing_student(self):
        student = self.env['res.partner'].create({
            'name': 'Sug Cont', 'contact_type': 'student',
            'main_group_id': self.g1a.id, 'study_id': self.study.id})
        # Same letter + shift in the destination course: PLST1A -> PLST2A.
        self.assertEqual(self.Wizard._ems_suggested_group(student, self.template2), self.g2a)

    def test_suggested_group_applicant_smallest_letter(self):
        applicant = self.env['res.partner'].create({
            'name': 'Sug App', 'contact_type': 'applicant',
            'study_id': self.study.id, 'preinscription_shift': 'morning'})
        # Lowest-letter first-course group of the granted shift.
        self.assertEqual(self.Wizard._ems_suggested_group(applicant, self.template1), self.g1a)

    def test_suggested_group_applicant_shift(self):
        applicant = self.env['res.partner'].create({
            'name': 'Sug App Aft', 'contact_type': 'applicant',
            'study_id': self.study.id, 'preinscription_shift': 'afternoon'})
        self.assertEqual(self.Wizard._ems_suggested_group(applicant, self.template1), self.g1a_aft)

    # --- proposal wizard end to end -----------------------------------------

    def test_proposal_preselects_first_course_for_applicant(self):
        applicant = self.env['res.partner'].create({
            'name': 'Presel App', 'contact_type': 'applicant',
            'study_id': self.study.id, 'preinscription_shift': 'morning'})
        wizard = self.Wizard.with_context(active_ids=applicant.ids).create({})
        # First-course template auto-selected (study_year=1 over study_year=2).
        self.assertEqual(wizard.template_id, self.template1)

    def test_proposal_preselects_by_entry_course(self):
        # An applicant granted 2nd course preselects the 2nd-course template.
        applicant = self.env['res.partner'].create({
            'name': 'C2 App', 'contact_type': 'applicant',
            'study_id': self.study.id, 'preinscription_shift': 'morning',
            'preinscription_course': '2'})
        wizard = self.Wizard.with_context(active_ids=applicant.ids).create({})
        self.assertEqual(wizard.template_id, self.template2)

    def test_proposal_onchange_suggests_group_for_applicant(self):
        applicant = self.env['res.partner'].create({
            'name': 'Onch App', 'contact_type': 'applicant',
            'study_id': self.study.id, 'preinscription_shift': 'afternoon'})
        wizard = self.Wizard.with_context(active_ids=applicant.ids).create({})
        wizard._onchange_suggest_group()
        self.assertEqual(wizard.ems_group_id, self.g1a_aft)

    # --- retroactive group suggestion on existing enrollments ---------------

    def test_order_suggest_group_continuing(self):
        student = self.env['res.partner'].create({
            'name': 'OSG Cont', 'contact_type': 'student', 'main_group_id': self.g1a.id})
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study.id,
            'ems_course_id': self.course.id, 'shift': 'morning',
            'sale_order_template_id': self.template2.id})
        self.assertEqual(order._ems_suggest_group(), self.g2a)

    # --- newcomers already converted into students ---------------------------

    def test_suggested_group_for_a_newcomer_already_turned_into_a_student(self):
        """Confirming the enrollment converts the applicant into a student, so by the
        time anybody suggests groups the 'applicant' branch no longer fires — and the
        continuing-student one has no current group to copy the letter from."""
        newcomer = self.env['res.partner'].create({
            'name': 'PL Converted Newcomer', 'contact_type': 'student',
            'study_id': self.study.id, 'preinscription_shift': 'morning'})
        self.assertFalse(newcomer.main_group_id)
        order = self.env['sale.order'].create({
            'partner_id': newcomer.id, 'ems_study_id': self.study.id,
            'ems_course_id': self.course.id, 'shift': 'morning',
            'sale_order_template_id': self.template2.id})
        self.assertEqual(order._ems_suggest_group(), self.g2a)

    def test_a_groupless_student_takes_the_shift_from_its_preinscription(self):
        """The order may carry no shift; the one granted at pre-enrollment stands in."""
        newcomer = self.env['res.partner'].create({
            'name': 'PL Converted Afternoon', 'contact_type': 'student',
            'study_id': self.study.id, 'preinscription_shift': 'afternoon'})
        order = self.env['sale.order'].create({
            'partner_id': newcomer.id, 'ems_study_id': self.study.id,
            'ems_course_id': self.course.id,
            'sale_order_template_id': self.template1.id})
        self.assertEqual(order._ems_suggest_group(), self.g1a_aft)

    def test_a_student_with_a_group_still_keeps_its_letter(self):
        """The fallback must not steal the continuing-student rule: a student that
        does have a group keeps matching by acronym."""
        student = self.env['res.partner'].create({
            'name': 'PL Keeps Letter', 'contact_type': 'student',
            'main_group_id': self.g1a.id})
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study.id,
            'ems_course_id': self.course.id, 'shift': 'morning',
            'sale_order_template_id': self.template2.id})
        self.assertEqual(order._ems_suggest_group(), self.g2a)

    # --- destination course read from the tutorship, with no template ---------

    def _tutorship(self, code, year):
        """A course-specific tutorship subject, sold by the template of that year."""
        subject = self.env['ems.subject'].create({
            'code': code, 'acronym': code, 'name': 'Tutorship %s' % code,
            'is_tutorship': True, 'study_ids': [(6, 0, [self.study.id])]})
        template = self.template1 if year == 1 else self.template2
        template.sale_order_template_line_ids = [
            (0, 0, {'product_id': subject.product_id.id})]
        return subject

    def _repeater_order(self, student, *subjects):
        """A re-enrolment: no template, only the subjects the student is retaking."""
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study.id,
            'ems_course_id': self.course.id, 'shift': 'morning'})
        order.order_line = [(0, 0, {'product_id': s.product_id.id}) for s in subjects]
        return order

    def test_suggested_group_reads_the_course_from_the_tutorship(self):
        """A repeater re-enrolling only in what they failed never goes through a
        template, so study_year is empty and the suggestion used to give up."""
        tutorship = self._tutorship('PLTUT2', 2)
        student = self.env['res.partner'].create({
            'name': 'PL Repeater', 'contact_type': 'student', 'main_group_id': self.g2a.id})
        order = self._repeater_order(student, tutorship)
        self.assertFalse(order.sale_order_template_id)
        self.assertEqual(order._ems_suggest_group(), self.g2a)

    def test_the_tutorship_wins_over_modules_pending_from_another_course(self):
        """Their lines cannot be matched against a template as a whole: they mix
        modules pending from an earlier course with the current one."""
        tutorship = self._tutorship('PLTUT2B', 2)
        self.template1.sale_order_template_line_ids = [
            (0, 0, {'product_id': self.subject1.product_id.id})]
        student = self.env['res.partner'].create({
            'name': 'PL Mixed', 'contact_type': 'student', 'main_group_id': self.g2a.id})
        order = self._repeater_order(student, tutorship, self.subject1)
        self.assertEqual(order._ems_suggest_group(), self.g2a)

    def test_no_suggestion_without_a_tutorship_line(self):
        student = self.env['res.partner'].create({
            'name': 'PL No Tutorship', 'contact_type': 'student', 'main_group_id': self.g2a.id})
        order = self._repeater_order(student, self.subject1)
        self.assertFalse(order._ems_suggest_group())

    def test_no_suggestion_when_two_tutorships_are_enrolled(self):
        """Ambiguous input must leave the group empty rather than pick a course."""
        first = self._tutorship('PLTUT1C', 1)
        second = self._tutorship('PLTUT2C', 2)
        student = self.env['res.partner'].create({
            'name': 'PL Two Tutorships', 'contact_type': 'student', 'main_group_id': self.g2a.id})
        order = self._repeater_order(student, first, second)
        self.assertFalse(order._ems_suggest_group())

    def test_no_suggestion_when_the_tutorship_is_sold_by_two_courses(self):
        """A tutorship shared by both templates pins nothing down."""
        tutorship = self._tutorship('PLTUTX', 2)
        self.template1.sale_order_template_line_ids = [
            (0, 0, {'product_id': tutorship.product_id.id})]
        student = self.env['res.partner'].create({
            'name': 'PL Shared Tutorship', 'contact_type': 'student', 'main_group_id': self.g2a.id})
        order = self._repeater_order(student, tutorship)
        self.assertFalse(order._ems_suggest_group())

    def test_the_template_still_wins_when_there_is_one(self):
        """The tutorship is a fallback, not a replacement."""
        self._tutorship('PLTUT1D', 1)
        student = self.env['res.partner'].create({
            'name': 'PL Templated', 'contact_type': 'student', 'main_group_id': self.g1a.id})
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study.id,
            'ems_course_id': self.course.id, 'shift': 'morning',
            'sale_order_template_id': self.template2.id})
        self.assertEqual(order._ems_suggest_group(), self.g2a)

    def test_action_suggest_fills_enrolled_skips_unenrolled(self):
        enrolled = self.env['res.partner'].create({
            'name': 'ASG Enrolled', 'contact_type': 'student', 'main_group_id': self.g1a.id})
        self.env['sale.order'].create({
            'partner_id': enrolled.id, 'ems_study_id': self.study.id,
            'ems_course_id': self.course.id, 'shift': 'morning',
            'sale_order_template_id': self.template2.id})
        missing = self.env['res.partner'].create({
            'name': 'ASG Missing', 'contact_type': 'student', 'main_group_id': self.g1a.id})
        self.assertEqual(enrolled.transition_status, 'unplaced')
        (enrolled + missing).action_suggest_destination_group()
        # Enrolled student gets the suggested group; unenrolled one is untouched.
        self.assertEqual(enrolled.ems_current_enrollment_id.ems_group_id, self.g2a)
        self.assertEqual(enrolled.transition_status, 'enrolled')
        self.assertFalse(missing.ems_current_enrollment_id)

    def test_portal_wizard_targets_applicant_directly(self):
        applicant = self.env['res.partner'].create({
            'name': 'Portal App', 'contact_type': 'applicant',
            'study_id': self.study.id, 'preinscription_shift': 'morning',
            'email': 'portal.app@example.com'})
        wizard = self.env['ems.portal.access.wizard'].with_context(
            active_ids=applicant.ids).create({})
        self.assertIn(applicant, wizard.student_ids)
        # The applicant itself is the recipient (personal email), no age/family logic.
        self.assertEqual(wizard._resolve_recipients(applicant), applicant)

    def test_proposal_writes_group_and_preinscription_shift(self):
        applicant = self.env['res.partner'].create({
            'name': 'Prop App', 'contact_type': 'applicant',
            'study_id': self.study.id, 'preinscription_shift': 'afternoon'})
        wizard = self.Wizard.with_context(active_ids=applicant.ids).create({
            'template_id': self.template1.id})
        wizard.action_create_enrollments()
        order = self.env['sale.order'].search([('partner_id', '=', applicant.id)], limit=1)
        self.assertTrue(order)
        self.assertEqual(order.ems_group_id, self.g1a_aft)
        self.assertEqual(order.shift, 'afternoon')

    # --- cross-study proposal ------------------------------------------------

    def _wizard_as(self, user, students, **vals):
        return self.Wizard.with_user(user).with_context(active_ids=students.ids).create(vals)

    def _student(self, name, study=None, group=None):
        return self.env['res.partner'].create({
            'name': name, 'contact_type': 'student',
            'study_id': study.id if study else False,
            'main_group_id': group.id if group else False})

    def test_no_template_opens_wizard_for_secretary(self):
        # The GEDAC continuer: its current study has no template, so the wizard
        # opens in free mode instead of raising, listing the whole catalogue.
        student = self._student('Cross NoTpl', self.study_no_template)
        wizard = self._wizard_as(self.secretary, student)
        self.assertTrue(wizard.allow_other_study)
        self.assertIn(self.template1, wizard.available_template_ids)
        self.assertIn(self.template_s2, wizard.available_template_ids)

    def test_no_template_still_raises_for_tutor(self):
        student = self._student('Cross NoTpl Tut', self.study_no_template)
        with self.assertRaises(UserError):
            self._wizard_as(self.tutor, student)

    def test_different_studies_open_in_free_mode_for_secretary(self):
        # Rayan (study A) and Quique (study B) both heading to the same destination.
        one = self._student('Cross Mixed 1', self.study, self.g1a)
        two = self._student('Cross Mixed 2', self.study2)
        wizard = self._wizard_as(self.secretary, one + two)
        self.assertTrue(wizard.allow_other_study)
        self.assertEqual(wizard.student_ids, one + two)

    def test_different_studies_still_raise_for_tutor(self):
        one = self._student('Cross Mixed T1', self.study, self.g1a)
        two = self._student('Cross Mixed T2', self.study2)
        with self.assertRaises(UserError):
            self._wizard_as(self.tutor, one + two)

    def test_free_mode_drops_study_and_course_filters(self):
        # A 2nd-course student normally sees only its own study from course 2 on;
        # free mode must also drop the study_year floor, or a 4th-course ESO
        # student would never reach a 1st-course SMX template.
        student = self._student('Cross Filters', self.study, self.g2a)
        wizard = self._wizard_as(self.secretary, student)
        self.assertEqual(wizard.available_template_ids, self.template2)
        wizard.allow_other_study = True
        self.assertIn(self.template1, wizard.available_template_ids)
        self.assertIn(self.template_s2, wizard.available_template_ids)

    def test_tutor_cannot_write_allow_other_study(self):
        student = self._student('Cross Tutor Write', self.study, self.g1a)
        wizard = self._wizard_as(self.tutor, student)
        # The tutor still renders the dialog: the compute reads the restricted
        # flag through sudo, so its own template list stays readable.
        self.assertIn(self.template1, wizard.available_template_ids)
        with self.assertRaises(AccessError):
            wizard.allow_other_study = True

    def test_cross_study_enrollment_uses_destination_study(self):
        # The order must be booked against the template's study, not the origin
        # one, or it would carry the wrong numbering and authorizations.
        student = self._student('Cross Dest', self.study, self.g1a)
        wizard = self._wizard_as(self.secretary, student)
        wizard.allow_other_study = True
        wizard.template_id = self.template_s2
        wizard.ems_group_id = self.s2_g1a
        wizard.action_create_enrollments()
        order = self.env['sale.order'].search([('partner_id', '=', student.id)], limit=1)
        self.assertEqual(order.ems_study_id, self.study2)
        self.assertEqual(order.ems_group_id, self.s2_g1a)

    def test_cross_study_shift_comes_from_destination_group(self):
        # Rayan: morning in his current group, afternoon in the destination one.
        student = self._student('Cross Shift', self.study, self.g1a)
        wizard = self._wizard_as(self.secretary, student)
        wizard.allow_other_study = True
        wizard.template_id = self.template_s2
        wizard.ems_group_id = self.s2_g1a_aft
        wizard.action_create_enrollments()
        order = self.env['sale.order'].search([('partner_id', '=', student.id)], limit=1)
        self.assertEqual(order.shift, 'afternoon')

    def test_tutor_cannot_cross_study_through_the_orm(self):
        # The checkbox is the UI gate; the server must refuse the cross-study
        # template even when it is set directly (the view domain is not a rule).
        student = self._student('Cross Tutor Rpc', self.study, self.g1a)
        wizard = self._wizard_as(self.tutor, student)
        wizard.template_id = self.template_s2
        with self.assertRaises(UserError):
            wizard.action_create_enrollments()

    # --- GEDAC destination on the active student -----------------------------

    def _continuer(self, name='GEDAC Cont', shift='afternoon', course='1'):
        """An active student of `study` that GEDAC reassigned to `study2`.

        Its current group is B/morning and the destination has no B letter, so it
        reproduces both traps: the letter cannot be kept, and the old group's shift
        is not the granted one.
        """
        return self.env['res.partner'].create({
            'name': name, 'contact_type': 'student',
            'study_id': self.study.id, 'main_group_id': self.g1b.id,
            'preinscription_study_id': self.study2.id,
            'preinscription_shift': shift, 'preinscription_course': course,
        })

    def test_destination_study_prefers_the_gedac_assignment(self):
        self.assertEqual(self._continuer()._ems_destination_study(), self.study2)

    def test_destination_study_falls_back_to_the_own_study(self):
        # An applicant's destination already lives in study_id, and a continuer with
        # no assignment simply renews its own study.
        applicant = self.env['res.partner'].create({
            'name': 'Dest App', 'contact_type': 'applicant', 'study_id': self.study2.id})
        self.assertEqual(applicant._ems_destination_study(), self.study2)
        renewing = self._student('Dest Cont', self.study, self.g1a)
        self.assertEqual(renewing._ems_destination_study(), self.study)

    def test_templates_offer_the_destination_to_the_secretary(self):
        # The destination's 1st-course template must show up even though the student
        # sits in another study: the study_year floor cannot hide it.
        templates = self.Wizard.with_user(self.secretary)._ems_templates_for(
            self._continuer(), allow_other_study=False)
        self.assertIn(self.template_s2, templates)
        self.assertNotIn(self.template1, templates)

    def test_templates_keep_the_own_study_for_the_tutor(self):
        # The tutor cannot cross studies, so it must not be offered a destination
        # template the server guard would reject on create.
        templates = self.Wizard.with_user(self.tutor)._ems_templates_for(
            self._continuer(), allow_other_study=False)
        self.assertNotIn(self.template_s2, templates)
        self.assertIn(self.template1, templates)

    def test_proposal_preselects_the_granted_template(self):
        # No checkbox needed: the assignment drives both study and course.
        wizard = self._wizard_as(self.secretary, self._continuer())
        self.assertEqual(wizard.template_id, self.template_s2)

    def test_suggested_group_crossing_uses_the_granted_shift(self):
        # Trap 1: keeping the current letter (B) finds nothing in the destination.
        # The granted shift must pick the lowest-letter group instead.
        group = self.Wizard._ems_suggested_group(self._continuer(), self.template_s2)
        self.assertEqual(group, self.s2_g1a_aft)

    def test_crossing_enrollment_uses_the_granted_shift(self):
        # Trap 2: the shift comes from the assignment, never from the old group.
        student = self._continuer()
        self._wizard_as(self.secretary, student).action_create_enrollments()
        order = self.env['sale.order'].search([('partner_id', '=', student.id)], limit=1)
        self.assertEqual(order.ems_study_id, self.study2)
        self.assertEqual(order.ems_group_id, self.s2_g1a_aft)
        self.assertEqual(order.shift, 'afternoon')

    def test_admit_clears_the_consumed_assignment(self):
        # Once enrolled into the granted study the assignment is spent: the "GEDAC
        # assignment" filter must only list students still pending enrollment.
        student = self._continuer()
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study2.id,
            'ems_course_id': self.course.id, 'shift': 'afternoon'})
        order._ems_admit_student()
        self.assertFalse(student.preinscription_study_id)
        self.assertFalse(student.preinscription_shift)
        self.assertFalse(student.preinscription_course)

    def test_admit_keeps_an_unconsumed_assignment(self):
        # Another study was confirmed (the manual escape hatch): the GEDAC assignment
        # is still pending and must survive.
        student = self._continuer()
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.study.id,
            'ems_course_id': self.course.id, 'shift': 'morning'})
        order._ems_admit_student()
        self.assertEqual(student.preinscription_study_id, self.study2)
