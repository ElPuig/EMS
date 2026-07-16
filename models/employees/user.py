# -*- coding: utf-8 -*-

from odoo import _, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError
from .employee import _UNSET, EMS_PHOTO_SYNC_CONTEXT_KEY, write_photo

EMS_SYNC_CONTEXT_KEY = 'ems_syncing_groups'


class ems_users(models.Model):
    _inherit = "res.users"

    # Single switch, set from "My Profile" (base.action_res_users_my). While True, nobody -
    # not even an admin, from any form - may change image_1920 on this user's partner or on
    # the linked hr.employee (see write() here and in employee.py); the photo becomes Odoo's
    # own initials placeholder. There is no automatic restore on re-enable: re-enabling just
    # allows a fresh upload again.
    image_disabled = fields.Boolean(string="Disable profile picture", default=False)

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['image_disabled']

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['image_disabled']

    def write(self, vals):
        trigger = any(
            k == 'groups_id' or k.startswith(('sel_groups_', 'in_group_'))
            for k in vals
        )
        before = {}
        if trigger and not self.env.context.get(EMS_SYNC_CONTEXT_KEY):
            before = {user: user.groups_id for user in self}

        syncing_photo = self.env.context.get(EMS_PHOTO_SYNC_CONTEXT_KEY)
        disabling = vals.get('image_disabled') is True
        photo = vals.pop('image_1920', _UNSET)
        if photo is not _UNSET and not syncing_photo:
            for user in self:
                # Use the state image_disabled WILL have after this write (vals, if
                # present, wins over the current DB value) - not just the current DB
                # value - so re-enabling and uploading a new photo in the same save (e.g.
                # "My Profile": untick "Disable profile picture" and pick a file, then
                # Save once) works in one step instead of needing two separate saves.
                will_be_disabled = vals.get('image_disabled', user.image_disabled)
                if will_be_disabled:
                    raise UserError(_("The profile picture is disabled; it cannot be changed."))

        res = super().write(vals)

        if photo is not _UNSET:
            for user in self:
                write_photo(user.partner_id.sudo(), photo)

        if before:
            self._sync_ems_implied_groups(before)

        if disabling:
            for user in self:
                # res.users has no avatar.mixin method of its own (only its delegated FIELDS
                # are auto-generated via _inherits) - generate the placeholder from the
                # partner, which does inherit avatar.mixin directly.
                placeholder = user.partner_id._avatar_generate_svg()
                # ir_attachment._check_contents forces any XML-like mimetype (SVG included)
                # down to 'text/plain' unless the acting user can write ir.ui.view - checked
                # with sudo(False), so a plain .sudo() wrapper does NOT bypass it (by design,
                # to stop a non-admin sneaking a script-bearing SVG through a sudo'd write).
                # with_user(SUPERUSER_ID) genuinely changes the acting user for this
                # placeholder write, which is what actually clears that check - without it,
                # a teacher disabling their own photo gets a mislabeled attachment that
                # browsers refuse to render as an image ("Binary file" instead of the
                # placeholder).
                synced = user.with_user(SUPERUSER_ID).with_context(**{EMS_PHOTO_SYNC_CONTEXT_KEY: True})
                write_photo(synced.partner_id, placeholder)
                if user.employee_id:
                    write_photo(synced.employee_id, placeholder)
        elif photo is not _UNSET and not syncing_photo:
            for user in self:
                if user.employee_id:
                    write_photo(
                        user.employee_id.sudo().with_context(**{EMS_PHOTO_SYNC_CONTEXT_KEY: True}),
                        user.image_1920)

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
