# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
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

# How a class left without its teacher gets resolved (issues #571/#605): a guard teacher is sent to
# it, or the teachers rearrange themselves (two of them swap lessons, one moves a lesson earlier so
# the group leaves sooner...) so that nobody has to cover it.
COVER_TYPES = [
    ('guard', 'Guard teacher'),
    ('arrangement', 'Internal arrangement'),
]

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
    copied, and only the days or hours the request adds come up as new rows to cover.

    An internal arrangement (issue #605) is the other way of resolving the class: no guard is
    sent because the teachers rearranged themselves. 'guard_employee_id' is then the teacher who
    is with the group instead (they are busy, so the board never offers them as a guard then),
    'message' describes the movement, and 'vacated_hour_from'/'vacated_hour_to' the lesson of
    theirs with the group it leaves free, if any. When that free lesson changes the group's day
    (it can leave earlier, come in later...) the families have to be told: 'notice_id' is that
    notice, and the arrangement only counts once it has been sent ('is_effective')."""
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
    cover_type = fields.Selection(string="Resolved by", selection=COVER_TYPES, default='guard', required=True)
    guard_employee_id = fields.Many2one(string="Guard teacher", comodel_name='hr.employee', required=True)
    message = fields.Text(string="Message")
    vacated_hour_from = fields.Float(string="Lesson left free from")
    vacated_hour_to = fields.Float(string="Lesson left free until")
    # Deleting the draft notice discards the arrangement waiting for it: it was never accepted.
    notice_id = fields.Many2one(string="Notice", comodel_name='ems.notice', ondelete='cascade', index='btree_not_null')
    is_effective = fields.Boolean(string="Effective", compute='_compute_is_effective')
    state = fields.Selection(
        string="State",
        selection=[('assigned', 'Assigned'), ('released', 'Released')],
        default='assigned',
        required=True,
    )
    assigned_by_id = fields.Many2one(string="Assigned by", comodel_name='res.users', default=lambda self: self.env.user)
    is_self_assigned = fields.Boolean(string="Self-assigned", compute='_compute_is_self_assigned')

    @api.depends('assigned_by_id', 'guard_employee_id.user_id')
    def _compute_is_self_assigned(self):
        """Whether the guard took the class themselves (issue #601) rather than being sent to it."""
        for cover in self:
            cover.is_self_assigned = (cover.cover_type == 'guard' and bool(cover.assigned_by_id)
                                      and cover.assigned_by_id == cover.guard_employee_id.user_id)

    @api.depends('cover_type', 'notice_id.state')
    def _compute_is_effective(self):
        """Whether the cover resolves its class: always for a guard; for an arrangement, once the
        notice its free lesson needs has left the draft state (issue #605) - accepting it and
        telling the families go together, never one without the other."""
        for cover in self:
            cover.is_effective = (cover.cover_type == 'guard' or not cover.notice_id
                                  or cover.notice_id.state in COMMUNICATED_NOTICE_STATES)

    @api.constrains('cover_type', 'message', 'vacated_hour_from', 'vacated_hour_to')
    def _check_arrangement(self):
        for cover in self.filtered(lambda cover: cover.cover_type == 'arrangement'):
            if not (cover.message or '').strip():
                raise ValidationError(_("Describe the arrangement: who moves which lesson."))
            if cover.vacated_hour_to and overlaps(cover.vacated_hour_from, cover.vacated_hour_to, cover.hour_from, cover.hour_to):
                raise ValidationError(_("The lesson left free cannot be the one being covered."))

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

    def _board_records(self, absent_employee_id, group_id, guard_employee_id):
        absent = self.env['hr.employee'].browse(absent_employee_id).exists()
        group = self.env['ems.group'].browse(group_id).exists()
        guard = self.env['hr.employee'].browse(guard_employee_id).exists()
        if not (absent and group and guard):
            raise UserError(_("The class or the guard teacher no longer exists."))
        return absent, group, guard

    def _check_board_assignable(self, day, hour_from, hour_to, absent, group, guard):
        """The block of `group`'s day `guard` may be sent to: the day is not over, the class still
        needs a guard and `guard` is on guard duty then. Raises otherwise."""
        course = self.env['ems.course']
        course._check_board_day_not_past(day)
        block = course._get_needed_absence_block(day, group, absent, hour_from, hour_to)
        if not block:
            raise UserError(_("This class no longer needs covering: the absence or the class has changed. Reload the board."))
        if guard not in course._get_guard_candidates(day, hour_from, hour_to):
            raise UserError(_("%s is not on guard duty in this period.", guard.name))
        return block

    def _board_current_covers(self, day, hour_from, hour_to, absent, group):
        """Whatever resolves this class now - a guard or an arrangement, effective or not."""
        return self.sudo().search([
            ('state', '=', 'assigned'), ('date', '=', day),
            ('absent_employee_id', '=', absent.id), ('group_id', '=', group.id),
        ]).filtered(lambda cover: overlaps(cover.hour_from, cover.hour_to, hour_from, hour_to))

    def _board_create_cover(self, day, hour_from, hour_to, absent, group, guard, block, message=False, **values):
        first = block['entries'].filtered(lambda attendance: attendance.employee_id == absent)[:1]
        return self.sudo().create({
            'date': day, 'hour_from': hour_from, 'hour_to': hour_to,
            'absent_employee_id': absent.id, 'group_id': group.id,
            'subject_id': first.subject_id.id, 'space_id': first.space_id.id,
            'guard_employee_id': guard.id, 'message': message, 'assigned_by_id': self.env.uid,
            **values,
        })

    def _board_withdraw(self, message=False):
        """Takes these covers off their class: a guard is released and told so; an arrangement
        simply stops counting, and one still waiting for its notice loses that draft too (nobody
        was told anything yet)."""
        for cover in self:
            if cover.cover_type == 'arrangement' and cover.notice_id.state == 'draft':
                cover.notice_id.unlink()  # cascades to the arrangement waiting for it
                continue
            cover.write({'state': 'released'})
            if cover.cover_type == 'guard':
                cover._notify_guard(cover.guard_employee_id, released=True, message=message)

    # Board actions. Called from the guard duty board's absences table
    # (static/src/js/backend/guard_duty_board.js); every one re-checks on the server that the
    # current user may manage the absent teacher's cover, whatever the screen showed.

    @api.model
    def board_assign(self, day, hour_from, hour_to, absent_employee_id, group_id, guard_employee_id, message=False):
        """Sends `guard_employee_id` to cover `absent_employee_id`'s class of `group_id` in the
        period, notifying them. Assigning someone else to a class that already had a guard
        releases (and tells) the previous one, and replaces an internal arrangement; assigning the
        same one again re-sends the message, which is how a planner adds or corrects the
        instructions."""
        day = fields.Date.to_date(day)
        absent, group, guard = self._board_records(absent_employee_id, group_id, guard_employee_id)
        self.env['ems.course']._check_absence_manager(absent)
        block = self._check_board_assignable(day, hour_from, hour_to, absent, group, guard)

        current = self._board_current_covers(day, hour_from, hour_to, absent, group)
        same = current.filtered(lambda cover: cover.cover_type == 'guard' and cover.guard_employee_id == guard)[:1]
        (current - same)._board_withdraw()
        if same:
            cover = same
            cover.write({'message': message, 'assigned_by_id': self.env.uid})
        else:
            cover = self._board_create_cover(day, hour_from, hour_to, absent, group, guard, block, message)
        cover._notify_guard(guard, released=False, message=message)
        return cover.id

    @api.model
    def board_arrange(self, day, hour_from, hour_to, absent_employee_id, group_id, employee_id, note,
                      vacated_hour_from=0.0, vacated_hour_to=0.0):
        """Records that `absent_employee_id`'s class of `group_id` in the period needs no guard
        because the teachers rearranged themselves (issue #605): `employee_id` is with the group
        instead, `note` says how, and `vacated_hour_from`/`_to` is the lesson of theirs with the
        group the movement leaves free, if any. Replaces whatever covered the class (a guard is
        released and told). When the free lesson changes the group's day, the notice for the
        families is prepared at once and the arrangement only counts once it is sent: returns
        `{'cover_id', 'notice_action'}`, the latter the draft notice's form to open (or False)."""
        day = fields.Date.to_date(day)
        absent, group, teacher = self._board_records(absent_employee_id, group_id, employee_id)
        course = self.env['ems.course']
        course._check_absence_manager(absent)
        course._check_board_day_not_past(day)
        if not (note or '').strip():
            raise UserError(_("Describe the arrangement: who moves which lesson."))
        block = course._get_needed_absence_block(day, group, absent, hour_from, hour_to)
        if not block:
            raise UserError(_("This class no longer needs covering: the absence or the class has changed. Reload the board."))
        vacated = (vacated_hour_from, vacated_hour_to) if vacated_hour_to else None
        current = self._board_current_covers(day, hour_from, hour_to, absent, group)
        course._check_arrangement_teacher(day, hour_from, hour_to, teacher, group, vacated, exclude=current)
        current._board_withdraw()
        cover = self._board_create_cover(
            day, hour_from, hour_to, absent, group, teacher, block, note, cover_type='arrangement',
            vacated_hour_from=vacated[0] if vacated else 0.0, vacated_hour_to=vacated[1] if vacated else 0.0)
        notice_action = False
        if vacated:
            change, rectification = course._get_arrangement_change(day, group, vacated)
            if change:
                notice = self.env['ems.notice']._create_absence_change_notice(change, group, day, rectification)
                cover.notice_id = notice
                notice_action = notice._absence_change_form_action()
        return {'cover_id': cover.id, 'notice_action': notice_action}

    @api.model
    def board_release(self, cover_id, message=False):
        """Takes the guard off a class (because it no longer needs covering, or the planner
        changed their mind) and tells them so; on an internal arrangement, withdraws it."""
        cover = self.sudo().browse(cover_id).exists()
        if not cover or cover.state != 'assigned':
            raise UserError(_("This assignment no longer exists. Reload the board."))
        self.env['ems.course']._check_absence_manager(cover.absent_employee_id)
        cover._board_withdraw(message=message)
        return True

    # Self-assignment (issue #601): a teacher on guard duty takes a class still left without
    # anybody on their own, without waiting for its planner. Nobody is told - the board already
    # shows it - and only a class with no guard yet can be taken; changing someone else's
    # assignment stays with the absent teacher's chain of command.

    @api.model
    def board_self_assign(self, day, hour_from, hour_to, absent_employee_id, group_id):
        """The current user, on guard duty in the period, covers `absent_employee_id`'s class of
        `group_id` themselves."""
        day = fields.Date.to_date(day)
        guard = self.env.user.employee_id
        if not guard:
            raise UserError(_("Only a teacher on guard duty can cover a class."))
        absent, group, guard = self._board_records(absent_employee_id, group_id, guard.id)
        block = self._check_board_assignable(day, hour_from, hour_to, absent, group, guard)
        if self._board_current_covers(day, hour_from, hour_to, absent, group):
            raise UserError(_("This class already has a guard teacher assigned. Reload the board."))
        return self._board_create_cover(day, hour_from, hour_to, absent, group, guard, block).id

    @api.model
    def board_self_release(self, cover_id):
        """The current user stops covering a class they took themselves. One their planner sent
        them to can only be released by the planner."""
        cover = self.sudo().browse(cover_id).exists()
        if not cover or cover.state != 'assigned':
            raise UserError(_("This assignment no longer exists. Reload the board."))
        if not cover.is_self_assigned or cover.assigned_by_id != self.env.user:
            raise AccessError(_("Only the guard teacher who took this class themselves can leave it."))
        self.env['ems.course']._check_board_day_not_past(cover.date)
        cover.write({'state': 'released'})
        return True
