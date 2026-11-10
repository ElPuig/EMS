import ast
import importlib.util
import os
import re
from datetime import date, datetime, timedelta

from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase

from .common import create_level_study, create_role_user, shift_ems_clock, mock_outgoing_email, next_student_id


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
            'student_ids': [(6, 0, self.student.ids)],
            'start_date': datetime(2026, 1, 5, 9, 0),
            'end_date': datetime(2026, 1, 5, 11, 0),
        })

        # The error names the student in conflict (a justification can list many).
        with self.assertRaisesRegex(ValidationError, re.escape(self.student.name)):
            self.env['ems.attendance_justification'].create({
                'teacher_id': self.teacher.id,
                'student_ids': [(6, 0, self.student.ids)],
                'start_date': datetime(2026, 1, 5, 10, 0),
                'end_date': datetime(2026, 1, 5, 12, 0),
            })

    def test_non_overlapping_justification_allowed(self):
        self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id,
            'student_ids': [(6, 0, self.student.ids)],
            'start_date': datetime(2026, 1, 5, 9, 0),
            'end_date': datetime(2026, 1, 5, 11, 0),
        })

        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id,
            'student_ids': [(6, 0, self.student.ids)],
            'start_date': datetime(2026, 1, 5, 11, 0),
            'end_date': datetime(2026, 1, 5, 13, 0),
        })
        self.assertTrue(justification.id)

    def test_start_after_end_raises(self):
        with self.assertRaises(ValidationError):
            self.env['ems.attendance_justification'].create({
                'teacher_id': self.teacher.id,
                'student_ids': [(6, 0, self.student.ids)],
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
            'student_ids': [(6, 0, self.student.ids)],
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
            'teacher_id': self.teacher.id, 'student_ids': [(6, 0, self.student.ids)],
        })
        justification._compute_display_name()
        self.assertFalse(justification.display_name)

    def test_student_ids_domain_is_valid_syntax(self):
        """Regression test: the student field's domain string was missing its closing
        ']', a syntax error that only ever surfaced when the browser tried to
        evaluate it for the Many2one picker (domains aren't enforced server-side
        by the ORM, so no TransactionCase test could have caught this before —
        only real UI usage or a syntax check would). Fixed in this DTON pass."""
        field = self.env['ems.attendance_justification']._fields['student_ids']
        # Must parse as a valid Python literal without raising.
        ast.literal_eval(field.domain)


