import io
import zipfile
from datetime import timedelta

import openpyxl

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from .common import create_level_study_group, create_role_employee, create_role_user, mock_outgoing_email, \
    next_student_id
from .test_erasmus import PDF

# Per student: record grade (None: no evaluated module), declares fewer opportunities, minor.
# Grades are whole numbers. 4 student places. Ranking at closing: ana 10, ivet 9, bel 8 (fewer opportunities accredited),
# cai 8 (declared, not accredited), dani / eva 7 (tied: drawn), fiona (no grades: 6.5 entered by
# the team), hugo 6 (claims against the provisional list: 8.5 entered by the team), gil (no grades:
# excluded by the coordinator), jan (3 conduct warnings after enrolling: excluded).
STUDENTS = {
    'ana': (10.0, False, False),
    'ivet': (9.0, False, True),
    'bel': (8.0, True, False),
    'cai': (8.0, True, False),
    'dani': (7.0, False, False),
    'eva': (7.0, False, False),
    'fiona': (None, False, False),
    'hugo': (6.0, False, False),
    'gil': (None, False, False),
    'jan': (7.0, False, False),
    'kim': (9.5, False, False),        # 3 conduct warnings before: cannot enrol
    'max': (9.9, False, False),        # enrols and withdraws
    'leo': (9.9, False, False),        # afternoon group: cannot enrol
}


