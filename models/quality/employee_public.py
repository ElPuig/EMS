# -*- coding: utf-8 -*-

from odoo import api, models


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """With 'ems_first_ids' in the context, those people come first in a dropdown and everybody
        else follows: the likely choices are one click away, and anybody can still be picked by
        typing or through "Search more". Used to choose who approves a minute."""
        results = super().name_search(name, args, operator, limit)
        first_ids = self.env.context.get('ems_first_ids')
        if not first_ids:
            return results
        first = super().name_search(name, list(args or []) + [('id', 'in', first_ids)], operator, limit)
        seen = {result[0] for result in first}
        return (first + [result for result in results if result[0] not in seen])[:limit]
