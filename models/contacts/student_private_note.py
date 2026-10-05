# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsStudentPrivateNote(models.Model):
    """The private notes (tutoring) of a student, issue #511.

    Kept out of res.partner on purpose: every teacher reads every student
    (rule_contact_teacher), so a plain partner field would be readable by all of them. Only the
    academic admin has access rights on this model; everyone else reaches it exclusively through
    res.partner.private_notes, which checks res.partner._ems_can_access_private_notes() per
    student before reading or writing it as superuser."""
    _name = 'ems.student.private_note'
    _description = 'Student private notes'
    _rec_name = 'partner_id'
    _sql_constraints = [
        ('partner_unique', 'UNIQUE(partner_id)', "A student can only have one private notes record."),
    ]

    partner_id = fields.Many2one(string='Student', comodel_name='res.partner', required=True, ondelete='cascade', index=True)
    notes = fields.Html(string='Private notes (tutoring)')
