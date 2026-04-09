from odoo import models, fields

class ResPartnerRelationAll(models.AbstractModel):
    _inherit = 'res.partner.relation.all'

    other_partner_relation = fields.Char(related='type_id.name', string='Relation', readonly=True)
    other_partner_phone = fields.Char(related='other_partner_id.phone', string='Phone')
    other_partner_mobile = fields.Char(related='other_partner_id.mobile', string='Mobile')
    other_partner_email = fields.Char(related='other_partner_id.email', string='Email')
