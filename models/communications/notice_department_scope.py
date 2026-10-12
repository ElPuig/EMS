# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Groups whose notices are not limited to their own department's groups: they reach every group
# (see security/rules/communications.xml). Department chiefs - and Seminar chiefs, the same
# res.groups - are limited; Head of Studies implies their group but is not.
UNRESTRICTED_NOTICE_GROUPS = (
    'ems.group_academic_admin', 'ems.group_director', 'ems.group_head_of_studies', 'ems.group_quality_admin',
)


class EmsGroupDepartmentScope(models.Model):
    _inherit = 'ems.group'

    # The users who chief a department (as its Department Chief or its Seminar Chief) one of whose
    # teachers - or a teacher of one of its sub-departments - teaches this group: the groups a
    # department chief may send notices to. Not stored: always follows the current teaching
    # assignments (ems.teaching, kept in step with every teacher's schedule) and department heads.
    department_chief_user_ids = fields.Many2many(
        string="Department chiefs", comodel_name='res.users',
        compute='_compute_department_chief_user_ids', search='_search_department_chief_user_ids', compute_sudo=True)

    def _compute_department_chief_user_ids(self):
        teachings = self.env['ems.teaching'].sudo().search([('group_id', 'in', self.ids)])
        for group in self:
            users = self.env['res.users']
            departments = teachings.filtered(lambda teaching, group=group: teaching.group_id == group).teacher_id.department_id
            seen = self.env['hr.department']
            while departments - seen:
                seen |= departments
                users |= departments.manager_id.user_id | departments.seminar_chief_id.user_id
                departments = departments.parent_id
            group.department_chief_user_ids = users

    def _search_department_chief_user_ids(self, operator, value):
        if operator not in ('=', 'in'):
            raise NotImplementedError(_("Unsupported search on department_chief_user_ids"))
        user_ids = [user_id for user_id in ([value] if isinstance(value, int) else value or []) if user_id]
        chiefs = self.env['hr.employee'].sudo().search([('user_id', 'in', user_ids)])
        headed = self.env['hr.department'].sudo().search([
            '|', ('manager_id', 'in', chiefs.ids), ('seminar_chief_id', 'in', chiefs.ids)])
        if not headed:
            return [('id', '=', False)]
        teachings = self.env['ems.teaching'].sudo().search([('teacher_id.department_id', 'child_of', headed.ids)])
        return [('id', 'in', teachings.group_id.ids)]


class EmsNoticeDepartmentScope(models.Model):
    """Department and Seminar chiefs send notices too, but only to the groups their department
    teaches (see ems.group.department_chief_user_ids): the record rules let them read notices
    addressed to those groups and manage their own, and this constraint keeps what they write
    within those groups."""
    _inherit = 'ems.notice'

    # The groups the current user may address - what the form's Groups field offers.
    available_group_ids = fields.Many2many(
        string="Available groups", comodel_name='ems.group', compute='_compute_available_group_ids')

    @api.model
    def _user_notice_groups(self):
        """The groups the current user may send notices to, or None for every group."""
        user = self.env.user
        if self.env.su or not user.has_group('ems.group_department_chief') or any(
                user.has_group(xmlid) for xmlid in UNRESTRICTED_NOTICE_GROUPS):
            return None
        return self.env['ems.group'].search([('department_chief_user_ids', 'in', user.id)])

    # 'state' is only there so a new record's onchange computes it at all: a compute with no
    # dependency is never evaluated there, which left the Groups field offering nothing.
    @api.depends('state')
    @api.depends_context('uid')
    def _compute_available_group_ids(self):
        allowed = self._user_notice_groups()
        groups = self.env['ems.group'].search([]) if allowed is None else allowed
        for notice in self:
            notice.available_group_ids = groups

    @api.constrains('group_ids', 'notice_line_ids')
    def _check_department_chief_groups(self):
        allowed = self._user_notice_groups()
        if allowed is None:
            return
        for notice in self:
            outside = (notice.group_ids | notice.notice_line_ids.source_group_id) - allowed
            if outside or notice.notice_line_ids.filtered(lambda line: not line.source_group_id):
                raise ValidationError(_(
                    "You can only send notices to the groups your department teaches: %s is not one of them.",
                    ", ".join(outside.mapped('name')) or _("a recipient outside your groups")))
