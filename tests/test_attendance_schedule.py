# -*- coding: utf-8 -*-

from datetime import date

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestAttendanceScheduleAccess(TransactionCase):
    """Focused regression coverage for the ir.rule fix in security/rules/attendance.xml:
    a teacher who is session_teacher_id/template_teacher_ids on a session built from a
    schedule (e.g. covering a guard-duty/substitution session) must be able to read that
    schedule even when they are not one of the schedule's own template.teacher_ids —
    otherwise the session's own form (which shows attendance_schedule_id) raises an
    AccessError, even though the session itself is readable. This is not a full DTON pass
    on ems.attendance_schedule (no dedicated test file existed before); it covers only the
    access-rule behaviour touched by this fix."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_academic_admin = cls.env.ref('ems.group_academic_admin')

        cls.level, cls.study = create_level_study(cls, 'TASC', level={'name': 'Test Level (Attendance Schedule)'}, study={
            'code': 'TASC001', 'name': 'Test Study (Attendance Schedule)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TASC001', 'acronym': 'TASC', 'name': 'Test Subject (Attendance Schedule)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group_record = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TASC', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'name': 'Test Group (Attendance Schedule)',
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TASC-A', 'name': 'Test Space (Attendance Schedule)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })

        cls.owner_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Owner Teacher (Attendance Schedule)', 'login': 'test_owner_teacher_asc',
            'email': 'test_owner_teacher_asc@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.owner_employee = cls.env['hr.employee'].create({
            'name': 'Test Owner Teacher Employee (Attendance Schedule)', 'employee_type': 'teacher',
            'user_id': cls.owner_user.id,
        })

        cls.substitute_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Substitute Teacher (Attendance Schedule)', 'login': 'test_substitute_teacher_asc',
            'email': 'test_substitute_teacher_asc@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.substitute_employee = cls.env['hr.employee'].create({
            'name': 'Test Substitute Teacher Employee (Attendance Schedule)', 'employee_type': 'teacher',
            'user_id': cls.substitute_user.id,
        })

        cls.unrelated_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Unrelated Teacher (Attendance Schedule)', 'login': 'test_unrelated_teacher_asc',
            'email': 'test_unrelated_teacher_asc@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })

        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Attendance Schedule)', 'login': 'test_admin_asc',
            'email': 'test_admin_asc@example.com',
            'groups_id': [(4, cls.group_academic_admin.id), (4, cls.env.ref('base.group_user').id)],
        })

        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.owner_employee.id])], 'study_ids': [(6, 0, [cls.study.id])],
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group_record.id])], 'space_id': cls.space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
        })
        # A session covered by the substitute, not the template's own teacher — the scenario
        # that used to raise an AccessError when opening the session's own form.
        cls.substitute_session = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': date.today(),
            'mode': 'guard', 'session_teacher_id': cls.substitute_employee.id,
        })

    def test_template_teacher_can_read_schedule(self):
        schedule = self.env['ems.attendance_schedule'].with_user(self.owner_user).search(
            [('id', '=', self.schedule.id)]
        )
        self.assertIn(self.schedule, schedule)

    def test_unrelated_teacher_cannot_read_schedule(self):
        schedule = self.env['ems.attendance_schedule'].with_user(self.unrelated_user).search(
            [('id', '=', self.schedule.id)]
        )
        self.assertNotIn(self.schedule, schedule)

    def test_substitute_teacher_can_read_schedule_via_own_session(self):
        schedule = self.env['ems.attendance_schedule'].with_user(self.substitute_user).search(
            [('id', '=', self.schedule.id)]
        )
        self.assertIn(self.schedule, schedule)

    def test_substitute_teacher_can_read_the_field_on_the_session_form(self):
        session = self.env['ems.attendance_session_header'].with_user(self.substitute_user).browse(
            self.substitute_session.id
        )
        # Reading attendance_schedule_id used to raise AccessError on ems.attendance_schedule.
        self.assertEqual(session.attendance_schedule_id, self.schedule)

    def test_substitute_teacher_cannot_write_schedule(self):
        schedule = self.schedule.with_user(self.substitute_user)
        with self.assertRaises(AccessError):
            schedule.write({'notes': 'Attempted edit.'})

    def test_admin_reads_all_schedules(self):
        schedule = self.env['ems.attendance_schedule'].with_user(self.admin_user).search(
            [('id', '=', self.schedule.id)]
        )
        self.assertIn(self.schedule, schedule)


class TestAttendanceScheduleLogic(TransactionCase):
    """The model's own business logic: computed name/time_range/start_date/end_date,
    check_overlap's co-teaching exception, and the unlink guard. See
    docs/en/developers/attendance/attendance_schedule.md; the sync pipeline that
    creates/archives these schedules from a teacher's weekly timetable is documented
    (and separately tested) in attendance_template.md/tests/test_attendance_template.py
    — not duplicated here."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TASL', level={'name': 'Test Level (Attendance Schedule Logic)'}, study={
            'code': 'TASL001', 'name': 'Test Study (Attendance Schedule Logic)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TASL001', 'acronym': 'TASL', 'name': 'Test Subject (Attendance Schedule Logic)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.other_subject = cls.env['ems.subject'].create({
            'code': 'TASL002', 'acronym': 'TASL2', 'name': 'Other Subject (Attendance Schedule Logic)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group1 = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TASLA', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.group2 = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TASLB', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TASL-A', 'name': 'Test Space (Attendance Schedule Logic)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.other_space = cls.env['ems.space'].create({
            'code': 'TASL-B', 'name': 'Other Space (Attendance Schedule Logic)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.teacher1 = cls.env['hr.employee'].create({
            'name': 'Test Teacher 1 (Attendance Schedule Logic)', 'employee_type': 'teacher'})
        cls.teacher2 = cls.env['hr.employee'].create({
            'name': 'Test Teacher 2 (Attendance Schedule Logic)', 'employee_type': 'teacher'})

    def _template(self, teacher, subject=None, groups=None, space=None):
        return self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, teacher.ids)], 'study_ids': [(6, 0, [self.study.id])],
            'subject_id': (subject or self.subject).id,
            'group_ids': [(6, 0, (groups or self.group1).ids)],
            'space_id': (space or self.space).id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })

    # --- computed fields ---------------------------------------------------------------

    def test_compute_name_and_time_range(self):
        template = self._template(self.teacher1)
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '2',
            'start_time': 9.5, 'end_time': 11.0, 'space_id': self.space.id,
        })
        self.assertIn('Wednesday', schedule.name)
        self.assertIn(template.display_name, schedule.name)
        self.assertEqual(schedule.time_range, '09:30 - 11:00')

    # --- find_schedule_lines_for_teaching ------------------------------------------------

    def test_find_schedule_lines_for_teaching_finds_the_matching_line(self):
        template = self._template(self.teacher1)
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })

        found = self.env['ems.attendance_schedule'].find_schedule_lines_for_teaching(
            self.teacher1, self.subject, self.group1, '1', 8.0, 9.0)

        self.assertEqual(found, schedule)

    def test_find_schedule_lines_for_teaching_filters_by_teacher(self):
        template = self._template(self.teacher1)
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })

        found = self.env['ems.attendance_schedule'].find_schedule_lines_for_teaching(
            self.teacher2, self.subject, self.group1, '1', 8.0, 9.0)

        self.assertFalse(found)

    def test_find_schedule_lines_for_teaching_filters_by_subject(self):
        template = self._template(self.teacher1)
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })

        found = self.env['ems.attendance_schedule'].find_schedule_lines_for_teaching(
            self.teacher1, self.other_subject, self.group1, '1', 8.0, 9.0)

        self.assertFalse(found)

    def test_find_schedule_lines_for_teaching_requires_time_overlap(self):
        template = self._template(self.teacher1)
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })

        found = self.env['ems.attendance_schedule'].find_schedule_lines_for_teaching(
            self.teacher1, self.subject, self.group1, '1', 9.0, 10.0)

        self.assertFalse(found)

    def test_find_schedule_lines_for_teaching_matches_on_any_group_overlap(self):
        template = self._template(self.teacher1, groups=self.group1 | self.group2)
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })

        # Only ONE of the template's two groups is passed - a real overlap, not an exact match.
        found = self.env['ems.attendance_schedule'].find_schedule_lines_for_teaching(
            self.teacher1, self.subject, self.group2, '1', 8.0, 9.0)

        self.assertEqual(found, schedule)

    def test_find_schedule_lines_for_teaching_matches_regardless_of_room(self):
        # The whole point of this lookup (2026-08-10, developer feedback): a teacher can freely
        # change the room while taking attendance (e.g. an unplanned workshop), so the calendar
        # block's own room can legitimately drift from the schedule line's authoritative one -
        # matching on room, as this lookup originally did, silently broke the very link it
        # exists to find.
        template = self._template(self.teacher1, space=self.space)
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.other_space.id,
        })

        found = self.env['ems.attendance_schedule'].find_schedule_lines_for_teaching(
            self.teacher1, self.subject, self.group1, '1', 8.0, 9.0)

        self.assertEqual(found, schedule)

    def test_find_schedule_lines_for_teaching_includes_an_inactive_leftover_line_with_active_test_false(self):
        # Developer feedback (2026-08-10): "si ya no es docente de esa materia, en ese grupo,
        # para ese dia y hora, ambos schedules deberian archivarse" - a stale leftover line
        # archived by an earlier edit, alongside a newer active one, can both genuinely match the
        # same (teacher, subject, group, weekday, time) - check_overlap forbids two ACTIVE lines
        # like this for the same teacher/time regardless of room, so the leftover must already be
        # inactive by the time a new one exists; the caller (with 'active_test=False', exactly
        # like '_apply_calendar_archival' already does) must still see both, not just the active
        # one, and let the caller decide what to do with each.
        template = self._template(self.teacher1)
        old_schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })
        old_schedule.action_archive()
        other_template = self._template(self.teacher1)
        new_schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': other_template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.other_space.id,
        })

        found = self.env['ems.attendance_schedule'].with_context(active_test=False).find_schedule_lines_for_teaching(
            self.teacher1, self.subject, self.group1, '1', 8.0, 9.0)

        self.assertEqual(found, old_schedule | new_schedule)

    def test_start_end_date_derived_from_template_dates_and_times(self):
        template = self._template(self.teacher1)
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })
        self.assertTrue(schedule.start_date)
        self.assertTrue(schedule.end_date)
        self.assertLess(schedule.start_date, schedule.end_date)

    # --- check_overlap -----------------------------------------------------------------

    def test_overlap_same_teacher_same_time_raises(self):
        template1 = self._template(self.teacher1, space=self.space)
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template1.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })
        template2 = self._template(self.teacher1, subject=self.other_subject, groups=self.group2, space=self.other_space)
        with self.assertRaises(ValidationError):
            self.env['ems.attendance_schedule'].create({
                'attendance_template_id': template2.id, 'weekday': '1',
                'start_time': 8.5, 'end_time': 9.5, 'space_id': self.other_space.id,
            })

    def test_overlap_same_space_different_teachers_raises(self):
        template1 = self._template(self.teacher1, space=self.space)
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template1.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })
        template2 = self._template(self.teacher2, subject=self.other_subject, groups=self.group2, space=self.space)
        with self.assertRaises(ValidationError):
            self.env['ems.attendance_schedule'].create({
                'attendance_template_id': template2.id, 'weekday': '1',
                'start_time': 8.5, 'end_time': 9.5, 'space_id': self.space.id,
            })

    def test_overlap_co_teaching_same_subject_shared_group_does_not_raise(self):
        """Same subject + shared group, different teacher, same room/time: a legitimate
        co-taught session, not a double-booking — check_overlap's exception via
        is_co_teaching_with()."""
        template1 = self._template(self.teacher1, subject=self.subject, groups=self.group1, space=self.space)
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template1.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })
        template2 = self._template(self.teacher2, subject=self.subject, groups=self.group1, space=self.space)
        schedule2 = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template2.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })
        self.assertTrue(schedule2.id)

    def test_overlap_different_weekday_does_not_raise(self):
        template1 = self._template(self.teacher1, space=self.space)
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template1.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })
        template2 = self._template(self.teacher1, subject=self.other_subject, groups=self.group2, space=self.other_space)
        schedule2 = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template2.id, 'weekday': '2',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.other_space.id,
        })
        self.assertTrue(schedule2.id)

    # --- unlink guard --------------------------------------------------------------------

    def test_unlink_blocked_when_sessions_exist(self):
        template = self._template(self.teacher1)
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })
        self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date.today(),
            'mode': 'guard', 'session_teacher_id': self.teacher1.id,
        })
        with self.assertRaises(ValidationError):
            schedule.unlink()

    def test_unlink_allowed_without_sessions(self):
        template = self._template(self.teacher1)
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': self.space.id,
        })
        schedule.unlink()
        self.assertFalse(schedule.exists())
