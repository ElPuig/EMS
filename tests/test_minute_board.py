from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
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


class TestMinuteBoardDecisions(TransactionCase):
    """Issue #881: the board's decision per student, and where it goes (enrollment proposal,
    course transition, academic record)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        build_claim_fixture(cls)
        cls.board_type = cls.env.ref('__import__.minute_type_board')
        cls.course = cls.env.company.current_course_id
        cls.final_session = cls.env['ems.grade_session'].create({
            'group_id': cls.group.id, 'subject_id': cls.subject.id, 'round': '4', 'teacher_id': cls.teacher.id})
        cls.final_session.fill_students()

    def _second_year(self):
        return self.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'level_id': self.level.id, 'study_id': self.study.id})

    def _board_line(self, session):
        session.with_user(self.head_of_studies).write({'state': 'board'})
        minute = self.env['ems.minute'].search([('type_id', '=', self.board_type.id), ('group_id', '=', self.group.id),
                                                ('grade_round', '=', session.round)])
        return minute.board_student_ids.filtered(lambda line: line.student_id == self.student)

    def test_decisions_offered_per_round_and_course(self):
        self.assertFalse(self._board_line(self.grade_session).allowed_decisions)
        final = self._board_line(self.final_session)
        # The group is the study's last course: its students graduate.
        self.assertEqual(final.allowed_decisions, 'graduate,repeat,dropout')
        self._second_year()
        final.invalidate_recordset(['allowed_decisions'])
        self.assertEqual(final.allowed_decisions, 'promote,repeat,dropout')
        second = self.env['ems.grade_session'].create({
            'group_id': self.group.id, 'subject_id': self.subject.id, 'round': '2', 'teacher_id': self.teacher.id})
        self.assertEqual(self._board_line(second).allowed_decisions, 'repeat_risk,next_course,dropout')

    def test_a_decision_of_another_round_is_refused(self):
        with self.assertRaises(ValidationError):
            self._board_line(self.grade_session).decision = 'repeat'
        with self.assertRaises(ValidationError):
            self._board_line(self.final_session).decision = 'repeat_risk'

    def test_recommended_enrollment_filled_with_the_failed_modules(self):
        # RA1 graded 4 and RA2 not graded: the module has no passing final grade.
        line = self._board_line(self.final_session)
        line.decision = 'repeat'
        self.assertEqual(line.recommended_subject_ids, self.subject)
        line.decision = 'dropout'
        self.assertFalse(line.recommended_subject_ids)

    def test_recommended_enrollment_follows_the_outcomes_only(self):
        # Every outcome at 5 or more passes the module, as in the academic record, even without a
        # final grade (the external part, the work placement, never fails a module).
        self.final_session.planning_id.write({'internal_ponderation': 90.0, 'external_ponderation': 10.0})
        self.final_session.grade_outcome_line_ids.sudo().write({'score': 6, 'is_scored': True})
        line = self._board_line(self.final_session)
        line.decision = 'repeat'
        self.assertFalse(line.recommended_subject_ids)

    def test_dropout_offers_the_expected_withdrawal(self):
        line = self._board_line(self.final_session)
        line.decision = 'dropout'
        self.assertTrue(line.with_user(self.tutor_user).can_mark_withdrawal_expected)
        self.assertFalse(line.with_user(self.other_teacher_user).can_mark_withdrawal_expected)
        action = line.with_user(self.tutor_user).action_mark_withdrawal_expected()
        self.assertEqual(action['res_model'], 'ems.withdrawal_expected_wizard')
        with self.assertRaises(UserError):
            line.with_user(self.other_teacher_user).action_mark_withdrawal_expected()

    def test_academic_record_keeps_the_decision(self):
        self._board_line(self.final_session).decision = 'repeat'
        record = self.env['ems.student.year_record'].sudo()._generate_one(self.student, self.course)
        self.assertEqual(record.board_decision, 'repeat')

    def test_enrollment_proposal_follows_the_decision(self):
        self.env.company.enrollment_course_id = self.env['ems.course'].create({'start': 2098, 'end': 2099})
        tutorship, other = self.env['ems.subject'].create([
            {'code': 'TGCTUT', 'acronym': 'TGCT', 'name': 'Claim Tutorship', 'is_tutorship': True,
             'study_ids': [(4, self.study.id)]},
            {'code': 'TGCOTH', 'acronym': 'TGCO', 'name': 'Claim Other Subject', 'study_ids': [(4, self.study.id)]},
        ])
        template = self.env['sale.order.template'].create({
            'name': 'Claim Template C1', 'ems_study_id': self.study.id, 'study_year': 1,
            'sale_order_template_line_ids': [(0, 0, {'product_id': subject.product_id.id})
                                             for subject in (tutorship, self.subject, other)]})
        self.env['sale.order.template'].create({'name': 'Claim Template C2', 'ems_study_id': self.study.id, 'study_year': 2})
        self._second_year()
        line = self._board_line(self.final_session)
        line.decision = 'repeat'
        wizard = self.env['ems.enrollment_proposal_wizard'].with_context(active_ids=self.student.ids).create({})
        self.assertEqual(wizard.template_id, template)
        self.assertTrue(wizard.board_decision_info)
        wizard.action_create_enrollments()
        order = self.env['sale.order'].search([('partner_id', '=', self.student.id)])
        self.assertEqual(order.order_line.product_id & (tutorship | self.subject | other).product_id,
                         (tutorship | self.subject).product_id)

    def test_transition_warns_when_the_enrollment_contradicts_the_decision(self):
        group2 = self._second_year()
        line = self._board_line(self.final_session)
        line.decision = 'repeat'
        wizard = self.env['ems.course_transition_wizard'].new({
            'source_course_id': self.course.id, 'study_ids': [(6, 0, self.study.ids)]})
        order = self.env['sale.order'].new({'partner_id': self.student.id, 'ems_study_id': self.study.id,
                                            'ems_group_id': group2.id})
        self.assertEqual(len(wizard._board_mismatches({self.student.id: order})), 1)
        order.ems_group_id = self.group
        self.assertEqual(wizard._board_mismatches({self.student.id: order}), [])
