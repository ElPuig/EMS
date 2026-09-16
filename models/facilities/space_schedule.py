# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ems_space_schedule(models.Model):
    # NOTE: an explicit '_name' is required here — a 2-item '_inherit' list without one would make
    # Odoo's metaclass define a brand-new model named after this Python class instead of extending
    # 'ems.space' in place (same gotcha documented on ems.group's own group_schedule.py and
    # res.partner (student)'s student_schedule.py).
    _name = 'ems.space'
    _inherit = ['ems.space', 'ems.schedule_report_mixin']

    # Every real teaching/non-teaching slot booked in this room, aggregated across every teacher's
    # calendar — unlike ems.group's/res.partner (student)'s own version of this field, a room's
    # occupation is a plain, direct search on 'space_id' (every candidate row already carries its
    # own, so there is no group/enrollment indirection to go through, and no break to derive: a
    # break row is tied to a LEVEL's schedule framework, not to any room, and in practice almost
    # never carries a real space_id of its own). Not stored, same pattern as the group's/student's.
    schedule_attendance_ids = fields.Many2many(string="Schedule", comodel_name="resource.calendar.attendance",
        compute="_compute_schedule_attendance_ids")

    # A real dependency on 'resource.calendar.attendance' itself can't be expressed (a cross-model
    # search) - same structural limitation as ems.group's/res.partner (student)'s own version of
    # this field. Unlike those two, there is no partial mitigation available here either: their
    # own '@api.depends' at least guards against a same-transaction staleness trap by naming a
    # field that is itself an input to the search (level_id/shift, or enrollment_ids) - a room's
    # occupation search has no input but its own id, which never changes after create(). So this
    # is a genuinely empty '@api.depends()': a value cached earlier in the same transaction (e.g.
    # a test reading this field before creating the calendar blocks that should show up in it)
    # is never invalidated by anything short of a fresh env/cache (a real web-client request
    # always gets one). Tests must create every 'resource.calendar.attendance' fixture BEFORE the
    # first read of this field, or call 'invalidate_recordset()' in between if that ordering isn't
    # possible - see feedback_compute_field_no_depends_stale_cache_in_tests in project memory.
    @api.depends()
    def _compute_schedule_attendance_ids(self):
        # 'active_test=True' forced explicitly, not left to the ORM's own default - same reasoning
        # as ems.group's/res.partner (student)'s own version of this compute: a caller context that
        # already turned active filtering off for an unrelated reason (e.g. an archived-records
        # list) must not resurrect a stale/archived calendar's own leftover attendance rows here.
        Attendance = self.env['resource.calendar.attendance'].with_context(active_test=True)
        for space in self:
            space.schedule_attendance_ids = Attendance.search([('space_id', '=', space.id)])

    def _schedule_report_shift(self):
        """A room has no shift of its own — unlike a group or a student, it can legitimately host
        classes in both the morning and the afternoon, so no shift-window filtering ever applies
        to its occupation schedule (returning a falsy value here is what makes
        'ems.schedule_report_mixin.get_schedule_report_lines()' skip that filtering step)."""
        self.ensure_one()
        return False
