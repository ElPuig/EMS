import io
from datetime import timedelta
from unittest.mock import patch

import openpyxl

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import Request
from odoo.tests.common import HttpCase, TransactionCase, tagged
from odoo.addons.ems.models.erasmus.application import PARTICIPANT_HEADERS

from .common import create_level_study_group, create_role_employee, create_role_user, mock_outgoing_email, \
    next_student_id
from .test_erasmus import PDF


def create_group_mobility_fixtures(cls):
    """A KA121-VET project and an enrolling group mobility for the two morning groups of a test
    CFGM-like level (8 places, 2 teachers), ten adult students and a minor in those groups and a
    student of the afternoon group; the Erasmus coordinator, a mobility technician, the leader and
    the accompanying teacher, and another teacher (login doubles as password)."""
    cls.level, cls.study, cls.group_a = create_level_study_group(
        cls, 'TGMG', group={'course': 2, 'shift': 'morning'})
    cls.group_b, cls.group_c = cls.env['ems.group'].create([
        {'course': 2, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id, 'shift': 'morning'},
        {'course': 2, 'acronym': 'C', 'level_id': cls.level.id, 'study_id': cls.study.id, 'shift': 'afternoon'},
    ])
    cls.project = cls.env['ems.erasmus.project'].create({'name': 'TEST-GROUP-VET', 'kind': 'ka121_vet'})
    cls.students = cls.env['res.partner'].create([{
        'name': f'Group Test Student {index:02d}', 'contact_type': 'student', 'student_id': next_student_id(),
        'main_group_id': (cls.group_a if index % 2 else cls.group_b).id, 'birth_date': '2005-01-01',
        'email': f'group.student{index}@example.com', 'document_id': f'9100000{index}T'} for index in range(10)])
    cls.minor, cls.afternoon_student = cls.env['res.partner'].create([
        {'name': 'Group Test Minor', 'contact_type': 'student', 'student_id': next_student_id(),
         'main_group_id': cls.group_a.id, 'birth_date': fields.Date.today() - timedelta(days=16 * 365),
         'email': 'group.minor@example.com', 'document_id': '91000099T'},
        {'name': 'Group Test Afternoon', 'contact_type': 'student', 'student_id': next_student_id(),
         'main_group_id': cls.group_c.id, 'birth_date': '2005-01-01'},
    ])
    cls.coordinator_user = create_role_user(cls, 'erasmus_coordinator', 'test_group_coordinator')
    cls.technician_user = create_role_user(cls, 'erasmus', 'test_group_technician')
    cls.leader_user = create_role_user(cls, 'teacher', 'test_group_leader', name='Group Leader Teacher')
    cls.companion_user = create_role_user(cls, 'teacher', 'test_group_companion', name='Group Companion Teacher')
    cls.other_teacher_user = create_role_user(cls, 'teacher', 'test_group_other_teacher', name='Group Other Teacher')
    cls.leader, cls.companion, cls.other_teacher = (
        create_role_employee(cls, user) for user in (cls.leader_user, cls.companion_user, cls.other_teacher_user))
    now = fields.Datetime.now()
    cls.mobility = cls.env['ems.erasmus.group.mobility'].with_user(cls.coordinator_user).create({
        'name': 'Test SMX2 morning', 'project_id': cls.project.id, 'shift': 'morning',
        'group_ids': [(6, 0, (cls.group_a | cls.group_b).ids)],
        'leader_id': cls.leader.id, 'companion_ids': [(6, 0, cls.companion.ids)],
        'enrolment_open': now - timedelta(days=1), 'enrolment_close': now + timedelta(days=5),
        'date_start': fields.Date.today() + timedelta(days=90), 'date_end': fields.Date.today() + timedelta(days=104),
    })
    cls.mobility.with_user(cls.coordinator_user).action_open_enrolment()
    cls.env.company.strike_escalation_threshold = 3


class ErasmusGroupMobilityCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_group_mobility_fixtures(cls)

    def _enrol(self, partners, mobility=None, **kwargs):
        Registration = self.env['ems.erasmus.group.registration']
        return Registration.concat(*(Registration._ems_portal_enrol(mobility or self.mobility, partner, **kwargs)
                                     for partner in partners))

    def _close(self, averages, mobility=None):
        """Close the enrolment with these record averages ({partner: average}, 0 hours = none)."""
        def grades(partner, _course_name):
            average = averages.get(partner)
            return [] if average is None else [{'grade': average, 'hours': 100}]
        with patch.object(type(self.env['ems.erasmus.application']), '_ems_partner_grade_values',
                          side_effect=grades):
            (mobility or self.mobility).with_user(self.coordinator_user).action_close_enrolment()

    def _strikes(self, partner, count):
        return self.env['ems.strike'].create([{
            'student_id': partner.id, 'teacher_id': self.other_teacher.id,
            'date': fields.Datetime.now() - timedelta(minutes=index + 1)} for index in range(count)])

    def _ranked(self):
        """All ten students enrolled and ranked: averages 9.0, 8.5... in their order."""
        registrations = self._enrol(self.students)
        self._close({student: 9.0 - index * 0.5 for index, student in enumerate(self.students)})
        return registrations

    def _publish_provisional(self):
        """The coordinator publishes the provisional list, with the claims open for a week."""
        self.mobility.claims_deadline = fields.Datetime.now() + timedelta(days=7)
        self.mobility.with_user(self.coordinator_user).action_publish_provisional()

    def _claims_over(self):
        """The claims deadline has passed."""
        self.mobility.claims_deadline = fields.Datetime.now() - timedelta(minutes=1)

    def _approve(self):
        self._publish_provisional()
        self._claims_over()
        self.mobility.with_user(self.coordinator_user).action_approve_selection()

    def _approved(self):
        registrations = self._ranked()
        self.mobility.with_user(self.leader_user).action_submit_proposal()
        self._approve()
        return registrations

    def _family(self):
        """A family contact (the father) of the minor."""
        family = self.env['res.partner'].create({
            'name': 'Group Test Family', 'contact_type': 'family', 'email': 'group.family@example.com'})
        self.env['res.partner.relation'].create({
            'left_partner_id': family.id, 'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': self.minor.id})
        return family

    def _approved_with_minor(self):
        """The minor and seven adults selected: the minor's file."""
        self._enrol(self.minor | self.students[:7])
        self._close({**{student: 8.0 - index * 0.1 for index, student in enumerate(self.students[:7])},
                     self.minor: 5.0})
        self.mobility.with_user(self.leader_user).action_submit_proposal()
        self._approve()
        return self.mobility.participant_ids.filtered(lambda participant: participant.partner_id == self.minor)


