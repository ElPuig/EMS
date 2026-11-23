# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import UserError

from ..employees.non_teaching_type import GENERAL_LEVELS, VOCATIONAL_DEGREES

class EmsGroupScheduleDeclaration(models.Model):
    """The group pages of the Departament's "Annexos Dades anuals" (issue #853), the counterpart of
    hr.employee's teacher page (#723): printed from the groups' list and the form's Actions dropdown."""
    _inherit = 'ems.group'

    def get_schedule_declaration_data(self):
        """What the group's page adds to the weekly grid: which page of the form it takes, the cycle's
        degree (page 6) or the level's name (page 5), how many students it has and its study's
        duration in hours."""
        self.ensure_one()
        code = self.level_id.declaration_code
        return {
            'page': 'vocational' if code in VOCATIONAL_DEGREES else 'general',
            'degree': VOCATIONAL_DEGREES.get(code, ''),
            'level': GENERAL_LEVELS.get(code) or self.level_id.name or '',
            'students': self.env['res.partner'].search_count(
                [('main_group_id', '=', self.id), ('contact_type', '=', 'student')]),
            'course_hours': self.study_id.duration_hours,
        }

    def action_print_schedule_declaration(self):
        """From the form's Actions dropdown (a type="action" button would print the form's whole pager)
        and from the list's own selection. Only the main groups have one: their splits and optatives
        are already in the schedule of their main group (#611)."""
        self.env['ems.base'].check_can_print_schedule_declaration()
        return self.env.ref('ems.action_report_group_schedule_declaration').report_action(
            self._schedule_declaration_groups())

    def _schedule_declaration_groups(self):
        """The main groups of these, the only ones with a declaration; none at all is an error. Shared by
        the button and the report model (the report URL skips the button)."""
        groups = self.filtered(lambda group: group.group_type == 'main')
        if not groups:
            raise UserError(_("Only the main groups have a schedule declaration."))
        return groups


class ReportGroupScheduleDeclaration(models.AbstractModel):
    """Prints only to those who may, whichever way it is reached, the report URL included, and then reads
    as superuser what it prints (an administrator outside the hr groups is above Direction)."""
    _name = "report.ems.report_group_schedule_declaration"
    _description = "Group schedule declaration report data"

    @api.model
    def _get_report_values(self, docids, data=None):
        self.env['ems.base'].check_can_print_schedule_declaration()
        groups = self.env['ems.group'].sudo().browse(docids)._schedule_declaration_groups()
        return {'doc_ids': groups.ids, 'doc_model': 'ems.group', 'docs': groups}
