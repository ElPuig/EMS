# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .mobility import host_place_vals
from .staff_backend import staff_wizard


class EmsErasmusMobility(models.Model):
    _inherit = 'ems.erasmus.mobility'

    def action_open_destination_wizard(self):
        """Issue #786 (5.16): the agreed destination is asked for in a dialog."""
        self.ensure_one()
        self._ems_check_manager()
        return staff_wizard(self.env, 'ems.erasmus.mobility.destination.wizard', _("Set the agreed destination"),
                            mobility_id=self.id, country_id=self.country_id.id, city=self.city,
                            host_partner_id=self.host_partner_id.id,
                            date_start=fields.Date.to_string(self.date_start),
                            date_end=fields.Date.to_string(self.date_end))

    def action_open_cancel_wizard(self):
        """Issue #786 (5.15, 8.11): the reason for cancelling is asked for in a dialog."""
        self.ensure_one()
        self._ems_check_manager()
        return staff_wizard(self.env, 'ems.erasmus.mobility.cancel.wizard', _("Cancel the mobility"),
                            mobility_id=self.id)


class EmsErasmusMobilityCancelWizard(models.TransientModel):
    """Issue #786 (5.15, 8.11): the Erasmus team cancels a mobility saying why, in one step, instead of
    writing the reason in a tab first and getting an error otherwise. Same pattern as cancelling a
    convalidation request (`ems.convalidation.cancel_wizard`)."""
    _name = 'ems.erasmus.mobility.cancel.wizard'
    _description = 'Erasmus+ cancel a mobility'

    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', required=True,
                                  ondelete='cascade')
    partner_id = fields.Many2one(string="Participant", related='mobility_id.partner_id')
    reason = fields.Text(string="Reason", required=True,
                         help="Why the mobility is cancelled (e.g. travel documents not handed in on time). It "
                              "stays on the mobility.")

    def action_confirm(self):
        self.ensure_one()
        reason = (self.reason or '').strip()
        if not reason:
            raise UserError(_("Write the reason for cancelling first."))
        mobility = self.mobility_id
        mobility._ems_check_manager()
        mobility.write({'cancel_reason': reason})
        mobility.action_cancel()
        return {'type': 'ir.actions.act_window_close'}


class EmsErasmusMobilityDestinationWizard(models.TransientModel):
    """Issue #786 (5.16): the destination the Erasmus team agreed with a student (art. 15), asked for
    when setting it instead of failing when the country was not written on the mobility first."""
    _name = 'ems.erasmus.mobility.destination.wizard'
    _description = 'Erasmus+ set the agreed destination'

    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', required=True,
                                  ondelete='cascade')
    partner_id = fields.Many2one(string="Participant", related='mobility_id.partner_id')
    country_id = fields.Many2one(string="Country", comodel_name='res.country', required=True)
    city = fields.Char(string="City")
    host_partner_id = fields.Many2one(string="Host entity", comodel_name='res.partner',
                                      domain="[('is_erasmus_host', '=', True)]")
    date_start = fields.Date(string="Start")
    date_end = fields.Date(string="End")

    @api.onchange('host_partner_id')
    def _onchange_host_partner_id(self):
        """Issue #788 (13.6): the entity's country and city, as on the mobility."""
        self.update(host_place_vals(self, self.host_partner_id))

    def action_confirm(self):
        self.ensure_one()
        mobility = self.mobility_id
        mobility._ems_check_manager()
        if self.date_start and self.date_end and self.date_end < self.date_start:
            raise UserError(_("The end of the stay cannot be before its start."))
        mobility.write({'country_id': self.country_id.id, 'city': self.city,
                        'host_partner_id': self.host_partner_id.id, 'date_start': self.date_start,
                        'date_end': self.date_end})
        mobility.action_agree_destination()
        return {'type': 'ir.actions.act_window_close'}