@tagged('post_install', '-at_install')
class TestErasmusGroupEnrolment(ErasmusGroupMobilityCase):
    """Issue #701 - enrolment from the portal."""

    def test_eligible_student_enrols_once(self):
        registration = self._enrol(self.students[:1])
        self.assertEqual(registration.state, 'enrolled')
        self.assertTrue(registration.enrol_date)
        with self.assertRaises(UserError):
            self._enrol(self.students[:1])

    def test_student_of_another_group_cannot_enrol(self):
        with self.assertRaises(UserError):
            self._enrol(self.afternoon_student)
        self.assertNotIn(self.mobility, self.afternoon_student._ems_erasmus_group_mobilities())
        self.assertIn(self.mobility, self.students[0]._ems_erasmus_group_mobilities())
        self.assertTrue(self.students[0]._ems_erasmus_portal_visible())

    def test_only_while_the_enrolment_is_open(self):
        self.mobility.with_user(self.coordinator_user).enrolment_close = fields.Datetime.now() - timedelta(minutes=1)
        with self.assertRaises(UserError):
            self._enrol(self.students[:1])
        draft = self.mobility.copy({'name': 'Draft group'})
        self.assertEqual(draft.state, 'draft')
        with self.assertRaises(UserError):
            self._enrol(self.students[:1], mobility=draft)

    def test_withdraw_keeps_the_record_and_allows_enrolling_again(self):
        registration = self._enrol(self.students[:1])
        registration.sudo().action_withdraw()
        self.assertEqual(registration.state, 'withdrawn')
        self.assertTrue(registration.withdraw_date)
        self.assertEqual(self._enrol(self.students[:1]), registration)
        self.assertEqual(registration.state, 'enrolled')

    def test_too_many_conduct_warnings_cannot_enrol(self):
        self._strikes(self.students[0], 3)
        with self.assertRaises(UserError):
            self._enrol(self.students[:1])
        self._strikes(self.students[1], 2)
        self._enrol(self.students[1])

    def test_others_cannot_withdraw_an_enrolment(self):
        registration = self._enrol(self.students[:1])
        with self.assertRaises(AccessError):
            registration.with_user(self.leader_user).action_withdraw()

    def test_needs_groups_period_and_criteria_to_open(self):
        draft = self.mobility.copy({'name': 'Another group'})
        draft.tie_break = False
        with self.assertRaises(UserError):
            draft.with_user(self.coordinator_user).action_open_enrolment()
        with self.assertRaises(AccessError):
            self.mobility.copy().with_user(self.leader_user).action_open_enrolment()

    def test_only_a_ka121_vet_project(self):
        hed = self.env['ems.erasmus.project'].create({'name': 'TEST-GROUP-HED', 'kind': 'ka131_hed'})
        with self.assertRaises(ValidationError):
            self.mobility.project_id = hed

    def test_cron_closes_the_enrolment_when_it_ends(self):
        self._enrol(self.students[:2])
        self.mobility.enrolment_close = fields.Datetime.now() - timedelta(minutes=1)
        self.env['ems.erasmus.group.mobility']._cron_close_enrolments()
        self.assertEqual(self.mobility.state, 'selection')
        self.assertTrue(self.mobility.ranking_date)


@tagged('post_install', '-at_install')
class TestErasmusGroupRanking(ErasmusGroupMobilityCase):
    """Issue #702 - the ranking at closing time, frozen."""

    def test_grade_average_is_the_internship_calls(self):
        """The same record average as the internship call (weighted by the modules' hours)."""
        self._enrol(self.students[:1])
        lines = [{'grade': 8.0, 'hours': 100}, {'grade': 5.0, 'hours': 300}]
        with patch.object(type(self.env['ems.erasmus.application']), '_ems_partner_grade_values',
                          return_value=lines) as grade_values:
            self.mobility.action_close_enrolment()
        grade_values.assert_called_once()
        registration = self.mobility.registration_ids
        self.assertEqual(registration.grade_average, 5.75)
        self.assertEqual(registration.grade_average,
                         self.env['ems.erasmus.application']._ems_grade_average(lines)[0])
        self.assertTrue(registration.grade_found)

    def test_ranked_by_average_places_and_reserves(self):
        registrations = self._ranked()
        self.assertEqual(self.mobility.state, 'selection')
        self.assertEqual(registrations.mapped('rank'), list(range(1, 11)))
        self.assertEqual(registrations[:8].mapped('proposed_result'), ['selected'] * 8)
        self.assertEqual(registrations[8:].mapped('proposed_result'), ['reserve'] * 2)
        self.assertEqual(registrations[8:].mapped('reserve_position'), [1, 2])
        self.assertEqual(self.mobility.selected_count, 8)

    def test_two_warnings_are_eligible_three_are_excluded(self):
        registrations = self._enrol(self.students[:3])
        self._strikes(self.students[0], 2)
        self._strikes(self.students[1], 3)
        self._close({student: 7.0 for student in self.students[:3]})
        self.assertTrue(registrations[0].eligible)
        self.assertEqual(registrations[0].strike_count, 2)
        self.assertFalse(registrations[1].eligible)
        self.assertEqual(registrations[1].exclusion, 'conduct')
        self.assertEqual(registrations[1].proposed_result, 'excluded')
        self.assertEqual(registrations[1].rank, 0)

    def test_out_of_the_group_at_closing_is_excluded(self):
        registration = self._enrol(self.students[:1])
        self.students[0].main_group_id = self.group_c
        self._close({self.students[0]: 9.0})
        self.assertEqual(registration.exclusion, 'group')
        self.assertEqual(registration.frozen_group_id, self.group_c)

    def test_a_tie_blocks_the_proposal_until_the_coordinator_draws_it(self):
        registrations = self._enrol(self.students[:3])
        self._close({self.students[0]: 7.0, self.students[1]: 7.0, self.students[2]: 9.0})
        self.assertEqual(registrations.mapped('needs_draw'), [True, True, False])
        with self.assertRaises(UserError):
            self.mobility.with_user(self.leader_user).action_submit_proposal()
        with self.assertRaises(AccessError):
            registrations[1].with_user(self.coordinator_user).draw_order = 1
        for user in (self.leader_user, self.technician_user):
            with self.assertRaises(AccessError):
                self.mobility.with_user(user).action_draw_ties()
        self.mobility.with_user(self.coordinator_user).action_draw_ties()
        self.assertFalse(self.mobility.needs_draw)
        self.assertEqual(sorted(registrations[:2].mapped('draw_order')), [1, 2])
        self.assertEqual(sorted(registrations[:2].mapped('rank')), [2, 3])
        self.assertEqual(registrations[2].rank, 1, "The draw never moves anyone not tied.")
        self.assertFalse(registrations[2].draw_order)
        self.assertIn('Draw of the ties', self.mobility.message_ids[:1].body)
        with self.assertRaises(UserError):
            self.mobility.with_user(self.coordinator_user).action_draw_ties()
        self.mobility.with_user(self.leader_user).action_submit_proposal()

    def test_accredited_fewer_opportunities_break_a_tie(self):
        registrations = self._enrol(self.students[:1]) | self._enrol(self.students[1:2], fewer_opportunities=True)
        self._close({self.students[0]: 7.0, self.students[1]: 7.0})
        with self.assertRaises(UserError):
            self.mobility.with_user(self.leader_user).action_submit_proposal()
        registrations[1].with_user(self.technician_user).fewer_opportunities_check = 'yes'
        self.assertEqual(registrations.mapped('rank'), [2, 1])
        self.assertFalse(self.mobility.needs_draw)

    def test_data_frozen_at_closing(self):
        registrations = self._ranked()
        self._strikes(self.students[0], 5)
        with patch.object(type(self.env['ems.erasmus.application']), '_ems_partner_grade_values', return_value=[]):
            self.mobility._ems_rank()
        self.assertEqual(registrations[0].grade_average, 9.0)
        self.assertTrue(registrations[0].eligible)
        self.assertEqual(registrations[0].rank, 1)

    def test_ranking_cannot_change_once_approved(self):
        registrations = self._approved()
        with self.assertRaises(UserError):
            registrations[0].with_user(self.coordinator_user).fewer_opportunities_check = 'yes'
        self.mobility._ems_rank()
        self.assertEqual(registrations[0].rank, 1)


