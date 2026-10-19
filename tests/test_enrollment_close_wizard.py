import base64
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import (
    create_level_study_group,
    create_role_user,
    mock_outgoing_email,
    next_student_id,
)


class TestEnrollmentCloseWizard(TransactionCase):
    """ems.enrollment_close_wizard (issue #643): one action per person holding an enrollment
    nobody confirmed. See docs/en/developers/enrollment/close_unconfirmed_wizard.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Withdrawals and ex-student exits warn the Google account and revoke portals.
        mock_outgoing_email(cls)
        Course = cls.env['ems.course']
        cls.past_course = Course.create({'start': 2096, 'end': 2097})
        cls.current_course = Course.create({'start': 2098, 'end': 2099})
        cls.env.company.current_course_id = cls.current_course
        cls.next_course = Course.create({'start': 2099, 'end': 2100})
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'ECW', level={'name': 'Close Level'}, study={
            'code': 'ECW001', 'acronym': 'ECWS', 'name': 'Close Study',
        })
        cls.secretary = create_role_user(cls, 'secretary', 'ecw_secretary')
        cls.teacher = create_role_user(cls, 'teacher', 'ecw_teacher')

    # --- fixtures ------------------------------------------------------------

    def _partner(self, name, contact_type, **vals):
        return self.env['res.partner'].create(dict({
            'name': name, 'contact_type': contact_type, 'student_id': next_student_id(),
        }, **vals))

    def _order(self, partner, state='sent', course=None):
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'ems_course_id': (course or self.current_course).id,
            'ems_study_id': self.study.id,
        })
        if state != 'draft':
            order.write({'state': state})
        return order

    def _portal_user(self, partner, login):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': partner.name, 'login': login, 'email': login, 'partner_id': partner.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })

    def _ex_student(self, name, graduated):
        """An ex-student whose new offer has been sent: sale.order._ems_offer_to_ex_student()
        has already turned them into an applicant and cleared their exit data."""
        exit_type = 'graduation' if graduated else 'withdrawal'
        partner = self._partner(name, 'alumni' if graduated else 'withdrawal', active=False,
                                has_graduated=graduated, exit_type=exit_type,
                                exit_course_id=self.past_course.id)
        self.env['ems.student.year_record'].create({
            'student_id': partner.id, 'course_id': self.past_course.id,
            'study_id': self.study.id, 'study_name': self.study.display_name,
            'exit_type': exit_type, 'exit_date': '2097-06-20',
        })
        order = self._order(partner)
        self.assertEqual(partner.contact_type, 'applicant')
        self.assertFalse(partner.exit_type)
        return partner, order

    def _wizard(self, records, user=None):
        Wizard = self.env['ems.enrollment_close_wizard']
        if user:
            Wizard = Wizard.with_user(user)
        return Wizard.with_context(active_model=records._name, active_ids=records.ids).create({})

    def _action_of(self, wizard, partner):
        return wizard.line_ids.filtered(lambda line: line.partner_id == partner).action

    # --- one action per person ---------------------------------------------------

    def test_new_applicant_is_deleted_with_its_enrollment_and_portal_user(self):
        applicant = self._partner('ECW New Applicant', 'applicant', email='ecw_new@example.com')
        user = self._portal_user(applicant, 'ecw_new@example.com')
        order = self._order(applicant)
        wizard = self._wizard(order, user=self.secretary)
        self.assertEqual(self._action_of(wizard, applicant), 'delete')
        wizard.action_apply()
        self.assertFalse(applicant.exists())
        self.assertFalse(order.exists())
        self.assertFalse(user.exists())

    def test_draft_enrollments_are_handled_too(self):
        applicant = self._partner('ECW Draft Applicant', 'applicant')
        order = self._order(applicant, state='draft')
        self._wizard(order).action_apply()
        self.assertFalse(applicant.exists())

    def test_graduated_ex_student_goes_back_to_alumni(self):
        partner, order = self._ex_student('ECW Graduate', graduated=True)
        wizard = self._wizard(order)
        self.assertEqual(self._action_of(wizard, partner), 'ex_student')
        wizard.action_apply()
        self.assertEqual(order.state, 'cancel')
        self.assertEqual(partner.contact_type, 'alumni')
        self.assertFalse(partner.active)
        # The exit data the offer cleared comes back from the academic history.
        self.assertEqual(partner.exit_type, 'graduation')
        self.assertEqual(partner.exit_course_id, self.past_course)
        self.assertEqual(str(partner.exit_date), '2097-06-20')
        self.assertFalse(partner.study_id)

    def test_ex_student_without_title_goes_back_to_withdrawal(self):
        partner, order = self._ex_student('ECW Returner', graduated=False)
        self._wizard(order).action_apply()
        self.assertEqual(partner.contact_type, 'withdrawal')
        self.assertEqual(partner.exit_type, 'withdrawal')
        self.assertFalse(partner.active)

    def test_student_without_group_is_withdrawn(self):
        student = self._partner('ECW No Group', 'student')
        order = self._order(student)
        wizard = self._wizard(order)
        self.assertEqual(self._action_of(wizard, student), 'withdraw')
        wizard.exit_reason = 'Enrollment never formalised'
        wizard.action_apply()
        self.assertEqual(order.state, 'cancel')
        self.assertEqual(student.contact_type, 'withdrawal')
        self.assertEqual(student.exit_type, 'withdrawal')
        self.assertEqual(student.exit_course_id, self.current_course)
        self.assertEqual(student.exit_reason, 'Enrollment never formalised')
        self.assertFalse(student.active)
        # The withdrawal wizard's own steps: the academic history is frozen.
        self.assertTrue(student.year_record_ids.filtered(
            lambda record: record.course_id == self.current_course))

    def test_student_with_group_only_loses_the_enrollment(self):
        student = self._partner('ECW In Group', 'student', main_group_id=self.group.id)
        order = self._order(student)
        wizard = self._wizard(order)
        self.assertEqual(self._action_of(wizard, student), 'cancel')
        wizard.action_apply()
        self.assertEqual(order.state, 'cancel')
        self.assertEqual(student.contact_type, 'student')
        self.assertTrue(student.active)

    def test_student_with_a_confirmed_enrollment_only_loses_the_other_one(self):
        """Confirmed for the running course, still waiting for a group: staying."""
        student = self._partner('ECW Confirmed Elsewhere', 'student')
        confirmed = self._order(student)
        confirmed.write({'state': 'sale'})
        pending = self._order(student, course=self.next_course)
        wizard = self._wizard(pending)
        self.assertEqual(self._action_of(wizard, student), 'cancel')
        wizard.action_apply()
        self.assertEqual(pending.state, 'cancel')
        self.assertEqual(confirmed.state, 'sale')
        self.assertEqual(student.contact_type, 'student')

    def test_expelled_only_loses_the_enrollment(self):
        expelled = self._partner('ECW Expelled', 'expelled', active=False)
        order = self._order(expelled)
        wizard = self._wizard(order)
        self.assertEqual(self._action_of(wizard, expelled), 'cancel')
        wizard.action_apply()
        self.assertEqual(order.state, 'cancel')
        self.assertEqual(expelled.contact_type, 'expelled')

    def test_applicant_with_a_corporate_account_is_archived_not_deleted(self):
        applicant = self._partner('ECW Corporate', 'applicant', student_email='ecw_corp@example.com')
        order = self._order(applicant)
        wizard = self._wizard(order)
        self.assertEqual(self._action_of(wizard, applicant), 'archive')
        wizard.action_apply()
        self.assertTrue(applicant.exists())
        self.assertFalse(applicant.active)
        self.assertEqual(order.state, 'cancel')

    def test_enrollment_with_a_payment_is_left_for_review(self):
        applicant = self._partner('ECW Paid', 'applicant')
        order = self._order(applicant)
        with patch.object(type(order), '_ems_has_payment', lambda orders: bool(orders)):
            wizard = self._wizard(order)
            self.assertEqual(self._action_of(wizard, applicant), 'review')
            wizard.action_apply()
        self.assertTrue(applicant.exists())
        self.assertEqual(order.state, 'sent')

    def test_failed_delete_falls_back_to_archive(self):
        applicant = self._partner('ECW Undeletable', 'applicant')
        order = self._order(applicant)
        wizard = self._wizard(order)
        with patch.object(type(applicant), 'unlink', side_effect=Exception('still referenced')):
            result = wizard.action_apply()
        self.assertTrue(applicant.exists())
        self.assertFalse(applicant.active)
        self.assertEqual(order.state, 'cancel')
        self.assertEqual(result['res_id'], wizard.id)
        self.assertIn('still referenced', wizard.result_html)
        log = base64.b64decode(wizard.log_file).decode('utf-8-sig').splitlines()
        self.assertIn('Delete the person,Archive', log[1])
        self.assertIn('still referenced', log[1])

    # --- launched from Pre-inscripció ------------------------------------------------

    def test_applicants_without_enrollment_are_deleted_from_the_applicant_list(self):
        applicant = self._partner('ECW Never Offered', 'applicant')
        wizard = self._wizard(applicant)
        self.assertEqual(self._action_of(wizard, applicant), 'delete')
        wizard.action_apply()
        self.assertFalse(applicant.exists())

    def test_without_enrollment_filter(self):
        offered = self._partner('ECW Filter Offered', 'applicant')
        self._order(offered)
        cancelled = self._partner('ECW Filter Cancelled', 'applicant')
        self._order(cancelled).write({'state': 'cancel'})
        never = self._partner('ECW Filter Never', 'applicant')
        people = offered + cancelled + never
        Partner = self.env['res.partner']
        self.assertEqual(Partner.search([('id', 'in', people.ids), ('ems_has_enrollment', '=', False)]),
                         cancelled + never)
        self.assertEqual(Partner.search([('id', 'in', people.ids), ('ems_has_enrollment', '=', True)]),
                         offered)
        self.assertEqual(people.mapped('ems_has_enrollment'), [True, False, False])

    # --- preview and access ------------------------------------------------------------

    def test_one_line_per_person_whatever_the_number_of_enrollments(self):
        applicant = self._partner('ECW Two Offers', 'applicant')
        orders = self._order(applicant) + self._order(applicant, state='draft', course=self.next_course)
        wizard = self._wizard(orders)
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.order_ids, orders)

    def test_confirmed_and_cancelled_enrollments_are_ignored(self):
        student = self._partner('ECW Only Confirmed', 'student', main_group_id=self.group.id)
        confirmed = self._order(student)
        confirmed.write({'state': 'sale'})
        with self.assertRaises(UserError):
            self._wizard(confirmed)

    def test_refused_to_a_teacher(self):
        applicant = self._partner('ECW Refused', 'applicant')
        order = self._order(applicant)
        with self.assertRaises(UserError):
            self._wizard(order, user=self.teacher)

    # --- summary before and after ----------------------------------------------------------

    def test_preview_counts_people_and_enrollments_per_action(self):
        new = self._partner('ECW Preview New', 'applicant')
        student = self._partner('ECW Preview Student', 'student', main_group_id=self.group.id)
        orders = self._order(new) + self._order(student)
        wizard = self._wizard(orders)
        self.assertIn('People: 2. Enrollments: 2.', wizard.preview_html)
        self.assertIn('Delete the person: 1', wizard.preview_html)
        self.assertIn('Cancel the enrollment only: 1', wizard.preview_html)
        self.assertNotIn('Withdraw', wizard.preview_html)
        self.assertFalse(wizard.has_withdrawals)

    def test_result_and_log_after_applying(self):
        new = self._partner('ECW Result New', 'applicant')
        student = self._partner('ECW Result No Group', 'student')
        orders = self._order(new) + self._order(student)
        wizard = self._wizard(orders)
        self.assertTrue(wizard.has_withdrawals)
        wizard.action_apply()
        self.assertIn('People processed: 2.', wizard.result_html)
        self.assertIn('Withdraw: 1', wizard.result_html)
        log = base64.b64decode(wizard.log_file).decode('utf-8-sig').splitlines()
        self.assertEqual(len(log), 3)
        rows = {row.split(',')[0]: row for row in log[1:]}
        self.assertIn('Delete the person,Delete the person', rows['ECW Result New'])
        self.assertIn('Withdraw,Withdraw', rows['ECW Result No Group'])
        self.assertTrue(wizard.log_file_name.endswith('.csv'))
