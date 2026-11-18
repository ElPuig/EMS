# -*- coding: utf-8 -*-

from odoo import _, api, fields, models

# The walkouts whose students who join are off the roll-calls of the day (issue #844).
APPLIED_STATES = ('closed', 'validated')


class EmsStudentWalkoutAttendancePartner(models.Model):
    """Issue #844: a student who joins a student walkout is not required to attend the classes of its
    day, from when joining closes with the group's support. Here, not in models/attendance/: it extends
    _ems_not_expected_reasons, which withdrawal_expected.py (loaded with contacts/) defines."""
    _inherit = 'res.partner'

    @api.model
    def _ems_walkout_lines_on(self, students, day):
        """{student id: ems.student_walkout.line} of `students` joining a walkout on `day` (the centre's
        date) that applies. One search."""
        lines = self.env['ems.student_walkout.line'].sudo().search([
            ('student_id', 'in', students.ids), ('joins', '=', True),
            ('walkout_id.walkout_date', '=', day), ('walkout_id.state', 'in', APPLIED_STATES),
        ])
        return {line.student_id.id: line for line in lines if line.walkout_id.group_supports}

    @api.model
    def _ems_not_expected_reasons(self, students, subject, start):
        reasons = super()._ems_not_expected_reasons(students, subject, start)
        pending = students.filtered(lambda student: student.id not in reasons)
        if pending and start:
            day = self.env['ems.datetime_utils'].utc_to_local_date(start)
            for student_id in self._ems_walkout_lines_on(pending, day):
                reasons[student_id] = {'active': False, 'not_expected_reason': 'walkout'}
        return reasons


class EmsStudentWalkoutAttendanceSessionLine(models.Model):
    """Issue #844: "not required to attend: student walkout". Neither an absence nor a presence; only the
    family of a minor who joins without its ratification is told of the class, for information."""
    _inherit = 'ems.attendance_session_line'

    not_expected_reason = fields.Selection(selection_add=[('walkout', 'Student walkout')],
                                           ondelete={'walkout': 'set null'})

    def _ems_unratified_walkout_lines(self):
        """The lines of `self` off the roll-call for a walkout their student joins as a minor whose
        family has not ratified it (pending, refused or never asked through the portal). One search
        per walkout day."""
        lines = self.filtered(lambda line: not line.active and line.not_expected_reason == 'walkout')
        unratified = self.browse()
        for day, day_lines in lines.grouped(lambda line: line.attendance_session_id.date).items():
            walkout_lines = self.env['res.partner']._ems_walkout_lines_on(day_lines.student_id, day)
            unratified |= day_lines.filtered(lambda line: (walkout_line := walkout_lines.get(line.student_id.id))
                                             and walkout_line.needs_ratification
                                             and walkout_line.ratification != 'ratified')
        return unratified

    def status_is_notificable(self):
        if super().status_is_notificable():
            return True
        # A session's creation works the whole session out once (ems_unratified_walkout_line_ids), not
        # with a search per line.
        known = self.env.context.get('ems_unratified_walkout_line_ids')
        return self.id in known if known is not None else bool(self._ems_unratified_walkout_lines())

    @api.depends('active', 'not_expected_reason')
    def _compute_roll_call_label(self):
        super()._compute_roll_call_label()
        for line in self._ems_unratified_walkout_lines():
            line.roll_call_label = _("%(label)s (the family has not said it agrees: it will be told)",
                                     label=line.roll_call_label)
