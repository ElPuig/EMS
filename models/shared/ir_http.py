# -*- coding: utf-8 -*-

from odoo import models


class IrHttp(models.AbstractModel):
    """Hands the company's timezone to the web client (backend and portal), which shows every
    date/time in it instead of the browser's - see docs/en/developers/shared/timezones.md."""
    _inherit = 'ir.http'

    def session_info(self):
        return dict(super().session_info(), ems_tz=self.env['ems.datetime_utils'].company_tz_name())

    def get_frontend_session_info(self):
        return dict(super().get_frontend_session_info(), ems_tz=self.env['ems.datetime_utils'].company_tz_name())
