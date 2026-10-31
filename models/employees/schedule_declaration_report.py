# -*- coding: utf-8 -*-

from odoo import api, models


class ReportScheduleDeclaration(models.AbstractModel):
    """Issue #723: the official schedule declaration (reports/employees/report_schedule_declaration.xml)
    is printed only by those who may (hr.employee._check_can_print_schedule_declaration), whichever
    way it is reached, the report URL included. Once allowed, it reads what it prints as superuser:
    the teacher's groups, levels and NIF, which an administrator outside the hr groups could not read
    otherwise (the administrator is above Direction)."""
    _name = "report.ems.report_schedule_declaration"
    _description = "Schedule declaration report data"

    @api.model
    def _get_report_values(self, docids, data=None):
        self.env['hr.employee']._check_can_print_schedule_declaration()
        return {
            'doc_ids': docids,
            'doc_model': 'hr.employee',
            'docs': self.env['hr.employee'].sudo().browse(docids),
        }