@tagged('post_install', '-at_install')
class TestErasmusGroupMobilityEndToEnd(TransactionCase):
    """A KA121-VET group mobility (4 students, a leader and an accompanying teacher) run from its
    creation to its closure with the roles of the real process: the mobility technician sets it up
    and keeps the files, the students enrol from the portal, the leader teacher proposes the
    selection, the coordinator draws the ties, publishes the lists and approves, the families of
    minors accept the commitment letter, the Head of Studies only reads."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.env.company.strike_escalation_threshold = 3
        cls.level, cls.study, cls.group_a = create_level_study_group(
            cls, 'E2EGRP', group={'course': 2, 'shift': 'morning'})
        cls.group_b, cls.group_pm = cls.env['ems.group'].create([
            {'course': 2, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id, 'shift': 'morning'},
            {'course': 2, 'acronym': 'C', 'level_id': cls.level.id, 'study_id': cls.study.id, 'shift': 'afternoon'},
        ])
        cls.subject = cls.env['ems.subject'].create({
            'code': 'E2EGRPM', 'acronym': 'EGRPM', 'name': 'E2E group module', 'internal_hours': 99,
            'study_ids': [(4, cls.study.id)]})
        cls.project = cls.env['ems.erasmus.project'].create({'name': 'E2E-GROUP-VET', 'kind': 'ka121_vet'})
        cls.technician = create_role_user(cls, 'erasmus', 'test_e2e_grp_technician', email='tech@example.com')
        cls.coordinator = create_role_user(cls, 'erasmus_coordinator', 'test_e2e_grp_coordinator',
                                           email='coord@example.com')
        cls.hos = create_role_user(cls, 'head_of_studies', 'test_e2e_grp_hos', email='hos@example.com')
        cls.leader_user = create_role_user(cls, 'teacher', 'test_e2e_grp_leader', name='E2E leader',
                                           email='leader@example.com')
        cls.companion_user = create_role_user(cls, 'teacher', 'test_e2e_grp_companion', name='E2E companion',
                                              email='companion@example.com')
        cls.other_user = create_role_user(cls, 'teacher', 'test_e2e_grp_other', name='E2E other leader',
                                          email='other@example.com')
        cls.leader, cls.companion, cls.other = (create_role_employee(cls, user) for user in (
            cls.leader_user, cls.companion_user, cls.other_user))
        create_role_employee(cls, cls.hos)
        portal = cls.env.ref('base.group_portal')
        cls.students, cls.portal_users = {}, {}
        for index, (name, (grade, _fewer, minor)) in enumerate(STUDENTS.items(), 1):
            birth = fields.Date.today() - timedelta(days=16 * 365) if minor else '2005-03-01'
            partner = cls.env['res.partner'].create({
                'name': f'E2E {name}', 'contact_type': 'student', 'student_id': next_student_id(),
                'main_group_id': (cls.group_pm if name == 'leo' else cls.group_a if index % 2 else cls.group_b).id,
                'birth_date': birth, 'email': f'{name}@example.com', 'lang': 'en_US',
                # Every masked DNI differs: 71050505Z -> ***5050**.
                'document_id': f'71{index:02d}{index:02d}{index:02d}Z'})
            cls.students[name] = partner
            cls.portal_users[name] = cls.env['res.users'].with_context(no_reset_password=True).create({
                'name': partner.name, 'login': f'test_e2e_grp_{name}', 'password': f'test_e2e_grp_{name}',
                'partner_id': partner.id, 'groups_id': [(6, 0, portal.ids)]})
            if grade is not None:
                cls._grade(partner, grade)
        cls.family = cls.env['res.partner'].create({
            'name': 'E2E family of ivet', 'contact_type': 'family', 'email': 'family@example.com'})
        cls.env['res.partner.relation'].create({
            'left_partner_id': cls.family.id, 'type_id': cls.env.ref('ems.relation_type_mother').id,
            'right_partner_id': cls.students['ivet'].id})
        cls.family_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': cls.family.name, 'login': 'test_e2e_grp_family', 'password': 'test_e2e_grp_family',
            'partner_id': cls.family.id, 'groups_id': [(6, 0, portal.ids)]})
        cls._strikes(cls.students['kim'], 3)

    @classmethod
    def _grade(cls, partner, grade):
        group = partner.main_group_id
        values = {'group_id': group.id, 'subject_id': cls.subject.id, 'round': '1'}
        session = cls.env['ems.grade_session'].search([(key, '=', value) for key, value in values.items()]) \
            or cls.env['ems.grade_session'].create(values)
        line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == partner) \
            or cls.env['ems.grade_subject_line'].create({'grade_session_id': session.id, 'student_id': partner.id})
        line.write({'is_overridden': True, 'internal_score': grade})

    @classmethod
    def _strikes(cls, partner, count):
        cls.env['ems.strike'].create([{
            'student_id': partner.id, 'teacher_id': cls.other.id,
            'date': fields.Datetime.now() - timedelta(minutes=index + 1)} for index in range(count)])

    # --- helpers ----------------------------------------------------------------------------

    def _as(self, user, record=None):
        return (record or self.mobility).with_user(user)

    def _enrol(self, name):
        """What the portal route does: the logged-in student's own partner, as superuser."""
        mobility = self.students[name].with_user(self.portal_users[name])._ems_erasmus_group_mobilities()
        return self.env['ems.erasmus.group.registration'].sudo()._ems_portal_enrol(
            mobility.filtered(lambda found: found == self.mobility), self.students[name],
            STUDENTS[name][1])

    def _registrations(self):
        return {registration.partner_id.name.removeprefix('E2E '): registration
                for registration in self.mobility.registration_ids}

    def _list(self, resolution):
        return {line.partner_id.name.removeprefix('E2E '): (line.result, line.rank) for line in resolution.line_ids}

    def _participant(self, name):
        return self.mobility.participant_ids.filtered(lambda participant: participant.partner_id == self.students[name])

    def _line(self, record, name):
        return record.document_ids.filtered(lambda line: line.name == name)

    def _renounce(self, registration, user, reason):
        """What the Renounce button of the enrolments' list does."""
        action = registration.with_user(user).action_open_renounce()
        wizard = self.env[action['res_model']].with_user(user).with_context(action['context']).create(
            {'reason': reason})
        wizard.action_confirm()

    def _mails_to(self, address):
        return self.env['mail.mail'].search([('email_to', '=', address)])

    # --- the whole process --------------------------------------------------------------------

    def test_group_mobility_from_enrolment_to_closure(self):
        Mobility = self.env['ems.erasmus.group.mobility']
        now = fields.Datetime.now()
        today = fields.Date.today()
        # 1. The technician creates the mobility for the two morning groups; the Head of Studies,
        # the teachers and the students cannot.
        vals = {'name': 'E2E SMX2 morning', 'project_id': self.project.id, 'shift': 'morning',
                'group_ids': [(6, 0, (self.group_a | self.group_b).ids)], 'student_places': 4,
                'leader_id': self.leader.id, 'companion_ids': [(6, 0, self.companion.ids)],
                'enrolment_open': now - timedelta(days=1), 'enrolment_close': now + timedelta(days=5),
                'date_start_planned': today + timedelta(days=120), 'date_end_planned': today + timedelta(days=134)}
        for user in (self.hos, self.leader_user):
            with self.assertRaises(AccessError):
                Mobility.with_user(user).create(dict(vals))
        self.mobility = Mobility.with_user(self.technician).create(vals)
        self.assertEqual(self.mobility.participant_ids.mapped('role'), ['leader', 'companion'],
                         "The teachers join without any staff call.")
        self.assertTrue(self.leader_user.has_group('ems.group_erasmus_group_teacher'))
        self.assertTrue(self.mobility.tie_break, "The agreed criteria by default.")
        self.assertFalse(self.mobility.document_ids, "No shared document before the selection.")
        with self.assertRaises(AccessError):
            self._as(self.leader_user).action_open_enrolment()
        self._as(self.technician).action_open_enrolment()
        self.assertTrue(self.mobility.is_enrolling)

        # 2. Enrolling from the portal: the morning groups only, never with 3 conduct warnings.
        self.assertFalse(self.mobility & self.students['leo'].with_user(self.portal_users['leo'])
                         ._ems_erasmus_group_mobilities(), "The afternoon group does not see it.")
        with self.assertRaises(UserError):
            self.env['ems.erasmus.group.registration'].sudo()._ems_portal_enrol(self.mobility, self.students['leo'])
        with self.assertRaises(UserError, msg="Three conduct warnings this course: cannot enrol."):
            self._enrol('kim')
        for name in ('ana', 'ivet', 'bel', 'cai', 'dani', 'eva', 'fiona', 'hugo', 'gil', 'jan', 'max'):
            self._enrol(name)
        with self.assertRaises(UserError):
            self._enrol('ana')
        registrations = self._registrations()
        registrations['max'].with_user(self.portal_users['max']).sudo().action_withdraw()
        self.assertEqual(registrations['max'].state, 'withdrawn')
        with self.assertRaises(AccessError, msg="Nobody else withdraws a student."):
            registrations['ana'].with_user(self.leader_user).action_withdraw()
        for user in (self.portal_users['ana'], self.family_user):
            with self.assertRaises(AccessError, msg="The portal never reads the Erasmus models directly."):
                self.env['ems.erasmus.group.registration'].with_user(user).search_read([], ['partner_id'])
        # jan gets 3 conduct warnings after enrolling: excluded when the enrolment closes.
        self._strikes(self.students['jan'], 3)

        # 3. Closing: EMS freezes and ranks; the leader gets the task.
        self.assertEqual(self.mobility.registration_count, 10)
        with self.assertRaises(AccessError):
            self._as(self.leader_user).action_close_enrolment()
        self._as(self.technician).action_close_enrolment()
        self.assertEqual(self.mobility.state, 'selection')
        self.assertTrue(self.mobility.activity_ids.filtered(lambda activity: activity.user_id == self.leader_user))
        registrations = self._registrations()
        self.assertEqual(registrations['jan'].exclusion, 'conduct')
        self.assertEqual(registrations['jan'].proposed_result, 'excluded')
        self.assertEqual((registrations['fiona'].grade_incident, registrations['gil'].grade_incident), (True, True))
        self.assertEqual(self.mobility.grade_incidents, 2)
        self.assertEqual(registrations['ana'].grade_average, 10.0, "The internship call's average, from EMS.")

        # 4. What the leader reads: rank and average, never the conduct data nor the fewer
        # opportunities (read and search_read alike). The accompanying teacher, no enrolment.
        Registration = self.env['ems.erasmus.group.registration']
        rows = Registration.with_user(self.leader_user).search_read(
            [('group_mobility_id', '=', self.mobility.id)], ['partner_id', 'rank', 'grade_average', 'eligible'])
        self.assertEqual(len(rows), 11, "The withdrawn enrolment too.")
        for field in ('strike_count', 'exclusion', 'fewer_opportunities', 'fewer_opportunities_check'):
            with self.assertRaises(AccessError, msg=field):
                Registration.with_user(self.leader_user).search_read(
                    [('group_mobility_id', '=', self.mobility.id)], [field])
            with self.assertRaises(AccessError, msg=field):
                registrations['jan'].with_user(self.leader_user).read([field])
        self.assertFalse(Registration.with_user(self.companion_user).search([]))
        with self.assertRaises(AccessError, msg="A teacher with no group mobility reaches nothing."):
            Registration.with_user(self.other_user).search([])
        rows = Registration.with_user(self.hos).search_read([('group_mobility_id', '=', self.mobility.id)],
                                                            ['rank', 'grade_average'])
        self.assertEqual(len(rows), 11, "The Head of Studies reads the ranking.")
        with self.assertRaises(AccessError):
            Registration.with_user(self.hos).search_read([('id', '=', registrations['jan'].id)], ['strike_count'])
        with self.assertRaises(AccessError):
            registrations['ana'].with_user(self.hos).write({'exception_request': 'x'})

        # 5. Before the proposal: the fewer opportunities checked, the students with no grades
        # resolved, the tie drawn.
        with self.assertRaises(UserError, msg="A declared fewer-opportunities situation is pending."):
            self._as(self.leader_user).action_submit_proposal()
        with self.assertRaises(AccessError, msg="Only the team accredits it."):
            registrations['bel'].with_user(self.leader_user).write({'fewer_opportunities_check': 'yes'})
        registrations['bel'].with_user(self.technician).fewer_opportunities_check = 'yes'
        registrations['cai'].with_user(self.technician).fewer_opportunities_check = 'no'
        with self.assertRaises(UserError, msg="Two students with no grades."):
            self._as(self.leader_user).action_submit_proposal()
        registrations['fiona'].with_user(self.technician).write({
            'grade_manual': True, 'grade_average_manual': 6.5,
            'grade_manual_reason': "Academic record of the previous centre"})
        with self.assertRaises(AccessError, msg="Only the coordinator excludes."):
            registrations['gil'].with_user(self.technician).write({
                'result_override': 'excluded', 'override_reason': 'No record'})
        registrations['gil'].with_user(self.coordinator).write({
            'result_override': 'excluded', 'override_reason': "No record: enrolled this course without grades"})
        self.assertEqual(self.mobility.grade_incidents, 0)
        self.assertEqual([registrations[name].rank for name in ('ana', 'ivet', 'bel', 'cai')], [1, 2, 3, 4],
                         "The accredited fewer opportunities break the tie at 8.")
        self.assertTrue(registrations['dani'].needs_draw and registrations['eva'].needs_draw)
        with self.assertRaises(UserError, msg="The tie at 7 first."):
            self._as(self.leader_user).action_submit_proposal()
        for user in (self.leader_user, self.technician):
            with self.assertRaises(AccessError, msg="Only the coordinator draws."):
                self._as(user).action_draw_ties()
        self._as(self.coordinator).action_draw_ties()
        draw = self.mobility.draw_ids
        self.assertEqual((len(draw), draw.tied_count, draw.grade_average), (1, 2, 7.0))
        self.assertEqual(set(draw.line_ids.partner_id.mapped('name')), {'E2E dani', 'E2E eva'})
        first, second = draw.line_ids.sorted('position').partner_id
        self.assertEqual(self.env['ems.erasmus.group.draw'].with_user(self.hos).search_count(
            [('group_mobility_id', '=', self.mobility.id)]), 1, "The Head of Studies reads the draws.")
        with self.assertRaises(UserError):
            draw.write({'user_id': self.technician.id})
        self.assertEqual([registrations[name].proposed_result for name in ('ana', 'ivet', 'bel', 'cai')],
                         ['selected'] * 4)

        # 6. The leader proposes; the coordinator sends it back with a reason, then publishes the
        # provisional list (never the leader nor the technician).
        self._as(self.leader_user).write({'proposal_note': "Ranking checked with the tutors"})
        self._as(self.leader_user).action_submit_proposal()
        self.assertEqual(self.mobility.state, 'validation')
        with self.assertRaises(UserError):
            self._as(self.coordinator).action_return_proposal()
        self._as(self.coordinator).write({'return_note': "Check the average of fiona"})
        self._as(self.coordinator).action_return_proposal()
        self.assertEqual(self.mobility.state, 'selection')
        self._as(self.leader_user).action_submit_proposal()
        self._as(self.technician).write({'claims_deadline': now + timedelta(days=7)})
        for user in (self.leader_user, self.technician):
            with self.assertRaises(AccessError):
                self._as(user).action_publish_provisional()
        self._as(self.coordinator).action_publish_provisional()
        provisional = self.mobility.resolution_ids
        self.assertEqual(provisional.kind, 'provisional')
        self.assertEqual(self._list(provisional), {
            'ana': ('selected', 1), 'ivet': ('selected', 2), 'bel': ('selected', 3), 'cai': ('selected', 4),
            first.name.removeprefix('E2E '): ('reserve', 5), second.name.removeprefix('E2E '): ('reserve', 6),
            'fiona': ('reserve', 7), 'hugo': ('reserve', 8), 'gil': ('excluded', 0), 'jan': ('excluded', 0)})
        self.assertEqual(len(set(provisional.line_ids.mapped('public_id'))), 10, "Every masked DNI differs.")
        self.assertNotIn('71', ''.join(provisional.line_ids.mapped('public_id')), "Never the whole DNI.")
        html = self.env['ir.actions.report']._render_qweb_html(
            'ems.report_erasmus_resolution', provisional.ids)[0].decode()
        self.assertIn('***5050**', html)
        self.assertNotIn('E2E ana', html, "The published list never names anyone.")
        self.assertNotIn('conduct', html.lower(), "Nor why someone is excluded.")
        mail = self._mails_to('hugo@example.com').filtered(lambda mail: provisional.name in (mail.subject or ''))
        self.assertTrue(mail, "Each student gets their provisional result.")
        self.assertIn('claim by replying', mail.body_html)
        self.assertIn('Reason:', self._mails_to('jan@example.com').body_html, "The excluded learn why.")
        self.assertEqual(self.env['ems.erasmus.resolution.line'].with_user(self.hos).search_count(
            [('resolution_id', '=', provisional.id)]), 10, "The Head of Studies reads the lists.")
        with self.assertRaises(AccessError, msg="The leader does not read the published lists."):
            self.env['ems.erasmus.resolution'].with_user(self.leader_user).search_read([], ['name'])

        # 7. hugo claims by email: a module was missing; the team enters the right average.
        registrations['hugo'].with_user(self.technician).write({
            'grade_manual': True, 'grade_average_manual': 8.5,
            'grade_manual_reason': "Claim: module 3 was not in EMS (academic record)"})
        self.assertEqual(registrations['hugo'].rank, 3)

        # 8. The definitive list waits for the claims deadline (as the calls' one).
        with self.assertRaises(UserError, msg="The students can still claim."):
            self._as(self.coordinator).action_approve_selection()
        self.mobility.sudo().claims_deadline = now - timedelta(minutes=1)
        with self.assertRaises(AccessError):
            self._as(self.technician).action_approve_selection()
        self._as(self.coordinator).action_approve_selection()
        self.assertEqual(self.mobility.state, 'preparation')
        definitive = self.mobility.resolution_ids - provisional
        self.assertEqual({name: result for name, (result, _rank) in self._list(definitive).items()}, {
            'ana': 'selected', 'ivet': 'selected', 'hugo': 'selected', 'bel': 'selected', 'cai': 'reserve',
            'dani': 'reserve', 'eva': 'reserve', 'fiona': 'reserve', 'gil': 'excluded', 'jan': 'excluded'})
        self.assertEqual(registrations['cai'].reserve_position, 1)
        self.assertEqual(self.mobility.selected_count, 4)
        self.assertIn('selected', self._mails_to('hugo@example.com').filtered(
            lambda mail: 'result of your enrolment' in (mail.subject or '')).body_html)
        with self.assertRaises(UserError, msg="The ranking is frozen once approved."):
            registrations['cai'].with_user(self.technician).fewer_opportunities_check = 'yes'
        self.assertEqual(self.mobility.participant_ids.filtered(lambda participant: participant.role == 'student')
                         .partner_id.mapped('name'), ['E2E ana', 'E2E bel', 'E2E hugo', 'E2E ivet'])

        # 9. The commitment letter: each student on the portal, the family of the minor on its own.
        ivet = self._participant('ivet')
        self.assertTrue(self._mails_to('family@example.com'), "The family is told when the file opens.")
        self.assertEqual(self.family._ems_erasmus_guardian_group_participants(), ivet)
        self.assertEqual(self.mobility.commitments_pending, 4)
        self.assertIn('still to be confirmed', ivet._ems_commitment_text())
        ivet.with_user(self.portal_users['ivet']).sudo().action_sign_commitment(True, '10.0.0.1')
        ivet.with_user(self.family_user).sudo().action_sign_commitment(True, '10.0.0.2', guardian=True)
        self.assertTrue(ivet.commitment_provisional, "Accepted before the destination was confirmed.")
        self.assertFalse(ivet.preparation_complete)
        self._as(self.technician).write({
            'city': 'Hamburg', 'country_id': self.env.ref('base.de').id, 'date_start': today + timedelta(days=120),
            'date_end': today + timedelta(days=134), 'travel_date_out': today + timedelta(days=120),
            'travel_date_back': today + timedelta(days=134)})
        self.assertEqual(len(ivet.commitment_version_ids), 1, "What was accepted is kept.")
        self.assertTrue(ivet.commitment_pending and ivet.commitment_guardian_pending)
        self.assertIn('Hamburg', ivet._ems_commitment_text())
        ivet.with_user(self.portal_users['ivet']).sudo().action_sign_commitment(True, '10.0.0.1')
        ivet.with_user(self.family_user).sudo().action_sign_commitment(True, '10.0.0.2', guardian=True)
        self.assertFalse(ivet.commitment_provisional)
        for name in ('ana', 'bel', 'hugo'):
            participant = self._participant(name)
            self.assertFalse(participant.commitment_guardian_pending, "An adult signs alone.")
            participant.with_user(self.portal_users[name]).sudo().action_sign_commitment(True, '10.0.0.3')
        self.assertEqual(self.mobility.commitments_pending, 0)

        # 10. Renouncing and the reserves: bel renounces; cai (first reserve) is proposed by the
        # leader and approved by the coordinator.
        bel = registrations['bel']
        bel.with_user(self.portal_users['bel']).sudo().action_renounce("Family reasons")
        self.assertEqual((bel.result, self._participant('bel').state), ('renounced', 'withdrawn'))
        self.assertEqual(self.mobility.next_reserve, 'E2E cai')
        with self.assertRaises(AccessError):
            self._as(self.companion_user).action_propose_substitution()
        self._as(self.leader_user).action_propose_substitution()
        with self.assertRaises(AccessError):
            registrations['cai'].with_user(self.leader_user).action_approve_substitution()
        registrations['cai'].with_user(self.coordinator).action_approve_substitution()
        self.assertEqual((registrations['cai'].result, registrations['cai'].substitute_for_id), ('selected', bel))
        self.assertEqual(self._participant('cai').state, 'active')
        self._participant('cai').with_user(self.portal_users['cai']).sudo().action_sign_commitment(True, '10.0.0.4')
        # hugo renounces too (the leader records it); the next reserve, the first drawn, is proposed
        # but does not want the place: the leader records it and the following one is proposed.
        self._renounce(registrations['hugo'], self.leader_user, "Health")
        self.assertEqual(self.mobility.next_reserve, first.name)
        self._as(self.leader_user).action_propose_substitution()
        declined = registrations[first.name.removeprefix('E2E ')]
        self.assertFalse(self.mobility.next_reserve, "A substitution is waiting for the coordinator.")
        with self.assertRaises(AccessError):
            self._renounce(declined, self.companion_user, "Not mine to say")
        self._renounce(declined, self.leader_user, "Does not want the place: told the leader")
        self.assertEqual((declined.result, declined.substitution_state, declined.reserve_position),
                         ('renounced', False, 0))
        self.assertEqual(self.mobility.next_reserve, second.name, "The queue moves on.")
        self._as(self.leader_user).action_propose_substitution()
        registrations[second.name.removeprefix('E2E ')].with_user(self.coordinator).action_approve_substitution()
        self.assertEqual(self.mobility.selected_count, 4)

        # 11. The documents: the team uploads and validates; the students upload from the portal;
        # the leader reviews what is not confidential; the accompanying teacher reviews nothing.
        active = self.mobility.participant_ids.filtered(lambda participant: participant.state == 'active')
        self.assertEqual(len(active), 6, "Four students and two teachers.")
        agreement = self._line(self.mobility, 'Group learning agreement (planned)')
        self.assertEqual(len(agreement), 1, "One shared learning agreement for the group.")
        self.assertFalse(self._line(self.mobility, 'Final list of participants'))
        card = self._line(ivet, 'European Health Insurance Card')
        authorisation = self._line(ivet, 'Authorisation for minors to travel abroad')
        self.assertTrue(authorisation.is_required)
        self.assertFalse(self._line(self._participant('ana'), 'Authorisation for minors to travel abroad').is_required)
        documents = self.env['ems.erasmus.application.document']
        self.assertNotIn(card, documents.with_user(self.leader_user).search([]), "Confidential: the team only.")
        with self.assertRaises(AccessError):
            documents.with_user(self.other_user).search([('group_mobility_id', '=', self.mobility.id)])
        ivet._ems_portal_upload({card.call_document_id.id: [('card.pdf', PDF)],
                                 authorisation.call_document_id.id: [('mossos.pdf', PDF)]})
        self.assertEqual(card.attachment_ids.mapped('name'), ['card.pdf'])
        with self.assertRaises(AccessError):
            authorisation.with_user(self.companion_user).action_mark_valid()
        authorisation.with_user(self.leader_user).action_mark_valid()
        # Insurance: the collective policy covers the students, the teachers have their own.
        policy = self._line(self.mobility, 'Collective insurance policy')
        self.assertFalse(policy.is_required)
        students = active.filtered(lambda participant: participant.role == 'student')
        students.with_user(self.technician).write({'insurance_collective': True})
        self.assertTrue(policy.is_required)
        self.assertFalse(any(self._line(students, 'Insurance policy').mapped('is_required')))
        self.assertTrue(all(self._line(active - students, 'Insurance policy').mapped('is_required')))
        for optional in ('Green Travel: sworn statement and evidence', 'Europass mobility document',
                         'Certificate of stay'):
            lines = self._line(self.mobility, optional) | self._line(active, optional)
            self.assertTrue(lines and not any(lines.mapped('is_required')), optional)
        self.assertEqual(ivet.auth_image, self.students['ivet'].auth_image, "The course's image rights.")
        # The Head of Studies reads every file but changes none.
        self.assertEqual(self.env['ems.erasmus.group.participant'].with_user(self.hos).search_count(
            [('group_mobility_id', '=', self.mobility.id)]), len(self.mobility.participant_ids))
        with self.assertRaises(AccessError):
            authorisation.with_user(self.hos).action_mark_valid()

        # 12. The participants' spreadsheet and the documents' ZIP: the team only.
        with self.assertRaises(AccessError):
            self._as(self.leader_user).action_export_participants()
        content = active.with_user(self.technician)._ems_participants_xlsx()
        rows = list(openpyxl.load_workbook(io.BytesIO(content)).active.iter_rows(values_only=True))
        self.assertEqual(len(rows), 1 + 6)
        with self.assertRaises(AccessError):
            self._as(self.leader_user).action_export_dossier()
        export = self.env['ems.erasmus.export'].with_user(self.technician).create({
            'scope': 'group', 'group_mobility_id': self.mobility.id, 'project_id': self.project.id})
        with zipfile.ZipFile(export._ems_zip()) as bundle:
            names = bundle.namelist()
        self.assertTrue(any(name.endswith('index.csv') for name in names))
        self.assertTrue(any('mossos.pdf' in name for name in names))
        self.assertFalse(any('card.pdf' in name for name in names), "Confidential: only in an audit export.")

        # 13. The stay: the leader starts it, both teachers write the follow-up, the leader ends
        # it, answers the programme question and the EU Survey; the team validates and closes.
        with self.assertRaises(AccessError):
            self._as(self.companion_user).action_start_stay()
        self._as(self.leader_user).action_start_stay()
        log = self.env['ems.erasmus.group.log'].with_user(self.companion_user).create({
            'group_mobility_id': self.mobility.id, 'kind': 'attendance', 'name': 'Day 1',
            'participant_ids': [(6, 0, self._participant('ana').ids)]})
        self.assertEqual(log.author_id, self.companion_user)
        with self.assertRaises(AccessError):
            self.env['ems.erasmus.group.log'].with_user(self.other_user).create({
                'group_mobility_id': self.mobility.id, 'name': 'Not mine'})
        self._as(self.leader_user).action_end_stay()
        self.assertEqual(self.mobility.state, 'return')
        with self.assertRaises(UserError, msg="The programme question first."):
            self._as(self.leader_user).action_propose_closure()
        self._as(self.leader_user).write({'programme_execution': 'changed'})
        with self.assertRaises(UserError):
            self._as(self.leader_user).action_propose_closure()
        self._as(self.leader_user).write({'programme_changes': "One company visit moved to the second week"})
        self._as(self.leader_user).action_eu_survey_done()
        self._as(self.leader_user).action_propose_closure()
        with self.assertRaises(UserError, msg="The EU Survey and every required document first."):
            self._as(self.technician).action_close()
        self._as(self.technician).action_eu_survey_validate()
        with self.assertRaises(UserError):
            self._as(self.technician).action_close()
        required = (self.mobility.document_ids | active.document_ids).filtered('is_required')
        for line in required.filtered(lambda line: not line.attachment_ids and not line.prepared_attachment_ids):
            line.sudo()._ems_add_files([('done.pdf', PDF)])
        required.signature_ids.with_user(self.technician).write({'signed': True})
        required.with_user(self.technician).action_mark_valid()
        with self.assertRaises(AccessError):
            self._as(self.leader_user).action_close()
        self._as(self.technician).action_close()
        self.assertEqual(self.mobility.state, 'done')
