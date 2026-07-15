# -*- coding: utf-8 -*-

import base64

from odoo import fields, models
from .employee import EMS_PHOTO_SYNC_CONTEXT_KEY

EMS_SYNC_CONTEXT_KEY = 'ems_syncing_groups'


class ems_users(models.Model):
    _inherit = "res.users"

    # Photo visibility: this is the field the user actually sets, from "My Profile"
    # (base.action_res_users_my). hr.employee.image_visibility mirrors it (see employee.py),
    # with a fallback for employees who have no linked user at all.
    image_visibility = fields.Selection(
        [('public', 'Public'), ('private', 'Private (only directive staff)'),
         ('no_photo', 'No photo (erase permanently)')],
        string="Photo visibility", default='public')

    # Mirror of employee_id.image_private (the real photo storage - see employee.py for why it
    # lives there and not here). Read-only from "My Profile" (see SELF_WRITEABLE_FIELDS below) -
    # only directive staff and above may actually change a photo (hr.employee.can_edit_photo /
    # write()'s sudo bypass); a plain employee only ever controls image_visibility here.
    image_private = fields.Binary(string="Photo", compute='_compute_image_private', inverse='_inverse_image_private')

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['image_visibility']

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
        if (vals.keys() & {'image_visibility', 'image_private'}
                and not self.env.context.get(EMS_PHOTO_SYNC_CONTEXT_KEY)):
            self._sync_partner_photo()
        return res

    def _sync_partner_photo(self):
        """Keep the linked contact's (res.partner) photo consistent with what "My Profile"
        just set - this is what makes the visibility restriction truly global (Discuss, the
        top bar, the org chart, ems.notice.sent_by, anywhere else that reads a user's own
        avatar instead of hr.employee's), without needing to gate res.partner.image_1920 for
        every contact in the database (students, families, companies...).

        'no_photo' erases the real photo for good (GDPR) - everywhere it's stored, not just
        hidden. Otherwise, back up the contact's current photo into its own image_private the
        first time it goes through this sync (it may still hold the real, pre-feature photo),
        then push whatever hr.employee.image_1920 currently resolves to (real photo, or the
        initials placeholder - see employee.py's _compute_image_1920): this mirrors exactly
        what the employee's own kanban/form already show to an unauthorized viewer.
        """
        for user in self:
            if not user.employee_id:
                continue
            employee = user.employee_id.sudo().with_context(**{EMS_PHOTO_SYNC_CONTEXT_KEY: True})
            partner = user.partner_id.sudo()
            if user.image_visibility == 'no_photo':
                employee.image_private = False
                partner.image_private = False
            elif not partner.image_private and self._partner_has_real_image_1920(partner):
                partner.image_private = partner.image_1920
            partner.image_1920 = employee.image_1920

    def _partner_has_real_image_1920(self, partner):
        # image_1920 always has SOME value on a res.users' partner - Odoo auto-generates an SVG
        # initials placeholder on user creation (res.users.create()) when none is set, and this
        # feature itself writes one whenever visibility isn't 'public' (see employee.py). That's
        # not a real photo to back up: without this check, a sync would "back up" a placeholder
        # as if it were the real photo, and every later sync would just keep re-serving it.
        #
        # Checks the decoded bytes directly (not ir_attachment.mimetype): overwriting an
        # attachment's content in place does not necessarily re-detect its mimetype, so a
        # placeholder written over a real photo's attachment can keep reporting the OLD, real
        # mimetype - unreliable. The actual content is always authoritative.
        if not partner.image_1920:
            return False
        try:
            decoded = base64.b64decode(partner.image_1920)
        except (ValueError, TypeError):
            return True
        return not decoded.lstrip().startswith(b'<?xml')

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