@tagged('post_install', '-at_install')
class TestErasmusGroupIncidents(ErasmusGroupMobilityCase):
    """Issue #702 - a student with no grades is an incident, and a draw is kept as evidence."""

    def test_no_grades_is_an_incident_never_a_zero(self):
        registrations = self._enrol(self.students[:3])
        self._close({self.students[0]: 7.0, self.students[1]: 6.0})
        nogrades = registrations[2]
        self.assertTrue(nogrades.grade_incident)
        self.assertFalse(nogrades.has_average)
        self.assertEqual((nogrades.rank, nogrades.proposed_result), (0, False), "Not ranked last with a 0.")
        self.assertEqual(self.mobility.grade_incidents, 1)
        with self.assertRaises(UserError):
            self.mobility.with_user(self.leader_user).action_submit_proposal()
        with self.assertRaises(AccessError):
            nogrades.with_user(self.leader_user).write({'grade_manual': True, 'grade_average_manual': 8.0,
                                                        'grade_manual_reason': 'Academic record'})
        with self.assertRaises(ValidationError):
            nogrades.with_user(self.technician_user).write({'grade_manual': True, 'grade_average_manual': 8.0})
        nogrades.with_user(self.technician_user).write({'grade_manual': True, 'grade_average_manual': 8.0,
                                                        'grade_manual_reason': 'Academic record, other centre'})
        self.assertFalse(nogrades.grade_incident)
        self.assertEqual(registrations.mapped('rank'), [2, 3, 1])
        self.mobility.with_user(self.leader_user).action_submit_proposal()

    def test_the_coordinator_can_exclude_a_student_with_no_grades(self):
        registrations = self._enrol(self.students[:2])
        self._close({self.students[0]: 7.0})
        registrations[1].with_user(self.coordinator_user).write({'result_override': 'excluded',
                                                                  'override_reason': 'Not enrolled in the modules'})
        self.assertFalse(registrations[1].grade_incident)
        self.mobility.with_user(self.leader_user).action_submit_proposal()

    def test_a_draw_keeps_the_tied_set_the_order_who_and_when(self):
        registrations = self._enrol(self.students[:4])
        self._close({self.students[0]: 7.0, self.students[1]: 7.0, self.students[2]: 7.0, self.students[3]: 9.0})
        self.mobility.with_user(self.coordinator_user).action_draw_ties()
        draw = self.mobility.draw_ids
        self.assertEqual(len(draw), 1)
        self.assertEqual(draw.user_id, self.coordinator_user)
        self.assertTrue(draw.date)
        self.assertEqual(draw.grade_average, 7.0)
        self.assertEqual(draw.line_ids.registration_id, registrations[:3], "Exactly the students tied.")
        self.assertEqual([line.registration_id.draw_order for line in draw.line_ids], [1, 2, 3])
        self.assertEqual(draw.line_ids.mapped('position'), [1, 2, 3])
        self.assertEqual(draw.line_ids.sorted('position').registration_id.mapped('rank'), [2, 3, 4])
        for record in (draw, draw.line_ids[:1]):
            with self.assertRaises(UserError):
                record.write({'position': 5} if record._name.endswith('line') else {'grade_average': 1.0})
            with self.assertRaises(UserError):
                record.unlink()

    def test_joining_a_drawn_tie_reopens_it(self):
        registrations = self._enrol(self.students[:3])
        self._close({self.students[0]: 7.0, self.students[1]: 7.0})
        self.mobility.with_user(self.coordinator_user).action_draw_ties()
        self.assertFalse(self.mobility.needs_draw)
        registrations[2].with_user(self.technician_user).write({
            'grade_manual': True, 'grade_average_manual': 7.0, 'grade_manual_reason': 'Academic record'})
        self.assertTrue(self.mobility.needs_draw)
        self.mobility.with_user(self.coordinator_user).action_draw_ties()
        self.assertEqual(len(self.mobility.draw_ids), 2)
        self.assertEqual(len(self.mobility.draw_ids[:1].line_ids), 3)


@tagged('post_install', '-at_install')
class TestErasmusGroupCommitment(ErasmusGroupMobilityCase):
    """Issue #703 - the commitment letter (the internship mobilities' mechanism) and the
    participants' spreadsheet."""

    def test_the_letter_is_the_common_template_with_the_mobility_data(self):
        minor = self._approved_with_minor()
        letter = minor._ems_commitment_text()
        self.assertIn('Test SMX2 morning', letter)
        self.assertIn('still to be confirmed', letter, "No destination yet.")
        self.assertIn('does not replace the official authorisation', letter)
        self.mobility.write({'city': 'Hamburg', 'country_id': self.env.ref('base.de').id,
                             'commitment_extra': '<p>No motorbikes</p>'})
        letter = minor._ems_commitment_text()
        self.assertIn('Hamburg', letter)
        self.assertIn('No motorbikes', letter)
        self.assertNotIn('still to be confirmed', letter)
        leader = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'leader')
        self.assertFalse(leader.commitment_pending, "Teachers sign no letter.")

    def test_student_and_family_sign_and_the_text_is_kept(self):
        family = self._family()
        minor = self._approved_with_minor()
        self.assertTrue(minor.commitment_pending)
        self.assertTrue(minor.commitment_guardian_pending)
        self.assertTrue(self.env['mail.mail'].search([('email_to', '=', family.email),
                                                      ('model', '=', minor._name), ('res_id', '=', minor.id)]),
                        "The family is told when the file opens.")
        self.assertEqual(family._ems_erasmus_guardian_group_participants(), minor)
        self.assertTrue(family._ems_erasmus_portal_visible())
        self.assertEqual(self.mobility.commitments_pending, 8)
        with self.assertRaises(UserError):
            minor.action_sign_commitment(False, '10.0.0.1')
        minor.action_sign_commitment(True, '10.0.0.1')
        self.assertIn('Test SMX2 morning', minor.commitment_signed_text)
        accepted = minor.commitment_signed_text
        self.assertEqual(minor._ems_commitment_text(), accepted, "The family signs the same text.")
        self.mobility.commitment_extra = '<p>Changed later</p>'
        self.assertEqual(minor.commitment_version_ids.text, accepted, "What was accepted never changes: it is kept.")
        self.assertTrue(minor.commitment_pending, "The new conditions are accepted again.")
        self.assertIn('Changed later', minor._ems_commitment_text())
        self.assertTrue(minor.commitment_guardian_pending)
        self.assertFalse(minor.preparation_complete)
        minor.action_sign_commitment(True, '10.0.0.3')
        minor.action_sign_commitment(True, '10.0.0.2', guardian=True)
        self.assertIn('Changed later', minor.commitment_signed_text)
        self.assertEqual(minor.commitment_guardian_signed_ip, '10.0.0.2')
        self.assertFalse(minor.commitment_guardian_pending)
        with self.assertRaises(UserError):
            minor.action_sign_commitment(True, guardian=True)

    def test_an_adult_signs_alone(self):
        self._approved()
        adult = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'student')[:1]
        self.assertFalse(adult.commitment_guardian_pending)
        with self.assertRaises(UserError):
            adult.action_sign_commitment(True, guardian=True)

    def test_participants_spreadsheet_in_the_calls_format(self):
        self._approved()
        with self.assertRaises(AccessError):
            self.mobility.with_user(self.leader_user).action_export_participants()
        action = self.mobility.with_user(self.technician_user).action_export_participants()
        self.assertIn('/ems/erasmus/group/participants?participant_ids=', action['url'])
        participants = self.mobility.participant_ids
        with self.assertRaises(AccessError):
            participants.with_user(self.leader_user)._ems_participants_xlsx()
        content = participants.with_user(self.technician_user)._ems_participants_xlsx()
        rows = list(openpyxl.load_workbook(io.BytesIO(content))['Participantes'].iter_rows(values_only=True))
        self.assertEqual(rows[0], PARTICIPANT_HEADERS, "The calls' columns, unchanged.")
        self.assertEqual(len(rows), 1 + 8 + 2, "Eight students and the two teachers.")
        records = [dict(zip(rows[0], row)) for row in rows[1:]]
        students, teachers = records[:8], records[8:]
        self.assertTrue(all(row['Ciclo formativo'] for row in students))
        self.assertFalse(any(row['Ciclo formativo'] or row['Curso'] for row in teachers),
                         "An accompanying teacher has no cycle nor year: what tells them apart.")
        self.assertFalse(any(row['IBAN'] or row['Banco'] for row in records), "No bank data in a group mobility.")


