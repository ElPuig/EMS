# -*- coding: utf-8 -*-

from collections import defaultdict

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_date

from ..attendance.absence_coverage import COMMUNICATED_NOTICE_STATES, overlaps


class EmsNoticeArrangement(models.Model):
    """A notice that tells a group's students that some of their lessons change time on a day
    (issue #649), because an internal arrangement of the guard duty board moved them: a lesson
    moved into the gap an absence left, or two lessons swapped. One notice per group and day,
    listing every lesson of the group that changes time then, kept up to date as arrangements are
    applied or withdrawn. Accepting an arrangement on the board sends it at once (issue #652, see
    ems.absence_cover._board_send_notices); a correction that withdrawing one prepares stays a
    draft, never sent from here: whoever organises the absences reviews it and sends it from the
    notice's own form. Unlike the notice to the families about a shorter day
    (notice_absence_change.py), no arrangement waits for it.

    'arrangement_lessons' is what the notice tells, so that a change after it was sent can be
    compared against it and a correction proposed, since a sent notice can never be taken back."""
    _inherit = 'ems.notice'

    arrangement_date = fields.Date(string="Moved lessons day", readonly=True, copy=False, index=True)
    arrangement_group_id = fields.Many2one(string="Moved lessons group", comodel_name='ems.group', readonly=True, copy=False)
    # [[subject id, teacher id, usual hour_from, usual hour_to, new hour_from, new hour_to], ...]
    arrangement_lessons = fields.Json(string="Moved lessons", readonly=True, copy=False)

    @api.constrains('arrangement_group_id', 'recipient_type', 'group_ids', 'notice_line_ids')
    def _check_arrangement_recipients(self):
        """Same reason as _check_absence_change_recipients: a department chief who organises the
        arrangement may prepare and send this notice, so it must stay a notice to that one group's
        students - never its families (issue #649) nor anybody else."""
        for notice in self.filtered('arrangement_group_id'):
            group = notice.arrangement_group_id
            if notice.recipient_type != 'students' or notice.group_ids != group or notice.notice_line_ids.filtered(
                    lambda line: line.source_group_id != group or line.recipient_type != 'student'):
                raise ValidationError(_(
                    "A notice about moved lessons can only be sent to the students of %s.", group.name))

    def unlink(self):
        """Deleting a draft notice to the families discards the moved lessons waiting for it (see
        ems.absence_cover.notice_id): the students' notice about them is brought up to date."""
        covers = self.env['ems.absence_cover'].sudo().search([('notice_id', 'in', self.ids)])
        pairs = covers._arrangement_notice_pairs()
        result = super().unlink()
        if pairs:
            self.env['ems.notice']._sync_arrangement_notices(pairs)
        return result

    @api.model
    def _arrangement_moved_lessons(self, covers):
        """`{(group id, day): {(subject id, teacher id, usual from, usual to, new from, new to)}}`:
        the lessons `covers` (swaps and moved lessons) make change time. A moved lesson is its
        teacher's lesson left free, now in the gap; a swap is that same one plus the absent
        teacher's lesson, now where the other one was. Co-taught gaps give one cover per absent
        teacher for the same moved lesson: the set keeps it once."""
        if not covers:
            return {}
        # The subject of each teacher's lesson left free, from one read of the timetable.
        attendances = self.env['ems.course']._get_guard_duty_board_attendance_ids([
            ('dayofweek', 'in', list({str(day.weekday()) for day in covers.mapped('date')})),
            ('employee_id', 'in', covers.guard_employee_id.ids), ('group_ids', 'in', covers.group_id.ids)])
        timetable = defaultdict(list)
        for attendance in attendances:
            for group in attendance.group_ids:
                timetable[(attendance.employee_id.id, group.id, attendance.dayofweek)].append(attendance)

        def subject_id(teacher, group, day, hour_from, hour_to):
            return next((attendance.subject_id.id for attendance in timetable[(teacher.id, group.id, str(day.weekday()))]
                         if overlaps(attendance.hour_from, attendance.hour_to, hour_from, hour_to)), False)

        lessons = defaultdict(set)
        for cover in covers:
            usual, new = (cover.vacated_hour_from, cover.vacated_hour_to), (cover.hour_from, cover.hour_to)
            pair = (cover.group_id.id, cover.date)
            lessons[pair].add((subject_id(cover.guard_employee_id, cover.group_id, cover.date, *usual),
                               cover.guard_employee_id.id, *usual, *new))
            if cover.arrangement_type == 'swap':
                lessons[pair].add((cover.subject_id.id, cover.absent_employee_id.id, *new, *usual))
        return lessons

    @api.model
    def _sync_arrangement_notices(self, pairs):
        """Brings the students' notice of each `(group id, day)` of `pairs` up to date with the
        arrangements in force (issue #649), and returns the drafts that need sending (accepting an
        arrangement sends them, see ems.absence_cover._board_send_notices):
        - nothing told yet: a draft listing every lesson that changes time (created, rewritten, or
          deleted when nothing changes any more);
        - a notice already sent, and the lessons no longer as it said: a correction draft listing
          the lessons that change time now and those back at their usual time; none, if the
          lessons are back to what was sent.
        A draft is only rewritten when its lessons change, so the planner's own edits survive any
        other board action. New drafts belong to the current user, as the families' ones do: they
        can review and send them; existing ones, possibly someone else's, are updated as superuser,
        since every caller has already checked the user organises these absences."""
        pairs = {(group_id, day) for group_id, day in pairs if group_id}
        if not pairs:
            return self.browse()
        group_ids = list({group_id for group_id, _day in pairs})
        days = list({day for _group_id, day in pairs})
        covers = self.env['ems.absence_cover'].sudo().search([
            ('date', 'in', days), ('group_id', 'in', group_ids), ('state', '=', 'assigned'),
            ('cover_type', '=', 'arrangement'), ('arrangement_type', 'in', ('swap', 'move'))])
        lessons = self._arrangement_moved_lessons(covers)
        covers_by_pair = defaultdict(covers.browse)
        for cover in covers:
            covers_by_pair[(cover.group_id.id, cover.date)] |= cover
        notices = self.sudo().search([
            ('arrangement_date', 'in', days), ('arrangement_group_id', 'in', group_ids)], order='id')
        notices_by_pair = defaultdict(notices.browse)
        for notice in notices:
            notices_by_pair[(notice.arrangement_group_id.id, notice.arrangement_date)] |= notice
        groups = {group.id: group for group in self.env['ems.group'].browse(group_ids)}

        drafts = self.browse()
        for group_id, day in sorted(pairs):
            current = sorted(lessons.get((group_id, day), ()))
            pair_notices = notices_by_pair[(group_id, day)]
            communicated = pair_notices.filtered(lambda notice: notice.state in COMMUNICATED_NOTICE_STATES)[-1:]
            told = sorted(tuple(lesson) for lesson in communicated.arrangement_lessons or []) if communicated else []
            draft = pair_notices.filtered(lambda notice: notice.state == 'draft')[-1:]
            if current == told:
                draft.unlink()
                notice = communicated
            elif draft and sorted(tuple(lesson) for lesson in draft.arrangement_lessons or []) == current:
                notice = draft
            else:
                moved = {lesson[:4] for lesson in current}
                back = [lesson for lesson in told if lesson[:4] not in moved]
                subject, message = self._arrangement_notice_text(
                    groups[group_id], day, current, back, correction=bool(communicated))
                values = {'subject': subject, 'message': message, 'arrangement_lessons': [list(lesson) for lesson in current]}
                if draft:
                    draft.write(values)
                    notice = draft
                else:
                    notice = self._create_arrangement_notice(groups[group_id], day, values)
            if notice.state == 'draft':
                drafts |= notice
            covers_by_pair[(group_id, day)].student_notice_id = notice
        return drafts.sudo(False)

    @api.model
    def _create_arrangement_notice(self, group, day, values):
        """A draft notice to `group`'s students only, with their usual recipients (the same ones
        _create_absence_change_notice builds, without the families). Never sent from here."""
        Notice = self.sudo(False)
        draft = Notice.new({'group_ids': [(6, 0, group.ids)], 'recipient_type': 'students'})
        lines, _skipped = draft._build_auto_lines(group, 'students', draft.recipient_email_type, set())
        return Notice.create({
            **values,
            'group_ids': [(6, 0, group.ids)],
            'recipient_type': 'students',
            'notice_line_ids': [(0, 0, {
                'partner_id': line.partner_id.id, 'email': line.email, 'student_id': line.student_id.id,
                'recipient_type': line.recipient_type, 'source_group_id': line.source_group_id.id,
            }) for line in lines],
            'arrangement_date': day,
            'arrangement_group_id': group.id,
        })

    def _arrangement_notice_text(self, group, day, lessons, back, correction):
        """(subject, html message) proposed for the students' notice: the lessons that change time
        (`lessons`) and, in a correction, those back at their usual time (`back`). Times are the
        timetable's own, already in the company's timezone. Only a starting point, the planner
        edits the draft before sending it."""
        course = self.env['ems.course']
        everything = list(lessons) + list(back)
        subjects = {subject.id: subject.name for subject in self.env['ems.subject'].sudo().browse(
            {lesson[0] for lesson in everything if lesson[0]})}
        teachers = {teacher.id: teacher.name for teacher in self.env['hr.employee'].sudo().browse(
            {lesson[1] for lesson in everything})}

        def label(lesson):
            return subjects.get(lesson[0]) or teachers.get(lesson[1], '')

        def span(hour_from, hour_to):
            return f"{course._format_report_time(hour_from)}-{course._format_report_time(hour_to)}"

        values = {'group': group.name, 'date': format_date(self.env, day)}
        subject = _("%(group)s | lessons at a different time on %(date)s", **values)
        paragraphs = [Markup("<p>{}</p>").format(_("Dear students,"))]
        if correction:
            subject = _("Correction: %s", subject)
            paragraphs.append(Markup("<p>{}</p>").format(
                _("This message corrects the one we sent you earlier about this day.")))
        if lessons:
            paragraphs.append(Markup("<p>{}</p>").format(
                _("Because a teacher is absent, these lessons of group %(group)s will be at a different time on %(date)s:", **values)))
            # A co-taught lesson is one line per teacher in `lessons`, one for the students (issue #678).
            paragraphs.append(self.env['ems.base'].build_html_list(list(dict.fromkeys(
                _("%(subject)s: from %(usual)s to %(new)s", subject=label(lesson), usual=span(*lesson[2:4]), new=span(*lesson[4:6]))
                for lesson in lessons))))
        if back:
            paragraphs.append(Markup("<p>{}</p>").format(
                _("These lessons of group %(group)s will be at their usual time on %(date)s:", **values)))
            paragraphs.append(self.env['ems.base'].build_html_list(list(dict.fromkeys(
                _("%(subject)s: %(time)s", subject=label(lesson), time=span(*lesson[2:4])) for lesson in back))))
        return subject, Markup("").join(paragraphs)
