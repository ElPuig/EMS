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

    def test_working_schedules_import_resolve_group_tour(self):
        # Seeds a real group the tour's XML deliberately does NOT name exactly (a reinforcement
        # group needs no level/study/course, matching the existing backend test's own
        # 'reinforcement_group' fixture) - the tour picks it via the 'groups' step's Many2one to
        # prove that new screen actually renders and resolves in a real browser, not just at the
        # TransactionCase level (see TestWorkingSchedulesImportWizard.
        # test_continue_from_groups_resolves_pending_group_and_completes_import).
        space = self.env['ems.space'].create({
            'code': 'TOURRESOLVEGROUP-A',
            'name': 'Tour Resolve Group Space',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        self.env['ems.subject'].create({
            'code': 'TOURRESOLVEGROUP',
            'acronym': 'TRSVG',
            'name': 'Tour Resolve Group Subject',
        })
        self.env['ems.group'].create({
            'group_type': 'reinforcement',
            'name': 'Tour Resolve Group',
            'space_id': space.id,
        })
        self.start_tour("/odoo", "ems_working_schedules_import_resolve_group", login="admin")

    def test_working_schedules_import_resolve_teacher_email_tour(self):
        # Seeds a real teacher the tour's XML deliberately does NOT reference by e-mail - the tour
        # picks it via the 'teachers' step's Many2one to prove that new screen actually renders and
        # resolves in a real browser (see TestWorkingSchedulesImportWizard.
        # test_continue_from_teachers_resolves_pending_email_and_completes_import).
        self.env['hr.employee'].create({
            'name': 'Tour Resolve Teacher Email',
            'employee_type': 'teacher',
        })
        self.start_tour("/odoo", "ems_working_schedules_import_resolve_teacher_email", login="admin")

    def test_employee_pending_identification_indicator_tour(self):
        # "0000 "/"0001 " prefixes: hr.employee's default _order is "name", so these sort first on
        # the list's very first page among the pre-existing teachers in this DB (same convention as
        # TestEmployeeGoogleWorkspaceTour._seed_teacher). A confirmed-identity teacher is seeded
        # alongside the pending one so the tour can prove the kanban badge shows on the right card
        # only, not on every card regardless of pending_identification.
        self.env['hr.employee'].create({
            'name': '0000 Tour Pending Teacher',
            'employee_type': 'teacher',
            'schedule_import_code': 'TOURBADGE',
        })
        self.env['hr.employee'].create({
            'name': '0001 Tour Confirmed Teacher',
            'employee_type': 'teacher',
        })
        self.start_tour("/odoo", "ems_employee_pending_identification_indicator", login="admin")
