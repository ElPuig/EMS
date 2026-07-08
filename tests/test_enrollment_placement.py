from datetime import date

from odoo.tests.common import TransactionCase


class TestEnrollmentPlacement(TransactionCase):
    """Fase 4: destination group, applicant admission on confirm, placement helper
    and the enrollment-proposal group suggestion."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Course = cls.env['ems.course']
        cls.course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2099, 'end': 2100, 'is_enrollment_default': True})
        cls.level = cls.env['ems.level'].create({'acronym': 'PLV', 'name': 'Placement Level'})
        cls.study = cls.env['ems.study'].create({
            'code': 'PLC001', 'acronym': 'PLST', 'name': 'Placement Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id})
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
