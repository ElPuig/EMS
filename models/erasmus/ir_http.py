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
