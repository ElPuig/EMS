# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date, plaintext2html

from ..shared.schedule_report_mixin import HOUR_EPSILON

# How a group's day changes because of a teacher's absence (issues #539/#581), as communicated
# to its students and families through an ems.notice. Each one belongs to one "side" of the day:
# the start (entry), the end (leave), or one of the group's breaks. 'no_classes' is the start side
# stretched over the whole day, 'long_break' a break stretched over the empty lessons right before
# and/or after it, and the 'normal_*' values are the rectification that puts a side back to the
# usual timetable after something was communicated for it.
CHANGE_TYPES = [
    ('late_entry', 'Late entry'),
    ('early_leave', 'Early leave'),
    ('no_classes', 'No classes'),
    ('long_break', 'Longer break'),
    ('normal_entry', 'Usual start time'),
    ('normal_leave', 'Usual finish time'),
    ('normal_break', 'Usual break'),
]
CHANGE_SIDES = {
    'late_entry': 'entry',
    'no_classes': 'entry',
    'normal_entry': 'entry',
    'early_leave': 'leave',
    'normal_leave': 'leave',
    'long_break': 'break',
    'normal_break': 'break',
}
NORMAL_CHANGE = {'entry': 'normal_entry', 'leave': 'normal_leave', 'break': 'normal_break'}
# A break change carries its own span - (change_type, hour_from, hour_to) - every other one only
# its time: (change_type, hour).
BREAK_CHANGES = ('long_break', 'normal_break')

# A notice already on its way counts as communicated: a scheduled one is going to reach the
# families, and a failed one reached at least some of them. Only a draft has told nobody yet.
COMMUNICATED_NOTICE_STATES = ('scheduled', 'sent', 'failed')

# Same 'GWC' code get_guard_duty_board_data() checks to flag a WC guard: whoever is watching the
# toilets cannot also be in a classroom, so they are never offered to cover a class.
WC_GUARD_CODE = 'GWC'


def overlaps(start, stop, other_start, other_stop):
    return start < other_stop - HOUR_EPSILON and stop > other_start + HOUR_EPSILON


