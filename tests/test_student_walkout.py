from datetime import timedelta
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from .common import (create_head_of_studies_branch, create_level_study_group, create_role_employee,
                     create_role_user, mock_outgoing_email, next_student_id, shift_ems_clock)

PDF = b'%PDF-1.4 test union call'


def clear_holidays(cls):
    """No public holiday nor school break (removed inside the test's transaction, rolled back after
    it), so that the school-hour calendar is the same whenever the suite runs. A test adds its own
    with add_holiday()."""
    cls.env.cr.execute("DELETE FROM resource_calendar_leaves WHERE resource_id IS NULL")
    cls.env['resource.calendar.leaves'].invalidate_model()


def add_holiday(case, day):
    utils = case.env['ems.datetime_utils']
    start, end = (utils.datetime_to_odoo(utils.time_float_to_utc_datetime(day + timedelta(days=offset), 0.0))
                  for offset in (0, 1))
    case.env['resource.calendar.leaves'].sudo().create({'name': 'WLK holiday', 'date_from': start, 'date_to': end})


def create_walkout_fixtures(cls, prefix):
    """A 3rd-year group of an allowed level with a tutor below a Head of Studies, its delegate (an
    adult), its sub-delegate and a classmate (minors with a family), all three with portal access,
    and a student without it. The clock on a Monday at 10:00, no holidays and no group schedule
    (emails sent at once): a call opened now votes until Tuesday 10:00 and joins until Wednesday
    10:00, so its first walkout day is next Monday. Fictitious data and addresses only (CLAUDE.md,
    "Email safety")."""
    clear_holidays(cls)
    cls.now = shift_ems_clock(cls, hour=10.0, weekdays=[0])
    cls.today = cls.now.date()
    cls.level, cls.study, cls.group = create_level_study_group(
        cls, prefix, level={'walkout_allowed': True}, group={'course': 3})
    cls.tutor = create_role_user(cls, 'tutor', f'test_walkout_tutor_{prefix.lower()}', name=f'{prefix} Tutor',
                                 email=f'tutor.{prefix.lower()}@example.com')
    cls.group.tutor_id = create_role_employee(cls, cls.tutor)
    create_head_of_studies_branch(cls, prefix, cls.group.tutor_id)
    cls.head_of_studies.email = f'hos.{prefix.lower()}@example.com'
    cls.env.company.write({'walkout_phase_hours': 24, 'walkout_notice_hours': 48})

    def student(name, age, portal=True, **vals):
        partner = cls.env['res.partner'].create({
            'name': f'{prefix} {name}', 'contact_type': 'student', 'main_group_id': cls.group.id,
            'birth_date': cls.today - relativedelta(years=age), 'student_id': next_student_id(),
            'student_email': f'{name.lower().replace(" ", ".")}.{prefix.lower()}@example.com', **vals,
        })
        if portal:
            cls.env['res.users'].with_context(no_reset_password=True).create({
                'name': partner.name, 'login': f'test_walkout_{name.lower().replace(" ", "_")}_{prefix.lower()}',
                'password': f'test_walkout_{name.lower().replace(" ", "_")}_{prefix.lower()}',
                'partner_id': partner.id, 'lang': 'en_US',
                'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
            })
        return partner

    cls.delegate = student('Delegate', 19)
    cls.subdelegate = student('Subdelegate', 16)
    cls.classmate = student('Classmate', 16)
    cls.offline = student('Offline', 16, portal=False)
    cls.group.write({'delegate_id': cls.delegate.id, 'subdelegate_id': cls.subdelegate.id})
    cls.family = cls.env['res.partner'].create({
        'name': f'{prefix} Family', 'contact_type': 'family', 'email': f'family.{prefix.lower()}@example.com',
    })
    for child in (cls.subdelegate, cls.classmate):
        cls.env['res.partner.relation'].create({
            'left_partner_id': cls.family.id, 'type_id': cls.env.ref('ems.relation_type_mother').id,
            'right_partner_id': child.id,
        })
    # The family ratifies, on the portal, that a minor joins.
    cls.family_user = cls.env['res.users'].with_context(no_reset_password=True).create({
        'name': cls.family.name, 'login': f'test_walkout_family_{prefix.lower()}',
        'password': f'test_walkout_family_{prefix.lower()}', 'partner_id': cls.family.id, 'lang': 'en_US',
        'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
    })


def ratify(walkout, family, student, ratifies=True):
    """`family` ratifies (or refuses) on the portal that `student` joins `walkout`."""
    line = walkout.line_ids.filtered(lambda line: line.student_id == student)
    walkout._ems_portal_ratify(family, line, ratifies)


def open_walkout(cls, partner=None, days=7, files=None, **values):
    """Calls a walkout `days` from today (next Monday by default, the first day it can be for) as
    `partner` (the delegate by default)."""
    return cls.env['ems.student_walkout'].sudo()._ems_portal_open(partner or cls.delegate, {
        'walkout_date': cls.today + timedelta(days=days), 'notes': 'Union call', **values,
    }, files if files is not None else [('union_call.pdf', PDF)])


