from odoo.tests.common import Form, TransactionCase

from .common import create_level_study_group, next_student_id


def create_subject_group_fixture(cls, prefix):
    """A two-course study (groups <prefix>1A/<prefix>2A, enrollment templates for each year),
    a reinforcement group, a 2nd-year student and four subjects: one sold by the 1st-year
    template, one by the 2nd-year one, one sold by neither, and one belonging to a different
    study. Shared by the backend tests and the tour."""
    cls.level, cls.study, cls.group_1a = create_level_study_group(
        cls, prefix, level={'name': f'Test Level ({prefix})'}, study={'name': f'Test Study ({prefix})'})
    cls.group_2a = cls.env['ems.group'].create({
        'course': 2, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
    })
    cls.reinforcement = cls.env['ems.group'].create({
        'group_type': 'reinforcement', 'name': f'{prefix} Reinforcement',
    })
    _other_level, cls.other_study, _other_group = create_level_study_group(
        cls, f'{prefix}O', level={'name': f'Test Level ({prefix} other)'}, study={'name': f'Test Study ({prefix} other)'})

    def subject(code, name, study):
        return cls.env['ems.subject'].create({
            'code': f'{prefix}{code}', 'acronym': f'{prefix}{code}', 'name': f'{prefix} {name}',
            'study_ids': [(6, 0, [study.id])],
        })
    cls.subject_year1 = subject('01', 'First Year Module', cls.study)
    cls.subject_year2 = subject('02', 'Second Year Module', cls.study)
    cls.subject_untemplated = subject('03', 'Untemplated Module', cls.study)
    cls.subject_foreign = subject('04', 'Foreign Module', cls.other_study)
    for year, subj in ((1, cls.subject_year1), (2, cls.subject_year2)):
        cls.env['sale.order.template'].create({
            'name': f'{prefix}-{year}', 'ems_study_id': cls.study.id, 'study_year': year,
            'sale_order_template_line_ids': [(0, 0, {'product_id': subj.product_id.id})],
        })
    # "0000 " prefix: sorts first among the real students already in the database (see
    # test_contact_group_change_tour.py for the same pattern).
    cls.student = cls.env['res.partner'].create({
        'name': f'0000 {prefix} Student', 'contact_type': 'student', 'student_id': next_student_id(),
        'level_id': cls.level.id, 'study_id': cls.study.id, 'main_group_id': cls.group_2a.id,
    })


class TestEnrollmentSubjectGroup(TransactionCase):
    """A subject added by hand on the student's form defaults to the group of the course its
    enrollment template sells it for. See docs/en/developers/contacts/enrollment.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_subject_group_fixture(cls, 'TESG')

    def _add_line(self, subject, group=None):
        with Form(self.student) as form:
            with form.enrollment_ids.new() as line:
                if group:
                    line.group_id = group
                line.subject_id = subject
        return self.student.enrollment_ids.filtered(lambda enrollment: enrollment.subject_id == subject)

    def test_line_defaults_to_main_group(self):
        with Form(self.student) as form:
            with form.enrollment_ids.new() as line:
                self.assertEqual(line.group_id, self.group_2a)
                line.subject_id = self.subject_year2

    def test_subject_of_another_course_goes_to_that_course_group(self):
        self.assertEqual(self._add_line(self.subject_year1).group_id, self.group_1a)

    def test_subject_of_the_main_group_course_stays_in_main_group(self):
        self.assertEqual(self._add_line(self.subject_year2).group_id, self.group_2a)

    def test_subject_in_no_template_stays_in_main_group(self):
        self.assertEqual(self._add_line(self.subject_untemplated).group_id, self.group_2a)

    def test_reinforcement_group_is_kept(self):
        self.assertEqual(self._add_line(self.subject_year1, group=self.reinforcement).group_id, self.reinforcement)

    def test_group_for_subject_matches_placement(self):
        self.assertEqual(self.group_2a._ems_group_for_subject(self.subject_year1), self.group_1a)
        self.assertEqual(self.group_2a._ems_group_for_subject(self.subject_year2), self.group_2a)
        self.assertEqual(self.group_1a._ems_group_for_subject(self.subject_year2), self.group_2a)

