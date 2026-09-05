from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group


class TestContactRelationWizard(TransactionCase):
    """ems.contact.relation.wizard: adds a family contact (new or existing) and
    creates the res.partner.relation between it and a student."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = cls.env['res.partner'].create({
            'name': 'Relation Wizard Student', 'contact_type': 'student',
            'street': 'Carrer Test', 'city': 'Santa Coloma'})
        cls.relation_father = cls.env.ref('ems.relation_type_father')

        # Fixtures for the permission checks in action_save(): a real tutor (of the
        # student's group) vs. a teacher who isn't - res.partner/res.partner.relation
        # are locked down for teachers at the ir.model.access/ir.rule level (see
        # security/ir.model.access.csv, security/rules/contacts.xml), so action_save()
        # must sudo() past that only for a user actually authorized to manage this
        # student (mirrors the "Add contact" button's own visibility condition).
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Test Tutor (Relation Wizard)', 'employee_type': 'teacher',
        })
        cls.tutor_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Tutor User (Relation Wizard)', 'login': 'test_tutor_relation_wizard',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.tutor_employee.user_id = cls.tutor_user
        cls.other_teacher_employee = cls.env['hr.employee'].create({
            'name': 'Test Other Teacher (Relation Wizard)', 'employee_type': 'teacher',
        })
        cls.other_teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Other Teacher User (Relation Wizard)', 'login': 'test_other_teacher_relation_wizard',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.other_teacher_employee.user_id = cls.other_teacher_user
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'TCRW', level={'name': 'Test Contact Relation Wizard Level'}, study={
                'code': 'TCRW001', 'acronym': 'TCRW', 'name': 'Test Contact Relation Wizard Study',
            }, group={'tutor_id': cls.tutor_employee.id})
        cls.student.main_group_id = cls.group.id

    def test_onchange_student_id_prefills_address(self):
        wizard = self.env['ems.contact.relation.wizard'].new({'student_id': self.student.id})
        wizard._onchange_student_id()
        self.assertEqual(wizard.street, self.student.street)
        self.assertEqual(wizard.city, self.student.city)

    def test_save_new_contact_creates_partner_and_relation(self):
        wizard = self.env['ems.contact.relation.wizard'].create({
            'student_id': self.student.id,
            'type_selection_id': self.relation_father.id,
            'is_new_contact': True,
            'firstname': 'New', 'lastname': 'Father',
            'phone': '600000000',
            'document_id': '12345678A',
        })
        wizard.action_save()
        new_partner = self.env['res.partner'].search([('lastname', '=', 'Father'), ('firstname', '=', 'New')])
        self.assertTrue(new_partner)
        self.assertEqual(new_partner.contact_type, 'family')
        relation = self.env['res.partner.relation'].search([
            ('left_partner_id', '=', new_partner.id), ('right_partner_id', '=', self.student.id)])
        self.assertTrue(relation)
        self.assertEqual(relation.type_id, self.relation_father)

    def test_save_existing_contact_only_creates_relation(self):
        existing = self.env['res.partner'].create({
            'name': 'Existing Family Contact', 'contact_type': 'family'})
        wizard = self.env['ems.contact.relation.wizard'].create({
            'student_id': self.student.id,
            'type_selection_id': self.relation_father.id,
            'partner_id': existing.id,
        })
        wizard.action_save()
        relation = self.env['res.partner.relation'].search([
            ('left_partner_id', '=', existing.id), ('right_partner_id', '=', self.student.id)])
        self.assertTrue(relation)
        self.assertEqual(self.env['res.partner'].search_count([('lastname', '=', False), ('firstname', '=', False)]), 0)

    def test_save_without_relation_type_raises(self):
        wizard = self.env['ems.contact.relation.wizard'].create({
            'student_id': self.student.id, 'is_new_contact': True,
            'firstname': 'X', 'lastname': 'Y', 'phone': '600000000', 'document_id': '12345678A',
        })
        with self.assertRaises(ValidationError):
            wizard.action_save()

    def test_save_new_contact_without_name_raises(self):
        wizard = self.env['ems.contact.relation.wizard'].create({
            'student_id': self.student.id, 'type_selection_id': self.relation_father.id,
            'is_new_contact': True,
        })
        with self.assertRaises(ValidationError):
            wizard.action_save()

    def test_save_new_contact_without_document_succeeds(self):
        # Developer feedback (2026-09-05): the identification document (DNI/NIE or
        # passport) must not be mandatory - a family contact is frequently added
        # before that information is available.
        wizard = self.env['ems.contact.relation.wizard'].create({
            'student_id': self.student.id, 'type_selection_id': self.relation_father.id,
            'is_new_contact': True, 'firstname': 'X', 'lastname': 'Y', 'phone': '600000000',
        })
        wizard.action_save()
        new_partner = self.env['res.partner'].search([('lastname', '=', 'Y'), ('firstname', '=', 'X')])
        self.assertTrue(new_partner)
        self.assertFalse(new_partner.document_id)
        self.assertFalse(new_partner.passport_id)

    def test_save_new_contact_without_contact_method_raises(self):
        wizard = self.env['ems.contact.relation.wizard'].create({
            'student_id': self.student.id, 'type_selection_id': self.relation_father.id,
            'is_new_contact': True, 'firstname': 'X', 'lastname': 'Y', 'document_id': '12345678A',
        })
        with self.assertRaises(ValidationError):
            wizard.action_save()

    def test_save_as_tutor_of_record_succeeds(self):
        # Reproduces the reported bug: a tutor could open the wizard and fill it in,
        # but action_save() failed - res.partner/res.partner.relation have no create
        # rights for teachers (see security/ir.model.access.csv, rules/contacts.xml).
        wizard = self.env['ems.contact.relation.wizard'].with_user(self.tutor_user).create({
            'student_id': self.student.id, 'type_selection_id': self.relation_father.id,
            'is_new_contact': True, 'firstname': 'Tutor', 'lastname': 'Saved', 'phone': '600000000',
        })
        wizard.action_save()
        new_partner = self.env['res.partner'].search([('lastname', '=', 'Saved'), ('firstname', '=', 'Tutor')])
        self.assertTrue(new_partner)
        relation = self.env['res.partner.relation'].search([
            ('left_partner_id', '=', new_partner.id), ('right_partner_id', '=', self.student.id)])
        self.assertTrue(relation)

    def test_save_as_tutor_of_record_with_existing_contact_succeeds(self):
        existing = self.env['res.partner'].create({
            'name': 'Existing Family Contact (Tutor)', 'contact_type': 'family'})
        wizard = self.env['ems.contact.relation.wizard'].with_user(self.tutor_user).create({
            'student_id': self.student.id, 'type_selection_id': self.relation_father.id,
            'partner_id': existing.id,
        })
        wizard.action_save()
        relation = self.env['res.partner.relation'].search([
            ('left_partner_id', '=', existing.id), ('right_partner_id', '=', self.student.id)])
        self.assertTrue(relation)

    def test_save_as_non_tutoring_teacher_raises_access_error(self):
        # other_teacher_user is a real teacher (holds ems.group_teacher, can open the
        # wizard), but is not this student's tutor - must stay blocked.
        wizard = self.env['ems.contact.relation.wizard'].with_user(self.other_teacher_user).create({
            'student_id': self.student.id, 'type_selection_id': self.relation_father.id,
            'is_new_contact': True, 'firstname': 'Should', 'lastname': 'Fail', 'phone': '600000000',
        })
        with self.assertRaises(AccessError):
            wizard.action_save()
