# -*- coding: utf-8 -*-

from datetime import date, timedelta

from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval, time

from .common import create_level_study, create_role_employee, create_role_user, next_student_id


class AttendanceReportCommon(TransactionCase):
    """Shared fixtures: two teachers, two groups/subjects, two students and owner's sessions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Native Odoo intercepts an admin's *first ever* report_action() call with a "configure
        # your document layout" wizard instead of the real report action whenever
        # company.external_report_layout_id is unset (see
        # ir.actions.report.report_action()/_action_configure_external_report_layout in Odoo
        # core) - print()'s result then has no 'report_name', breaking every
        # assertion below. A long-lived dev database has this already configured (someone
        # clicked through it once); a genuinely fresh install never has, so this only ever
        # surfaced on a real clean-install CI run (confirmed 2026-07-31), never locally. Not an
        # EMS bug to "fix" in production - this is standard Odoo onboarding UX every real
        # company goes through once - just needs to be pre-configured here so the test exercises
        # the report dispatch itself, not Odoo's one-time layout prompt.
        cls.env.company.external_report_layout_id = cls.env.ref('web.external_layout_standard')

        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_academic_admin = cls.env.ref('ems.group_academic_admin')

        cls.level, cls.study1 = create_level_study(cls, 'TARW', level={'name': 'Test Level (Attendance Reports)'}, study={
            'code': 'TARW001', 'acronym': 'TARW1', 'name': 'Test Study 1 (Attendance Reports)',
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
            'name': 'Test Student 1 (Attendance Reports)', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        cls.student2 = cls.env['res.partner'].create({
            'name': 'Test Student 2 (Attendance Reports)', 'contact_type': 'student', 'student_id': next_student_id(),
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
            'teacher_ids': [(6, 0, [cls.owner_employee.id])], 'study_ids': [(6, 0, [cls.study1.id])],
            'subject_id': cls.subject_a.id, 'group_ids': [(6, 0, [cls.group1.id])],
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

    def _wizard(self, user=None, **vals):
        model = self.env['ems.attendance_report_wizard']
        if user is not None:
            model = model.with_user(user)
        return model.create(vals)

    def _values(self, wizard, **data):
        # The real call path: the controller renders the report on the wizard's own id.
        report = self.env[f'report.ems.attendance_report_{wizard.report_type}'].with_env(wizard.env)
        return report._get_report_values(wizard.ids, data=data or None)


class TestAttendanceReportWizards(AttendanceReportCommon):
    """Covers the unified attendance report wizard (ems.attendance_report_wizard): a single model
    driving all 3 PDF variants via a 'report_type' selector (group / student / subject). Exercises
    the teacher-scoping dropdown filters (allowed_group_ids/allowed_student_ids/allowed_subject_ids,
    computed per report_type), the print() dispatch that fetches ems.attendance_session_line ids per
    type, the opt-in per-dimension Details/Strikes (detail_status_ids/include_strikes/warning, now
    shared by all 3 variants), and the exclusion of student-less orphan lines."""

    # --- allowed_group_ids: by-group variant, scoped to the current teacher ------------

    def test_allowed_group_ids_scoped_to_owner(self):
        wizard = self._wizard(self.owner_user, report_type='group')
        wizard._compute_allowed_ids()
        # owner teaches both group1/subject_a and group2/subject_a.
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertIn(self.group2, wizard.allowed_group_ids)

    def test_allowed_group_ids_scoped_to_other(self):
        wizard = self._wizard(self.other_user, report_type='group')
        wizard._compute_allowed_ids()
        # 'other' only teaches group1/subject_b.
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertNotIn(self.group2, wizard.allowed_group_ids)

    def test_allowed_group_ids_admin_sees_all(self):
        wizard = self._wizard(self.admin_user, report_type='group')
        wizard._compute_allowed_ids()
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertIn(self.group2, wizard.allowed_group_ids)

    # --- allowed_subject_ids: by-subject variant, teacher scoping ----------------------

    def test_allowed_subject_ids_scoped_to_owner(self):
        wizard = self._wizard(self.owner_user, report_type='subject', subject_id=self.subject_a.id)
        wizard._compute_allowed_ids()
        self.assertIn(self.subject_a, wizard.allowed_subject_ids)
        self.assertNotIn(self.subject_b, wizard.allowed_subject_ids)

    def test_allowed_subject_ids_scoped_to_other(self):
        wizard = self._wizard(self.other_user, report_type='subject', subject_id=self.subject_b.id)
        wizard._compute_allowed_ids()
        self.assertIn(self.subject_b, wizard.allowed_subject_ids)
        self.assertNotIn(self.subject_a, wizard.allowed_subject_ids)

    def test_allowed_subject_ids_admin_sees_both(self):
        wizard = self._wizard(self.admin_user, report_type='subject', subject_id=self.subject_a.id)
        wizard._compute_allowed_ids()
        self.assertIn(self.subject_a, wizard.allowed_subject_ids)
        self.assertIn(self.subject_b, wizard.allowed_subject_ids)

    # --- allowed_group_ids / group_ids prefill: groups teaching the chosen subject -----

    def test_allowed_group_ids_for_subject_scoped_to_owner(self):
        # owner teaches subject_a in both group1 and group2.
        wizard = self._wizard(self.owner_user, report_type='subject', subject_id=self.subject_a.id)
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertIn(self.group2, wizard.allowed_group_ids)

    def test_allowed_group_ids_for_subject_scoped_to_other(self):
        # other only teaches subject_b, only in group1.
        wizard = self._wizard(self.other_user, report_type='subject', subject_id=self.subject_b.id)
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertNotIn(self.group2, wizard.allowed_group_ids)

    def test_onchange_subject_id_prefills_group_ids_with_every_allowed_group(self):
        wizard = self.env['ems.attendance_report_wizard'].with_user(self.owner_user).new({'report_type': 'subject'})
        wizard.subject_id = self.subject_a
        wizard._onchange_subject_id()
        self.assertEqual(set(wizard.group_ids.ids), {self.group1.id, self.group2.id})

    # --- allowed_student_ids: by-student variant, scoped to the current teacher --------

    def test_allowed_student_ids_scoped_to_owner(self):
        wizard = self._wizard(self.owner_user, report_type='student', student_id=self.student1.id)
        wizard._compute_allowed_ids()
        self.assertIn(self.student1, wizard.allowed_student_ids)
        self.assertIn(self.student2, wizard.allowed_student_ids)

    def test_allowed_student_ids_scoped_to_other(self):
        wizard = self._wizard(self.other_user, report_type='student', student_id=self.student1.id)
        wizard._compute_allowed_ids()
        # 'other' only teaches group1/subject_b: student1 is enrolled there, student2 is not.
        self.assertIn(self.student1, wizard.allowed_student_ids)
        self.assertNotIn(self.student2, wizard.allowed_student_ids)

    def test_allowed_student_ids_admin_sees_all(self):
        wizard = self._wizard(self.admin_user, report_type='student', student_id=self.student1.id)
        wizard._compute_allowed_ids()
        self.assertIn(self.student1, wizard.allowed_student_ids)
        self.assertIn(self.student2, wizard.allowed_student_ids)

    # --- tutor_ids: unified for all 3 types --------------------------------------------

    def test_tutor_ids_follow_report_type(self):
        tutor = self.env['hr.employee'].create({
            'name': 'Test Tutor (Attendance Reports)', 'employee_type': 'teacher',
        })
        self.group1.tutor_id = tutor
        group_wizard = self._wizard(report_type='group', group_id=self.group1.id)
        self.assertIn(tutor, group_wizard.tutor_ids)
        subject_wizard = self._wizard(report_type='subject', subject_id=self.subject_a.id,
                                      group_ids=[(6, 0, [self.group1.id])])
        self.assertIn(tutor, subject_wizard.tutor_ids)

    # --- print(): ORM-fetched status_ids per report_type -------------------------------

    def test_print_group_returns_all_lines_in_range(self):
        wizard = self._wizard(report_type='group', group_id=self.group1.id,
                              from_date=self.old_date, to_date=self.today)
        self.assertEqual(wizard.print()['type'], 'ir.actions.report')
        self.assertEqual(sorted(wizard._get_report_lines().ids), sorted([self.line_recent.id, self.line_old.id]))

    def test_print_subject_returns_lines_for_subject(self):
        wizard = self._wizard(report_type='subject', subject_id=self.subject_a.id,
                              group_ids=[(6, 0, [self.group1.id])], from_date=self.old_date, to_date=self.today)
        self.assertEqual(sorted(wizard._get_report_lines().ids), sorted([self.line_recent.id, self.line_old.id]))

    def test_print_student_filters_by_date_range(self):
        wizard = self._wizard(report_type='student', student_id=self.student1.id,
                              from_date=self.today - timedelta(days=2), to_date=self.today)
        self.assertEqual(wizard._get_report_lines().ids, [self.line_recent.id])

    def test_print_dispatches_to_the_right_report(self):
        for report_type, report_name in [('group', 'ems.attendance_report_group'),
                                         ('student', 'ems.attendance_report_student'),
                                         ('subject', 'ems.attendance_report_subject')]:
            wizard = self._wizard(report_type=report_type, group_id=self.group1.id,
                                  student_id=self.student1.id, subject_id=self.subject_a.id,
                                  group_ids=[(6, 0, [self.group1.id])], from_date=self.old_date, to_date=self.today)
            self.assertEqual(wizard.print()['report_name'], report_name)

    def test_print_skips_student_less_lines(self):
        # A student partner hard-deleted from the DB leaves its session lines behind with
        # student_id = NULL (Odoo's default ondelete='set null'). Those orphans must not reach the
        # by-group/by-subject reports, where grouping-by-student renders a phantom blank-name row.
        orphan_line = self.env['ems.attendance_session_line'].create({
            'status_id': self.status_attended.id, 'attendance_session_id': self.session_recent.id,
        })
        self.assertFalse(orphan_line.student_id)

        subject_wizard = self._wizard(report_type='subject', subject_id=self.subject_a.id,
                                      group_ids=[(6, 0, [self.group1.id])], from_date=self.old_date, to_date=self.today)
        self.assertNotIn(orphan_line, subject_wizard._get_report_lines())
        # And it must not surface as an empty-partner key in the rendered report data.
        values = self._values(subject_wizard)
        self.assertTrue(all(student for student in values['lines']))

        group_wizard = self._wizard(report_type='group', group_id=self.group1.id,
                                    from_date=self.old_date, to_date=self.today)
        self.assertNotIn(orphan_line, group_wizard._get_report_lines())

    # --- stored related fields (used by the 'Attendance reports' pivot/graph) ---

    def test_session_line_analysis_fields_follow_the_session(self):
        self.assertEqual(self.line_recent.date, self.today)
        self.assertEqual(self.line_recent.level_id, self.level)
        self.assertEqual(self.line_recent.study_ids, self.study1)
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

    # --- print(): printed on the wizard itself, so the download gets its own file name ---

    def test_print_is_bound_to_the_wizard_without_data(self):
        # With 'data', the web client downloads through the "particular report" route, which
        # always names the file after the report and ignores print_report_name.
        wizard = self._wizard(report_type='group', group_id=self.group1.id,
                              from_date=self.old_date, to_date=self.today)
        result = wizard.print()
        self.assertFalse(result.get('data'))
        self.assertEqual(result['context']['active_ids'], [wizard.id])
        values = self._values(wizard)
        self.assertEqual(values['doc_ids'], [wizard.id])
        self.assertEqual(len(values['main'].overall), 2)

    def test_report_filename_names_the_selected_element(self):
        # The filename expression is evaluated as the download controller does.
        for vals, element in [
            ({'report_type': 'student', 'student_id': self.student1.id}, 'Test_Student_1_(Attendance_Reports)'),
            ({'report_type': 'group', 'group_id': self.group1.id}, 'Test_Group_1_(Attendance_Reports)'),
            ({'report_type': 'subject', 'subject_id': self.subject_a.id}, 'Test_Subject_A_(Attendance_Reports)'),
        ]:
            wizard = self._wizard(self.owner_user, **vals)
            report = self.env.ref(f"ems.action_attendance_report_{vals['report_type']}")
            self.assertEqual(report.model, 'ems.attendance_report_wizard')
            filename = safe_eval(report.print_report_name, {'object': wizard, 'time': time})
            self.assertEqual(filename, f'{report.name}_{element}')

    # --- 'Reports' menu server action: role-based default domain scoping -------

    def test_reports_action_scoped_to_own_teaching_for_plain_teacher(self):
        server_action = self.env.ref('ems.action_attendance_reports_open')
        result = server_action.with_user(self.owner_user).run()
        self.assertEqual(result.get('domain'), [
            ('session_active', '=', True),
            '|', ('template_teacher_ids.user_id', '=', self.owner_user.id),
            ('student_id.tutor_id.tutor_scope_user_ids', '=', self.owner_user.id),
        ])
        self.assertEqual(result.get('context', {}).get('pivot_measures'), ['absence_rate', 'strike_count', '__count'])
        self.assertEqual(result['context'].get('search_default_my_subjects'), 1)

    def test_reports_action_unscoped_for_academic_admin(self):
        # group_academic_admin implies group_head_of_studies (security/groups.xml), which is one
        # of the roles the server action's code checks to skip the teacher-scoping domain - the
        # base action's own current-course-only domain (below) still applies to everyone,
        # admin included.
        server_action = self.env.ref('ems.action_attendance_reports_open')
        result = server_action.with_user(self.admin_user).run()
        self.assertEqual(result.get('domain'), [('session_active', '=', True)])
        self.assertNotIn('search_default_my_subjects', result['context'])
        self.assertIn(self.group1, self.line_recent.group_ids)

    # --- Student form's 'Attendance' button: same screen, filtered on one student (issue #519) ---

    def test_student_attendance_action_keeps_teacher_scope_and_filters_student(self):
        result = self.student1.with_user(self.owner_user).action_view_attendance_reports()
        self.assertEqual(result.get('domain'), [
            ('session_active', '=', True),
            '|', ('template_teacher_ids.user_id', '=', self.owner_user.id),
            ('student_id.tutor_id.tutor_scope_user_ids', '=', self.owner_user.id),
        ])
        self.assertEqual(result['context'].get('search_default_student_id'), self.student1.id)
        self.assertEqual(result['context'].get('pivot_measures'), ['absence_rate', 'strike_count', '__count'])
        # Every subject of the student within the user's scope, not just their own teaching.
        self.assertNotIn('search_default_my_subjects', result['context'])
        self.assertIn(self.student1.name, result['name'])
        self.assertEqual(result['display_name'], result['name'])

    def test_student_attendance_action_unscoped_for_academic_admin(self):
        result = self.student1.with_user(self.admin_user).action_view_attendance_reports()
        self.assertEqual(result.get('domain'), [('session_active', '=', True)])
        self.assertEqual(result['context'].get('search_default_student_id'), self.student1.id)

    def test_reports_action_domain_excludes_a_line_of_an_archived_session(self):
        """Developer feedback (2026-08-10): "debe mostrar la información del curso actual. Una
        vez transicionamos de curso, debería estar en blanco" - once the course transition wizard
        archives the outgoing course's sessions (see course_transition_wizard.md), this report
        must stop showing their lines, for every role, not just the teacher-scoped one."""
        self.session_old.action_archive()
        server_action = self.env.ref('ems.action_attendance_reports_open')

        admin_result = server_action.with_user(self.admin_user).run()
        found = self.env['ems.attendance_session_line'].search(admin_result['domain'])
        self.assertIn(self.line_recent, found)
        self.assertNotIn(self.line_old, found)

    # --- opt-in per-dimension 'Details'/'Strikes' (detail_status_ids/include_strikes) ---
    # The per-dimension 'Details' table used to list every session unconditionally, which is what
    # made the by-subject PDF choke on large subject/group combinations. It's now opt-in and shared
    # by all 3 report variants: detail_status_ids defaults to absence-category statuses only,
    # include_strikes defaults to True, and picking anything beyond the default warns (inline) that
    # it may be slow/large.

    def test_default_detail_status_ids_is_absence_category_only(self):
        wizard = self._wizard(report_type='subject', subject_id=self.subject_a.id,
                              group_ids=[(6, 0, [self.group1.id])])
        self.assertTrue(wizard.detail_status_ids)
        self.assertTrue(all(status.category == 'absence' for status in wizard.detail_status_ids))
        self.assertNotIn(self.status_attended, wizard.detail_status_ids)

    def test_detail_status_warning_false_within_default(self):
        wizard = self.env['ems.attendance_report_wizard'].with_user(self.owner_user).new({'report_type': 'subject'})
        wizard.detail_status_ids = self.env.ref('ems.attendance_status_miss')
        self.assertFalse(wizard.detail_status_warning)

    def test_detail_status_warning_true_beyond_default(self):
        wizard = self.env['ems.attendance_report_wizard'].with_user(self.owner_user).new({'report_type': 'subject'})
        wizard.detail_status_ids = wizard._default_detail_status_ids() | self.status_attended
        self.assertTrue(wizard.detail_status_warning)

    def test_subject_report_filters_detail_entries_by_status(self):
        miss_status = self.env.ref('ems.attendance_status_miss')
        miss_line = self.env['ems.attendance_session_line'].create({
            'student_id': self.student1.id, 'status_id': miss_status.id,
            'attendance_session_id': self.session_recent.id,
        })
        wizard = self._wizard(report_type='subject', subject_id=self.subject_a.id,
                              group_ids=[(6, 0, [self.group1.id])], from_date=self.old_date, to_date=self.today)
        values = self._values(wizard)
        # by-subject groups by student; default detail_status_ids is absence-only.
        self.assertIn(miss_line, values['detail_entries'][self.student1])
        self.assertNotIn(self.line_recent, values['detail_entries'][self.student1])
        self.assertNotIn(self.line_old, values['detail_entries'][self.student1])

    def test_group_report_also_has_filtered_detail_sections(self):
        # The detail_status_ids/include_strikes controls now apply uniformly to all 3 reports; the
        # by-group report groups its detail sections by subject.
        miss_status = self.env.ref('ems.attendance_status_miss')
        miss_line = self.env['ems.attendance_session_line'].create({
            'student_id': self.student1.id, 'status_id': miss_status.id,
            'attendance_session_id': self.session_recent.id,
        })
        wizard = self._wizard(report_type='group', group_id=self.group1.id,
                              from_date=self.old_date, to_date=self.today)
        values = self._values(wizard)
        self.assertIn(miss_line, values['detail_entries'][self.subject_a])
        self.assertNotIn(self.line_recent, values['detail_entries'][self.subject_a])

    def test_student_report_also_has_filtered_detail_sections(self):
        miss_status = self.env.ref('ems.attendance_status_miss')
        miss_line = self.env['ems.attendance_session_line'].create({
            'student_id': self.student1.id, 'status_id': miss_status.id,
            'attendance_session_id': self.session_recent.id,
        })
        wizard = self._wizard(report_type='student', student_id=self.student1.id,
                              from_date=self.old_date, to_date=self.today)
        values = self._values(wizard)
        # by-student groups its detail sections by subject.
        self.assertIn(miss_line, values['detail_entries'][self.subject_a])
        self.assertNotIn(self.line_recent, values['detail_entries'][self.subject_a])

    def test_include_strikes_toggles_detail_strikes(self):
        strike = self.env['ems.strike'].create({
            'student_id': self.student1.id, 'teacher_id': self.owner_employee.id,
            'attendance_session_line_id': self.line_recent.id,
        })
        on = self._wizard(report_type='subject', subject_id=self.subject_a.id,
                          group_ids=[(6, 0, [self.group1.id])], from_date=self.old_date, to_date=self.today,
                          include_strikes=True)
        on_values = self._values(on)
        self.assertIn(strike, on_values['detail_strikes'][self.student1])

        off = self._wizard(report_type='subject', subject_id=self.subject_a.id,
                           group_ids=[(6, 0, [self.group1.id])], from_date=self.old_date, to_date=self.today,
                           include_strikes=False)
        off_values = self._values(off)
        self.assertFalse(off_values['detail_strikes'][self.student1])


class AttendanceReportTutorScopeCommon(AttendanceReportCommon):
    """Adds another teacher's session (subject_b, group1) and a tutor of group1 who teaches nothing,
    with a department chief above them. student1 (group1) is a tutee; student2 (group2) is not."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A session of *another* teacher (subject_b) for student1, older than owner's own ones.
        other_template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.other_employee.id])], 'study_ids': [(6, 0, [cls.study1.id])],
            'subject_id': cls.subject_b.id, 'group_ids': [(6, 0, [cls.group1.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        other_schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': other_template.id, 'weekday': '2',
            'start_time': 9.0, 'end_time': 10.0, 'space_id': cls.space.id,
        })
        cls.other_date = cls.today - timedelta(days=20)
        cls.session_other = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': other_schedule.id, 'date': cls.other_date,
            'mode': 'manual', 'session_teacher_id': cls.other_employee.id,
        })
        cls.line_other = cls.env['ems.attendance_session_line'].create({
            'student_id': cls.student1.id, 'status_id': cls.env.ref('ems.attendance_status_miss').id,
            'attendance_session_id': cls.session_other.id,
        })
        # A student outside the tutor's group, with a session of the other teacher.
        cls.line_foreign = cls.env['ems.attendance_session_line'].create({
            'student_id': cls.student2.id, 'status_id': cls.status_attended.id,
            'attendance_session_id': cls.session_other.id,
        })

        # The group1 tutor teaches nothing at all; a department chief sits above them.
        cls.chief_user = create_role_user(cls, 'department_chief', 'test_chief_arw')
        cls.chief_employee = create_role_employee(cls, cls.chief_user)
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_tutor_arw')
        cls.tutor_employee = create_role_employee(cls, cls.tutor_user, parent_id=cls.chief_employee.id)
        cls.group1.tutor_id = cls.tutor_employee
        cls.student1.main_group_id = cls.group1
        cls.student2.main_group_id = cls.group2


