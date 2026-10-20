# -*- coding: utf-8 -*-

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from .common import create_role_employee, create_role_user


class MinuteRulesFixtures:
    """Two teachers, each in a department of their own, and a way to make a minute."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.type = cls.env.ref('__import__.minute_type_dep')
        cls.course = cls.env['ems.course'].search([('is_current', '=', True)], limit=1)
        cls.dep_a = cls.env['hr.department'].create({'name': 'Rules Department A'})
        cls.dep_b = cls.env['hr.department'].create({'name': 'Rules Department B'})
        # Distinct names on purpose: the helper derives the employee name from the user's, and the
        # working calendar it creates has a unique name constraint.
        cls.user_a = create_role_user(cls, 'teacher', 'rules.a@example.com', name='Rules Teacher A')
        cls.employee_a = create_role_employee(cls, cls.user_a, department_id=cls.dep_a.id)
        cls.user_b = create_role_user(cls, 'teacher', 'rules.b@example.com', name='Rules Teacher B')
        cls.employee_b = create_role_employee(cls, cls.user_b, department_id=cls.dep_b.id)

    def _minute(self, department, **overrides):
        vals = {'type_id': self.type.id, 'department_id': department.id, 'course_id': self.course.id,
                'date': fields.Date.context_today(self.env['ems.minute'])}
        vals.update(overrides)
        return self.env['ems.minute'].create(vals)


class TestQualityMinuteRules(MinuteRulesFixtures, TransactionCase):
    """Without record rules every teacher could read and write every minute, which is the gap these
    rules close. Worth testing because access rights alone say nothing about *which* records."""

    def test_a_teacher_reads_their_own_department_minute(self):
        minute = self._minute(self.dep_a)
        self.assertTrue(minute.with_user(self.user_a).read(['name']))

    def test_a_teacher_does_not_read_another_department_minute(self):
        minute = self._minute(self.dep_b, attendee_ids=[(6, 0, [])])
        found = self.env['ems.minute'].with_user(self.user_a).search([('id', '=', minute.id)])
        self.assertFalse(found, "another department's minute is none of this teacher's business")

    def test_an_attendee_reads_the_minute_whatever_the_scope(self):
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        minute = self._minute(self.dep_b, attendee_ids=[(6, 0, public_a.ids)])
        self.assertTrue(minute.with_user(self.user_a).read(['name']))

    def test_an_approved_minute_cannot_be_edited_by_the_teaching_staff(self):
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        minute = self._minute(self.dep_a, redactor_employee_id=public_a.id)
        minute.section_value_ids.filtered(lambda value: value.required).content = "<p>Discussed.</p>"
        minute.action_submit()
        minute.action_approve()
        with self.assertRaises(AccessError):
            minute.with_user(self.user_a).write({'abstract': 'changed after approval'})

    def test_an_attendee_who_did_not_write_it_gets_it_read_only(self):
        """The form shows a minute as plain reading from can_edit: an attendee may read it but
        not write it, so it must say so instead of offering fields the save would refuse."""
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        public_b = self.env['hr.employee.public'].browse(self.employee_b.id)
        minute = self._minute(self.dep_b, attendee_ids=[(6, 0, public_a.ids)], redactor_employee_id=public_b.id,
                              approver_employee_id=public_b.id)
        self.assertFalse(minute.with_user(self.user_a).can_edit)
        self.assertTrue(minute.with_user(self.user_b).can_edit)

    def _ready_minute(self, **overrides):
        minute = self._minute(self.dep_a, **overrides)
        minute.section_value_ids.filtered(lambda value: value.required).content = "<p>Discussed.</p>"
        minute.action_submit()
        return minute

    def test_whoever_writes_the_minute_does_not_approve_it(self):
        """Being able to edit a minute is not being the one who approves it: the writer gets
        neither the button nor, through any other way in, the approval itself."""
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        public_b = self.env['hr.employee.public'].browse(self.employee_b.id)
        minute = self._ready_minute(redactor_employee_id=public_a.id, approver_employee_id=public_b.id)
        self.assertFalse(minute.with_user(self.user_a).can_approve)
        with self.assertRaises(UserError):
            minute.with_user(self.user_a).action_approve()
        self.assertEqual(minute.state, 'to_approve')

    def test_the_person_named_to_approve_it_does(self):
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        public_b = self.env['hr.employee.public'].browse(self.employee_b.id)
        minute = self._ready_minute(redactor_employee_id=public_a.id, approver_employee_id=public_b.id)
        self.assertTrue(minute.with_user(self.user_b).can_approve)
        minute.with_user(self.user_b).action_approve()
        self.assertEqual(minute.state, 'approved')
        self.assertEqual(minute.approver_employee_id, public_b)

    def test_the_chain_of_command_of_whoever_writes_it_edits_it(self):
        """A Seminar Chief above the teacher who writes the minute edits it too, even when somebody
        else (a Department Chief above that Seminar Chief) approves it; a chief from another branch
        does not."""
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        public_b = self.env['hr.employee.public'].browse(self.employee_b.id)
        seminar_chief = create_role_user(self, 'department_chief', 'rules.writer.chief@example.com', name='Rules Writer Chief')
        self.employee_a.parent_id = create_role_employee(self, seminar_chief)
        other_chief = create_role_user(self, 'department_chief', 'rules.writer.other@example.com', name='Rules Writer Other')
        create_role_employee(self, other_chief)
        minute = self._minute(self.dep_a, redactor_employee_id=public_a.id, approver_employee_id=public_b.id)
        self.assertTrue(minute.with_user(seminar_chief).can_edit)
        minute.with_user(seminar_chief).write({'abstract': 'Completed by the seminar chief'})
        with self.assertRaises(AccessError):
            minute.with_user(other_chief).write({'abstract': 'Not my branch'})

    def test_the_chain_of_command_of_whoever_approves_it_stands_in(self):
        """When the person named to approve it is away, whoever is above them approves it instead
        (and may write it to do so); a chief from another branch may not."""
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        chief = create_role_user(self, 'department_chief', 'rules.approver.chief@example.com', name='Rules Approver Chief')
        chief_employee = create_role_employee(self, chief)
        other_chief = create_role_user(self, 'department_chief', 'rules.other.chief@example.com', name='Rules Other Chief')
        create_role_employee(self, other_chief)
        self.employee_b.parent_id = chief_employee
        public_b = self.env['hr.employee.public'].browse(self.employee_b.id)
        minute = self._ready_minute(redactor_employee_id=public_a.id, approver_employee_id=public_b.id)
        self.assertTrue(minute.with_user(chief).can_approve)
        self.assertFalse(minute.with_user(other_chief).can_approve)
        # Refused either way: they cannot even read it (AccessError), let alone approve it.
        with self.assertRaises(Exception):
            minute.with_user(other_chief).action_approve()
        minute.with_user(chief).action_approve()
        self.assertEqual(minute.state, 'approved')
        self.assertEqual(minute.approver_employee_id.id, chief_employee.id, "it says who actually approved it")

    def test_with_nobody_named_the_holders_of_the_post_approve_it(self):
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        role = self.env['ems.role'].create({'name': 'Rules Approver Post', 'employee_type': 'teacher',
                                            'employee_ids': [(6, 0, [self.employee_b.id])]})
        minute = self._ready_minute(redactor_employee_id=public_a.id, approver_role_id=role.id)
        minute.approver_employee_id = False
        self.assertFalse(minute.with_user(self.user_a).can_approve)
        self.assertTrue(minute.with_user(self.user_b).can_approve)

    def test_the_secretariat_sees_only_its_own_scopes(self):
        """The secretariat no longer oversees every minute: it goes by its own scopes, like the
        rest of the staff. It needs a rule of its own - in none, it would see them all."""
        minute = self._minute(self.dep_b)
        user = create_role_user(self, 'secretary', 'rules.secretary@example.com', name='Rules Secretary')
        create_role_employee(self, user, employee_type='asp')
        found = self.env['ems.minute'].with_user(user).search([('id', '=', minute.id)])
        self.assertFalse(found)

    def test_the_head_of_studies_above_a_department_sees_its_minutes(self):
        """A department's minutes reach the Head or Deputy Head of Studies it hangs from (through
        its Department Chief's parent), not every holder of the post."""
        own_hos = create_role_user(self, 'head_of_studies', 'rules.hos.own@example.com', name='Rules Own HoS')
        own_hos_employee = create_role_employee(self, own_hos)
        other_hos = create_role_user(self, 'head_of_studies', 'rules.hos.other@example.com', name='Rules Other HoS')
        create_role_employee(self, other_hos)
        chief = create_role_user(self, 'department_chief', 'rules.chief@example.com', name='Rules Chief')
        chief_employee = create_role_employee(self, chief)
        # As the centre has it (FP above Informàtica): the area's department is managed by its Head
        # of Studies, and the department cascade hangs the chief of the one below from them.
        area = self.env['hr.department'].create({'name': 'Rules Area', 'manager_id': own_hos_employee.id})
        department = self.env['hr.department'].create({
            'name': 'Rules Chained Department', 'parent_id': area.id, 'manager_id': chief_employee.id,
        })
        self.assertEqual(chief_employee.parent_id, own_hos_employee)
        minute = self._minute(department, attendee_ids=[(6, 0, [])])
        Minute = self.env['ems.minute']
        self.assertTrue(Minute.with_user(own_hos).search([('id', '=', minute.id)]))
        self.assertFalse(Minute.with_user(other_hos).search([('id', '=', minute.id)]))

    def test_the_quality_committee_sees_every_minute(self):
        minute = self._minute(self.dep_b, attendee_ids=[(6, 0, [])])
        self.user_a.groups_id = [(4, self.env.ref('ems.group_quality').id)]
        self.assertTrue(self.env['ems.minute'].with_user(self.user_a).search([('id', '=', minute.id)]))

    def test_a_teacher_does_not_see_another_department_action_plan(self):
        minute = self._minute(self.dep_b)
        action = self.env['ems.quality.action'].create({
            'name': "Someone else's action", 'type': 'corrective', 'minute_id': minute.id,
            'course_id': self.course.id, 'department_id': self.dep_b.id,
        })
        found = self.env['ems.quality.action'].with_user(self.user_a).search([('id', '=', action.id)])
        self.assertFalse(found)

    def test_a_teacher_sees_the_action_they_are_responsible_for(self):
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        action = self.env['ems.quality.action'].create({
            'name': 'Mine to do', 'type': 'agreement', 'course_id': self.course.id,
            'department_id': self.dep_b.id, 'responsible_employee_ids': [(6, 0, public_a.ids)],
        })
        found = self.env['ems.quality.action'].with_user(self.user_a).search([('id', '=', action.id)])
        self.assertIn(action, found, "an action is visible to whoever has to do it, wherever it came from")


