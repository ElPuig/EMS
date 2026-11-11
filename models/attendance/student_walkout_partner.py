# -*- coding: utf-8 -*-

from odoo import fields, models

from .student_walkout import VISIBLE_STATES


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

    def _ems_walkout_opener_groups(self):
        """The groups that call a walkout together with this delegate's: their main group and the
        halves of a split group that share them as delegate or sub-delegate."""
        self.ensure_one()
        group = self._ems_walkout_opener_group()
        return group | group.joinable_group_ids.filtered(lambda half: self in (half.delegate_id | half.subdelegate_id))

    def _ems_walkout_calls(self):
        """The calls this student sees, newest first."""
        self.ensure_one()
        # A call its delegate cancelled stays theirs alone.
        return self.env['ems.student_walkout'].sudo().search([
            '|', ('opener_id', '=', self.id),
            '&', ('line_ids.student_id', '=', self.id), ('state', 'in', VISIBLE_STATES)])

    def _ems_walkout_portal_visible(self):
        """The portal's Student walkouts card and menu entry: a student with portal access who may
        open a call or is in one, or a family asked to ratify that its child joins one."""
        self.ensure_one()
        if self._ems_walkout_portal_family():
            return bool(self._ems_walkout_family_lines())
        return self._ems_walkout_portal_student() and bool(self._ems_walkout_opener_group()
                                                           or self._ems_walkout_calls())

    def _ems_walkout_portal_family(self):
        """This partner when it is a family with portal access: it ratifies that its minor children
        join a walkout (Decret 102/2010, art. 24.2)."""
        self.ensure_one()
        partner = self.sudo()
        return partner.contact_type == 'family' and bool(partner.user_ids.filtered('share'))

    def _ems_walkout_family_lines(self, pending=False):
        """The lines of this family's children it was asked to ratify, newest first; `pending`, only
        the ones still waiting for its answer while joining lasts."""
        self.ensure_one()
        children = self.sudo().get_portal_students().filtered(lambda child: self in child._ems_family_contacts())
        domain = [('student_id', 'in', children.ids), ('needs_ratification', '=', True), ('joins', '=', True),
                  ('walkout_id.state', '!=', 'cancelled')]
        if pending:
            domain += [('ratification', '=', 'pending'), ('walkout_id.state', '=', 'joining'),
                       ('walkout_id.join_until', '>', fields.Datetime.now())]
        return self.env['ems.student_walkout.line'].sudo().search(domain, order='id desc')

    def _ems_walkout_pending_votes(self):
        """The calls waiting for this student: the group vote not cast, or whether they join not said
        yet, for the portal home's banner."""
        self.ensure_one()
        if not self._ems_walkout_portal_student():
            return self.env['ems.student_walkout']
        now = fields.Datetime.now()
        mine = [('student_id', '=', self.id), ('has_portal', '=', True)]
        return self.env['ems.student_walkout'].sudo().search([
            '|',
            '&', '&', ('state', '=', 'voting'), ('vote_until', '>', now),
            ('line_ids', 'any', mine + [('voted', '=', False)]),
            '&', '&', ('state', '=', 'joining'), ('join_until', '>', now),
            ('line_ids', 'any', mine + [('join_answered', '=', False)]),
        ])
