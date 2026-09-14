# -*- coding: utf-8 -*-

from datetime import date

from odoo.tests.common import TransactionCase

from odoo.addons.ems.models.shared.attendance_mixin import EMS_SKIP_AUTO_SCHEDULE_SYNC

from .common import create_level_study


class TestGroupClassroomChange(TransactionCase):
    """Issue #405: changing ems.group.space_id must propagate to the group's own teaching
    schedule (resource.calendar.attendance + ems.attendance_schedule), never at the cost of
    losing any other field written in the same save - a room collision is left pending
    (space_pending_group_sync) and resolved later via ems.group_classroom_change_wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TGCC', level={'name': 'Test Level (Group Classroom Change)'}, study={
            'code': 'TGCC001', 'name': 'Test Study (Group Classroom Change)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TGCC001', 'acronym': 'TGCC', 'name': 'Test Subject (Group Classroom Change)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.old_space, cls.new_space, cls.other_space = cls.env['ems.space'].create([{
            'code': code, 'name': name,
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        } for code, name in (
            ('TGCC-OLD', 'Test Old Space (Group Classroom Change)'),
            ('TGCC-NEW', 'Test New Space (Group Classroom Change)'),
            ('TGCC-OTH', 'Test Other Space (Group Classroom Change)'),
        )])
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Group Classroom Change)', 'employee_type': 'teacher',
            'work_email': 'test.teacher.gcc@example.com',
        })
        cls.other_teacher = cls.env['hr.employee'].create({
            'name': 'Test Other Teacher (Group Classroom Change)', 'employee_type': 'teacher',
            'work_email': 'test.other.teacher.gcc@example.com',
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'space_id': cls.old_space.id,
        })

    def _create_synced_block(self, teacher, group, space, weekday='0', hour_from=9.0, hour_to=10.0):
        """A teaching block ('resource.calendar.attendance') with its matching, already-synced
        'ems.attendance_schedule' line, linked via 'attendance_schedule_id' - built directly via
        the ORM (rather than through the real sync pipeline) for test determinism."""
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [teacher.id])], 'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject.id, 'group_ids': [(6, 0, [group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': weekday,
            'start_time': hour_from, 'end_time': hour_to, 'space_id': space.id,
        })
        block = self.env['resource.calendar.attendance'].create({
            'calendar_id': teacher.resource_calendar_id.id, 'name': "%s: %s" % (teacher.name, self.subject.name),
            'dayofweek': weekday, 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
            'group_ids': [group.id], 'subject_id': self.subject.id, 'space_id': space.id,
            'attendance_schedule_id': schedule.id,
        })
        return block, schedule

    def test_write_without_affected_blocks_is_noop(self):
        self.group.write({'space_id': self.new_space.id})
        self.assertEqual(self.group.space_id, self.new_space)
        self.assertEqual(self.group.pending_classroom_conflict_count, 0)

    def test_write_moves_block_without_conflict(self):
        block, schedule = self._create_synced_block(self.teacher, self.group, self.old_space)
        self.group.write({'space_id': self.new_space.id})
        self.assertEqual(block.space_id, self.new_space)
        self.assertEqual(schedule.space_id, self.new_space)
        self.assertFalse(block.space_pending_group_sync)
        self.assertEqual(self.group.pending_classroom_conflict_count, 0)

    def test_write_with_conflict_completes_full_write_and_flags_block(self):
        block, schedule = self._create_synced_block(self.teacher, self.group, self.old_space)
        other_group = self.env['ems.group'].create({
            'course': 2, 'acronym': 'B', 'level_id': self.level.id, 'study_id': self.study.id,
            'space_id': self.new_space.id,
        })
        _other_block, other_schedule = self._create_synced_block(self.other_teacher, other_group, self.new_space)

        self.group.write({'space_id': self.new_space.id, 'notes': 'kept me'})

        # The group's own save is never aborted - both the classroom and the unrelated field land.
        self.assertEqual(self.group.space_id, self.new_space)
        self.assertEqual(self.group.notes, 'kept me')
        # The colliding block is left exactly where it was, flagged as pending.
        self.assertEqual(block.space_id, self.old_space)
        self.assertTrue(block.space_pending_group_sync)
        self.assertEqual(self.group.pending_classroom_conflict_count, 1)
        # Nothing touched on the side it collided with.
        self.assertEqual(other_schedule.space_id, self.new_space)
        self.assertTrue(other_schedule.active)

    def _build_conflict_wizard(self):
        block, schedule = self._create_synced_block(self.teacher, self.group, self.old_space)
        other_group = self.env['ems.group'].create({
            'course': 3, 'acronym': 'C', 'level_id': self.level.id, 'study_id': self.study.id,
            'space_id': self.new_space.id,
        })
        other_block, other_schedule = self._create_synced_block(self.other_teacher, other_group, self.new_space)
        self.group.write({'space_id': self.new_space.id})
        self.assertTrue(block.space_pending_group_sync)
        wizard = self.env['ems.group_classroom_change_wizard'].create({'group_id': self.group.id})
        self.assertEqual(len(wizard.conflict_line_ids), 1)
        line = wizard.conflict_line_ids
        self.assertEqual(line.kind, 'plain_conflict')
        self.assertEqual(line.left_attendance_id, block)
        self.assertEqual(line.right_schedule_id, other_schedule)
        return wizard, line, block, schedule, other_schedule, other_block

    def test_wizard_reassign_rooms_resolves_both_sides(self):
        wizard, line, block, schedule, other_schedule, other_block = self._build_conflict_wizard()
        line.write({'resolution': 'reassign_rooms', 'left_space_id': self.new_space.id, 'right_space_id': self.other_space.id})
        wizard.action_confirm()
        self.assertEqual(block.space_id, self.new_space)
        self.assertEqual(schedule.space_id, self.new_space)
        self.assertEqual(other_schedule.space_id, self.other_space)
        # Regression (found 2026-09-08 on real data, SMX1D/SMX2D): the teacher's own calendar block
        # behind the moved-away "existing" session must follow it too, not just the schedule line -
        # otherwise the calendar still shows the old room and a later re-sync silently undoes this.
        self.assertEqual(other_block.space_id, self.other_space)
        self.assertEqual(other_block.attendance_schedule_id, other_schedule)
        self.assertFalse(block.space_pending_group_sync)
        self.assertEqual(self.group.pending_classroom_conflict_count, 0)

    def test_wizard_prevail_right_keeps_block_in_old_room(self):
        wizard, line, block, schedule, other_schedule, other_block = self._build_conflict_wizard()
        line.resolution = 'prevail_right'
        wizard.action_confirm()
        self.assertEqual(block.space_id, self.old_space)
        self.assertEqual(schedule.space_id, self.old_space)
        self.assertEqual(other_schedule.space_id, self.new_space)
        self.assertEqual(other_block.space_id, self.new_space)
        self.assertFalse(block.space_pending_group_sync)

    def test_wizard_prevail_left_archives_existing_session(self):
        wizard, line, block, schedule, other_schedule, other_block = self._build_conflict_wizard()
        line.resolution = 'prevail_left'
        wizard.action_confirm()
        self.assertEqual(block.space_id, self.new_space)
        self.assertEqual(schedule.space_id, self.new_space)
        # The colliding session has no real attendance history behind it - _archive_or_delete()
        # deletes it (and its now-empty template) outright rather than leaving dead clutter behind
        # (see ems.attendance_template._archive_or_delete's own docstring). Its own calendar block
        # is archived, not deleted (resource.calendar.attendance has no such cascade-delete rule).
        self.assertFalse(other_schedule.exists())
        self.assertFalse(other_block.active)
        self.assertFalse(block.space_pending_group_sync)

    def test_employee_wizard_surfaces_pending_conflict_from_teacher_calendar(self):
        """Issue #444's follow-up, 2026-09-12: the SAME pending-conflict mechanism, reached from a
        single teacher's own calendar (not a group-wide classroom change) -
        hr.employee.action_open_classroom_change_wizard() must surface it just like ems.group's
        own action does, reusing the exact same wizard/resolution model - generalized so
        'pending_new_space_id' (not the group's own space_id) drives the resolution."""
        block, schedule = self._create_synced_block(self.teacher, self.group, self.old_space)
        other_group = self.env['ems.group'].create({
            'course': 4, 'acronym': 'D', 'level_id': self.level.id, 'study_id': self.study.id,
            'space_id': self.new_space.id,
        })
        _other_block, other_schedule = self._create_synced_block(self.other_teacher, other_group, self.new_space)

        conflicts = block.relocate_or_flag_pending(self.new_space)

        self.assertTrue(conflicts)
        self.assertEqual(block.space_id, self.old_space)
        self.assertTrue(block.space_pending_group_sync)
        self.assertEqual(block.pending_new_space_id, self.new_space)

    def test_group_wizard_with_co_teaching_conflict_builds_two_lines_confirm_does_not_crash(self):
        """Found while preparing issue #446 (editing topic/classroom from the group's own
        Schedule tab, which is about to make this routine rather than a rare edge case): unlike
        the employee-scoped wizard (always at most one pending block per teacher's own calendar),
        the GROUP-scoped wizard's own 'pending_blocks' search has no such natural cap - a
        co-taught class colliding with the SAME already-active session flags BOTH co-teachers' own
        blocks independently (exactly like the group-wide classroom-change flow already does via
        '_propagate_classroom_change', one call per affected block). '_build_conflict_lines' then
        creates ONE conflict-line PER block, so two near-identical lines can end up both pointing
        at the SAME 'right_schedule_id'. Confirming both used to crash: resolving the first
        ('prevail_left'/'reassign_rooms' can archive-to-deletion or otherwise remove 'existing')
        cascade-deletes every OTHER still-unprocessed line referencing that same schedule too
        (required Many2one fields default to 'ondelete=cascade', see odoo/fields.py's Many2one.
        setup_nonrelated) - 'action_confirm()' then tried to call '_apply_resolution()' on an
        already-gone TransientModel record. Fixed with a plain 'line.exists()' guard in
        'action_confirm()' - safe because the underlying calendar block a vanishing line was
        about to resolve is still correctly resolved by the FIRST line's own "clear siblings" pass
        (see '_apply_resolution', issue #444's third follow-up), never silently dropped."""
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.teacher.id, self.other_teacher.id])], 'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject.id, 'group_ids': [(6, 0, [self.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '0',
            'start_time': 9.0, 'end_time': 10.0, 'space_id': self.old_space.id,
        })
        suppressed = self.env['resource.calendar.attendance'].with_context(**{EMS_SKIP_AUTO_SCHEDULE_SYNC: True})
        block = suppressed.create({
            'calendar_id': self.teacher.resource_calendar_id.id, 'name': 'Co-taught block (teacher)',
            'dayofweek': '0', 'hour_from': 9.0, 'hour_to': 10.0, 'day_period': 'morning',
            'group_ids': [self.group.id], 'subject_id': self.subject.id, 'space_id': self.old_space.id,
            'attendance_schedule_id': schedule.id,
        })
        co_teacher_block = suppressed.create({
            'calendar_id': self.other_teacher.resource_calendar_id.id, 'name': 'Co-taught block (other teacher)',
            'dayofweek': '0', 'hour_from': 9.0, 'hour_to': 10.0, 'day_period': 'morning',
            'group_ids': [self.group.id], 'subject_id': self.subject.id, 'space_id': self.old_space.id,
            'attendance_schedule_id': schedule.id,
        })
        third_teacher = self.env['hr.employee'].create({
            'name': 'Test Third Teacher (Group Classroom Change 2)', 'employee_type': 'teacher',
        })
        other_group = self.env['ems.group'].create({
            'course': 6, 'acronym': 'F', 'level_id': self.level.id, 'study_id': self.study.id,
            'space_id': self.new_space.id,
        })
        self._create_synced_block(third_teacher, other_group, self.new_space)

        block.relocate_or_flag_pending(self.new_space)
        co_teacher_block.relocate_or_flag_pending(self.new_space)
        self.assertTrue(block.space_pending_group_sync)
        self.assertTrue(co_teacher_block.space_pending_group_sync)

        action = self.group.action_open_classroom_change_wizard()
        wizard = self.env['ems.group_classroom_change_wizard'].browse(action['res_id'])
        self.assertEqual(len(wizard.conflict_line_ids), 2)
        wizard.conflict_line_ids.write({'resolution': 'prevail_left'})
        wizard.action_confirm()

        self.assertEqual(block.space_id, self.new_space)
        self.assertEqual(co_teacher_block.space_id, self.new_space)
        self.assertFalse(block.space_pending_group_sync)
        self.assertFalse(co_teacher_block.space_pending_group_sync)

    def test_resolving_from_one_teacher_also_clears_a_co_teachers_own_sibling_flag(self):
        """Issue #444's THIRD follow-up, 2026-09-12: a co-taught class shares ONE
        'ems.attendance_schedule' line, but EACH co-teacher's own 'resource.calendar.attendance'
        block gets independently flagged pending when the shared slot collides (both the
        group-wide flow's own '_propagate_classroom_change' - which finds every teacher's block at
        the group's old space and flags each one in turn - and the schedule-sync pipeline's own
        '_flag_room_change_pending' do this). Reported live: resolving the conflict from ONE
        teacher's own wizard (hr.employee.action_open_classroom_change_wizard, scoped to just
        their calendar) left the OTHER co-teacher's own sibling block stuck pending forever - the
        group's own banner kept showing "pending" even though the room had already converged
        correctly. Confirmed to happen symmetrically the other way too (resolving from the
        group's own wizard must clear a solo teacher's own sibling the same way)."""
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.teacher.id, self.other_teacher.id])], 'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject.id, 'group_ids': [(6, 0, [self.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '0',
            'start_time': 9.0, 'end_time': 10.0, 'space_id': self.old_space.id,
        })
        # NOTE: suppressed - creating these one at a time would otherwise trigger the automatic
        # sync hook after EACH create(), and in between the two, only one of the two co-teachers
        # has a real calendar row yet - a mismatch against the template's own (both teachers)
        # teacher_ids that the sync would "fix" by creating an unwanted duplicate solo template.
        # Real co-teaching is never actually constructed this way (always through the sync
        # pipeline itself, both calendars already in place) - this is test-fixture-only.
        suppressed = self.env['resource.calendar.attendance'].with_context(**{EMS_SKIP_AUTO_SCHEDULE_SYNC: True})
        block = suppressed.create({
            'calendar_id': self.teacher.resource_calendar_id.id, 'name': 'Co-taught block (teacher)',
            'dayofweek': '0', 'hour_from': 9.0, 'hour_to': 10.0, 'day_period': 'morning',
            'group_ids': [self.group.id], 'subject_id': self.subject.id, 'space_id': self.old_space.id,
            'attendance_schedule_id': schedule.id,
        })
        co_teacher_block = suppressed.create({
            'calendar_id': self.other_teacher.resource_calendar_id.id, 'name': 'Co-taught block (other teacher)',
            'dayofweek': '0', 'hour_from': 9.0, 'hour_to': 10.0, 'day_period': 'morning',
            'group_ids': [self.group.id], 'subject_id': self.subject.id, 'space_id': self.old_space.id,
            'attendance_schedule_id': schedule.id,
        })
        third_teacher = self.env['hr.employee'].create({
            'name': 'Test Third Teacher (Group Classroom Change)', 'employee_type': 'teacher',
        })
        # A DIFFERENT group - sharing no group with the co-taught class means this is a genuine
        # room collision, not legitimate co-teaching (which 'find_room_conflicts' would otherwise
        # exempt, since 'is_co_teaching_with' only needs the same subject and an overlapping group).
        unrelated_group = self.env['ems.group'].create({
            'course': 5, 'acronym': 'E', 'level_id': self.level.id, 'study_id': self.study.id,
            'space_id': self.new_space.id,
        })
        self._create_synced_block(third_teacher, unrelated_group, self.new_space)

        # Both co-teachers' own blocks are independently flagged, exactly like the group-wide flow
        # and the schedule-sync pipeline both already do for a shared class.
        block.relocate_or_flag_pending(self.new_space)
        co_teacher_block.relocate_or_flag_pending(self.new_space)
        self.assertTrue(block.space_pending_group_sync)
        self.assertTrue(co_teacher_block.space_pending_group_sync)

        # Resolve from 'self.teacher's OWN wizard only - scoped to just their calendar, so
        # 'co_teacher_block' is never even shown here.
        action = self.teacher.action_open_classroom_change_wizard()
        wizard = self.env['ems.group_classroom_change_wizard'].browse(action['res_id'])
        self.assertEqual(len(wizard.conflict_line_ids), 1)
        wizard.conflict_line_ids.resolution = 'prevail_left'
        wizard.action_confirm()

        self.assertEqual(block.space_id, self.new_space)
        self.assertFalse(block.space_pending_group_sync)
        # The co-teacher's own sibling block, never shown in THIS wizard, must still be cleared.
        self.assertEqual(co_teacher_block.space_id, self.new_space)
        self.assertFalse(co_teacher_block.space_pending_group_sync)
        self.assertFalse(co_teacher_block.pending_new_space_id)
