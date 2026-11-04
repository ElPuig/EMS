# -*- coding: utf-8 -*-

from odoo import models

# The centre's own documents: printed in the centre language (res.company.ems_lang) whoever prints
# them (issue #746). The public group schedule is not here: it is generated in that language, but
# its Print menu entry follows each user's.
CENTRE_LANG_REPORTS = {
    'ems.report_convalidation_resolution',
    'ems.report_ex_officio_withdrawal',
    'ems.report_minute',
    'ems.report_student_card',
}


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _ems_report_env(self, report_ref):
        if self._get_report(report_ref).report_name in CENTRE_LANG_REPORTS:
            return self.with_env(self.env['res.company']._ems_centre_env())
        return self

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        return super(IrActionsReport, self._ems_report_env(report_ref))._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data)

    def _render_qweb_html(self, report_ref, docids, data=None):
        return super(IrActionsReport, self._ems_report_env(report_ref))._render_qweb_html(
            report_ref, docids, data=data)
