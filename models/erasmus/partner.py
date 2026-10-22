# -*- coding: utf-8 -*-

from odoo import models


class ResPartner(models.Model):
    """Issue #683 - which Erasmus+ calls a student sees on the portal."""
    _inherit = 'res.partner'

    def _ems_erasmus_calls(self):
        """Published calls with a modality for this student's level, open or not yet."""
        self.ensure_one()
        level = self.contact_type == 'student' and self.main_group_id.level_id
        if not level:
            return self.env['ems.erasmus.call']
        return self.env['ems.erasmus.call'].sudo().search([
            ('state', '=', 'published'), ('modality_ids.level_ids', 'in', level.ids)])

    def _ems_erasmus_applications(self):
        self.ensure_one()
        return self.env['ems.erasmus.application'].sudo().search([('partner_id', '=', self.id)])

    def _ems_erasmus_portal_visible(self):
        """The portal's Erasmus+ card: for students who can apply to a published call or already
        applied to one. Families do not see it."""
        self.ensure_one()
        return bool(self._ems_erasmus_calls() or self._ems_erasmus_applications())
