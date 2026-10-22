# -*- coding: utf-8 -*-

from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _visible_menu_ids(self, debug=False):
        """Hides Academic management > Enrollment > Enrollment proposal outside the pre-enrollment
        period from whoever res.company._ems_preenrollment_closed_for_user() keeps out (issue
        #654), and every folder above it left with nothing to open (Odoo shows a folder only
        through a visible child, a decision super() has already taken). super()'s set is ormcached
        and shared: never changed in place. The opening and closing reach the cached menus
        through res.company._ems_sync_preenrollment_period()."""
        visible = super()._visible_menu_ids(debug)
        proposal = self.env.ref('ems.menu_students_tutor', raise_if_not_found=False)
        if not proposal or proposal.id not in visible \
                or not self.env.company._ems_preenrollment_closed_for_user():
            return visible
        visible = visible - {proposal.id}
        folder = proposal.with_context(**{'ir.ui.menu.full_list': True}).sudo().parent_id
        while folder and not folder.action and folder.id in visible \
                and visible.isdisjoint(folder.child_id.ids):
            visible.discard(folder.id)
            folder = folder.parent_id
        return visible
