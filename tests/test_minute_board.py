from datetime import date, timedelta

from odoo.tests.common import TransactionCase

from .common import next_student_id
from .test_grade_claim import build_claim_fixture


class TestMinuteBoard(TransactionCase):
    """Issue #880: the evaluation board minute, created when a group's sessions reach the board."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        build_claim_fixture(cls)
        cls.Minute = cls.env['ems.minute']
        cls.board_type = cls.env.ref('__import__.minute_type_board')

    def _to_board(self):
        self.grade_session.with_user(self.head_of_studies).write({'state': 'board'})
        return self.Minute.search([('type_id', '=', self.board_type.id), ('group_id', '=', self.group.id),
                                   ('grade_round', '=', '1')])

    def test_minute_created_once_when_the_sessions_reach_the_board(self):
        minute = self._to_board()
        self.assertEqual(len(minute), 1)
        self.assertEqual(minute.redactor_employee_id.id, self.tutor.id)
        self.assertEqual(minute.board_difficulty_ids.mapped('area'), ['a', 'b', 'c', 'd'])
        line = minute.board_student_ids.filtered(lambda line: line.student_id == self.student)
        # RA1 graded 4 (failed), RA2 not graded.
        self.assertEqual((line.passed_count, line.evaluated_count), (0, 1))
        self.assertEqual(minute.activity_ids.user_id, self.tutor_user)
        self.grade_session.with_user(self.head_of_studies).write({'state': 'open'})
        self.assertEqual(self._to_board(), minute)

    def test_refresh_reads_the_grades_again(self):
        minute = self._to_board()
        self.line2.sudo().write({'score': 7, 'is_scored': True})
        minute.action_board_refresh_grades()
        line = minute.board_student_ids.filtered(lambda line: line.student_id == self.student)
        self.assertEqual((line.passed_count, line.evaluated_count), (1, 2))

    def test_writing_task_done_once_sent_for_approval(self):
        minute = self._to_board()
        minute.sudo().state = 'to_approve'
        self.assertFalse(minute.activity_ids.filtered(
            lambda activity: activity.activity_type_id == self.env.ref('ems.mail_activity_board_minute_write')))

    def test_withdrawals_of_the_term(self):
        self.student.write({'exit_type': 'withdrawal', 'exit_date': self.today, 'exit_reason': 'Moved to another town'})
        minute = self._to_board()
        self.assertIn('Claim Student: Moved to another town', minute.board_withdrawals)

    def test_absence_statistics(self):
        # One student misses 2 of 4 hours (50%: above 25% and, unjustified, above 5%); another one
        # misses 1 of 10 hours, justified (10%: neither).
        other = self.env['res.partner'].create({
            'name': 'Claim Other Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.group.id})
        self.env.company.attendance_manual_justified = True
        space = self.env['ems.space'].create({
            'code': 'TMB-A', 'name': 'Board Space', 'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id})
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, self.teacher.ids)], 'study_ids': [(6, 0, self.study.ids)],
            'subject_id': self.subject.id, 'group_ids': [(6, 0, self.group.ids)],
            'start_date': date(2040, 1, 1), 'end_date': date(2040, 12, 31)})
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '0', 'start_time': 8, 'end_time': 9,
            'space_id': space.id, 'student_ids': [(6, 0, (self.student | other).ids)]})
        statuses = {self.student: ['miss', 'miss', 'attended', 'attended'],
                    other: ['justified'] + ['attended'] * 9}
        monday = date(2040, 1, 2)
        for week in range(10):
            lines = [(0, 0, {'student_id': student.id, 'status_id': self.env.ref(f'ems.attendance_status_{marks[week]}').id})
                     for student, marks in statuses.items() if week < len(marks)]
            self.env['ems.attendance_session_header'].create({
                'attendance_schedule_id': schedule.id, 'date': monday + timedelta(weeks=week), 'mode': 'scheduled',
                'session_teacher_id': self.teacher.id, 'attendance_session_line_ids': lines})
        minute = self.Minute.new({'type_id': self.board_type.id, 'group_id': self.group.id})
        counts = minute._ems_board_absences(self.student | other, date(2040, 1, 1), date(2040, 6, 30))
        self.assertEqual(counts, (1, 1))

    def test_tutor_comment_shown_in_the_portal_once_published(self):
        minute = self._to_board()
        minute.board_student_ids.filtered(lambda line: line.student_id == self.student).family_comment = 'Keep working on RA2.'
        self.assertEqual(self.student._ems_portal_grade_rounds(), [])
        self.grade_session.with_user(self.head_of_studies).write({'state': 'published'})
        self.assertEqual(self.student._ems_portal_grade_rounds()[0]['tutor_comment'], 'Keep working on RA2.')

    def test_board_lines_follow_the_minute(self):
        minute = self._to_board()
        Lines = self.env['ems.minute.board.student']
        self.assertTrue(Lines.with_user(self.tutor_user).search([('minute_id', '=', minute.id)]))
        self.assertFalse(Lines.with_user(self.other_teacher_user).search([('minute_id', '=', minute.id)]))
