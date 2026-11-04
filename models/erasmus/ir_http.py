# -*- coding: utf-8 -*-

from odoo import models


class IrHttp(models.AbstractModel):
    """The issue-#682 review: tells the backend whether its user has a staff call to apply to, or
    an application, for the user menu's "Erasmus+" (static/src/js/backend/user_menu_erasmus.js),
    which opens the staff calls in the backend (staff never use the portal, the 2026-11-04 review)."""
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        user = self.env.user
        if self.env.uid and not user.share:
            info['ems_erasmus_staff'] = bool(self.env['ems.erasmus.call']._ems_staff_calls_of(user.partner_id))
        return info
