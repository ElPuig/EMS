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

    def test_working_schedules_import_create_new_teacher_tour(self):
        # No teacher fixture is seeded here on purpose - 'tour.create.new.teacher@example.com'
        # must genuinely not match any existing employee, so the tour's own 'Create new' tick is
        # what resolves the row (see TestWorkingSchedulesImportWizard.
        # test_continue_from_teachers_create_new_creates_pending_teacher_with_manual_email).
        self.start_tour("/odoo", "ems_working_schedules_import_create_new_teacher", login="admin")

    def test_working_schedules_import_resolve_internal_conflict_tour(self):
        # Two reinforcement groups (no level/study/course needed, same simplification as the
        # 'resolve_group' tour's own fixture) sharing the SAME classroom - the "desdoble" (split
        # session) shape screen 4 needs to detect and let the admin resolve by reassigning one
        # side's room (see TestWorkingSchedulesImportWizard.
        # test_continue_from_internal_conflicts_reassign_rooms_writes_different_rooms_and_completes_import).
        shared_space = self.env['ems.space'].create({
            'code': 'TOURRESOLVECONFLICT-A',
            'name': 'Tour Resolve Conflict Space A',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        self.env['ems.space'].create({
            'code': 'TOURRESOLVECONFLICT-B',
            'name': 'Tour Resolve Conflict Space B',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        self.env['ems.subject'].create({
            'code': 'TOURRESOLVECONFLICT',
            'acronym': 'TRSVC',
            'name': 'Tour Resolve Conflict Subject',
        })
        self.env['ems.group'].create({
            'group_type': 'reinforcement',
            'name': 'Tour Resolve Conflict Group A',
            'space_id': shared_space.id,
        })
        self.env['ems.group'].create({
            'group_type': 'reinforcement',
            'name': 'Tour Resolve Conflict Group B',
            'space_id': shared_space.id,
        })
        self.env['hr.employee'].create({
            'name': 'Tour Resolve Conflict Teacher A',
            'employee_type': 'teacher',
            'work_email': 'tour.resolve.conflict.a@example.com',
        })
        self.env['hr.employee'].create({
            'name': 'Tour Resolve Conflict Teacher B',
            'employee_type': 'teacher',
            'work_email': 'tour.resolve.conflict.b@example.com',
        })
        self.start_tour("/odoo", "ems_working_schedules_import_resolve_internal_conflict", login="admin")

    def test_working_schedules_import_resolve_db_conflict_tour(self):
        # Seeds a REAL, already-active 'ems.attendance_schedule' directly via the ORM (teacher A,
        # sharing 'Tour Resolve DB Conflict Space A' with a sibling reinforcement group B) - the
        # tour then imports a SECOND, different teacher into group B, a "desdoble" against this
        # existing DB session rather than another entry in the same batch (see
        # TestWorkingSchedulesImportWizard.
        # test_continue_from_db_conflicts_reassign_rooms_with_has_sessions_archives_and_clones for
        # the has_sessions branch - this tour only needs to prove the screen itself renders and
        # resolves in a real browser, matching the internal-conflict tour's own scope).
        shared_space = self.env['ems.space'].create({
            'code': 'TOURRESOLVEDBCONFLICT-A',
            'name': 'Tour Resolve DB Conflict Space A',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        self.env['ems.space'].create({
            'code': 'TOURRESOLVEDBCONFLICT-B',
            'name': 'Tour Resolve DB Conflict Space B',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        subject = self.env['ems.subject'].create({
            'code': 'TOURRESOLVEDBCONFLICT',
            'acronym': 'TRSVDB',
            'name': 'Tour Resolve DB Conflict Subject',
        })
        group_a = self.env['ems.group'].create({
            'group_type': 'reinforcement',
            'name': 'Tour Resolve DB Conflict Group A',
            'space_id': shared_space.id,
        })
        self.env['ems.group'].create({
            'group_type': 'reinforcement',
            'name': 'Tour Resolve DB Conflict Group B',
            'space_id': shared_space.id,
        })
        teacher_a = self.env['hr.employee'].create({
            'name': 'Tour Resolve DB Conflict Teacher A',
            'employee_type': 'teacher',
            'work_email': 'tour.resolve.dbconflict.a@example.com',
        })
        self.env['hr.employee'].create({
            'name': 'Tour Resolve DB Conflict Teacher B',
            'employee_type': 'teacher',
            'work_email': 'tour.resolve.dbconflict.b@example.com',
        })
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [teacher_a.id])],
            'subject_id': subject.id,
            'group_ids': [(6, 0, [group_a.id])],
            'space_id': shared_space.id,
            'start_date': '2026-01-01',
            'end_date': '2026-06-30',
        })
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id,
            'weekday': '0',
            'start_time': 9.0,
            'end_time': 13.0,
            'space_id': shared_space.id,
        })
        self.start_tour("/odoo", "ems_working_schedules_import_resolve_db_conflict", login="admin")

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