@tagged('post_install', '-at_install')
class TestErasmusGroupSelection(ErasmusGroupMobilityCase):
    """Issue #702 - the leader proposes, the coordinator approves; withdrawals and substitutions."""

    def test_proposal_validation_and_publication(self):
        registrations = self._ranked()
        with self.assertRaises(AccessError):
            self.mobility.with_user(self.companion_user).action_submit_proposal()
        self.mobility.with_user(self.leader_user).action_submit_proposal()
        self.assertEqual(self.mobility.state, 'validation')
        self.assertEqual(self.mobility.proposal_user_id, self.leader_user)
        with self.assertRaises(AccessError):
            self.mobility.with_user(self.leader_user).action_approve_selection()
        with self.assertRaises(AccessError):
            self.mobility.with_user(self.technician_user).action_approve_selection()
        self._approve()
        self.assertEqual(self.mobility.state, 'preparation')
        self.assertEqual(registrations[:8].mapped('result'), ['selected'] * 8)
        self.assertEqual(registrations[8:].mapped('result'), ['reserve'] * 2)
        self.assertEqual(self.env['mail.mail'].search_count([
            ('model', '=', 'ems.erasmus.group.registration'), ('res_id', 'in', registrations.ids)]), 10)
        self.assertEqual(self.mobility.approval_user_id, self.coordinator_user)

    def test_coordinator_sends_the_proposal_back_with_a_reason(self):
        self._ranked()
        self.mobility.with_user(self.leader_user).action_submit_proposal()
        with self.assertRaises(UserError):
            self.mobility.with_user(self.coordinator_user).action_return_proposal()
        self.mobility.with_user(self.coordinator_user).return_note = 'Check the tie-break'
        self.mobility.with_user(self.coordinator_user).action_return_proposal()
        self.assertEqual(self.mobility.state, 'selection')

    def test_leader_cannot_change_grades_results_or_publish(self):
        registrations = self._ranked()
        for vals in ({'grade_average': 10.0}, {'rank': 1}, {'result_override': 'selected', 'override_reason': 'x'}):
            with self.assertRaises(AccessError):
                registrations[9].with_user(self.leader_user).write(vals)
        registrations[9].with_user(self.leader_user).exception_request = 'Reason for an exception'
        registrations[9].with_user(self.leader_user).action_request_exception()
        with self.assertRaises(AccessError):
            self.mobility.with_user(self.leader_user).write({'student_places': 9})

    def test_coordinator_exception_needs_a_reason(self):
        registrations = self._ranked()
        with self.assertRaises(ValidationError):
            registrations[9].with_user(self.coordinator_user).result_override = 'selected'
        with self.assertRaises(AccessError):
            registrations[9].with_user(self.technician_user).write(
                {'result_override': 'selected', 'override_reason': 'Justified'})
        registrations[7].with_user(self.coordinator_user).write(
            {'result_override': 'reserve', 'override_reason': 'Justified and authorised'})
        registrations[9].with_user(self.coordinator_user).write(
            {'result_override': 'selected', 'override_reason': 'Justified and authorised'})
        self.mobility.with_user(self.leader_user).action_submit_proposal()
        self._approve()
        self.assertEqual(registrations[9].result, 'selected')
        self.assertEqual(registrations[7].result, 'reserve')
        self.assertEqual(registrations[7].proposed_result, 'selected')

    def test_renounce_and_substitution(self):
        registrations = self._approved()
        selected = registrations[0]
        file = selected.participant_id
        line = file.document_ids[:1]
        line._ems_add_files([('card.pdf', PDF)])
        selected.with_user(self.leader_user).action_renounce('Family reasons')
        self.assertEqual(selected.result, 'renounced')
        self.assertEqual(file.state, 'withdrawn')
        self.assertTrue(line.attachment_ids, "The documents already handed in are kept.")
        self.assertEqual(self.mobility.next_reserve, registrations[8].partner_id.name)
        self.mobility.with_user(self.leader_user).action_propose_substitution()
        self.assertEqual(registrations[8].substitution_state, 'proposed')
        self.assertEqual(registrations[8].substitute_for_id, selected)
        with self.assertRaises(AccessError):
            registrations[8].with_user(self.leader_user).action_approve_substitution()
        registrations[8].with_user(self.coordinator_user).action_approve_substitution()
        self.assertEqual(registrations[8].result, 'selected')
        self.assertEqual(selected.substitute_id, registrations[8])
        self.assertTrue(registrations[8].participant_id.document_ids)
        self.assertEqual(selected.rank, 1, "The frozen ranking is never rewritten.")
        self.assertFalse(self.mobility.next_reserve)

    def test_a_reserve_who_does_not_want_the_place_leaves_the_queue(self):
        """The coordinator rejecting the substitution kept proposing the same reserve: whoever does
        not want the place renounces it (the leader or the team record it) and the next is proposed."""
        registrations = self._approved()
        registrations[0].sudo().action_renounce("Cannot travel")
        first, second = registrations.filtered(lambda registration: registration.result == 'reserve').sorted('rank')
        self.mobility.with_user(self.leader_user).action_propose_substitution()
        action = first.with_user(self.leader_user).action_open_renounce()
        wizard = self.env[action['res_model']].with_user(self.leader_user).with_context(action['context']).create(
            {'reason': "Told the leader they do not want it"})
        wizard.action_confirm()
        self.assertEqual((first.result, first.substitution_state, first.renounce_reason),
                         ('renounced', False, "Told the leader they do not want it"))
        self.assertEqual(self.mobility.next_reserve, second.partner_id.name)
        with self.assertRaises(AccessError):
            second.with_user(self.companion_user).action_open_renounce()
        with self.assertRaises(UserError, msg="Excluded or already renounced: nothing to renounce."):
            first.sudo().action_renounce()

    def test_student_renounces_from_the_portal(self):
        registrations = self._approved()
        registrations[1].sudo().action_renounce()
        self.assertEqual(registrations[1].result, 'renounced')


