# -*- coding: utf-8 -*-

from odoo import models


class EmsScheduleReportMixin(models.AbstractModel):
    _name = 'ems.schedule_report_mixin'
    _description = "Shared coloring/time-formatting helpers for weekly schedule PDF reports."

    # NOTE: assigned in first-seen order to the distinct items on a schedule, so two unrelated
    # items only ever share a color once the palette itself runs out.
    REPORT_COLOR_PALETTE = [
        '#5b8def', '#f4a261', '#2a9d8f', '#e76f51', '#8ecae6', '#ffb703',
        '#c77dff', '#06d6a0', '#ef476f', '#118ab2', '#bc6c25', '#9d4edd',
    ]

    def _report_color_key(self, attendance):
        return ('non_teaching', attendance.non_teaching.id) if attendance.non_teaching else ('subject', attendance.subject_id.id)

    def _format_report_time(self, value):
        hour, minutes = divmod(round(value * 60), 60)
        return f"{hour:02d}:{minutes:02d}"
