# -*- coding: utf-8 -*-

import logging
import traceback

from odoo import _, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError
from .employee import _UNSET, write_photo

_logger = logging.getLogger(__name__)

EMS_SYNC_CONTEXT_KEY = 'ems_syncing_groups'


def _group_change_caller():
    """Nearest EMS function up the stack that isn't one of the write() overrides doing the
    logging itself, i.e. the code that actually asked for the change. None means no EMS code was
    involved: an admin in Settings > Users, or Odoo itself."""
    for frame in reversed(traceback.extract_stack()[:-2]):
        if '/ems/' not in frame.filename:
            continue
        path = frame.filename.split('/ems/')[-1]
        if frame.name == 'write' and path in ('models/employees/user.py', 'models/employees/group.py'):
            continue
        return f"{frame.name} ({path}:{frame.lineno})"
    return None


def log_group_changes(env, before, after):
    """Logs, per user, the security groups granted and revoked between two {user: groups}
    snapshots (issue #535: a group granted by hand kept disappearing and nothing recorded who
    or what removed it). Server log only, never the database: these changes are rare."""
    caller = _group_change_caller() or "no EMS code (Settings > Users or Odoo itself)"
    for user, groups_before in before.items():
        groups_after = after.get(user, env['res.groups'])
        added, removed = groups_after - groups_before, groups_before - groups_after
        if added or removed:
            _logger.info(
                "Security groups of %s (user %s) changed by %s (uid %s) via %s: added [%s]; removed [%s]",
                user.login, user.id, env.user.login, env.uid, caller,
                ", ".join(added.mapped('full_name')), ", ".join(removed.mapped('full_name')))

# "Private Information" tab fields (hr/views/res_users.xml's "personal_information" page) -
# always self-editable regardless of "can_edit"/administrator status (developer feedback
# 2026-09-10: personal, not professional, data - the user is free to modify it). Deliberately
# excludes 'additional_note' (also in hr's own HR_WRITABLE_FIELDS, but an HR-authored note about
# the employee, not shown on this tab at all - not something the employee should freely rewrite).
PRIVATE_INFO_SELF_EDITABLE_FIELDS = frozenset({
    'private_street', 'private_street2', 'private_city', 'private_state_id', 'private_zip',
    'private_country_id', 'private_email', 'private_phone', 'private_lang',
    'employee_bank_account_id', 'distance_home_work', 'distance_home_work_unit',
    'employee_country_id', 'identification_id', 'ssnid', 'passport_id', 'gender', 'birthday',
    'place_of_birth', 'country_of_birth', 'marital', 'spouse_complete_name', 'spouse_birthdate',
    'certificate', 'study_field', 'study_school', 'children', 'emergency_contact',
    'emergency_phone', 'visa_no', 'permit_no', 'visa_expire',
})


class ems_users(models.Model):
    _inherit = "res.users"

    # Single switch, set from "My Profile" (base.action_res_users_my). While True, nobody -
    # not even an admin, from any form - may change image_1920 on this user's partner or on
    # the linked hr.employee (see write() here and in employee.py); the photo becomes Odoo's
    # own initials placeholder. There is no automatic restore on re-enable: re-enabling just
    # allows a fresh upload again.
    image_disabled = fields.Boolean(string="Disable profile picture", default=False)

    # "Schedule" tab on the My Profile screen (see views/community/employee/
    # user_profile_form.xml): reuses the exact same 'schedule_grid' OWL widget as the
    # teacher's own "Schedule" tab (views/community/employee/form.xml), which hardcodes
    # 'resource_calendar_id' and 'can_edit_schedule' as field names to read off the record
    # (schedule_grid_field.js). 'res.users' already has its OWN native 'resource_calendar_id'
    # (from the 'resource' module, related='resource_ids.calendar_id') - re-declaring it here
    # to point at 'employee_id.resource_calendar_id' instead would have hijacked that
    # unrelated native mechanism. No override needed though: since 'hr.employee.resource_id'
    # (a 'resource.mixin' field) always carries the same 'user_id' as the linked user, both
    # paths already resolve to the very same 'resource.calendar' record - verified empirically
    # against every teacher in this dev DB. Only 'can_edit_schedule' and
    # 'schedule_attendance_ids' are genuinely new fields.
    can_edit_schedule = fields.Boolean(related="employee_id.can_edit_schedule")
    schedule_attendance_ids = fields.One2many(
        string="Schedule", related="employee_id.schedule_attendance_ids")

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['image_disabled']

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            'image_disabled', 'resource_calendar_id', 'can_edit_schedule',
            'schedule_attendance_ids',
        ]

    def write(self, vals):
        # "Private Information": always self-editable regardless of "can_edit" - hr's own
        # write() (hr/models/res_users.py) blocks ANY hr.employee-related field for a self-edit
        # unless "can_edit" is True, with no per-field exception of its own. Elevating to
        # SUPERUSER_ID only for this carved-out field set (never the rest of vals) makes
        # 'self.env.user.has_group(...)' resolve True inside that check, without touching
        # anything else this same write might also be doing. The re-entrant write() call below
        # naturally skips this same branch (its own 'self.env.user' is then the superuser, not
        # this record, so 'self == self.env.user' is False) - no separate recursion guard needed.
        private_vals = {}
        if self == self.env.user and not self.can_edit:
            private_vals = {k: vals.pop(k) for k in list(vals) if k in PRIVATE_INFO_SELF_EDITABLE_FIELDS}

        trigger = any(
            k == 'groups_id' or k.startswith(('sel_groups_', 'in_group_'))
            for k in vals
        )
        groups_before = {user: user.groups_id for user in self.sudo()} if trigger else {}
        before = {}
        if trigger and not self.env.context.get(EMS_SYNC_CONTEXT_KEY):
            before = groups_before

        disabling = vals.get('image_disabled') is True
        photo = vals.pop('image_1920', _UNSET)
        if photo is not _UNSET:
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

        if groups_before:
            log_group_changes(self.env, groups_before, {user: user.groups_id for user in groups_before})

        if private_vals:
            self.with_user(SUPERUSER_ID).write(private_vals)

        if photo is not _UNSET:
            for user in self:
                write_photo(user.partner_id.sudo(), photo)

        if before:
            self._sync_ems_implied_groups(before)

        if disabling:
            self._refresh_photo_placeholder()
        elif photo is not _UNSET:
            for user in self:
                if user.employee_id:
                    write_photo(user.employee_id.sudo(), user.image_1920)

        return res

    def _refresh_photo_placeholder(self):
        """(Re)generate the initials placeholder SVG from the current partner name and
        bake it into both the partner and the linked employee's stored photo.

        Called when "Disable profile picture" is (first) confirmed, and again from
        hr.employee._refresh_stale_avatar_placeholder() (employee.py) whenever a
        name change leaves a stale initial behind - unlike the rest of the app's
        avatar (avatar_mixin, non-stored compute), a baked placeholder is a one-time
        write into image_1920 itself, so it does not track a later name change on
        its own and needs this explicit refresh instead.
        """
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
            # a teacher disabling their own photo (or an admin renaming them afterwards)
            # gets a mislabeled attachment that browsers refuse to render as an image
            # ("Binary file" instead of the placeholder).
            synced = user.with_user(SUPERUSER_ID)
            write_photo(synced.partner_id, placeholder)
            if user.employee_id:
                write_photo(synced.employee_id, placeholder)

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
