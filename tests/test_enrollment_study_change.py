from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import create_level_study, create_role_user, mock_outgoing_email, next_student_id


class TestEnrollmentStudyChange(TransactionCase):
    """Issue #875: moving a confirmed enrollment to another study (wizard), the guard that keeps a
    student's study in line with their enrollment, and the realignment the migration runs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        # Its own course, made the running one: the guard reads the enrollment in force.
        cls.course = cls.env['ems.course'].create({'start': 2098, 'end': 2099})
        cls.env.company.current_course_id = cls.course.id
        cls.level, cls.old_study = create_level_study(cls, 'SCO')
        cls.new_study = cls.env['ems.study'].create({
            'code': 'SCN-01', 'acronym': 'SCN', 'name': 'Study Change New', 'date': '2026-01-01',
            'deprecated': False, 'level_id': cls.level.id})
        cls.old_group = cls._group(cls.old_study, 2, 'morning')
        cls.new_group = cls._group(cls.new_study, 2, 'morning')
        cls.new_group_afternoon = cls._group(cls.new_study, 2, 'afternoon')
        cls.new_group_first = cls._group(cls.new_study, 1, 'morning')
        cls.old_subjects = cls._subjects(cls.old_study, 'SCO', 2)
        cls.new_subjects = cls._subjects(cls.new_study, 'SCN', 3)
        cls.old_template = cls._template(cls.old_study, 2, cls.old_subjects)
        cls.new_template = cls._template(cls.new_study, 2, cls.new_subjects)
        cls.new_template_first = cls._template(cls.new_study, 1, cls.new_subjects[:1])
        cls.generic = cls.env.ref('ems.product_generic_enrollment').product_variant_id
        cls.secretary = create_role_user(cls, 'secretary', 'sc_secretary', email='sc_secretary@example.com')

    @classmethod
    def _group(cls, study, course, shift):
        return cls.env['ems.group'].create({
            'course': course, 'acronym': 'A', 'shift': shift, 'level_id': cls.level.id,
            'study_id': study.id})

    @classmethod
    def _subjects(cls, study, prefix, count):
        return cls.env['ems.subject'].create([{
            'code': f'{prefix}SUB{index}', 'acronym': f'{prefix}{index}', 'name': f'{prefix} subject {index}',
            'study_ids': [(6, 0, study.ids)]} for index in range(count)])

    @classmethod
    def _template(cls, study, year, subjects):
        return cls.env['sale.order.template'].create({
            'name': f'{study.acronym}-{year}', 'ems_study_id': study.id, 'study_year': year,
            'sale_order_template_line_ids': [
                (0, 0, {'product_id': subject.product_id.id, 'name': subject.name}) for subject in subjects],
        })

    def _confirmed_order(self):
        """A student of the old study with a confirmed enrollment, placed in the old group."""
        student = self.env['res.partner'].create({
            'name': 'Study Change Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'birth_date': '2000-01-01', 'study_id': self.old_study.id, 'main_group_id': self.old_group.id})
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': self.old_study.id, 'ems_course_id': self.course.id,
            'shift': 'morning', 'ems_group_id': self.old_group.id,
            'sale_order_template_id': self.old_template.id,
            'order_line': [(0, 0, {'product_id': self.generic.id})] + [
                (0, 0, {'product_id': subject.product_id.id}) for subject in self.old_subjects],
        })
        order.action_confirm()
        return order

    def _wizard(self, order, **values):
        wizard = self.env['ems.enrollment_study_change_wizard'].with_user(self.secretary).create({
            'order_id': order.id, 'study_id': self.new_study.id, **values})
        return wizard

    def _quantities(self, order):
        return {line.product_id: line.product_uom_qty for line in order.order_line}

    # --- wizard ----------------------------------------------------------------------------------

    def test_wizard_defaults_to_same_course_template_and_shift_group(self):
        order = self._confirmed_order()
        wizard = self._wizard(order)
        self.assertEqual(wizard.template_id, self.new_template)
        self.assertEqual(wizard.group_id, self.new_group)
        self.assertEqual(wizard.adjustment_amount, 0)

    def test_change_realigns_the_enrollment(self):
        order = self._confirmed_order()
        invoices = order.invoice_ids
        total = order.amount_total
        self._wizard(order).action_apply()
        self.assertEqual(order.ems_study_id, self.new_study)
        self.assertEqual(order.sale_order_template_id, self.new_template)
        self.assertEqual(order.ems_group_id, self.new_group)
        self.assertEqual(order.name, order._get_dynamic_enrollment_name())
        self.assertIn('/SCN/', order.name, "Renamed after the new study")
        quantities = self._quantities(order)
        self.assertEqual(quantities[self.generic], 1, "Generic lines are never touched")
        for subject in self.old_subjects:
            self.assertEqual(quantities[subject.product_id], 0)
        for subject in self.new_subjects:
            self.assertEqual(quantities[subject.product_id], 1)
        self.assertEqual(order.amount_total, total)
        self.assertEqual(order.invoice_ids, invoices, "No adjustment, no new invoice")

    def test_change_places_the_student_without_freezing_the_year(self):
        order = self._confirmed_order()
        student = order.partner_id
        Enrollment = self.env['ems.enrollment'].sudo()
        self.assertTrue(Enrollment.search_count([('student_id', '=', student.id), ('group_id', '=', self.old_group.id)]))
        self._wizard(order).action_apply()
        self.assertEqual(student.main_group_id, self.new_group)
        self.assertEqual(student.study_id, self.new_study)
        enrollments = Enrollment.search([('student_id', '=', student.id)])
        self.assertEqual(enrollments.subject_id, self.new_subjects)
        self.assertEqual(enrollments.group_id, self.new_group)
        self.assertFalse(self.env['ems.student.year_record'].sudo().search_count([('student_id', '=', student.id)]),
                         "A change of studies during the course records no year")

    def test_graded_old_enrollment_is_kept(self):
        order = self._confirmed_order()
        graded = self.old_subjects[0]
        GradeSession = type(self.env['ems.grade_session'])
        with patch.object(GradeSession, '_ems_has_scored_grades',
                          lambda self, student_id, group_id, subject_id: subject_id == graded.id):
            self._wizard(order).action_apply()
        kept = self.env['ems.enrollment'].sudo().search([
            ('student_id', '=', order.partner_id.id), ('group_id', '=', self.old_group.id)])
        self.assertEqual(kept.subject_id, graded)

    def test_positive_adjustment_is_invoiced(self):
        order = self._confirmed_order()
        before = order.invoice_ids
        self._wizard(order, adjustment_amount=40).action_apply()
        new = order.invoice_ids - before
        self.assertEqual(len(new), 1)
        self.assertEqual((new.move_type, new.state, new.amount_total), ('out_invoice', 'posted', 40))

    def test_negative_adjustment_is_a_credit_note(self):
        order = self._confirmed_order()
        before = order.invoice_ids
        self._wizard(order, adjustment_amount=-25).action_apply()
        new = order.invoice_ids - before
        self.assertEqual(len(new), 1)
        self.assertEqual((new.move_type, new.state, new.amount_total), ('out_refund', 'posted', 25))

    def test_only_a_confirmed_enrollment_changes_study(self):
        order = self._confirmed_order()
        order._action_cancel()
        with self.assertRaises(UserError):
            self._wizard(order).action_apply()

    def test_the_same_study_is_refused(self):
        order = self._confirmed_order()
        with self.assertRaises(UserError):
            self._wizard(order, study_id=self.old_study.id).action_apply()

    # --- guard (point 2.2) -----------------------------------------------------------------------

    def test_guard_refuses_a_study_other_than_the_enrollment(self):
        student = self._confirmed_order().partner_id.with_user(self.secretary)
        with self.assertRaises(UserError):
            student.write({'study_id': self.new_study.id})
        with self.assertRaises(UserError):
            student.write({'main_group_id': self.new_group.id})

    def test_guard_allows_the_enrollment_study_and_students_without_enrollment(self):
        student = self._confirmed_order().partner_id.with_user(self.secretary)
        other_group = self._group(self.old_study, 2, 'afternoon')
        student.write({'main_group_id': other_group.id})
        self.assertEqual(student.main_group_id, other_group)
        loose = self.env['res.partner'].create({
            'name': 'No Enrollment Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'study_id': self.old_study.id, 'main_group_id': self.old_group.id})
        loose.with_user(self.secretary).write({'study_id': self.new_study.id})
        self.assertEqual(loose.study_id, self.new_study)

    # --- realignment of existing data (migration) ------------------------------------------------

    def test_realign_follows_the_group_and_the_subjects_attended(self):
        order = self._confirmed_order()
        student = order.partner_id
        # What was done by hand before: the student moved, the enrollment left behind.
        student.sudo().write({'main_group_id': self.new_group.id, 'study_id': self.new_study.id})
        Enrollment = self.env['ems.enrollment'].sudo()
        Enrollment.search([('student_id', '=', student.id)]).unlink()
        attended = self.new_subjects[:2]
        Enrollment.create([{'student_id': student.id, 'group_id': self.new_group.id, 'subject_id': subject.id}
                           for subject in attended])
        self.env['sale.order']._ems_realign_study_with_group()
        self.assertEqual(order.ems_study_id, self.new_study)
        self.assertEqual(order.sale_order_template_id, self.new_template)
        self.assertEqual(order.ems_group_id, self.new_group)
        self.assertIn('/SCN/', order.name)
        self.assertEqual(order._ems_module_lines().filtered('product_uom_qty').product_id, attended.product_id)
        self.assertEqual(Enrollment.search([('student_id', '=', student.id)]).subject_id, attended,
                         "The realignment never touches the student")

    def test_realign_leaves_consistent_enrollments_alone(self):
        order = self._confirmed_order()
        lines = self._quantities(order)
        self.env['sale.order']._ems_realign_study_with_group()
        self.assertEqual(order.ems_study_id, self.old_study)
        self.assertEqual(self._quantities(order), lines)
