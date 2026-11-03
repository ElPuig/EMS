# -*- coding: utf-8 -*-

from odoo import models


class IrHttp(models.AbstractModel):
    """The issue-#682 review: tells the backend whether its user has the portal's Erasmus+ page (a
    staff call to apply to, or an application), for the user menu's "Erasmus+"
    (static/src/js/backend/user_menu_erasmus.js). Staff work in the backend, and the page is only
    on the portal."""
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        user = self.env.user
        if self.env.uid and not user.share:
            info['ems_erasmus_portal'] = user.partner_id._ems_erasmus_portal_visible()
        return info