class TestAttendanceStudentReportScope(AttendanceReportTutorScopeCommon):
    """Issue #500: the by-student report mixes session lines (readable by every teacher) with
    session headers (readable only by the session's own teacher). A plain teacher gets only their
    own sessions; the student's tutor scope (the tutor, their chiefs up the parent_id chain, the
    Director) gets every session of the student, whatever the subject or teacher."""

    def _report_lines(self, user, **vals):
        wizard = self._wizard(user, report_type='student', student_id=self.student1.id,
                              from_date=self.other_date, to_date=self.today, **vals)
        return wizard._get_report_lines().ids, self._values(wizard)

    def _onchange_dates(self, user):
        wizard = self.env['ems.attendance_report_wizard'].with_user(user).new({'report_type': 'student'})
        wizard.student_id = self.student1
        wizard._onchange_student_id()
        return wizard.from_date, wizard.to_date

    # --- plain teacher: own sessions only, never an AccessError --------------------

    def test_onchange_plain_teacher_only_own_sessions(self):
        self.assertEqual(self._onchange_dates(self.owner_user), (self.old_date, self.today))

    def test_print_and_render_plain_teacher_only_own_sessions(self):
        line_ids, values = self._report_lines(self.owner_user)
        self.assertEqual(sorted(line_ids), sorted([self.line_recent.id, self.line_old.id]))
        self.assertEqual(set(values['lines']), {self.subject_a})

    def test_render_ignores_crafted_status_ids_for_plain_teacher(self):
        wizard = self._wizard(self.owner_user, report_type='student', student_id=self.student1.id,
                              from_date=self.other_date, to_date=self.today)
        values = self._values(wizard, status_ids=[self.line_recent.id, self.line_other.id])
        self.assertNotIn(self.subject_b, values['lines'])

    # --- tutor scope: every subject of the student -----------------------------------

    def test_tutor_finds_tutee_without_teaching_them(self):
        wizard = self._wizard(self.tutor_user, report_type='student')
        wizard._compute_allowed_ids()
        self.assertIn(self.student1, wizard.allowed_student_ids)
        self.assertNotIn(self.student2, wizard.allowed_student_ids)

    def test_onchange_tutor_covers_every_session(self):
        self.assertEqual(self._onchange_dates(self.tutor_user), (self.other_date, self.today))

    def test_print_and_render_tutor_every_subject(self):
        line_ids, values = self._report_lines(self.tutor_user)
        self.assertEqual(sorted(line_ids), sorted([self.line_recent.id, self.line_old.id, self.line_other.id]))
        self.assertEqual(set(values['lines']), {self.subject_a, self.subject_b})
        # The detail rows read the other teacher's session header too.
        self.assertEqual(values['detail_entries'][self.subject_b][0].attendance_session_id.session_teacher_id,
                         self.other_employee)

    def test_chief_above_the_tutor_every_subject(self):
        line_ids, values = self._report_lines(self.chief_user)
        self.assertIn(self.line_other.id, line_ids)
        self.assertEqual(set(values['lines']), {self.subject_a, self.subject_b})

    def test_render_ignores_crafted_status_ids_of_another_student(self):
        # The tutor scope only widens the selected student, never lines sent back by the client.
        wizard = self._wizard(self.tutor_user, report_type='student', student_id=self.student1.id,
                              from_date=self.other_date, to_date=self.today)
        values = self._values(wizard, status_ids=[self.line_foreign.id])
        self.assertNotIn(self.line_foreign, values['main'].entries)


