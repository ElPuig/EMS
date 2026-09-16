import ast
from datetime import date, datetime

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study, mock_outgoing_email, next_student_id


class TestAttendanceJustification(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Attendance Justification)',
            'employee_type': 'teacher',
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Test Student (Attendance Justification)',
            'contact_type': 'student', 'student_id': next_student_id(),
        })

    def test_overlapping_justification_raises(self):
        self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id,
            'student_id': self.student.id,
            'start_date': datetime(2026, 1, 5, 9, 0),
            'end_date': datetime(2026, 1, 5, 11, 0),
        })

        with self.assertRaises(ValidationError):
            self.env['ems.attendance_justification'].create({
                'teacher_id': self.teacher.id,
                'student_id': self.student.id,
                'start_date': datetime(2026, 1, 5, 10, 0),
                'end_date': datetime(2026, 1, 5, 12, 0),
            })

    def test_non_overlapping_justification_allowed(self):
        self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id,
            'student_id': self.student.id,
            'start_date': datetime(2026, 1, 5, 9, 0),
            'end_date': datetime(2026, 1, 5, 11, 0),
        })

        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id,
            'student_id': self.student.id,
            'start_date': datetime(2026, 1, 5, 11, 0),
            'end_date': datetime(2026, 1, 5, 13, 0),
        })
        self.assertTrue(justification.id)

    def test_start_after_end_raises(self):
        with self.assertRaises(ValidationError):
            self.env['ems.attendance_justification'].create({
                'teacher_id': self.teacher.id,
                'student_id': self.student.id,
                'start_date': datetime(2026, 1, 5, 12, 0),
                'end_date': datetime(2026, 1, 5, 9, 0),
            })

    def test_compute_display_name(self):
        # start_date/end_date are stored as naive UTC and rendered in local
        # time (ems.datetime_utils.utc_datetime_to_local), so the displayed
        # clock digits depend on server timezone offset — assert on format/
        # structure, not hardcoded hours.
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id,
            'student_id': self.student.id,
            'start_date': datetime(2026, 1, 5, 9, 0),
            'end_date': datetime(2026, 1, 5, 11, 0),
        })
        self.assertRegex(
            justification.display_name,
            r'^.+ \(from \d{2}:\d{2} to \d{2}:\d{2}\)$',
        )
        self.assertIn(self.student.display_name, justification.display_name)

    def test_display_name_false_when_dates_missing(self):
        justification = self.env['ems.attendance_justification'].new({
            'teacher_id': self.teacher.id, 'student_id': self.student.id,
        })
        justification._compute_display_name()
        self.assertFalse(justification.display_name)

    def test_student_id_domain_is_valid_syntax(self):
        """Regression test: student_id's domain string was missing its closing
        ']', a syntax error that only ever surfaced when the browser tried to
        evaluate it for the Many2one picker (domains aren't enforced server-side
        by the ORM, so no TransactionCase test could have caught this before —
        only real UI usage or a syntax check would). Fixed in this DTON pass."""
        field = self.env['ems.attendance_justification']._fields['student_id']
        # Must parse as a valid Python literal without raising.
        ast.literal_eval(field.domain)


