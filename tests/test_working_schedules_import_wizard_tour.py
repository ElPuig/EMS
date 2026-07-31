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

    def test_working_schedules_import_pending_teacher_tour(self):
        self.start_tour("/odoo", "ems_working_schedules_import_pending_teacher", login="admin")

    def test_employee_pending_identification_indicator_tour(self):
        # "0000 " prefix: hr.employee's default _order is "name", so this sorts first on the
        # list's very first page among the pre-existing teachers in this DB (same convention as
        # TestEmployeeGoogleWorkspaceTour._seed_teacher).
        self.env['hr.employee'].create({
            'name': '0000 Tour Pending Teacher',
            'employee_type': 'teacher',
            'schedule_import_code': 'TOURBADGE',
        })
        self.start_tour("/odoo", "ems_employee_pending_identification_indicator", login="admin")
