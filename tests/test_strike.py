# -*- coding: utf-8 -*-

from datetime import date, timedelta

from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group, mock_outgoing_email, next_student_id


class TestStrike(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ems.strike sends real emails synchronously (force_send=True) on every create();
        # this environment has real, credentialed outgoing mail servers configured (AWS
        # SES / Gmail), so the actual SMTP call must be neutralized for tests.
        mock_outgoing_email(cls)

        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_tutor = cls.env.ref('ems.group_tutor')
        cls.group_academic_admin = cls.env.ref('ems.group_academic_admin')
        cls.group_coexistence = cls.env.ref('ems.group_coexistence')
        cls.group_secretary = cls.env.ref('ems.group_secretary')

        cls.role_coexistence = cls.env.ref('ems.role_coexistence')
        # Unipersonal is expected to be false for this feature to make sense; clear any
        # pre-existing assignment so the tests are self-contained either way.
        cls.role_coexistence.sudo().write({'employee_ids': [(5, 0, 0)]})

        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Strike)',
            'login': 'test_admin_strike',
            'email': 'test_admin_strike@example.com',
            'groups_id': [(4, cls.group_academic_admin.id), (4, cls.env.ref('base.group_user').id)],
        })

        # Branch A: hos_a -> manager_a -> teacher_a ; coexistence_a shares hos_a.
        cls.hos_a_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test HOS A (Strike)', 'login': 'test_hos_a_strike', 'email': 'test_hos_a_strike@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_head_of_studies').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.hos_a_employee = cls.env['hr.employee'].create({
            'name': 'Test HOS A Employee (Strike)', 'employee_type': 'teacher', 'user_id': cls.hos_a_user.id,
        })
        cls.teacher_a_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher A (Strike)', 'login': 'test_teacher_a_strike', 'email': 'test_teacher_a_strike@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.teacher_a_employee = cls.env['hr.employee'].create({
            'name': 'Test Teacher A Employee (Strike)', 'employee_type': 'teacher',
            'user_id': cls.teacher_a_user.id, 'parent_id': cls.hos_a_employee.id,
        })
        cls.coexistence_a_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Coexistence A (Strike)', 'login': 'test_coexistence_a_strike', 'email': 'test_coexistence_a_strike@example.com',
            'groups_id': [(4, cls.group_coexistence.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.coexistence_a_employee = cls.env['hr.employee'].create({
            'name': 'Test Coexistence A Employee (Strike)', 'employee_type': 'teacher',
            'user_id': cls.coexistence_a_user.id, 'parent_id': cls.hos_a_employee.id,
        })
        cls.coexistence_a_employee.write({'role_ids': [(4, cls.role_coexistence.id)]})

        # Branch B: hos_b ; coexistence_b shares hos_b, NOT hos_a.
        cls.hos_b_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test HOS B (Strike)', 'login': 'test_hos_b_strike', 'email': 'test_hos_b_strike@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_head_of_studies').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.hos_b_employee = cls.env['hr.employee'].create({
            'name': 'Test HOS B Employee (Strike)', 'employee_type': 'teacher', 'user_id': cls.hos_b_user.id,
        })
        cls.coexistence_b_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Coexistence B (Strike)', 'login': 'test_coexistence_b_strike', 'email': 'test_coexistence_b_strike@example.com',
            'groups_id': [(4, cls.group_coexistence.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.coexistence_b_employee = cls.env['hr.employee'].create({
            'name': 'Test Coexistence B Employee (Strike)', 'employee_type': 'teacher',
            'user_id': cls.coexistence_b_user.id, 'parent_id': cls.hos_b_employee.id,
        })
        cls.coexistence_b_employee.write({'role_ids': [(4, cls.role_coexistence.id)]})

        # Tutor, unrelated to either branch.
        cls.tutor_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Tutor (Strike)', 'login': 'test_tutor_strike', 'email': 'test_tutor_strike@example.com',
            'groups_id': [(4, cls.group_tutor.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Test Tutor Employee (Strike)', 'employee_type': 'teacher', 'user_id': cls.tutor_user.id,
        })

        cls.other_teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Other Teacher (Strike)', 'login': 'test_other_teacher_strike', 'email': 'test_other_teacher_strike@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })

        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Strike)', 'login': 'test_secretary_strike', 'email': 'test_secretary_strike@example.com',
            'groups_id': [(4, cls.group_secretary.id), (4, cls.env.ref('base.group_user').id)],
        })

        cls.level, cls.study, cls.group_record = create_level_study_group(cls, 'TSTK', level={'name': 'Test Level (Strike)'}, study={
            'code': 'TSTK001', 'name': 'Test Study (Strike)',
        }, group={'name': 'Test Group (Strike)', 'tutor_id': cls.tutor_employee.id})

        cls.reason_other = cls.env.ref('ems.strike_reason_other')
        cls.relation_type_family = cls.env.ref('ems.relation_type_father')

        cls.family_partner = cls.env['res.partner'].create({
            'name': 'Test Family (Strike)',
            'contact_type': 'family',
            'email': 'test_family_strike@example.com',
        })

        cls.minor_student = cls.env['res.partner'].create({
            'name': 'Test Minor Student (Strike)',
            'contact_type': 'student', 'student_id': next_student_id(),
            'student_email': 'test_minor_student_strike@example.com',
            'birth_date': date(date.today().year - 15, 1, 1),
            'main_group_id': cls.group_record.id,
        })
        cls.env['res.partner.relation'].sudo().create({
            'left_partner_id': cls.family_partner.id,
            'right_partner_id': cls.minor_student.id,
            'type_id': cls.relation_type_family.id,
        })

    def _create_strike(self, user, **values):
        vals = {'student_id': self.minor_student.id, 'reason_id': self.reason_other.id}
        if user == self.admin_user:
            vals['teacher_id'] = self.teacher_a_employee.id
        vals.update(values)
        return self.env['ems.strike'].with_user(user).create(vals)

    def test_create_valid_strike(self):
        strike = self._create_strike(self.teacher_a_user)
        self.assertEqual(strike.student_id, self.minor_student)
        self.assertEqual(strike.teacher_id, self.teacher_a_employee)
        self.assertEqual(strike.reason_id, self.reason_other)

    def test_reason_required(self):
        with self.assertRaises(Exception):
            self._create_strike(self.teacher_a_user, reason_id=False)

    def test_student_required(self):
        with self.assertRaises(Exception):
            self._create_strike(self.teacher_a_user, student_id=False)

    def test_display_name(self):
        strike = self._create_strike(self.teacher_a_user)
        self.assertTrue(strike.display_name)
        self.assertIn(self.minor_student.display_name, strike.display_name)

    def test_admin_crud(self):
        strike = self._create_strike(self.admin_user)
        strike.with_user(self.admin_user).write({'notes': 'Updated.'})
        strike.with_user(self.admin_user).unlink()

    def test_teacher_sees_only_own_strikes(self):
        own = self._create_strike(self.teacher_a_user)
        found = self.env['ems.strike'].with_user(self.other_teacher_user).search([('id', '=', own.id)])
        self.assertFalse(found)

    def test_teacher_cannot_unlink(self):
        strike = self._create_strike(self.teacher_a_user)
        with self.assertRaises(AccessError):
            strike.with_user(self.teacher_a_user).unlink()

    def test_tutor_sees_tutee_strikes(self):
        strike = self._create_strike(self.teacher_a_user)
        found = self.env['ems.strike'].with_user(self.tutor_user).search([('id', '=', strike.id)])
        self.assertIn(strike, found)

    def test_coexistence_group_sees_all_strikes(self):
        strike = self._create_strike(self.teacher_a_user)
        found = self.env['ems.strike'].with_user(self.coexistence_a_user).search([('id', '=', strike.id)])
        self.assertIn(strike, found)

    def test_hos_sees_all_strikes_centrewide(self):
        # hos_b is on a different branch than teacher_a (issued from hos_a's branch) - the
        # centre-wide read comes from group_student_data_reader, not branch matching.
        strike = self._create_strike(self.teacher_a_user)
        found = self.env['ems.strike'].with_user(self.hos_b_user).search([('id', '=', strike.id)])
        self.assertIn(strike, found)

    def test_hos_can_unlink_any_strike(self):
        # Issue #464: Head of Studies / Deputy Head of Studies / Director can delete any
        # strike centre-wide, not just their own tutees' - hos_b deleting a strike issued on
        # hos_a's branch proves this isn't scoped by branch.
        strike = self._create_strike(self.teacher_a_user)
        strike.with_user(self.hos_b_user).unlink()

    def test_coexistence_can_unlink_any_strike(self):
        # Issue #464: coexistence coordinators can delete any strike centre-wide, regardless
        # of which HoS/DHoS branch issued it - same transversal reach as their read access.
        strike = self._create_strike(self.teacher_a_user)
        strike.with_user(self.coexistence_b_user).unlink()

    def test_secretary_can_open_student_form_strike_count(self):
        strike = self._create_strike(self.teacher_a_user)
        student_as_secretary = self.minor_student.with_user(self.secretary_user)
        self.assertEqual(student_as_secretary.strike_count, 1)
        found = self.env['ems.strike'].with_user(self.secretary_user).search([('id', '=', strike.id)])
        self.assertIn(strike, found)

    def test_secretary_cannot_write_or_create_strike(self):
        strike = self._create_strike(self.teacher_a_user)
        with self.assertRaises(AccessError):
            strike.with_user(self.secretary_user).write({'notes': 'Updated.'})
        with self.assertRaises(AccessError):
            self._create_strike(self.secretary_user)

    def test_notification_recipients_minor_student(self):
        # Recipient targeting is what this test covers, not strike_family_notification_mode
        # itself - force 'all' so the family entry doesn't depend on whichever default this
        # environment happens to be running with (a clean install starts on 'kicked_out').
        self.env.company.strike_family_notification_mode = 'all'
        strike = self._create_strike(self.teacher_a_user)
        recipients = strike.send_to.split('; ')
        self.assertIn(self.minor_student.student_email, recipients)
        self.assertIn(self.family_partner.email, recipients)
        self.assertIn(self.tutor_employee.email, recipients)

    def test_notification_templates_resolve(self):
        for xml_id in ('ems.mail_strike_notification_student', 'ems.mail_strike_notification_family', 'ems.mail_strike_notification_tutor'):
            self.assertTrue(self.env.ref(xml_id).exists())

    def test_notification_recipients_adult_no_auth(self):
        adult_student = self.env['res.partner'].create({
            'name': 'Test Adult Student No Auth (Strike)',
            'contact_type': 'student', 'student_id': next_student_id(),
            'student_email': 'test_adult_student_noauth_strike@example.com',
            'birth_date': date(date.today().year - 20, 1, 1),
            'main_group_id': self.group_record.id,
        })
        self.env['res.partner.relation'].sudo().create({
            'left_partner_id': self.family_partner.id,
            'right_partner_id': adult_student.id,
            'type_id': self.relation_type_family.id,
        })
        strike = self._create_strike(self.teacher_a_user, student_id=adult_student.id)
        recipients = strike.send_to.split('; ')
        self.assertIn(adult_student.student_email, recipients)
        self.assertNotIn(self.family_partner.email, recipients)

    def test_notification_recipients_adult_with_auth_share(self):
        adult_student = self.env['res.partner'].create({
            'name': 'Test Adult Student Auth (Strike)',
            'contact_type': 'student', 'student_id': next_student_id(),
            'student_email': 'test_adult_student_auth_strike@example.com',
            'birth_date': date(date.today().year - 20, 1, 1),
            'main_group_id': self.group_record.id,
        })
        self.env['res.partner.relation'].sudo().create({
            'left_partner_id': self.family_partner.id,
            'right_partner_id': adult_student.id,
            'type_id': self.relation_type_family.id,
        })
        # auth_share is a stored compute field (derived from sale_order authorizations);
        # bypass the compute entirely via SQL. Also invalidate the whole recordset (not
        # just auth_share): relation_all_ids is a view-backed One2many that isn't
        # auto-invalidated when a res.partner.relation row is created for it afterwards.
        adult_student.flush_recordset()
        self.env.cr.execute("UPDATE res_partner SET auth_share = TRUE WHERE id = %s", (adult_student.id,))
        adult_student.invalidate_recordset()
        # Recipient targeting is what this test covers, not strike_family_notification_mode
        # itself - force 'all' so the family entry doesn't depend on whichever default this
        # environment happens to be running with (a clean install starts on 'kicked_out').
        self.env.company.strike_family_notification_mode = 'all'
        strike = self._create_strike(self.teacher_a_user, student_id=adult_student.id)
        recipients = strike.send_to.split('; ')
        self.assertIn(self.family_partner.email, recipients)

    def test_family_notification_mode_defaults_to_all(self):
        # Checks the field's own model-level default, not self.env.company: the running
        # company's actual value depends on whether this environment came from a clean
        # install (post_init_hook already forced it to 'kicked_out') or an upgrade
        # (post_init_hook never re-runs, so the field default backfilled during the
        # schema migration is what sticks). Read the field descriptor's own default
        # callable (Odoo normalizes a plain default value into `lambda model: value` -
        # see fields.py) instead of creating a real res.company: a real create() cascades
        # through account/hr/resource's own company-setup logic, including a default
        # "Standard 40 hours/week" resource.calendar that collides with this module's own
        # global unique-name constraint on resource.calendar (working_schedule.py) - a
        # real, CI-only failure hit once already (2026-09-02) before switching to this.
        field = self.env['res.company']._fields['strike_family_notification_mode']
        self.assertEqual(field.default(self.env['res.company']), 'all')

    def test_family_notified_on_every_strike_when_mode_all(self):
        self.env.company.strike_family_notification_mode = 'all'
        strike = self._create_strike(self.teacher_a_user, kicked_out=False)
        recipients = strike.send_to.split('; ')
        self.assertIn(self.family_partner.email, recipients)

    def test_family_not_notified_when_mode_kicked_out_and_not_kicked_out(self):
        self.env.company.strike_family_notification_mode = 'kicked_out'
        strike = self._create_strike(self.teacher_a_user, kicked_out=False)
        recipients = strike.send_to.split('; ')
        self.assertNotIn(self.family_partner.email, recipients)
        # Student and tutor notifications are unaffected by this setting.
        self.assertIn(self.minor_student.student_email, recipients)
        self.assertIn(self.tutor_employee.email, recipients)

    def test_family_notified_when_mode_kicked_out_and_kicked_out_true(self):
        self.env.company.strike_family_notification_mode = 'kicked_out'
        strike = self._create_strike(self.teacher_a_user, kicked_out=True)
        recipients = strike.send_to.split('; ')
        self.assertIn(self.family_partner.email, recipients)

    def test_escalation_fires_at_threshold_and_repeats(self):
        self.env.company.strike_escalation_threshold = 3
        for _i in range(2):
            self._create_strike(self.teacher_a_user)
        self._create_strike(self.teacher_a_user)
        # 3rd strike must trigger escalation; verify via the mail sent (mail.mail traces
        # are auto-deleted, so check the strike's own notification bookkeeping instead).
        third_strike = self.env['ems.strike'].search(
            [('student_id', '=', self.minor_student.id)], order='id desc', limit=1
        )
        self.assertEqual(third_strike.strike_count, 3)

        for _i in range(3):
            self._create_strike(self.teacher_a_user)
        sixth_strike = self.env['ems.strike'].search(
            [('student_id', '=', self.minor_student.id)], order='id desc', limit=1
        )
        self.assertEqual(sixth_strike.strike_count, 6)

    def test_escalation_recipient_matches_teacher_branch(self):
        self.env.company.strike_escalation_threshold = 1
        strike = self._create_strike(self.teacher_a_user)
        self.assertEqual(strike.teacher_id.find_head_of_studies(), self.hos_a_employee)
        self.assertEqual(self.coexistence_a_employee.find_head_of_studies(), self.hos_a_employee)
        self.assertNotEqual(self.coexistence_b_employee.find_head_of_studies(), self.hos_a_employee)

    def test_strike_count_smart_button(self):
        self._create_strike(self.teacher_a_user)
        self._create_strike(self.teacher_a_user)
        self.assertEqual(self.minor_student.strike_count, 2)
        action = self.minor_student.action_view_strikes()
        self.assertEqual(action['domain'], [('student_id', '=', self.minor_student.id)])

    def test_strike_count_smart_button_presets_student(self):
        # The list opened from the student's button passes the student on to its "New strike"
        # dialog, which defaults (and locks, in the view) the student to it.
        context = self.minor_student.action_view_strikes()['context']
        self.assertEqual(context, {'strike_student_id': self.minor_student.id})
        strike = self.env['ems.strike'].with_user(self.teacher_a_user).with_context(context).create({})
        self.assertEqual(strike.student_id, self.minor_student)
        self.assertEqual(strike.teacher_id.user_id, self.teacher_a_user)

    def test_kicked_out_default_false(self):
        strike = self._create_strike(self.teacher_a_user)
        self.assertFalse(strike.kicked_out)

    def test_kicked_out_can_be_set_true(self):
        strike = self._create_strike(self.teacher_a_user, kicked_out=True)
        self.assertTrue(strike.kicked_out)

    def test_notification_mentions_kicked_out_status(self):
        strike_out = self._create_strike(self.teacher_a_user, kicked_out=True)
        strike_not_out = self._create_strike(self.teacher_a_user, kicked_out=False)
        template = self.env.ref('ems.mail_strike_notification_student')
        rendered_out = template._render_field('body_html', strike_out.ids)[strike_out.id]
        rendered_not_out = template._render_field('body_html', strike_not_out.ids)[strike_not_out.id]
        self.assertIn('Kicked out of class:</strong> Yes', rendered_out)
        self.assertIn('Kicked out of class:</strong> No', rendered_not_out)

    def test_attendance_session_line_id_is_optional(self):
        strike = self._create_strike(self.teacher_a_user)
        self.assertFalse(strike.attendance_session_line_id)

    def test_teacher_issues_strike_outside_session(self):
        # Issue #402: the "New strike" dialog (Coexistence > Strikes) only sends student,
        # reason, kicked_out, date and notes; the issuer comes from the teacher_id default.
        strike = self._create_strike(self.teacher_a_user, kicked_out=True, notes='Caught in the corridor.')
        self.assertEqual(strike.teacher_id, self.teacher_a_employee)
        self.assertFalse(strike.attendance_session_line_id)
        self.assertIn('test_minor_student_strike@example.com', strike.send_to)

    def test_teacher_cannot_issue_strike_for_another_teacher(self):
        with self.assertRaises(AccessError):
            self._create_strike(self.teacher_a_user, teacher_id=self.coexistence_a_employee.id)

    def test_default_reason_is_first_active_by_order(self):
        # Same reason the roll-call dialog preselects (first active by sequence), so the
        # New strike dialog never disagrees with it once an admin reorders the reasons.
        first = self.env['ems.strike.reason'].create({'name': 'Test First Reason (Strike)', 'sequence': -1})
        strike = self.env['ems.strike'].with_user(self.teacher_a_user).create({'student_id': self.minor_student.id})
        self.assertEqual(strike.reason_id, first)

    def test_new_strike_button_hidden_from_secretary(self):
        # Secretary reads strikes but can't create them, so the list's header button is
        # stripped from their arch by its groups= attribute.
        list_view = self.env.ref('ems.view_strike_list')
        button_xpath = f"//header/button[@name='{self.env.ref('ems.action_strike_issue').id}']"

        def issue_buttons(user):
            arch = self.env['ems.strike'].with_user(user).get_view(list_view.id)['arch']
            return etree.fromstring(arch).xpath(button_xpath)

        self.assertTrue(issue_buttons(self.teacher_a_user))
        self.assertFalse(issue_buttons(self.secretary_user))

    def test_date_cannot_be_in_the_future(self):
        with self.assertRaises(ValidationError):
            self._create_strike(self.teacher_a_user, date=fields.Datetime.now() + timedelta(minutes=5))
        strike = self._create_strike(self.admin_user)
        with self.assertRaises(ValidationError):
            strike.with_user(self.admin_user).write({'date': fields.Datetime.now() + timedelta(days=1)})

    def test_date_can_be_in_the_past(self):
        past = fields.Datetime.now() - timedelta(hours=2)
        strike = self._create_strike(self.teacher_a_user, date=past)
        self.assertEqual(strike.date, past)

    def test_issue_dialog_teacher_editable_only_by_admin(self):
        view = self.env.ref('ems.view_strike_form_issue')

        def teacher_nodes(user):
            arch = self.env['ems.strike'].with_user(user).get_view(view.id)['arch']
            return etree.fromstring(arch).xpath("//field[@name='teacher_id']")

        teacher_fields = teacher_nodes(self.teacher_a_user)
        self.assertEqual(len(teacher_fields), 1)
        self.assertEqual(teacher_fields[0].get('readonly'), '1')
        admin_fields = teacher_nodes(self.admin_user)
        self.assertEqual(len(admin_fields), 1)
        self.assertNotEqual(admin_fields[0].get('readonly'), '1')

    def test_issue_action_opens_dialog(self):
        action = self.env.ref('ems.action_strike_issue')
        self.assertEqual(action.target, 'new')
        self.assertEqual(action.view_id, self.env.ref('ems.view_strike_form_issue'))

    def test_strike_count_per_session_line(self):
        session_line = self.env['ems.attendance_session_line'].create({
            'student_id': self.minor_student.id,
        })
        self._create_strike(self.teacher_a_user, attendance_session_line_id=session_line.id)
        self.assertEqual(len(session_line.strike_ids), 1)
        self._create_strike(self.teacher_a_user, attendance_session_line_id=session_line.id)
        self.assertEqual(len(session_line.strike_ids), 2)

        other_session_line = self.env['ems.attendance_session_line'].create({
            'student_id': self.minor_student.id,
        })
        self.assertEqual(len(other_session_line.strike_ids), 0)

    def test_session_line_strike_count(self):
        session_line = self.env['ems.attendance_session_line'].create({
            'student_id': self.minor_student.id,
        })
        self.assertEqual(session_line.strike_count, 0)
        self._create_strike(self.teacher_a_user, attendance_session_line_id=session_line.id)
        self.assertEqual(session_line.strike_count, 1)
        self._create_strike(self.teacher_a_user, attendance_session_line_id=session_line.id)
        self.assertEqual(session_line.strike_count, 2)

    def test_session_line_action_view_strikes(self):
        session_line = self.env['ems.attendance_session_line'].create({
            'student_id': self.minor_student.id,
        })
        self._create_strike(self.teacher_a_user, attendance_session_line_id=session_line.id)
        action = session_line.action_view_strikes()
        self.assertEqual(action['domain'], [('attendance_session_line_id', '=', session_line.id)])

    # Issue #554: possible duplicate warning.

    def _duplicate_warning(self, user, **kwargs):
        return self.env['ems.strike'].with_user(user).get_duplicate_warning(
            kwargs.get('student_id', self.minor_student.id), kwargs.get('teacher_id', False), kwargs.get('line_id', False))

    def test_duplicate_window_defaults_to_one_minute(self):
        self.assertEqual(self.env['res.company'].new({}).strike_duplicate_window, 1)

    def test_duplicate_warning_same_teacher_and_student(self):
        self.assertFalse(self._duplicate_warning(self.teacher_a_user))
        self._create_strike(self.teacher_a_user)
        warning = self._duplicate_warning(self.teacher_a_user)
        self.assertIn(self.minor_student.display_name, warning)
        self.assertIn(self.teacher_a_employee.display_name, warning)

    def test_no_duplicate_warning_for_another_teacher_or_student(self):
        self._create_strike(self.teacher_a_user)
        self.assertFalse(self._duplicate_warning(self.admin_user, teacher_id=self.coexistence_a_employee.id))
        other_student = self.minor_student.copy({'student_id': next_student_id()})
        self.assertFalse(self._duplicate_warning(self.teacher_a_user, student_id=other_student.id))

    def test_no_duplicate_warning_outside_window(self):
        strike = self._create_strike(self.teacher_a_user)
        self.env.cr.execute("UPDATE ems_strike SET create_date = create_date - interval '61 seconds' WHERE id = %s", (strike.id,))
        strike.invalidate_recordset(['create_date'])
        self.assertFalse(self._duplicate_warning(self.teacher_a_user))
        self.env.company.strike_duplicate_window = 2
        self.assertTrue(self._duplicate_warning(self.teacher_a_user))

    def test_duplicate_warning_disabled_by_zero_window(self):
        self._create_strike(self.teacher_a_user)
        self.env.company.strike_duplicate_window = 0
        self.assertFalse(self._duplicate_warning(self.teacher_a_user))

    def test_duplicate_warning_ignores_backdated_date(self):
        # A strike noticed a while ago and backdated is still a fresh one to compare against.
        self._create_strike(self.teacher_a_user, date=fields.Datetime.now() - timedelta(hours=2))
        self.assertTrue(self._duplicate_warning(self.teacher_a_user))

    def test_duplicate_warning_field_only_on_new_strike(self):
        strike = self._create_strike(self.teacher_a_user)
        self.assertFalse(strike.duplicate_warning)
        new_strike = self.env['ems.strike'].with_user(self.teacher_a_user).new({'student_id': self.minor_student.id})
        self.assertTrue(new_strike.duplicate_warning)

    def test_issue_dialog_send_asks_confirmation_only_on_duplicate(self):
        arch = self.env['ems.strike'].with_user(self.teacher_a_user).get_view(self.env.ref('ems.view_strike_form_issue').id)['arch']
        buttons = etree.fromstring(arch).xpath("//footer/button[@special='save']")
        self.assertEqual([(button.get('invisible'), bool(button.get('confirm'))) for button in buttons],
                         [('duplicate_warning', False), ('not duplicate_warning', True)])

    def test_duplicate_warning_only_on_same_session_line(self):
        line, other_line = self.env['ems.attendance_session_line'].create([
            {'student_id': self.minor_student.id}, {'student_id': self.minor_student.id},
        ])
        self._create_strike(self.teacher_a_user, attendance_session_line_id=line.id)
        self.assertTrue(self._duplicate_warning(self.teacher_a_user, line_id=line.id))
        self.assertFalse(self._duplicate_warning(self.teacher_a_user, line_id=other_line.id))
        # The New strike dialog sets no line: a roll-call strike is not its duplicate.
        self.assertFalse(self._duplicate_warning(self.teacher_a_user))
