from datetime import date, datetime

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from .common import create_head_of_studies_branch, create_level_study, create_role_employee, create_role_user, \
    mock_outgoing_email, next_student_id


class TestAttendedDespiteJustification(TransactionCase):
    """Issue #811: a justified student comes to class after all (ems.attendance_session_line
    attend_despite_justification / undo_attend_despite_justification)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.level, cls.study = create_level_study(cls, 'TCDJ', level={'name': 'Test Level (Came Despite Justification)'}, study={
            'code': 'TCDJ', 'name': 'Test Study (Came Despite Justification)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TCDJ', 'acronym': 'TCDJ', 'name': 'Test Subject (Came Despite Justification)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TCDJ-A', 'name': 'Test Space (Came Despite Justification)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_teacher_tcdj', name='TCDJ Teacher')
        cls.teacher = create_role_employee(cls, cls.teacher_user)
        cls.other_teacher_user = create_role_user(cls, 'teacher', 'test_other_teacher_tcdj', name='TCDJ Other Teacher')
        create_role_employee(cls, cls.other_teacher_user)
        cls.tutor_user = create_role_user(cls, 'teacher', 'test_tutor_tcdj', name='TCDJ Tutor')
        cls.tutor = create_role_employee(cls, cls.tutor_user)
        create_head_of_studies_branch(cls, 'TCDJ', cls.tutor)
        cls.admin_user = create_role_user(cls, 'academic_admin', 'test_admin_tcdj', name='TCDJ Admin')
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TCDJ', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.tutor.id,
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Came Despite Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
        })
        template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.teacher.id])], 'study_ids': [(6, 0, [cls.study.id])],
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': str(date.today().weekday()),
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
            'student_ids': [(6, 0, [cls.student.id])],
        })
        cls.session = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': cls.teacher.id,
        })
        cls.line = cls.session.attendance_session_line_ids.filtered(lambda line: line.student_id == cls.student)
        cls.line.status_id = cls.env.ref('ems.attendance_status_miss')
        cls.justification = cls.env['ems.attendance_justification'].create({
            'teacher_id': cls.tutor.id, 'student_ids': [(6, 0, cls.student.ids)],
            'start_date': datetime(2026, 1, 5, 9, 0), 'end_date': datetime(2026, 1, 5, 11, 0),
            'attendance_session_line_ids': [(6, 0, cls.line.ids)],
        })
        cls.attended = cls.env.ref('ems.attendance_status_attended')
        cls.justified = cls.env.ref('ems.attendance_status_justified')

    def _attend(self, user=None, status=None, line=None):
        Line = self.env['ems.attendance_session_line'].with_user(user or self.teacher_user)
        return Line.change_justified_status((line or self.line).id, (status or self.attended).id)

    def _notices(self):
        return self.env['ems.info_notice'].sudo().search([
            ('user_id', '=', self.tutor_user.id), ('res_model', '=', 'res.partner'), ('res_id', '=', self.student.id)])

    def test_justified_line_is_justified(self):
        self.assertEqual(self.line.status_id, self.justified)
        self.assertEqual(self.line.attendance_justification_id, self.justification)

    def test_attending_keeps_the_justification_and_tells_the_tutor(self):
        self._attend()
        self.assertEqual(self.line.status_id, self.attended)
        self.assertTrue(self.line.came_despite_justification)
        self.assertEqual(self.line.attendance_justification_id, self.justification)
        notices = self._notices()
        self.assertEqual(len(notices), 1)
        self.assertIn('Came Despite Student', notices.body)

    def test_a_delay_is_allowed(self):
        self._attend(status=self.env.ref('ems.attendance_status_delayed'))
        self.assertEqual(self.line.status_id, self.env.ref('ems.attendance_status_delayed'))

    def test_only_the_ordinary_absence_stays_locked(self):
        with self.assertRaises(UserError):
            self._attend(status=self.env.ref('ems.attendance_status_miss'))
        self.assertEqual(self.line.status_id, self.justified)
        self.assertFalse(self.line.came_despite_justification)

    def test_a_severe_delay_is_allowed(self):
        severe = self.env.ref('ems.attendance_status_delayed_severe')
        self._attend(status=severe)
        self.assertEqual(self.line.status_id, severe)
        self.assertTrue(self.line.came_despite_justification)

    def test_switching_between_options_needs_no_undo(self):
        for xmlid in ('attended', 'delayed_severe', 'delayed', 'attended'):
            self._attend(status=self.env.ref(f'ems.attendance_status_{xmlid}'))
            self.assertEqual(self.line.status_id, self.env.ref(f'ems.attendance_status_{xmlid}'))
            self.assertTrue(self.line.came_despite_justification)
        # ... and back to the justified absence, with its justification and notes.
        self._attend(status=self.justified)
        self.assertFalse(self.line.came_despite_justification)
        self.assertEqual(self.line.attendance_justification_id, self.justification)

    def test_a_justified_severe_delay_stays_locked(self):
        # Justifying a severe delay leaves a minor delay that is itself the justified state.
        self.line.write({'status_id': self.env.ref('ems.attendance_status_delayed').id, 'came_despite_justification': False})
        with self.assertRaises(UserError):
            self._attend(status=self.attended)

    def test_a_line_without_justification_cannot_be_changed(self):
        self.line.write({'attendance_justification_id': False})
        with self.assertRaises(UserError):
            self._attend()

    def test_undo_puts_the_justified_absence_back(self):
        self._attend()
        self._attend(status=self.justified)
        self.assertEqual(self.line.status_id, self.justified)
        self.assertFalse(self.line.came_despite_justification)
        self.assertEqual(self.line.attendance_justification_id, self.justification)
        self.assertEqual(len(self._notices()), 2)

    def test_who_may_change_it(self):
        with self.assertRaises(AccessError):
            self._attend(user=self.other_teacher_user)  # not their session
        # The student's tutor, a chief above them and an administrator may, whoever owns the session.
        for user in (self.tutor_user, self.head_of_studies, self.admin_user):
            self._attend(user=user)
            self.assertTrue(self.line.came_despite_justification)
            self._attend(user=user, status=self.justified)
        # Not a chief of another branch.
        with self.assertRaises(AccessError):
            self._attend(user=self.other_head_of_studies)
        with self.assertRaises(AccessError):
            self._attend(user=self.other_department_chief)

    def test_a_guard_teacher_may_in_guard_mode(self):
        Line = self.env['ems.attendance_session_line'].with_user(self.other_teacher_user)
        Line.change_justified_status(self.line.id, self.attended.id, True)
        self.assertTrue(self.line.came_despite_justification)

    def test_no_tutor_no_notice_and_no_error(self):
        self.student.main_group_id = False
        self._attend()
        self.assertFalse(self._notices())

    def test_no_new_family_notification(self):
        self.student.student_email = 'came.despite@example.com'
        before = self.env['ems.attendance_issue_status'].search_count([('attendance_session_line_id', '=', self.line.id)])
        self._attend()
        self.assertEqual(
            self.env['ems.attendance_issue_status'].search_count([('attendance_session_line_id', '=', self.line.id)]), before)

    def test_removing_the_justification_keeps_the_attendance(self):
        self._attend()
        self.justification.unlink()
        self.assertEqual(self.line.status_id, self.attended)
        self.assertFalse(self.line.came_despite_justification)
        self.assertFalse(self.line.attendance_justification_id)