class TestAttendanceGroupSubjectReportScope(AttendanceReportTutorScopeCommon):
    """The by-group and by-subject reports: a plain teacher gets only their own sessions, while for a
    group in the user's tutor scope (its tutor, the chiefs above them, the Director) they cover every
    subject of the group, whoever teaches it. Never widened for a group outside that scope."""

    def _lines(self, user, **vals):
        wizard = self._wizard(user, from_date=self.other_date, to_date=self.today, **vals)
        return wizard._get_report_lines(), self._values(wizard)

    def _onchange_dates(self, user, **vals):
        wizard = self.env['ems.attendance_report_wizard'].with_user(user).new(vals)
        wizard._onchange_group_id()
        wizard._onchange_subject_id()
        return wizard.from_date, wizard.to_date

    # --- by group ------------------------------------------------------------------------

    def test_tutor_finds_tutored_group_without_teaching_it(self):
        wizard = self._wizard(self.tutor_user, report_type='group')
        wizard._compute_allowed_ids()
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertNotIn(self.group2, wizard.allowed_group_ids)

    def test_group_tutor_every_subject(self):
        lines, values = self._lines(self.tutor_user, report_type='group', group_id=self.group1.id)
        self.assertEqual(set(lines.ids), {self.line_recent.id, self.line_old.id, self.line_other.id, self.line_foreign.id})
        self.assertEqual(set(values['lines']), {self.subject_a, self.subject_b})
        # The detail rows read the other teacher's session header too.
        self.assertEqual(values['detail_entries'][self.subject_b][0].attendance_session_id.session_teacher_id,
                         self.other_employee)

    def test_group_chief_above_the_tutor_every_subject(self):
        _lines, values = self._lines(self.chief_user, report_type='group', group_id=self.group1.id)
        self.assertEqual(set(values['lines']), {self.subject_a, self.subject_b})

    def test_group_plain_teacher_only_own_sessions(self):
        lines, values = self._lines(self.owner_user, report_type='group', group_id=self.group1.id)
        self.assertEqual(set(lines.ids), {self.line_recent.id, self.line_old.id})
        self.assertEqual(set(values['lines']), {self.subject_a})

    def test_group_onchange_tutor_covers_every_session(self):
        self.assertEqual(self._onchange_dates(self.tutor_user, report_type='group', group_id=self.group1.id),
                         (self.other_date, self.today))

    def test_group_outside_tutor_scope_not_widened(self):
        # A group picked by hand outside the dropdown gets no sudo(): record rules decide.
        lines, _values = self._lines(self.tutor_user, report_type='group', group_id=self.group2.id)
        self.assertFalse(lines)

    # --- by subject ----------------------------------------------------------------------

    def test_tutor_finds_subjects_taught_by_others_in_tutored_group(self):
        wizard = self._wizard(self.tutor_user, report_type='subject', subject_id=self.subject_b.id)
        wizard._compute_allowed_ids()
        self.assertEqual(wizard.allowed_subject_ids, self.subject_a | self.subject_b)
        # subject_a is also taught in group2, which is not in the tutor's scope.
        self.assertEqual(wizard._get_groups_teaching(self.subject_a), self.group1)

    def test_plain_teacher_subjects_and_groups_unchanged(self):
        wizard = self._wizard(self.owner_user, report_type='subject', subject_id=self.subject_a.id)
        wizard._compute_allowed_ids()
        self.assertEqual(wizard.allowed_subject_ids, self.subject_a)
        self.assertEqual(wizard._get_groups_teaching(self.subject_a), self.group1 | self.group2)

    def test_subject_tutor_every_session_of_tutored_group(self):
        lines, values = self._lines(self.tutor_user, report_type='subject', subject_id=self.subject_b.id,
                                    group_ids=[(6, 0, [self.group1.id])])
        self.assertEqual(set(lines.ids), {self.line_other.id, self.line_foreign.id})
        self.assertEqual(set(values['lines']), {self.student1, self.student2})

    def test_subject_onchange_tutor_prefills_group_and_dates(self):
        wizard = self.env['ems.attendance_report_wizard'].with_user(self.tutor_user).new({
            'report_type': 'subject', 'subject_id': self.subject_b.id,
        })
        wizard._onchange_subject_id()
        self.assertEqual(wizard.group_ids._origin, self.group1)
        self.assertEqual((wizard.from_date, wizard.to_date), (self.other_date, self.other_date))

    def test_subject_outside_tutor_scope_not_widened(self):
        lines, _values = self._lines(self.tutor_user, report_type='subject', subject_id=self.subject_a.id,
                                     group_ids=[(6, 0, [self.group2.id])])
        self.assertFalse(lines)


