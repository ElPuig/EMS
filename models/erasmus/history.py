# -*- coding: utf-8 -*-

from odoo import fields, models, tools

from .call import PROJECTS


class EmsErasmusHistory(models.Model):
    """A person's Erasmus+ participations as EMS has them (the issue-#682 review): one line per
    individual mobility (ems.erasmus.mobility) and one per group mobility they take part in
    (ems.erasmus.group.participant), cancelled and withdrawn ones left out. A read-only SQL view,
    shown under the academic history on the student form so every teacher knows, without access
    to the Erasmus+ app; and on the application, for the Erasmus team checking "First mobility".
    It holds names and dates only: the scores, documents and money stay in the Erasmus+ app."""
    _name = 'ems.erasmus.history'
    _description = 'Erasmus+ participation'
    _auto = False
    _order = 'date_start desc, id desc'

    partner_id = fields.Many2one(string="Participant", comodel_name='res.partner', readonly=True)
    kind = fields.Selection(string="Kind", readonly=True, selection=[
        ('individual', "Individual mobility"), ('group', "Group mobility")])
    role = fields.Selection(string="Role", readonly=True, selection=[
        ('student', "Student"), ('staff', "Staff"), ('leader', "Leader teacher"),
        ('companion', "Accompanying teacher")])
    # The call or the group mobility, as text: whoever reads it may have no access to either.
    name = fields.Char(string="Call or group mobility", readonly=True)
    project = fields.Selection(string="Project", selection=PROJECTS, readonly=True)
    country_id = fields.Many2one(string="Country", comodel_name='res.country', readonly=True)
    city = fields.Char(string="City", readonly=True)
    date_start = fields.Date(string="Start", readonly=True)
    date_end = fields.Date(string="End", readonly=True)
    state = fields.Selection(string="State", readonly=True, selection=[
        ('planned', "Planned"), ('done', "Completed")])

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # Even ids for the individual mobilities, odd for the group participants: unique across both.
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT mobility.id * 2 AS id,
                       mobility.partner_id,
                       'individual' AS kind,
                       mobility.audience AS role,
                       call.name,
                       modality.project,
                       mobility.country_id,
                       mobility.city,
                       mobility.date_start,
                       mobility.date_end,
                       CASE WHEN mobility.state = 'done' THEN 'done' ELSE 'planned' END AS state
                  FROM ems_erasmus_mobility mobility
                  JOIN ems_erasmus_call call ON call.id = mobility.call_id
                  LEFT JOIN ems_erasmus_call_modality modality ON modality.id = mobility.modality_id
                 WHERE mobility.state != 'cancelled'
                UNION ALL
                SELECT participant.id * 2 + 1,
                       participant.partner_id,
                       'group',
                       participant.role,
                       grp.name,
                       project.kind,
                       grp.country_id,
                       grp.city,
                       grp.date_start,
                       grp.date_end,
                       CASE WHEN grp.state = 'done' THEN 'done' ELSE 'planned' END
                  FROM ems_erasmus_group_participant participant
                  JOIN ems_erasmus_group_mobility grp ON grp.id = participant.group_mobility_id
                  LEFT JOIN ems_erasmus_project project ON project.id = grp.project_id
                 WHERE participant.state = 'active' AND grp.state != 'cancelled'
            )
        """)
