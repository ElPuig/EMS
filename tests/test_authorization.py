import base64
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study, create_level_study_group, next_student_id

FAKE_PDF = base64.b64encode(b'%PDF-1.4 fake test content')


class TestAuthorizationTemplate(TransactionCase):
    """models/enrollment/authorization.py — EmsAuthorizationTemplate.

    Level/study matching (AND-of-scopes) lives in _matches_scope(), shared with
    sale.order._get_authorization_commands' live onchange sync (tested in
    tests/test_enrollment_header.py) — see
    docs/en/developers/enrollment/authorization.md.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Course = cls.env['ems.course']
        cls.course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        cls.level, cls.study = create_level_study(cls, 'TAT', level={'name': 'Test Auth Template Level'}, study={
            'code': 'TAT001', 'acronym': 'TATS', 'name': 'Test Auth Template Study',
        })
        cls.other_study = cls.env['ems.study'].create({
            'code': 'TAT002', 'acronym': 'TATS2', 'name': 'Other Auth Template Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TATSUB', 'acronym': 'TAS', 'name': 'Test Auth Template Subject',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.student1 = cls.env['res.partner'].create({'name': 'Auth Student 1', 'contact_type': 'student', 'student_id': next_student_id()})
        cls.student2 = cls.env['res.partner'].create({'name': 'Auth Student 2', 'contact_type': 'student', 'student_id': next_student_id()})
        cls.student3 = cls.env['res.partner'].create({'name': 'Auth Student 3', 'contact_type': 'student', 'student_id': next_student_id()})

    def _order(self, partner, study=None, state=None, with_line=False):
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'ems_study_id': (study or self.study).id,
            'ems_course_id': self.course.id,
        })
        if with_line:
            order.order_line = [(0, 0, {'product_id': self.subject.product_id.id})]
        if state == 'sent':
            order.action_quotation_sent()
        elif state == 'sale':
            order.action_confirm()
        elif state == 'cancel':
            order.action_cancel()
        return order

    def test_create_applies_to_matching_draft_enrollment_no_scope(self):
        order = self._order(self.student1)
        template = self.env['ems.authorization.template'].create({
            'name': 'Unscoped Auth', 'legal_text': '<p>Text</p>',
        })
        self.assertIn(template, order.ems_authorization_ids.mapped('template_id'))

    def test_create_applies_only_within_matching_level(self):
        other_level = self.env['ems.level'].create({'acronym': 'TAT2', 'name': 'Other Level'})
        order = self._order(self.student1)
        template = self.env['ems.authorization.template'].create({
            'name': 'Level-scoped Auth', 'legal_text': '<p>Text</p>',
            'ems_level_ids': [(6, 0, [other_level.id])],
        })
        self.assertNotIn(template, order.ems_authorization_ids.mapped('template_id'))

    def test_create_applies_only_within_matching_study(self):
        order_matching = self._order(self.student1, study=self.study)
        order_other = self._order(self.student2, study=self.other_study)
        template = self.env['ems.authorization.template'].create({
            'name': 'Study-scoped Auth', 'legal_text': '<p>Text</p>',
            'ems_study_ids': [(6, 0, [self.study.id])],
        })
        self.assertIn(template, order_matching.ems_authorization_ids.mapped('template_id'))
        self.assertNotIn(template, order_other.ems_authorization_ids.mapped('template_id'))

    def test_create_with_both_level_and_study_requires_both_to_match(self):
        """AND-of-scopes, shared via _matches_scope() with
        sale.order._get_authorization_commands' live onchange sync (see
        test_enrollment_header.py::test_get_authorization_commands_with_both_level_and_study_requires_both
        for the same rule exercised from the enrollment side)."""
        order = self._order(self.student1, study=self.other_study)
        template = self.env['ems.authorization.template'].create({
            'name': 'Level+Study-scoped Auth', 'legal_text': '<p>Text</p>',
            'ems_level_ids': [(6, 0, [self.level.id])],
            'ems_study_ids': [(6, 0, [self.study.id])],
        })
        # order's level matches (self.other_study shares self.level) but its
        # study doesn't -> AND semantics means no match.
        self.assertNotIn(template, order.ems_authorization_ids.mapped('template_id'))

    def test_create_skips_confirmed_and_cancelled_enrollments(self):
        confirmed = self._order(self.student1, state='sale', with_line=True)
        cancelled = self._order(self.student2, state='cancel')
        template = self.env['ems.authorization.template'].create({
            'name': 'Draft-only Auth', 'legal_text': '<p>Text</p>',
        })
        self.assertNotIn(template, confirmed.ems_authorization_ids.mapped('template_id'))
        self.assertNotIn(template, cancelled.ems_authorization_ids.mapped('template_id'))

    def test_action_apply_to_open_enrollments_is_idempotent(self):
        order = self._order(self.student1)
        template = self.env['ems.authorization.template'].create({
            'name': 'Idempotent Auth', 'legal_text': '<p>Text</p>',
        })
        template.action_apply_to_open_enrollments()
        auths = order.ems_authorization_ids.filtered(lambda a: a.template_id == template)
        self.assertEqual(len(auths), 1)

    def test_action_remove_from_open_enrollments_keeps_answered(self):
        order_pending = self._order(self.student1)
        order_answered = self._order(self.student2)
        template = self.env['ems.authorization.template'].create({
            'name': 'Removable Auth', 'legal_text': '<p>Text</p>',
        })
        answered_auth = order_answered.ems_authorization_ids.filtered(lambda a: a.template_id == template)
        answered_auth.write({'status': 'yes', 'signed_document': FAKE_PDF, 'signed_document_name': 'x.pdf'})

        template.action_remove_from_open_enrollments()

        self.assertFalse(order_pending.ems_authorization_ids.filtered(lambda a: a.template_id == template))
        self.assertTrue(order_answered.ems_authorization_ids.filtered(lambda a: a.template_id == template))

    def test_action_remove_from_open_enrollments_keeps_confirmed_order_auth(self):
        order = self._order(self.student1, with_line=True)
        template = self.env['ems.authorization.template'].create({
            'name': 'Kept On Confirm Auth', 'legal_text': '<p>Text</p>', 'is_required': False,
        })
        order.action_confirm()
        template.action_remove_from_open_enrollments()
        self.assertTrue(order.ems_authorization_ids.filtered(lambda a: a.template_id == template))


    # --- apply_on_enrollment: forms that do not apply to it stay out of the enrollment ---

    def test_standalone_template_is_not_applied_on_create(self):
        order = self._order(self.student1)
        template = self.env['ems.authorization.template'].create({
            'name': 'Mid-year Auth', 'legal_text': '<p>Text</p>', 'apply_on_enrollment': False, 'sendable_during_course': True,
        })
        self.assertNotIn(template, order.ems_authorization_ids.mapped('template_id'))

    def test_standalone_template_is_ignored_by_the_enrollment_sync(self):
        """The one that matters: without the apply_on_enrollment filter in
        sale.order._get_authorization_commands(), the next onchange on any draft
        enrollment would pull in a template created mid-year for another course."""
        order = self._order(self.student1)
        template = self.env['ems.authorization.template'].create({
            'name': 'Mid-year Sync Auth', 'legal_text': '<p>Text</p>', 'apply_on_enrollment': False, 'sendable_during_course': True,
        })
        order.apply_authorizations()
        self.assertNotIn(template, order.ems_authorization_ids.mapped('template_id'))

    def test_apply_to_open_enrollments_is_a_noop_for_a_standalone_template(self):
        order = self._order(self.student1)
        template = self.env['ems.authorization.template'].create({
            'name': 'Mid-year Apply Auth', 'legal_text': '<p>Text</p>', 'apply_on_enrollment': False, 'sendable_during_course': True,
        })
        template.action_apply_to_open_enrollments()
        self.assertNotIn(template, order.ems_authorization_ids.mapped('template_id'))

    def test_remove_from_open_enrollments_is_a_noop_for_a_standalone_template(self):
        """A template switched to standalone after it had already been attached keeps
        its existing enrollment rows - removing them is the enrollment-side button's
        job, and it is hidden for a standalone template."""
        order = self._order(self.student1)
        template = self.env['ems.authorization.template'].create({
            'name': 'Mid-year Remove Auth', 'legal_text': '<p>Text</p>',
        })
        self.assertIn(template, order.ems_authorization_ids.mapped('template_id'))
        template.write({'apply_on_enrollment': False, 'sendable_during_course': True})
        template.action_remove_from_open_enrollments()
        self.assertIn(template, order.ems_authorization_ids.mapped('template_id'))


    def test_a_form_must_take_at_least_one_route(self):
        with self.assertRaises(ValidationError):
            self.env['ems.authorization.template'].create({
                'name': 'Nowhere Auth', 'legal_text': '<p>Text</p>',
                'apply_on_enrollment': False, 'sendable_during_course': False,
            })

    def test_a_form_can_apply_to_enrollment_and_be_sent_during_the_course(self):
        """'Apply to Pre-Enrollments' only reaches draft/sent enrollments, so a form created once
        some enrollments were already confirmed can only reach those students by hand."""
        order = self._order(self.student1)
        template = self.env['ems.authorization.template'].create({
            'name': 'Both Routes Auth', 'legal_text': '<p>Text</p>',
            'sendable_during_course': True,
        })
        self.assertIn(template, order.ems_authorization_ids.mapped('template_id'))
        self.assertIn(template, self.env['ems.authorization.template'].search(
            [('sendable_during_course', '=', True)]))

class TestAuthorization(TransactionCase):
    """EmsAuthorization — the per-enrollment response row."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Course = cls.env['ems.course']
        cls.course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        cls.level, cls.study = create_level_study(cls, 'TAU', level={'name': 'Test Auth Level'}, study={
            'code': 'TAU001', 'acronym': 'TAUS', 'name': 'Test Auth Study',
        })
        cls.student = cls.env['res.partner'].create({'name': 'Auth Response Student', 'contact_type': 'student', 'student_id': next_student_id()})
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.student.id, 'ems_study_id': cls.study.id, 'ems_course_id': cls.course.id,
        })
        cls.template = cls.env['ems.authorization.template'].create({
            'name': 'Response Template', 'legal_text': '<p>Hello {{student_name}}, year {{academic_year}}, '
                                                         'study {{study_name}}.</p>',
        })
        # rule_ems_authorization_portal scopes access to
        # enrollment_id.partner_id = user.partner_id (or its parent) — the
        # portal user must actually be (or parent) the enrolled student.
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Auth Portal User', 'login': 'auth_portal_teau',
            'partner_id': cls.student.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def _auth(self):
        return self.order.ems_authorization_ids.filtered(lambda a: a.template_id == self.template)

    def test_sql_constraint_blocks_duplicate_enrollment_template_pair(self):
        with self.assertRaises(Exception):
            self.env['ems.authorization'].create({
                'enrollment_id': self.order.id, 'template_id': self.template.id,
            })

    def test_acceptance_only_template_cannot_be_rejected(self):
        self.template.acceptance_only = True
        with self.assertRaises(ValidationError):
            self._auth().write({'status': 'no', 'signed_document': FAKE_PDF, 'signed_document_name': 'x.pdf'})

    def test_internal_user_must_attach_document_to_respond(self):
        with self.assertRaises(ValidationError):
            self._auth().write({'status': 'yes'})

    def test_internal_user_with_document_sets_response_metadata(self):
        auth = self._auth()
        auth.write({'status': 'yes', 'signed_document': FAKE_PDF, 'signed_document_name': 'x.pdf'})
        self.assertEqual(auth.status, 'yes')
        self.assertTrue(auth.response_date)
        self.assertEqual(auth.response_uid, self.env.user)

    def test_portal_user_can_respond_without_document(self):
        auth = self._auth().with_user(self.portal_user)
        auth.write({'status': 'yes'})
        self.assertEqual(auth.status, 'yes')
        self.assertTrue(auth.response_date)

    def test_clearing_signed_document_clears_response_metadata(self):
        auth = self._auth()
        auth.write({'status': 'yes', 'signed_document': FAKE_PDF, 'signed_document_name': 'x.pdf'})
        auth.write({'signed_document': False})
        self.assertFalse(auth.response_date)
        self.assertFalse(auth.response_uid)

    def test_legal_text_rendered_substitutes_placeholders(self):
        auth = self._auth()
        rendered = auth.legal_text_rendered
        self.assertIn(self.student.name, rendered)
        self.assertIn(self.course.name, rendered)
        self.assertIn(self.study.name, rendered)
        self.assertNotIn('{{student_name}}', rendered)


