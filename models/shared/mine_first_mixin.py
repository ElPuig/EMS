# -*- coding: utf-8 -*-

from odoo import api, models


class EmsMineFirstMixin(models.AbstractModel):
    _name = 'ems.mine_first_mixin'
    _description = "Dropdowns that offer the user's own records first."

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """The user's own records (_ems_first_ids) come first in a dropdown, then the ones near
        them (_ems_near_ids), and everything else follows: the likely choices are one click away,
        and anything can still be picked by typing or through "Search more"."""
        results = self._ems_name_search(name, args, operator, limit)
        first_ids = self._ems_first_ids()
        if not first_ids:
            return results
        ordered, seen = [], set()
        for ids in (first_ids, self._ems_near_ids(first_ids)):
            if not ids:
                continue
            for result in self._ems_name_search(name, list(args or []) + [('id', 'in', ids)], operator, limit):
                if result[0] not in seen:
                    ordered.append(result)
                    seen.add(result[0])
        return (ordered + [result for result in results if result[0] not in seen])[:limit]

    @api.model
    def _ems_name_search(self, name, args, operator, limit):
        """The plain search, in the order the rest is offered. Override to sort it otherwise."""
        return super().name_search(name, args, operator, limit)

    @api.model
    def _ems_first_ids(self):
        """Ids of the records offered first: the ones passed as 'ems_first_ids' in the context (a
        view that knows the likely choices), else the current user's own. Override the latter."""
        return list(self.env.context.get('ems_first_ids') or []) or self._ems_my_ids()

    @api.model
    def _ems_my_ids(self):
        return []

    @api.model
    def _ems_near_ids(self, first_ids):
        """Ids of the records offered right after the first ones (e.g. the same area's)."""
        return []
