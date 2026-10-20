# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import format_date

from ..attendance.absence_coverage import BREAK_CHANGES, CHANGE_SIDES, COMMUNICATED_NOTICE_STATES

# The order the changes of one notice are told in: the start of the day, its breaks, its end.
SIDE_ORDER = {'entry': 0, 'break': 1, 'leave': 2}


def in_day_order(changes):
    return sorted(changes, key=lambda change: (SIDE_ORDER[CHANGE_SIDES[change[0]]], change[1]))


class EmsNoticeAbsenceChange(models.Model):
    """A notice that tells a group's students and families their day changes because a teacher
    is away (issues #539/#581): they can come in later, leave earlier, have a longer break or no
    classes at all, or - as a rectification - that a side of the day is back to normal. One notice
    can tell several of these at once (issue #652: a guard arrangement plan accepted from the board
    sends one notice per group and day with every change it brings), at most one per side of the
    day. The notice itself is the record of what was communicated: the guard duty board reads
    'absence_changes' back to strike out what no longer needs a guard, and to offer a
    rectification when the absences change after it was sent, since a sent notice can never be
    taken back."""
    _inherit = 'ems.notice'

    absence_date = fields.Date(string="Absence day", readonly=True, copy=False, index=True)
    absence_group_id = fields.Many2one(string="Absence group", comodel_name='ems.group', readonly=True, copy=False)
    # The changes the notice tells, each as the same list the board's options use: [change type,
    # hour] or, for a break, [change type, hour from, hour to] (see CHANGE_TYPES). Only ever
    # written by EMS itself, together with the notice, and always read with it: a JSON list on
    # the notice, like the students' notice's arrangement_lessons, needs no access rules of its
    # own to stay in step with the notice's.
    absence_changes = fields.Json(string="Timetable changes", readonly=True, copy=False)
    absence_change_label = fields.Char(string="Timetable change", compute='_compute_absence_change_label')

    @api.depends('absence_changes')
    def _compute_absence_change_label(self):
        course = self.env['ems.course']
        for notice in self:
            notice.absence_change_label = course._absence_changes_label(notice._absence_change_tuples())

    @api.constrains('absence_group_id', 'group_ids', 'notice_line_ids')
    def _check_absence_change_recipients(self):
        """A timetable change only concerns its own group: proposing one is open to department
        chiefs (see security/rules/communications.xml), who cannot otherwise send notices, so it
        must not be turned into a notice for anybody else."""
        for notice in self.filtered('absence_group_id'):
            if notice.group_ids != notice.absence_group_id or notice.notice_line_ids.filtered(
                    lambda line: line.source_group_id != notice.absence_group_id):
                raise ValidationError(_(
                    "A timetable change notice can only be sent to the students and families of %s.",
                    notice.absence_group_id.name))

    def _absence_change_tuples(self):
        """The changes the notice tells, as the tuples the board's options use."""
        self.ensure_one()
        return [tuple(change) for change in self.absence_changes or []]

    def write(self, vals):
        """A moved lesson (issue #605) only counts once its notice to the families has left the
        draft state: that is when the teachers involved are told about it - or, if the notice is
        taken back to draft, that it no longer applies. Each teacher is told once, however many
        covers of the same move wait for the notice. A board action that sends notices itself
        (board_apply_plan) tells them afterwards, once for everything it applied, and skips this
        with the 'ems_skip_arrangement_notify' context key. The group's tutors get a copy of this
        notice and of the students' one about moved lessons either way (issue #658)."""
        if 'state' not in vals:
            return super().write(vals)
        before = {notice.id: notice.state in COMMUNICATED_NOTICE_STATES for notice in self}
        result = super().write(vals)
        changed = self.filtered(lambda notice: (notice.state in COMMUNICATED_NOTICE_STATES) != before[notice.id])
        if changed and not self.env.context.get('ems_skip_arrangement_notify'):
            covers = self.env['ems.absence_cover'].sudo().search([('notice_id', 'in', changed.ids), ('state', '=', 'assigned')])
            effective = covers.filtered('is_effective')
            effective._notify_arrangements()
            (covers - effective)._notify_arrangements(cancelled=True)
        for notice in changed:
            notice._notify_group_tutors(cancelled=notice.state not in COMMUNICATED_NOTICE_STATES)
        return result

    def _notify_group_tutors(self, cancelled=False):
        """Tells the tutors of the group a guard duty board notice is about (issue #658) what its
        students or families have been told - a shorter day, a longer break, lessons at a
        different time - or, if it is taken back to draft before going out, that it was cancelled:
        an Odoo message, as their own preference says, like the teachers an arrangement involves.
        A reinforcement group has no tutor: those of its main groups are told."""
        self.ensure_one()
        group = self.absence_group_id or self.arrangement_group_id
        if not group:
            return
        for tutor in (group | group.parent_group_ids).tutor_id:
            partner = self.env['ems.absence_cover']._guard_partner(tutor)
            if not partner:
                continue
            notice = self.with_context(lang=partner.lang or self.env.lang)
            values = {'group': group.name, 'subject': self.subject}
            if cancelled:
                subject = notice.env._("Notice cancelled: %(subject)s", **values)
                intro = notice.env._("This notice about group %(group)s has been cancelled:", **values)
            else:
                subject = notice.env._("Notice sent to %(group)s: %(subject)s", **values)
                intro = notice.env._("As tutor, here is a copy of the notice sent about group %(group)s:", **values)
            body = Markup("<p>{}</p>{}").format(intro, self.message)
            notice.sudo().message_notify(partner_ids=partner.ids, subject=subject, body=body)

    def _absence_change_text(self, changes, group, day, rectification):
        """(subject, html message) proposed for the timetable changes `changes` of `group` on
        `day`, in the wording the centre's own notices already used ("A causa de l'absència
        justificada del docent assignat, ...", subject "AIF1 | ... podran sortir abans de
        l'institut"): one sentence per change, from the start of the day to its end. Only a
        starting point, the planner can edit a draft before sending it."""
        changes = in_day_order(changes)
        values = {'group': group.name, 'date': format_date(self.env, day)}
        if len(changes) == 1:
            subject = self._absence_change_sentences(changes[0], values)[0]
        else:
            subject = _("%(group)s | timetable changes on %(date)s", **values)
        paragraphs = [_("Dear students and families,")]
        paragraphs += [self._absence_change_sentences(change, values)[1] for change in changes]
        if rectification:
            subject = _("Correction: %s", subject)
            paragraphs.insert(1, _("This message corrects the one we sent you earlier about this day."))
        message = Markup("").join(Markup("<p>{}</p>").format(paragraph) for paragraph in paragraphs)
        return subject, message

    def _absence_change_sentences(self, change, values):
        """(subject, sentence) telling one change, `values` being the group's and the day's."""
        course = self.env['ems.course']
        change_type = change[0]
        values = dict(values, hour=course._format_report_time(change[1]))
        # A break's span; every sentence below is built, so the others need it too.
        values.update(start=values['hour'], end=course._format_report_time(change[2]) if len(change) > 2 else values['hour'])
        subjects = {
            'late_entry': _("%(group)s | they can come in later on %(date)s", **values),
            'early_leave': _("%(group)s | they can leave earlier on %(date)s", **values),
            'no_classes': _("%(group)s | no classes on %(date)s", **values),
            'long_break': _("%(group)s | longer break on %(date)s", **values),
            'normal_entry': _("%(group)s | usual timetable on %(date)s", **values),
            'normal_leave': _("%(group)s | usual timetable on %(date)s", **values),
            'normal_break': _("%(group)s | usual timetable on %(date)s", **values),
        }
        sentences = {
            'late_entry': _("Due to the justified absence of the assigned teacher, group %(group)s will start classes at %(hour)s on %(date)s.", **values),
            'early_leave': _("Due to the justified absence of the assigned teacher, group %(group)s will finish classes at %(hour)s on %(date)s.", **values),
            'no_classes': _("Due to the justified absence of the assigned teacher, group %(group)s will have no classes on %(date)s.", **values),
            'long_break': _("Due to the justified absence of the assigned teacher, group %(group)s will have a longer break, from %(start)s to %(end)s, on %(date)s.", **values),
            'normal_entry': _("Group %(group)s will start classes at the usual time on %(date)s.", **values),
            'normal_leave': _("Group %(group)s will finish classes at the usual time on %(date)s.", **values),
            'normal_break': _("Group %(group)s will have the usual break, from %(start)s to %(end)s, on %(date)s.", **values),
        }
        return subjects[change_type], sentences[change_type]

    @api.model
    def board_send_absence_change(self, day, group_id, change_type, hour=0.0, hour_to=0.0):
        """Sends the notice of a timetable change the board proposed, a correction included (issue
        #652): clicking "Send notice" is the confirmation, as checking a notice step of a plan is.
        Returns `{'notice_action', 'notice_error'}` as ems.absence_cover._board_send_notices: the
        draft's form and why, when it could not be sent and stays a draft to review."""
        notice = self._board_absence_change_draft(day, group_id, change_type, hour, hour_to)
        return self.env['ems.absence_cover']._board_send_notices(notice)

    @api.model
    def _board_absence_change_draft(self, day, group_id, change_type, hour=0.0, hour_to=0.0):
        """The draft notice for a timetable change the board proposed, created if no draft for
        that exact change exists yet. The change must be one of the options the group's day
        currently offers, on whichever side (start, end or a break) it belongs to, and the user
        must organise the absences it concerns."""
        day = fields.Date.to_date(day)
        group = self.env['ems.group'].browse(group_id).exists()
        if not group or change_type not in CHANGE_SIDES:
            raise UserError(_("This group no longer exists."))
        course = self.env['ems.course']
        course._check_board_day_not_past(day)
        if change_type in BREAK_CHANGES:
            requested = (change_type, hour, hour_to)
        else:
            requested = (change_type, hour if change_type in ('late_entry', 'early_leave') else 0.0)
        # A change already told can still be changed for another one, as a correction (issue #659).
        state, change = next(((state, option) for state in course._get_absence_change_states(day, group)[group.id].values()
                              for option in state['options'] + state['change_options']
                              if course._same_change(option, requested)), (None, None))
        if not change:
            raise UserError(_("The absences of this group have changed since the board was loaded. Reload the board."))
        if not any(course._is_absence_manager(teacher, group) for teacher in state['teachers']):
            raise AccessError(_("Only whoever organises the absences of this group's classes can do this."))
        notice = state['draft'] if course._same_change(state['draft_change'], change) else self.browse()
        if not notice:
            notice = self._create_absence_change_notice([change], group, day, rectification=bool(state['communicated']))
        return notice

    @api.model
    def _create_absence_change_notice(self, changes, group, day, rectification):
        """A draft notice telling `group`'s students and families about `changes` on `day` (at most
        one per side of the day), with the proposed wording and the group's usual recipients.
        Never sent from here."""
        subject, message = self._absence_change_text(changes, group, day, rectification=rectification)
        draft = self.new({'group_ids': [(6, 0, group.ids)]})
        lines, _skipped = draft._build_auto_lines(group, draft.recipient_type, draft.recipient_email_type, set())
        return self.create({
            'subject': subject,
            'message': message,
            'group_ids': [(6, 0, group.ids)],
            'notice_line_ids': [(0, 0, {
                'partner_id': line.partner_id.id, 'email': line.email, 'student_id': line.student_id.id,
                'recipient_type': line.recipient_type, 'source_group_id': line.source_group_id.id,
            }) for line in lines],
            'absence_date': day,
            'absence_group_id': group.id,
            'absence_changes': [list(change) for change in in_day_order(changes)],
        })

    def _absence_change_form_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ems.notice',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'current',
        }