@tagged('post_install', '-at_install')
class TestErasmusGroupFiles(ErasmusGroupMobilityCase):
    """Issue #703 - participants' files and the shared documents, on the Erasmus+ document engine."""

    def test_eight_students_and_two_teachers(self):
        self._approved()
        participants = self.mobility.participant_ids
        self.assertEqual(len(participants.filtered(lambda participant: participant.role == 'student')), 8)
        self.assertEqual(participants.filtered(lambda participant: participant.role == 'leader').employee_id,
                         self.leader)
        self.assertEqual(participants.filtered(lambda participant: participant.role == 'companion').employee_id,
                         self.companion)
        self.assertFalse(participants.registration_ids.filtered(lambda registration: registration.result != 'selected'))
        lines = participants.document_ids
        self.mobility.with_user(self.coordinator_user).action_sync_requirements()
        self.assertEqual(participants.document_ids, lines, "Updating never duplicates a document.")

    def test_teachers_join_without_a_staff_call(self):
        self.assertEqual(self.mobility.participant_ids.mapped('role'), ['leader', 'companion'])
        self.assertIn(self.env.ref('ems.group_erasmus_group_teacher'), self.leader_user.groups_id)
        self.mobility.companion_ids = self.other_teacher
        self.assertIn(self.env.ref('ems.group_erasmus_group_teacher'), self.other_teacher_user.groups_id)
        self.assertNotIn(self.env.ref('ems.group_erasmus_group_teacher'), self.companion_user.groups_id)
        old = self.mobility.participant_ids.filtered(lambda participant: participant.employee_id == self.companion)
        self.assertEqual(old.state, 'withdrawn')
        with self.assertRaises(ValidationError):
            self.mobility.companion_ids = self.companion | self.other_teacher

    def test_group_learning_agreement_once_and_no_individual_one(self):
        self._approved()
        agreement = self.mobility.requirement_ids.filtered(
            lambda document: document.name == 'Group learning agreement (planned)')
        self.assertEqual(agreement.group_audience, 'collective')
        self.assertEqual(len(self.mobility.document_ids.filtered(lambda line: line.call_document_id == agreement)), 1)
        self.assertFalse(self.mobility.participant_ids.document_ids.filtered(
            lambda line: line.call_document_id == agreement or 'learning agreement' in line.name.lower()))
        teacher = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'leader')
        self.assertFalse(teacher.document_ids.filtered(lambda line: line.name == 'Europass mobility document'))
        student = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'student')[:1]
        self.assertTrue(student.document_ids.filtered(lambda line: line.name == 'Europass mobility document'))
        self.assertTrue(student.document_ids.filtered(lambda line: line.name == 'Grant agreement'))
        self.assertTrue(teacher.document_ids.filtered(lambda line: line.name == 'Grant agreement'))

    def test_family_authorisations_only_for_minors(self):
        """The official authorisation to travel abroad, only for minors: a document of their own
        file, apart from the commitment letter."""
        minor = self._approved_with_minor()
        authorisation = 'Authorisation for minors to travel abroad'
        adult = self.mobility.registration_ids.filtered(lambda registration: registration.partner_id ==
                                                        self.students[0]).participant_id
        self.assertTrue(minor.is_minor)
        self.assertFalse(minor.document_ids.filtered(lambda line: line.name == 'Family authorisation to travel'),
                         "The family's authorisation to take part is the commitment letter, not a document.")
        self.assertTrue(minor.document_ids.filtered(lambda line: line.name == authorisation).is_required)
        self.assertFalse(adult.document_ids.filtered(lambda line: line.name == authorisation).is_required)

    def test_deadline_counts_from_the_group_dates(self):
        self._approved()
        line = self.mobility.document_ids.filtered(lambda line: line.name == 'Group learning agreement (planned)')
        self.assertEqual(line.deadline, self.mobility.date_start - timedelta(days=30))

    def test_a_line_has_one_owner(self):
        document = self.mobility.requirement_ids[:1]
        with self.assertRaises(Exception), self.cr.savepoint():
            self.env['ems.erasmus.application.document'].create({'call_document_id': document.id})
        student = self.env['ems.erasmus.group.participant'].search([('group_mobility_id', '=', self.mobility.id)])[:1]
        other = self.mobility.copy()
        with self.assertRaises(ValidationError):
            self.env['ems.erasmus.application.document'].create({
                'call_document_id': document.id, 'group_mobility_id': other.id, 'group_participant_id': student.id})

    def test_versions_and_review(self):
        self._approved()
        line = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'student')[
            :1].document_ids.filtered(lambda line: line.handled_by == 'participant' and not line.confidential)[:1]
        line._ems_add_files([('v1.pdf', PDF)])
        line.with_user(self.leader_user).action_mark_needs_change()
        line._ems_add_files([('v2.pdf', PDF)])
        self.assertEqual(line.attachment_ids.mapped('name'), ['v1.pdf', 'v2.pdf'])
        self.assertEqual(line.review_state, 'pending')
        with self.assertRaises(AccessError):
            line.with_user(self.companion_user).action_mark_valid()
        line.with_user(self.leader_user).action_mark_valid()
        self.assertEqual(line.review_state, 'valid')

    def test_eu_survey_and_closure(self):
        self._approved()
        self.mobility.with_user(self.leader_user).action_start_stay()
        self.env['ems.erasmus.group.log'].with_user(self.companion_user).create({
            'group_mobility_id': self.mobility.id, 'kind': 'attendance', 'name': 'Day 1',
            'participant_ids': [(6, 0, self.mobility.participant_ids[:1].ids)]})
        self.mobility.with_user(self.leader_user).action_end_stay()
        self.assertEqual(self.mobility.state, 'return')
        self.assertTrue(self.mobility.eu_survey_deadline)
        self.assertTrue(self.mobility.activity_ids.filtered(lambda activity: activity.user_id == self.leader_user))
        with self.assertRaises(AccessError):
            self.mobility.with_user(self.companion_user).action_eu_survey_done()
        self.mobility.with_user(self.leader_user).action_eu_survey_done()
        with self.assertRaises(UserError):
            self.mobility.with_user(self.coordinator_user).action_close()
        self.mobility.with_user(self.coordinator_user).action_eu_survey_validate()
        self.mobility.with_user(self.leader_user).programme_execution = 'as_planned'
        self.mobility.with_user(self.leader_user).action_propose_closure()
        self.assertTrue(self.mobility.closure_proposed_date)
        with self.assertRaises(UserError):
            self.mobility.with_user(self.coordinator_user).action_close()


