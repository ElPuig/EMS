import base64
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tests.common import TransactionCase

from .common import (create_level_study_group, create_role_employee, create_role_user,
                     mock_outgoing_email)

FAKE_PDF = base64.b64encode(b'%PDF-1.4 fake test content')


class TestAuthorizationSendWizard(TransactionCase):
    """ems.authorization.send.wizard: sending authorizations during the school year
    (issue #443), when the running course's enrollment is already closed.

    See docs/en/developers/enrollment/authorization.md, "Standalone authorizations".
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The wizard emails the student (or the family of a minor) - see CLAUDE.md's
        # "Email safety in tests". Queued mail.mail records are what the assertions read,
        # so nothing reaches a real mailbox either way.
        mock_outgoing_email(cls)

        Course = cls.env['ems.course']
        cls.course = Course.search([('is_current', '=', True)], limit=1) \
            or Course.create({'start': 2096, 'end': 2097, 'is_current': True})
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TSW', study={
            'code': 'TSW001', 'acronym': 'TSWS', 'name': 'Test Send Wizard Study',
        })
        cls.other_level, cls.other_study, cls.other_group = create_level_study_group(cls, 'TSW2', study={
            'code': 'TSW002', 'acronym': 'TSWS2', 'name': 'Other Send Wizard Study',
        })

        cls.sender = create_role_user(cls, 'secretary', 'test_secretary_send_wizard',
                                      name='Test Secretary (Send Wizard)',
                                      email='secretary.sw@example.com')
        cls.head = create_role_user(cls, 'head_of_studies', 'test_head_send_wizard',
                                    name='Test Head (Send Wizard)', email='head.sw@example.com')
        cls.teacher = create_role_user(cls, 'teacher', 'test_teacher_send_wizard',
                                       name='Test Teacher (Send Wizard)')
        cls.tutor = create_role_user(cls, 'tutor', 'test_tutor_send_wizard',
                                     name='Test Tutor (Send Wizard)')
        cls.tutor_employee = create_role_employee(cls, cls.tutor)

        # cls.group is the tutor's; cls.other_group, and its student, are somebody else's.
        cls.group.tutor_id = cls.tutor_employee
        cls.adult = cls._student('Adult Student (Send Wizard)', cls.group, age=19,
                                 email='adult.sw@example.com')
        cls.minor = cls._student('Minor Student (Send Wizard)', cls.group, age=15)
        cls.family = cls.env['res.partner'].create({
            'name': 'Family Contact (Send Wizard)', 'contact_type': 'family',
            'email': 'family.sw@example.com',
        })
        cls.env['res.partner.relation'].create({
            'left_partner_id': cls.family.id,
            'type_id': cls.env.ref('ems.relation_type_father').id,
            'right_partner_id': cls.minor.id,
        })
        # Same group, but no enrollment at all for cls.course.
        cls.unenrolled = cls.env['res.partner'].create({
            'name': 'Unenrolled Student (Send Wizard)', 'contact_type': 'student',
            'main_group_id': cls.group.id, 'email': 'unenrolled.sw@example.com',
            'birth_date': date.today() - relativedelta(years=19),
        })
        cls.other_student = cls._student('Other Study Student (Send Wizard)', cls.other_group,
                                         age=19, study=cls.other_study,
                                         email='other.sw@example.com')

        Template = cls.env['ems.authorization.template']
        cls.template = Template.create({
            'name': 'Mid-year Trip', 'legal_text': '<p>Trip for {{student_name}}</p>',
            'apply_on_enrollment': False, 'sendable_during_course': True,
        })
        cls.second_template = Template.create({
            'name': 'Mid-year Image', 'legal_text': '<p>Image rights</p>',
            'apply_on_enrollment': False, 'sendable_during_course': True,
        })
        cls.scoped_template = Template.create({
            'name': 'Mid-year Scoped', 'legal_text': '<p>Only one study</p>',
            'apply_on_enrollment': False, 'sendable_during_course': True, 'ems_study_ids': [(6, 0, [cls.study.id])],
        })

    @classmethod
    def _student(cls, name, group, age, study=None, email=None):
        """A student sitting in `group` with an enrollment for cls.course - which is what
        the wizard's scope targets resolve through."""
        student = cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'main_group_id': group.id,
            'email': email, 'birth_date': date.today() - relativedelta(years=age),
        })
        cls.env['sale.order'].create({
            'partner_id': student.id,
            'ems_study_id': (study or cls.study).id,
            'ems_course_id': cls.course.id,
        })
        return student

    def _wizard(self, user=None, **vals):
        vals.setdefault('course_id', self.course.id)
        vals.setdefault('template_ids', [(6, 0, self.template.ids)])
        # lang: the summary notification's text is asserted on, and this DB defaults to ca_ES.
        return self.env['ems.authorization.send.wizard'].with_user(user or self.sender) \
            .with_context(lang='en_US').create(vals)

    def _auths(self, student=None, template=None):
        domain = [('course_id', '=', self.course.id), ('enrollment_id', '=', False)]
        if student:
            domain.append(('partner_id', '=', student.id))
        if template:
            domain.append(('template_id', '=', template.id))
        return self.env['ems.authorization'].search(domain)

    def _mails(self, student):
        return self.env['mail.mail'].search([
            ('model', '=', 'res.partner'), ('res_id', '=', student.id),
        ])

    # ------------------------------------------------------------------
    # Resolving recipients
    # ------------------------------------------------------------------
    def test_selected_students_come_from_active_ids(self):
        # active_model included, as action_authorization_send_bulk passes it: active_ids alone
        # are no longer trusted to be students (see the test opening it from a form below).
        wizard = self.env['ems.authorization.send.wizard'].with_user(self.sender).with_context(
            active_ids=(self.adult | self.minor | self.family).ids, active_model='res.partner',
        ).create({'template_ids': [(6, 0, self.template.ids)]})
        self.assertEqual(wizard.target, 'students')
        self.assertEqual(wizard.student_ids, self.adult | self.minor)

    def test_scope_resolves_enrolled_students_of_a_group(self):
        wizard = self._wizard(target='scope', group_ids=[(6, 0, self.group.ids)])
        resolved = wizard._resolve_students()
        self.assertIn(self.adult, resolved)
        self.assertIn(self.minor, resolved)
        self.assertNotIn(self.other_student, resolved)

    def test_scope_resolves_enrolled_students_of_a_study(self):
        wizard = self._wizard(target='scope', ems_study_ids=[(6, 0, self.other_study.ids)])
        resolved = wizard._resolve_students()
        self.assertEqual(resolved, self.other_student)

    def test_scope_resolves_enrolled_students_of_a_level(self):
        wizard = self._wizard(target='scope', ems_level_ids=[(6, 0, self.level.ids)])
        resolved = wizard._resolve_students()
        self.assertIn(self.adult, resolved)
        self.assertNotIn(self.other_student, resolved)

    def test_students_without_an_enrollment_in_the_course_are_excluded(self):
        """The scope targets go through the enrollment on purpose: a group record still
        holds ex-students who must not be asked for anything."""
        wizard = self._wizard(target='scope', group_ids=[(6, 0, self.group.ids)])
        self.assertNotIn(self.unenrolled, wizard._resolve_students())

    def test_scope_choices_are_ready_when_the_assistant_opens_preloaded(self):
        """Found by the tutor tour: computed, the allowed groups never reached the web client
        when the assistant opened (the onchange's default phase leaves them out), so a form
        preloaded from its own button offered no group at all. Form goes through that same
        default phase."""
        form = Form(self.env['ems.authorization.send.wizard'].with_user(self.sender).with_context(
            lang='en_US', default_target='scope',
            default_template_ids=[(6, 0, self.scoped_template.ids)]))
        wizard = form.save()
        self.assertIn(self.group, wizard.allowed_group_ids)
        self.assertNotIn(self.other_group, wizard.allowed_group_ids)

    def test_scope_choices_stay_inside_the_authorizations_scope(self):
        wizard = self._wizard(target='scope', template_ids=[(6, 0, self.scoped_template.ids)])
        wizard._onchange_selection()  # what the form runs when the chosen forms change
        self.assertIn(self.group, wizard.allowed_group_ids)
        self.assertNotIn(self.other_group, wizard.allowed_group_ids)
        self.assertIn(self.study, wizard.allowed_study_ids)
        self.assertNotIn(self.other_study, wizard.allowed_study_ids)
        self.assertIn(self.level, wizard.allowed_level_ids)
        self.assertNotIn(self.other_level, wizard.allowed_level_ids)

    def test_a_student_outside_the_authorizations_scope_is_skipped(self):
        action = self._wizard(student_ids=[(6, 0, (self.adult | self.other_student).ids)],
                              template_ids=[(6, 0, self.scoped_template.ids)]).action_apply()
        self.assertTrue(self._auths(self.adult, self.scoped_template))
        self.assertFalse(self._auths(self.other_student, self.scoped_template))
        self.assertIn('outside the scope', action['params']['message'])

    def test_sending_to_a_scope_requires_choosing_one(self):
        """An empty choice used to mean every enrolled student in the centre."""
        with self.assertRaises(UserError):
            self._wizard(target='scope').action_apply()

    def test_only_authorizations_sendable_during_the_course_are_offered(self):
        Template = self.env['ems.authorization.template']
        enrollment_only = Template.create({
            'name': 'Enrollment Only (Send Wizard)', 'legal_text': '<p>x</p>',
            'ems_study_ids': [(6, 0, self.other_study.ids)],
        })
        both_routes = Template.create({
            'name': 'Both Routes (Send Wizard)', 'legal_text': '<p>x</p>',
            'sendable_during_course': True, 'ems_study_ids': [(6, 0, self.other_study.ids)],
        })
        domain = self.env['ems.authorization.send.wizard']._fields['template_ids'].domain
        offered = Template.search(domain)
        self.assertIn(self.template, offered)
        self.assertIn(both_routes, offered)
        self.assertNotIn(enrollment_only, offered)

    def test_preview_lists_the_students_of_a_chosen_group(self):
        """Found testing by hand: the preview is built in an onchange, where the chosen group is a
        virtual record wrapping the real one. Compared straight against each student's real group
        it matched nothing, so the preview came out empty while sending worked."""
        form = Form(self.env['ems.authorization.send.wizard'].with_user(self.sender)
                    .with_context(lang='en_US', default_target='scope'))
        form.template_ids.add(self.template)
        form.group_ids.add(self.group)
        self.assertEqual(len(form.line_ids), 2)  # adult + minor; the unenrolled one is not

    def test_opening_from_an_authorization_form_does_not_read_its_id_as_a_student(self):
        """Found testing by hand: from the form's own button, active_ids carry the form's id, and
        reading it as a res.partner id failed with "record does not exist"."""
        action = self.template.action_send_to_students()
        wizard = self.env['ems.authorization.send.wizard'].with_user(self.sender).with_context(
            action['context'], active_id=self.template.id, active_ids=self.template.ids,
            active_model='ems.authorization.template').create({})
        self.assertEqual(wizard.template_ids, self.template)
        self.assertEqual(wizard.target, 'scope')
        self.assertFalse(wizard.student_ids)
    # ------------------------------------------------------------------
    # Creating the authorizations
    # ------------------------------------------------------------------
    def test_apply_creates_one_pending_authorization_per_student_and_template(self):
        wizard = self._wizard(student_ids=[(6, 0, (self.adult | self.minor).ids)],
                              template_ids=[(6, 0, (self.template | self.second_template).ids)])
        wizard.action_apply()
        for student in (self.adult, self.minor):
            auths = self._auths(student)
            self.assertEqual(len(auths), 2)
            self.assertEqual(set(auths.mapped('status')), {'pending'})
            self.assertFalse(any(auths.mapped('enrollment_id')))
            self.assertEqual(set(auths.mapped('course_id')), {self.course})

    def test_existing_standalone_authorization_is_skipped_not_recreated(self):
        wizard = self._wizard(student_ids=[(6, 0, self.adult.ids)])
        wizard.action_apply()
        answered = self._auths(self.adult, self.template)
        answered.write({'status': 'yes', 'signed_document': FAKE_PDF,
                        'signed_document_name': 'x.pdf'})

        self._wizard(student_ids=[(6, 0, self.adult.ids)]).action_apply()

        self.assertEqual(len(self._auths(self.adult, self.template)), 1)
        self.assertEqual(answered.status, 'yes')

    def test_an_authorization_already_held_through_the_enrollment_is_skipped(self):
        """Same (course, template) reached by the other route still counts as held."""
        enrollment = self.env['sale.order'].search([
            ('partner_id', '=', self.adult.id), ('ems_course_id', '=', self.course.id)], limit=1)
        self.env['ems.authorization'].create({
            'enrollment_id': enrollment.id, 'template_id': self.template.id,
        })
        self._wizard(student_ids=[(6, 0, self.adult.ids)]).action_apply()
        self.assertFalse(self._auths(self.adult, self.template))

    # ------------------------------------------------------------------
    # Notification
    # ------------------------------------------------------------------
    def test_one_email_per_student_not_one_per_authorization(self):
        wizard = self._wizard(student_ids=[(6, 0, self.adult.ids)],
                              template_ids=[(6, 0, (self.template | self.second_template).ids)])
        wizard.action_apply()
        mails = self._mails(self.adult)
        self.assertEqual(len(mails), 1)
        body = mails.body_html or ''
        self.assertIn(self.template.name, body)
        self.assertIn(self.second_template.name, body)

    def test_adult_student_is_emailed_himself(self):
        self._wizard(student_ids=[(6, 0, self.adult.ids)]).action_apply()
        self.assertIn(self.adult.email, self._mails(self.adult).email_to)

    def test_minor_student_emails_the_family(self):
        self._wizard(student_ids=[(6, 0, self.minor.ids)]).action_apply()
        mails = self._mails(self.minor)
        self.assertEqual(len(mails), 1)
        self.assertIn(self.family.email, mails.email_to)
        self.assertNotIn('@', mails.email_to.replace(self.family.email, ''))

    def test_nothing_is_emailed_when_notify_is_off(self):
        self._wizard(student_ids=[(6, 0, self.adult.ids)], notify=False).action_apply()
        self.assertFalse(self._mails(self.adult))
        self.assertTrue(self._auths(self.adult, self.template))

    def test_recipient_without_email_is_reported_as_an_issue(self):
        orphan = self._student('Orphan Minor (Send Wizard)', self.group, age=15)
        action = self._wizard(student_ids=[(6, 0, orphan.ids)]).action_apply()
        self.assertIn(orphan.name, action['params']['message'])
        self.assertEqual(action['params']['type'], 'warning')
        # The authorization is still created: it shows up in the portal regardless.
        self.assertTrue(self._auths(orphan, self.template))

    def test_action_apply_returns_a_summary_notification(self):
        action = self._wizard(student_ids=[(6, 0, self.adult.ids)]).action_apply()
        self.assertEqual(action['tag'], 'display_notification')
        self.assertEqual(action['params']['type'], 'success')
        self.assertIn('1', action['params']['message'])

    # ------------------------------------------------------------------
    # Who may send
    # ------------------------------------------------------------------
    def test_head_of_studies_can_send(self):
        self._wizard(user=self.head, student_ids=[(6, 0, self.adult.ids)]).action_apply()
        self.assertTrue(self._auths(self.adult, self.template))

    def test_staff_are_not_restricted_to_their_own_students(self):
        Authorization = self.env['ems.authorization']
        self.assertTrue(Authorization.with_user(self.sender)._ems_sees_every_student())
        self.assertTrue(Authorization.with_user(self.head)._ems_sees_every_student())
        self.assertFalse(Authorization.with_user(self.tutor)._ems_sees_every_student())

    def test_a_tutor_sees_why_someone_elses_student_is_left_out(self):
        wizard = self._wizard(user=self.tutor,
                              student_ids=[(6, 0, (self.adult | self.other_student).ids)])
        wizard._onchange_selection()
        notes = {line.student_id: line.note for line in wizard.line_ids}
        self.assertIn('Not one of your students', notes[self.other_student])
        self.assertNotIn('Not one of your students', notes[self.adult] or '')

    def test_a_tutor_can_send_to_their_own_group(self):
        self._wizard(user=self.tutor, target='scope', group_ids=[(6, 0, self.group.ids)]).action_apply()
        self.assertTrue(self._auths(self.adult, self.template))
        self.assertTrue(self._auths(self.minor, self.template))

    def test_a_tutor_is_offered_only_their_own_groups(self):
        wizard = self._wizard(user=self.tutor, target='scope')
        wizard._onchange_selection()
        self.assertIn(self.group, wizard.allowed_group_ids)
        self.assertNotIn(self.other_group, wizard.allowed_group_ids)

    def test_a_tutor_never_sends_to_someone_elses_student(self):
        """Whatever reaches the wizard: the picker's domain is the widget's business, this is
        the server's."""
        self._wizard(user=self.tutor,
                     student_ids=[(6, 0, (self.adult | self.other_student).ids)]).action_apply()
        self.assertTrue(self._auths(self.adult, self.template))
        self.assertFalse(self._auths(self.other_student, self.template))

    def test_a_tutor_follows_up_only_their_own_students(self):
        self._wizard(student_ids=[(6, 0, (self.adult | self.other_student).ids)]).action_apply()
        Authorization = self.env['ems.authorization']
        tutor_action = Authorization.with_user(self.tutor).action_open_follow_up()
        seen = Authorization.with_user(self.tutor).search(tutor_action['domain'])
        self.assertIn(self._auths(self.adult, self.template), seen)
        self.assertNotIn(self._auths(self.other_student, self.template), seen)
        staff_action = Authorization.with_user(self.sender).action_open_follow_up()
        self.assertFalse(staff_action.get('domain'))

    def test_a_plain_teacher_cannot_send(self):
        with self.assertRaises(Exception):
            self._wizard(user=self.teacher, student_ids=[(6, 0, self.adult.ids)]).action_apply()

    def test_sending_without_a_template_is_rejected(self):
        wizard = self._wizard(student_ids=[(6, 0, self.adult.ids)], template_ids=[(6, 0, [])])
        with self.assertRaises(UserError):
            wizard.action_apply()