class TestAttendanceJustificationPermissionsAndSync(TransactionCase):
    """create()/write()/unlink()'s tutor-only permission gates and their sync
    with ems.attendance_session_line (auto-justify on create, add/remove on
    write, un-justify on unlink)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = shift_ems_clock(cls).date()
        # Marking a line as a miss queues family notifications.
        mock_outgoing_email(cls)
        cls.level, cls.study = create_level_study(cls, 'TAJ', study={
            'name': 'Test Study (Attendance Justification)', 'date': cls.today,
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
            'name': 'Test Tutor User (Attendance Justification)', 'login': 'test_tutor_taj', 'lang': 'en_US',
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
            'attendance_template_id': cls.template.id, 'weekday': str(cls.today.weekday()),
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
            'student_ids': [(6, 0, [cls.student.id])],
        })
        cls.session = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': cls.today,
            'mode': 'scheduled', 'session_teacher_id': cls.tutor_employee.id,
        })

    def _line(self):
        return self.session.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student)

    def _today_range(self):
        return {
            'start_date': datetime.combine(self.today, datetime.min.time()),
            'end_date': datetime.combine(self.today, datetime.max.time()),
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
            'attendance_template_id': template.id, 'weekday': str(self.today.weekday()),
            'start_time': 10.0, 'end_time': 11.0, 'space_id': self.space.id,
            'student_ids': [(6, 0, [self.student.id])],
        })

    def _other_teacher_miss_line(self):
        """The student's line, marked as a miss, in a session the tutor cannot read."""
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self._other_teacher_schedule().id, 'date': self.today,
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
                'teacher_id': self.other_teacher.id, 'student_ids': [(6, 0, self.student.ids)],
                **self._today_range(),
            })

    def test_create_auto_justifies_linked_miss_lines(self):
        line = self._line()
        line.status_id = self.env.ref('ems.attendance_status_miss')

        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
            'attendance_session_line_ids': [(6, 0, [line.id])],
        })
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_justified'))
        self.assertEqual(line.attendance_justification_id, justification)

    def test_non_tutor_cannot_change_dates(self):
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
        })
        with self.assertRaises(UserError):
            justification.with_user(self.other_teacher_user).write({
                'end_date': datetime(2026, 1, 10, 23, 59),
            })

    def test_unlink_requires_tutor_permission(self):
        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
        })
        with self.assertRaises(UserError):
            justification.with_user(self.other_teacher_user).unlink()

    def test_unlink_reverts_justified_lines_to_miss(self):
        line = self._line()
        line.status_id = self.env.ref('ems.attendance_status_miss')
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
            'attendance_session_line_ids': [(6, 0, [line.id])],
        })
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_justified'))
        justification.unlink()
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_miss'))

    def _justify_severe_delay(self):
        """The student's line marked as a severe delay, then justified (issue #578)."""
        line = self._line()
        line.status_id = self.env.ref('ems.attendance_status_delayed_severe')
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
            'attendance_session_line_ids': [(6, 0, [line.id])],
        })
        return line, justification

    def test_create_justifies_severe_delay_as_mild_delay(self):
        """A severe delay counts as an absence: justifying it turns it into a mild delay, not a
        justified miss, linked to the justification (which locks it in the roll-call) and noted."""
        line, justification = self._justify_severe_delay()
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_delayed'))
        self.assertEqual(line.attendance_justification_id, justification)
        self.assertIn(self.tutor_employee.display_name, line.notes)

    def test_onchange_finds_severe_delay_lines(self):
        line = self._line()
        line.status_id = self.env.ref('ems.attendance_status_delayed_severe')
        justification = self.env['ems.attendance_justification'].new({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
        })
        justification._onchange_attendance_session_line_ids()
        self.assertIn(line.id, justification.attendance_session_line_ids.ids)

    def test_onchange_skips_unjustified_mild_delay_lines(self):
        line = self._line()
        line.status_id = self.env.ref('ems.attendance_status_delayed')
        justification = self.env['ems.attendance_justification'].new({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
        })
        justification._onchange_attendance_session_line_ids()
        self.assertNotIn(line.id, justification.attendance_session_line_ids.ids)

    def test_unlink_reverts_justified_severe_delay(self):
        line, justification = self._justify_severe_delay()
        justification.unlink()
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_delayed_severe'))
        self.assertFalse(line.attendance_justification_id)

    def test_date_change_reverts_dropped_severe_delay(self):
        # The form's onchange sends the new dates together with the lines they now cover.
        line, justification = self._justify_severe_delay()
        tomorrow = self.today + timedelta(days=1)
        justification.write({
            'start_date': datetime.combine(tomorrow, datetime.min.time()),
            'end_date': datetime.combine(tomorrow, datetime.max.time()),
            'attendance_session_line_ids': [(6, 0, [])],
        })
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_delayed_severe'))

    def test_compute_session_teacher_ids_includes_template_and_session_teacher(self):
        line = self._line()
        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
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
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
        })
        schedule = self._other_teacher_schedule()

        # The justification is normally created in an earlier request, so its
        # attendance_session_line_ids is a cold read when the session is started.
        # Without this the value is still cached from the create() above, no fetch
        # happens, and the record rules are never enforced — masking the bug.
        self.env.invalidate_all()

        result = self.env['ems.attendance_session_header'].with_user(
            self.other_teacher_user).create_scheduled_session(self.today, schedule.id)
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
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
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
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
        })
        justification._onchange_attendance_session_line_ids()
        self.assertIn(line.id, justification.attendance_session_line_ids.ids)

    def test_tutor_create_justifies_miss_lines_taught_by_other_teachers(self):
        line = self._other_teacher_miss_line()
        self.env.invalidate_all()

        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
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
            'teacher_id': self.other_teacher.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
        })
        justification._onchange_attendance_session_line_ids()
        self.assertFalse(justification.attendance_session_line_ids)

    def _attachment_command(self, name):
        return (0, 0, {'name': name, 'raw': b'justificant', 'res_model': 'ems.attendance_justification'})

    def test_head_of_studies_sees_attachment_uploaded_by_tutor(self):
        """Regression (#553): the form's attachments list creates each file without a res_id,
        and Odoo only lets the uploader (or a system admin) read an unlinked attachment, so
        Head of Studies saw an empty 'Attached files' tab."""
        hos_user = create_role_user(self, 'head_of_studies', 'test_hos_taj')
        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
            'attachment_ids': [self._attachment_command('justificant.pdf')],
        })
        self.env.invalidate_all()

        names = justification.with_user(hos_user).attachment_ids.mapped('name')
        self.assertEqual(names, ['justificant.pdf'])

    def test_attachment_added_later_is_linked_to_justification(self):
        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
        })
        justification.with_user(self.tutor_user).write({
            'attachment_ids': [self._attachment_command('justificant.pdf')],
        })

        self.assertEqual(justification.attachment_ids.res_id, justification.id)
        self.assertEqual(justification.attachment_ids.res_model, 'ems.attendance_justification')

    def test_attachment_removed_by_tutor_is_deleted(self):
        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            **self._today_range(),
            'attachment_ids': [self._attachment_command('justificant.pdf')],
        })
        attachment = justification.attachment_ids

        justification.with_user(self.tutor_user).write({'attachment_ids': [(3, attachment.id)]})
        self.assertFalse(attachment.exists())

    # Issue #795: one justification shared by several students (a strike, a competition).

    def _group_mate_with_miss(self):
        """A second student of the tutor's group, with a miss in a session taught by another
        teacher (whose header the tutor cannot read)."""
        mate = self.env['res.partner'].create({
            'name': 'Test Group Mate (Attendance Justification)', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': self.group.id,
        })
        schedule = self._other_teacher_schedule()
        schedule.student_ids = [(6, 0, [mate.id])]
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': self.today,
            'mode': 'scheduled', 'session_teacher_id': self.other_teacher.id,
        })
        line = session.attendance_session_line_ids.filtered(lambda l: l.student_id == mate)
        line.status_id = self.env.ref('ems.attendance_status_miss')
        return mate, line

    def _other_tutor_student(self):
        other_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TAJ2', 'level_id': self.level.id, 'study_id': self.study.id,
            'tutor_id': self.other_teacher.id,
        })
        return self.env['res.partner'].create({
            'name': 'Test Other Tutor Student (Attendance Justification)', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': other_group.id,
        })

    def _shared_justification(self, students, user=None):
        Justification = self.env['ems.attendance_justification']
        return (Justification.with_user(user) if user else Justification).create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, students.ids)],
            **self._today_range(),
        })

    def test_one_justification_justifies_every_student(self):
        own_line = self._line()
        own_line.status_id = self.env.ref('ems.attendance_status_miss')
        mate, mate_line = self._group_mate_with_miss()

        justification = self._shared_justification(self.student | mate, self.tutor_user)

        justified = self.env.ref('ems.attendance_status_justified')
        self.assertEqual(own_line.status_id, justified)
        self.assertEqual(mate_line.status_id, justified)
        self.assertEqual((own_line | mate_line).attendance_justification_id, justification)
        self.assertEqual(justification.student_summary, '2 students')
        self.assertIn('2 students', justification.display_name)

    def test_removing_a_student_unjustifies_only_their_lines(self):
        own_line = self._line()
        own_line.status_id = self.env.ref('ems.attendance_status_miss')
        mate, mate_line = self._group_mate_with_miss()
        justification = self._shared_justification(self.student | mate)

        justification.with_user(self.tutor_user).write({'student_ids': [(3, mate.id)]})

        self.assertEqual(mate_line.status_id, self.env.ref('ems.attendance_status_miss'))
        self.assertFalse(mate_line.attendance_justification_id)
        self.assertEqual(own_line.status_id, self.env.ref('ems.attendance_status_justified'))
        self.assertEqual(justification.attendance_session_line_ids, own_line)

    def test_adding_a_student_justifies_their_lines(self):
        mate, mate_line = self._group_mate_with_miss()
        justification = self._shared_justification(self.student)

        justification.with_user(self.tutor_user).write({'student_ids': [(4, mate.id)]})

        self.assertEqual(mate_line.status_id, self.env.ref('ems.attendance_status_justified'))
        self.assertEqual(mate_line.attendance_justification_id, justification)

    def test_add_groups_adds_the_group_students_but_the_overlapping_ones(self):
        mate, __ = self._group_mate_with_miss()
        self._shared_justification(self.student)
        with Form(self.env['ems.attendance_justification'].with_user(self.tutor_user)) as form:
            form.start_date, form.end_date = self._today_range().values()
            form.mode = 'group'
            form.add_group_ids.add(self.group)
            self.assertFalse(form.add_group_ids)
        self.assertEqual(form.record.student_ids, mate)

    def test_student_mode_justifies_the_one_student_picked(self):
        # Issue #808: the default mode picks a single student directly.
        mate, __ = self._group_mate_with_miss()
        with Form(self.env['ems.attendance_justification'].with_user(self.tutor_user)) as form:
            self.assertEqual(form.mode, 'student')
            form.start_date, form.end_date = self._today_range().values()
            form.student_id = self.student
        self.assertEqual(form.record.student_ids, self.student)
        self.assertNotIn(mate, form.record.student_ids)

    def test_switching_to_student_mode_keeps_one_student(self):
        mate, __ = self._group_mate_with_miss()
        justification = self._shared_justification(self.student | mate, self.tutor_user)
        with Form(justification.with_user(self.tutor_user)) as form:
            self.assertEqual(form.mode, 'group')
            form.mode = 'student'
        self.assertEqual(len(justification.student_ids), 1)

    def test_overlap_warning_lists_students_already_justified(self):
        mate, __ = self._group_mate_with_miss()
        self._shared_justification(self.student)
        justification = self.env['ems.attendance_justification'].new({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, (self.student | mate).ids)],
            **self._today_range(),
        })
        self.assertEqual(justification.overlap_student_ids._origin, self.student)

    def test_tutor_cannot_justify_students_of_another_tutor(self):
        with self.assertRaises(UserError):
            self._shared_justification(self.student | self._other_tutor_student(), self.tutor_user)

    def test_tutor_cannot_change_or_remove_a_justification_with_other_students(self):
        # Shared by students of two tutors: its comment and files belong to all of them.
        justification = self._shared_justification(self.student | self._other_tutor_student())
        with self.assertRaises(UserError):
            justification.with_user(self.tutor_user).write({'reason_id': self._reason('activity').id})
        with self.assertRaises(UserError):
            justification.with_user(self.tutor_user).unlink()
        # Reading it is enough with one student of theirs.
        justification.with_user(self.tutor_user).read(['reason_id'])

    def test_tutor_cannot_add_a_student_of_another_tutor(self):
        justification = self._shared_justification(self.student, self.tutor_user)
        with self.assertRaises(UserError):
            justification.with_user(self.tutor_user).write({'student_ids': [(4, self._other_tutor_student().id)]})

    def test_administrator_manages_a_justification_of_several_tutors(self):
        # The administrator is at the top of the permission pyramid, outside every tutor chain.
        admin = create_role_user(self, 'academic_admin', 'test_admin_taj')
        other = self._other_tutor_student()
        justification = self._shared_justification(self.student | other, admin)
        justification.with_user(admin).write({'student_ids': [(3, other.id)], 'notes': 'Revisat'})
        self.assertEqual(justification.student_ids, self.student)
        justification.with_user(admin).unlink()
        self.assertFalse(justification.exists())

    def _view_operations(self, user, view_type):
        arch = self.env['ems.attendance_justification'].with_user(user).get_view(view_type=view_type)['arch']
        node = etree.fromstring(arch)
        return {operation: node.get(operation) for operation in ('create', 'edit', 'delete')}

    def test_non_tutor_teacher_reads_justifications_without_new_edit_delete(self):
        # Only tutors justify: create()/write()/unlink() would refuse the rest anyway.
        for view_type in ('list', 'form'):
            self.assertEqual(self._view_operations(self.other_teacher_user, view_type),
                             {'create': '0', 'edit': '0', 'delete': '0'})
            self.assertNotIn('0', self._view_operations(self.tutor_user, view_type).values())

    def test_reasons_menu_only_for_administrators_and_heads_of_studies(self):
        menu = self.env.ref('ems.menu_attendance_justification_reasons')
        hos = create_role_user(self, 'head_of_studies', 'test_hos_reasons_taj')
        for user, expected in ((self.tutor_user, False), (self.other_teacher_user, False), (hos, True)):
            visible = self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()
            self.assertEqual(menu.id in visible, expected, user.login)

    def test_domains_offer_only_the_tutor_scope(self):
        other_student = self._other_tutor_student()
        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).new({
            'teacher_id': self.tutor_employee.id,
        })
        groups = self.env['ems.group'].search(ast.literal_eval(justification.group_domain))
        self.assertIn(self.group, groups)
        self.assertNotIn(other_student.main_group_id, groups)
        students = self.env['res.partner'].search(ast.literal_eval(justification.student_domain))
        self.assertIn(self.student, students)
        self.assertNotIn(other_student, students)

    def test_every_student_gets_the_prevision(self):
        mate = self.env['res.partner'].create({
            'name': 'Test Prevision Mate (Attendance Justification)', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': self.group.id,
        })
        justification = self._shared_justification(self.student | mate)
        schedule = self._other_teacher_schedule()
        schedule.student_ids = [(6, 0, (self.student | mate).ids)]

        result = self.env['ems.attendance_session_header'].create_scheduled_session(self.today, schedule.id)

        lines = self.env['ems.attendance_session_header'].browse(result['id']).attendance_session_line_ids
        self.assertEqual(lines.attendance_prevision_id, justification)
        self.assertEqual(lines.student_id, self.student | mate)

    # Issue #795: justification reasons.

    def _reason(self, key):
        return self.env.ref(f'ems.attendance_justification_reason_{key}')

    def test_default_reason_is_the_first_one(self):
        justification = self._shared_justification(self.student)
        self.assertEqual(justification.reason_id, self.env['ems.attendance_justification_reason'].search([], limit=1))
        self.assertEqual(justification.reason_id, self._reason('health'))

    def test_other_requires_details(self):
        with self.assertRaises(ValidationError):
            self.env['ems.attendance_justification'].create({
                'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
                'reason_id': self._reason('other').id, **self._today_range(),
            })

    def test_other_reason_in_the_form_keeps_details_only_for_it(self):
        with Form(self.env['ems.attendance_justification'].with_user(self.tutor_user)) as form:
            form.start_date, form.end_date = self._today_range().values()
            form.student_id = self.student
            form.reason_id = self._reason('other')
            form.details = 'Visita a la família'
            form.reason_id = self._reason('health')
            self.assertFalse(form.details)

    def test_strike_covers_the_whole_day_picked(self):
        line = self._line()
        line.status_id = self.env.ref('ems.attendance_status_miss')
        justification = self.env['ems.attendance_justification'].with_user(self.tutor_user).create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            'reason_id': self._reason('strike').id, 'day': self.today,
        })
        utils = self.env['ems.datetime_utils']
        self.assertEqual(justification.start_date, utils.datetime_to_odoo(utils.time_float_to_utc_datetime(self.today, 0.0)))
        self.assertEqual(utils.utc_to_local_date(justification.end_date), self.today)
        self.assertEqual(justification.day, self.today)
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_justified'))

    def test_strike_in_the_form_picks_a_day(self):
        with Form(self.env['ems.attendance_justification'].with_user(self.tutor_user)) as form:
            form.student_id = self.student
            form.reason_id = self._reason('strike')
            form.day = self.today
        justification = form.record
        self.assertEqual(justification.utc_to_local_date(justification.start_date), self.today)
        self.assertEqual(justification.utc_to_local_date(justification.end_date), self.today)
        self.assertGreater(justification.end_date - justification.start_date, timedelta(hours=23))

    def test_partial_period_keeps_its_hours_in_the_form(self):
        # The day follows the period's start: it must only set a whole day for a full-day reason.
        start = datetime.combine(self.today, datetime.min.time()) + timedelta(hours=8)
        with Form(self.env['ems.attendance_justification'].with_user(self.tutor_user)) as form:
            form.student_id = self.student
            form.start_date, form.end_date = start, start + timedelta(hours=2)
        self.assertEqual((form.record.start_date, form.record.end_date), (start, start + timedelta(hours=2)))

    def test_switching_to_strike_turns_the_period_into_its_whole_day(self):
        start = datetime.combine(self.today, datetime.min.time()) + timedelta(hours=8)
        with Form(self.env['ems.attendance_justification'].with_user(self.tutor_user)) as form:
            form.student_id = self.student
            form.start_date, form.end_date = start, start + timedelta(hours=2)
            form.reason_id = self._reason('strike')
        justification = form.record
        self.assertEqual(justification.day, justification.utc_to_local_date(start))
        self.assertGreater(justification.end_date - justification.start_date, timedelta(hours=23))

    def test_strike_refuses_a_partial_period(self):
        with self.assertRaises(ValidationError):
            self.env['ems.attendance_justification'].create({
                'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
                'reason_id': self._reason('strike').id,
                'start_date': datetime.combine(self.today, datetime.min.time()) + timedelta(hours=8),
                'end_date': datetime.combine(self.today, datetime.min.time()) + timedelta(hours=10),
            })

    def _post_migrate(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'migrations', '18.0.0.47.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('ems_post_migrate_18_0_0_47_0', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        return migration

    def test_migration_merges_each_batch_into_one_justification(self):
        """What the assistant (issues #656, #763) created: one justification per student, created
        together, each with a copy of the file. Merged into one; one created on its own stays."""
        own_line = self._line()
        own_line.status_id = self.env.ref('ems.attendance_status_miss')
        mate, mate_line = self._group_mate_with_miss()
        Justification = self.env['ems.attendance_justification']
        batch = Justification.create([{
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, student.ids)],
            'reason_id': self._reason('other').id, 'details': 'Vaga', **self._today_range(),
            'attachment_ids': [self._attachment_command('vaga.pdf')],
        } for student in (self.student, mate)])
        tomorrow = self.today + timedelta(days=1)
        alone = Justification.create({
            'teacher_id': self.tutor_employee.id, 'student_ids': [(6, 0, self.student.ids)],
            'reason_id': self._reason('other').id, 'details': 'Vaga',
            'start_date': datetime.combine(tomorrow, datetime.min.time()),
            'end_date': datetime.combine(tomorrow, datetime.max.time()),
        })
        self.env.flush_all()

        self._post_migrate().merge_batch_justifications(self.env.cr)
        self.env.invalidate_all()

        kept = batch[0]
        self.assertFalse(batch[1].exists())
        self.assertTrue(alone.exists())
        self.assertEqual(kept.student_ids, self.student | mate)
        self.assertEqual(kept.attendance_session_line_ids, own_line | mate_line)
        self.assertEqual((own_line | mate_line).attendance_justification_id, kept)
        self.assertEqual(mate_line.status_id, self.env.ref('ems.attendance_status_justified'))
        self.assertEqual(kept.attachment_ids.mapped('name'), ['vaga.pdf'])

    def test_migration_moves_notes_to_details_and_keeps_the_notes_field(self):
        justification = self._shared_justification(self.student)
        justification.notes = 'Vaga 11/11'
        self.env.flush_all()

        self._post_migrate().move_notes_to_details(self.env.cr)
        self.env.invalidate_all()

        self.assertEqual(justification.details, 'Vaga 11/11')
        self.assertFalse(justification.notes)

    def test_migration_keeps_justifications_created_one_by_one(self):
        Justification = self.env['ems.attendance_justification']
        mate, __ = self._group_mate_with_miss()
        first = self._shared_justification(self.student)
        second = self._shared_justification(mate)
        # Created in different requests: never the same instant.
        self.env.flush_all()
        self.env.cr.execute("UPDATE ems_attendance_justification SET create_date = create_date - interval '1 minute' WHERE id = %s", (first.id,))

        self._post_migrate().merge_batch_justifications(self.env.cr)
        self.env.invalidate_all()

        self.assertEqual((first | second).exists(), first | second)
        self.assertEqual(Justification.search([('id', 'in', (first | second).ids)]).student_ids, self.student | mate)