class TestAuthorizationField(TransactionCase):

    def test_fields_ordered_by_sequence(self):
        template = self.env['ems.authorization.template'].create({
            'name': 'Field Order Template', 'legal_text': '<p>Text</p>',
            'field_ids': [
                (0, 0, {'label': 'Second', 'sequence': 20}),
                (0, 0, {'label': 'First', 'sequence': 10}),
            ],
        })
        # field_ids right after create() reflects command order, not _order,
        # until re-read from the DB (an Odoo o2m-cache quirk, not specific
        # to this model) — search() to see what a list view would actually
        # render.
        fields = self.env['ems.authorization.field'].search([('template_id', '=', template.id)])
        self.assertEqual(fields.mapped('label'), ['First', 'Second'])


class TestAuthorizationStandalone(TransactionCase):
    """EmsAuthorization with no enrollment - the mid-year authorizations of issue #443.

    partner_id/course_id are the record's real anchor; enrollment_id only says which
    route created it. See docs/en/developers/enrollment/authorization.md's
    "Standalone authorizations" section.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Course = cls.env['ems.course']
        cls.course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TAS', study={
            'code': 'TAS001', 'acronym': 'TASS', 'name': 'Test Standalone Study',
        })
        cls.group_study = cls.env['ems.study'].create({
            'code': 'TAS002', 'acronym': 'TASG', 'name': 'Group Standalone Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.group.study_id = cls.group_study
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TASSUB', 'acronym': 'TSS', 'name': 'Test Standalone Subject',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Standalone Student', 'contact_type': 'student',
            'main_group_id': cls.group.id,
        })
        cls.other_student = cls.env['res.partner'].create({
            'name': 'Standalone Other Student', 'contact_type': 'student',
        })
        cls.template = cls.env['ems.authorization.template'].create({
            'name': 'Mid-year Template', 'apply_on_enrollment': False, 'sendable_during_course': True,
            'legal_text': '<p>Hello {{student_name}}, year {{academic_year}}, '
                          'study {{study_name}}.</p>',
        })

    def _standalone(self, student=None, template=None):
        return self.env['ems.authorization'].create({
            'partner_id': (student or self.student).id,
            'course_id': self.course.id,
            'template_id': (template or self.template).id,
        })

    def _order(self, student=None, with_line=False):
        order = self.env['sale.order'].create({
            'partner_id': (student or self.student).id,
            'ems_study_id': self.study.id,
            'ems_course_id': self.course.id,
        })
        if with_line:
            order.order_line = [(0, 0, {'product_id': self.subject.product_id.id})]
        return order

    def test_create_without_an_enrollment(self):
        auth = self._standalone()
        self.assertFalse(auth.enrollment_id)
        self.assertEqual(auth.partner_id, self.student)
        self.assertEqual(auth.course_id, self.course)
        self.assertEqual(auth.status, 'pending')

    def test_partner_and_course_are_derived_from_the_enrollment(self):
        order = self._order()
        auth = self.env['ems.authorization'].create({
            'enrollment_id': order.id, 'template_id': self.template.id,
        })
        self.assertEqual(auth.partner_id, self.student)
        self.assertEqual(auth.course_id, self.course)

    def test_standalone_target_survives_a_later_write(self):
        auth = self._standalone()
        auth.write({'status': 'yes', 'signed_document': FAKE_PDF, 'signed_document_name': 'x.pdf'})
        self.assertEqual(auth.partner_id, self.student)
        self.assertEqual(auth.course_id, self.course)

    def test_a_standalone_may_duplicate_an_enrollment_bound_template(self):
        """The partial index only covers standalone rows: the wizard, not the DB, is
        what keeps a student from being asked the same thing twice."""
        order = self._order()
        enrollment_auth = self.env['ems.authorization'].create({
            'enrollment_id': order.id, 'template_id': self.template.id,
        })
        standalone_auth = self._standalone()
        self.assertNotEqual(enrollment_auth, standalone_auth)
        self.assertEqual(standalone_auth.partner_id, enrollment_auth.partner_id)

    def test_legal_text_rendered_without_an_enrollment(self):
        auth = self._standalone()
        rendered = auth.legal_text_rendered
        self.assertIn(self.student.name, rendered)
        self.assertIn(self.course.name, rendered)
        self.assertIn(self.group_study.name, rendered)
        self.assertNotIn('{{student_name}}', rendered)
        self.assertNotIn('{{academic_year}}', rendered)
        self.assertNotIn('{{study_name}}', rendered)

    def test_legal_text_rendered_prefers_the_enrollment_study_over_the_group(self):
        order = self._order()
        auth = self.env['ems.authorization'].create({
            'enrollment_id': order.id, 'template_id': self.template.id,
        })
        self.assertIn(self.study.name, auth.legal_text_rendered)
        self.assertNotIn(self.group_study.name, auth.legal_text_rendered)

    def test_acceptance_only_rule_still_applies(self):
        self.template.acceptance_only = True
        auth = self._standalone()
        with self.assertRaises(ValidationError):
            auth.write({'status': 'no', 'signed_document': FAKE_PDF, 'signed_document_name': 'x.pdf'})

    def test_internal_user_must_still_attach_a_document(self):
        auth = self._standalone()
        with self.assertRaises(ValidationError):
            auth.write({'status': 'yes'})

    def test_certificate_filename_falls_back_to_the_course(self):
        auth = self._standalone()
        self.assertIn(self.course.name, auth._certificate_filename())
        self.assertTrue(auth._certificate_filename().endswith('.pdf'))

    def test_display_name_names_the_student_and_the_template(self):
        auth = self._standalone()
        self.assertIn(self.student.name, auth.display_name)
        self.assertIn(self.template.name, auth.display_name)

    def test_a_pending_required_standalone_does_not_block_action_confirm(self):
        """A mid-year authorization must never gate an enrollment: action_confirm()
        reads the enrollment's own one2many, which a standalone row is not part of."""
        order = self._order(with_line=True)
        self.assertTrue(self.template.is_required)
        auth = self._standalone()
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertEqual(auth.status, 'pending')

    def test_portal_user_only_sees_own_authorizations(self):
        """Pins rule_ems_authorization_portal's domain, which moves from
        enrollment_id.partner_id to partner_id."""
        portal_user = self.env['res.users'].create({
            'name': 'Standalone Portal User', 'login': 'standalone_portal_tas',
            'partner_id': self.student.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        mine = self._standalone()
        theirs = self._standalone(student=self.other_student)
        visible = self.env['ems.authorization'].with_user(portal_user).search([])
        self.assertIn(mine, visible)
        self.assertNotIn(theirs, visible)

    def test_missing_partner_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['ems.authorization'].create({
                'course_id': self.course.id, 'template_id': self.template.id,
            })

    def test_missing_course_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['ems.authorization'].create({
                'partner_id': self.student.id, 'template_id': self.template.id,
            })

    def test_duplicate_standalone_is_rejected(self):
        """The ems_authorization_unique_standalone partial index. Last assertion in
        this test on purpose: an IntegrityError leaves the cursor unusable."""
        self._standalone()
        with self.assertRaises(Exception):
            self._standalone()
            self.env.flush_all()