class TestQualityMinuteAttendanceCorrection(MinuteRulesFixtures, TransactionCase):
    """A tag left at home or a broken one: whoever runs the meeting corrects its NFC attendance by
    hand, from the minute, while it is not approved. Head of Studies, the secretariat and the
    administrator keep every session from Meetings > Attendance."""

    def _nfc_minute(self):
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        public_b = self.env['hr.employee.public'].browse(self.employee_b.id)
        return self._minute(
            self.dep_a, attendance_mode='nfc', start_datetime=fields.Datetime.now(), duration=1.0,
            redactor_employee_id=public_a.id, attendee_ids=[(6, 0, (public_a | public_b).ids)])

    def test_whoever_writes_the_minute_corrects_its_attendance(self):
        minute = self._nfc_minute()
        action = minute.with_user(self.user_a).action_correct_attendance()
        self.assertEqual((action['res_model'], action['res_id']), ('ems.meeting.presence', minute.presence_id.id))
        line = minute.presence_id.line_ids.filtered(lambda item: item.employee_id.id == self.employee_b.id)
        line.with_user(self.user_a).write({'state': 'present'})
        self.assertEqual(line.method, 'manual')
        self.assertIn(self.employee_b.id, minute.attendee_ids.ids, "the minute's lists follow the correction at once")

    def test_an_attendee_who_does_not_write_it_cannot_correct_it(self):
        minute = self._nfc_minute()
        found = self.env['ems.meeting.presence'].with_user(self.user_b).search([('id', '=', minute.presence_id.id)])
        self.assertFalse(found)

    def test_an_approved_minute_freezes_its_attendance(self):
        minute = self._nfc_minute()
        minute.section_value_ids.filtered(lambda value: value.required).content = "<p>Discussed.</p>"
        minute.action_submit()
        minute.action_approve()
        line = minute.presence_id.line_ids[:1]
        with self.assertRaises(AccessError):
            line.with_user(self.user_a).write({'state': 'absent'})

    def test_head_of_studies_keeps_every_session(self):
        minute = self._nfc_minute()
        hos = create_role_user(self, 'head_of_studies', 'rules.attendance.hos@example.com', name='Rules Attendance HoS')
        self.assertTrue(self.env['ems.meeting.presence'].with_user(hos).search([('id', '=', minute.presence_id.id)]))
