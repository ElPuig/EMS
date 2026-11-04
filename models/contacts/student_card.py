# -*- coding: utf-8 -*-

import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..curriculum.level import CARD_PALETTE, DEFAULT_CARD_COLOR


class ResPartner(models.Model):
    """The student card PDF (issue #524). See docs/en/developers/contacts/student_card.md."""
    _inherit = 'res.partner'

    # The code in the QR on the back of the card, which opens its public check page (/ems/card/<code>).
    # One per student, kept for the whole academic year so a reprinted card keeps working; a new one
    # when the course changes (the old card expires) or when the card is revoked (lost, stolen).
    # Only ever read and written through sudo(): a code is as good as the card in hand.
    ems_card_token = fields.Char(string="Student card code", copy=False, groups='base.group_system')
    ems_card_course_id = fields.Many2one(
        'ems.course', string="Student card course", copy=False, groups='base.group_system')

    _sql_constraints = [
        ('ems_card_token_unique', 'unique (ems_card_token)', "Another student card already uses this code."),
    ]

    # Whoever may act on the student (ems.student.scope.mixin, issue #483) may print their card.
    can_print_student_card = fields.Boolean(string="Can print student card", compute='_compute_can_print_student_card')
    # What the card tells the teacher at the door. Not stored: is_adult depends on today's date.
    can_leave_centre = fields.Boolean(
        string="May leave the centre", compute='_compute_can_leave_centre',
        help="The student is of age, or the family accepted the 'Leave the Centre' authorization "
             "for the academic year in force.")

    @api.depends('birth_date', 'auth_leave')
    def _compute_can_leave_centre(self):
        for partner in self:
            partner.can_leave_centre = partner.is_adult or partner.auth_leave

    @api.depends('contact_type', 'tutor_id')
    @api.depends_context('uid')
    def _compute_can_print_student_card(self):
        printable = self._student_card_printable()
        for partner in self:
            partner.can_print_student_card = partner in printable

    def _student_card_printable(self):
        """The students of self the current user may print a card for, sorted by name."""
        scope = self.env['ems.student.scope.mixin']
        return self.filtered(
            lambda partner: partner.contact_type == 'student' and scope._scope_acts_on_student(partner)
        ).sorted('name')

    def action_print_student_card(self):
        students = self._student_card_printable()
        if not students:
            raise UserError(_("None of the selected contacts is a student you can print a card for."))
        # Here and not while rendering: the report is downloaded on a read-only cursor.
        students.sudo()._ems_ensure_card_token()
        # config=False: the card has its own layout, so never the document layout configurator.
        return self.env.ref('ems.action_report_student_card').report_action(students, config=False)

    def action_revoke_student_card(self):
        """A lost or stolen card: a new code, so the QR of every card printed so far shows "not
        valid". The next card printed carries the new one."""
        students = self._student_card_printable()
        if not students:
            raise UserError(_("None of the selected contacts is a student you can revoke the card of."))
        students.sudo()._ems_ensure_card_token(renew=True)
        # A note on the record, so whoever looks later knows why an old card fails.
        for student in students:
            student._message_log(body=_("Student card revoked: the cards printed until now are no longer valid."))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Student card revoked. Print a new card for the student."),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _ems_card_current_course(self):
        return self.env.company.current_course_id

    def _ems_ensure_card_token(self, renew=False):
        """Gives every student of self (sudo) a code for the academic year in force, keeping the one
        they have unless it belongs to another year or `renew` asks for a new one."""
        course = self._ems_card_current_course()
        for student in self:
            if renew or not student.ems_card_token or student.ems_card_course_id != course:
                student.write({'ems_card_token': secrets.token_urlsafe(24), 'ems_card_course_id': course.id})

    def _ems_card_check_url(self):
        """The address the QR holds, or False when the student has no valid code (sudo)."""
        self.ensure_one()
        if not self.ems_card_token or self.ems_card_course_id != self._ems_card_current_course():
            return False
        return f"{self.get_base_url()}/ems/card/{self.ems_card_token}"

    @api.model
    def _ems_card_from_token(self, token):
        """The student a card's code belongs to, as long as the card is still valid: the student's
        current code, issued for the academic year in force, and still a student (a withdrawal,
        graduation or expulsion voids it). An empty recordset otherwise."""
        students = self.sudo().browse()
        if token:
            students = self.sudo().search([('ems_card_token', '=', token)], limit=1)
        return students.filtered(lambda student: student.contact_type == 'student'
                                 and student.ems_card_course_id == self._ems_card_current_course())

    def _ems_card_check_values(self):
        """What the public check page shows: the least needed to compare it with the card in hand -
        the band (level, study, course), the initials, the IDALU's last four digits and whether the
        student may leave the centre. Never the name, the photo or the reason they may leave."""
        self.ensure_one()
        card = self._get_student_card_values()
        names = ' '.join(filter(None, (self.firstname, self.lastname))) or self.name or ''
        idalu = self.student_id or ''
        return {
            **card,
            'initials': ' '.join(f"{word[0].upper()}." for word in names.split()),
            'idalu': '*' * max(len(idalu) - 4, 0) + idalu[-4:],
            'can_leave': self.can_leave_centre,
        }

    def _get_student_card_values(self):
        """What the card template shows besides the plain fields."""
        self.ensure_one()
        group = self.main_group_id
        level = group.level_id or group.study_id.level_id
        return {
            'document': self.document_id or self.passport_id,
            'level': level,
            # A student without a main group still gets a band, in the colour of a level without one.
            'color': CARD_PALETTE[level.card_color or DEFAULT_CARD_COLOR],
            # The study's acronym (SMX, not its full name), so the block never takes two lines; left out
            # when it only repeats the level's (ESO, BTX).
            'study': group.study_id.acronym if group.study_id.acronym != level.acronym else '',
            'course': group.course,
        }


class EmsGroup(models.Model):
    _inherit = 'ems.group'

    can_print_student_cards = fields.Boolean(string="Can print student cards", compute='_compute_can_print_student_cards')

    @api.depends('main_student_ids')
    @api.depends_context('uid')
    def _compute_can_print_student_cards(self):
        for group in self:
            group.can_print_student_cards = bool(group.main_student_ids._student_card_printable())

    def action_print_student_cards(self):
        self.ensure_one()
        return self.main_student_ids.action_print_student_card()


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _ems_student_card_lang(self, report_ref):
        """A student card is the centre's document: printed in the centre's language (Catalan)
        whoever prints it, as a minute is (ir.actions.report._ems_in_centre_lang)."""
        if self._get_report(report_ref).report_name == 'ems.report_student_card':
            return self.with_context(lang=self.env['ems.minute']._ems_centre_lang())
        return self

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        return super(IrActionsReport, self._ems_student_card_lang(report_ref))._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data)

    def _render_qweb_html(self, report_ref, docids, data=None):
        return super(IrActionsReport, self._ems_student_card_lang(report_ref))._render_qweb_html(
            report_ref, docids, data=data)
