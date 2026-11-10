# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import models

from .student_walkout import JOIN_DAYS_BEFORE, VISIBLE_STATES, VOTE_DAYS_BEFORE


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _ems_walkout_portal_student(self):
        """This partner when it is a student with portal access: only they open and vote student
        walkout calls, never a family acting for its child."""
        self.ensure_one()
        partner = self.sudo()
        return partner.contact_type == 'student' and bool(partner.user_ids.filtered('share'))

    def _ems_walkout_opener_group(self):
        """The main group this student may open a student walkout call for: their own, when they
        are its delegate or sub-delegate and it may call one."""
        self.ensure_one()
        group = self.sudo().main_group_id
        if not (self._ems_walkout_portal_student() and group and self in (group.delegate_id | group.subdelegate_id)
                and group._ems_walkout_allowed()):
            return self.env['ems.group']
        return group

    def _ems_walkout_calls(self):
        """The calls this student sees, newest first."""
        self.ensure_one()
        # The group sees a call once the Head of Studies accepts it (and why, if rejected after
        # that); its delegate, from the start.
        return self.env['ems.student_walkout'].sudo().search([
            '|', ('opener_id', '=', self.id),
            '&', ('line_ids.student_id', '=', self.id),
            '|', ('state', 'in', VISIBLE_STATES),
            '&', ('state', '=', 'rejected'), ('rejected_from_state', '!=', 'pending')])

    def _ems_walkout_portal_visible(self):
        """The portal's Student walkouts card and menu entry: a student with portal access who may
        open a call or is in one."""
        self.ensure_one()
        return self._ems_walkout_portal_student() and bool(self._ems_walkout_opener_group()
                                                           or self._ems_walkout_calls())

    def _ems_walkout_pending_votes(self):
        """The calls waiting for this student: the group vote not cast, or whether they join not said
        yet, for the portal home's banner."""
        self.ensure_one()
        if not self._ems_walkout_portal_student():
            return self.env['ems.student_walkout']
        Walkout = self.env['ems.student_walkout'].sudo()
        today = Walkout.get_local_today()
        mine = [('student_id', '=', self.id), ('has_portal', '=', True)]
        return Walkout.search([
            '|',
            '&', '&', ('state', '=', 'voting'), ('walkout_date', '>=', today + timedelta(days=VOTE_DAYS_BEFORE)),
            ('line_ids', 'any', mine + [('voted', '=', False)]),
            '&', '&', ('state', '=', 'joining'), ('walkout_date', '>=', today + timedelta(days=JOIN_DAYS_BEFORE)),
            ('line_ids', 'any', mine + [('join_answered', '=', False)]),
        ])
