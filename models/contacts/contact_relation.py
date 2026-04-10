from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ems_partner_relation_all(models.AbstractModel):
    _inherit = 'res.partner.relation.all'

    other_partner_relation = fields.Char(related='type_id.name', string='Relation', readonly=True)
    other_partner_phone = fields.Char(related='other_partner_id.phone', string='Phone')
    other_partner_mobile = fields.Char(related='other_partner_id.mobile', string='Mobile')
    other_partner_email = fields.Char(related='other_partner_id.email', string='Email')

class ems_contact_relation_wizard(models.TransientModel):
    _name = 'ems.contact.relation.wizard'
    _description = 'Add family contact and relation'

    student_id = fields.Many2one('res.partner', string='Student', readonly=True)
    type_selection_id = fields.Many2one('res.partner.relation.type', string='Relation')
    is_new_contact = fields.Boolean(string='New contact', default=False)
    partner_id = fields.Many2one('res.partner', string='Existing contact',
                                  domain=[('contact_type', '=', 'family')])
    firstname = fields.Char(string='First name')
    lastname = fields.Char(string='Last name')
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    email = fields.Char(string='Email')
    document_id = fields.Char(string='Document ID (DNI/NIE)')
    passport_id = fields.Char(string='Passport')
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street 2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one('res.country', string='Country')

    @api.onchange('student_id')
    def _onchange_student_id(self):
        if self.student_id:
            self.street = self.student_id.street
            self.street2 = self.student_id.street2
            self.city = self.student_id.city
            self.state_id = self.student_id.state_id
            self.zip = self.student_id.zip
            self.country_id = self.student_id.country_id

    def action_save(self):
        if not self.type_selection_id:
            raise ValidationError("Please select a relation type.")
        if not self.partner_id and not (self.firstname or self.lastname):
            raise ValidationError("Please select an existing contact or enter a first/last name for the new one.")
        if not self.partner_id:
            if not (self.document_id or self.passport_id):
                raise ValidationError("Please provide at least one identification document (DNI/NIE or Passport).")
            if not (self.phone or self.mobile or self.email):
                raise ValidationError("Please provide at least one contact method (phone, mobile or email).")

        if self.partner_id:
            partner = self.partner_id
        else:
            partner = self.env['res.partner'].create({
                'firstname': self.firstname,
                'lastname': self.lastname,
                'phone': self.phone,
                'mobile': self.mobile,
                'email': self.email,
                'document_id': self.document_id,
                'passport_id': self.passport_id,
                'contact_type': 'family',
                'street': self.street,
                'street2': self.street2,
                'city': self.city,
                'state_id': self.state_id.id,
                'zip': self.zip,
                'country_id': self.country_id.id,
            })

        self.env['res.partner.relation'].create({
            'left_partner_id': partner.id,
            'type_id': self.type_selection_id.id,
            'right_partner_id': self.student_id.id,
        })
