# -*- coding: utf-8 -*-

from odoo import fields, models

from .convalidation import CONVALIDATED_GRADE, GRADE_TYPE_HELP, GRADE_TYPES


class EmsConvalidationGrantWizard(models.TransientModel):
    _name = 'ems.convalidation.grant_wizard'
    _description = "The Head of Studies convalidates a subject of a request, with its grade or without one."

    line_id = fields.Many2one(string="Subject", comodel_name='ems.convalidation.line', required=True,
                              ondelete='cascade')
    grade = fields.Integer(string="Grade", default=CONVALIDATED_GRADE,
                           help="The grade the previous studies hold, from 5 to 10.")
    mode = fields.Selection(string="Mode", required=True, default='grade', selection=GRADE_TYPES,
                            help=GRADE_TYPE_HELP)

    def action_grant(self):
        """A grade out of range is refused by the line itself, leaving the dialog open."""
        self.ensure_one()
        vals = {'state': 'granted', 'grade_type': self.mode}
        if self.mode != 'without_grade':
            vals['grade'] = self.grade if self.mode == 'grade' else CONVALIDATED_GRADE
        self.line_id.write(vals)
        return {'type': 'ir.actions.act_window_close'}
