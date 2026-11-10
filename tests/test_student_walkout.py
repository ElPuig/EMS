from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from .common import (create_head_of_studies_branch, create_level_study_group, create_role_employee,
                     create_role_user, mock_outgoing_email, next_student_id, shift_ems_clock)

PDF = b'%PDF-1.4 test union call'


def create_walkout_fixtures(cls, prefix):
    """A 3rd-year group of an allowed level with a tutor below a Head of Studies, its delegate (an
    adult), its sub-delegate and a classmate (minors with a family), all three with portal access,
    and a student without it. Fictitious data and addresses only (CLAUDE.md, "Email safety")."""
    cls.today = shift_ems_clock(cls).date()
    cls.level, cls.study, cls.group = create_level_study_group(
        cls, prefix, level={'walkout_allowed': True}, group={'course': 3})
    cls.tutor = create_role_user(cls, 'tutor', f'test_walkout_tutor_{prefix.lower()}', name=f'{prefix} Tutor')
    cls.group.tutor_id = create_role_employee(cls, cls.tutor)
    create_head_of_studies_branch(cls, prefix, cls.group.tutor_id)
    cls.head_of_studies.email = f'hos.{prefix.lower()}@example.com'

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


def open_walkout(cls, partner=None, days=3, close_days=None, files=None, **values):
    """Opens a call as `partner` (the delegate by default) for `days` from today, closing as late as
    the notice period allows unless `close_days` says otherwise."""
    notice = cls.env.company.walkout_notice_days
    walkout_date = cls.today + timedelta(days=days)
    close_date = cls.today + timedelta(days=close_days) if close_days is not None \
        else walkout_date - timedelta(days=notice)
    return cls.env['ems.student_walkout'].sudo()._ems_portal_open(partner or cls.delegate, {
        'walkout_date': walkout_date, 'close_date': close_date, 'notes': 'Union call', **values,
    }, files if files is not None else [('union_call.pdf', PDF)])


