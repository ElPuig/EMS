# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..curriculum.level import CARD_PALETTE, DEFAULT_CARD_COLOR


class ResPartner(models.Model):
    """The student card PDF (issue #524). See docs/en/developers/contacts/student_card.md."""
    _inherit = 'res.partner'

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
        # config=False: the card has its own layout, so never the document layout configurator.
        return self.env.ref('ems.action_report_student_card').report_action(students, config=False)

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
