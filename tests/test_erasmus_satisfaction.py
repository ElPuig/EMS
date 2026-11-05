import io
import zipfile
from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, next_student_id, shift_ems_clock
from .test_erasmus_mobility import ErasmusMobilityCase


class ErasmusSatisfactionCase(ErasmusMobilityCase):
    """Both students accept a place; their stay ends yesterday."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.technician_user = create_role_user(cls, 'erasmus', 'test_satisfaction_technician')
        cls.today = cls.env['ems.datetime_utils'].get_local_today()

    def _ended(self):
        first, second = self._accepted()
        (first | second).sudo().write({'state': 'preparing', 'date_start': self.today - timedelta(days=30),
                                       'date_end': self.today - timedelta(days=1)})
        return first, second

    def _open(self):
        first, second = self._ended()
        self.env['ems.erasmus.satisfaction']._ems_open_ended()
        return first.sudo().satisfaction_ids, second.sudo().satisfaction_ids


@tagged('post_install', '-at_install')
class TestErasmusSatisfaction(ErasmusSatisfactionCase):

    def test_the_survey_opens_once_the_stay_is_over_and_is_answered_on_the_portal(self):
        first, _second = self._accepted()
        first.sudo().write({'state': 'preparing', 'date_start': self.today, 'date_end': self.today + timedelta(days=5)})
        self.env['ems.erasmus.satisfaction']._ems_open_ended()
        self.assertFalse(first.sudo().satisfaction_ids, "Not while the stay goes on.")
        first.sudo().date_end = self.today - timedelta(days=1)
        survey = self.env['ems.erasmus.satisfaction']._ems_open_ended()
        self.assertEqual(survey, first.sudo().satisfaction_ids)
        self.assertEqual((survey.state, survey.participant_type, survey.course_id, survey.open_date),
                         ('pending', 'student_other', self.call.course_id, self.today))
        self.assertFalse(self.env['ems.erasmus.satisfaction']._ems_open_ended() & survey, "Opened only once.")
        self.assertEqual(self.student._ems_erasmus_satisfaction_pending(), survey)
        self.assertTrue(self.student._ems_erasmus_portal_visible())
        survey._ems_portal_answer(9, comment='  Great company  ')
        self.assertEqual((survey.state, survey.score, survey.comment, survey.is_low), ('answered', 9, 'Great company', False))
        with self.assertRaises(UserError, msg="Only once."):
            survey._ems_portal_answer(8)

    def test_a_low_score_needs_what_did_not_work_and_the_score_goes_from_1_to_10(self):
        survey, _other = self._open()
        for score in (0, 11, '7'):
            with self.assertRaises(UserError):
                survey._ems_portal_answer(score)
        with self.assertRaises(UserError):
            survey._ems_portal_answer(6, what_failed='   ')
        survey._ems_portal_answer(6, what_failed='Accommodation far from the company')
        self.assertTrue(survey.is_low)

    def test_students_are_reminded_at_3_and_7_days_from_9_in_the_morning(self):
        survey, answered = self._open()
        answered._ems_portal_answer(10)
        shift_ems_clock(self, hour=10.0)
        today = self.env['ems.datetime_utils'].get_local_today()
        Survey = self.env['ems.erasmus.satisfaction']
        for days, expected in ((2, 0), (3, 1), (6, 1), (7, 2), (30, 2)):
            survey.sudo().open_date = today - timedelta(days=days)
            Survey._cron_satisfaction()
            self.assertEqual(survey.reminder_count, expected, days)
        self.assertEqual(answered.reminder_count, 0, "An answered survey is never reminded.")

    def test_staff_get_a_todo_instead_of_emails_and_it_goes_away_once_answered(self):
        survey, _other = self._open()
        survey.sudo().participant_type = 'staff'
        self.student.sudo().user_ids = self.teacher_user
        self.teacher_user.sudo().lang = 'ca_ES'
        # The hourly cron runs as the system user, in English: the to-do is in the teacher's
        # language (usage test, 2026-11-04).
        survey.with_context(lang='en_US')._ems_schedule_todo()
        self.assertEqual(survey.activity_id.user_id, self.teacher_user)
        self.assertEqual(survey.activity_id.summary,
                         survey.with_context(lang='ca_ES')._ems_todo_texts()[0])
        self.assertNotEqual(survey.activity_id.summary, "Erasmus+: answer the satisfaction survey")
        self.assertIn('/my/erasmus/satisfaction/', survey.activity_id.note)
        survey._ems_portal_answer(10)
        self.assertFalse(survey.activity_id.exists())

    def test_the_mobility_closes_only_with_the_survey_answered_or_closed_without_answer(self):
        first, second = self._ended()
        with self.assertRaisesRegex(UserError, 'satisfaction'):
            first.with_user(self.erasmus_user)._ems_check_satisfaction()
        survey = first.sudo().satisfaction_ids
        self.assertTrue(survey, "Closing opens it when the cron has not yet.")
        survey._ems_portal_answer(8)
        first.with_user(self.erasmus_user)._ems_check_satisfaction()
        self.assertEqual(first.with_user(self.technician_user).satisfaction_state, 'answered')
        # The coordinator, as an exception and with the reason.
        other = self.env['ems.erasmus.satisfaction']._ems_open_ended() or second.sudo().satisfaction_ids
        with self.assertRaises(AccessError):
            other.with_user(self.technician_user).action_mark_not_answered()
        with self.assertRaises(UserError):
            other.with_user(self.erasmus_user).action_mark_not_answered()
        other.with_user(self.erasmus_user).not_answered_reason = 'Unreachable after the reminders'
        other.with_user(self.erasmus_user).action_mark_not_answered()
        self.assertEqual((other.state, other.not_answered_by_id), ('not_answered', self.erasmus_user))
        second.with_user(self.erasmus_user)._ems_check_satisfaction()

    def test_the_team_reads_the_answers_without_the_name_and_the_coordinator_with_it(self):
        survey, _other = self._open()
        survey._ems_portal_answer(4, what_failed='Nobody met me at the airport')
        self.env.invalidate_all()
        team = survey.with_user(self.technician_user)
        self.assertEqual(team.read(['score', 'what_failed'])[0]['score'], 4)
        self.assertNotIn(self.student.name, team.display_name)
        for name in ('partner_id', 'mobility_id', 'group_participant_id'):
            with self.assertRaises(AccessError, msg=name):
                team.read([name])
        with self.assertRaises(AccessError):
            self.env['ems.erasmus.satisfaction'].with_user(self.technician_user).search(
                [('partner_id', '=', self.student.id)])
        self.assertEqual(survey.with_user(self.erasmus_user).partner_id, self.student)
        with self.assertRaises(AccessError):
            survey.with_user(self.hos_user).read(['score'])

    def test_a_low_score_becomes_an_improvement_action_of_the_quality_app_without_the_name(self):
        survey, answered = self._open()
        with self.assertRaises(UserError, msg="Not answered yet, so not low."):
            answered.with_user(self.technician_user).action_create_improvement()
        survey._ems_portal_answer(5, what_failed='The company had no tasks for me')
        answered._ems_portal_answer(4, what_failed='No mentor')
        with self.assertRaises(AccessError):
            survey.with_user(self.teacher_user).action_create_improvement()
        # The 2026-11-04 usage test: one who may not see the Quality app's actions is told, instead
        # of opening it and getting an access error.
        self.assertFalse(self.technician_user.has_group('ems.group_teacher'))
        result = answered.with_user(self.technician_user).action_create_improvement()
        self.assertEqual(result['tag'], 'display_notification')
        self.assertTrue(answered.improvement_action_id)
        # The Erasmus team are teachers: they then manage the action like any other of theirs.
        self.technician_user.groups_id |= self.env.ref('ems.group_teacher')
        result = survey.with_user(self.technician_user).action_create_improvement()
        action = self.env['ems.quality.action'].browse(result['res_id'])
        self.assertEqual((action.type, survey.improvement_action_id), ('improvement', action))
        self.assertIn('The company had no tasks for me', action.description)
        self.assertNotIn(self.student.name, action.name + action.description)
        self.assertEqual(action.create_uid, self.technician_user)
        with self.assertRaises(UserError, msg="Only once."):
            survey.with_user(self.technician_user).action_create_improvement()

    def test_interest_counts_who_applied_out_of_who_could_and_is_frozen_with_the_definitive_list(self):
        applicants, target = self.call._ems_interest()
        submitted = self.call.application_ids.filtered(lambda application: application.state not in (
            'draft', 'not_submitted'))
        self.assertEqual(applicants, len(submitted.partner_id))
        self.assertEqual(target, len(self.call._ems_eligible_partners()))
        self.assertFalse(self.call.interest_date)
        self._accepted()
        self.assertTrue(self.call.interest_date, "Frozen when the definitive resolution is published.")
        frozen = (self.call.interest_applicant_count, self.call.interest_target_count)
        self.env['res.partner'].create({'name': 'Erasmus Late Student', 'contact_type': 'student',
                                        'student_id': next_student_id(), 'main_group_id': self.group.id})
        self.assertEqual(self.call._ems_interest(), frozen, "The history never changes.")


@tagged('post_install', '-at_install')
class TestErasmusQualityPanel(ErasmusSatisfactionCase):
    """The figures: percentage, average, median, response rate, and nothing without access."""

    def _panel(self, **vals):
        return self.env['ems.erasmus.quality.panel'].with_user(self.technician_user).create(vals)

    def test_stats_average_median_and_empty(self):
        Panel = self.env['ems.erasmus.quality.panel']
        self.assertEqual(Panel._ems_stats([]), (None, None, 0))
        self.assertEqual(Panel._ems_stats([10, 8, 6, 9]), (8.25, 8.5, 4))
        self.assertEqual(Panel._ems_stats([7, 3, 10]), (20 / 3, 7, 3))
        self.assertEqual(Panel._ems_number(8.25), '8,2')
        self.assertEqual(Panel._ems_number(None), '-')

    def test_interest_percentage_adds_the_calls_up(self):
        class Call:
            def __init__(self, applicants, target):
                self.counts = applicants, target

            def _ems_interest(self):
                return self.counts

        Panel = self.env['ems.erasmus.quality.panel']
        self.assertEqual(Panel._ems_interest([Call(3, 40)]), (7.5, 3, 40))
        self.assertEqual(Panel._ems_interest([Call(3, 40), Call(2, 10)]), (10.0, 5, 50))
        self.assertEqual(Panel._ems_interest([]), (None, 0, 0))

    def test_panel_shows_satisfaction_response_rate_and_no_names(self):
        first, second = self._open()
        first._ems_portal_answer(10)
        panel = self._panel(call_id=self.call.id)
        data = panel._ems_data()
        satisfaction = next(row for row in data['indicators'] if row['target'] == 8.5)
        self.assertEqual((satisfaction['value'], satisfaction['median'], satisfaction['n']), (10, 10, 1))
        rate = data['indicators'][-1]
        self.assertEqual((rate['value'], rate['n']), (50.0, '1 / 2'))
        second._ems_portal_answer(5, what_failed='Too short')
        self.assertEqual(self._panel(call_id=self.call.id)._ems_data()['indicators'][2]['value'], 7.5)
        html = ''.join(str(panel[name]) for name in ('indicators_html', 'breakdown_html', 'funnel_html',
                                                      'evolution_html'))
        self.assertIn(self.call.name, html)
        for name in (self.student.name, self.second.name):
            self.assertNotIn(name, html)
        self.assertEqual(self._panel(participant_type='staff')._ems_data()['indicators'][2]['n'], 0)

    def test_only_the_team_opens_the_panel(self):
        with self.assertRaises(AccessError):
            self.env['ems.erasmus.quality.panel'].with_user(self.teacher_user).create({})


@tagged('post_install', '-at_install')
class TestErasmusQualityEvidence(ErasmusSatisfactionCase):
    """Phase 2: earlier courses typed in by hand, diffusion actions, the PDF and the network evidence."""

    def test_earlier_courses_join_the_evolution_marked_as_manual_load(self):
        History = self.env['ems.erasmus.quality.history']
        with self.assertRaises(Exception):
            History.create({'course_name': '22-23', 'source': 'Test'})
        with self.assertRaises(Exception):
            History.create({'course_name': '2019-2020', 'satisfaction': 11, 'source': 'Test'})
        History.create({'course_name': '2019-2020', 'student_applicants': 10, 'student_target': 200,
                        'satisfaction': 9.5, 'satisfaction_count': 12, 'source': 'Test sheet'})
        rows = self.env['ems.erasmus.quality.panel'].with_user(self.technician_user).create({})._ems_evolution()
        row = next(row for row in rows if '2019-2020' in row[0])
        self.assertEqual(row[1:], ['5,0 %', '-', '9,5', 12])
        self.assertIn('2019-2020', rows[0][0], "Oldest first.")
        with self.assertRaises(AccessError):
            History.with_user(self.technician_user).create({'course_name': '2018-2019', 'source': 'Test'})

    def test_every_call_email_is_a_diffusion_action_with_a_generic_audience(self):
        Diffusion = self.env['ems.erasmus.diffusion']
        before = Diffusion.search_count([])
        count = self.call._ems_announce(self.student | self.second, 'ems.email_template_erasmus_call_open')
        action = Diffusion.search([], order='id desc', limit=1)
        self.assertEqual(Diffusion.search_count([]), before + 1)
        self.assertEqual((action.channel, action.recipient_count, action.call_id, action.is_automatic),
                         ('ems_email', count, self.call, True))
        self.assertNotIn(self.student.name, action.audience + action.name)
        manual = Diffusion.with_user(self.technician_user).create({'name': 'ErasmusDays', 'channel': 'event'})
        self.assertEqual(manual.course_id, self.env.company.current_course_id)

    def test_the_report_and_the_network_evidence_carry_no_names(self):
        first, second = self._open()
        first._ems_portal_answer(4, what_failed='Nobody at the airport')
        second._ems_portal_answer(10)
        first.sudo().action_create_improvement()
        self.env['ems.erasmus.diffusion'].create({'name': 'ErasmusDays', 'channel': 'event',
                                                  'course_id': self.call.course_id.id})
        panel = self.env['ems.erasmus.quality.panel'].with_user(self.technician_user).create(
            {'course_id': self.call.course_id.id})
        html, _type = self.env['ir.actions.report']._render_qweb_html('ems.action_report_erasmus_quality', panel.ids)
        html = html.decode()
        self.assertIn('Erasmus+ satisfaction: Nobody at the airport', html)
        export = self.env['ems.erasmus.export'].with_user(self.technician_user).create(
            {'scope': 'network', 'course_id': self.call.course_id.id})
        with export._ems_zip() as archive:
            bundle = zipfile.ZipFile(io.BytesIO(archive.read()))
        names = bundle.namelist()
        for folder in ('2-documentacio', '3-mobilitats', '4-difusio'):
            self.assertTrue(any(f'/{folder}/' in name for name in names), folder)
        content = b''.join(bundle.read(name) for name in names if not name.endswith('.pdf'))
        content += html.encode()
        for name in (self.student.name, self.second.name):
            self.assertNotIn(name.encode(), content)
        self.assertIn(b'ErasmusDays', content)
        with self.assertRaises(UserError):
            self.env['ems.erasmus.export'].with_user(self.technician_user).create({'scope': 'network'}).action_generate()


@tagged('post_install', '-at_install')
class TestErasmusSatisfactionTour(HttpCase, ErasmusSatisfactionCase):

    def test_portal_survey_low_score_asks_for_confirmation(self):
        survey, _other = self._open()
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': self.student.name, 'login': 'test_erasmus_satisfaction_student',
            'password': 'test_erasmus_satisfaction_student', 'partner_id': self.student.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.start_tour('/my/erasmus', 'ems_erasmus_satisfaction_tour', login='test_erasmus_satisfaction_student')
        self.assertEqual((survey.state, survey.score, survey.what_failed), ('answered', 4, 'The flights were late'))
