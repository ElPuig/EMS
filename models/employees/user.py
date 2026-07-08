# -*- coding: utf-8 -*-

from odoo import models

EMS_SYNC_CONTEXT_KEY = 'ems_syncing_groups'


class ems_users(models.Model):
    _inherit = "res.users"

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
