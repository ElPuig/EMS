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

    def test_working_schedules_import_resolve_subject_mismatch_tour(self):
        # Real error this screen was built for (2026-08-10): a file subject code that resolves to
        # a real 'ems.subject', but one that isn't taught in the group's own study - 'wrong_subject'
        # below has no 'study_ids' at all, so it can never satisfy ANY group's study. The tour picks
        # the correct one via the 'subjects' step's own domain-restricted Many2one to prove that
        # new screen actually renders and resolves in a real browser (see
        # TestWorkingSchedulesImportWizard.test_continue_from_subjects_applies_correction_and_completes_import).
        level = self.env['ems.level'].create({'acronym': 'TOURSUBJ', 'name': 'Tour Subject Mismatch Level'})
        study = self.env['ems.study'].create({
            'code': 'TOURSUBJ', 'acronym': 'TSUBJ', 'name': 'Tour Subject Mismatch Study',
            'date': '2026-01-01', 'deprecated': False, 'level_id': level.id,
        })
        space = self.env['ems.space'].create({
            'code': 'TOURSUBJMISMATCH',
            'name': 'Tour Subject Mismatch Space',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        self.env['ems.subject'].create({
            'code': 'TOURSUBJCORRECT',
            'acronym': 'TSC',
            'name': 'Tour Subject Correct',
            'study_ids': [(6, 0, [study.id])],
        })
        self.env['ems.subject'].create({
            'code': 'TOURSUBJWRONG',
            'acronym': 'TSW',
            'name': 'Tour Subject Wrong',
        })
        self.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id, 'space_id': space.id,
        })
        self.env['hr.employee'].create({
            'name': 'Tour Subject Mismatch Teacher',
            'employee_type': 'teacher',
            'work_email': 'tour.subject.mismatch@example.com',
        })
        self.start_tour("/odoo", "ems_working_schedules_import_resolve_subject_mismatch", login="admin")

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

    def test_working_schedules_import_resolve_self_conflict_tour(self):
        # Two placeholder codes in the SAME file, both manually assigned to the SAME real teacher
        # (the "same person as" merge confirmed 2026-08-10) - their own entries collide in time but
        # NOT in room, proving the 'self_conflict' kind actually renders and resolves in a real
        # browser (see TestWorkingSchedulesImportWizard.
        # test_continue_from_teachers_builds_self_conflict_line_when_two_identifiers_resolve_to_same_employee).
        space_a = self.env['ems.space'].create({
            'code': 'TOURSELFCONFLICT-A',
            'name': 'Tour Self Conflict Space A',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        space_b = self.env['ems.space'].create({
            'code': 'TOURSELFCONFLICT-B',
            'name': 'Tour Self Conflict Space B',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        self.env['ems.subject'].create({
            'code': 'TOURSELFCONFLICT',
            'acronym': 'TRSVSC',
            'name': 'Tour Self Conflict Subject',
        })
        self.env['ems.group'].create({
            'group_type': 'reinforcement',
            'name': 'Tour Self Conflict Group A',
            'space_id': space_a.id,
        })
        self.env['ems.group'].create({
            'group_type': 'reinforcement',
            'name': 'Tour Self Conflict Group B',
            'space_id': space_b.id,
        })
        self.env['hr.employee'].create({
            'name': 'Tour Self Conflict Teacher',
            'employee_type': 'teacher',
        })
        self.start_tour("/odoo", "ems_working_schedules_import_resolve_self_conflict", login="admin")

    def test_working_schedules_import_bulk_apply_resolution_tour(self):
        # Developer feedback (2026-08-10, hit resolving a large real batch by hand): "me iría bien
        # que estuvieran agrupadas por tipo... y por 'left', y que cada grupo me permitiera escoger
        # el resolution que se aplica al grupo entero." Three groups sharing the SAME classroom -
        # the anchor teacher's own entry collides (desdoble) with BOTH other teachers' entries at
        # the exact same slot, forming one sub-group (same left_label: the anchor's own entry) with
        # TWO rows underneath it - proves the sub-group's own bulk-resolution dropdown actually
        # writes onto every row in that sub-group at once, not just one.
        space = self.env['ems.space'].create({
            'code': 'TOURBULKAPPLY',
            'name': 'Tour Bulk Apply Space',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        self.env['ems.subject'].create({
            'code': 'TOURBULKAPPLY',
            'acronym': 'TRBLKA',
            'name': 'Tour Bulk Apply Subject',
        })
        for letter in 'ABC':
            self.env['ems.group'].create({
                'group_type': 'reinforcement',
                'name': f'Tour Bulk Apply Group {letter}',
                'space_id': space.id,
            })
        self.start_tour("/odoo", "ems_working_schedules_import_bulk_apply_resolution", login="admin")

    def test_working_schedules_import_conflicts_beyond_default_page_size_tour(self):
        # Developer feedback (2026-08-10, right after the fixed 'limit="1000"' fix landed): "si
        # tuviéramos más de 1000 conflictos estaríamos en las mismas... ¿no se puede paginar, o de
        # alguna otra forma?" - correct: a hardcoded arch 'limit' just moves the same silent-
        # Continue-stuck bug to a different threshold. Real fix: the widget itself now loads every
        # record via 'list.load({ limit: list.count })' before first render, with no arch-level cap
        # at all. This fixture creates 85 colliding pairs (safely past Odoo's own x2many
        # 'DEFAULT_LIMIT' of 80, the actual number that silently truncated 'records' before this
        # fix) sharing ONE classroom - one anchor teacher/group against 85 others, all same subject
        # so every pair lands in the SAME 'desdoble_eligible' sub-group (anchor is always "left") -
        # proving every one of the 85 rows actually renders (not just the first 80) and that
        # 'continue_disabled' correctly considers all of them. The tour deliberately does NOT also
        # bulk-apply to all 85 rows and complete the import - see the tour file's own comment for
        # why (a separate, already-covered concern, and Odoo's own tour step schema caps a single
        # step's wait at 60s, too unreliable for genuinely resolving a sub-group this large).
        space = self.env['ems.space'].create({
            'code': 'TOURPAGINATION',
            'name': 'Tour Pagination Space',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        self.env['ems.subject'].create({
            'code': 'TOURPAGINATION',
            'acronym': 'TRPAG',
            'name': 'Tour Pagination Subject',
        })
        for index in range(86):
            self.env['ems.group'].create({
                'group_type': 'reinforcement',
                'name': f'Tour Pagination Group {index}',
                'space_id': space.id,
            })
        self.start_tour("/odoo", "ems_working_schedules_import_conflicts_beyond_default_page_size", login="admin")

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
