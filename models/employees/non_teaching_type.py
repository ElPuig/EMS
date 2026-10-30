# -*- coding: utf-8 -*-

from odoo import api, fields, models

# Issue #723: the rows of the "Quadre resum d'hores" of the Departament's official schedule
# declaration ("Annexos Dades anuals"), as on the form: its left column, then its right one. Each
# row: (key, code printed, label printed, lective hours apply, fixed hours apply); a cell that
# doesn't apply is grey on the form. The form is always printed in Catalan, so are its labels.
DECLARATION_ROWS = [
    ('eso', 'ESO', 'ESO', True, False),
    ('bat', 'BAT', 'BATXILLERAT', True, False),
    ('cfgb', 'CFGB', 'C. FORM. G. BÀSIC', True, False),
    ('cfgm', 'CFGM', 'C. FORM. G. MITJÀ', True, False),
    ('cfgs', 'CFGS', 'C. FORM. G. SUPERIOR', True, False),
    ('t_eso', 'T-ESO', 'TUTORIA ESO', True, True),
    ('t_bat', 'T-BAT', 'TUTORIA Batxillerat', True, True),
    ('t_fp', 'T-FP', 'TUTORIA FP', True, True),
    ('fct', 'FCT', 'FCT - FP', True, True),
    ('psi', 'PSI', 'Suport tècnic profes. (PSI)', True, True),
    ('siei', 'SIEI', 'Suport inten. Ed inclusiva', True, True),
    ('pfi', 'PFI', 'Prog. de formació i inserció', True, True),
    ('cam', 'CAM', 'Curs accés CFGM', True, False),
    ('cpigs', 'CPIGS', 'Curs preparació inc. CFGS', True, False),
    ('ppas', 'PPAS', 'Preparació proves accés', True, False),
    ('ioc', 'IOC', 'IOC – suport', True, False),
    ('cefp', 'CEFP', 'Curs d’especialització', True, False),
    ('cd', 'CD', 'Càrrec directiu', True, True),
    ('cc', 'CC', 'Càrrec coordinació', True, True),
    ('rd_rc', 'RD/RC', 'Reunions (depart., coord.)', False, True),
    ('g', 'G', 'Guàrdies', False, True),
    ('other', '', 'Altres:', False, True),
]
# The same rows as a selection: their code, or 'Others' for Altres, which has none on the form.
DECLARATION_CODES = [(key, code or 'Others') for key, code, _label, _lective, _fixed in DECLARATION_ROWS]
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
    'G': 'g', 'GB': 'g', 'GWC': 'g', 'TT': 'tutoring', 'ATAL': 'tutoring',
    'AA': 'other', 'S': 'other', 'SC': 'other',
    'BR': False, 'R': False,
}
# The break guard duty's periods (20-25 minutes) are added up before rounding (developer, 2026-10-29).
NON_TEACHING_ADDED_UP_SEED = {'GB'}


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
    adds_up_periods = fields.Boolean(
        string="Add up its periods",
        help="Its periods of the week are added up before rounding up to whole hours in the hours summaries, "
             "instead of each one counting at least one hour (e.g. break guard duties: three of 25 minutes "
             "count 2 hours).")
    declaration_code = fields.Selection(
        selection=DECLARATION_CODES + [('tutoring', 'Tutoring (T-ESO, T-BAT, T-FP or PFI)')],
        string="Schedule declaration code", default='other',
        help="Row of the summary table of the official schedule declaration these hours are added to. "
             "Tutoring goes to the row of the tutored group's level. Empty: not declared (e.g. the break).")
    active = fields.Boolean(string="Active", default=True)

    @api.model
    def _ems_seed_declaration_codes(self):
        """Issue #723: the official code of the centre's non-teaching types, and which add up their
        periods, by their code."""
        for non_teaching in self.with_context(active_test=False).search(
                [('code', 'in', list(NON_TEACHING_DECLARATION_SEED))]):
            non_teaching.write({
                'declaration_code': NON_TEACHING_DECLARATION_SEED[non_teaching.code],
                'adds_up_periods': non_teaching.code in NON_TEACHING_ADDED_UP_SEED,
            })
