# -*- coding: utf-8 -*-

from datetime import date, timedelta

from odoo.tests.common import TransactionCase


class TestAttendanceReportWizards(TransactionCase):
    """Covers the 3 attendance report wizards after their raw SQL (cr.execute) was replaced
    by ORM calls: the teacher-scoping filters (allowed_group_ids/allowed_student_ids/
    allowed_subject_ids) and the print() methods that fetch ems.attendance_session_line ids.
    Also covers a pre-existing bug fixed in the same change: allowed_subject_ids not actually
    scoping to the current teacher. All 3 wizards were later simplified, one at a time, to drop
    their level/study(/group) cascade: group and student down to a single group_id/student_id
    step, subject down to a single subject_id step that pre-fills a removable group_ids
    multi-select (every group teaching that subject, per the current teacher's own teaching)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_academic_admin = cls.env.ref('ems.group_academic_admin')

        cls.level = cls.env['ems.level'].create({'acronym': 'TARW', 'name': 'Test Level (Attendance Reports)'})
        cls.study1 = cls.env['ems.study'].create({
            'code': 'TARW001', 'acronym': 'TARW1', 'name': 'Test Study 1 (Attendance Reports)',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.study2 = cls.env['ems.study'].create({
            'code': 'TARW002', 'acronym': 'TARW2', 'name': 'Test Study 2 (Attendance Reports)',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.subject_a = cls.env['ems.subject'].create({
            'code': 'TARWA', 'acronym': 'TARWA', 'name': 'Test Subject A (Attendance Reports)',
            'study_ids': [(6, 0, [cls.study1.id, cls.study2.id])],
        })
        cls.subject_b = cls.env['ems.subject'].create({
            'code': 'TARWB', 'acronym': 'TARWB', 'name': 'Test Subject B (Attendance Reports)',
            'study_ids': [(6, 0, [cls.study1.id, cls.study2.id])],
        })
        cls.group1 = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TARW1', 'level_id': cls.level.id, 'study_id': cls.study1.id,
            'name': 'Test Group 1 (Attendance Reports)',
        })
        cls.group2 = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TARW2', 'level_id': cls.level.id, 'study_id': cls.study2.id,
            'name': 'Test Group 2 (Attendance Reports)',
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TARW-A', 'name': 'Test Space (Attendance Reports)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })

        cls.owner_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Owner Teacher (Attendance Reports)', 'login': 'test_owner_teacher_arw',
            'email': 'test_owner_teacher_arw@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.owner_employee = cls.env['hr.employee'].create({
            'name': 'Test Owner Teacher Employee (Attendance Reports)', 'employee_type': 'teacher',
            'user_id': cls.owner_user.id,
        })
        cls.other_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Other Teacher (Attendance Reports)', 'login': 'test_other_teacher_arw',
            'email': 'test_other_teacher_arw@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.other_employee = cls.env['hr.employee'].create({
            'name': 'Test Other Teacher Employee (Attendance Reports)', 'employee_type': 'teacher',
            'user_id': cls.other_user.id,
        })
        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Attendance Reports)', 'login': 'test_admin_arw',
            'email': 'test_admin_arw@example.com',
            'groups_id': [(4, cls.group_academic_admin.id), (4, cls.env.ref('base.group_user').id)],
        })

        # owner teaches group1/subject_a and group2/subject_a; other teaches group1/subject_b.
        cls.env['ems.teaching'].create({
            'teacher_id': cls.owner_employee.id, 'group_id': cls.group1.id, 'subject_id': cls.subject_a.id,
        })
        cls.env['ems.teaching'].create({
            'teacher_id': cls.owner_employee.id, 'group_id': cls.group2.id, 'subject_id': cls.subject_a.id,
        })
        cls.env['ems.teaching'].create({
            'teacher_id': cls.other_employee.id, 'group_id': cls.group1.id, 'subject_id': cls.subject_b.id,
        })

        cls.student1 = cls.env['res.partner'].create({
            'name': 'Test Student 1 (Attendance Reports)', 'contact_type': 'student',
        })
        cls.student2 = cls.env['res.partner'].create({
            'name': 'Test Student 2 (Attendance Reports)', 'contact_type': 'student',
        })
        # student1 is enrolled in both subjects of group1; student2 only in subject_a.
        cls.env['ems.enrollment'].create({
            'student_id': cls.student1.id, 'group_id': cls.group1.id, 'subject_id': cls.subject_a.id,
        })
        cls.env['ems.enrollment'].create({
            'student_id': cls.student1.id, 'group_id': cls.group1.id, 'subject_id': cls.subject_b.id,
        })
        cls.env['ems.enrollment'].create({
            'student_id': cls.student2.id, 'group_id': cls.group1.id, 'subject_id': cls.subject_a.id,
        })

        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.owner_employee.id])], 'level_id': cls.level.id, 'study_id': cls.study1.id,
            'subject_id': cls.subject_a.id, 'group_ids': [(6, 0, [cls.group1.id])], 'space_id': cls.space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
        })
        cls.status_attended = cls.env.ref('ems.attendance_status_attended')

        cls.today = date.today()
        cls.old_date = cls.today - timedelta(days=10)
        cls.session_recent = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': cls.today,
            'mode': 'manual', 'session_teacher_id': cls.owner_employee.id,
        })
        cls.session_old = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': cls.old_date,
            'mode': 'manual', 'session_teacher_id': cls.owner_employee.id,
        })
        cls.line_recent = cls.env['ems.attendance_session_line'].create({
            'student_id': cls.student1.id, 'status_id': cls.status_attended.id,
            'attendance_session_id': cls.session_recent.id,
        })
        cls.line_old = cls.env['ems.attendance_session_line'].create({
            'student_id': cls.student1.id, 'status_id': cls.status_attended.id,
            'attendance_session_id': cls.session_old.id,
        })

    # --- allowed_group_ids: scoped to the current teacher (no level/study step) --------

    def test_allowed_group_ids_scoped_to_owner(self):
        wizard = self.env['ems.attendance_report_group_wizard'].with_user(self.owner_user).create({})
        wizard._compute_allowed_group_ids()
        # owner teaches both group1/subject_a and group2/subject_a.
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertIn(self.group2, wizard.allowed_group_ids)

    def test_allowed_group_ids_scoped_to_other(self):
        wizard = self.env['ems.attendance_report_group_wizard'].with_user(self.other_user).create({})
        wizard._compute_allowed_group_ids()
        # 'other' only teaches group1/subject_b.
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertNotIn(self.group2, wizard.allowed_group_ids)

    def test_allowed_group_ids_admin_sees_all(self):
        wizard = self.env['ems.attendance_report_group_wizard'].with_user(self.admin_user).create({})
        wizard._compute_allowed_group_ids()
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertIn(self.group2, wizard.allowed_group_ids)

    # --- allowed_subject_ids: teacher scoping (bug fix; no level/study/group step) -----

    def test_allowed_subject_ids_scoped_to_owner(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].with_user(self.owner_user).create({
            'subject_id': self.subject_a.id,
        })
        wizard._compute_allowed_subject_ids()
        self.assertIn(self.subject_a, wizard.allowed_subject_ids)
        self.assertNotIn(self.subject_b, wizard.allowed_subject_ids)

    def test_allowed_subject_ids_scoped_to_other(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].with_user(self.other_user).create({
            'subject_id': self.subject_b.id,
        })
        wizard._compute_allowed_subject_ids()
        self.assertIn(self.subject_b, wizard.allowed_subject_ids)
        self.assertNotIn(self.subject_a, wizard.allowed_subject_ids)

    def test_allowed_subject_ids_admin_sees_both(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].with_user(self.admin_user).create({
            'subject_id': self.subject_a.id,
        })
        wizard._compute_allowed_subject_ids()
        self.assertIn(self.subject_a, wizard.allowed_subject_ids)
        self.assertIn(self.subject_b, wizard.allowed_subject_ids)

    # --- allowed_group_ids / group_ids prefill: groups teaching the chosen subject -----

    def test_allowed_group_ids_for_subject_scoped_to_owner(self):
        # owner teaches subject_a in both group1 and group2.
        wizard = self.env['ems.attendance_report_subject_wizard'].with_user(self.owner_user).create({
            'subject_id': self.subject_a.id,
        })
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertIn(self.group2, wizard.allowed_group_ids)

    def test_allowed_group_ids_for_subject_scoped_to_other(self):
        # other only teaches subject_b, only in group1.
        wizard = self.env['ems.attendance_report_subject_wizard'].with_user(self.other_user).create({
            'subject_id': self.subject_b.id,
        })
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertNotIn(self.group2, wizard.allowed_group_ids)

    def test_onchange_subject_id_prefills_group_ids_with_every_allowed_group(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].with_user(self.owner_user).new({})
        wizard.subject_id = self.subject_a
        wizard._onchange_subject_id()
        self.assertEqual(set(wizard.group_ids.ids), {self.group1.id, self.group2.id})

    # --- allowed_student_ids: scoped to the current teacher (no level/study/group step) --

    def test_allowed_student_ids_scoped_to_owner(self):
        wizard = self.env['ems.attendance_report_student_wizard'].with_user(self.owner_user).create({
            'student_id': self.student1.id,
        })
        wizard._compute_allowed_student_ids()
        self.assertIn(self.student1, wizard.allowed_student_ids)
        self.assertIn(self.student2, wizard.allowed_student_ids)

    def test_allowed_student_ids_scoped_to_other(self):
        wizard = self.env['ems.attendance_report_student_wizard'].with_user(self.other_user).create({
            'student_id': self.student1.id,
        })
        wizard._compute_allowed_student_ids()
        # 'other' only teaches group1/subject_b: student1 is enrolled there, student2 is not.
        self.assertIn(self.student1, wizard.allowed_student_ids)
        self.assertNotIn(self.student2, wizard.allowed_student_ids)

    def test_allowed_student_ids_admin_sees_all(self):
        wizard = self.env['ems.attendance_report_student_wizard'].with_user(self.admin_user).create({
            'student_id': self.student1.id,
        })
        wizard._compute_allowed_student_ids()
        self.assertIn(self.student1, wizard.allowed_student_ids)
        self.assertIn(self.student2, wizard.allowed_student_ids)

    # --- print(): ORM-fetched status_ids --------------------------------

    def test_print_group_wizard_returns_all_lines_in_range(self):
        wizard = self.env['ems.attendance_report_group_wizard'].create({
            'group_id': self.group1.id, 'from_date': self.old_date, 'to_date': self.today,
        })
        result = wizard.print()
        self.assertEqual(result['type'], 'ir.actions.report')
        self.assertEqual(sorted(result['data']['status_ids']), sorted([self.line_recent.id, self.line_old.id]))

    def test_print_subject_wizard_returns_lines_for_subject(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].create({
            'group_ids': [(6, 0, [self.group1.id])], 'subject_id': self.subject_a.id,
            'from_date': self.old_date, 'to_date': self.today,
        })
        result = wizard.print()
        self.assertEqual(sorted(result['data']['status_ids']), sorted([self.line_recent.id, self.line_old.id]))

    def test_print_student_wizard_filters_by_date_range(self):
        wizard = self.env['ems.attendance_report_student_wizard'].create({
            'student_id': self.student1.id,
            'from_date': self.today - timedelta(days=2), 'to_date': self.today,
        })
        result = wizard.print()
        self.assertEqual(result['data']['status_ids'], [self.line_recent.id])
        self.assertNotIn(self.line_old.id, result['data']['status_ids'])

    def test_print_wizards_skip_student_less_lines(self):
        # A student partner hard-deleted from the DB leaves its session lines behind with
        # student_id = NULL (Odoo's default ondelete='set null'). Those orphans must not reach
        # the report, where grouping-by-student would render a phantom blank-name row/group.
        orphan_line = self.env['ems.attendance_session_line'].create({
            'status_id': self.status_attended.id, 'attendance_session_id': self.session_recent.id,
        })
        self.assertFalse(orphan_line.student_id)

        subject_wizard = self.env['ems.attendance_report_subject_wizard'].create({
            'group_ids': [(6, 0, [self.group1.id])], 'subject_id': self.subject_a.id,
            'from_date': self.old_date, 'to_date': self.today,
        })
        subject_result = subject_wizard.print()
        self.assertNotIn(orphan_line.id, subject_result['data']['status_ids'])
        # And it must not surface as an empty-partner key in the rendered report data.
        values = self.env['report.ems.attendance_report_subject']._get_report_values(None, data=subject_result['data'])
        self.assertTrue(all(student for student in values['lines']))

        group_wizard = self.env['ems.attendance_report_group_wizard'].create({
            'group_id': self.group1.id, 'from_date': self.old_date, 'to_date': self.today,
        })
        self.assertNotIn(orphan_line.id, group_wizard.print()['data']['status_ids'])

    # --- stored related fields (used by the 'Attendance reports' pivot/graph) ---

    def test_session_line_analysis_fields_follow_the_session(self):
        self.assertEqual(self.line_recent.date, self.today)
        self.assertEqual(self.line_recent.level_id, self.level)
        self.assertEqual(self.line_recent.study_id, self.study1)
        self.assertEqual(self.line_recent.subject_id, self.subject_a)

    def test_absence_rate_follows_status_category(self):
        self.assertEqual(self.line_recent.status_id.category, 'assistance')
        self.assertEqual(self.line_recent.absence_rate, 0.0)

        miss_status = self.env.ref('ems.attendance_status_miss')
        absent_line = self.env['ems.attendance_session_line'].create({
            'student_id': self.student1.id, 'status_id': miss_status.id,
            'attendance_session_id': self.session_recent.id,
        })
        self.assertEqual(absent_line.status_id.category, 'absence')
        self.assertEqual(absent_line.absence_rate, 100.0)

    def test_strike_count_is_stored_and_summable(self):
        # store=True is what makes it usable as a pivot/graph measure (the 'Attendance reports'
        # screen) — a non-stored computed field can't be aggregated by read_group at all.
        groups = self.env['ems.attendance_session_line'].read_group(
            [('id', '=', self.line_recent.id)], ['strike_count'], [],
        )
        self.assertEqual(groups[0]['strike_count'], self.line_recent.strike_count)

    # --- _get_report_values: docids is always None on the real report_action() call path ---

    def test_get_report_values_handles_none_docids(self):
        wizard = self.env['ems.attendance_report_group_wizard'].create({
            'group_id': self.group1.id, 'from_date': self.old_date, 'to_date': self.today,
        })
        data = {'doc_ids': [wizard.id], 'status_ids': [self.line_recent.id, self.line_old.id]}
        # report_action(None, data=data) never sets active_ids, so the controller always calls
        # _get_report_values with docids=None, not []: len(None) used to raise TypeError here.
        values = self.env['report.ems.attendance_report_group']._get_report_values(None, data=data)
        self.assertEqual(values['doc_ids'], [wizard.id])
        self.assertEqual(len(values['main'].overall), 2)

    # --- 'Reports' menu server action: role-based default domain scoping -------

    def test_reports_action_scoped_to_own_teaching_for_plain_teacher(self):
        server_action = self.env.ref('ems.action_attendance_reports_open')
        result = server_action.with_user(self.owner_user).run()
        self.assertEqual(result.get('domain'), [('template_teacher_ids.user_id', '=', self.owner_user.id)])
        self.assertEqual(result.get('context', {}).get('pivot_measures'), ['absence_rate', 'strike_count', '__count'])

    def test_reports_action_unscoped_for_academic_admin(self):
        # group_academic_admin implies group_head_of_studies (security/groups.xml), which is one
        # of the roles the server action's code checks to skip the default domain.
        server_action = self.env.ref('ems.action_attendance_reports_open')
        result = server_action.with_user(self.admin_user).run()
        self.assertFalse(result.get('domain'))
        self.assertIn(self.group1, self.line_recent.group_ids)

    # --- by-subject wizard: opt-in per-student 'Details'/'Strikes' (detail_status_ids/include_strikes) ---
    # The per-student 'Details' table used to list every session unconditionally, which is what made
    # the PDF choke on large subject/group combinations (many sessions x many students). It's now
    # opt-in: detail_status_ids defaults to absence-category statuses only, include_strikes defaults
    # to True, and picking anything beyond the default warns the user it may be slow/large.

    def test_default_detail_status_ids_is_absence_category_only(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].create({
            'subject_id': self.subject_a.id, 'group_ids': [(6, 0, [self.group1.id])],
        })
        self.assertTrue(wizard.detail_status_ids)
        self.assertTrue(all(status.category == 'absence' for status in wizard.detail_status_ids))
        self.assertNotIn(self.status_attended, wizard.detail_status_ids)

    def test_detail_status_warning_false_within_default(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].with_user(self.owner_user).new({
            'subject_id': self.subject_a.id,
        })
        miss_status = self.env.ref('ems.attendance_status_miss')
        wizard.detail_status_ids = miss_status
        self.assertFalse(wizard.detail_status_warning)

    def test_detail_status_warning_true_beyond_default(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].with_user(self.owner_user).new({
            'subject_id': self.subject_a.id,
        })
        wizard.detail_status_ids = wizard._default_detail_status_ids() | self.status_attended
        self.assertTrue(wizard.detail_status_warning)

    def test_get_report_values_filters_detail_entries_by_status(self):
        miss_status = self.env.ref('ems.attendance_status_miss')
        miss_line = self.env['ems.attendance_session_line'].create({
            'student_id': self.student1.id, 'status_id': miss_status.id,
            'attendance_session_id': self.session_recent.id,
        })
        wizard = self.env['ems.attendance_report_subject_wizard'].create({
            'subject_id': self.subject_a.id, 'group_ids': [(6, 0, [self.group1.id])],
            'from_date': self.old_date, 'to_date': self.today,
        })
        result = wizard.print()
        values = self.env['report.ems.attendance_report_subject']._get_report_values(None, data=result['data'])

        # default detail_status_ids is absence-only: the two 'Attended' lines are excluded, the
        # 'Miss' one is included.
        self.assertIn(miss_line, values['detail_entries'][self.student1])
        self.assertNotIn(self.line_recent, values['detail_entries'][self.student1])
        self.assertNotIn(self.line_old, values['detail_entries'][self.student1])

    def test_get_report_values_includes_strikes_when_enabled(self):
        strike = self.env['ems.strike'].create({
            'student_id': self.student1.id, 'teacher_id': self.owner_employee.id,
            'attendance_session_line_id': self.line_recent.id,
        })
        wizard = self.env['ems.attendance_report_subject_wizard'].create({
            'subject_id': self.subject_a.id, 'group_ids': [(6, 0, [self.group1.id])],
            'from_date': self.old_date, 'to_date': self.today, 'include_strikes': True,
        })
        result = wizard.print()
        values = self.env['report.ems.attendance_report_subject']._get_report_values(None, data=result['data'])
        self.assertIn(strike, values['detail_strikes'][self.student1])

    def test_get_report_values_excludes_strikes_when_disabled(self):
        self.env['ems.strike'].create({
            'student_id': self.student1.id, 'teacher_id': self.owner_employee.id,
            'attendance_session_line_id': self.line_recent.id,
        })
        wizard = self.env['ems.attendance_report_subject_wizard'].create({
            'subject_id': self.subject_a.id, 'group_ids': [(6, 0, [self.group1.id])],
            'from_date': self.old_date, 'to_date': self.today, 'include_strikes': False,
        })
        result = wizard.print()
        values = self.env['report.ems.attendance_report_subject']._get_report_values(None, data=result['data'])
        self.assertFalse(values['detail_strikes'][self.student1])
