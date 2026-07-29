import base64
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study

FAKE_PDF = base64.b64encode(b'%PDF-1.4 fake test content')


class TestAuthorizationTemplate(TransactionCase):
    """models/enrollment/authorization.py — EmsAuthorizationTemplate.

    See docs/en/developers/enrollment/authorization.md for the two
    different level/study matching semantics this class covers: this
    template's own retroactive apply/remove (AND-of-scopes) vs
    sale.order._get_authorization_commands' live onchange sync
    (OR-of-scopes, tested in tests/test_enrollment_header.py).
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
        cls.student1 = cls.env['res.partner'].create({'name': 'Auth Student 1', 'contact_type': 'student'})
        cls.student2 = cls.env['res.partner'].create({'name': 'Auth Student 2', 'contact_type': 'student'})
        cls.student3 = cls.env['res.partner'].create({'name': 'Auth Student 3', 'contact_type': 'student'})

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
        """Known gap: this is AND-of-scopes, unlike the OR-of-scopes used by
        sale.order._get_authorization_commands for the live onchange sync
        (test_enrollment_header.py::test_apply_authorizations_adds_matching_template
        exercises the OR side of the same scoping fields)."""
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
        cls.student = cls.env['res.partner'].create({'name': 'Auth Response Student', 'contact_type': 'student'})
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