@tagged('post_install', '-at_install')
class TestErasmusGroupSepieDocuments(ErasmusGroupMobilityCase):
    """What SEPIE asks of a KA121-VET group mobility (2026-10-29): provisional and definitive lists,
    the group learning agreement planned and executed, insurance for every participant (own or
    collective), Green Travel and inclusion only when they apply, Europass and the teachers'
    certificate of stay optional, the image rights the student already authorised."""

    def _lines(self, participant=None):
        return (participant or self.mobility).document_ids

    def test_provisional_list_before_the_definitive_one(self):
        registrations = self._ranked()
        self.mobility.with_user(self.leader_user).action_submit_proposal()
        with self.assertRaises(UserError):
            self.mobility.with_user(self.coordinator_user).action_approve_selection()
        with self.assertRaises(UserError):
            self.mobility.with_user(self.coordinator_user).action_publish_provisional()
        self.mobility.claims_deadline = fields.Datetime.now() + timedelta(days=7)
        with self.assertRaises(AccessError):
            self.mobility.with_user(self.technician_user).action_publish_provisional()
        self.mobility.with_user(self.coordinator_user).action_publish_provisional()
        provisional = self.mobility.resolution_ids
        self.assertEqual((provisional.kind, provisional.state), ('provisional', 'published'))
        self.assertEqual(self.mobility.state, 'validation')
        self.assertEqual(provisional.line_ids.mapped('result'), ['selected'] * 8 + ['reserve'] * 2)
        self.assertEqual(provisional.line_ids[0].public_id, '***0000**')
        self.assertEqual(provisional.line_ids[0].score_total, 9.0)
        self.assertEqual(self.env['mail.mail'].search_count([
            ('model', '=', 'ems.erasmus.resolution.line'), ('res_id', 'in', provisional.line_ids.ids)]), 10)
        with self.assertRaises(UserError):
            self.mobility.with_user(self.coordinator_user).action_publish_provisional()
        registrations[9].with_user(self.coordinator_user).write(
            {'result_override': 'excluded', 'override_reason': 'Claim accepted: not enrolled in the cycle'})
        with self.assertRaises(UserError, msg="The students can still claim against the provisional list."):
            self.mobility.with_user(self.coordinator_user).action_approve_selection()
        self._claims_over()
        self.mobility.with_user(self.coordinator_user).action_approve_selection()
        definitive = self.mobility.resolution_ids - provisional
        self.assertEqual((definitive.kind, definitive.state), ('definitive', 'published'))
        self.assertEqual(definitive.line_ids.filtered(lambda line: line.group_registration_id == registrations[9])
                         .exclusion_reason, 'Claim accepted: not enrolled in the cycle')
        self.assertEqual(self.env['mail.mail'].search_count([
            ('model', '=', 'ems.erasmus.resolution.line'), ('res_id', 'in', definitive.line_ids.ids)]), 0,
            "The definitive result goes in the group's own result email, never twice.")

    def test_a_list_needs_every_identity_document(self):
        self._ranked()
        self.students[3].document_id = False
        self.mobility.with_user(self.leader_user).action_submit_proposal()
        self.mobility.claims_deadline = fields.Datetime.now() + timedelta(days=7)
        with self.assertRaises(UserError):
            self.mobility.with_user(self.coordinator_user).action_publish_provisional()

    def test_learning_agreement_planned_and_executed_no_separate_list(self):
        self._approved()
        names = self.mobility.document_ids.mapped('name')
        self.assertIn('Group learning agreement (planned)', names)
        self.assertIn('Group learning agreement (executed)', names)
        self.assertNotIn('Final list of participants and accompanying teachers', names)
        executed = self.mobility.document_ids.filtered(lambda line: line.name == 'Group learning agreement (executed)')
        self.assertEqual(executed.stage, 'return')
        self.assertTrue(executed.is_required)
        self.assertTrue(executed.call_document_id.sign_coordinator and executed.call_document_id.sign_host)

    def test_the_leader_says_whether_the_programme_went_as_planned(self):
        self._approved()
        self.mobility.with_user(self.leader_user).action_start_stay()
        self.mobility.with_user(self.leader_user).action_end_stay()
        self.assertTrue(self.mobility.activity_ids.filtered(
            lambda activity: activity.user_id == self.leader_user and 'programme' in activity.summary))
        with self.assertRaises(UserError):
            self.mobility.with_user(self.leader_user).action_propose_closure()
        with self.assertRaises(AccessError):
            self.mobility.with_user(self.companion_user).write({'programme_execution': 'as_planned'})
        self.mobility.with_user(self.leader_user).write({'programme_execution': 'changed'})
        with self.assertRaises(UserError):
            self.mobility.with_user(self.leader_user).action_propose_closure()
        self.mobility.with_user(self.leader_user).write({'programme_changes': 'One company visit moved to day 3.'})
        self.mobility.with_user(self.leader_user).action_propose_closure()
        self.assertTrue(self.mobility.closure_proposed_date)

    def test_insurance_for_every_participant_or_the_collective_policy(self):
        self._approved()
        participants = self.mobility.participant_ids
        policies = participants.document_ids.filtered(lambda line: line.name == 'Insurance policy')
        self.assertEqual(policies.group_participant_id, participants, "Students and accompanying teachers.")
        self.assertTrue(all(policies.mapped('is_required')))
        collective = self.mobility.document_ids.filtered(lambda line: line.name == 'Collective insurance policy')
        self.assertFalse(collective.is_required)
        self.assertEqual(collective.file_state, 'not_applicable')
        covered = participants[:3]
        covered.with_user(self.technician_user).write({'insurance_collective': True})
        self.assertTrue(collective.is_required)
        self.assertFalse(any(policies.filtered(lambda line: line.group_participant_id in covered).mapped('is_required')))
        self.assertTrue(all(policies.filtered(lambda line: line.group_participant_id not in covered)
                            .mapped('is_required')))
        with self.assertRaises(AccessError):
            covered[:1].with_user(self.leader_user).write({'insurance_collective': False})

    def test_optional_documents_never_block(self):
        self._approved()
        student = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'student')[:1]
        teacher = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'leader')
        optional = (student.document_ids.filtered(lambda line: line.name == 'Europass mobility document')
                    | teacher.document_ids.filtered(lambda line: line.name == 'Certificate of stay')
                    | self.mobility.document_ids.filtered(
                        lambda line: line.name == 'Green Travel: sworn statement and evidence'))
        self.assertEqual(len(optional), 3)
        self.assertFalse(any(optional.mapped('is_required')))
        self.assertEqual(set(optional.mapped('file_state')), {'optional'})

    def test_image_rights_are_the_students_own_authorisation(self):
        self._approved()
        self.assertFalse(self.mobility.participant_ids.document_ids.filtered(lambda line: 'image' in line.name.lower()))
        student = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'student')[:1]
        self.assertEqual(student.auth_image, student.partner_id.auth_image)


