from odoo.tests.common import HttpCase, tagged

from .common import create_level_study


@tagged('post_install', '-at_install')
class TestScheduleFrameworkTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(
            cls, 'TSFT', level={'name': 'Test Level (Schedule Framework Tour)'},
            study={'name': 'Test Study (Schedule Framework Tour)'},
        )
        cls.framework = cls.env['resource.calendar'].create({
            'name': 'Tour Schedule Framework', 'is_framework': True,
        })

    def test_schedule_framework_edit_tour(self):
        self.assertFalse(self.framework.level_id)

        self.start_tour("/odoo", "ems_schedule_framework_edit", login="admin")

        self.assertEqual(self.framework.level_id, self.level)
