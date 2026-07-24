from datetime import date

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestYearRecord(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Course = cls.env['ems.course']
        # The current course is driven by the "Current course" setting
        # (company.current_course_id), which syncs ems.course.is_current.
        cls.current_course = Course.create({'start': 2098, 'end': 2099})
        cls.env.company.current_course_id = cls.current_course
        cls.next_course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2099, 'end': 2100, 'is_enrollment_default': True})

        # Users / employees
        cls.tutor_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Tutor (Year Record)',
            'login': 'test_tutor_for_year_record',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Test Tutor (Year Record) Employee',
            'user_id': cls.tutor_user.id,
            'employee_type': 'teacher',
        })
        cls.other_teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Other Teacher (Year Record)',
            'login': 'test_other_teacher_for_year_record',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        # Also a teacher: like real secretariat staff, and the regression case for
        # the tutor rule shadowing the secretary's all-data access.
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Year Record)',
            'login': 'test_secretary_for_year_record',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_secretary').id),
                          (4, cls.env.ref('ems.group_teacher').id)],
        })

        # Curriculum: one study with two subjects. Subject 1 has a work placement
        # weight (90/10), subject 2 is internal-only (100/0).
        cls.level = cls.env['ems.level'].create({'acronym': 'YRL', 'name': 'Year Record Level'})
        cls.study = cls.env['ems.study'].create({
            'code': 'YRSTD1', 'acronym': 'YRS', 'name': 'Year Record Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.study_no_flow = cls.env['ems.study'].create({
            'code': 'YRSTD2', 'acronym': 'YRNF', 'name': 'Year Record Study No Flow',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.subject1 = cls.env['ems.subject'].create({
            'code': 'YRSUB1', 'acronym': 'YRS1', 'name': 'Year Record Subject 1',
            'study_ids': [(4, cls.study.id)],
        })
        cls.subject2 = cls.env['ems.subject'].create({
            'code': 'YRSUB2', 'acronym': 'YRS2', 'name': 'Year Record Subject 2',
            'study_ids': [(4, cls.study.id)],
        })
        cls.outcome1 = cls.env['ems.outcome'].create({
            'code': 'YRSUB1_01RA', 'acronym': 'RA1', 'name': 'Outcome 1', 'subject_id': cls.subject1.id,
        })
        cls.outcome2 = cls.env['ems.outcome'].create({
            'code': 'YRSUB1_02RA', 'acronym': 'RA2', 'name': 'Outcome 2', 'subject_id': cls.subject1.id,
        })
        cls.outcome3 = cls.env['ems.outcome'].create({
            'code': 'YRSUB2_01RA', 'acronym': 'RA1', 'name': 'Outcome 3', 'subject_id': cls.subject2.id,
        })
        cls.planning1 = cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subject1.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [
                (0, 0, {'outcome_id': cls.outcome1.id, 'ponderation': 60.0}),
                (0, 0, {'outcome_id': cls.outcome2.id, 'ponderation': 40.0}),
            ],
        })
        cls.planning2 = cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subject2.id,
            'internal_ponderation': 100.0, 'external_ponderation': 0.0,
            'planning_outcome_ids': [
                (0, 0, {'outcome_id': cls.outcome3.id, 'ponderation': 100.0}),
            ],
        })

        # Groups (tutored first year + a second year for promotion scenarios)
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.tutor_employee.id, 'shift': 'morning',
        })
        cls.group2 = cls.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.group_no_flow = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study_no_flow.id,
        })
        # Enrollment template makes cls.study a "flow" study.
        cls.template = cls.env['sale.order.template'].create({
            'name': 'Year Record Enrollment Template', 'ems_study_id': cls.study.id,
            'study_year': 1,
        })

    # --- helpers -------------------------------------------------------------

    def _student(self, name, **vals):
        return self.env['res.partner'].create(dict(
            {'name': name, 'contact_type': 'student', 'main_group_id': self.group.id}, **vals))

    def _enroll(self, student, subject):
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.group.id, 'subject_id': subject.id})

    def _session(self, subject, round="1"):
        return self.env['ems.grade_session'].create({
            'group_id': self.group.id, 'subject_id': subject.id, 'round': round})

    def _score(self, session, student, scores):
        """Write {outcome: score} on the session's lines for the student."""
        for outcome, score in scores.items():
            line = session.grade_outcome_line_ids.filtered(
                lambda l: l.student_id == student and l.outcome_id == outcome)
            line.write({'score': score, 'is_scored': True})

    def _generate(self, student, course=None):
        return self.env['ems.student.year_record'].generate_for_students(
            student, course or self.current_course)

    def _graded_student(self, name='Graded Student'):
        """A student with subject1 scored over two rounds (RA1=6 r1; RA2=4 r1, 5 r2)
        and subject2 fully passed (RA3=7 r1)."""
        student = self._student(name)
        self._enroll(student, self.subject1)
        self._enroll(student, self.subject2)
        session1 = self._session(self.subject1, round="1")
        session1.fill_students()
        self._score(session1, student, {self.outcome1: 6, self.outcome2: 4})
        session2 = self._session(self.subject1, round="2")
        session2.fill_students()
        self._score(session2, student, {self.outcome2: 5})
        session3 = self._session(self.subject2, round="1")
        session3.fill_students()
        self._score(session3, student, {self.outcome3: 7})
        return student

    # --- model basics --------------------------------------------------------

    def test_create_valid_and_display_name(self):
        student = self._student('Basic Student')
        record = self.env['ems.student.year_record'].create({
            'student_id': student.id, 'course_id': self.current_course.id})
        self.assertTrue(record)
        self.assertIn('Basic Student', record.display_name)
        self.assertIn(self.current_course.name, record.display_name)

    def test_required_fields(self):
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env['ems.student.year_record'].create({'course_id': self.current_course.id})
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env['ems.student.year_record'].create({'student_id': self._student('R').id})

    def test_unique_student_course(self):
        student = self._student('Unique Student')
        self.env['ems.student.year_record'].create({
            'student_id': student.id, 'course_id': self.current_course.id})
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env['ems.student.year_record'].create({
                'student_id': student.id, 'course_id': self.current_course.id})

    def test_legacy_grade_outcome_removed(self):
        self.assertNotIn('ems.grade_outcome', self.env)

    # --- generation: header --------------------------------------------------

    def test_generate_header_snapshot(self):
        student = self._student('Header Student')
        record = self._generate(student)
        self.assertEqual(record.student_id, student)
        self.assertEqual(record.course_id, self.current_course)
        self.assertEqual(record.study_id, self.study)
        self.assertEqual(record.study_name, self.study.display_name)
        self.assertEqual(record.level_id, self.level)
        self.assertEqual(record.group_id, self.group)
        self.assertEqual(record.group_name, self.group.name)
        self.assertEqual(record.tutor_id, self.tutor_employee)
        self.assertEqual(record.tutor_name, self.tutor_employee.name)
        self.assertEqual(record.shift, 'morning')
        self.assertIn(record, student.year_record_ids)

    def test_generate_is_idempotent(self):
        student = self._graded_student('Idempotent Student')
        record1 = self._generate(student)
        subjects1 = len(record1.subject_record_ids)
        record2 = self._generate(student)
        self.assertEqual(record1, record2)
        self.assertEqual(self.env['ems.student.year_record'].search_count(
            [('student_id', '=', student.id), ('course_id', '=', self.current_course.id)]), 1)
        self.assertEqual(len(record2.subject_record_ids), subjects1)

    def test_regenerate_refreshes_copied_values(self):
        student = self._graded_student('Refresh Student')
        record = self._generate(student)
        subject_rec = record.subject_record_ids.filtered(lambda s: s.subject_id == self.subject2)
        self.assertEqual(subject_rec.internal_grade, 7)
        # The teacher rectifies the grade; regeneration picks up the new value.
        session = self.env['ems.grade_session'].search([
            ('group_id', '=', self.group.id), ('subject_id', '=', self.subject2.id)])
        self._score(session, student, {self.outcome3: 9})
        record = self._generate(student)
        subject_rec = record.subject_record_ids.filtered(lambda s: s.subject_id == self.subject2)
        self.assertEqual(subject_rec.internal_grade, 9)

    # --- generation: subjects and outcomes ------------------------------------

    def test_generate_copies_last_round_subject_line(self):
        student = self._graded_student()
        record = self._generate(student)
        self.assertEqual(len(record.subject_record_ids), 2)
        subject_rec = record.subject_record_ids.filtered(lambda s: s.subject_id == self.subject1)
        # Frozen weights from the planning.
        self.assertEqual(subject_rec.internal_weight, 90.0)
        self.assertEqual(subject_rec.external_weight, 10.0)
        # Last round (2): RA1=6 (carried), RA2=5 -> internal = (6*60 + 5*40) / 100 = 5.6 -> 6
        self.assertEqual(subject_rec.internal_grade, 6)
        self.assertEqual(subject_rec.subject_name, self.subject1.display_name)

    def test_generate_state_passed_and_final_pending(self):
        student = self._graded_student()
        record = self._generate(student)
        subject_rec = record.subject_record_ids.filtered(lambda s: s.subject_id == self.subject1)
        # All RAs resolved >= 5 -> passed, even though the EM is not scored yet.
        self.assertEqual(subject_rec.state, 'passed')
        self.assertFalse(subject_rec.has_final)
        self.assertTrue(subject_rec.final_pending)

    def test_generate_no_external_weight_final_complete(self):
        student = self._graded_student()
        record = self._generate(student)
        subject_rec = record.subject_record_ids.filtered(lambda s: s.subject_id == self.subject2)
        self.assertEqual(subject_rec.state, 'passed')
        self.assertEqual(subject_rec.external_weight, 0.0)
        self.assertTrue(subject_rec.has_final)
        self.assertEqual(subject_rec.final_grade, 7)
        self.assertFalse(subject_rec.final_pending)

    def test_generate_state_failed(self):
        student = self._student('Failed Student')
        self._enroll(student, self.subject1)
        session = self._session(self.subject1, round="1")
        session.fill_students()
        self._score(session, student, {self.outcome1: 3, self.outcome2: 6})
        record = self._generate(student)
        subject_rec = record.subject_record_ids.filtered(lambda s: s.subject_id == self.subject1)
        self.assertEqual(subject_rec.state, 'failed')
        self.assertFalse(subject_rec.final_pending)

    def test_generate_state_failed_when_unscored(self):
        student = self._student('Unscored Student')
        self._enroll(student, self.subject1)
        session = self._session(self.subject1, round="1")
        session.fill_students()
        self._score(session, student, {self.outcome1: 6})  # outcome2 never scored
        record = self._generate(student)
        subject_rec = record.subject_record_ids.filtered(lambda s: s.subject_id == self.subject1)
        self.assertEqual(subject_rec.state, 'failed')

    def test_generate_outcome_rounds(self):
        student = self._graded_student()
        record = self._generate(student)
        subject_rec = record.subject_record_ids.filtered(lambda s: s.subject_id == self.subject1)
        self.assertEqual(len(subject_rec.outcome_record_ids), 2)
        ra2 = subject_rec.outcome_record_ids.filtered(lambda o: o.outcome_id == self.outcome2)
        self.assertEqual(ra2.round1_score, 4)
        self.assertTrue(ra2.round1_is_scored)
        self.assertEqual(ra2.round2_score, 5)
        self.assertTrue(ra2.round2_is_scored)
        self.assertFalse(ra2.round3_is_scored)
        # Resolved grade = last scored round.
        self.assertEqual(ra2.final_score, 5)
        self.assertTrue(ra2.final_is_scored)
        self.assertEqual(ra2.weight, 40.0)
        self.assertEqual(ra2.outcome_name, self.outcome2.display_name)

    # --- generation: attendance ------------------------------------------------

    def test_generate_attendance(self):
        student = self._student('Attendance Student')
        # A graded subject, so the record gets a subject line to carry the per-subject rate.
        self._enroll(student, self.subject1)
        grade_session = self._session(self.subject1, round="1")
        grade_session.fill_students()
        self._score(grade_session, student, {self.outcome1: 6, self.outcome2: 6})
        space_type = self.env['ems.space_type'].create({'name': 'Year Record Space Type'})
        work_location = self.env['hr.work.location'].create({
            'name': 'Year Record Work Location', 'address_id': self.env.company.partner_id.id})
        space = self.env['ems.space'].create({
            'code': 'YRS-SPACE', 'name': 'Year Record Space',
            'space_type_id': space_type.id, 'work_location_id': work_location.id})
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.tutor_employee.id])], 'level_id': self.level.id,
            'study_id': self.study.id, 'subject_id': self.subject1.id,
            'group_ids': [(6, 0, [self.group.id])], 'space_id': space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2098, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': str(date.today().weekday()),
            'start_time': 0.0, 'end_time': 23.0, 'space_id': space.id,
        })
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date.today(),
            'mode': 'manual', 'session_teacher_id': self.tutor_employee.id,
        })
        for xmlid in ('attendance_status_attended', 'attendance_status_delayed', 'attendance_status_issue', 'attendance_status_miss'):
            self.env['ems.attendance_session_line'].create({
                'attendance_session_id': session.id, 'student_id': student.id,
                'status_id': self.env.ref(f'ems.{xmlid}').id})
        self.env['ems.attendance_issue_student'].create({'student_id': student.id})
        record = self._generate(student)
        # 3 of 4 lines count as assistance ('a_' prefix).
        self.assertEqual(record.attendance_rate, 75.0)
        self.assertEqual(record.attendance_issue_count, 1)
        subject_rec = record.subject_record_ids.filtered(lambda s: s.subject_id == self.subject1)
        self.assertEqual(subject_rec.attendance_rate, 75.0)

    # --- generation: academic result -------------------------------------------

    def test_academic_result_withdrawn(self):
        student = self._student('Withdrawn Student', exit_type='withdrawal',
                                exit_course_id=self.current_course.id,
                                exit_date=date.today())
        record = self._generate(student)
        self.assertEqual(record.academic_result, 'withdrawn')
        self.assertEqual(record.exit_type, 'withdrawal')
        self.assertFalse(record.title_obtained)

    def test_academic_result_graduated(self):
        student = self._student('Graduated Student', has_graduated=True,
                                exit_type='graduation',
                                exit_course_id=self.current_course.id)
        record = self._generate(student)
        self.assertEqual(record.academic_result, 'full')
        self.assertTrue(record.title_obtained)

    def test_academic_result_promotes_full(self):
        student = self._graded_student('Promoted Student')
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_course_id': self.next_course.id,
            'ems_study_id': self.study.id, 'ems_group_id': self.group2.id})
        order.write({'state': 'sale'})
        record = self._generate(student)
        self.assertEqual(record.academic_result, 'full')
        self.assertFalse(record.title_obtained)

    def test_academic_result_promotes_partial(self):
        student = self._student('Partial Student')
        self._enroll(student, self.subject1)
        session = self._session(self.subject1, round="1")
        session.fill_students()
        self._score(session, student, {self.outcome1: 3, self.outcome2: 6})
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_course_id': self.next_course.id,
            'ems_study_id': self.study.id, 'ems_group_id': self.group2.id})
        order.write({'state': 'sale'})
        record = self._generate(student)
        self.assertEqual(record.academic_result, 'partial')

    def test_academic_result_repeating_same_year(self):
        student = self._graded_student('Repeating Student')
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_course_id': self.next_course.id,
            'ems_study_id': self.study.id, 'ems_group_id': self.group.id})
        order.write({'state': 'sale'})
        record = self._generate(student)
        self.assertEqual(record.academic_result, 'repeating')

    def test_academic_result_repeating_no_enrollment_flow_study(self):
        student = self._student('Missing Student')
        record = self._generate(student)
        self.assertEqual(record.academic_result, 'repeating')

    def test_academic_result_empty_without_flow(self):
        student = self.env['res.partner'].create({
            'name': 'No Flow Student', 'contact_type': 'student',
            'main_group_id': self.group_no_flow.id})
        record = self._generate(student)
        self.assertFalse(record.academic_result)

    # --- withdrawal wizard integration ------------------------------------------

    def test_withdrawal_generates_year_record(self):
        student = self._graded_student('Withdrawal Wizard Student')
        wizard = self.env['ems.withdrawal_wizard'].with_context(
            active_ids=[student.id]).create({'exit_date': date.today()})
        wizard.action_apply()
        self.assertEqual(student.contact_type, 'withdrawal')
        self.assertFalse(student.main_group_id)
        record = self.env['ems.student.year_record'].search([
            ('student_id', '=', student.id), ('course_id', '=', self.current_course.id)])
        self.assertEqual(len(record), 1)
        # The record kept the group snapshot even though the student was detached.
        self.assertEqual(record.group_id, self.group)
        self.assertEqual(record.study_id, self.study)
        self.assertEqual(record.academic_result, 'withdrawn')
        self.assertEqual(record.exit_type, 'withdrawal')
        self.assertEqual(len(record.subject_record_ids), 2)

    # --- access ------------------------------------------------------------------

    def test_access_tutor_reads_own_students_only(self):
        student = self._student('Access Student')
        record = self._generate(student)
        # The group's tutor can read its students' records.
        self.assertIn(record, self.env['ems.student.year_record'].with_user(
            self.tutor_user).search([]))
        # Another teacher cannot.
        self.assertNotIn(record, self.env['ems.student.year_record'].with_user(
            self.other_teacher_user).search([]))
        with self.assertRaises(AccessError):
            record.with_user(self.other_teacher_user).read(['student_id'])

    def test_access_secretary_can_adjust_result(self):
        student = self._graded_student('Secretary Access Student')
        record = self._generate(student)
        # Reads all records even without tutoring anyone (secretary rule beats the
        # tutor restriction that would otherwise apply to a secretary-teacher).
        self.assertIn(record, self.env['ems.student.year_record'].with_user(
            self.secretary_user).search([]))
        self.assertTrue(record.subject_record_ids.with_user(self.secretary_user).read(['state']))
        record.with_user(self.secretary_user).write({'academic_result': 'partial'})
        self.assertEqual(record.academic_result, 'partial')
        with self.assertRaises(AccessError):
            record.with_user(self.secretary_user).unlink()

    def test_access_teacher_cannot_write(self):
        student = self._student('Teacher Write Student')
        record = self._generate(student)
        with self.assertRaises(AccessError):
            record.with_user(self.tutor_user).write({'academic_result': 'full'})
