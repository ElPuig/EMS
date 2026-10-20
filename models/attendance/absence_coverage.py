# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import format_date, format_list, plaintext2html

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
# The arrangements: the two lessons of the group swapped between their teachers (nobody loses a
# lesson), a lesson at the start or end of the group's day moved into the empty one (the group
# comes in later or leaves earlier, which the families must be told), or anything else the
# teachers agreed and the board cannot work out by itself (two groups joined for the same subject,
# for instance), recorded by hand so that it is on record.
ARRANGEMENT_TYPES = [
    ('swap', 'Lesson swap'),
    ('move', 'Lesson moved'),
    ('manual', 'Other arrangement'),
]

# Same 'GWC' code the board and its PDF check to tag a WC guard "(WC)". Who may cover a class is
# decided by ems.non_teaching_type.is_regular_guard instead (issue #606), never by this code.
WC_GUARD_CODE = 'GWC'


def overlaps(start, stop, other_start, other_stop):
    return start < other_stop - HOUR_EPSILON and stop > other_start + HOUR_EPSILON


class EmsAbsenceCover(models.Model):
    """One class left without its teacher by an absence, and the guard teacher sent to cover it
    (issue #571) - or, instead of a class, a guard duty that is not regular (WC, break...) left
    without its teacher, which a regular guard covers the same way (issue #606): `duty_id` is then
    set and `group_id` empty, exactly one of the two always. Keyed by the absent teacher, the date, the period and the group, never by the
    absence record itself: an expected absence entered by the Head of Studies and the request
    the teacher files afterwards (which takes its place) are the same absence for whoever plans
    the guards, so an assignment made on the first one stays valid on the second without being
    copied, and only the days or hours the request adds come up as new rows to cover.

    An internal arrangement (issue #605) is the other way of resolving the class: no guard is
    sent because the teachers rearranged themselves ('arrangement_type'). 'guard_employee_id' is
    then the teacher who is with the group instead (they are busy, so the board never offers them
    as a guard then) and 'vacated_hour_from'/'vacated_hour_to' their own lesson with the group:
    in a swap the absent teacher teaches it, in a moved lesson nobody does, which changes the
    group's day (it comes in later or leaves earlier) - the families have to be told, 'notice_id'
    is that notice, and the arrangement only counts once it has been sent ('is_effective'), which
    accepting it from the board does at once (issue #652). A manual arrangement is a description
    ('message'), with the teacher involved if there is one.

    A swap or a moved lesson also changes when the group has a subject: its students are told by
    a notice of their own (issue #649, 'student_notice_id', see notice_arrangement.py), which the
    arrangement never waits for."""
    _name = 'ems.absence_cover'
    _description = "Absence cover: a guard teacher sent to a class left without its teacher"
    _inherit = ['mail.thread']
    _order = 'date desc, hour_from, id'
    _sql_constraints = [
        ('class_or_duty', 'CHECK((group_id IS NULL) != (duty_id IS NULL))',
         'A cover is either for a class or for a guard duty.'),
    ]

    date = fields.Date(string="Date", required=True, index=True)
    hour_from = fields.Float(string="From", required=True)
    hour_to = fields.Float(string="To", required=True)
    absent_employee_id = fields.Many2one(string="Absent teacher", comodel_name='hr.employee', required=True, index=True)
    group_id = fields.Many2one(string="Group", comodel_name='ems.group', ondelete='restrict')
    duty_id = fields.Many2one(string="Guard duty", comodel_name='ems.non_teaching_type', ondelete='restrict')
    subject_id = fields.Many2one(string="Subject", comodel_name='ems.subject')
    space_id = fields.Many2one(string="Room", comodel_name='ems.space')
    cover_type = fields.Selection(string="Resolved by", selection=COVER_TYPES, default='guard', required=True)
    arrangement_type = fields.Selection(string="Arrangement", selection=ARRANGEMENT_TYPES)
    guard_employee_id = fields.Many2one(string="Guard teacher", comodel_name='hr.employee')
    message = fields.Text(string="Message")
    vacated_hour_from = fields.Float(string="Lesson left free from")
    vacated_hour_to = fields.Float(string="Lesson left free until")
    # Deleting the draft notice discards the arrangement waiting for it: it was never accepted.
    notice_id = fields.Many2one(string="Notice", comodel_name='ems.notice', ondelete='cascade', index='btree_not_null')
    is_effective = fields.Boolean(string="Effective", compute='_compute_is_effective')
    # The notice telling the group's students that a lesson changes time (issue #649): the draft
    # still to send, or the last one sent. Unlike notice_id, the arrangement never waits for it.
    student_notice_id = fields.Many2one(
        string="Notice to the students", comodel_name='ems.notice', ondelete='set null', index='btree_not_null', copy=False)
    state = fields.Selection(
        string="State",
        selection=[('assigned', 'Assigned'), ('released', 'Released')],
        default='assigned',
        required=True,
    )
    assigned_by_id = fields.Many2one(string="Assigned by", comodel_name='res.users', default=lambda self: self.env.user)
    is_self_assigned = fields.Boolean(string="Self-assigned", compute='_compute_is_self_assigned')

    @api.depends('group_id', 'duty_id')
    def _compute_display_name(self):
        for cover in self:
            cover.display_name = cover.group_id.name or cover.duty_id.name

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

    @api.constrains('cover_type', 'arrangement_type', 'guard_employee_id', 'message', 'vacated_hour_from', 'vacated_hour_to')
    def _check_arrangement(self):
        for cover in self:
            if cover.cover_type == 'guard' or cover.arrangement_type in ('swap', 'move'):
                if not cover.guard_employee_id:
                    raise ValidationError(_("Choose the teacher who will be with the group."))
            if cover.cover_type != 'arrangement':
                continue
            if not cover.arrangement_type:
                raise ValidationError(_("Choose the kind of arrangement."))
            if cover.arrangement_type == 'manual' and not (cover.message or '').strip():
                raise ValidationError(_("Describe the arrangement: who moves which lesson."))
            if cover.arrangement_type in ('swap', 'move') and (
                    not cover.vacated_hour_to
                    or overlaps(cover.vacated_hour_from, cover.vacated_hour_to, cover.hour_from, cover.hour_to)):
                raise ValidationError(_("The lesson left free cannot be the one being covered."))

    def _arrangement_label(self):
        """What the arrangement is, in one sentence, for the board and the PDF."""
        self.ensure_one()
        course = self.env['ems.course']
        values = {
            'teacher': self.guard_employee_id.name, 'absent': self.absent_employee_id.name,
            'time': course._format_report_time(self.hour_from),
            'other_time': course._format_report_time(self.vacated_hour_from),
        }
        if self.arrangement_type == 'swap':
            return _("Swap: %(teacher)s teaches at %(time)s and %(absent)s at %(other_time)s.", **values)
        if self.arrangement_type == 'move':
            return _("%(teacher)s moves their %(other_time)s lesson to %(time)s.", **values)
        if self.guard_employee_id:
            return _("%(teacher)s: %(note)s", teacher=self.guard_employee_id.name, note=self.message)
        return self.message

    @api.constrains('date', 'hour_from', 'hour_to', 'absent_employee_id', 'group_id', 'duty_id', 'state')
    def _check_one_guard_per_class(self):
        for cover in self.filtered(lambda cover: cover.state == 'assigned'):
            others = self.search([
                ('id', '!=', cover.id), ('state', '=', 'assigned'), ('date', '=', cover.date),
                ('absent_employee_id', '=', cover.absent_employee_id.id),
                ('group_id', '=', cover.group_id.id), ('duty_id', '=', cover.duty_id.id),
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
            'group': cover.display_name,
            'date': format_date(cover.env, cover.date),
            'time': cover._time_label(),
        }
        if released:
            subject = cover.env._("Guard duty cancelled: %(group)s, %(date)s %(time)s", **values)
            intro = (cover.env._("You no longer need to cover this guard duty:") if cover.duty_id
                     else cover.env._("You no longer need to cover this class:"))
        else:
            subject = cover.env._("Guard duty: cover %(group)s, %(date)s %(time)s", **values)
            intro = (cover.env._("You have been assigned to cover this guard duty:") if cover.duty_id
                     else cover.env._("You have been assigned to cover this class:"))
        details = [
            cover.env._("Date: %s", values['date']),
            cover.env._("Time: %s", values['time']),
            cover.env._("Guard duty: %s", values['group']) if cover.duty_id else cover.env._("Group: %s", values['group']),
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

    def _notify_arrangements(self, cancelled=False):
        """_notify_arrangement for each of these covers, telling each teacher once about each
        lesson of theirs that moves: the covers of one move (one per group and per teacher whose
        class it fills) are one decision."""
        notified = set()
        for cover in self:
            cover._notify_arrangement(cancelled=cancelled, notified=notified)

    def _notify_arrangement(self, cancelled=False, notified=None):
        """Tells the teachers an internal arrangement involves (issue #605) - whoever is with the
        group instead and, in a swap or a moved lesson, the absent teacher - what it is, or that it
        no longer applies. Like a guard, an Odoo message as their own preference says, sent once
        the arrangement is in effect (a moved lesson waits for its notice to the families). A
        teacher whose own lesson was moved to fill another gap (issue #645) is not away: they are
        told about their own move, and the absent teacher named is the one the chain started from;
        a shared lesson moved for several groups is one message naming them all. `notified`: the
        `(teacher told, teacher who moves, day, arrangement, lesson left free)` already told by the
        same action, skipped and filled in (see _notify_arrangements)."""
        self.ensure_one()
        course = self.env['ems.course']
        absent = course._cover_original_absent(self)
        teachers = self.guard_employee_id
        if self.arrangement_type in ('swap', 'move') and absent == self.absent_employee_id:
            teachers |= self.absent_employee_id
        groups = format_list(self.env, self._with_siblings().group_id.mapped('name'))
        for teacher in teachers:
            if notified is not None:
                key = (teacher.id, self.guard_employee_id.id, self.date, self.arrangement_type, self.vacated_hour_from)
                if key in notified:
                    continue
                notified.add(key)
            partner = self._guard_partner(teacher)
            if not partner:
                continue
            cover = self.with_context(lang=partner.lang or self.env.lang)
            values = {'group': groups, 'date': format_date(cover.env, cover.date)}
            if cancelled:
                subject = cover.env._("Arrangement cancelled: %(group)s, %(date)s", **values)
                intro = cover.env._("This arrangement no longer applies, the usual timetable is back:")
            else:
                subject = cover.env._("Timetable arrangement: %(group)s, %(date)s", **values)
                intro = cover.env._("A change in your timetable has been agreed to cover an absence:")
            details = [
                cover._arrangement_label(),
                cover.env._("Date: %s", values['date']),
                cover.env._("Group: %s", values['group']),
                cover.env._("Absent teacher: %s", absent.name),
            ]
            if not cancelled:
                details += cover.env['ems.course']._cover_schedule_changes(cover)
            body = Markup("<p>{}</p>{}").format(intro, self.env['ems.base'].build_html_list(details))
            cover.sudo().message_notify(partner_ids=partner.ids, subject=subject, body=body)

    def _board_records(self, absent_employee_id, group_id, guard_employee_id, duty_id=False):
        """The records a board action names: the absent teacher, what of theirs is covered - a
        class of `group_id`, or (issue #606) their guard duty `duty_id` - and the guard."""
        absent = self.env['hr.employee'].browse(absent_employee_id).exists()
        group = self.env['ems.group'].browse(group_id).exists() if group_id else self.env['ems.group']
        duty = self.env['ems.non_teaching_type'].browse(duty_id).exists() if duty_id else self.env['ems.non_teaching_type']
        guard = self.env['hr.employee'].browse(guard_employee_id).exists()
        if not (absent and bool(group) != bool(duty) and guard):
            raise UserError(_("The class or the guard teacher no longer exists."))
        return absent, group, duty, guard

    def _check_board_assignable(self, day, hour_from, hour_to, absent, group, duty, guard):
        """What `guard` may be sent to: the block of `group`'s day, or the absent teacher's own
        guard duty `duty` - the day is not over, it still needs a guard and `guard` is on regular
        guard duty then. Raises otherwise. Returns that block (or duty entry) and the part of the
        period `guard` covers (issue #637: their guard duty may only overlap part of it)."""
        course = self.env['ems.course']
        course._check_board_day_not_past(day)
        if duty:
            needed = course._get_needed_duty_entry(day, duty, absent, hour_from, hour_to)
            if not needed:
                raise UserError(_("This guard duty no longer needs covering: the absence or the timetable has changed. Reload the board."))
        else:
            needed = course._get_needed_absence_block(day, group, absent, hour_from, hour_to)
            if not needed:
                raise UserError(_("This class no longer needs covering: the absence or the class has changed. Reload the board."))
        span = course._get_guard_candidates(day, hour_from, hour_to).get(guard)
        if not span:
            raise UserError(_("%s is not on guard duty in this period.", guard.name))
        return needed, span

    def _board_current_covers(self, day, hour_from, hour_to, absent, group, duty):
        """Whatever resolves this class (or guard duty) now - a guard or an arrangement, effective
        or not."""
        return self.sudo().search([
            ('state', '=', 'assigned'), ('date', '=', day), ('absent_employee_id', '=', absent.id),
            ('group_id', '=', group.id), ('duty_id', '=', duty.id),
        ]).filtered(lambda cover: overlaps(cover.hour_from, cover.hour_to, hour_from, hour_to))

    def _board_create_cover(self, day, hour_from, hour_to, absent, group, duty, guard, needed, message=False, **values):
        # A guard duty has no subject or room of its own; a class takes its absent teacher's.
        first = (self.env['resource.calendar.attendance'] if duty
                 else needed['entries'].filtered(lambda attendance: attendance.employee_id == absent)[:1])
        return self.sudo().create({
            'date': day, 'hour_from': hour_from, 'hour_to': hour_to,
            'absent_employee_id': absent.id, 'group_id': group.id, 'duty_id': duty.id,
            'subject_id': first.subject_id.id, 'space_id': first.space_id.id,
            'guard_employee_id': guard.id, 'message': message, 'assigned_by_id': self.env.uid,
            **values,
        })

    def _with_siblings(self):
        """These covers and, for a shared lesson moved for several groups (issue #645), that same
        move's covers of the other groups: one decision, applied and withdrawn as a whole."""
        moves = self.filtered(lambda cover: cover.arrangement_type == 'move' and cover.state == 'assigned')
        if not moves:
            return self
        others = self.sudo().search([
            ('date', 'in', moves.mapped('date')), ('guard_employee_id', 'in', moves.guard_employee_id.ids),
            ('arrangement_type', '=', 'move'), ('state', '=', 'assigned')])
        return self | others.filtered(lambda other: any(
            other.date == move.date and other.guard_employee_id == move.guard_employee_id
            and overlaps(other.vacated_hour_from, other.vacated_hour_to, move.vacated_hour_from, move.vacated_hour_to)
            and overlaps(other.hour_from, other.hour_to, move.hour_from, move.hour_to) for move in moves))

    def _arrangement_notice_pairs(self):
        """`{(group id, day)}` whose students' notice these covers concern (issue #649): those of
        the swaps and moved lessons among them."""
        return {(cover.group_id.id, cover.date) for cover in self
                if cover.cover_type == 'arrangement' and cover.arrangement_type in ('swap', 'move')}

    def _board_withdraw(self, message=False):
        """Takes these covers off their class: a guard is released and told so; an arrangement
        simply stops counting, and one still waiting for its notice loses that draft too (nobody
        was told anything yet). A moved shared lesson is withdrawn from all its groups. The
        students' notice of the lessons it moved is brought up to date (issue #649)."""
        covers = self._with_siblings()
        pairs = covers.filtered(lambda cover: cover.state == 'assigned')._arrangement_notice_pairs()
        arrangements = self.browse()
        for cover in covers:
            if not cover.exists() or cover.state != 'assigned':
                continue  # gone with a draft notice of the same move
            if cover.cover_type == 'arrangement' and cover.notice_id.state == 'draft':
                cover.notice_id.unlink()  # cascades to the arrangement waiting for it
                continue
            cover.write({'state': 'released'})
            if cover.cover_type == 'guard':
                cover._notify_guard(cover.guard_employee_id, released=True, message=message)
            else:
                arrangements |= cover
        arrangements._notify_arrangements(cancelled=True)
        self.env['ems.notice']._sync_arrangement_notices(pairs)

    # Board actions. Called from the guard duty board's absences table
    # (static/src/js/backend/guard_duty_board.js); every one re-checks on the server that the
    # current user may manage the absent teacher's cover, whatever the screen showed.

    @api.model
    def board_assign(self, day, hour_from, hour_to, absent_employee_id, group_id, guard_employee_id, message=False,
                     duty_id=False):
        """Sends `guard_employee_id` to cover `absent_employee_id`'s class of `group_id` in the
        period - or, with `duty_id` and no group, their guard duty (issue #606) - notifying them.
        The guard covers the part of the period their own guard duty overlaps, all of it or only
        some (issue #637), so several guards can each cover part of one class. Assigning someone
        else to a part that already had a guard releases (and tells) the previous one, and replaces
        an internal arrangement; assigning the same one again re-sends the message, which is how a
        planner adds or corrects the instructions."""
        day = fields.Date.to_date(day)
        absent, group, duty, guard = self._board_records(absent_employee_id, group_id, guard_employee_id, duty_id)
        self.env['ems.course']._check_cover_manager(day, absent, group, hour_from, hour_to)
        needed, (span_from, span_to) = self._check_board_assignable(day, hour_from, hour_to, absent, group, duty, guard)

        # Only what overlaps the part `guard` covers is replaced: another guard may be covering the
        # rest of the class (issue #637).
        current = self._board_current_covers(day, span_from, span_to, absent, group, duty)
        same = current.filtered(lambda cover: cover.cover_type == 'guard' and cover.guard_employee_id == guard
                                and (cover.hour_from, cover.hour_to) == (span_from, span_to))[:1]
        (current - same)._board_withdraw()
        if same:
            cover = same
            cover.write({'message': message, 'assigned_by_id': self.env.uid})
        else:
            cover = self._board_create_cover(day, span_from, span_to, absent, group, duty, guard, needed, message)
        cover._notify_guard(guard, released=False, message=message)
        return cover.id

    @api.model
    def board_arrange(self, day, hour_from, hour_to, absent_employee_id, group_id, arrangement_type,
                      employee_id=False, note=False, vacated_hour_from=0.0, vacated_hour_to=0.0):
        """Resolves `absent_employee_id`'s class of `group_id` in the period with an internal
        arrangement instead of a guard (issue #605), replacing whatever covered it (a guard is
        released and told). A swap must be one of those the board detected (see
        ems.course._get_arrangement_options): `employee_id` and their lesson with the group at
        `vacated_hour_from`/`_to`. A manual one is `note`, with `employee_id` if a teacher is
        involved. Moved lessons are applied as part of a plan instead (board_apply_plan). The
        teachers involved are told, and a swap sends the notice to the group's students at once
        (issues #649, #652). Returns `{'cover_id', 'notice_action', 'notice_error'}`: the latter two
        that notice's form and the reason, if it could not be sent and stays a draft to review
        (False otherwise)."""
        cover = self._board_arrange_cover(day, hour_from, hour_to, absent_employee_id, group_id, arrangement_type,
                                          employee_id, note, vacated_hour_from, vacated_hour_to)
        students = self.env['ems.notice']._sync_arrangement_notices(cover._arrangement_notice_pairs())
        return {'cover_id': cover.id, **self._board_send_notices(students)}

    def _board_arrange_cover(self, day, hour_from, hour_to, absent_employee_id, group_id, arrangement_type,
                             employee_id=False, note=False, vacated_hour_from=0.0, vacated_hour_to=0.0):
        """board_arrange's arrangement itself, checked, applied and told to the teachers involved,
        without the students' notice: a plan (board_apply_plan) prepares that once for all its
        steps."""
        day = fields.Date.to_date(day)
        absent = self.env['hr.employee'].browse(absent_employee_id).exists()
        group = self.env['ems.group'].browse(group_id).exists()
        teacher = self.env['hr.employee'].browse(employee_id).exists() if employee_id else self.env['hr.employee']
        if not (absent and group) or (employee_id and not teacher):
            raise UserError(_("The class or the guard teacher no longer exists."))
        course = self.env['ems.course']
        course._check_cover_manager(day, absent, group, hour_from, hour_to)
        course._check_board_day_not_past(day)
        block = course._get_needed_absence_block(day, group, absent, hour_from, hour_to)
        if not block:
            raise UserError(_("This class no longer needs covering: the absence or the class has changed. Reload the board."))
        # Teachers rearrange a group's lessons: an arrangement is always about a class, never a
        # guard duty (issue #606), which only a guard can cover.
        duty = self.env['ems.non_teaching_type']
        current = self._board_current_covers(day, hour_from, hour_to, absent, group, duty)
        values = {'cover_type': 'arrangement', 'arrangement_type': arrangement_type}
        option = None
        if arrangement_type not in ('swap', 'manual'):
            raise UserError(_("This arrangement is no longer possible: the absences or the timetable have changed. Reload the board."))
        if arrangement_type == 'manual':
            if not (note or '').strip():
                raise UserError(_("Describe the arrangement: who moves which lesson."))
            if teacher and course._guard_duty_absence_state(
                    course._get_guard_duty_absence_intervals(day, teacher), teacher, hour_from, hour_to):
                raise UserError(_("%s is away in this period.", teacher.name))
        else:
            option = next((option for option in course._get_arrangement_options(
                day, group, absent, hour_from, hour_to, exclude=current)
                if option['type'] == arrangement_type and option['teacher'] == teacher
                and overlaps(option['hour_from'], option['hour_to'], vacated_hour_from, vacated_hour_to)), None)
            if not option:
                raise UserError(_("This arrangement is no longer possible: the absences or the timetable have changed. Reload the board."))
            values.update(vacated_hour_from=option['hour_from'], vacated_hour_to=option['hour_to'])
        current._board_withdraw()
        cover = self._board_create_cover(day, hour_from, hour_to, absent, group, duty, teacher, block, note, **values)
        cover._notify_arrangement()
        return cover

    @api.model
    def _board_send_notices(self, notices):
        """Sends the notices a board action prepared (issue #652: accepting the arrangement is the
        confirmation) and returns `{'notice_action', 'notice_error'}`: the form of the first one
        that could not be sent and stays a draft to review, and why (both False when every one
        was sent)."""
        drafts, error = notices._send_or_keep_draft()
        if not drafts:
            return {'notice_action': False, 'notice_error': False}
        return {'notice_action': drafts[:1]._absence_change_form_action(),
                'notice_error': _("The notice could not be sent and stays a draft for you to review: %s", error)}

    @api.model
    def board_apply_plan(self, day, steps, reopen=None):
        """Applies the steps of a detected plan (issue #645) the planner kept, in their order:
        `steps` are their 'payload' (see ems.course._arrangement_plan_data). Any subset is
        possible as long as no kept step needs one left out - a move into the gap another one
        leaves, a notice freeing the group from a lesson a move left free - which the server checks
        again, with everything else, against the day as it is now: a stale screen can never apply
        something no longer possible.

        - A moved lesson is an arrangement of each of its groups, one per teacher whose class it
          fills (the absent one, or one whose lesson an earlier step moved); without its notice it
          is in effect at once, and the lesson it leaves free is a class to cover like any other.
        - The notices are one notice per group (issue #652), telling every change the kept steps
          bring to its day (a later entry, an earlier leave, a longer break), sent at once: keeping
          the step is the confirmation. The moves whose lessons it frees the group from wait for it
          as with a single moved lesson, so they are in effect as soon as it is sent. A draft
          prepared earlier for one of those same changes is replaced by it.
        - A swap is applied as board_arrange applies it.
        - Every group whose lessons a move or a swap changes gets a notice to its students (issue
          #649), sent at once too, in effect or not: the arrangement does not wait for it.
        - A correction (issue #659) of what a group's families were told goes in that same notice,
          which is then a correction: one email per group. `reopen`, `(group id, side)`, is the
          side whose communicated change the plan replaces (see
          ems.course.get_change_proposal_options): it is planned as if nothing had been told.
        The teachers whose lessons move are told once, when their move is in effect. A notice that
        cannot be sent stays a draft, and the moves waiting for it with it, for the planner to
        review and send from its form. Returns `{'cover_ids', 'notice_action', 'notice_error'}`:
        the form of the first notice left in draft (to the families first), and why, or False."""
        if reopen:
            return self.with_context(ems_reopen_side=list(reopen)).board_apply_plan(day, steps)
        day = fields.Date.to_date(day)
        course = self.env['ems.course']
        course._check_board_day_not_past(day)
        Group, Employee = self.env['ems.group'], self.env['hr.employee']
        moves, notices, corrections = [], [], []
        for step in steps:
            groups = Group.browse(step.get('group_ids') or []).exists()
            if not groups or len(groups) != len(set(step['group_ids'])):
                raise UserError(_("The class or the guard teacher no longer exists."))
            if step['kind'] in ('notice', 'correction'):
                (notices if step['kind'] == 'notice' else corrections).append((groups, tuple(step['change'])))
                continue
            teacher = Employee.browse(step['teacher_id']).exists()
            absent = Employee.browse(step.get('absent_id')).exists() if step.get('absent_id') else Employee
            if step['kind'] not in ('move', 'swap') or not teacher or (step['kind'] == 'swap' and not absent):
                raise UserError(_("The class or the guard teacher no longer exists."))
            moves.append((step['kind'], teacher, tuple(step['lesson']), tuple(step['target']), groups, absent))
        if not moves and not notices and not corrections:
            raise UserError(_("Choose at least one step of the arrangement."))
        context = course._arrangement_context(day)
        linked = course._linked_groups(context, (moves[0][4] if moves else (notices + corrections)[0][0])[:1])
        if any(groups - linked for *_head, groups, _absent in moves) \
                or any(groups - linked for groups, _change in notices + corrections):
            raise UserError(_("This arrangement is no longer possible: the absences or the timetable have changed. Reload the board."))
        planner = course._arrangement_planner(context, linked)
        planned = [(kind, teacher.id, lesson, target, frozenset(groups.ids), *([absent.id] if kind == 'swap' else []))
                   for kind, teacher, lesson, target, groups, absent in moves]
        if planner.check(planned, [(group.id, change) for groups, change in notices for group in groups]):
            raise UserError(_("This arrangement is no longer possible: the absences or the timetable have changed. Reload the board."))

        created = self.browse()
        applied = ()
        for (kind, teacher, lesson, target, groups, absent), step in zip(moves, planned):
            if kind == 'swap':
                created |= self._board_arrange_cover(day, *target, absent.id, groups.id, 'swap', teacher.id, False, *lesson)
            else:
                created |= self._board_create_move(context, planner.simulate(applied), day, teacher, lesson, target, groups)
            applied = (*applied, step)
        for cover in created:
            course._check_cover_manager(day, cover.absent_employee_id, cover.group_id, cover.hour_from, cover.hour_to)

        Notice = self.env['ems.notice']
        changes_by_group = {}
        for groups, change in notices + corrections:
            for group in groups:
                changes_by_group.setdefault(group, []).append(change)
        families = Notice
        group_states = course._get_absence_change_states(day, Group.union(*changes_by_group)) if changes_by_group else {}
        for group, changes in changes_by_group.items():
            states = group_states[group.id].values()
            replaced = Notice
            rectification = False
            for change in changes:
                # A side already told is changed as a correction (issue #659): a stale one, or one
                # whoever organises it changes their mind about.
                state = next((state for state in states if any(
                    course._same_change(change, option) for option in state['options'] + state['change_options'])), None)
                if not state:
                    raise UserError(_("This arrangement is no longer possible: the absences or the timetable have changed. Reload the board."))
                rectification = rectification or bool(state['communicated'])
                if not any(course._is_absence_manager(course._original_absent(context['covers'] | created, teacher, group, 0, 24), group)
                           for teacher in state['teachers']):
                    raise AccessError(_("Only whoever organises the absences of this group's classes can do this."))
                if course._same_change(state['draft_change'], change):
                    replaced |= state['draft']
            notice = Notice._create_absence_change_notice(changes, group, day, rectification=rectification)
            created.sudo().filtered(lambda cover, group=group, changes=changes: cover.group_id == group
                                    and cover.arrangement_type == 'move' and any(course._change_window_contains(
                                        change, cover.vacated_hour_from, cover.vacated_hour_to) for change in changes)
                                    ).notice_id = notice
            # A draft prepared earlier for these same changes (proposed alone, or a plan's notice
            # that could not be sent) is replaced: whatever waited for it now waits for this one.
            replaced = replaced.filtered(lambda draft, changes=changes: all(any(
                course._same_change(told, change) for change in changes) for told in draft._absence_change_tuples()))
            if replaced:
                self.sudo().search([('notice_id', 'in', replaced.ids)]).notice_id = notice
                replaced.sudo().unlink()
            families |= notice
        # Every teacher is told once below, for everything in effect: not once per notice sent.
        sent = self._board_send_notices(families.with_context(ems_skip_arrangement_notify=True))
        created.filtered(lambda cover: cover.arrangement_type == 'move' and cover.is_effective)._notify_arrangements()
        students = Notice._sync_arrangement_notices(created._arrangement_notice_pairs())
        result = self._board_send_notices(students)
        if sent['notice_action']:
            result = sent
        return {'cover_ids': created.ids, **result}

    def _board_create_move(self, context, day_blocks, day, teacher, lesson, target, groups):
        """The covers of one moved lesson (issue #645): one per group and per teacher whose class
        in the gap it fills, the gap being as earlier steps of the plan left it (`day_blocks`, see
        ArrangementPlanner.simulate)."""
        covers = self.browse()
        Employee = self.env['hr.employee']
        for group in groups:
            block = next(block for block in day_blocks[group.id] if overlaps(block['hour_from'], block['hour_to'], *target))
            for absent in Employee.browse(sorted(block['teachers'])):
                first = context['by_teacher'].get(absent.id, self.env['resource.calendar.attendance']).filtered(
                    lambda attendance, block=block, group=group: group in attendance.group_ids
                        and overlaps(attendance.hour_from, attendance.hour_to, block['hour_from'], block['hour_to']))[:1]
                covers |= self.sudo().create({
                    'date': day, 'hour_from': block['hour_from'], 'hour_to': block['hour_to'],
                    'absent_employee_id': absent.id, 'group_id': group.id,
                    'subject_id': first.subject_id.id, 'space_id': first.space_id.id,
                    'guard_employee_id': teacher.id, 'assigned_by_id': self.env.uid,
                    'cover_type': 'arrangement', 'arrangement_type': 'move',
                    'vacated_hour_from': lesson[0], 'vacated_hour_to': lesson[1],
                })
        return covers

    @api.model
    def board_release(self, cover_id, message=False):
        """Takes the guard off a class (because it no longer needs covering, or the planner
        changed their mind) and tells them so; on an internal arrangement, withdraws it."""
        cover = self.sudo().browse(cover_id).exists()
        if not cover or cover.state != 'assigned':
            raise UserError(_("This assignment no longer exists. Reload the board."))
        self.env['ems.course']._check_cover_manager(
            cover.date, cover.absent_employee_id, cover.group_id, cover.hour_from, cover.hour_to)
        cover._board_withdraw(message=message)
        return True

    # Self-assignment (issue #601): a teacher on guard duty takes a class still left without
    # anybody on their own, without waiting for its planner. Nobody is told - the board already
    # shows it - and only a class with no guard yet can be taken; changing someone else's
    # assignment stays with the absent teacher's chain of command.

    @api.model
    def board_self_assign(self, day, hour_from, hour_to, absent_employee_id, group_id, duty_id=False):
        """The current user, on regular guard duty in the period, covers `absent_employee_id`'s
        class of `group_id` - or their guard duty `duty_id` (issue #606) - themselves: the part of
        it their own guard duty overlaps (issue #637)."""
        day = fields.Date.to_date(day)
        guard = self.env.user.employee_id
        if not guard:
            raise UserError(_("Only a teacher on guard duty can cover a class."))
        absent, group, duty, guard = self._board_records(absent_employee_id, group_id, guard.id, duty_id)
        needed, (span_from, span_to) = self._check_board_assignable(day, hour_from, hour_to, absent, group, duty, guard)
        # Their own part of the class (issue #637), as long as nobody covers it yet.
        if self._board_current_covers(day, span_from, span_to, absent, group, duty):
            raise UserError(_("This class already has a guard teacher assigned. Reload the board."))
        return self._board_create_cover(day, span_from, span_to, absent, group, duty, guard, needed).id

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