@tagged('post_install', '-at_install')
class TestErasmusGroupSecurity(ErasmusGroupMobilityCase):
    """Issue #701 - each teacher reaches only their own mobilities, never the conduct data, and an
    accompanying teacher never the ranking."""

    def setUp(self):
        super().setUp()
        self.other = self.env['ems.erasmus.group.mobility'].create({
            'name': 'Test other group', 'project_id': self.project.id, 'leader_id': self.other_teacher.id})

    def test_leader_reaches_only_their_mobilities(self):
        Mobility = self.env['ems.erasmus.group.mobility'].with_user(self.leader_user)
        self.assertEqual(Mobility.search([]), self.mobility)
        with self.assertRaises(AccessError):
            self.other.with_user(self.leader_user).read(['name'])
        with self.assertRaises(AccessError):
            self.other.with_user(self.leader_user).action_start_stay()

    def test_draws_only_of_their_own_mobility_and_never_the_fewer_opportunities(self):
        """A draw lists the students tied and whether they had fewer opportunities accredited: the
        leader reads their own mobility's draws (the order), never another mobility's nor that flag;
        an accompanying teacher reads none."""
        registrations = self._enrol(self.students[:3])
        self._close({self.students[0]: 9.0, self.students[1]: 8.0, self.students[2]: 8.0})
        self.mobility.with_user(self.coordinator_user).action_draw_ties()
        Draw, Line = self.env['ems.erasmus.group.draw'], self.env['ems.erasmus.group.draw.line']
        self.assertEqual(Draw.with_user(self.leader_user).search([]), self.mobility.draw_ids)
        self.assertEqual(len(Line.with_user(self.leader_user).search([])), 2)
        for user in (self.other_teacher_user, self.companion_user):
            self.assertFalse(Draw.with_user(user).search([]), user.name)
            self.assertFalse(Line.with_user(user).search([]), user.name)
        with self.assertRaises(AccessError):
            Draw.with_user(self.leader_user).search_read([], ['fewer_opportunities'])
        with self.assertRaises(AccessError):
            self.mobility.draw_ids.with_user(self.leader_user).read(['fewer_opportunities'])
        self.assertTrue(registrations[1].needs_draw or registrations[1].draw_order)

    def test_accompanying_teacher_never_sees_the_enrolments(self):
        self._ranked()
        self.assertFalse(self.env['ems.erasmus.group.registration'].with_user(self.companion_user).search([]))
        self.assertEqual(len(self.env['ems.erasmus.group.registration'].with_user(self.leader_user).search([])), 10)
        self.mobility.with_user(self.companion_user).read(['selected_count', 'next_reserve', 'registration_ids'])

    def test_leader_never_reads_conduct_data(self):
        registrations = self._ranked()
        for field in ('strike_count', 'exclusion', 'fewer_opportunities', 'fewer_opportunities_check'):
            with self.assertRaises(AccessError):
                registrations[0].with_user(self.leader_user).read([field])
        registrations[0].with_user(self.leader_user).read(['grade_average', 'eligible', 'rank'])

    def test_teachers_never_reach_confidential_or_other_documents(self):
        self._approved()
        Line = self.env['ems.erasmus.application.document']
        inclusion = self.mobility.document_ids.filtered('confidential')
        inclusion._ems_add_files([('inclusion.pdf', PDF)])
        self.assertTrue(inclusion)
        self.assertNotIn(inclusion, Line.with_user(self.leader_user).search([]))
        with self.assertRaises(AccessError):
            inclusion.attachment_ids.with_user(self.leader_user).read(['datas'])
        self.other.with_user(self.coordinator_user)._ems_sync_collective_documents()
        other_line = self.other.document_ids[:1]
        other_line._ems_add_files([('other.pdf', PDF)])
        with self.assertRaises(AccessError):
            other_line.attachment_ids.with_user(self.leader_user).read(['datas'])
        self.assertFalse(Line.with_user(self.leader_user).search([('application_id', '!=', False)]))

    def test_accompanying_teacher_changes_only_their_own_documents(self):
        self._approved()
        own = self.mobility.participant_ids.filtered(lambda participant: participant.employee_id == self.companion)
        student = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'student')[:1]
        own.document_ids[:1].with_user(self.companion_user).review_comment = 'Mine'
        with self.assertRaises(AccessError):
            student.document_ids[:1].with_user(self.companion_user).review_comment = 'Not mine'

    def test_follow_up_only_in_own_mobility(self):
        with self.assertRaises(AccessError):
            self.env['ems.erasmus.group.log'].with_user(self.companion_user).create({
                'group_mobility_id': self.other.id, 'name': 'Not mine'})

    def test_another_teacher_reaches_nothing(self):
        nobody = create_role_user(self, 'teacher', 'test_group_nobody', name='Group Nobody Teacher')
        for model in ('ems.erasmus.group.mobility', 'ems.erasmus.group.registration',
                      'ems.erasmus.group.participant'):
            with self.assertRaises(AccessError):
                self.env[model].with_user(nobody).search([])

    def test_team_member_who_also_leads_keeps_every_call_document(self):
        self.mobility.leader_id = create_role_employee(self, self.technician_user)
        call_documents = self.env['ems.erasmus.call.document'].with_user(self.technician_user)
        self.assertEqual(call_documents.search_count([]), self.env['ems.erasmus.call.document'].search_count([]))