@tagged('post_install', '-at_install')
class TestStudentWalkout(TransactionCase):
    """Issue #800: a student walkout called by the group's delegate, voted by the group and
    justified by the Head of Studies. See docs/en/developers/attendance/student_walkout.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.env.company.walkout_notice_days = 2
        create_walkout_fixtures(cls, 'WLK')

    def _mails(self, records):
        return self.env['mail.mail'].sudo().search([('model', '=', records._name), ('res_id', 'in', records.ids)])

    def _vote(self, walkout, partner, group_vote='yes', joins=True):
        walkout._ems_portal_vote(partner, group_vote, joins)

    # Opening

    def test_delegate_opens_a_call_for_the_whole_group(self):
        walkout = open_walkout(self)
        self.assertEqual(walkout.state, 'voting')
        self.assertEqual(walkout.opener_id, self.delegate)
        self.assertEqual(walkout.line_ids.student_id,
                         self.delegate | self.subdelegate | self.classmate | self.offline)
        self.assertEqual(walkout.line_ids.filtered('has_portal').student_id,
                         self.delegate | self.subdelegate | self.classmate)
        self.assertEqual(walkout.attachment_ids.mapped('name'), ['union_call.pdf'])
        # One call email per student with portal access, none for the one without it.
        mails = self._mails(walkout.line_ids)
        self.assertEqual(len(mails), 3)
        self.assertNotIn(self.offline.student_email, ' '.join(mails.mapped('email_to')))

    def test_sub_delegate_may_open_but_not_a_classmate_or_a_family(self):
        self.assertTrue(open_walkout(self, self.subdelegate))
        for partner in (self.classmate, self.family):
            with self.assertRaises(UserError):
                open_walkout(self, partner, days=4)

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

    def test_notice_period_in_days(self):
        with self.assertRaisesRegex(UserError, '2 days'):
            open_walkout(self, days=1, close_days=1)
        with self.assertRaises(UserError):
            open_walkout(self, days=3, close_days=2)  # later than the walkout day minus the notice
        with self.assertRaises(UserError):
            open_walkout(self, days=3, close_days=0)  # nobody could vote
        self.env.company.walkout_notice_days = 3
        with self.assertRaises(UserError):
            open_walkout(self, days=2, close_days=1)
        self.assertTrue(open_walkout(self, days=4, close_days=1))

    def test_union_call_is_required(self):
        with self.assertRaises(UserError):
            open_walkout(self, files=[])

    def test_one_call_per_group_and_day(self):
        walkout = open_walkout(self)
        with self.assertRaises(UserError):
            open_walkout(self, self.subdelegate)
        walkout._ems_portal_cancel(self.delegate)
        self.assertEqual(walkout.state, 'cancelled')
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

    # Voting

    def test_group_vote_is_anonymous_and_counted_once(self):
        walkout = open_walkout(self)
        self._vote(walkout, self.classmate, 'yes', True)
        self._vote(walkout, self.classmate, 'no', False)  # only "I join" changes
        line = walkout.line_ids.filtered(lambda line: line.student_id == self.classmate)
        self.assertTrue(line.voted)
        self.assertFalse(line.joins)
        self.assertEqual((walkout.group_yes_count, walkout.group_no_count), (1, 0))
        self.assertFalse({'group_vote', 'vote'} & set(line._fields), "The line never keeps the group vote.")

    def test_only_students_with_portal_access_of_the_group_vote(self):
        walkout = open_walkout(self)
        with self.assertRaises(UserError):
            self._vote(walkout, self.offline)
        with self.assertRaises(UserError):
            self._vote(walkout, self.family)

    def test_majority_of_votes_cast(self):
        walkout = open_walkout(self)
        self._vote(walkout, self.delegate, 'yes')
        self._vote(walkout, self.subdelegate, 'no')
        self._vote(walkout, self.classmate, 'abstain')
        self.assertFalse(walkout.group_supports, "A tie does not support it; abstentions do not count.")
        walkout.group_no_count = 0
        self.assertTrue(walkout.group_supports)

    # Closing

    def test_cron_closes_on_the_close_date_only(self):
        walkout = open_walkout(self)
        self.env['ems.student_walkout']._cron_ems_close_due()
        self.assertEqual(walkout.state, 'voting')
        walkout.close_date = self.today
        with self.assertRaises(UserError):
            self._vote(walkout, self.classmate)  # the vote ended yesterday
        self.env['ems.student_walkout']._cron_ems_close_due()
        self.assertEqual(walkout.state, 'closed')

    def test_closing_sends_the_minute_and_the_task(self):
        walkout = open_walkout(self)
        self._vote(walkout, self.delegate, 'yes', True)
        self._vote(walkout, self.subdelegate, 'yes', True)
        self._vote(walkout, self.classmate, 'no', False)
        walkout._ems_portal_close(self.delegate)
        self.assertEqual(walkout.state, 'closed')
        self.assertTrue(walkout.pdf_attachment_id)
        self.assertEqual(walkout.joining_student_ids, self.delegate | self.subdelegate)
        head_mail = self._mails(walkout)
        self.assertEqual(len(head_mail), 1)
        self.assertIn(self.head_of_studies.email, head_mail.email_to)
        self.assertEqual(head_mail.attachment_ids.mimetype, 'application/pdf')
        self.assertEqual(walkout.activity_ids.user_id, self.head_of_studies)
        # The family of the joining minor is told; the adult delegate's family is not involved,
        # nor the family of the minor who does not join.
        family_mails = self._mails(walkout.line_ids).filtered(lambda mail: self.family.email in (mail.email_to or ''))
        self.assertEqual(len(family_mails), 1)

    def test_a_group_that_does_not_support_it_justifies_nobody(self):
        walkout = open_walkout(self)
        self._vote(walkout, self.delegate, 'no', True)
        walkout.action_close()
        self.assertFalse(walkout.activity_ids)
        with self.assertRaises(UserError):
            walkout.with_user(self.head_of_studies).action_generate_justification()

    def test_generate_the_justification(self):
        walkout = open_walkout(self)
        self._vote(walkout, self.delegate, 'yes', True)
        self._vote(walkout, self.classmate, 'yes', True)
        walkout.action_close()
        # The classmate already has a justification that day: skipped, and said.
        Justification = self.env['ems.attendance_justification']
        Justification.create({
            'teacher_id': self.group.tutor_id.id, 'student_ids': [(6, 0, self.classmate.ids)],
            'reason_id': self.env.ref('ems.attendance_justification_reason_health').id,
            **Justification._whole_day_vals(walkout.walkout_date),
        })
        walkout.with_user(self.head_of_studies).action_generate_justification()
        justification = walkout.justification_id
        self.assertEqual(walkout.state, 'justified')
        self.assertEqual(justification.reason_id, self.env.ref('ems.attendance_justification_reason_walkout'))
        self.assertEqual(justification.day, walkout.walkout_date)
        self.assertEqual(justification.student_ids, self.delegate)
        self.assertFalse(walkout.activity_ids, "The task is done.")
        self.assertIn(self.classmate.name, walkout.message_ids.mapped('body')[0])

    # Permissions

    def test_hierarchy_scope(self):
        walkout = open_walkout(self)
        self._vote(walkout, self.delegate, 'yes', True)
        walkout.action_close()
        walkout.with_user(self.tutor).check_access('read')
        walkout.with_user(self.head_of_studies).check_access('read')
        with self.assertRaises(UserError):
            walkout.with_user(self.tutor).action_generate_justification()
        with self.assertRaises(AccessError):
            walkout.with_user(self.other_head_of_studies).check_access('read')
        with self.assertRaises(AccessError):
            walkout.line_ids.with_user(self.tutor).write({'joins': False})

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
