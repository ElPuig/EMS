from datetime import timedelta

from odoo.exceptions import AccessError, UserError, ValidationError

from .common import create_role_employee, create_role_user, make_working_day
from .test_absence_detection import AbsenceDetectionCase

REVIEW = 'ems.mail_activity_absence_review'


class TestAbsenceReview(AbsenceDetectionCase):
    """Issue #707: every detected absence is first reviewed by whoever corrects the teacher's
    attendance, who requests a justification, corrects the check-in, prepares the absence or
    discards it. See "The review" in docs/en/developers/employees/absence.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.leave_type = cls.env.ref('ems.leave_type_justified')
        # A Department Chief between the Head of Studies and a teacher of their own: reads the
        # teacher's entries (rule_absence_pending_hierarchy) but doesn't review them.
        cls.chief_user = create_role_user(cls, 'department_chief', 'test_chief_tar', name='TAR Department Chief')
        cls.chief = create_role_employee(cls, cls.chief_user, parent_id=cls.head.id)
        cls.chief.department_id = cls.department
        cls.chief_teacher_user = create_role_user(cls, 'teacher', 'test_chief_teacher_tar', name='TAR Chief Teacher')
        cls.chief_teacher = cls._teacher('TAR Chief Teacher', user=cls.chief_teacher_user)
        cls.chief_teacher.parent_id = cls.chief

    def _detect(self, employee=None):
        self.Pending._ems_detect_missing_check_ins(self.yesterday)
        return self._detected(employee)

    def _review_activities(self, absence, done=False):
        """The review tasks of `absence`: open ones, or (done=True) those marked done."""
        if done:
            return self.env['mail.message'].search([
                ('model', '=', 'ems.absence_pending'), ('res_id', '=', absence.id),
                ('mail_activity_type_id', '=', self.env.ref(REVIEW).id)])
        return absence.activity_ids.filtered(lambda activity: activity.activity_type_id == self.env.ref(REVIEW))

    def _told(self, absence, user):
        return absence.message_ids.filtered(lambda message: user.partner_id in message.partner_ids)

    def _as_reviewer(self, absences):
        return absences.with_user(self.head_of_studies)

    # --- The task ---------------------------------------------------------------------------------

    def test_a_detected_absence_is_a_task_for_the_teachers_head_of_studies(self):
        absence = self._detect()

        self.assertEqual(absence.state, 'pending')
        self.assertEqual(self._review_activities(absence).user_id, self.head_of_studies)
        self.assertFalse(self._told(absence, self.teacher_user), 'the teacher is not told')

    def test_an_informed_absence_is_reviewed_too(self):
        informed = self.Pending.with_user(self.chief_user).create({
            'employee_id': self.chief_teacher.id, 'date_from': self._utc(self.yesterday, 9.0),
            'date_to': self._utc(self.yesterday, 11.0)})

        self.assertEqual(self._review_activities(informed).user_id, self.head_of_studies,
                         "not the chief who entered it: the teacher's Head of Studies")

    def test_without_a_head_of_studies_the_administrators_review_it(self):
        orphan = self._teacher('TAR Teacher Without Head Of Studies')
        orphan.parent_id = False
        absence = self._detect(orphan)
        reviewers = self._review_activities(absence).user_id

        self.assertTrue(reviewers)
        self.assertTrue(all(user.has_group('ems.group_academic_admin') for user in reviewers))
        self.assertNotIn(self.env.ref('base.user_root'), reviewers, 'nobody reads OdooBot\'s tasks')

    def test_the_task_is_in_the_reviewers_daily_digest_without_an_email_of_its_own(self):
        mails = self.env['mail.mail'].sudo().search([])
        absence = self._detect()

        digest_types = [group['type'] for group in self.head_of_studies._ems_task_digest_groups()]
        self.assertIn(self.env.ref(REVIEW), digest_types)
        new_mails = self.env['mail.mail'].sudo().search([]) - mails
        self.assertFalse(new_mails.filtered(lambda mail: self.head_of_studies.partner_id in mail.recipient_ids),
                         'the digest is how the reviewer hears about it')
        self.assertTrue(self._review_activities(absence))

    # --- Who reviews ------------------------------------------------------------------------------

    def test_only_the_teachers_reviewer_or_an_administrator(self):
        absence = self._detect(self.chief_teacher)

        self.assertTrue(self._as_reviewer(absence).can_review)
        self.assertFalse(absence.with_user(self.chief_user).can_review, 'a Department Chief reads it, no more')
        with self.assertRaises(UserError):
            absence.with_user(self.chief_user).action_discard()
        with self.assertRaises(AccessError):
            absence.with_user(self.other_head_of_studies).action_discard()
        self.assertTrue(absence.with_user(self.env.ref('base.user_admin')).can_review)

        absence.with_user(self.env.ref('base.user_admin')).action_discard()
        self.assertEqual(absence.state, 'discarded')

    def test_only_while_it_is_to_review(self):
        absence = self._detect()
        self._as_reviewer(absence).action_request_justification()

        self.assertFalse(self._as_reviewer(absence).can_review)
        with self.assertRaises(UserError):
            self._as_reviewer(absence).action_discard()

    def test_a_selection_acts_on_what_it_can_and_says_how_many_it_left(self):
        absence, other = self._detect(), self._detect(self.chief_teacher)
        self._as_reviewer(other).action_request_justification()

        result = self._as_reviewer(absence | other).action_discard()

        self.assertEqual(absence.state, 'discarded')
        self.assertEqual(other.state, 'justification_requested')
        self.assertEqual(result['params']['type'], 'warning')
        self.assertIn('1 left as they were', result['params']['message'])

    # --- Request justification --------------------------------------------------------------------

    def test_requesting_a_justification_asks_the_teacher_and_closes_the_task(self):
        absence = self._detect()
        self._as_reviewer(absence).action_request_justification()

        self.assertEqual(absence.state, 'justification_requested')
        self.assertEqual(len(self._told(absence, self.teacher_user)), 1)
        self.assertFalse(self._review_activities(absence))
        self.assertTrue(self._review_activities(absence, done=True), 'marked done, not deleted')
        self.assertTrue(absence.with_user(self.teacher_user).can_request)

    # --- Correct check-in -------------------------------------------------------------------------

    def _attendances(self, employee=None):
        return self.env['hr.attendance'].search([('employee_id', '=', (employee or self.teacher).id)])

    def test_correcting_a_day_without_check_in_records_it_and_tells_nobody(self):
        absence = self._detect()
        messages = self.env['mail.message'].search([])

        self._as_reviewer(absence).action_correct_check_in()

        attendance = self._attendances()
        self.assertEqual((attendance.check_in, attendance.check_out), (absence.date_from, absence.date_to))
        self.assertEqual(attendance.ems_checked_in_by_id, self.head_of_studies)
        self.assertEqual(absence.state, 'corrected', 'not discarded by the check-in it records')
        self.assertFalse(self._review_activities(absence))
        new = self.env['mail.message'].search([]) - messages
        self.assertFalse(new.filtered(lambda message: self.teacher_user.partner_id in message.partner_ids),
                         'the teacher is not told, unlike a check-in registered from the guard duty board')
        self.assertTrue(absence.message_ids.filtered(lambda message: 'Check-in corrected by' in (message.body or '')))
        self.assertFalse(absence.with_user(self.teacher_user).search([('id', '=', absence.id)]))

    def test_correcting_a_late_arrival_moves_the_check_in_back(self):
        late = self._check_in(self.teacher, self.yesterday, 10.5)
        absence = self._detect()

        self._as_reviewer(absence).action_correct_check_in()

        self.assertEqual(self._attendances(), late, 'no second attendance')
        self.assertEqual(late.check_in, self._utc(self.yesterday, 9.0))
        self.assertEqual(absence.state, 'corrected')

    def test_correcting_needs_it_over_and_within_one_day(self):
        future = self.Pending.create({'employee_id': self.teacher.id, 'date_from': self._utc(self.today, 12.0),
                                      'date_to': self._utc(self.today, 13.0)})
        days = self.Pending.create({'employee_id': self.teacher.id, 'date_from': self._utc(self.yesterday - timedelta(days=2), 9.0),
                                    'date_to': self._utc(self.yesterday, 13.0)})

        self.assertFalse(self._as_reviewer(future).can_correct)
        self.assertFalse(self._as_reviewer(days).can_correct)
        with self.assertRaises(UserError):
            self._as_reviewer(future | days).action_correct_check_in()
        self.assertFalse(self._attendances())

    # --- Create absence ---------------------------------------------------------------------------

    def _prepare(self, absences, leave_type=None):
        action = self._as_reviewer(absences).action_prepare_absence()
        self.assertEqual(action['res_model'], 'ems.absence_pending.prepare_wizard')
        wizard = self.env['ems.absence_pending.prepare_wizard'].with_user(self.head_of_studies).with_context(
            action['context']).create({'leave_type_id': (leave_type or self.leave_type).id})
        return wizard.action_confirm()

    def test_creating_the_absence_prepares_it_for_the_teacher_to_send(self):
        absence = self._detect()
        leaves = self.env['hr.leave'].search([('employee_id', '=', self.teacher.id)])

        result = self._prepare(absence)

        self.assertEqual(result['params']['next'], {'type': 'ir.actions.act_window_close'})
        self.assertEqual(absence.state, 'prepared')
        self.assertEqual(absence.proposed_leave_type_id, self.leave_type)
        self.assertEqual(absence.requested_date, self.today)
        self.assertEqual(self.env['hr.leave'].search([('employee_id', '=', self.teacher.id)]), leaves,
                         'nothing is filed on their behalf: the declaration is theirs')
        self.assertEqual(len(self._messages_to(absence, self.teacher_user, 'has been prepared for you')), 1)
        self.assertFalse(self._review_activities(absence))

    def test_the_prepared_request_opens_with_its_type_and_links_it(self):
        absence = self._detect()
        self._prepare(absence)
        teacher_absence = absence.with_user(self.teacher_user)
        self.assertTrue(teacher_absence.can_request)

        context = teacher_absence.action_request_absence()['context']
        self.assertEqual(context['default_holiday_status_id'], self.leave_type.id)
        defaults = self.env['hr.leave'].with_user(self.teacher_user).with_context(context).default_get(
            ['holiday_status_id', 'request_date_from', 'request_hour_from', 'request_hour_to'])
        self.assertEqual(defaults['holiday_status_id'], self.leave_type.id, 'kept, not left empty by EMS')
        leave = self.env['hr.leave'].with_user(self.teacher_user).with_context(context).create({
            'ems_submitted': True, 'ems_responsible_declaration': True})

        self.assertEqual(leave.holiday_status_id, self.leave_type)
        self.assertEqual(absence.state, 'linked')
        self.assertEqual(absence.leave_id, leave)

    def test_preparing_several_at_once(self):
        absence, other = self._detect(), self._detect(self.chief_teacher)

        self._prepare(absence | other)

        self.assertEqual((absence | other).mapped('state'), ['prepared', 'prepared'])

    def test_a_prepared_absence_not_sent_is_reported(self):
        self.env.company.write({'ems_absence_document_reminder_days': 1, 'ems_absence_document_escalation_days': 2})
        absence = self._detect()
        self._prepare(absence)
        later = self.today + timedelta(days=7)
        while later.weekday() > 4:
            later += timedelta(days=1)
        make_working_day(self, later)

        self._run_cron_on(later)

        self.assertTrue(self._messages_to(absence, self.head_of_studies, 'has still not sent the absence request'))
        self.assertTrue(self._messages_to(absence, self.teacher_user, 'has been prepared for you')[1:],
                        'reminded again')

    # --- Discard ----------------------------------------------------------------------------------

    def test_discarding_archives_it_and_tells_nobody(self):
        absence = self._detect()
        messages = self.env['mail.message'].search([])

        self._as_reviewer(absence).action_discard()

        self.assertEqual(absence.state, 'discarded')
        self.assertFalse(absence.active)
        self.assertFalse(self._detected(), 'out of the default list')
        self.assertTrue(self.Pending.with_context(active_test=False).search([('id', '=', absence.id)]))
        self.assertTrue(self._review_activities(absence, done=True), 'the task is done, not deleted')
        new = self.env['mail.message'].search([]) - messages
        self.assertFalse(new.filtered(lambda message: message.partner_ids), 'nobody is told')
        self.assertTrue(new.filtered(lambda message: 'Discarded by TAD Head of Studies' in (message.body or '')))
        with self.assertRaises(ValidationError):
            absence.date_to = self._utc(self.yesterday, 12.0)

    # --- What still settles it on its own ---------------------------------------------------------

    def test_a_check_in_settles_it_at_any_stage(self):
        absence = self._detect()
        self._as_reviewer(absence).action_request_justification()

        self._check_in(self.teacher, self.yesterday, 8.9)

        self.assertEqual(absence.state, 'discarded')
        self.assertFalse(absence.activity_ids)

    def test_the_teacher_filing_the_absence_before_the_review_closes_it(self):
        absence = self._detect()

        leave = self.env['hr.leave'].with_user(self.teacher_user).with_context(absence._ems_request_context()).create({
            'holiday_status_id': self.leave_type.id, 'ems_submitted': True, 'ems_responsible_declaration': True})

        self.assertEqual(absence.state, 'linked')
        self.assertEqual(absence.leave_id, leave)
        self.assertFalse(self._review_activities(absence))

    def test_the_guard_duty_board_plans_around_what_is_unresolved(self):
        course = self.env['ems.course']
        board = lambda employee: course._get_guard_duty_absence_intervals(self.yesterday, employee).get(employee.id)
        prepared_teacher = self._teacher('TAR Prepared Teacher')
        corrected_teacher = self._teacher('TAR Corrected Teacher')
        discarded_teacher = self._teacher('TAR Discarded Teacher')
        to_review, waiting, prepared = self._detect(), self._detect(self.chief_teacher), self._detect(prepared_teacher)
        corrected, discarded = self._detect(corrected_teacher), self._detect(discarded_teacher)
        self._as_reviewer(waiting).action_request_justification()
        self._prepare(prepared)
        self._as_reviewer(corrected).action_correct_check_in()
        self._as_reviewer(discarded).action_discard()

        self.assertEqual((to_review | waiting | prepared).mapped('state'), ['pending', 'justification_requested', 'prepared'])
        for teacher in (self.teacher, self.chief_teacher, prepared_teacher):
            self.assertEqual(board(teacher), [(9.0, 13.0, 'pending')], teacher.name)
        self.assertEqual((corrected | discarded).mapped('state'), ['corrected', 'discarded'])
        self.assertFalse(board(corrected_teacher))
        self.assertFalse(board(discarded_teacher))

    # --- Migration (18.0.0.40.1) ------------------------------------------------------------------

    def test_the_migration_keeps_the_reminded_ones_waiting_and_sends_the_rest_to_review(self):
        reminded, quiet = self._detect(), self._detect(self.chief_teacher)
        # As they were before the review existed: no task, one of them already reminded.
        (reminded | quiet).activity_ids.unlink()
        reminded.write({'reminder_date': self.yesterday})

        for _run in range(2):  # the second run proves it idempotent
            self.Pending._ems_migrate_to_review()

        self.assertEqual(reminded.state, 'justification_requested')
        self.assertEqual(reminded.requested_date, self.yesterday)
        self.assertFalse(self._review_activities(reminded))
        self.assertEqual(quiet.state, 'pending')
        self.assertEqual(len(self._review_activities(quiet)), 1)
