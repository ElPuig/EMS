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
            if home := self._ems_erasmus_home_action(user):
                info['home_action_id'] = home
        return info

    def _ems_erasmus_home_action(self, user):
        """The 2026-11-04 usage test: a member of the Erasmus team who is not a teacher landed on the
        roll call (every new account's default home) and got an access error. They land on the
        Erasmus+ calls instead; a home chosen on purpose is never changed."""
        roll_call = {self.env.ref('ems.action_attendance_passlist').id,
                     self.env.ref('ems.action_attendance_session_tree').id}
        if user.action_id.id in roll_call and user.has_group('ems.group_erasmus') \
                and not user.has_group('ems.group_teacher'):
            return self.env.ref('ems.action_erasmus_call').id
        return None