class TestAttendanceReportsAnalysisScope(AttendanceReportTutorScopeCommon):
    """The 'Reports' pivot/graph: a teacher sees their own subjects plus every subject of their
    tutor scope's students, with the removable 'My subjects' filter on by default."""

    def _action(self, user):
        return self.env.ref('ems.action_attendance_reports_open').with_user(user).run()

    def _search(self, user, *extra):
        domain = self._action(user)['domain'] + list(extra)
        return self.env['ems.attendance_session_line'].with_user(user).search(domain)

    def test_tutor_sees_every_subject_of_tutees(self):
        found = self._search(self.tutor_user)
        self.assertEqual(set(found.ids) & self._fixture_ids(), {self.line_recent.id, self.line_old.id, self.line_other.id})

    def test_my_subjects_filter_shows_only_own_teaching(self):
        arch = self.env.ref('ems.view_attendance_report_analysis_search').arch
        self.assertIn('name="my_subjects" domain="[(\'template_teacher_ids.user_id\', \'=\', uid)]"', arch)
        # With the default filter on, the tutor (who teaches nothing) gets none and the owner only their own.
        found = self._search(self.tutor_user, ('template_teacher_ids.user_id', '=', self.tutor_user.id))
        self.assertFalse(set(found.ids) & self._fixture_ids())
        found = self._search(self.owner_user, ('template_teacher_ids.user_id', '=', self.owner_user.id))
        self.assertEqual(set(found.ids) & self._fixture_ids(), {self.line_recent.id, self.line_old.id})

    def test_chief_above_the_tutor_sees_tutees(self):
        self.assertIn(self.line_other, self._search(self.chief_user))

    def test_plain_teacher_only_own_subjects(self):
        found = self._search(self.other_user)
        self.assertEqual(set(found.ids) & self._fixture_ids(), {self.line_other.id, self.line_foreign.id})

    def test_tutor_pivot_groups_every_subject(self):
        domain = self._action(self.tutor_user)['domain'] + [('student_id', '=', self.student1.id)]
        groups = self.env['ems.attendance_session_line'].with_user(self.tutor_user).read_group(
            domain, ['absence_rate:avg'], ['subject_id'])
        self.assertEqual({group['subject_id'][0] for group in groups}, {self.subject_a.id, self.subject_b.id})

    def test_tutor_current_course_excludes_archived_session_of_another_teacher(self):
        self.session_other.action_archive()
        self.assertNotIn(self.line_other, self._search(self.tutor_user))

    def _fixture_ids(self):
        return {self.line_recent.id, self.line_old.id, self.line_other.id, self.line_foreign.id}
