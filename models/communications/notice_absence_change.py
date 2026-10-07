# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import format_date

from ..attendance.absence_coverage import CHANGE_SIDES, CHANGE_TYPES


class EmsNoticeAbsenceChange(models.Model):
    """A notice that tells a group's students and families their day changes because a teacher
    is away (issues #539/#581): they can come in later, leave earlier, or have no classes at all,
    or - as a rectification - that a side of the day is back to normal. The notice itself is the
    record of what was communicated: the guard duty board reads these fields back to strike out
    what no longer needs a guard, and to offer a rectification when the absences change after it
    was sent, since a sent notice can never be taken back."""
    _inherit = 'ems.notice'

    absence_date = fields.Date(string="Absence day", readonly=True, copy=False, index=True)
    absence_group_id = fields.Many2one(string="Absence group", comodel_name='ems.group', readonly=True, copy=False)
    absence_change_type = fields.Selection(string="Timetable change", selection=CHANGE_TYPES, readonly=True, copy=False)
    absence_change_hour = fields.Float(string="Time", readonly=True, copy=False)

    @api.constrains('absence_change_type', 'group_ids', 'notice_line_ids')
    def _check_absence_change_recipients(self):
        """A timetable change only concerns its own group: proposing one is open to department
        chiefs (see security/rules/communications.xml), who cannot otherwise send notices, so it
        must not be turned into a notice for anybody else."""
        for notice in self.filtered('absence_change_type'):
            if notice.group_ids != notice.absence_group_id or notice.notice_line_ids.filtered(
                    lambda line: line.source_group_id != notice.absence_group_id):
                raise ValidationError(_(
                    "A timetable change notice can only be sent to the students and families of %s.",
                    notice.absence_group_id.name))

    def _absence_change_text(self, change_type, group, day, hour, rectification):
        """(subject, html message) proposed for a timetable change - only a starting point, the
        planner edits the draft before sending it."""
        values = {
            'group': group.name,
            'date': format_date(self.env, day),
            'hour': self.env['ems.course']._format_report_time(hour),
        }
        sentences = {
            'late_entry': _("On %(date)s, group %(group)s will start classes at %(hour)s.", **values),
            'early_leave': _("On %(date)s, group %(group)s will finish classes at %(hour)s.", **values),
            'no_classes': _("On %(date)s, group %(group)s will have no classes.", **values),
            'normal_entry': _("On %(date)s, group %(group)s will start classes at the usual time.", **values),
            'normal_leave': _("On %(date)s, group %(group)s will finish classes at the usual time.", **values),
        }
        subject = _("Timetable change for %(group)s on %(date)s", **values)
        paragraphs = [_("Dear students and families,"), sentences[change_type]]
        if rectification:
            subject = _("Correction: %s", subject)
            paragraphs.insert(1, _("This message corrects the one we sent you earlier about this day."))
        if change_type in ('late_entry', 'early_leave', 'no_classes'):
            paragraphs.append(_("This is due to the absence of a teacher."))
        message = Markup("").join(Markup("<p>{}</p>").format(paragraph) for paragraph in paragraphs)
        return subject, message

    @api.model
    def board_propose_absence_change(self, day, group_id, change_type, hour=0.0):
        """Opens the draft notice for a timetable change the board proposed, creating it if no
        draft for that exact change exists yet. Never sends anything: the planner reviews the
        draft and sends it from the notice's own form."""
        day = fields.Date.to_date(day)
        group = self.env['ems.group'].browse(group_id).exists()
        if not group or change_type not in CHANGE_SIDES:
            raise UserError(_("This group no longer exists."))
        course = self.env['ems.course']
        course._check_board_day_not_past(day)
        state = course._get_absence_change_states(day, group)[group.id][CHANGE_SIDES[change_type]]
        target = state['target']
        if not target or target != (change_type, hour if change_type in ('late_entry', 'early_leave') else 0.0):
            raise UserError(_("The absences of this group have changed since the board was loaded. Reload the board."))
        if not any(course._is_absence_manager(teacher) for teacher in state['teachers']):
            raise AccessError(_("Only the department chief of the absent teacher, or someone above them, can do this."))
        notice = state['draft']
        if not notice:
            subject, message = self._absence_change_text(
                change_type, group, day, target[1], rectification=bool(state['communicated']))
            draft = self.new({'group_ids': [(6, 0, group.ids)]})
            lines, _skipped = draft._build_auto_lines(group, draft.recipient_type, draft.recipient_email_type, set())
            notice = self.create({
                'subject': subject,
                'message': message,
                'group_ids': [(6, 0, group.ids)],
                'notice_line_ids': [(0, 0, {
                    'partner_id': line.partner_id.id, 'email': line.email, 'student_id': line.student_id.id,
                    'recipient_type': line.recipient_type, 'source_group_id': line.source_group_id.id,
                }) for line in lines],
                'absence_date': day,
                'absence_group_id': group.id,
                'absence_change_type': change_type,
                'absence_change_hour': target[1],
            })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ems.notice',
            'res_id': notice.id,
            'views': [(False, 'form')],
            'target': 'current',
        }
