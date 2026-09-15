from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, create_role_employee, create_role_user, next_student_id


@tagged('post_install', '-at_install')
class TestStudentMyGroupsTour(HttpCase):
    """Issue #421: the Students action's default 'My students' facet, in a real browser and
    logged in as an actual teacher. See docs/en/developers/contacts/contact.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.taught_group = create_level_study_group(
            cls, 'TMYG',
            level={'name': 'Test Level (My Groups Tour)'},
            study={'name': 'Test Study (My Groups Tour)'},
        )
        cls.other_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TMYG001', 'acronym': 'TMYG', 'name': 'Test Subject (My Groups Tour)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        # create_role_user() always sets 'lang': 'en_US' - needed here since the tour asserts on
        # the literal English facet labels ("Students", "My students") and a fresh res.users
        # does not reliably default to en_US on this box (see CLAUDE.md's "Tour tests and
        # language").
        cls.teacher_user = create_role_user(
            cls, 'teacher', 'test_teacher_my_groups_tour', name='My Groups Tour Teacher')
        cls.teacher = create_role_employee(cls, cls.teacher_user, name='My Groups Tour Teacher')
        cls.env['ems.teaching'].create({
            'teacher_id': cls.teacher.id, 'group_id': cls.taught_group.id,
            'subject_id': cls.subject.id,
        })
        # "0000 "/"0001 " prefixes: res.partner's _order is "name", so both fixtures sort onto
        # the list's first page among the ~1000+ real students this DB already has - which is
        # what the last step, taken with the facet removed, actually needs (see
        # test_contact_tour.py for the same pattern).
        cls.own_student = cls.env['res.partner'].create({
            'name': '0000 My Groups Own Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'level_id': cls.level.id, 'study_id': cls.study.id,
            'main_group_id': cls.taught_group.id,
        })
        cls.other_student = cls.env['res.partner'].create({
            'name': '0001 My Groups Other Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'level_id': cls.level.id, 'study_id': cls.study.id,
            'main_group_id': cls.other_group.id,
        })

    def test_student_my_groups_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_student_my_groups", login="test_teacher_my_groups_tour", watch=True)
        self.start_tour("/odoo", "ems_student_my_groups",
                        login="test_teacher_my_groups_tour", step_delay=300)
