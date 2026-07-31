from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group


@tagged('post_install', '-at_install')
class TestNoDestinationTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # course=1: the student's current group.
        cls.level, cls.study, cls.group1 = create_level_study_group(
            cls, 'NDST',
            level={'name': 'Test Level (No Destination Tour)'},
            study={'code': 'NDST001', 'name': 'Test Study (No Destination Tour)', 'date': date.today()},
        )
        # course=2, same acronym/study: the suggested destination
        # (_ems_suggest_group matches by study_id + template.study_year + current group's acronym).
        cls.group2 = cls.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.template = cls.env['sale.order.template'].create({
            'name': 'No Destination Tour Template', 'ems_study_id': cls.study.id, 'study_year': 2,
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'No Destination Tour Student', 'contact_type': 'student',
            'study_id': cls.study.id, 'main_group_id': cls.group1.id,
        })
        # ems_course_id defaults to the real current/enrollment-default ems.course - no
        # ems_group_id, so transition_status computes to 'unplaced' (matches the action's
        # domain) until the tour's "Suggest destination group" action fills it in.
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.student.id, 'ems_study_id': cls.study.id,
            'sale_order_template_id': cls.template.id,
        })

    def test_no_destination_suggest_group_tour(self):
        self.assertFalse(self.order.ems_group_id)

        self.start_tour("/odoo", "ems_no_destination_suggest_group", login="admin")

        self.assertEqual(self.order.ems_group_id, self.group2)
