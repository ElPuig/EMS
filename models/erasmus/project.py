# -*- coding: utf-8 -*-

from odoo import fields, models

from .call import PROJECTS


class EmsErasmusProject(models.Model):
    """Issue #687 - an Erasmus+ project the centre runs (its grant agreement), to which the Erasmus
    coordination assigns each mobility: CFGM on a KA121-VET project, CFGS on a KA131-HED one.
    Several of each kind can be active at once (one per call year)."""
    _name = 'ems.erasmus.project'
    _description = 'Erasmus+ project'
    _order = 'active desc, kind, name desc'

    name = fields.Char(string="Agreement number", required=True, help="e.g. 2026-1-ES01-KA121-VET-000123456")
    kind = fields.Selection(string="Kind", selection=PROJECTS, required=True)
    date_start = fields.Date(string="Start")
    date_end = fields.Date(string="End")
    active = fields.Boolean(string="Active", default=True)
    mobility_ids = fields.One2many(string="Mobilities", comodel_name='ems.erasmus.mobility', inverse_name='project_id')