def reject_walkout(walkout, user, reason_xmlid='ems.student_walkout_rejection_no_call', details=False):
    """`user` aborts `walkout` (voting, joining) or does not validate it (closed, justified), from
    its wizard."""
    wizard = walkout.env['ems.student_walkout.reject.wizard'].with_user(user).with_context(
        active_id=walkout.id).create({'reason_id': walkout.env.ref(reason_xmlid).id, 'details': details})
    return wizard.action_reject()


def end_phase(walkout):
    """The current phase's end comes (moved to a second ago: the clock stays) and the cron runs."""
    field = 'vote_until' if walkout.state == 'voting' else 'join_until'
    walkout.sudo()[field] = fields.Datetime.now() - timedelta(seconds=1)
    walkout.env['ems.student_walkout']._cron_ems_walkout_deadlines()


@tagged('post_install', '-at_install')
class TestStudentWalkout(TransactionCase):
    """Issue #800: a student walkout called by the group's delegate with no review first, watched by
    the group's tutor (who may abort it), voted by the group, joined one by one and validated (or
    not) by the Head of Studies. Each phase lasts its school hours from when the
    email reaches the students, and the Head of Studies gets the minute at least the notice before
    the walkout. See docs/en/developers/attendance/student_walkout.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_walkout_fixtures(cls, 'WLK')

    def _mails(self, records):
        return self.env['mail.mail'].sudo().search([('model', '=', records._name), ('res_id', 'in', records.ids)])

    def _tutor_mails(self, walkout):
        return self._mails(walkout).filtered(lambda mail: self.tutor.email in (mail.email_to or ''))

    def _family_mails(self, walkout):
        return self._mails(walkout.line_ids).filtered(lambda mail: self.family.email in (mail.email_to or ''))

    def _notices(self, walkout):
        return self.env['ems.info_notice'].sudo().search([('res_model', '=', walkout._name), ('res_id', '=', walkout.id)])

    def _vote(self, walkout, partner, group_vote='yes'):
        walkout._ems_portal_vote(partner, group_vote)

    def _join(self, walkout, partner, joins=True):
        walkout._ems_portal_join(partner, joins)

    def _supported(self, walkout):
        """Two of the three students with portal access vote yes: the third can no longer change it,
        so the vote ends at once and the joining opens."""
        self._vote(walkout, self.delegate, 'yes')
        self._vote(walkout, self.subdelegate, 'yes')
        self.assertEqual(walkout.state, 'joining')

    def _local(self, day_offset, hour):
        """Naive UTC of `hour` (company time) `day_offset` days from today."""
        utils = self.env['ems.datetime_utils']
        return utils.datetime_to_odoo(utils.time_float_to_utc_datetime(self.today + timedelta(days=day_offset), hour))

    def _calendar(self, now, groups=None):
        return self.env['ems.student_walkout']._ems_projected_calendar(groups or self.group, now)

    # Calling

    def test_delegate_calls_the_vote_at_once(self):
        walkout = open_walkout(self)
        self.assertEqual(walkout.state, 'voting', "No review first: the group votes at once.")
        self.assertEqual(walkout.opener_id, self.delegate)
        self.assertEqual(walkout.line_ids.student_id,
                         self.delegate | self.subdelegate | self.classmate | self.offline)
        self.assertEqual(walkout.line_ids.filtered('has_portal').student_id,
                         self.delegate | self.subdelegate | self.classmate)
        self.assertEqual(walkout.attachment_ids.mapped('name'), ['union_call.pdf'])
        self.assertEqual((walkout.phase_hours, walkout.notice_hours), (24, 48))
        # No group schedule: the email goes now, and the vote lasts 24 school hours from it.
        self.assertAlmostEqual(walkout.vote_start, fields.Datetime.now(), delta=timedelta(minutes=1))
        self.assertAlmostEqual(walkout.vote_until, walkout.vote_start + timedelta(hours=24), delta=timedelta(hours=1))
        self.assertFalse(walkout.join_until)
        mails = self._mails(walkout.line_ids)
        self.assertEqual(len(mails), 3, "The group vote email, to each student with portal access.")
        self.assertNotIn(self.offline.student_email, ' '.join(mails.mapped('email_to')))
        self.assertTrue(self.classmate.sudo()._ems_walkout_portal_visible())
        # The tutor gets a copy at once, to abort it if needed; the Head of Studies nothing until
        # the minute.
        self.assertEqual(self._tutor_mails(walkout).mapped('email_to'), [self.tutor.email_formatted])
        self.assertNotIn(self.head_of_studies.email, ' '.join(self._mails(walkout).mapped('email_to')))
        self.assertFalse(self._notices(walkout))
        self.assertFalse(walkout.activity_ids)
        # The cron is woken up when the vote ends.
        cron = self.env.ref('ems.ir_cron_student_walkout_deadlines')
        self.assertTrue(self.env['ir.cron.trigger'].sudo().search([('cron_id', '=', cron.id),
                                                                   ('call_at', '=', walkout.vote_until)]))

    def test_name_in_the_centre_language(self):
        """The name is stored and names the minute: in the centre's date format, whoever opens it."""
        self.env.company.ems_lang = 'ca_ES'
        self.env = self.env(context=dict(self.env.context, lang='en_US'))  # e.g. an English portal user
        walkout = open_walkout(self)
        self.assertEqual(walkout.name, f"{self.group.name} - {walkout.walkout_date.strftime('%d/%m/%Y')}")

    def test_sub_delegate_may_call_but_not_a_classmate_or_a_family(self):
        self.assertTrue(open_walkout(self, self.subdelegate))
        for partner in (self.classmate, self.family):
            with self.assertRaises(UserError):
                open_walkout(self, partner, days=8)

    def test_level_and_course_allowlist(self):
        self.level.walkout_allowed = False
        with self.assertRaises(UserError):
            open_walkout(self)
        self.level.write({'walkout_allowed': True, 'walkout_course_from': 4})
        with self.assertRaises(UserError):
            open_walkout(self)
        self.level.write({'walkout_course_from': 1, 'walkout_course_to': 2})
        with self.assertRaises(UserError):
            open_walkout(self)
        self.level.write({'walkout_course_from': 3, 'walkout_course_to': 0})
        self.assertTrue(open_walkout(self))
        self.assertFalse(self.offline.sudo()._ems_walkout_portal_visible(),
                         "Somebody with no portal access never sees it.")

    def test_notice_in_school_hours(self):
        """Opened on Monday at 10:00: vote until Tuesday 10:00, joining until Wednesday 10:00, and the
        minute 48 school hours before the walkout: Friday (38 hours) is too soon, the weekend does
        not count, next Monday is the first day."""
        with self.assertRaisesRegex(UserError, 'too late'):
            open_walkout(self, days=4)
        with self.assertRaisesRegex(UserError, 'school day'):
            open_walkout(self, days=5)  # Saturday
        Walkout = self.env['ems.student_walkout']
        self.assertEqual(Walkout._ems_first_walkout_day(self._calendar(fields.Datetime.now())),
                         self.today + timedelta(days=7))
        self.assertTrue(open_walkout(self, days=7))

    def test_school_hours_cross_a_break_longer_than_the_search_window(self):
        """A call shown or opened in July while the summer break runs past the first window of days
        read (hours / 24 * 3 + 60): the count goes on until the first school day instead of looping
        for ever."""
        Walkout = self.env['ems.student_walkout']
        start = fields.Datetime.now()
        break_end = fields.Date.to_date(start) + timedelta(days=120)

        def holiday_dates(_leaves, date_from, date_to):
            return {date_from + timedelta(days=n) for n in range((min(date_to, break_end) - date_from).days + 1)}

        with patch.object(type(self.env['resource.calendar.leaves']), '_ems_holiday_dates', holiday_dates):
            end = Walkout.ems_add_school_hours(start, 24)
        self.assertGreater(Walkout._ems_local_wall(end).date(), break_end)
        self.assertLess(Walkout._ems_local_wall(end).date(), break_end + timedelta(days=4))

    def test_notice_boundary_is_exact(self):
        """Opened on Monday at 00:00: the minute on Wednesday at 00:00, exactly 48 school hours before
        Friday. A minute later, Friday is too soon."""
        Walkout = self.env['ems.student_walkout']
        friday = self.today + timedelta(days=4)
        at_midnight = self._calendar(self._local(0, 0.0))
        self.assertEqual(at_midnight['join_until'], self._local(2, 0.0))
        Walkout._ems_check_request_date(friday, at_midnight)
        with self.assertRaises(UserError):
            Walkout._ems_check_request_date(friday, self._calendar(self._local(0, 0.0) + timedelta(minutes=1)))

    def test_weekends_and_holidays_do_not_count(self):
        Walkout = self.env['ems.student_walkout']
        # Friday 13:00 + 24 school hours = Monday 13:00; joining until Tuesday 13:00.
        friday = self._calendar(self._local(4, 13.0))
        self.assertEqual((friday['vote_until'], friday['join_until']), (self._local(7, 13.0), self._local(8, 13.0)))
        # A public holiday on Tuesday: Monday 10:00 votes until Wednesday 10:00.
        add_holiday(self, self.today + timedelta(days=1))
        calendar = self._calendar(self._local(0, 10.0))
        self.assertEqual((calendar['vote_until'], calendar['join_until']), (self._local(2, 10.0), self._local(3, 10.0)))
        with self.assertRaises(UserError):
            Walkout._ems_check_request_date(self.today + timedelta(days=1), calendar)  # a holiday
        self.assertEqual(Walkout._ems_first_walkout_day(calendar), self.today + timedelta(days=8))

    def test_calendar_follows_the_settings(self):
        self.env.company.write({'walkout_phase_hours': 12, 'walkout_notice_hours': 72})
        calendar = self._calendar(self._local(0, 10.0))
        self.assertEqual((calendar['vote_until'], calendar['join_until']), (self._local(0, 22.0), self._local(1, 10.0)))
        # Joining ends Tuesday 10:00; 72 school hours later is Friday 10:00, so Monday is the first day.
        walkout = open_walkout(self)
        self.assertEqual((walkout.phase_hours, walkout.notice_hours), (12, 72))
        self.env.company.write({'walkout_phase_hours': 48})
        self._supported(walkout)
        self.assertAlmostEqual(walkout.join_until, walkout.join_start + timedelta(hours=12), delta=timedelta(hours=1),
                               msg="A call keeps the settings it was opened with.")
        with self.assertRaises(Exception):
            self.env.company.write({'walkout_phase_hours': 0})

    def test_union_call_is_required(self):
        with self.assertRaises(UserError):
            open_walkout(self, files=[])

    def test_one_call_per_group_and_day(self):
        walkout = open_walkout(self)
        with self.assertRaises(UserError):
            open_walkout(self, self.subdelegate)
        walkout._ems_portal_cancel(self.delegate)
        self.assertEqual(walkout.state, 'cancelled')
        self.assertFalse(self.classmate.sudo()._ems_walkout_calls(), "A cancelled call stays its delegate's.")
        self.assertTrue(open_walkout(self, self.subdelegate))

    def test_split_group_halves_sharing_the_delegate_vote_together(self):
        half = self.group.copy({'acronym': 'B'})
        half.write({'delegate_id': self.delegate.id, 'subdelegate_id': self.subdelegate.id})
        self.group.joinable_group_ids = half
        other = self.env['res.partner'].create({
            'name': 'WLK Other Half', 'contact_type': 'student', 'main_group_id': half.id,
            'student_id': next_student_id(),
        })
        walkout = open_walkout(self)
        self.assertEqual(walkout.group_ids, self.group | half)
        self.assertIn(other, walkout.line_ids.student_id)

    # Aborting

    def test_the_tutor_chain_may_abort_it_with_a_reason(self):
        walkout = open_walkout(self)
        for user in (self.tutor, self.department_chief, self.head_of_studies):
            self.assertTrue(walkout.with_user(user).can_abort, user.name)
        for user in (self.other_department_chief, self.other_head_of_studies):
            with self.assertRaises(Exception):  # outside the chain: they cannot even read it
                reject_walkout(walkout, user)
        with self.assertRaises(UserError):
            reject_walkout(walkout, self.tutor, 'ems.student_walkout_rejection_other')  # no details
        reject_walkout(walkout, self.tutor, 'ems.student_walkout_rejection_other', "A dockers' strike")
        self.assertEqual((walkout.state, walkout.rejected_by_id, walkout.rejected_from_state),
                         ('rejected', self.tutor, 'voting'))
        self.assertTrue(self.classmate.sudo()._ems_walkout_portal_visible(), "The group sees why on the portal.")
        # The Head of Studies is told of every aborted call, in the daily summary.
        notice = self._notices(walkout)
        self.assertEqual(notice.user_id, self.head_of_studies)
        self.assertIn("A dockers", str(notice.body))

    def test_the_system_administrator_is_at_the_top(self):
        """Above Direction, outside the hierarchy: may abort a call and validate another."""
        admin = create_role_user(self, 'settings_admin', 'test_walkout_sysadmin_wlk', name='WLK System Administrator')
        walkout = open_walkout(self)
        self.assertTrue(walkout.with_user(admin).can_abort)
        reject_walkout(walkout, admin, 'ems.student_walkout_rejection_region')
        self.assertEqual((walkout.state, walkout.rejected_by_id), ('rejected', admin))
        closed = open_walkout(self, days=8)
        self._supported(closed)
        self._join(closed, self.delegate)
        end_phase(closed)
        closed.with_user(admin).action_generate_justification()
        self.assertEqual(closed.state, 'justified')
        justification = closed.justification_id
        reject_walkout(closed, admin, 'ems.student_walkout_rejection_no_call')  # undoes the validation
        self.assertEqual(closed.state, 'rejected')
        self.assertFalse(justification.exists())

    def test_co_tutors_of_a_split_group(self):
        half = self.group.copy({'acronym': 'B'})
        co_tutor = create_role_user(self, 'tutor', 'test_walkout_cotutor_wlk', name='WLK Co-tutor',
                                    email='cotutor.wlk@example.com')
        half.write({'delegate_id': self.delegate.id, 'subdelegate_id': self.subdelegate.id,
                    'tutor_id': create_role_employee(self, co_tutor).id})
        self.group.joinable_group_ids = half
        walkout = open_walkout(self)
        recipients = ' '.join(self._mails(walkout).mapped('email_to'))
        self.assertIn(self.tutor.email, recipients)
        self.assertIn(co_tutor.email, recipients)
        self.assertTrue(walkout.with_user(co_tutor).can_abort)

    def test_a_group_with_no_tutor_goes_to_every_head_of_studies(self):
        self.group.tutor_id = False
        walkout = open_walkout(self)
        recipients = ' '.join(self._mails(walkout).mapped('email_to'))
        self.assertIn(self.head_of_studies.email, recipients)
        for user in (self.head_of_studies, self.other_head_of_studies):
            walkout.with_user(user).check_access('read')
            self.assertTrue(walkout.with_user(user).can_abort, user.name)
        self.assertFalse(walkout.with_user(self.tutor).can_abort)

    # Group vote

    def test_group_vote_is_anonymous_and_counted_once(self):
        walkout = open_walkout(self)
        self._vote(walkout, self.classmate, 'yes')
        with self.assertRaises(UserError):
            self._vote(walkout, self.classmate, 'no')
        line = walkout.line_ids.filtered(lambda line: line.student_id == self.classmate)
        self.assertTrue(line.voted)
        self.assertEqual((walkout.group_yes_count, walkout.group_no_count), (1, 0))
        self.assertFalse({'group_vote', 'vote'} & set(line._fields), "The line never keeps the group vote.")
        with self.assertRaises(UserError):
            self._join(walkout, self.classmate)  # joining comes after the group vote

    def test_only_students_with_portal_access_of_the_group_vote(self):
        walkout = open_walkout(self)
        with self.assertRaises(UserError):
            self._vote(walkout, self.offline)
        with self.assertRaises(UserError):
            self._vote(walkout, self.family)

    def test_vote_ends_early_once_everybody_voted(self):
        walkout = open_walkout(self)
        self._vote(walkout, self.delegate, 'yes')
        self._vote(walkout, self.subdelegate, 'no')
        self.assertEqual(walkout.state, 'voting', "The last vote still decides it.")
        before = self._mails(walkout.line_ids)
        self._vote(walkout, self.classmate, 'yes')
        self.assertEqual(walkout.state, 'joining', "Everybody voted and more said yes: joining opens at once.")
        joining_mails = self._mails(walkout.line_ids) - before
        self.assertEqual(len(joining_mails), 3, "Each student is told the result and that they can join.")
        self.assertAlmostEqual(walkout.join_start, fields.Datetime.now(), delta=timedelta(minutes=1))
        self.assertAlmostEqual(walkout.join_until, walkout.join_start + timedelta(hours=24), delta=timedelta(hours=1))

    def test_vote_ends_early_once_the_result_is_decided(self):
        """Two yes out of three: the last vote can no longer change it. Two no (or a tie at best):
        the group cannot support it."""
        walkout = open_walkout(self)
        self._supported(walkout)
        self.assertEqual(walkout.voted_count, 2)
        other = open_walkout(self, days=8)
        self._vote(other, self.delegate, 'abstain')
        self.assertEqual(other.state, 'voting', "1 abstention: two votes could still say yes.")
        self._vote(other, self.subdelegate, 'no')
        self.assertEqual(other.state, 'closed', "The last yes would only tie: not supported.")
        self.assertFalse(other.group_supports)
        self.assertTrue(other.pdf_attachment_id)

    def test_students_may_answer_before_the_phase_starts(self):
        """The email may wait for the group's next class, but the portal lets them vote meanwhile
        (e.g. on the weekend)."""
        walkout = open_walkout(self)
        walkout.sudo().vote_start = fields.Datetime.now() + timedelta(days=2)
        self._vote(walkout, self.classmate, 'yes')
        self.assertEqual(walkout.group_yes_count, 1)

    def test_a_group_that_does_not_support_it_closes_and_justifies_nobody(self):
        walkout = open_walkout(self)
        self._vote(walkout, self.delegate, 'yes')
        self._vote(walkout, self.subdelegate, 'no')
        end_phase(walkout)  # the vote ends with a tie
        self.assertEqual(walkout.state, 'closed')
        self.assertFalse(walkout.group_supports)
        self.assertTrue(walkout.pdf_attachment_id, "The minute goes to the Head of Studies all the same.")
        self.assertFalse(walkout.activity_ids)
        with self.assertRaises(UserError):
            walkout.with_user(self.head_of_studies).action_generate_justification()

    # Joining

    def test_join_can_be_changed_until_the_joining_day_ends(self):
        walkout = open_walkout(self)
        self._supported(walkout)
        self._join(walkout, self.classmate, True)
        self._join(walkout, self.classmate, False)
        self._join(walkout, self.delegate, True)
        self.assertEqual(walkout.joining_student_ids, self.delegate)
        end_phase(walkout)  # the joining ends
        self.assertEqual(walkout.state, 'closed')
        with self.assertRaises(UserError):
            self._join(walkout, self.classmate, True)

    def test_closing_sends_the_minute_and_the_task(self):
        walkout = open_walkout(self)
        self._supported(walkout)
        self._join(walkout, self.delegate)
        self._join(walkout, self.subdelegate)
        end_phase(walkout)
        self.assertEqual(walkout.state, 'closed')
        self.assertTrue(walkout.pdf_attachment_id)
        self.assertGreaterEqual(walkout.ems_school_hours_between(walkout.closed_datetime, walkout.walkout_start),
                                walkout.notice_hours, "The minute arrives with the notice kept.")
        self.assertEqual(walkout.joining_student_ids, self.delegate | self.subdelegate)
        head_mail = self._mails(walkout).filtered('attachment_ids')
        self.assertEqual(len(head_mail), 1)
        self.assertIn(self.head_of_studies.email, head_mail.email_to)
        self.assertEqual(head_mail.attachment_ids.mimetype, 'application/pdf')
        self.assertEqual(walkout.activity_ids.user_id, self.head_of_studies)
        self.assertEqual(len(self._family_mails(walkout)), 1,
                         "Only the request to ratify that the minor joins: the result waits for the validation.")
        self.assertIn(self.tutor.email, ' '.join(self._mails(walkout).mapped('email_to')), "The tutor is told.")

    def test_generate_the_justification(self):
        walkout = open_walkout(self)
        self._supported(walkout)
        self._join(walkout, self.delegate)
        self._join(walkout, self.classmate)
        ratify(walkout, self.family, self.classmate)
        end_phase(walkout)
        # The classmate already has a justification that day: skipped, and said.
        Justification = self.env['ems.attendance_justification']
        Justification.create({
            'teacher_id': self.group.tutor_id.id, 'student_ids': [(6, 0, self.classmate.ids)],
            'reason_id': self.env.ref('ems.attendance_justification_reason_health').id,
            **Justification._whole_day_vals(walkout.walkout_date),
        })
        before = self._mails(walkout.line_ids)
        with self.assertRaises(UserError):
            walkout.with_user(self.tutor).action_generate_justification()  # the Head of Studies validates
        walkout.with_user(self.head_of_studies).action_generate_justification()
        justification = walkout.justification_id
        self.assertEqual(walkout.state, 'justified')
        # Validated: each student with portal access is told, and the family of the joining minor
        # (not the adult delegate's, nor the family of the minor who does not join).
        validated = self._mails(walkout.line_ids) - before
        self.assertEqual(len(validated.filtered(lambda mail: '@example.com' in mail.email_to
                                                and self.family.email not in mail.email_to)), 3)
        self.assertEqual(len(self._family_mails(walkout)), 2, "The request to ratify, then the validation.")
        self.assertEqual(justification.reason_id, self.env.ref('ems.attendance_justification_reason_walkout'))
        self.assertEqual(justification.day, walkout.walkout_date)
        self.assertEqual(justification.student_ids, self.delegate)
        self.assertFalse(walkout.activity_ids, "The task is done.")
        self.assertIn(self.classmate.name, walkout.message_ids.mapped('body')[0])

    # The families of minors ratify

    def test_a_minor_joining_needs_the_family_to_ratify_it(self):
        walkout = open_walkout(self)
        self._supported(walkout)
        self._join(walkout, self.delegate)  # an adult: nothing to ratify
        delegate_line = walkout.line_ids.filtered(lambda line: line.student_id == self.delegate)
        self.assertFalse(delegate_line.needs_ratification)
        self._join(walkout, self.classmate)
        line = walkout.line_ids.filtered(lambda line: line.student_id == self.classmate)
        self.assertEqual((line.needs_ratification, line.ratification), (True, 'pending'))
        self.assertEqual(len(self._family_mails(walkout)), 1, "The family is asked at once.")
        ratify(walkout, self.family, self.classmate)
        self.assertEqual((line.ratification, line.ratified_by_id), ('ratified', self.family))
        self.assertEqual(walkout.justifiable_student_ids, self.delegate | self.classmate)
        # Withdrawing clears it; joining again asks the family again.
        self._join(walkout, self.classmate, False)
        self.assertFalse(line.needs_ratification or line.ratification)
        self._join(walkout, self.classmate)
        self.assertEqual(line.ratification, 'pending')
        self.assertEqual(len(self._family_mails(walkout)), 2)

    def test_a_family_that_refuses_is_heard_and_the_student_told(self):
        walkout = open_walkout(self)
        self._supported(walkout)
        self._join(walkout, self.subdelegate)
        before = self._mails(walkout.line_ids)
        ratify(walkout, self.family, self.subdelegate, False)
        line = walkout.line_ids.filtered(lambda line: line.student_id == self.subdelegate)
        self.assertEqual(line.ratification, 'refused')
        self.assertIn(self.subdelegate.student_email, ' '.join((self._mails(walkout.line_ids) - before).mapped('email_to')))
        self.assertFalse(walkout.justifiable_student_ids)
        ratify(walkout, self.family, self.subdelegate)  # it can change its answer while joining lasts
        self.assertEqual(line.ratification, 'ratified')

    def test_only_a_family_with_portal_access_ratifies_while_joining_lasts(self):
        walkout = open_walkout(self)
        self._supported(walkout)
        self._join(walkout, self.classmate)
        no_portal = self.env['res.partner'].create({'name': 'WLK Father', 'contact_type': 'family',
                                                    'email': 'father.wlk@example.com'})
        self.env['res.partner.relation'].create({
            'left_partner_id': no_portal.id, 'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': self.classmate.id})
        for partner in (no_portal, self.delegate):  # no portal access; not the classmate's family
            with self.assertRaises(UserError):
                ratify(walkout, partner, self.classmate)
        end_phase(walkout)
        with self.assertRaises(UserError):
            ratify(walkout, self.family, self.classmate)

    def test_the_age_counts_on_the_walkout_day(self):
        walkout = open_walkout(self)
        self._supported(walkout)
        # 18 before the walkout day: an adult then, nothing to ratify; no birth date: a minor.
        self.classmate.birth_date = walkout.walkout_date - relativedelta(years=18)
        self.subdelegate.birth_date = False
        self._join(walkout, self.classmate)
        self._join(walkout, self.subdelegate)
        lines = {line.student_id: line for line in walkout.line_ids}
        self.assertFalse(lines[self.classmate].needs_ratification)
        self.assertTrue(lines[self.subdelegate].needs_ratification)

    def test_the_family_asked_to_ratify_is_told_why_it_ended(self):
        """Its email says what happened: aborted while joining, not validated once closed."""
        walkout = open_walkout(self)
        self._supported(walkout)
        self._join(walkout, self.classmate)
        before = self._family_mails(walkout)
        reject_walkout(walkout, self.tutor, 'ems.student_walkout_rejection_region')
        mail = self._family_mails(walkout) - before
        self.assertEqual(len(mail), 1)
        self.assertIn('aborted', mail.body_html)
        self.assertNotIn('withdrawn the validation', mail.body_html)

    def test_only_adults_and_ratified_minors_are_justified(self):
        walkout = open_walkout(self)
        self._supported(walkout)
        for student in (self.delegate, self.subdelegate, self.classmate):
            self._join(walkout, student)
        ratify(walkout, self.family, self.subdelegate)  # the classmate's stays pending
        end_phase(walkout)
        self.assertEqual(walkout.joining_student_ids, self.delegate | self.subdelegate | self.classmate)
        self.assertEqual(walkout.justifiable_student_ids, self.delegate | self.subdelegate)
        walkout.with_user(self.head_of_studies).action_generate_justification()
        self.assertEqual(walkout.justification_id.student_ids, self.delegate | self.subdelegate)

    def test_only_unratified_minors_join_so_nothing_to_justify(self):
        walkout = open_walkout(self)
        self._supported(walkout)
        self._join(walkout, self.classmate)
        end_phase(walkout)
        self.assertFalse(walkout.activity_ids, "No task: nobody can be justified.")
        with self.assertRaises(UserError):
            walkout.with_user(self.head_of_studies).action_generate_justification()

    # Aborted or not validated

    def test_aborted_while_voting_tells_the_group(self):
        walkout = open_walkout(self)
        self._vote(walkout, self.classmate, 'yes')
        before = self._mails(walkout.line_ids)
        reject_walkout(walkout, self.tutor, 'ems.student_walkout_rejection_region')
        self.assertEqual(walkout.state, 'rejected')
        recipients = ' '.join((self._mails(walkout.line_ids) - before).mapped('email_to'))
        for student in (self.delegate, self.subdelegate, self.classmate):
            self.assertIn(student.student_email, recipients, "The whole group knew of it: all of them are told.")
        self.assertNotIn(self.family.email, recipients, "The families had not been told anything yet.")
        self.assertTrue(self.classmate.sudo()._ems_walkout_portal_visible(), "The group sees why on the portal.")
        with self.assertRaises(UserError):
            self._vote(walkout, self.subdelegate)

    def test_rejected_after_justifying_undoes_the_justification(self):
        walkout = open_walkout(self)
        self._supported(walkout)
        self._join(walkout, self.delegate)
        self._join(walkout, self.subdelegate)
        ratify(walkout, self.family, self.subdelegate)
        end_phase(walkout)
        walkout.with_user(self.head_of_studies).action_generate_justification()
        justification = walkout.justification_id
        before = self._mails(walkout.line_ids)
        reject_walkout(walkout, self.head_of_studies, 'ems.student_walkout_rejection_no_call')
        self.assertEqual((walkout.state, walkout.rejected_from_state), ('rejected', 'justified'))
        self.assertFalse(justification.exists(), "The walkout day is no longer justified.")
        self.assertFalse(self._notices(walkout), "Not an aborted call: no notice.")
        self.assertIn(self.family.email, ' '.join((self._mails(walkout.line_ids) - before).mapped('email_to')),
                      "The family told that their child joined is told it was rejected.")

    def test_not_validated_removes_the_task_and_tells_the_family_asked(self):
        walkout = open_walkout(self)
        self._supported(walkout)
        self._join(walkout, self.subdelegate)
        ratify(walkout, self.family, self.subdelegate)
        self._join(walkout, self.delegate)  # an adult who does not share with a family: no family to tell
        end_phase(walkout)
        self.assertTrue(walkout.activity_ids)
        self.assertFalse(walkout.with_user(self.tutor).can_abort, "Closed: no longer the tutor's.")
        with self.assertRaises(UserError):
            reject_walkout(walkout, self.tutor, 'ems.student_walkout_rejection_level')
        before = self._mails(walkout.line_ids)
        reject_walkout(walkout, self.head_of_studies, 'ems.student_walkout_rejection_level')
        self.assertFalse(walkout.activity_ids)
        told = self._mails(walkout.line_ids) - before
        self.assertEqual(len(told.filtered(lambda mail: self.family.email not in mail.email_to)), 3,
                         "Every student is told.")
        self.assertEqual(len(told.filtered(lambda mail: self.family.email in mail.email_to)), 1,
                         "The family asked to ratify is told too.")
        with self.assertRaises(UserError):
            reject_walkout(walkout, self.head_of_studies, 'ems.student_walkout_rejection_level')

    # School hours

    def test_phases_start_when_the_email_reaches_the_group(self):
        calendar = self.env['resource.calendar'].create({'name': 'WLK schedule', 'attendance_ids': [(5, 0, 0)]})
        slot = self.env['resource.calendar.attendance'].create([{
            'name': f'WLK {day}', 'calendar_id': calendar.id, 'dayofweek': str(day), 'hour_from': 15.0,
            'hour_to': 16.0, 'group_ids': [(6, 0, self.group.ids)],
        } for day in range(5)])
        # Monday 10:00, class from 15:00: the email waits, and the vote runs from then.
        walkout = open_walkout(self)
        self.assertEqual((walkout.vote_start, walkout.vote_until), (self._local(0, 15.0), self._local(1, 15.0)))
        self.assertEqual(set(self._mails(walkout.line_ids).mapped('scheduled_date')), {walkout.vote_start})
        # Opened on Friday at 20:00, with classes from 8:00: the vote runs from Monday 8:00 to Tuesday 8:00.
        slot.write({'hour_from': 8.0, 'hour_to': 14.0})
        friday = self._calendar(self._local(4, 20.0))
        self.assertEqual((friday['vote_start'], friday['vote_until'], friday['join_until']),
                         (self._local(7, 8.0), self._local(8, 8.0), self._local(9, 8.0)))
        # During the group's classes it goes at once.
        walkout2 = open_walkout(self, self.subdelegate, days=8)
        self.assertFalse(any(self._mails(walkout2.line_ids).mapped('scheduled_date')))

    # Permissions and seed

    def test_hierarchy_scope(self):
        walkout = open_walkout(self)
        walkout.with_user(self.tutor).check_access('read')
        walkout.with_user(self.head_of_studies).check_access('read')
        with self.assertRaises(AccessError):
            walkout.with_user(self.other_head_of_studies).check_access('read')
        with self.assertRaises(AccessError):
            walkout.line_ids.with_user(self.tutor).write({'joins': False})

    def test_settings_edit_the_levels_and_courses(self):
        """Settings > Levels and courses: whoever enters Settings (a settings administrator, who is
        not an academic administrator) sets the three walkout fields, and nothing else of the level."""
        settings_admin = create_role_user(self, 'settings_admin', 'test_walkout_settings_admin')
        Wizard = self.env['ems.walkout.levels.wizard'].with_user(settings_admin)
        wizard = Wizard.create({})
        line = wizard.line_ids.filtered(lambda line: line.level_id == self.level)
        self.assertTrue(line.walkout_allowed)
        line.write({'walkout_course_from': 2, 'walkout_course_to': 4})
        wizard.action_save()
        self.assertEqual((self.level.walkout_course_from, self.level.walkout_course_to), (2, 4))
        with self.assertRaises(AccessError):
            self.env['ems.walkout.levels.wizard'].with_user(self.tutor).create({})

    def test_seed_follows_the_law(self):
        Level = self.env['ems.level']
        levels = {acronym: Level.search([('acronym', '=', acronym)]) for acronym in ('ESO', 'BTX', 'CFGM', 'PFI')}
        if not all(levels.values()):
            self.skipTest("The catalog levels are not installed.")
        Level.search([]).write({'walkout_allowed': False, 'walkout_course_from': 0})
        Level._ems_seed_walkout_levels()
        self.assertTrue(levels['ESO'].walkout_allowed)
        self.assertEqual(levels['ESO'].walkout_course_from, 3)
        self.assertTrue(levels['BTX'].walkout_allowed and levels['CFGM'].walkout_allowed)
        self.assertFalse(levels['PFI'].walkout_allowed)
