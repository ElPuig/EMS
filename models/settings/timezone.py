# -*- coding: utf-8 -*-

from odoo import api, models


class EmsCompanyTimezoneMixin(models.AbstractModel):
    """Keeps a record's own 'tz' equal to the company's. The whole centre works in the company's
    timezone (see docs/en/developers/shared/timezones.md), but Odoo fills every partner's, employee's
    and calendar's 'tz' from whichever browser created it, so without this a computer with a wrong
    timezone ends up deciding in which hour everything that record reads or receives is shown."""
    _name = 'ems.company_timezone_mixin'
    _description = 'Timezone aligned with the company'

    def _ems_company_tz_vals(self, vals):
        company_tz = self.env.company.sudo().partner_id.tz
        return dict(vals, tz=company_tz) if company_tz else vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._ems_company_tz_vals(vals) for vals in vals_list])

    def write(self, vals):
        if 'tz' in vals and not self.env.context.get('ems_company_tz_change'):
            vals = self._ems_company_tz_vals(vals)
        return super().write(vals)


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'ems.company_timezone_mixin']

    def write(self, vals):
        """The company's own partner is where its timezone is set, so it is the one partner whose
        'tz' can change, and everyone else follows it."""
        if 'tz' not in vals or not (self & self.env['res.company'].sudo().search([]).partner_id):
            return super().write(vals)
        result = super(ResPartner, self.with_context(ems_company_tz_change=True)).write(vals)
        self.env['res.company']._ems_align_timezones()
        return result


class ResourceResource(models.Model):
    _name = 'resource.resource'
    _inherit = ['resource.resource', 'ems.company_timezone_mixin']


class ResourceCalendar(models.Model):
    _name = 'resource.calendar'
    _inherit = ['resource.calendar', 'ems.company_timezone_mixin']


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _ems_align_timezones(self):
        """Sets the company's timezone on every partner (users, the public user the portal and the
        attendance kiosk run as, contacts), employee and working schedule. Called on install, by the
        migration that introduced it, and whenever the company's own timezone changes."""
        company_tz = self.env.company.sudo().partner_id.tz
        if not company_tz:
            return
        for table in ('res_partner', 'resource_resource', 'resource_calendar'):
            self.env.cr.execute(
                f"UPDATE {table} SET tz = %s WHERE tz IS DISTINCT FROM %s", [company_tz, company_tz])
        self.env.invalidate_all()
