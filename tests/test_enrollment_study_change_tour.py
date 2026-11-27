from odoo.tests import HttpCase, tagged

from .common import create_level_study, create_role_user, mock_outgoing_email, next_student_id


@tagged('post_install', '-at_install')
class TestEnrollmentStudyChangeTour(HttpCase):
    """Issue #875: the secretary changes a confirmed enrollment's studies from its Actions dropdown."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        course = cls.env['ems.course'].create({'start': 2098, 'end': 2099})
        cls.env.company.current_course_id = course.id
        level, old_study = create_level_study(cls, 'SCTO')
        cls.new_study = cls.env['ems.study'].create({
            'code': 'SCTN-01', 'acronym': 'SCTN', 'name': 'SCT New Study', 'date': '2026-01-01',
            'deprecated': False, 'level_id': level.id})
        groups, subjects = {}, {}
        for study in (old_study, cls.new_study):
            groups[study] = cls.env['ems.group'].create({
                'course': 2, 'acronym': 'A', 'shift': 'morning', 'level_id': level.id, 'study_id': study.id})
            subject = subjects[study] = cls.env['ems.subject'].create({
                'code': f'{study.acronym}SUB', 'acronym': f'{study.acronym}S', 'name': f'{study.acronym} subject',
                'study_ids': [(6, 0, study.ids)]})
            cls.env['sale.order.template'].create({
                'name': f'{study.acronym}-2', 'ems_study_id': study.id, 'study_year': 2,
                'sale_order_template_line_ids': [(0, 0, {'product_id': subject.product_id.id, 'name': subject.name})]})
        cls.new_group = groups[cls.new_study]
        cls.student = cls.env['res.partner'].create({
            'name': 'Study Change Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'birth_date': '2000-01-01', 'main_group_id': groups[old_study].id})
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.student.id, 'ems_study_id': old_study.id, 'ems_course_id': course.id,
            'shift': 'morning', 'ems_group_id': groups[old_study].id,
            'order_line': [(0, 0, {'product_id': subjects[old_study].product_id.id})]})
        cls.order.action_confirm()
        cls.secretary = create_role_user(cls, 'secretary', 'sct_secretary', email='sct_secretary@example.com')

    def test_secretary_changes_studies_tour(self):
        self.start_tour("/odoo", "enrollment_study_change", login="sct_secretary")
        self.assertEqual(self.order.ems_study_id, self.new_study)
        self.assertEqual(self.student.main_group_id, self.new_group)
