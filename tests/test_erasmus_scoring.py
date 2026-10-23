from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from .common import create_role_user, mock_outgoing_email, next_student_id
from .test_erasmus import create_erasmus_fixtures, upload

GENERAL = ('motivation', 'maturity', 'difficulties', 'adaptation')
ENGLISH = ('comprehension', 'fluency', 'accuracy')


def score_interview(interview, general, english):
    """Score every general criterion with `general` and every English one with `english`, and
    submit the interview."""
    interview.write({**{name: str(general) for name in GENERAL}, **{name: str(english) for name in ENGLISH}})
    interview.action_submit()


class ErasmusScoringCase(TransactionCase):
    """Phase 1 fixtures plus two subjects of the call's study, a past course, a second student and
    two evaluators (plain teachers)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_transport = mock_outgoing_email(cls)
        create_erasmus_fixtures(cls)
        cls.subject_a, cls.subject_b, cls.subject_other = cls.env['ems.subject'].create([
            {'code': 'TERASA', 'acronym': 'TEA', 'name': 'Erasmus Subject A', 'internal_hours': 60,
             'study_ids': [(4, cls.study.id)]},
            {'code': 'TERASB', 'acronym': 'TEB', 'name': 'Erasmus Subject B', 'internal_hours': 120,
             'study_ids': [(4, cls.study.id)]},
            {'code': 'TERASO', 'acronym': 'TEO', 'name': 'Erasmus Other Study Subject', 'internal_hours': 99,
             'study_ids': [(4, cls.other_group.study_id.id)]},
        ])
        cls.past_course = cls.env['ems.course'].create({'start': 2001, 'end': 2002})
        cls.second = cls.env['res.partner'].create({
            'name': 'Erasmus Second Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id, 'birth_date': '2000-01-01', 'email': 'erasmus.second@example.com'})
        cls.evaluator_1 = create_role_user(cls, 'teacher', 'test_erasmus_evaluator_1')
        cls.evaluator_2 = create_role_user(cls, 'teacher', 'test_erasmus_evaluator_2')
        cls.secretary_user = create_role_user(cls, 'secretary', 'test_erasmus_secretary')
        cls.erasmus_user.email = 'erasmus.team@example.com'  # posts in the chatter

    def _admitted(self, partner=None):
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(
            self.call, partner or self.student)
        upload(application, self.cv)
        application.action_submit()
        application.requirements_check = 'met'
        application.document_ids.filtered('attachment_ids').action_mark_valid()
        application.action_admit()
        return application

    def _past_grade(self, partner, subject, grade, course=None, **vals):
        return self.env['ems.student.year_record'].create({
            'student_id': partner.id, 'course_id': (course or self.past_course).id, 'study_id': self.study.id,
            'subject_record_ids': [(0, 0, {'subject_id': subject.id, 'subject_name': subject.name,
                                           'final_grade': grade, 'has_final': True,
                                           'state': 'passed' if grade >= 5 else 'failed', **vals})],
        })

    def _current_grade(self, partner, subject, grade, group=None, **vals):
        """A live grade line of this course for `partner`: an overridden internal grade."""
        values = {'group_id': (group or self.group).id, 'subject_id': subject.id, 'round': '1'}
        session = self.env['ems.grade_session'].search([(key, '=', value) for key, value in values.items()]) \
            or self.env['ems.grade_session'].create(values)
        line = session.grade_subject_line_ids.filtered(lambda subject_line: subject_line.student_id == partner)
        line = line or self.env['ems.grade_subject_line'].create({
            'grade_session_id': session.id, 'student_id': partner.id})
        line.write({'is_overridden': True, 'internal_score': grade, **vals})
        return line

    def _strike(self, partner, days_ago=1):
        return self.env['ems.strike'].create({
            'student_id': partner.id, 'teacher_id': self.env['hr.employee'].search([], limit=1).id,
            'date': fields.Datetime.now() - timedelta(days=days_ago),
        })

    def _complete(self, application, language='none', fewer='no', first='yes', general=3, english=3):
        """Every manual criterion and two interviews scoring `general`/`english` per criterion."""
        application.write({'language_level': language, 'fewer_opportunities_check': fewer,
                           'first_mobility': first})
        for evaluator in (self.evaluator_1, self.evaluator_2):
            interview = self.env['ems.erasmus.interview'].create({
                'application_id': application.id, 'evaluator_id': evaluator.id})
            score_interview(interview.with_user(evaluator), general, english)
        return application


@tagged('post_install', '-at_install')
class TestErasmusRecordAverage(ErasmusScoringCase):

    def test_hours_weighted_mean_of_past_and_current_modules(self):
        self._past_grade(self.student, self.subject_a, 6)
        self._current_grade(self.student, self.subject_b, 9)
        application = self._admitted()
        self.call.action_close()
        self.assertAlmostEqual(application.grade_average, 8.0)  # (6 x 60 + 9 x 120) / 180
        self.assertAlmostEqual(application.score_a, 32.0)
        self.assertEqual(sorted(application.grade_line_ids.mapped('grade')), [6, 9])
        self.assertTrue(application.scoring_frozen_date)

    def test_repeated_module_counts_once_with_its_latest_grade(self):
        self._past_grade(self.student, self.subject_a, 3)
        self._current_grade(self.student, self.subject_a, 7)
        application = self._admitted()
        self.call.action_close()
        self.assertEqual(application.grade_line_ids.mapped('grade'), [7])
        self.assertAlmostEqual(application.grade_average, 7.0)

    def test_failed_modules_count_convalidated_and_other_studies_do_not(self):
        self._past_grade(self.student, self.subject_a, 4)
        self._past_grade(self.student, self.subject_b, 9, course=self.env['ems.course'].create(
            {'start': 2002, 'end': 2003}), is_convalidated=True)
        record = self._past_grade(self.student, self.subject_other, 10, course=self.env['ems.course'].create(
            {'start': 2003, 'end': 2004}))
        record.study_id = self.other_group.study_id
        application = self._admitted()
        self.call.action_close()
        self.assertEqual(application.grade_line_ids.mapped('grade'), [4])
        self.assertAlmostEqual(application.grade_average, 4.0)

    def test_module_with_nothing_evaluated_is_left_out(self):
        self._current_grade(self.student, self.subject_a, 8)
        session = self.env['ems.grade_session'].create({
            'group_id': self.group.id, 'subject_id': self.subject_b.id, 'round': '1'})
        if not session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student):
            self.env['ems.grade_subject_line'].create({'grade_session_id': session.id, 'student_id': self.student.id})
        application = self._admitted()
        self.call.action_close()
        self.assertEqual(application.grade_line_ids.subject_id, self.subject_a)

    def test_frozen_at_closing(self):
        line = self._current_grade(self.student, self.subject_a, 8)
        application = self._admitted()
        self.call.action_close()
        line.internal_score = 2
        self.assertAlmostEqual(application.grade_average, 8.0)

    def test_without_any_evaluated_grade_the_average_stays_pending(self):
        application = self._admitted()
        self.call.action_close()
        self.assertFalse(application.grade_line_ids)
        self.assertTrue(application.score_a_pending)
        self.assertFalse(application.score_complete)

    def test_secretariat_has_no_access(self):
        application = self._admitted()
        with self.assertRaises(AccessError):
            application.with_user(self.secretary_user).read(['score_total'])


@tagged('post_install', '-at_install')
class TestErasmusScore(ErasmusScoringCase):

    def test_conduct_warnings_of_the_cycle_until_the_closing_date(self):
        application = self._admitted()
        strikes = self.env['ems.strike']
        for _index in range(4):
            strikes |= self._strike(self.student)
        strikes.write({'group_id': self.group.id})
        other_cycle = self._strike(self.student)
        other_cycle.group_id = self.other_group
        self.call.action_close()
        self.assertEqual(application.strike_count, 4)
        self.assertEqual(application.strike_ids, strikes)
        self.assertEqual(application.score_f, -9, "Capped at -9")

    def test_a_pending_criterion_blocks_the_total(self):
        self._current_grade(self.student, self.subject_a, 7)
        application = self._admitted()
        self.call.action_close()
        self.assertFalse(application.score_complete)
        application.write({'language_level': 'b2', 'fewer_opportunities_check': 'yes', 'first_mobility': 'yes'})
        self.assertFalse(application.score_complete, "The interviews are still missing")
        for evaluator in (self.evaluator_1, self.evaluator_2):
            interview = self.env['ems.erasmus.interview'].create({
                'application_id': application.id, 'evaluator_id': evaluator.id})
            score_interview(interview.with_user(evaluator), 4, 3)
        self.assertTrue(application.score_complete)
        # A 28 + interview 16 + 9 + language 5 + fewer opportunities 10 + first mobility 5
        self.assertAlmostEqual(application.score_total, 73.0)
        self.assertTrue(application.is_eligible)

    def test_manual_criteria_record_author_and_date(self):
        application = self._admitted()
        application.with_user(self.erasmus_user).language_level = 'c1'
        self.assertEqual(application.language_level_user_id, self.erasmus_user)
        self.assertTrue(application.language_level_date)
        self.assertAlmostEqual(application.score_c, 7.5)

    def test_fewer_opportunities_only_for_the_erasmus_team(self):
        application = self._admitted()
        with self.assertRaises(AccessError):
            application.with_user(self.hos_user).fewer_opportunities_check = 'yes'
        with self.assertRaises(AccessError):
            application.with_user(self.hos_user).read(['fewer_opportunities_check'])

    def test_ranking_per_modality_with_the_tie_breaks(self):
        self._current_grade(self.student, self.subject_a, 6)
        self._current_grade(self.second, self.subject_a, 6)
        first = self._admitted()
        second = self._admitted(self.second)
        self.call.action_close()
        self._complete(first, fewer='no', first='no')
        self.assertEqual(first.rank, 0, "The ranking waits for every admitted application")
        self._complete(second, fewer='yes', first='no', language='none')
        # Same total once fewer opportunities is balanced by a language certificate.
        first.language_level = 'c2'
        self.assertEqual(first.score_total, second.score_total)
        self.assertEqual((second.rank, first.rank), (1, 2), "Fewer opportunities breaks the tie")

    def test_a_tie_after_every_criterion_needs_a_draw(self):
        self._current_grade(self.student, self.subject_a, 6)
        self._current_grade(self.second, self.subject_a, 6)
        first = self._admitted()
        second = self._admitted(self.second)
        self.call.action_close()
        self._complete(first)
        self._complete(second)
        self.assertEqual((first.rank, second.rank), (1, 1))
        self.assertTrue(first.needs_draw and second.needs_draw)
        (first | second).write({'draw_order': 2})
        second.draw_order = 1
        self.assertEqual((second.rank, first.rank), (1, 2))
        self.assertFalse(first.needs_draw)


@tagged('post_install', '-at_install')
class TestErasmusInterview(ErasmusScoringCase):

    def _interview(self, application, evaluator):
        return self.env['ems.erasmus.interview'].create({
            'application_id': application.id, 'evaluator_id': evaluator.id})

    def test_evaluator_only_sees_their_own_interview(self):
        application = self._admitted()
        mine = self._interview(application, self.evaluator_1)
        self._interview(application, self.evaluator_2)
        visible = self.env['ems.erasmus.interview'].with_user(self.evaluator_1).search([])
        self.assertEqual(visible, mine)
        with self.assertRaises(AccessError):
            application.with_user(self.evaluator_1).read(['state'])

    def test_assignment_manages_the_evaluator_group(self):
        group = self.env.ref('ems.group_erasmus_evaluator')
        interview = self._interview(self._admitted(), self.evaluator_1)
        self.assertIn(group, self.evaluator_1.groups_id)
        interview.evaluator_id = self.evaluator_2
        self.assertNotIn(group, self.evaluator_1.groups_id)
        self.assertIn(group, self.evaluator_2.groups_id)
        interview.unlink()
        self.assertNotIn(group, self.evaluator_2.groups_id)

    def test_assignment_creates_an_activity_done_on_submit(self):
        interview = self._interview(self._admitted(), self.evaluator_1)
        self.assertEqual(interview.activity_ids.user_id, self.evaluator_1)
        score_interview(interview.with_user(self.evaluator_1), 5, 5)
        self.assertFalse(interview.activity_ids)

    def test_submit_needs_every_criterion(self):
        interview = self._interview(self._admitted(), self.evaluator_1).with_user(self.evaluator_1)
        interview.write({name: '4' for name in GENERAL})
        with self.assertRaises(UserError):
            interview.action_submit()
        interview.write({'comprehension': '0', 'fluency': '3', 'accuracy': '2'})
        interview.action_submit()
        self.assertEqual((interview.general_score, interview.english_score), (16, 5))

    def test_evaluator_only_writes_the_rubric(self):
        interview = self._interview(self._admitted(), self.evaluator_1)
        with self.assertRaises(AccessError):
            interview.with_user(self.evaluator_1).evaluator_id = self.evaluator_2

    def test_interview_score_is_the_mean_of_both(self):
        application = self._admitted()
        score_interview(self._interview(application, self.evaluator_1).with_user(self.evaluator_1), 5, 5)
        self.assertFalse(application.interview_complete)
        score_interview(self._interview(application, self.evaluator_2).with_user(self.evaluator_2), 4, 4)
        self.assertTrue(application.interview_complete)
        self.assertAlmostEqual(application.interview_general, 18.0)
        self.assertAlmostEqual(application.interview_english, 13.5)

    def test_one_interview_only_with_a_reason(self):
        application = self._admitted()
        score_interview(self._interview(application, self.evaluator_1).with_user(self.evaluator_1), 5, 5)
        self.assertFalse(application.interview_complete)
        application.single_interview_reason = 'Second evaluator on sick leave'
        self.assertTrue(application.interview_complete)
        self.assertAlmostEqual(application.interview_general, 20.0)

    def test_evaluator_reopens_only_until_the_deadline(self):
        interview = self._interview(self._admitted(), self.evaluator_1)
        self.call.interview_deadline = fields.Datetime.now() + timedelta(days=1)
        score_interview(interview.with_user(self.evaluator_1), 3, 3)
        interview.with_user(self.evaluator_1).action_reopen()
        self.assertEqual(interview.state, 'draft')
        interview.with_user(self.evaluator_1).action_submit()
        self.call.interview_deadline = fields.Datetime.now() - timedelta(hours=1)
        with self.assertRaises(UserError):
            interview.with_user(self.evaluator_1).action_reopen()
        with self.assertRaises(UserError):
            interview.with_user(self.erasmus_user).action_reopen()
        interview.with_user(self.erasmus_user).rectification_note = 'Material error in fluency'
        interview.with_user(self.erasmus_user).action_reopen()
        self.assertEqual(interview.state, 'draft')

    def test_submitted_interview_is_read_only_for_the_evaluator(self):
        interview = self._interview(self._admitted(), self.evaluator_1)
        score_interview(interview.with_user(self.evaluator_1), 3, 3)
        with self.assertRaises(UserError):
            interview.with_user(self.evaluator_1).motivation = '5'

    def test_one_interview_per_evaluator(self):
        application = self._admitted()
        self._interview(application, self.evaluator_1)
        with self.assertRaises(Exception), self.cr.savepoint():
            self._interview(application, self.evaluator_1)

    def test_interview_call_at_least_24_hours_ahead(self):
        application = self._admitted()
        with self.assertRaises(UserError):
            application.action_send_interview_call()
        application.write({'interview_date': fields.Datetime.now() + timedelta(hours=10),
                           'interview_place': 'Room 12'})
        with self.assertRaises(UserError):
            application.action_send_interview_call()
        application.interview_date = fields.Datetime.now() + timedelta(days=2)
        application.action_send_interview_call()
        mail = self.env['mail.mail'].search([('model', '=', application._name), ('res_id', '=', application.id),
                                             ('body_html', 'ilike', 'Room 12')])
        self.assertEqual(len(mail), 1)
        self.assertIn('Room 12', mail.body_html)
        self.assertTrue(application.interview_call_date)

    def test_no_show_excludes_an_admitted_application(self):
        application = self._admitted()
        application.exclusion_reason = 'Did not attend the interview'
        application.action_exclude()
        self.assertEqual(application.state, 'excluded')