class TestAttendanceJustificationPermissionsAndSync(TransactionCase):
    """create()/write()/unlink()'s tutor-only permission gates and their sync
    with ems.attendance_session_line (auto-justify on create, add/remove on
    write, un-justify on unlink)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Marking a line as a miss queues family notifications.
        mock_outgoing_email(cls)
        cls.level, cls.study = create_level_study(cls, 'TAJ', study={
            'name': 'Test Study (Attendance Justification)', 'date': date.today(),
        }, level={'name': 'Test Level (Attendance Justification)'})
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TAJ001', 'acronym': 'TAJ', 'name': 'Test Subject (Attendance Justification)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TAJ-A', 'name': 'Test Space (Attendance Justification)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Test Tutor (Attendance Justification)', 'employee_type': 'teacher',
        })
        cls.tutor_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Tutor User (Attendance Justification)', 'login': 'test_tutor_taj',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.tutor_employee.user_id = cls.tutor_user.id
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TAJ', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.tutor_employee.id,
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Test Student (Attendance Justification Perms)', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
        })
        cls.other_teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Other Teacher User (Attendance Justification)', 'login': 'test_other_teacher_taj',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.other_teacher = cls.env['hr.employee'].create({
            'name': 'Other Teacher (Attendance Justification)', 'employee_type': 'teacher',
            'user_id': cls.other_teacher_user.id,
        })

        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.tutor_employee.id])], 'study_ids': [(6, 0, [cls.study.id])],
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': str(date.today().weekday()),
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
            'student_ids': [(6, 0, [cls.student.id])],
        })
        cls.session = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': cls.tutor_employee.id,
        })

    def _line(self):
        return self.session.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student)

    def _today_range(self):
        return {
            'start_date': datetime.combine(date.today(), datetime.min.time()),
            'end_date': datetime.combine(date.today(), datetime.max.time()),
        }

    def _other_teacher_schedule(self):
        """A second slot for the same student, taught by a teacher who is neither
        the student's tutor nor any justification's author."""
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.other_teacher.id])], 'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject.id, 'group_ids': [(6, 0, [self.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        return self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': str(date.today().weekday()),
            'start_time': 10.0, 'end_time': 11.0, 'space_id': self.space.id,
            'student_ids': [(6, 0, [self.student.id])],
        })

    def _other_teacher_miss_line(self):
        """The student's line, marked as a miss, in a session the tutor cannot read."""
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self._other_teacher_schedule().id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.other_teacher.id,
        })
        line = session.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student)
        line.status_id = self.env.ref('ems.attendance_status_miss')
        return line

    def test_non_tutor_teacher_cannot_create_justification(self):
        # default_get's admin/tutor guard fires before create()'s own
        # _check_permissions check, and raises UserError, not ValidationError.
        with self.assertRaises(UserError):
            self.env['ems.attendance_justification'].with_user(self.other_teacher_user).create({
                'teacher_id': self.other_teacher.id, 'student_id': self.student.id,
                **self._today_range(),
            })

    def test_tutor_can_create_justification(self):
        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).create({
            'teacher_id': self.tutor_employee.id, 'student_id': self.student.id,
            **self._today_range(),
        })
        self.assertTrue(justification.id)

    def test_create_auto_justifies_linked_miss_lines(self):
        line = self._line()
        line.status_id = self.env.ref('ems.attendance_status_miss')

        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.tutor_employee.id, 'student_id': self.student.id,
            **self._today_range(),
            'attendance_session_line_ids': [(6, 0, [line.id])],
        })
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_justified'))
        self.assertEqual(line.attendance_justification_id, justification)

    def test_non_tutor_cannot_change_dates(self):
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.tutor_employee.id, 'student_id': self.student.id,
            **self._today_range(),
        })
        with self.assertRaises(UserError):
            justification.with_user(self.other_teacher_user).write({
                'end_date': datetime(2026, 1, 10, 23, 59),
            })

    def test_unlink_requires_tutor_permission(self):
        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).create({
            'teacher_id': self.tutor_employee.id, 'student_id': self.student.id,
            **self._today_range(),
        })
        with self.assertRaises(UserError):
            justification.with_user(self.other_teacher_user).unlink()

    def test_unlink_reverts_justified_lines_to_miss(self):
        line = self._line()
        line.status_id = self.env.ref('ems.attendance_status_miss')
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.tutor_employee.id, 'student_id': self.student.id,
            **self._today_range(),
            'attendance_session_line_ids': [(6, 0, [line.id])],
        })
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_justified'))
        justification.unlink()
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_miss'))

    def test_compute_session_teacher_ids_includes_template_and_session_teacher(self):
        line = self._line()
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.tutor_employee.id, 'student_id': self.student.id,
            **self._today_range(),
            'attendance_session_line_ids': [(6, 0, [line.id])],
        })
        self.assertIn(self.tutor_employee, justification.session_teacher_ids)

    def test_other_teacher_can_start_session_overlapping_tutor_justification(self):
        """Regression (#432): a teacher starting a session that overlaps a
        justification created by a different teacher got an AccessError and the
        session was never created, blocking roll-call for that slot entirely.

        The back-link that registers the session's teachers on the justification
        (and therefore grants them read access through
        rule_attendance_justification_teacher_own_read) was itself written through
        write(), whose override reads attendance_session_line_ids first — a read
        the teacher is not yet allowed to perform."""
        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).create({
            'teacher_id': self.tutor_employee.id, 'student_id': self.student.id,
            **self._today_range(),
        })
        schedule = self._other_teacher_schedule()

        # The justification is normally created in an earlier request, so its
        # attendance_session_line_ids is a cold read when the session is started.
        # Without this the value is still cached from the create() above, no fetch
        # happens, and the record rules are never enforced — masking the bug.
        self.env.invalidate_all()

        result = self.env['ems.attendance_session_header'].with_user(
            self.other_teacher_user).create_scheduled_session(date.today(), schedule.id)
        session = self.env['ems.attendance_session_header'].browse(result['id'])
        self.assertTrue(session.exists())

        self.assertIn(self.other_teacher, justification.session_teacher_ids)

        # What the roll-call screen itself does right after creating the session.
        line = session.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student)
        self.assertEqual(line.attendance_prevision_id, justification)
        line.with_user(self.other_teacher_user).read(['attendance_prevision_id'])

    def test_tutor_reads_affected_sessions_taught_by_other_teachers(self):
        """Regression (#469): once another teacher's session line was linked to a
        justification, its tutor could no longer open it - the affected-sessions list
        shows each line's display_name, built from a session header the teacher
        record rules only let its own teachers read."""
        line = self._other_teacher_miss_line()
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.tutor_employee.id, 'student_id': self.student.id,
            **self._today_range(),
            'attendance_session_line_ids': [(6, 0, [line.id])],
        })
        self.env.invalidate_all()

        names = justification.with_user(self.tutor_user).attendance_session_line_ids.read(['display_name'])
        self.assertIn(self.space.name, names[0]['display_name'])

    def test_tutor_onchange_finds_miss_lines_taught_by_other_teachers(self):
        """Regression (#469): the header record rules also filtered the onchange's own
        search, so a justification for past absences silently left every other
        teacher's miss unjustified."""
        line = self._other_teacher_miss_line()
        self.env.invalidate_all()

        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).new({
            'teacher_id': self.tutor_employee.id, 'student_id': self.student.id,
            **self._today_range(),
        })
        justification._onchange_attendance_session_line_ids()
        self.assertIn(line.id, justification.attendance_session_line_ids.ids)

    def test_tutor_create_justifies_miss_lines_taught_by_other_teachers(self):
        line = self._other_teacher_miss_line()
        self.env.invalidate_all()

        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).create({
            'teacher_id': self.tutor_employee.id, 'student_id': self.student.id,
            **self._today_range(),
            'attendance_session_line_ids': [(6, 0, [line.id])],
        })
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_justified'))
        self.assertEqual(line.attendance_justification_id, justification)

    def test_non_tutor_onchange_does_not_see_unreadable_sessions(self):
        """The onchange only searches past the record rules for the student's own tutor
        (or an admin): any other teacher still gets just the sessions they can read."""
        self._line().status_id = self.env.ref('ems.attendance_status_miss')
        self.env.invalidate_all()

        justification = self.env['ems.attendance_justification'].with_user(self.other_teacher_user).new({
            'teacher_id': self.other_teacher.id, 'student_id': self.student.id,
            **self._today_range(),
        })
        justification._onchange_attendance_session_line_ids()
        self.assertFalse(justification.attendance_session_line_ids)
