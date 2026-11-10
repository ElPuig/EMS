# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .mobility import OPEN_STATES


class ResPartner(models.Model):
    """Issue #683 - which Erasmus+ calls a student sees on the portal; issue #686, which staff
    calls a staff member sees; issue #697, the host entities of the mobilities."""
    _inherit = 'res.partner'

    is_erasmus_host = fields.Boolean(
        string="Erasmus+ host entity",
        help="A company, school or course provider that hosts Erasmus+ participants. Its contacts are the tutors "
             "at destination.")
    erasmus_oid = fields.Char(string="OID", help="The Erasmus+ organisation ID of the host entity (e.g. E10150031).")
    erasmus_history_ids = fields.One2many(string="Erasmus+ participations", comodel_name='ems.erasmus.history',
                                          inverse_name='partner_id', readonly=True)
    # Issue #777 (13.3): the contact form hides its details block (address, website, OID...) from
    # whoever is not admin, Secretary, Head of Studies or the contact's tutor (read_only_user),
    # meant for the students' data; the Erasmus team needs it on host entities and their tutors.
    can_edit_erasmus_host = fields.Boolean(string="Can edit the host entity",
                                           compute='_compute_can_edit_erasmus_host')
    # Issue #782 (13.4): how much a host entity has been used, on its list.
    erasmus_mobility_count = fields.Integer(string="Mobilities", compute='_compute_erasmus_mobility_count',
                                            help="Individual and group mobilities hosted, cancelled ones aside.")

    @api.depends('is_erasmus_host', 'parent_id.is_erasmus_host')
    @api.depends_context('uid')
    def _compute_can_edit_erasmus_host(self):
        is_team = self.env.user.has_group('ems.group_erasmus')
        for partner in self:
            partner.can_edit_erasmus_host = is_team and (partner.is_erasmus_host or partner.parent_id.is_erasmus_host)

    def _compute_erasmus_mobility_count(self):
        """One grouped count per model for the whole list, never a search per row."""
        counts = dict.fromkeys(self.ids, 0)
        for model in ('ems.erasmus.mobility', 'ems.erasmus.group.mobility'):
            for host, count in self.env[model].sudo()._read_group(
                    [('host_partner_id', 'in', self.ids), ('state', '!=', 'cancelled')], ['host_partner_id'],
                    ['__count']):
                counts[host.id] += count
        for partner in self:
            partner.erasmus_mobility_count = counts.get(partner.id, 0)

    def _ems_erasmus_email(self):
        """The address every Erasmus+ email to this person goes to: a student's school address
        (student_email, the one they read every day and sign in to the portal with; never the
        personal one, adriamt 2026-11-09, issue #802), anybody else's own email (staff, families,
        host contacts). Empty: they get no email."""
        self.ensure_one()
        return self.student_email if self.contact_type == 'student' else self.email

    def _ems_erasmus_calls(self):
        """Published calls this person can apply to, open or not yet: the students' calls with a
        modality for their level, or the staff calls of an internal user whose employee file
        meets art. 6 (`_ems_staff_can_apply`: FP's teachers and Direction)."""
        self.ensure_one()
        Call = self.env['ems.erasmus.call'].sudo()
        calls = Call
        level = self.contact_type == 'student' and self.main_group_id.level_id
        if level:
            calls |= Call.search([('state', '=', 'published'), ('audience', '=', 'student'),
                                  ('modality_ids.level_ids', 'in', level.ids)])
        employee = self._ems_erasmus_employee()
        if employee:
            calls |= Call.search([('state', '=', 'published'), ('audience', '=', 'staff')]).filtered(
                lambda call: call._ems_staff_can_apply(employee))
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
        if self.sudo().user_ids.filtered(lambda user: not user.share):
            # Staff work in the backend, never on the portal (the 2026-11-04 review).
            return False
        return bool(self._ems_erasmus_calls() or self._ems_erasmus_applications()
                    or self._ems_erasmus_guardian_mobilities() or self._ems_erasmus_guardian_applications())

    def _ems_erasmus_guardian_applications(self):
        """The 2026-11-04 usage test: the applications of the minors this family acts for, which it
        follows from the start (it saw nothing until the commitment letter)."""
        self.ensure_one()
        Application = self.env['ems.erasmus.application'].sudo()
        if self.contact_type != 'family':
            return Application
        students = self.get_portal_students().filtered(self._ems_portal_can_act_for).filtered(
            lambda student: not student.is_adult)
        return Application.search([('partner_id', 'in', students.ids), ('audience', '=', 'student')])

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
