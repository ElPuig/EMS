from datetime import date

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestWorkingSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher User (Working Schedule)',
            'login': 'test_teacher_for_working_schedule',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.head_of_department_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Head of Department User (Working Schedule)',
            'login': 'test_hod_for_working_schedule',
            'groups_id': [(4, cls.env.ref('ems.group_department_chief').id)],
        })
        # role_secretary is unipersonal and may already be assigned to a real employee in the
        # working database; clear it so the tests below are self-contained.
        cls.env.ref('ems.role_secretary').sudo().with_context(ems_syncing_roles=True).write({'employee_ids': [(5, 0, 0)]})
        cls.level, cls.study = create_level_study(cls, 'TWSL', level={'name': 'Test Level (Working Schedule)'}, study={
            'code': 'TWSL001', 'name': 'Test Study (Working Schedule)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TWSL001',
            'acronym': 'TWSL',
            'name': 'Test Subject (Working Schedule)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TWSL-A',
            'name': 'Test Space (Working Schedule)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1,
            'acronym': 'TWSL',
            'level_id': cls.level.id,
            'study_id': cls.study.id,
            'space_id': cls.space.id,
        })
        cls.framework = cls.env['resource.calendar'].create({
            'name': 'Test Framework (Working Schedule)',
            'is_framework': True,
            'full_time_required_hours': 24,
        })
        cls.env['resource.calendar.attendance'].create({
            'calendar_id': cls.framework.id,
            'name': 'Free',
            'dayofweek': '0',
            'hour_from': 8,
            'hour_to': 9,
            'day_period': 'morning',
        })
        cls.non_teaching_br = cls.env.ref('ems.non_teaching_br')
        cls.non_teaching_g = cls.env.ref('ems.non_teaching_g')
        cls.non_teaching_cm = cls.env.ref('ems.non_teaching_cm')
        cls.non_teaching_sc = cls.env.ref('ems.non_teaching_sc')
        cls.env['resource.calendar.attendance'].create({
            'calendar_id': cls.framework.id,
            'name': 'BR: Break',
            'dayofweek': '0',
            'hour_from': 9,
            'hour_to': 9.5,
            'day_period': 'morning',
            'non_teaching': cls.non_teaching_br.id,
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Working Schedule)',
            'employee_type': 'teacher',
        })

    def test_non_teaching_type_includes_break(self):
        self.assertTrue(self.env['ems.non_teaching_type'].search([('code', '=', 'BR')]))

    def test_seed_from_framework_sets_source_and_writes_nothing(self):
        # NOTE: 'attendance_ids' is a stored compute field that auto-fills from the company's own
        # calendar when a create() call doesn't include it — passing (5, 0, 0) here keeps this fixture
        # a clean slate instead of inheriting the company's real rows (resource_calendar.py's
        # '_compute_attendance_ids'). 'seed_from_framework'/'apply_schedule_changes' are unaffected in
        # production since they always unlink weekday rows before doing anything else.
        calendar = self.env['resource.calendar'].create({
            'name': 'Test Seed Target (Working Schedule)',
            'attendance_ids': [(5, 0, 0), (0, 0, {
                'dayofweek': '1', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning', 'name': 'Old',
            })],
        })

        calendar.seed_from_framework(self.framework)

        self.assertEqual(calendar.source_framework_id, self.framework)
        # Unassigned/blank periods are never stored — seeding only points at the framework and clears
        # whatever weekday rows existed before, it does not copy the framework's own rows.
        self.assertFalse(calendar.attendance_ids.filtered(lambda a: a.dayofweek in ('0', '1', '2', '3', '4')))

    def test_apply_schedule_changes_writes_only_real_cells(self):
        calendar = self.env['resource.calendar'].create({'name': 'Test Apply (Working Schedule)'})
        cells = [{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'Test: Group',
        }]

        calendar.apply_schedule_changes(cells, source_framework_id=self.framework.id)

        self.assertEqual(len(calendar.attendance_ids), 1)
        self.assertEqual(calendar.source_framework_id, self.framework)

    def test_attendance_row_active_defaults_true_and_can_be_archived(self):
        # 'active' added 2026-08-06 (core resource.calendar.attendance has none) so a course
        # transition can archive a teacher's migrating blocks instead of unlink()-ing them - see
        # plans/course_transition_teacher_schedule_archival.md. Odoo's own generic action_archive()
        # already works for any model with this field, no override needed here.
        calendar = self.env['resource.calendar'].create({'name': 'Test Active (Working Schedule)'})
        calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'Test: Group',
        }])
        attendance = calendar.attendance_ids

        self.assertTrue(attendance.active)
        attendance.action_archive()
        self.assertFalse(attendance.active)

    def test_calendar_action_archive_cascades_to_its_attendance_rows(self):
        """Mirrors 'ems.attendance_template.action_archive()' 's own cascade to its schedule
        lines (2026-09-01, see plans/course_transition_stale_teacher_assignments.md) - archiving
        the calendar itself must not leave any of its own rows dangling active, regardless of
        which kind (teaching or non-teaching) they are."""
        calendar = self.env['resource.calendar'].create({'name': 'Test Cascade (Working Schedule)'})
        calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'Test: Group',
        }])
        teaching_row = calendar.attendance_ids
        guard_row = self.env['resource.calendar.attendance'].create({
            'calendar_id': calendar.id, 'name': 'Test Guard (Working Schedule)',
            'dayofweek': '1', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
            'non_teaching': self.non_teaching_g.id,
        })

        calendar.action_archive()

        teaching_row.invalidate_recordset()
        guard_row.invalidate_recordset()
        self.assertFalse(calendar.active)
        self.assertFalse(teaching_row.active)
        self.assertFalse(guard_row.active)

    def _bare_employee(self, name):
        # A non-teacher employee (default 'employee_type') never gets an auto-created personal
        # calendar (see 'ems_employee.create()') - a clean fixture to attach a test calendar to
        # without an auto-created sibling that could collide with it on the 'unique_name' constraint.
        return self.env['hr.employee'].create({'name': name})

    def test_create_derives_name_from_employee_and_course(self):
        # 'employee_id'/'course_id' added 2026-08-06 - see
        # plans/course_transition_teacher_schedule_archival.md. 'name' is auto-derived from them
        # ("<teacher> (<course>)") when the caller doesn't pass an explicit one, matching the
        # long-standing naming convention without every caller having to build the string by hand.
        employee = self._bare_employee('Test Derive Name With Course (Working Schedule)')
        course = self.env['ems.course'].create({'start': 2097, 'end': 2098})

        calendar = self.env['resource.calendar'].create({
            'employee_id': employee.id, 'course_id': course.id,
        })

        self.assertEqual(calendar.name, "%s (%s)" % (employee.name, course.name))

    def test_create_derives_name_from_employee_alone_without_a_course(self):
        employee = self._bare_employee('Test Derive Name No Course (Working Schedule)')

        calendar = self.env['resource.calendar'].create({'employee_id': employee.id})

        self.assertEqual(calendar.name, employee.name)

    def test_create_respects_an_explicit_name_over_the_derived_one(self):
        employee = self._bare_employee('Test Derive Name Explicit Override (Working Schedule)')

        calendar = self.env['resource.calendar'].create({
            'employee_id': employee.id, 'name': 'Test Explicit Name (Working Schedule)',
        })

        self.assertEqual(calendar.name, 'Test Explicit Name (Working Schedule)')

    def test_apply_schedule_changes_defaults_space_from_group(self):
        # 'space_id' stopped being a compute (2026-08-01, room-granularity change) - a cell that
        # doesn't specify one must still default to the group's own room, matching the old
        # compute's behavior for the common, no-override case.
        calendar = self.env['resource.calendar'].create({'name': 'Test Space Default (Working Schedule)'})
        cells = [{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'Test: Group',
        }]

        calendar.apply_schedule_changes(cells)

        self.assertEqual(calendar.attendance_ids.space_id, self.space)

    def test_apply_schedule_changes_respects_explicit_space_id(self):
        # A cell carrying its own 'space_id' (e.g. a one-off room reassignment) must survive as-is
        # instead of being silently overwritten by the group's own default room.
        other_space = self.env['ems.space'].create({
            'code': 'TWSL-B', 'name': 'Test Space B (Working Schedule)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        calendar = self.env['resource.calendar'].create({'name': 'Test Space Override (Working Schedule)'})
        cells = [{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'Test: Group',
            'space_id': other_space.id,
        }]

        calendar.apply_schedule_changes(cells)

        self.assertEqual(calendar.attendance_ids.space_id, other_space)

    def test_apply_schedule_changes_unlinks_previous_weekday_rows(self):
        calendar = self.env['resource.calendar'].create({
            'name': 'Test Apply Replace (Working Schedule)',
            'attendance_ids': [(5, 0, 0), (0, 0, {
                'dayofweek': '0', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning', 'name': 'Old',
            })],
        })

        calendar.apply_schedule_changes([{
            'dayofweek': '2', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id, 'name': 'BR: Break',
        }])

        self.assertEqual(len(calendar.attendance_ids), 1)
        self.assertEqual(calendar.attendance_ids.dayofweek, '2')

    def test_apply_schedule_changes_syncs_teaching_and_attendance_template(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Apply Sync (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        cells = [{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'Test: Group',
        }]

        schedule.apply_schedule_changes(cells)

        teaching = self.env['ems.teaching'].search([
            ('teacher_id', '=', self.teacher.id),
            ('subject_id', '=', self.subject.id),
            ('group_id', '=', self.group.id),
        ])
        self.assertTrue(teaching)

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id),
            ('subject_id', '=', self.subject.id),
        ])
        self.assertTrue(template)
        self.assertIn(self.group, template.group_ids)

    def test_apply_schedule_changes_links_calendar_attendance_to_schedule_line(self):
        # See plans/calendar_driven_attendance_templates.md, point 4 - the real FK replacing the
        # inferred (teacher+subject+group+weekday/time) matching find_schedule_lines_for_teaching
        # otherwise needs.
        schedule = self.env['resource.calendar'].create({'name': 'Test FK Link (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        cells = [{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'Test: Group',
        }]

        schedule.apply_schedule_changes(cells)

        line = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.teacher_ids', 'in', self.teacher.id),
            ('attendance_template_id.subject_id', '=', self.subject.id),
        ])
        self.assertTrue(line)
        self.assertEqual(schedule.attendance_ids.attendance_schedule_id, line)

    def test_apply_schedule_changes_links_co_teaching_calendar_rows_to_same_schedule_line(self):
        # Co-teaching cardinality: TWO teachers, each with their OWN personal calendar, land on the
        # exact same class - both calendar rows must point at the SAME single schedule line, not
        # one each. Also covers the "untouched co-teacher" case: teacher A's row was written and
        # linked by an EARLIER call, before B ever joined - re-linking it here (when B's own
        # arrival supersedes A's old solo template with a new shared one) is the whole reason
        # '_link_calendar_attendance' reads 'merged_groups' instead of the raw submission.
        other_teacher = self.env['hr.employee'].create({
            'name': 'Test Co-Teacher (Working Schedule)', 'employee_type': 'teacher',
        })
        cell = {
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'Test: Group',
        }
        self.teacher.resource_calendar_id.apply_schedule_changes([cell])

        other_teacher.resource_calendar_id.apply_schedule_changes([cell])

        line = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.subject_id', '=', self.subject.id),
            ('attendance_template_id.teacher_ids', 'in', other_teacher.id),
        ])
        self.assertEqual(len(line), 1)
        self.assertEqual(set(line.attendance_template_id.teacher_ids.ids), {self.teacher.id, other_teacher.id})
        self.assertEqual(self.teacher.resource_calendar_id.attendance_ids.attendance_schedule_id, line)
        self.assertEqual(other_teacher.resource_calendar_id.attendance_ids.attendance_schedule_id, line)

    def test_get_schedule_report_lines_only_covers_real_entries(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Report Lines (Working Schedule)'})
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
        }])

        lines = schedule.get_schedule_report_lines()

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['time_label'], '09:00-10:00')
        monday, tuesday = lines[0]['cells'][0], lines[0]['cells'][1]
        self.assertEqual(monday['entry'].subject_id, self.subject)
        self.assertTrue(monday['color'])
        self.assertFalse(tuesday['entry'])
        self.assertFalse(tuesday['color'])

    def test_get_derived_break_entries_tolerates_float_rounding_at_the_boundary(self):
        # Regression test: a framework break stored as the literal '11.416667' (25 minutes past
        # 11, as typically entered/imported) and a real period computed as '11 + 25/60' ==
        # 11.416666666666666 represent the exact same moment (11:25) but differ by a hair — a
        # strict '<' overlap check used to treat that as a genuine overlap and silently drop the
        # break, exactly as it did in production for a teacher whose first afternoon/morning
        # period started immediately after a framework break.
        level_framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (Float Rounding)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': level_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 11, 'hour_to': 11.416667, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test Float Rounding (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 11, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                # Starts at 11 + 25/60, the float-computed equivalent of the break's own hour_to.
                'dayofweek': '0', 'hour_from': 11 + 25 / 60, 'hour_to': 13, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
        ])

        breaks = self.teacher._get_derived_break_entries()

        # Not 'assertIn(our_break, breaks)': the real 'ems' database happens to already ship a
        # production CFGS framework break at this exact (day, hour_from, hour_to) — the dedup step
        # (by design) keeps only one of the two identical-slot records, and which one depends on
        # search order, not on which is "ours". What this regression test actually cares about is
        # that a break at ~11:00-11:25 survives at all despite the float-rounded boundary, not
        # which specific record represents it.
        matching = breaks.filtered(lambda attendance: attendance.dayofweek == '0' and abs(attendance.hour_from - 11) < 0.01)
        self.assertTrue(matching)
        self.assertAlmostEqual(matching[:1].hour_to, 11.416667, places=3)

    def test_get_derived_break_entries_fills_exact_gap(self):
        # NOTE: these tests run against the real 'ems' database, which already ships real,
        # seeded schedule frameworks (ESO, CFGS...) with their own real break rows — since the
        # algorithm deliberately searches EVERY framework regardless of level (see its own
        # docstring), one of those unrelated real breaks can legitimately also fit inside a
        # test's gap. Assertions below check that THIS test's own break is present (and, where
        # relevant, that unwanted ones are absent) rather than asserting an exact total count.
        level_framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (Gap Fill)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        our_break = self.env['resource.calendar.attendance'].create({
            'calendar_id': level_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 11, 'hour_to': 11.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test Gap Fill (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '0', 'hour_from': 12, 'hour_to': 13, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
        ])

        breaks = self.teacher._get_derived_break_entries()

        self.assertIn(our_break, breaks)

    def test_get_derived_break_entries_excludes_overlap_with_real_entry(self):
        level_framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (Overlap)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': level_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 11, 'hour_to': 11.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test Overlap (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        # A single long class spans right across the break's own time (9-12) — no gap to fill.
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 12, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
        }])

        # Scoped to Monday, not an exact total count: since this teacher's ONLY real entry all
        # week is this one Monday block, the weekly-span design (2026-08-11) legitimately shows
        # OTHER weekdays' own real, seeded framework breaks too (a teacher working ANY morning at
        # all now sees their morning break every weekday - see the new tests covering that
        # directly) - what this test actually cares about is that the overlap on Monday itself
        # still excludes a break there, same as before the redesign.
        self.assertFalse(self.teacher._get_derived_break_entries().filtered(lambda attendance: attendance.dayofweek == '0'))

    def test_get_derived_break_entries_excludes_break_outside_weekly_span(self):
        level_framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (Outside Span)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        # Earlier than the teacher's own first entry all week (the containment check is a
        # whole-week span since 2026-08-11, not a per-day one — with a single real entry across
        # the whole week, the two coincide, which is what this test actually exercises) — never
        # shown, per the "the teacher always enters at 11" case explicitly called out when this
        # algorithm was designed.
        self.env['resource.calendar.attendance'].create({
            'calendar_id': level_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 7, 'hour_to': 7.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test Outside Span (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
        }])

        self.assertFalse(self.teacher._get_derived_break_entries())

    def test_get_derived_break_entries_shows_several_levels_same_day(self):
        # Both real teaching assignments matter now that candidate breaks are scoped to the
        # levels the teacher actually teaches (teaching_ids.group_id.level_id, 2026-08-11) - a
        # group genuinely in 'other_level' is what makes its own break candidate discoverable at
        # all, not just its framework existing.
        other_level = self.env['ems.level'].create({'acronym': 'TWSL3', 'name': 'Test Level 3 (Working Schedule)'})
        other_study = self.env['ems.study'].create({
            'code': 'TWSL003', 'acronym': 'TWSL3', 'name': 'Test Study 3 (Working Schedule)',
            'date': date.today(), 'deprecated': False, 'level_id': other_level.id,
        })
        other_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TWSL3', 'level_id': other_level.id, 'study_id': other_study.id, 'space_id': self.space.id,
        })
        # A subject genuinely taught in 'other_study' - 'self.subject' only lists 'self.study',
        # and 'ems.attendance_template' validates a subject is actually taught in every study its
        # groups belong to.
        other_subject = self.env['ems.subject'].create({
            'code': 'TWSL004', 'acronym': 'TWSL3', 'name': 'Test Subject 3 (Working Schedule)',
            'study_ids': [(6, 0, [other_study.id])],
        })
        morning_framework = self.env['resource.calendar'].create({
            'name': 'Test Morning Framework (Multi-level)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': morning_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 10, 'hour_to': 10.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
        })
        afternoon_framework = self.env['resource.calendar'].create({
            'name': 'Test Afternoon Framework (Multi-level)', 'is_framework': True, 'level_id': other_level.id, 'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': afternoon_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 17, 'hour_to': 17.5, 'day_period': 'afternoon', 'non_teaching': self.non_teaching_br.id,
        })
        # An English-teacher-style day: one level in the morning, a different one in the afternoon —
        # this is the extreme case the gap-fill algorithm exists for (3+ levels is the same principle).
        schedule = self.env['resource.calendar'].create({'name': 'Test Multi-level (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '0', 'hour_from': 10.5, 'hour_to': 12, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '0', 'hour_from': 16, 'hour_to': 17, 'day_period': 'afternoon',
                'subject_id': other_subject.id, 'group_ids': [other_group.id], 'name': 'TWSL3: TWSL3',
            },
            {
                'dayofweek': '0', 'hour_from': 17.5, 'hour_to': 18.5, 'day_period': 'afternoon',
                'subject_id': other_subject.id, 'group_ids': [other_group.id], 'name': 'TWSL3: TWSL3',
            },
        ])

        breaks = self.teacher._get_derived_break_entries()

        self.assertIn(10.0, breaks.mapped('hour_from'))
        self.assertIn(17.0, breaks.mapped('hour_from'))

    def test_get_derived_break_entries_shows_on_day_with_no_real_entries_within_weekly_span(self):
        # Developer's own spec (2026-08-11, replacing the earlier per-day design): a break must
        # still show on a day the teacher has no real entries at all, as long as it fits within
        # the teacher's own WEEKLY working span for that half of the day — "aunque ese día el
        # docente no trabaje". The old behavior (skip a day with nothing at all) is exactly what
        # hid a real teacher's own break on their day off even though it clearly fit their known
        # weekly pattern.
        level_framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (No Entries Day)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': level_framework.id, 'name': 'BR: Break', 'dayofweek': '1',
            'hour_from': 9.25, 'hour_to': 9.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test No Entries Day (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        # Only Monday has a real entry — the break candidate is on Tuesday, a day with nothing at
        # all, but well within Monday's own morning span (9-10).
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
        }])

        breaks = self.teacher._get_derived_break_entries()

        self.assertTrue(breaks.filtered(lambda attendance: attendance.dayofweek == '1' and attendance.hour_from == 9.25))

    def test_get_derived_break_entries_shows_both_halves_every_weekday_across_different_days(self):
        # Real-world case that prompted this redesign (developer's own report): a teacher whose
        # calendar alternates between a morning-only shift on some weekdays and an afternoon-only
        # shift on others (a common dual-shift vocational-program pattern) must see BOTH breaks on
        # EVERY weekday, not just on the specific days each half happens to occur on — "si el
        # docente trabaja de mañana y tarde, se muestran ambos [...] toda la semana".
        level_framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (Both Halves)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        for day in ('0', '1', '2', '3', '4'):
            self.env['resource.calendar.attendance'].create({
                'calendar_id': level_framework.id, 'name': 'BR: Morning Break', 'dayofweek': day,
                'hour_from': 11, 'hour_to': 11.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
            })
            self.env['resource.calendar.attendance'].create({
                'calendar_id': level_framework.id, 'name': 'BR: Afternoon Break', 'dayofweek': day,
                'hour_from': 18, 'hour_to': 18.5, 'day_period': 'afternoon', 'non_teaching': self.non_teaching_br.id,
            })
        schedule = self.env['resource.calendar'].create({'name': 'Test Both Halves (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        schedule.apply_schedule_changes([
            cell
            for day, hour_from, hour_to in (
                ('0', 9, 11), ('0', 11.5, 13),      # Monday: morning only, gap at the break's own time
                ('4', 9, 11), ('4', 11.5, 13),      # Friday: morning only, same gap
                ('1', 16, 18), ('1', 18.5, 19),     # Tuesday: afternoon only, gap at the break's own time
                ('2', 16, 18), ('2', 18.5, 19),     # Wednesday: afternoon only, same gap
                ('3', 16, 18), ('3', 18.5, 19),     # Thursday: afternoon only, same gap
            )
            for cell in [{
                'dayofweek': day, 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning' if hour_from < 13 else 'afternoon',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            }]
        ])

        breaks = self.teacher._get_derived_break_entries()

        morning_days = set(breaks.filtered(lambda attendance: attendance.hour_from == 11.0).mapped('dayofweek'))
        afternoon_days = set(breaks.filtered(lambda attendance: attendance.hour_from == 18.0).mapped('dayofweek'))
        self.assertEqual(morning_days, {'0', '1', '2', '3', '4'})
        self.assertEqual(afternoon_days, {'0', '1', '2', '3', '4'})

    def test_get_derived_break_entries_never_shows_break_for_half_never_worked(self):
        # The flip side of the redesign: a teacher who never works a given half of the day AT ALL
        # (any weekday) must never see that half's break, anywhere - there is no weekly span to
        # contain it, regardless of any single day's own real entries.
        level_framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (Half Never Worked)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        for day in ('0', '1', '2', '3', '4'):
            self.env['resource.calendar.attendance'].create({
                'calendar_id': level_framework.id, 'name': 'BR: Morning Break', 'dayofweek': day,
                'hour_from': 11, 'hour_to': 11.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
            })
            self.env['resource.calendar.attendance'].create({
                'calendar_id': level_framework.id, 'name': 'BR: Afternoon Break', 'dayofweek': day,
                'hour_from': 18, 'hour_to': 18.5, 'day_period': 'afternoon', 'non_teaching': self.non_teaching_br.id,
            })
        schedule = self.env['resource.calendar'].create({'name': 'Test Half Never Worked (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        # Every real entry is in the morning, every weekday - the teacher never works any
        # afternoon at all, with a gap at 11-11.5 matching the morning break exactly.
        schedule.apply_schedule_changes([
            cell
            for day in ('0', '1', '2', '3', '4')
            for hour_from, hour_to in ((9, 11), (11.5, 13))
            for cell in [{
                'dayofweek': day, 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            }]
        ])

        breaks = self.teacher._get_derived_break_entries()

        self.assertFalse(breaks.filtered(lambda attendance: attendance.hour_from == 18.0))
        morning_days = set(breaks.filtered(lambda attendance: attendance.hour_from == 11.0).mapped('dayofweek'))
        self.assertEqual(morning_days, {'0', '1', '2', '3', '4'})

    def test_get_derived_break_entries_dedupes_identical_break_across_frameworks(self):
        other_level = self.env['ems.level'].create({'acronym': 'TWSL4', 'name': 'Test Level 4 (Working Schedule)'})
        framework_a = self.env['resource.calendar'].create({
            'name': 'Test Framework A (Dedup)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        framework_b = self.env['resource.calendar'].create({
            'name': 'Test Framework B (Dedup)', 'is_framework': True, 'level_id': other_level.id, 'full_time_required_hours': 24,
        })
        for framework in (framework_a, framework_b):
            self.env['resource.calendar.attendance'].create({
                'calendar_id': framework.id, 'name': 'BR: Break', 'dayofweek': '0',
                'hour_from': 11, 'hour_to': 11.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
            })
        schedule = self.env['resource.calendar'].create({'name': 'Test Dedup (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '0', 'hour_from': 12, 'hour_to': 13, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
        ])

        breaks = self.teacher._get_derived_break_entries()

        matching = breaks.filtered(lambda attendance: attendance.hour_from == 11.0 and attendance.hour_to == 11.5)
        self.assertEqual(len(matching), 1)

    def test_get_derived_break_entries_scoped_to_teachers_own_level(self):
        # A break from an UNRELATED level's framework must never show, even if its time would
        # otherwise fit the teacher's own weekly span and not overlap any real entry - candidates
        # are scoped to teaching_ids.group_id.level_id (2026-08-11), not searched across every
        # framework unconditionally. Developer's own report: a real teacher's calendar mixed a
        # CCFF program's own break with two unrelated ESO breaks that never applied to them.
        own_framework = self.env['resource.calendar'].create({
            'name': 'Test Own Framework (Level Scope)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        own_break = self.env['resource.calendar.attendance'].create({
            'calendar_id': own_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 11, 'hour_to': 11.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
        })
        other_level = self.env['ems.level'].create({'acronym': 'TWSL5', 'name': 'Test Level 5 (Working Schedule)'})
        other_framework = self.env['resource.calendar'].create({
            'name': 'Test Other Framework (Level Scope)', 'is_framework': True, 'level_id': other_level.id, 'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': other_framework.id, 'name': 'BR: Other Break', 'dayofweek': '0',
            'hour_from': 9.5, 'hour_to': 10, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test Level Scope (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        # A gap at 9.5-10 (where the OTHER level's own break would fit) and another at 11-11.5
        # (this teacher's own level's break) - only the teacher's own level, self.level, is ever
        # taught here (via self.group).
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 9.5, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '0', 'hour_from': 11.5, 'hour_to': 13, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
        ])

        breaks = self.teacher._get_derived_break_entries()

        self.assertIn(own_break, breaks)
        self.assertFalse(breaks.filtered(lambda attendance: attendance.hour_from == 9.5))

    def test_get_derived_break_entries_falls_back_to_every_framework_with_no_teaching_assignment(self):
        # A teacher with no real teaching_ids at all (only a non-teaching commitment so far) has
        # no identifiable level to scope to - falls back to searching every framework, same as
        # before level-scoping existed.
        level_framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (No Teaching Fallback)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        our_break = self.env['resource.calendar.attendance'].create({
            'calendar_id': level_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 11, 'hour_to': 11.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test No Teaching Fallback (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        schedule.apply_schedule_changes([
            {'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
             'non_teaching': self.non_teaching_g.id, 'name': 'Guard'},
            {'dayofweek': '0', 'hour_from': 12, 'hour_to': 13, 'day_period': 'morning',
             'non_teaching': self.non_teaching_g.id, 'name': 'Guard'},
        ])
        self.assertFalse(self.teacher.teaching_ids)

        breaks = self.teacher._get_derived_break_entries()

        self.assertIn(our_break, breaks)

    def test_get_derived_break_attendance_data_matches_derived_break_entries(self):
        level_framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (RPC Data)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': level_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 11, 'hour_to': 11.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test RPC Data (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '0', 'hour_from': 12, 'hour_to': 13, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
        ])

        data = self.teacher.get_derived_break_attendance_data()

        matching = [row for row in data if row['hour_from'] == 11.0 and row['hour_to'] == 11.5]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]['dayofweek'], '0')
        self.assertTrue(matching[0]['non_teaching_is_break'])
        self.assertEqual(matching[0]['non_teaching'][0], self.non_teaching_br.id)

    def test_report_working_schedule_includes_derived_break(self):
        level_framework = self.env['resource.calendar'].create({
            'name': 'Test Level Framework (Derived Break Report)', 'is_framework': True, 'level_id': self.level.id, 'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': level_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 11, 'hour_to': 11.5, 'day_period': 'morning', 'non_teaching': self.non_teaching_br.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test Derived Break Report (Working Schedule)'})
        self.teacher.resource_calendar_id = schedule
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '0', 'hour_from': 12, 'hour_to': 13, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
        ])

        lines = schedule.get_schedule_report_lines()

        matching = [line for line in lines if line['time_label'] == '11:00-11:30']
        self.assertEqual(len(matching), 1)
        self.assertTrue(matching[0]['cells'][0]['entry'])

    def test_get_schedule_report_lines_same_item_gets_same_color_across_days(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Report Colors (Working Schedule)'})
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '2', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '1', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'non_teaching': self.non_teaching_br.id, 'name': 'BR: Break',
            },
        ])

        lines = schedule.get_schedule_report_lines()

        monday, tuesday, wednesday = lines[0]['cells'][0], lines[0]['cells'][1], lines[0]['cells'][2]
        self.assertEqual(monday['color'], wednesday['color'])
        self.assertNotEqual(monday['color'], tuesday['color'])

    def test_get_schedule_hours_summary_groups_teaching_hours_by_level(self):
        other_level = self.env['ems.level'].create({'acronym': 'TWSL2', 'name': 'Test Level 2 (Working Schedule)'})
        other_study = self.env['ems.study'].create({
            'code': 'TWSL002', 'acronym': 'TWSL2', 'name': 'Test Study 2 (Working Schedule)',
            'date': date.today(), 'deprecated': False, 'level_id': other_level.id,
        })
        other_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TWSL2', 'level_id': other_level.id, 'study_id': other_study.id, 'space_id': self.space.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test Hours Summary (Working Schedule)'})
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '1', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '2', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [other_group.id], 'name': 'TWSL: TWSL2',
            },
        ])

        summary = schedule.get_schedule_hours_summary()

        teaching = {row['label']: row['hours'] for row in summary['teaching']['rows']}
        self.assertEqual(teaching[self.level.display_name], 2)
        self.assertEqual(teaching[other_level.display_name], 1)
        self.assertEqual(summary['teaching']['total'], 3)

    def test_get_schedule_hours_summary_groups_reinforcement_group_separately(self):
        reinforcement_group = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'REF-TWS', 'space_id': self.space.id,
        })
        schedule = self.env['resource.calendar'].create({'name': 'Test Hours Summary Reinforcement (Working Schedule)'})
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [reinforcement_group.id], 'name': 'TWSL: REF-TWS',
        }])

        summary = schedule.get_schedule_hours_summary()

        teaching = {row['label']: row['hours'] for row in summary['teaching']['rows']}
        self.assertEqual(teaching[reinforcement_group.display_name], 1)
        self.assertEqual(summary['teaching']['total'], 1)

    def test_get_schedule_hours_summary_counts_a_date_split_slot_only_once(self):
        # See plans/calendar_driven_attendance_templates.md's "Mid-course subject handoff"
        # refinement - two rows sharing the same weekday/overlapping time but scoped to different,
        # non-overlapping date ranges represent the SAME weekly slot, not two separate ones - must
        # count once (the longer entry), not add both durations together.
        schedule = self.env['resource.calendar'].create({'name': 'Test Hours Summary Date Split (Working Schedule)'})
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
                'date_from': date(2026, 9, 1), 'date_to': date(2027, 2, 28),
            },
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10.5, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
                'date_from': date(2027, 3, 1), 'date_to': date(2027, 7, 1),
            },
        ])

        summary = schedule.get_schedule_hours_summary()

        teaching = {row['label']: row['hours'] for row in summary['teaching']['rows']}
        # ceil(10.5 - 9) = 2 - the LONGER entry wins over the first-encountered 1h one.
        self.assertEqual(teaching[self.level.display_name], 2)
        self.assertEqual(summary['teaching']['total'], 2)

    def test_get_schedule_hours_summary_excludes_break(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Hours Summary Break (Working Schedule)'})
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 9.5, 'day_period': 'morning',
            'non_teaching': self.non_teaching_br.id, 'name': 'BR: Break',
        }])

        summary = schedule.get_schedule_hours_summary()

        self.assertFalse(summary['teaching']['rows'])
        self.assertFalse(summary['fixed']['rows'])
        self.assertEqual(summary['total'], 0)

    def test_get_schedule_hours_summary_guard_and_wednesday_coordination_go_to_fixed_column(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Hours Summary Fixed (Working Schedule)'})
        schedule.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
                'non_teaching': self.non_teaching_g.id, 'name': 'G: Guard',
            },
            {
                'dayofweek': '2', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
                'non_teaching': self.non_teaching_cm.id, 'name': 'CM: Coordination Meeting',
            },
            {
                'dayofweek': '1', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
                'non_teaching': self.non_teaching_cm.id, 'name': 'CM: Coordination Meeting',
            },
            {
                'dayofweek': '3', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
                'non_teaching': self.non_teaching_sc.id, 'name': 'SC: School Council',
            },
        ])

        summary = schedule.get_schedule_hours_summary()

        fixed = {row['label']: row['hours'] for row in summary['fixed']['rows']}
        teaching = {row['label']: row['hours'] for row in summary['teaching']['rows']}
        self.assertEqual(fixed['Guard'], 1)
        self.assertEqual(fixed['Coordination Meeting'], 1)  # only the Wednesday one
        self.assertEqual(teaching['Coordination Meeting'], 1)  # Tuesday one, not fixed
        self.assertEqual(teaching['School Council'], 1)
        self.assertEqual(summary['fixed']['total'], 2)
        self.assertEqual(summary['teaching']['total'], 2)
        self.assertEqual(summary['total'], 4)

    def test_get_schedule_hours_summary_rounds_partial_hours_up(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Hours Summary Rounding (Working Schedule)'})
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 9.5, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
        }])

        summary = schedule.get_schedule_hours_summary()

        self.assertEqual(summary['teaching']['rows'][0]['hours'], 1)

    def test_report_working_schedule_renders(self):
        self.teacher.resource_calendar_id = self.framework
        self.teacher.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
        }])

        content, content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_working_schedule', [self.teacher.id])

        self.assertTrue(content)
        self.assertIn(content_type, ('pdf', 'html'))
        self.assertIn(b'TWSL', content)

    def test_report_working_schedule_includes_hours_summary(self):
        self.teacher.resource_calendar_id = self.framework
        self.teacher.resource_calendar_id.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
            },
            {
                'dayofweek': '0', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
                'non_teaching': self.non_teaching_g.id, 'name': 'G: Guard',
            },
        ])

        content, _content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_working_schedule', [self.teacher.id])

        self.assertIn(b'Weekly teaching hours', content)
        self.assertIn(b'Other fixed-schedule hours', content)
        self.assertIn(b'Overall total', content)

    def test_get_report_role_lines_tutor_shows_tutored_group(self):
        role_tutor = self.env.ref('ems.role_tutor')
        self.teacher.write({'role_ids': [(4, role_tutor.id)], 'tutorship_ids': [(4, self.group.id)]})

        lines = self.teacher.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(self.group.name, lines[0])

    def test_get_report_role_lines_dchieff_shows_department(self):
        department = self.env['hr.department'].create({
            'name': 'Test Department (Working Schedule)', 'manager_id': self.teacher.id,
        })

        lines = self.teacher.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(department.name, lines[0])

    def test_get_report_role_lines_plain_role_has_no_suffix(self):
        role_secretary = self.env.ref('ems.role_secretary')
        self.teacher.with_context(ems_syncing_roles=True).write({'role_ids': [(4, role_secretary.id)]})

        lines = self.teacher.get_report_role_lines()

        self.assertEqual(lines, [role_secretary.name])

    def test_get_report_role_lines_no_roles_returns_empty(self):
        self.assertEqual(self.teacher.get_report_role_lines(), [])

    def test_report_working_schedule_header_shows_department_and_roles(self):
        role_tutor = self.env.ref('ems.role_tutor')
        department = self.env['hr.department'].create({'name': 'Test Department Header (Working Schedule)'})
        self.teacher.write({
            'role_ids': [(4, role_tutor.id)], 'tutorship_ids': [(4, self.group.id)], 'department_id': department.id,
        })
        self.teacher.resource_calendar_id = self.framework
        # NOTE: create() without inline attendance_ids auto-fills from the company's own calendar
        # (see working_schedule.py's module docstring) — apply_schedule_changes() always unlinks
        # weekday rows first, which is what clears that contamination before we render.
        self.teacher.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TWSL: TWSL',
        }])

        content, _content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_working_schedule', [self.teacher.id])

        self.assertIn(department.name.encode(), content)
        self.assertIn(self.group.name.encode(), content)
        self.assertNotIn(b'ws-employee-title">Working Schedule', content)

    def test_get_report_label_translates_non_teaching_reason(self):
        schedule = self.env['resource.calendar'].create({'name': 'Test Report Label (Working Schedule)'})
        schedule.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_g.id, 'name': 'G: Guard',
        }])
        attendance = schedule.attendance_ids

        self.assertEqual(attendance.with_context(lang='en_US').get_report_label(), 'Guard')
        self.assertEqual(attendance.with_context(lang='ca_ES').get_report_label(), 'Guàrdia')

    def test_report_working_schedule_translates_non_teaching_reason(self):
        self.teacher.resource_calendar_id = self.framework
        self.teacher.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.non_teaching_g.id, 'name': 'G: Guard',
        }])

        content, _content_type = self.env['ir.actions.report'].with_context(lang='ca_ES')._render_qweb_pdf(
            'ems.report_working_schedule', [self.teacher.id]
        )

        self.assertIn('Guàrdia'.encode(), content)

    def test_teacher_cannot_write_schedule_attendance(self):
        calendar = self.env['resource.calendar'].create({'name': 'Test ACL Teacher (Working Schedule)'})
        with self.assertRaises(AccessError):
            self.env['resource.calendar.attendance'].with_user(self.teacher_user).create({
                'calendar_id': calendar.id, 'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            })

    def test_head_of_department_can_write_schedule_attendance(self):
        calendar = self.env['resource.calendar'].create({'name': 'Test ACL HoD (Working Schedule)'})
        attendance = self.env['resource.calendar.attendance'].with_user(self.head_of_department_user).create({
            'calendar_id': calendar.id, 'name': 'Test', 'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
        })
        self.assertTrue(attendance.id)

    def test_can_edit_schedule_reflects_role(self):
        # NOTE: 'can_edit_schedule' is a non-stored compute — the transaction-level cache keys by
        # (field, record), not by the acting user, so switching user on the same record within one
        # test needs an explicit invalidation or the second read returns the first user's cached value.
        teacher_view = self.teacher.with_user(self.teacher_user)
        self.assertFalse(teacher_view.can_edit_schedule)

        self.teacher.invalidate_recordset(['can_edit_schedule'])
        hod_view = self.teacher.with_user(self.head_of_department_user)
        self.assertTrue(hod_view.can_edit_schedule)
