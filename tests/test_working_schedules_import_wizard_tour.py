from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestWorkingSchedulesImportWizardTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The wizard's create() requires a "current course" (company.current_course_id).
        if not cls.env.company.current_course_id:
            cls.env.company.current_course_id = cls.env['ems.course'].create({'start': 2098, 'end': 2099})

    def test_working_schedules_import_unknown_teacher_tour(self):
        self.start_tour("/odoo", "ems_working_schedules_import_unknown_teacher", login="admin")
