from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


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

    def test_save_new_contact_without_document_raises(self):
        wizard = self.env['ems.contact.relation.wizard'].create({
            'student_id': self.student.id, 'type_selection_id': self.relation_father.id,
            'is_new_contact': True, 'firstname': 'X', 'lastname': 'Y', 'phone': '600000000',
        })
        with self.assertRaises(ValidationError):
            wizard.action_save()

    def test_save_new_contact_without_contact_method_raises(self):
        wizard = self.env['ems.contact.relation.wizard'].create({
            'student_id': self.student.id, 'type_selection_id': self.relation_father.id,
            'is_new_contact': True, 'firstname': 'X', 'lastname': 'Y', 'document_id': '12345678A',
        })
        with self.assertRaises(ValidationError):
            wizard.action_save()
