# -*- coding: utf-8 -*-

from odoo import api, fields, models

# Issue #723: the rows of the "Quadre resum d'hores" of the Departament's official schedule
# declaration ("Annexos Dades anuals"), as (key, code printed on the form).
DECLARATION_CODES = [
    ('eso', 'ESO'), ('bat', 'BAT'), ('cfgb', 'CFGB'), ('cfgm', 'CFGM'), ('cfgs', 'CFGS'),
    ('t_eso', 'T-ESO'), ('t_bat', 'T-BAT'), ('t_fp', 'T-FP'), ('fct', 'FCT'), ('psi', 'PSI'),
    ('siei', 'SIEI'), ('pfi', 'PFI'), ('cam', 'CAM'), ('cpigs', 'CPIGS'), ('ppas', 'PPAS'),
    ('ioc', 'IOC'), ('cefp', 'CEFP'), ('cd', 'CD'), ('cc', 'CC'), ('rd_rc', 'RD/RC'), ('g', 'G'),
    ('other', 'Others'),
]
# The rows a level's teaching hours can go to.
LEVEL_DECLARATION_CODES = [
    code for code in DECLARATION_CODES
    if code[0] in ('eso', 'bat', 'cfgb', 'cfgm', 'cfgs', 'pfi', 'cam', 'cpigs', 'ppas', 'ioc', 'cefp', 'siei')
]
# Tutoring is declared on the row of the tutored group's level (developer, 2026-10-29).
TUTORING_CODE_BY_LEVEL_CODE = {'eso': 't_eso', 'bat': 't_bat', 'pfi': 'pfi'}
TUTORING_DEFAULT_CODE = 't_fp'

# Seeded once (post_init_hook and migrations/18.0.0.43.0), then configured by the centre.
# False: not declared at all (the break, a reduction of working hours).
NON_TEACHING_DECLARATION_SEED = {
    'MT': 'cd', 'CT': 'cc', 'AC': 'cc', 'WIC': 'cc', 'CM': 'rd_rc', 'MM': 'rd_rc',
    'G': 'g', 'GB': 'g', 'GWC': 'g', 'TT': 'tutoring',
    'AA': 'other', 'ATAL': 'other', 'S': 'other', 'SC': 'other',
    'BR': False, 'R': False,
}


class EmsNonTeachingType(models.Model):
    _name = "ems.non_teaching_type"
    _description = "Non-teaching activity type: a working schedule period that isn't a subject (guard duty, break, coordination meeting...)."
    _order = "name"
    _sql_constraints = [
        ('unique_code', 'unique(code)', 'The code must be unique.'),
    ]

    code = fields.Char(string="Code", required=True)
    name = fields.Char(string="Name", translate=True, required=True)
    is_break = fields.Boolean(string="Is a break", help="Dropped from both hours-summary columns on the working schedule (e.g. lunch/patio break).")
    is_fixed = fields.Boolean(string="Fixed schedule", help="Counted in the 'Other fixed-schedule hours' column every day (e.g. guard duties).")
    is_guard = fields.Boolean(string="Is guard duty", help="Counted as guard duty on the guard duty schedule board (Employee Attendances > Guard duty schedule).")
    is_regular_guard = fields.Boolean(
        string="Regular guard",
        help="A teacher on this guard duty can be sent to cover a class, or a guard duty that is not regular "
             "(WC, break...), left without its teacher. A guard duty that is not regular has to be covered "
             "itself when its teacher is away.")
    declaration_code = fields.Selection(
        selection=DECLARATION_CODES + [('tutoring', 'Tutoring (T-ESO, T-BAT, T-FP or PFI)')],
        string="Schedule declaration code", default='other',
        help="Row of the summary table of the official schedule declaration these hours are added to. "
             "Tutoring goes to the row of the tutored group's level. Empty: not declared (e.g. the break).")
    active = fields.Boolean(string="Active", default=True)

    @api.model
    def _ems_seed_declaration_codes(self):
        """Issue #723: the official code of the centre's non-teaching types, by their code."""
        for non_teaching in self.with_context(active_test=False).search(
                [('code', 'in', list(NON_TEACHING_DECLARATION_SEED))]):
            non_teaching.declaration_code = NON_TEACHING_DECLARATION_SEED[non_teaching.code]
