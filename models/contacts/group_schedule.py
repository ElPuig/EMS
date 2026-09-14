# -*- coding: utf-8 -*-

import base64

from odoo import api, fields, models

from ..shared.schedule_report_mixin import PUBLIC_SCHEDULE_ROUTE

# Issue #453 - see docs/en/developers/contacts/group_schedule.md's "Public schedule link".
# One public PDF per group, in the centre's own language (developer choice).
PUBLIC_SCHEDULE_LANG = 'ca_ES'
# 'name' itself is a stored compute over study/course/acronym for a main group, so the fields it
# derives from have to be listed too - a write only ever carries the source field, never 'name'.
PUBLIC_SCHEDULE_GROUP_FIELDS = {
    'name', 'course', 'acronym', 'study_id', 'group_type', 'tutor_id', 'space_id', 'level_id', 'shift', 'active',
}


class ems_group_schedule(models.Model):
    # NOTE: an explicit '_name' is required here — a 2-item '_inherit' list without one would make
    # Odoo's metaclass define a brand-new model named after this Python class instead of extending
    # 'ems.group' in place (see MetaModel in odoo/models.py).
    _name = 'ems.group'
    _inherit = ['ems.group', 'ems.schedule_report_mixin']

    # Union of two sources: the group's real teaching slots, aggregated from every teacher's
    # calendar whose 'group_ids' includes this group, and — when derivable — the group's break
    # period, taken from its level's schedule framework (see '_get_break_entries'). Not stored,
    # same pattern already used for 'enrolled_student_ids'.
    schedule_attendance_ids = fields.Many2many(string="Schedule", comodel_name="resource.calendar.attendance",
        compute="_compute_schedule_attendance_ids")
    public_schedule_slug = fields.Char(string="Public schedule slug", compute="_compute_public_schedule_slug",
        store=True, index=True)
    public_schedule_url = fields.Char(string="Public schedule link", compute="_compute_public_schedule_url")
    public_schedule_pdf = fields.Binary(string="Public schedule PDF", attachment=True, readonly=True, copy=False)
    # NOTE: default True on purpose - a new group, and every group that already exists when the
    # upgrade adds this column, gets its first PDF on the next cron run with no migration needed.
    public_schedule_dirty = fields.Boolean(string="Public schedule pending update", default=True, copy=False)

    # A real dependency on 'resource.calendar.attendance' itself can't be expressed (a cross-model
    # search) - see the equivalent note on res.partner (student)._compute_schedule_attendance_ids
    # for why this still matters even so (invalidating a value the SAME transaction cached before
    # 'level_id'/'shift' changed - a fresh web request always recomputes regardless).
    @api.depends('level_id', 'shift')
    def _compute_schedule_attendance_ids(self):
        # 'active_test=True' forced explicitly, not left to the ORM's own default: this compute
        # can run under a caller context that already set active_test=False for an unrelated
        # reason (found 2026-09-10 on the student's own version of this field, opened from
        # ems.action_student_kanban - its context turns active_test off so archived/withdrawn
        # students still show up in that list). Without forcing it back on here, a stale/archived
        # calendar's own leftover attendance rows (never deleted, only archived, by course
        # transition's calendar rollover) would resurface as if they were still part of this
        # group's CURRENT schedule - duplicated against, and often overlapping, the real one.
        Attendance = self.env['resource.calendar.attendance'].with_context(active_test=True)
        for group in self:
            teaching = Attendance.search([('group_ids', '=', group.id)])
            group.schedule_attendance_ids = teaching | group._get_break_entries()

    @api.depends('name')
    def _compute_public_schedule_slug(self):
        for group in self:
            group.public_schedule_slug = self.env['ir.http']._slugify(group.name) if group.name else False

    @api.depends('public_schedule_slug')
    def _compute_public_schedule_url(self):
        for group in self:
            group.public_schedule_url = f"{group.get_base_url()}{PUBLIC_SCHEDULE_ROUTE}/{group.public_schedule_slug}.pdf" \
                if group.public_schedule_slug else False

    @api.model_create_multi
    def create(self, vals_list):
        groups = super().create(vals_list)
        groups._mark_public_schedule_dirty()
        return groups

    def write(self, vals):
        res = super().write(vals)
        if vals.keys() & PUBLIC_SCHEDULE_GROUP_FIELDS:
            self._mark_public_schedule_dirty()
        return res

    def _mark_public_schedule_dirty(self):
        """Flags these groups' public PDF for re-rendering and wakes the cron up right after this
        transaction commits - the PDF is never rendered inline, so a bulk schedule change renders
        each affected group once, outside the user's request. sudo: whoever changes a schedule
        (e.g. a teacher on their own calendar) usually has no write access to ems.group. The write
        is deliberately unconditional (even on an already-dirty group): if the cron is rendering
        that group right now, the concurrent row update makes its batch fail and retry instead of
        clearing the flag over a PDF that already misses this change."""
        groups = self.sudo().exists()
        if not groups:
            return
        groups.write({'public_schedule_dirty': True})
        self._trigger_public_schedule_cron()

    @api.model
    def _trigger_public_schedule_cron(self):
        """Wakes the cron up once per transaction. A bulk change marks groups many times over (a
        single upgrade's data reload queued 558 triggers), and every ir.cron._trigger() call also
        queues its own post-commit NOTIFY connection. Deduplicated against the database, not with a
        transaction-scoped flag in cr.precommit.data: every savepoint flushes (and so clears) the
        precommit callbacks, and the CSV loader opens one savepoint per record. The ORM stamps
        'create_date' with the transaction's own timestamp (cr.now()), so a trigger this same
        transaction already created is recognisable - and one undone by a rolled-back savepoint no
        longer counts. One per transaction is enough: a cron run deletes only the triggers older
        than the moment that run started, so a trigger committed mid-run still schedules the next."""
        # NOTE: the cron may not exist yet while a clean install is still loading data files that
        # create groups before 'data/main/ir.cron-group_public_schedule.csv' - nothing is lost,
        # since the cron's own first run (nextcall defaults to "now") renders every dirty group.
        cron = self.env.ref('ems.ir_cron_group_public_schedule', raise_if_not_found=False)
        if not cron:
            return
        already_triggered = self.env['ir.cron.trigger'].sudo().search_count(
            [('cron_id', '=', cron.id), ('create_date', '=', self.env.cr.now())], limit=1)
        if not already_triggered:
            cron.sudo()._trigger()

    @api.model
    def _mark_public_schedule_dirty_for_blocks(self, domain):
        """Marks every group whose public PDF prints one of the schedule blocks matching `domain`."""
        blocks = self.env['resource.calendar.attendance'].sudo().search(domain)
        blocks._get_public_schedule_groups()._mark_public_schedule_dirty()

    def _generate_public_schedule(self):
        report = self.env['ir.actions.report'].sudo().with_context(lang=PUBLIC_SCHEDULE_LANG)
        for group in self:
            content, _content_type = report._render_qweb_pdf('ems.report_group_schedule', group.ids)
            group.write({'public_schedule_pdf': base64.b64encode(content), 'public_schedule_dirty': False})

    @api.model
    def _cron_generate_public_schedules(self, batch_size=10):
        """Renders one bounded batch per call and reports what's left through ir.cron's own
        progress API, so the cron framework calls it again straight away in a fresh transaction -
        each batch commits on its own, and a concurrent schedule edit can only ever roll back one
        small batch. Archived groups are skipped (their public link is a 404 anyway) and picked up
        again if reactivated."""
        groups = self.sudo().search([('public_schedule_dirty', '=', True)])
        batch = groups[:batch_size]
        batch._generate_public_schedule()
        self.env['ir.cron']._notify_progress(done=len(batch), remaining=len(groups) - len(batch))

    def _get_break_entries(self):
        """The group's break/patio period, derived from its level's schedule framework — see
        'ems.schedule_report_mixin._get_level_break_entries' for the actual derivation."""
        self.ensure_one()
        return self._get_level_break_entries(self.level_id, self.shift)

    # 'get_schedule_report_lines()'/'get_subject_teachers_summary()' are inherited as-is from
    # 'ems.schedule_report_mixin' — a group's own 'shift' field is exactly what
    # 'ems.schedule_report_mixin._schedule_report_shift()' already defaults to, so no override is
    # needed here (compare with res.partner (student), which does need one).
