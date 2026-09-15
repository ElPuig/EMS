from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study


def create_portal_schedule_fixtures(cls):
    """A main group with two classes (TPSC on Monday, TPSO on Tuesday), a student enrolled only in
    TPSC, a sibling enrolled only in TPSO, both with the same family contact, and portal users for
    the student and the family (login doubles as password)."""
    cls.level, cls.study = create_level_study(cls, 'TPSC', level={'name': 'Test Level (Portal Schedule)'}, study={
        'code': 'TPSC001', 'name': 'Test Study (Portal Schedule)', 'date': date.today(),
    })
    cls.subject, cls.other_subject = cls.env['ems.subject'].create([{
        'code': code, 'acronym': acronym, 'name': name, 'study_ids': [(6, 0, [cls.study.id])],
    } for code, acronym, name in (
        ('TPSC001', 'TPSC', 'Test Subject (Portal Schedule)'),
        ('TPSC002', 'TPSO', 'Test Other Subject (Portal Schedule)'),
    )])
    cls.space = cls.env['ems.space'].create({
        'code': 'TPSC-A', 'name': 'Test Space (Portal Schedule)',
        'space_type_id': cls.env.ref('ems.space_type_classroom').id,
        'work_location_id': cls.env.ref('ems.work_location_main').id,
    })
    cls.group = cls.env['ems.group'].create({
        'course': 1, 'acronym': 'TPSC', 'level_id': cls.level.id, 'study_id': cls.study.id,
        'space_id': cls.space.id, 'shift': 'morning',
    })
    teacher = cls.env['hr.employee'].create({'name': 'Test Teacher (Portal Schedule)', 'employee_type': 'teacher'})
    calendar = cls.env['resource.calendar'].create({'name': 'Test Calendar (Portal Schedule)'})
    teacher.resource_calendar_id = calendar
    calendar.apply_schedule_changes([{
        'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
        'subject_id': cls.subject.id, 'group_ids': [cls.group.id], 'name': 'TPSC: TPSC',
    }, {
        'dayofweek': '1', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
        'subject_id': cls.other_subject.id, 'group_ids': [cls.group.id], 'name': 'TPSO: TPSO',
    }])
    cls.student, cls.sibling, cls.family = cls.env['res.partner'].create([
        {'name': 'Portal Schedule Student', 'contact_type': 'student', 'main_group_id': cls.group.id},
        {'name': 'Portal Schedule Sibling', 'contact_type': 'student', 'main_group_id': cls.group.id},
        {'name': 'Portal Schedule Family', 'contact_type': 'family'},
    ])
    cls.env['ems.enrollment'].create([
        {'student_id': cls.student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id},
        {'student_id': cls.sibling.id, 'group_id': cls.group.id, 'subject_id': cls.other_subject.id},
    ])
    cls.env['res.partner.relation'].create([{
        'left_partner_id': cls.family.id, 'type_id': cls.env.ref('ems.relation_type_father').id,
        'right_partner_id': child.id,
    } for child in (cls.student, cls.sibling)])
    cls.student_user, cls.family_user = cls.env['res.users'].with_context(no_reset_password=True).create([{
        'name': partner.name, 'login': login, 'password': login, 'partner_id': partner.id,
        'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
    } for partner, login in (
        (cls.student, 'test_portal_schedule_student'),
        (cls.family, 'test_portal_schedule_family'),
    )])


@tagged('post_install', '-at_install')
class TestPortalSchedule(HttpCase):
    """Issue #453 - the student's schedule on the portal's Attendance card (/my/asistencia) and its
    on-request PDF. See docs/en/developers/contacts/student_schedule.md's "Student portal page"."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_portal_schedule_fixtures(cls)

    def _login(self, user):
        self.authenticate(user.login, user.login)

    def test_student_sees_only_their_own_classes(self):
        self._login(self.student_user)
        response = self.url_open('/my/asistencia')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.subject.name, response.text)
        self.assertNotIn(self.other_subject.name, response.text)
        self.assertIn('/my/asistencia/pdf', response.text)

    def test_student_downloads_their_pdf(self):
        self._login(self.student_user)
        response = self.url_open('/my/asistencia/pdf')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['Content-Type'].startswith('application/pdf'))
        self.assertIn(self.student.name.encode(), response.content)

    def test_family_sees_the_selected_child(self):
        self._login(self.family_user)
        self.family.selected_student_id = self.sibling
        response = self.url_open('/my/asistencia')
        self.assertIn(self.other_subject.name, response.text)
        self.assertNotIn(self.subject.name, response.text)

        self.family.selected_student_id = self.student
        response = self.url_open('/my/asistencia')
        self.assertIn(self.subject.name, response.text)
        self.assertNotIn(self.other_subject.name, response.text)

    def test_family_pdf_follows_the_selected_child(self):
        self._login(self.family_user)
        self.family.selected_student_id = self.sibling
        response = self.url_open('/my/asistencia/pdf')
        self.assertIn(self.sibling.name.encode(), response.content)
        self.assertNotIn(self.student.name.encode(), response.content)

    def test_family_without_students_gets_empty_state_and_no_pdf(self):
        lonely_family = self.env['res.partner'].create({'name': 'Portal Schedule Lonely Family', 'contact_type': 'family'})
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': lonely_family.name, 'login': 'test_portal_schedule_lonely', 'password': 'test_portal_schedule_lonely',
            'partner_id': lonely_family.id, 'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self._login(user)
        response = self.url_open('/my/asistencia')
        self.assertEqual(response.status_code, 200)
        self.assertIn('alert-info', response.text)
        self.assertNotIn('/my/asistencia/pdf', response.text)
        self.assertTrue(self.url_open('/my/asistencia/pdf').url.endswith('/my/asistencia'))

    def test_anonymous_visitor_is_sent_to_login(self):
        self.assertIn('/web/login', self.url_open('/my/asistencia').url)
        self.assertIn('/web/login', self.url_open('/my/asistencia/pdf').url)
