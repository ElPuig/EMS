from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestContactGroupChangeTour(HttpCase):
    """Issue #395: a tutor can change their tutorand's main group, and their subject
    enrollments follow. See docs/en/developers/contacts/contact.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'TCGC',
            level={'name': 'Test Level (Contact Group Change Tour)'},
            study={'name': 'Test Study (Contact Group Change Tour)'},
        )
        cls.other_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TCGC001', 'acronym': 'TCGC', 'name': 'Test Subject (Contact Group Change Tour)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        # A fresh res.users fixture does not reliably default to en_US (confirmed ca_ES on this
        # box) - explicit 'lang' avoids the tour flake documented in CLAUDE.md's "Tour tests and
        # language" (the tour asserts on the literal English "Studies" tab label).
        cls.tutor_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Contact Group Change Tour Tutor', 'login': 'test_tutor_contact_group_change_tour',
            'lang': 'en_US',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Contact Group Change Tour Tutor', 'employee_type': 'teacher',
            'user_id': cls.tutor_user.id,
        })
        cls.group.tutor_id = cls.tutor_employee
        # "0000 " prefix: res.partner's _order is "name", so this seeded student sorts
        # first on the list's very first page among the ~1000+ real students already in
        # this DB - rule_contact_teacher grants unrestricted read to any teacher/tutor, so
        # without this the fixture could land past the first page (see test_contact_tour.py
        # / test_withdrawal_tour.py for the same pattern).
        cls.student = cls.env['res.partner'].create({
            'name': '0000 Group Change Tour Student', 'contact_type': 'student',
            'level_id': cls.level.id, 'study_id': cls.study.id, 'main_group_id': cls.group.id,
        })
        cls.enrollment = cls.env['ems.enrollment'].create({
            'student_id': cls.student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id,
        })
        # 'other_group' has no tutor_id, so this student is visible to the tutor (unrestricted
        # read for any teacher, rule_contact_teacher) but is NOT their tutorand - used to
        # regression-test the "wpi_enrolled readable but writable by anyone" bug below.
        cls.non_tutorand_student = cls.env['res.partner'].create({
            'name': '0001 Group Change Tour Non-Tutorand', 'contact_type': 'student',
            'level_id': cls.level.id, 'study_id': cls.study.id, 'main_group_id': cls.other_group.id,
        })

    def test_tutor_can_change_student_main_group_tour(self):
        self.start_tour("/odoo", "ems_contact_group_change", login="test_tutor_contact_group_change_tour")

        self.assertEqual(self.student.main_group_id, self.other_group)
        self.assertFalse(self.enrollment.exists())
        moved = self.env['ems.enrollment'].search([('student_id', '=', self.student.id)])
        self.assertEqual(moved.group_id, self.other_group)

    def test_wpi_enrolled_is_readonly_for_a_non_tutorand_student_tour(self):
        # Regression (found 2026-09-06): 'wpi_enrolled' was missing 'read_only_user' from its
        # readonly condition (every sibling field in the tab combines both) - is_tutor_readonly
        # alone is False for a teacher who is not THIS student's own tutor, so the field looked
        # editable for any teacher viewing any other student, not just their own tutorands.
        self.start_tour("/odoo", "ems_contact_wpi_readonly_for_non_tutorand",
                         login="test_tutor_contact_group_change_tour")
