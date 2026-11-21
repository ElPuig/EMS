# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import UserError

# Issue #853: the cycles' page (6) of the official form is for these levels (ems.level.declaration_code),
# with the degree it names; every other level uses the general one (page 5).
VOCATIONAL_DEGREES = {'cfgb': 'Bàsic', 'cfgm': 'Mitjà', 'cfgs': 'Superior', 'cefp': "Curs d'especialització"}


class EmsGroupScheduleDeclaration(models.Model):
    """The group pages of the Departament's "Annexos Dades anuals" (issue #853), the counterpart of
    hr.employee's teacher page (#723): printed from the groups' list and the form's Actions dropdown."""
    _inherit = 'ems.group'

    def get_schedule_declaration_data(self):
        """What the group's page adds to the weekly grid: which page of the form it takes, the cycle's
        degree, how many students it has and the course's hours (the distinct modules of its schedule)."""
        self.ensure_one()
        code = self.level_id.declaration_code
        return {
            'page': 'vocational' if code in VOCATIONAL_DEGREES else 'general',
            'degree': VOCATIONAL_DEGREES.get(code, ''),
            'students': self.env['res.partner'].search_count(
                [('main_group_id', '=', self.id), ('contact_type', '=', 'student')]),
            'course_hours': sum(self.schedule_attendance_ids.mapped('subject_id.total_hours')),
        }

    def action_print_schedule_declaration(self):
        """From the form's Actions dropdown (a type="action" button would print the form's whole pager)
        and from the list's own selection. Only the main groups have one: their splits and optatives
        are already in the schedule of their main group (#611)."""
        self.env['ems.base'].check_can_print_schedule_declaration()
        groups = self.filtered(lambda group: group.group_type == 'main')
        if not groups:
            raise UserError(_("Only the main groups have a schedule declaration."))
        return self.env.ref('ems.action_report_group_schedule_declaration').report_action(groups)


class ReportGroupScheduleDeclaration(models.AbstractModel):
    """Prints only to those who may, whichever way it is reached, the report URL included, and then reads
    as superuser what it prints (an administrator outside the hr groups is above Direction)."""
    _name = "report.ems.report_group_schedule_declaration"
    _description = "Group schedule declaration report data"

    @api.model
    def _get_report_values(self, docids, data=None):
        self.env['ems.base'].check_can_print_schedule_declaration()
        groups = self.env['ems.group'].sudo().browse(docids).filtered(lambda group: group.group_type == 'main')
        if not groups:
            raise UserError(_("Only the main groups have a schedule declaration."))
        return {'doc_ids': groups.ids, 'doc_model': 'ems.group', 'docs': groups}
