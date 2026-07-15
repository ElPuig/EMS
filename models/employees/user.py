# -*- coding: utf-8 -*-

from odoo import fields, models

EMS_SYNC_CONTEXT_KEY = 'ems_syncing_groups'


class ems_users(models.Model):
    _inherit = "res.users"

    # Photo visibility: this is the field the user actually sets, from "My Profile"
    # (base.action_res_users_my). hr.employee.image_visibility mirrors it (see employee.py),
    # with a fallback for employees who have no linked user at all.
    image_visibility = fields.Selection(
        [('all', 'All'), ('teachers', 'Only teachers'), ('directive', 'Only directive staff')],
        string="Photo visibility", default='all')

    # Mirror of employee_id.image_private (the real photo storage - see employee.py for why it
    # lives there and not here). Kept as compute+inverse, not a plain related field: a related
    # field's write would go through hr.employee's own ACL (write=0 for teachers), which is
    # exactly what must NOT change for this feature - employee_id is always "my own employee",
    # so the sudo() here doesn't open any access to someone else's record.
    image_private = fields.Binary(string="Photo", compute='_compute_image_private', inverse='_inverse_image_private')

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['image_visibility', 'image_private']

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['image_visibility', 'image_private']

    def _compute_image_private(self):
        for user in self:
            user.image_private = user.employee_id.image_private if user.employee_id else False

    def _inverse_image_private(self):
        for user in self:
            if user.employee_id:
                user.employee_id.sudo().image_private = user.image_private
            # Keep the account picture (topbar/Discuss/chatter, which read res.partner.image_1920)
            # equal to the *real*, unfiltered photo - the visibility restriction only governs
            # hr.employee.image_1920 (see employee.py), not the account avatar used across core
            # Odoo. Written straight to partner_id, not through res.users.image_1920, to avoid
            # cascading back through the whole res.users write() MRO (gamification/mail/resource/
            # base overrides) a second time within the same write().
            user.partner_id.sudo().image_1920 = user.image_private

    def write(self, vals):
        trigger = any(
            k == 'groups_id' or k.startswith(('sel_groups_', 'in_group_'))
            for k in vals
        )
        before = {}
        if trigger and not self.env.context.get(EMS_SYNC_CONTEXT_KEY):
            before = {user: user.groups_id for user in self}
        res = super().write(vals)
        if before:
            self._sync_ems_implied_groups(before)
        return res

    def _sync_ems_implied_groups(self, before):
        """When a user loses an EMS group (Academic/Secretary/Quality/Settings
        role or admin level), also revoke the external, non-EMS native Odoo
        groups that EMS group's implied_ids granted - UNLESS another EMS group
        the user still holds also implies them.

        Odoo's own implied-group mechanism (GroupsImplied.write) is grant-only
        and never revokes; this compensates for that specifically within the
        EMS-managed group set. It intentionally does NOT touch external groups
        an admin granted manually and unrelated to any EMS group the user ever
        held - there is no way to distinguish that case from an EMS-implied
        grant once both are rows in res_groups_users_rel; this is an accepted,
        documented limitation.

        Only the *direct* implied_ids declared on the removed EMS group(s) are
        considered - not their full transitive closure. Groups like
        `sales_team.group_sale_salesman_all_leads` (one of Secretary's direct
        grants) themselves transitively imply very generic, foundational
        groups (e.g. `base.group_user` "Internal User") that are not specific
        to EMS and that virtually every internal user needs regardless of
        their EMS role; chasing the full transitive closure would revoke
        those too and could effectively lock a user out. Staying at depth 1
        matches exactly what security/groups.xml itself declares as "granted
        by this EMS group", which is enough to fix every case in this module
        (Attendances, Sales/Invoicing/Bank/Contact Creation, hr.group_hr_manager,
        Settings' Access Rights/Settings/Canned Responses/Job Queue).
        """
        ems_root = self.env.ref('ems.category_main')
        ems_groups = self.env['res.groups'].sudo().search(
            [('category_id', 'child_of', ems_root.id)])
        for user in self:
            removed_ems_groups = (before.get(user, self.env['res.groups']) & ems_groups) - user.groups_id
            if not removed_ems_groups:
                continue
            orphaned = removed_ems_groups.implied_ids - ems_groups
            still_justified = (user.groups_id & ems_groups).trans_implied_ids
            to_revoke = (orphaned - still_justified) & user.groups_id
            if to_revoke:
                user.sudo().with_context(**{EMS_SYNC_CONTEXT_KEY: True}).write(
                    {'groups_id': [(3, g.id) for g in to_revoke]})