class EmsAbsenceCover(models.Model):
    """One class left without its teacher by an absence, and the guard teacher sent to cover it
    (issue #571). Keyed by the absent teacher, the date, the period and the group, never by the
    absence record itself: an expected absence entered by the Head of Studies and the request
    the teacher files afterwards (which takes its place) are the same absence for whoever plans
    the guards, so an assignment made on the first one stays valid on the second without being
    copied, and only the days or hours the request adds come up as new rows to cover."""
    _name = 'ems.absence_cover'
    _description = "Absence cover: a guard teacher sent to a class left without its teacher"
    _inherit = ['mail.thread']
    _order = 'date desc, hour_from, id'
    _rec_name = 'group_id'

    date = fields.Date(string="Date", required=True, index=True)
    hour_from = fields.Float(string="From", required=True)
    hour_to = fields.Float(string="To", required=True)
    absent_employee_id = fields.Many2one(string="Absent teacher", comodel_name='hr.employee', required=True, index=True)
    group_id = fields.Many2one(string="Group", comodel_name='ems.group', required=True)
    subject_id = fields.Many2one(string="Subject", comodel_name='ems.subject')
    space_id = fields.Many2one(string="Room", comodel_name='ems.space')
    guard_employee_id = fields.Many2one(string="Guard teacher", comodel_name='hr.employee', required=True)
    message = fields.Text(string="Message")
    state = fields.Selection(
        string="State",
        selection=[('assigned', 'Assigned'), ('released', 'Released')],
        default='assigned',
        required=True,
    )
    assigned_by_id = fields.Many2one(string="Assigned by", comodel_name='res.users', default=lambda self: self.env.user)

    @api.constrains('date', 'hour_from', 'hour_to', 'absent_employee_id', 'group_id', 'state')
    def _check_one_guard_per_class(self):
        for cover in self.filtered(lambda cover: cover.state == 'assigned'):
            others = self.search([
                ('id', '!=', cover.id), ('state', '=', 'assigned'), ('date', '=', cover.date),
                ('absent_employee_id', '=', cover.absent_employee_id.id), ('group_id', '=', cover.group_id.id),
            ])
            if any(overlaps(other.hour_from, other.hour_to, cover.hour_from, cover.hour_to) for other in others):
                raise ValidationError(_("This class already has a guard teacher assigned."))

    def _time_label(self):
        course = self.env['ems.course']
        return f"{course._format_report_time(self.hour_from)}-{course._format_report_time(self.hour_to)}"

    @staticmethod
    def _guard_partner(guard):
        return guard.user_id.partner_id or guard.work_contact_id

    def _notify_guard(self, guard, released, message=False):
        """Tells `guard` they have been sent to (or released from) this class: an Odoo message,
        delivered to their inbox or by email as their own notification preference says. Always
        the direct result of a button the planner pressed, never sent on its own."""
        self.ensure_one()
        partner = self._guard_partner(guard)
        if not partner:
            return
        cover = self.with_context(lang=partner.lang or self.env.lang)
        values = {
            'group': cover.group_id.name,
            'date': format_date(cover.env, cover.date),
            'time': cover._time_label(),
        }
        if released:
            subject = cover.env._("Guard duty cancelled: %(group)s, %(date)s %(time)s", **values)
            intro = cover.env._("You no longer need to cover this class:")
        else:
            subject = cover.env._("Guard duty: cover %(group)s, %(date)s %(time)s", **values)
            intro = cover.env._("You have been assigned to cover this class:")
        details = [
            cover.env._("Date: %s", values['date']),
            cover.env._("Time: %s", values['time']),
            cover.env._("Group: %s", values['group']),
        ]
        if cover.subject_id:
            details.append(cover.env._("Subject: %s", cover.subject_id.display_name))
        if cover.space_id:
            details.append(cover.env._("Room: %s", cover.space_id.display_name))
        details.append(cover.env._("Absent teacher: %s", cover.absent_employee_id.name))
        body = Markup("<p>{}</p>{}").format(intro, self.env['ems.base'].build_html_list(details))
        if message:
            body += plaintext2html(message)
        cover.sudo().message_notify(partner_ids=partner.ids, subject=subject, body=body)

    # Board actions. Called from the guard duty board's absences table
    # (static/src/js/backend/guard_duty_board.js); every one re-checks on the server that the
    # current user may manage the absent teacher's cover, whatever the screen showed.

    @api.model
    def board_assign(self, day, hour_from, hour_to, absent_employee_id, group_id, guard_employee_id, message=False):
        """Sends `guard_employee_id` to cover `absent_employee_id`'s class of `group_id` in the
        period, notifying them. Assigning someone else to a class that already had a guard
        releases (and tells) the previous one; assigning the same one again re-sends the message,
        which is how a planner adds or corrects the instructions."""
        day = fields.Date.to_date(day)
        course = self.env['ems.course']
        absent = self.env['hr.employee'].browse(absent_employee_id).exists()
        group = self.env['ems.group'].browse(group_id).exists()
        guard = self.env['hr.employee'].browse(guard_employee_id).exists()
        if not (absent and group and guard):
            raise UserError(_("The class or the guard teacher no longer exists."))
        course._check_absence_manager(absent)
        course._check_board_day_not_past(day)
        block = course._get_needed_absence_block(day, group, absent, hour_from, hour_to)
        if not block:
            raise UserError(_("This class no longer needs covering: the absence or the class has changed. Reload the board."))
        if guard not in course._get_guard_candidates(day, hour_from, hour_to):
            raise UserError(_("%s is not on guard duty in this period.", guard.name))

        covers = self.sudo()
        current = covers.search([
            ('state', '=', 'assigned'), ('date', '=', day),
            ('absent_employee_id', '=', absent.id), ('group_id', '=', group.id),
        ]).filtered(lambda cover: overlaps(cover.hour_from, cover.hour_to, hour_from, hour_to))
        if current and current[:1].guard_employee_id != guard:
            current.write({'state': 'released'})
            for cover in current:
                cover._notify_guard(cover.guard_employee_id, released=True)
            current = covers
        if current:
            cover = current[:1]
            cover.write({'message': message, 'assigned_by_id': self.env.uid})
        else:
            first = block['entries'].filtered(lambda attendance: attendance.employee_id == absent)[:1]
            cover = covers.create({
                'date': day, 'hour_from': hour_from, 'hour_to': hour_to,
                'absent_employee_id': absent.id, 'group_id': group.id,
                'subject_id': first.subject_id.id, 'space_id': first.space_id.id,
                'guard_employee_id': guard.id, 'message': message, 'assigned_by_id': self.env.uid,
            })
        cover._notify_guard(guard, released=False, message=message)
        return cover.id

    @api.model
    def board_release(self, cover_id, message=False):
        """Takes the guard off a class (because it no longer needs covering, or the planner
        changed their mind) and tells them so."""
        cover = self.sudo().browse(cover_id).exists()
        if not cover or cover.state != 'assigned':
            raise UserError(_("This assignment no longer exists. Reload the board."))
        self.env['ems.course']._check_absence_manager(cover.absent_employee_id)
        cover.write({'state': 'released'})
        cover._notify_guard(cover.guard_employee_id, released=True, message=message)
        return True
