# -*- coding: utf-8 -*-

from odoo import fields, models

from .mobility import OPEN_STATES


class ResPartner(models.Model):
    """Issue #683 - which Erasmus+ calls a student sees on the portal; issue #686, which staff
    calls a staff member sees; issue #697, the host entities of the mobilities."""
    _inherit = 'res.partner'

    is_erasmus_host = fields.Boolean(
        string="Erasmus+ host entity",
        help="A company, school or course provider that hosts Erasmus+ participants. Its contacts are the tutors "
             "at destination.")

    def _ems_erasmus_calls(self):
        """Published calls this person can apply to, open or not yet: the students' calls with a
        modality for their level, or the staff calls for an internal user with an employee file."""
        self.ensure_one()
        Call = self.env['ems.erasmus.call'].sudo()
        calls = Call
        level = self.contact_type == 'student' and self.main_group_id.level_id
        if level:
            calls |= Call.search([('state', '=', 'published'), ('audience', '=', 'student'),
                                  ('modality_ids.level_ids', 'in', level.ids)])
        if self._ems_erasmus_employee():
            calls |= Call.search([('state', '=', 'published'), ('audience', '=', 'staff')])
        return calls

    def _ems_erasmus_employee(self):
        """The employee file of this partner's internal user, if any (staff calls)."""
        self.ensure_one()
        users = self.sudo().user_ids.filtered(lambda user: not user.share)
        return users.employee_ids[:1]

    def _ems_erasmus_applications(self):
        self.ensure_one()
        return self.env['ems.erasmus.application'].sudo().search([('partner_id', '=', self.id)])

    def _ems_erasmus_portal_visible(self):
        """The portal's Erasmus+ card: for whoever can apply to a published call or already applied
        to one, and for the family of a minor going on a mobility, which signs its commitment letter."""
        self.ensure_one()
        return bool(self._ems_erasmus_calls() or self._ems_erasmus_applications()
                    or self._ems_erasmus_guardian_mobilities())

    def _ems_erasmus_guardian_mobilities(self):
        """Issue #687: the mobilities in preparation of the minors this family acts for, whose
        commitment letter it signs too (pending or already signed)."""
        self.ensure_one()
        Mobility = self.env['ems.erasmus.mobility'].sudo()
        if self.contact_type != 'family':
            return Mobility
        students = self.get_portal_students().filtered(self._ems_portal_can_act_for)
        return Mobility.search([('partner_id', 'in', students.ids), ('state', '=', 'preparing')]).filtered(
            lambda mobility: mobility.commitment_guardian_pending or mobility.commitment_guardian_signed_date)

    def _ems_erasmus_open_mobility(self):
        """Issue #687: an Erasmus+ mobility of this person not closed nor cancelled yet."""
        return bool(self.env['ems.erasmus.mobility'].sudo().search_count(
            [('partner_id', 'in', self.ids), ('state', 'in', OPEN_STATES)]))

    def _ems_erasmus_release_graduate(self):
        """Issue #687: a graduate the course transition kept on the portal for their mobility is
        retired, as the transition would have done, once no mobility of theirs is open."""
        for partner in self.sudo():
            if partner.active and partner.contact_type == 'alumni' and not partner._ems_erasmus_open_mobility():
                partner._ems_retire_graduate()
