# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

WALKOUT_FIELDS = ('walkout_allowed', 'walkout_course_from', 'walkout_course_to')


class EmsWalkoutLevelsWizard(models.TransientModel):
    """Issue #800: Settings > Student Walkout Settings > Levels and courses. Whoever enters Settings
    sets which levels (and courses) may call a student walkout, like the convalidation levels: only
    these three fields of ems.level, written with sudo, without granting write access to the levels."""
    _name = 'ems.walkout.levels.wizard'
    _description = "Levels and courses that may propose supporting a student walkout"

    line_ids = fields.One2many(string="Levels", comodel_name='ems.walkout.levels.wizard.line',
                               inverse_name='wizard_id', default=lambda self: self._default_line_ids())

    @api.model
    def _default_line_ids(self):
        return [(0, 0, {'level_id': level.id, **{name: level[name] for name in WALKOUT_FIELDS}})
                for level in self.env['ems.level'].sudo().search([])]

    def action_save(self):
        self.ensure_one()
        if not self.env['ems.base'].get_user_is_top_admin():
            raise AccessError(_("Only an administrator can change which levels may propose supporting a student walkout."))
        for line in self.line_ids:
            vals = {name: line[name] for name in WALKOUT_FIELDS}
            level = line.level_id.sudo()
            if any(level[name] != value for name, value in vals.items()):
                level.write(vals)
        return {'type': 'ir.actions.act_window_close'}


class EmsWalkoutLevelsWizardLine(models.TransientModel):
    _name = 'ems.walkout.levels.wizard.line'
    _description = "Level that may propose supporting a student walkout"
    _order = 'level_acronym'

    wizard_id = fields.Many2one(comodel_name='ems.walkout.levels.wizard', required=True, ondelete='cascade')
    level_id = fields.Many2one(string="Level", comodel_name='ems.level', required=True, readonly=True,
                               ondelete='cascade')
    level_acronym = fields.Char(related='level_id.acronym', string="Acronym")
    walkout_allowed = fields.Boolean(string="May propose supporting a student walkout")
    walkout_course_from = fields.Integer(string="From course")
    walkout_course_to = fields.Integer(string="To course")