@tagged('post_install', '-at_install')
class TestPortalErasmusGroup(HttpCase, ErasmusGroupMobilityCase):
    """Issue #701 - the portal: one-click enrolment, own data only, and the selected student's file."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student_user, cls.afternoon_user, cls.classmate_user = cls.env['res.users'].with_context(
            no_reset_password=True).create([{
                'name': partner.name, 'login': login, 'password': login, 'partner_id': partner.id, 'lang': 'en_US',
                'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
            } for partner, login in ((cls.students[0], 'test_group_portal_student'),
                                     (cls.afternoon_student, 'test_group_portal_afternoon'),
                                     (cls.students[1], 'test_group_portal_classmate'))])

    def _post(self, url, **data):
        return self.url_open(url, data={'csrf_token': Request.csrf_token(self), **data})

    def test_enrol_and_withdraw_with_one_click(self):
        self.authenticate(self.student_user.login, self.student_user.login)
        page = self.url_open('/my/erasmus')
        self.assertIn('Test SMX2 morning', page.text)
        self.assertIn('o_ems_erasmus_group_enrol', page.text)
        response = self._post(f'/my/erasmus/group/{self.mobility.id}/enrol')
        self.assertIn('enrolled=1', response.url)
        registration = self.mobility.registration_ids
        self.assertEqual((registration.partner_id, registration.state), (self.students[0], 'enrolled'))
        self.assertEqual(registration.enrol_user_id, self.student_user)
        self.assertIn('o_ems_erasmus_group_withdraw', self.url_open('/my/erasmus').text)
        self._post(f'/my/erasmus/group/{self.mobility.id}/withdraw')
        self.assertEqual(registration.state, 'withdrawn')

    def test_student_of_another_group_is_kept_out(self):
        self.authenticate(self.afternoon_user.login, self.afternoon_user.login)
        self.assertNotIn('Test SMX2 morning', self.url_open('/my/erasmus').text)
        response = self._post(f'/my/erasmus/group/{self.mobility.id}/enrol')
        self.assertTrue(response.url.endswith('/my/home'))
        self.assertFalse(self.mobility.registration_ids)

    def test_never_another_students_enrolment_or_file(self):
        self._approved()
        self.authenticate(self.classmate_user.login, self.classmate_user.login)
        page = self.url_open('/my/erasmus').text
        self.assertNotIn(self.students[0].name, page)
        self.assertNotIn('9.00', page)
        own = self.mobility.participant_ids.filtered(lambda participant: participant.partner_id == self.students[1])
        other = self.mobility.participant_ids.filtered(lambda participant: participant.partner_id == self.students[0])
        line = other.document_ids.filtered(lambda line: line.handled_by == 'team_to_sign')[:1]
        line.prepared_attachment_ids = self.env['ir.attachment'].create({'name': 'theirs.pdf', 'raw': PDF})
        response = self.url_open(f'/my/erasmus/group/{self.mobility.id}/file/{line.prepared_attachment_ids.id}')
        self.assertNotEqual(response.content, PDF)
        self.assertIn('/my/erasmus', response.url)
        self.assertTrue(own)

    def test_selected_student_uploads_and_renounces(self):
        self._approved()
        self.authenticate(self.student_user.login, self.student_user.login)
        page = self.url_open(f'/my/erasmus/group/{self.mobility.id}')
        self.assertEqual(page.status_code, 200)
        self.assertIn('o_ems_erasmus_group_documents', page.text)
        participant = self.mobility.participant_ids.filtered(lambda participant: participant.partner_id == self.students[0])
        card = participant.document_ids.filtered(lambda line: line.name == 'European Health Insurance Card')
        self.url_open(f'/my/erasmus/group/{self.mobility.id}/upload',
                      data={'csrf_token': Request.csrf_token(self)},
                      files=[(f'document_{card.call_document_id.id}', ('card.pdf', PDF, 'application/pdf'))])
        self.assertEqual(card.attachment_ids.mapped('name'), ['card.pdf'])
        self._post(f'/my/erasmus/group/{self.mobility.id}/renounce', reason='Cannot travel')
        self.assertEqual(participant.registration_ids.result, 'renounced')
        self.assertEqual(participant.registration_ids.renounce_reason, 'Cannot travel')

    def test_published_lists_on_the_portal(self):
        self._ranked()
        self.mobility.with_user(self.leader_user).action_submit_proposal()
        self._publish_provisional()
        provisional = self.mobility.resolution_ids
        self.authenticate(self.student_user.login, self.student_user.login)
        card = self.url_open('/my/erasmus').text
        self.assertIn('o_ems_erasmus_group_provisional', card)
        self.assertIn(f'/my/erasmus/group/{self.mobility.id}/resolution/{provisional.id}', card)
        page = self.url_open(f'/my/erasmus/group/{self.mobility.id}/resolution/{provisional.id}').text
        self.assertIn('***0000**', page)
        self.assertNotIn(self.students[1].name, page, "Never a classmate's name.")
        self.authenticate(self.afternoon_user.login, self.afternoon_user.login)
        response = self.url_open(f'/my/erasmus/group/{self.mobility.id}/resolution/{provisional.id}')
        self.assertNotIn('***0000**', response.text)

    def test_not_selected_student_has_no_file(self):
        self._approved()
        reserve = self.mobility.registration_ids.filtered(lambda registration: registration.result == 'reserve')[:1]
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': reserve.partner_id.name, 'login': 'test_group_portal_reserve', 'password': 'test_group_portal_reserve',
            'partner_id': reserve.partner_id.id, 'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.authenticate(user.login, user.login)
        self.assertIn('o_ems_erasmus_group_result_reserve', self.url_open('/my/erasmus').text)
        response = self.url_open(f'/my/erasmus/group/{self.mobility.id}')
        self.assertFalse(response.url.endswith(f'/my/erasmus/group/{self.mobility.id}'))

    def test_a_reserve_leaves_the_reserve_list_from_the_portal(self):
        registrations = self._approved()
        first, second = registrations.filtered(lambda registration: registration.result == 'reserve').sorted('rank')
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': first.partner_id.name, 'login': 'test_group_portal_reserve', 'password': 'test_group_portal_reserve',
            'partner_id': first.partner_id.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.authenticate(self.student_user.login, self.student_user.login)
        self.assertNotIn('o_ems_erasmus_group_reserve_renounce', self.url_open('/my/erasmus').text,
                         "Only a reserve sees it.")
        self._post(f'/my/erasmus/group/{self.mobility.id}/reserve/renounce', reason='Not mine')
        self.assertEqual(registrations[0].result, 'selected', "Never a selected student's place from here.")
        self.authenticate(user.login, user.login)
        self.assertIn('o_ems_erasmus_group_reserve_renounce', self.url_open('/my/erasmus').text)
        self._post(f'/my/erasmus/group/{self.mobility.id}/reserve/renounce', reason='I found a job')
        self.assertEqual((first.result, first.renounce_reason), ('renounced', 'I found a job'))
        self.assertEqual(second.reserve_position, 1)

    def test_student_and_family_accept_the_letter_on_the_portal(self):
        family = self._family()
        family_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': family.name, 'login': 'test_group_portal_family', 'password': 'test_group_portal_family',
            'partner_id': family.id, 'lang': 'en_US', 'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        minor_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': self.minor.name, 'login': 'test_group_portal_minor', 'password': 'test_group_portal_minor',
            'partner_id': self.minor.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        minor = self._approved_with_minor()
        url = f'/my/erasmus/group/commitment/{minor.id}'
        self.authenticate(minor_user.login, minor_user.login)
        page = self.url_open(f'/my/erasmus/group/{self.mobility.id}').text
        self.assertIn('o_ems_erasmus_commitment_sign', page)
        self.assertIn('o_ems_erasmus_guardian_pending', page)
        self.assertIn('error=1', self._post(f'/my/erasmus/group/{self.mobility.id}/commitment').url)
        self._post(f'/my/erasmus/group/{self.mobility.id}/commitment', accepted='on')
        self.assertEqual(minor.commitment_signed_by_id, minor_user)
        self.assertIn('error=1', self._post(url, accepted='on').url, "The student does not sign for the family.")
        self.authenticate(family_user.login, family_user.login)
        self.assertIn('o_ems_erasmus_group_guardian_commitment', self.url_open('/my/erasmus').text)
        self.assertIn('error=1', self._post(url).url, "Not without ticking the acceptance.")
        self._post(url, accepted='on')
        self.assertEqual(minor.commitment_guardian_signed_by_id, family_user)
        self.assertIn('o_ems_erasmus_guardian_signed', self.url_open('/my/erasmus').text)
