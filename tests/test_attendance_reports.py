# -*- coding: utf-8 -*-

from datetime import date, timedelta

from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval, time

from .common import create_level_study, create_role_employee, create_role_user, next_student_id


class AttendanceReportCommon(TransactionCase):
    """Shared fixtures: two teachers, two groups/subjects, two students (student1 in group1,
    student2 in group2) and owner's sessions."""

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
            'main_group_id': cls.group1.id,
        })
        cls.student2 = cls.env['res.partner'].create({
            'name': 'Test Student 2 (Attendance Reports)', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group2.id,
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
        # owner also takes the roll-call of group2 (subject_a), where student2 is.
        template_group2 = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.owner_employee.id])], 'study_ids': [(6, 0, [cls.study2.id])],
            'subject_id': cls.subject_a.id, 'group_ids': [(6, 0, [cls.group2.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule_group2 = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': template_group2.id, 'weekday': '5',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
        })
        session_group2 = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule_group2.id, 'date': cls.today,
            'mode': 'manual', 'session_teacher_id': cls.owner_employee.id,
        })
        cls.line_group2 = cls.env['ems.attendance_session_line'].create({
            'student_id': cls.student2.id, 'status_id': cls.status_attended.id,
            'attendance_session_id': session_group2.id,
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
    the dropdowns (allowed_group_ids/allowed_student_ids and the subject_label options, taken from
    the lines the user may consult), the print() dispatch that fetches ems.attendance_session_line ids per
    type, the opt-in per-dimension Details/Strikes (detail_status_ids/include_strikes/warning, now
    shared by all 3 variants), and the exclusion of student-less orphan lines."""

    # --- Dropdowns: the lines the user may consult (_get_reports_domain), issue #633 ------
    # owner takes the roll-call of subject_a in group1 (student1) and group2 (student2); 'other'
    # teaches subject_b in group1 (ems.teaching) but has never taken a roll-call here.

    def _scope(self, user, report_type='student'):
        wizard = self._wizard(user, report_type=report_type)
        wizard._compute_allowed_ids()
        labels = {label for label, _name in wizard._selection_subject_label()}
        return wizard.allowed_group_ids, wizard.allowed_student_ids, labels

    def test_dropdowns_offer_the_teachers_own_roll_calls(self):
        groups, students, labels = self._scope(self.owner_user)
        self.assertEqual(groups & (self.group1 | self.group2), self.group1 | self.group2)
        self.assertEqual(students & (self.student1 | self.student2), self.student1 | self.student2)
        self.assertIn(self.subject_a.display_name, labels)
        self.assertNotIn(self.subject_b.display_name, labels)

    def test_dropdowns_ignore_teaching_without_roll_calls(self):
        # What the reports offer comes from the attendance itself, never from ems.teaching.
        groups, students, labels = self._scope(self.other_user)
        self.assertFalse(groups & (self.group1 | self.group2))
        self.assertFalse(students & (self.student1 | self.student2))
        self.assertFalse(labels & {self.subject_a.display_name, self.subject_b.display_name})

    def test_dropdowns_whole_centre_for_the_administrator(self):
        groups, students, labels = self._scope(self.admin_user)
        self.assertLessEqual(self.group1 | self.group2, groups)
        self.assertLessEqual(self.student1 | self.student2, students)
        self.assertIn(self.subject_a.display_name, labels)

    def test_subject_outside_the_scope_prints_nothing(self):
        # Not offered to 'other', and a value sent by hand still only reaches the lines in scope.
        wizard = self._wizard(self.other_user, report_type='subject', subject_label=self.subject_a.display_name,
                              group_ids=[(6, 0, [self.group1.id])], from_date=self.old_date, to_date=self.today)
        self.assertFalse(wizard._get_report_lines())

    def test_allowed_group_ids_for_subject_are_the_groups_having_it(self):
        wizard = self._wizard(self.owner_user, report_type='subject', subject_label=self.subject_a.display_name)
        self.assertEqual(wizard.allowed_group_ids, self.group1 | self.group2)

    def test_onchange_subject_label_prefills_group_ids_with_every_allowed_group(self):
        wizard = self.env['ems.attendance_report_wizard'].with_user(self.owner_user).new({'report_type': 'subject'})
        wizard.subject_label = self.subject_a.display_name
        wizard._onchange_subject_label()
        self.assertEqual(set(wizard.group_ids.ids), {self.group1.id, self.group2.id})

    # --- Prefill from the 'Reports' screen's search facets (issue #633) ------------------

    def _defaults(self, **context):
        keys = {f'ems_report_{name}': value for name, value in context.items()}
        return self.env['ems.attendance_report_wizard'].with_user(self.owner_user).with_context(**keys).default_get(
            ['report_type', 'student_id', 'group_id', 'subject_label'])

    def test_student_facet_prefills_the_student_report(self):
        defaults = self._defaults(student_id=self.student1.id, student_group_id=self.group1.id)
        self.assertEqual((defaults['report_type'], defaults['student_id']), ('student', self.student1.id))

    def test_group_facet_prefills_the_group_report(self):
        defaults = self._defaults(student_group_id=self.group2.id)
        self.assertEqual((defaults['report_type'], defaults['group_id']), ('group', self.group2.id))

    def test_subject_and_group_facets_prefill_the_subject_report_on_that_group(self):
        defaults = self._defaults(subject_id=self.subject_a.id, student_group_id=self.group2.id)
        self.assertEqual((defaults['report_type'], defaults['subject_label']), ('subject', self.subject_a.display_name))
        wizard = self.env['ems.attendance_report_wizard'].with_user(self.owner_user).with_context(
            ems_report_student_group_id=self.group2.id).new(defaults)
        wizard._onchange_subject_label()
        self.assertEqual(wizard.group_ids._origin, self.group2)

    def test_no_facet_keeps_the_plain_defaults(self):
        self.assertEqual(self._defaults()['report_type'], 'group')

    # --- tutor_ids: unified for all 3 types --------------------------------------------

    def test_tutor_ids_follow_report_type(self):
        tutor = self.env['hr.employee'].create({
            'name': 'Test Tutor (Attendance Reports)', 'employee_type': 'teacher',
        })
        self.group1.tutor_id = tutor
        group_wizard = self._wizard(report_type='group', group_id=self.group1.id)
        self.assertIn(tutor, group_wizard.tutor_ids)
        subject_wizard = self._wizard(report_type='subject', subject_label=self.subject_a.display_name,
                                      group_ids=[(6, 0, [self.group1.id])])
        self.assertIn(tutor, subject_wizard.tutor_ids)

    # --- print(): ORM-fetched status_ids per report_type -------------------------------

    def test_print_group_returns_all_lines_in_range(self):
        wizard = self._wizard(report_type='group', group_id=self.group1.id,
                              from_date=self.old_date, to_date=self.today)
        self.assertEqual(wizard.print()['type'], 'ir.actions.report')
        self.assertEqual(sorted(wizard._get_report_lines().ids), sorted([self.line_recent.id, self.line_old.id]))

    def test_print_subject_returns_lines_for_subject(self):
        wizard = self._wizard(report_type='subject', subject_label=self.subject_a.display_name,
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
                                  student_id=self.student1.id, subject_label=self.subject_a.display_name,
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

        subject_wizard = self._wizard(report_type='subject', subject_label=self.subject_a.display_name,
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

    def test_student_group_is_the_students_group_when_the_roll_call_is_taken(self):
        self.assertEqual(self.line_recent.student_group_id, self.group1)
        # A later group change only moves the following roll-calls, never the earlier ones.
        self.student1.main_group_id = self.group2
        self.assertEqual(self.line_recent.student_group_id, self.group1)
        new_line = self.env['ems.attendance_session_line'].create({
            'student_id': self.student1.id, 'status_id': self.status_attended.id,
            'attendance_session_id': self.session_recent.id,
        })
        self.assertEqual(new_line.student_group_id, self.group2)

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
            ({'report_type': 'subject', 'subject_label': self.subject_a.display_name}, 'TARWA_Test_Subject_A_(Attendance_Reports)'),
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
        Line = self.env['ems.attendance_session_line'].with_user(self.owner_user)
        self.assertEqual(result.get('domain'), Line._get_reports_domain())
        self.assertEqual(set(Line.search(result['domain']).ids) & {self.line_recent.id, self.line_old.id, self.line_group2.id},
                         {self.line_recent.id, self.line_old.id, self.line_group2.id})
        self.assertEqual(result.get('context', {}).get('pivot_measures'), ['absence_rate', 'strike_count', '__count'])
        self.assertEqual(result['context'].get('search_default_my_subjects'), 1)

    def test_reports_action_unscoped_for_academic_admin(self):
        # group_academic_admin implies group_director (security/groups.xml), which sees the whole
        # centre - the current-course-only domain still applies to everyone, admin included.
        server_action = self.env.ref('ems.action_attendance_reports_open')
        result = server_action.with_user(self.admin_user).run()
        self.assertEqual(result.get('domain'), [('session_active', '=', True)])
        self.assertNotIn('search_default_my_subjects', result['context'])
        self.assertIn(self.group1, self.line_recent.group_ids)

    # --- Student form's 'Attendance' button: same screen, filtered on one student (issue #519) ---

    def test_student_attendance_action_keeps_teacher_scope_and_filters_student(self):
        result = self.student1.with_user(self.owner_user).action_view_attendance_reports()
        self.assertEqual(result.get('domain'),
                         self.env['ems.attendance_session_line'].with_user(self.owner_user)._get_reports_domain())
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

    def test_reports_unscoped_for_guidance_and_coexistence(self):
        # Issue #626: both posts read every student's attendance centre-wide, so neither entry
        # point narrows them to their own teaching.
        server_action = self.env.ref('ems.action_attendance_reports_open')
        for role in ('orientation', 'coexistence'):
            with self.subTest(role=role):
                user = create_role_user(self, role, f'test_{role}_arw626')
                create_role_employee(self, user)
                for result in (server_action.with_user(user).run(),
                               self.student1.with_user(user).action_view_attendance_reports()):
                    self.assertEqual(result.get('domain'), [('session_active', '=', True)])
                    self.assertNotIn('search_default_my_subjects', result['context'])
                    # A session of another teacher's subject is actually listed.
                    lines = self.env['ems.attendance_session_line'].with_user(user).search(result['domain'])
                    self.assertIn(self.line_recent, lines)

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

    # --- Students removed from the roll-call (archived lines) never count (issue #628) ---

    def test_reports_action_ignores_removed_students_from_the_students_list(self):
        # The students' list runs with active_test off and a button's result inherits the context
        # of the screen it is clicked on, as the web client merges it: (screen, action).
        self.line_old.active = False
        screen_context = safe_eval(self.env.ref('ems.action_student_kanban').context)
        self.assertIs(screen_context.get('active_test'), False)
        for result in (self.env.ref('ems.action_attendance_reports_open').with_user(self.admin_user).run(),
                       self.student1.with_user(self.admin_user).action_view_attendance_reports()):
            lines = self.env['ems.attendance_session_line'].with_user(self.admin_user).with_context(
                **{**screen_context, **result['context']})
            self.assertEqual(lines.search(result['domain'] + [('student_id', '=', self.student1.id)]), self.line_recent)
            groups = lines.read_group(result['domain'] + [('student_id', '=', self.student1.id)], ['absence_rate:avg'], ['subject_id'])
            self.assertEqual(groups[0]['subject_id_count'], 1)

    def test_pdf_reports_ignore_removed_students_whatever_the_context(self):
        self.line_old.active = False
        for report_type in ('group', 'student', 'subject'):
            with self.subTest(report_type=report_type):
                wizard = self._wizard(report_type=report_type, group_id=self.group1.id,
                                      student_id=self.student1.id, subject_label=self.subject_a.display_name,
                                      group_ids=[(6, 0, [self.group1.id])], from_date=self.old_date, to_date=self.today)
                self.assertEqual(wizard.with_context(active_test=False)._get_report_lines(), self.line_recent)

    def test_year_record_rate_ignores_removed_students_whatever_the_context(self):
        self.line_old.write({'status_id': self.env.ref('ems.attendance_status_miss').id, 'active': False})
        rate, _by_subject = self.env['ems.student.year_record'].with_context(active_test=False)._attendance_rates(self.student1)
        self.assertEqual(rate, 100.0)

    # --- opt-in per-dimension 'Details'/'Strikes' (detail_status_ids/include_strikes) ---
    # The per-dimension 'Details' table used to list every session unconditionally, which is what
    # made the by-subject PDF choke on large subject/group combinations. It's now opt-in and shared
    # by all 3 report variants: detail_status_ids defaults to absence-category statuses only,
    # include_strikes defaults to True, and picking anything beyond the default warns (inline) that
    # it may be slow/large.

    def test_default_detail_status_ids_is_absence_category_only(self):
        wizard = self._wizard(report_type='subject', subject_label=self.subject_a.display_name,
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
        wizard = self._wizard(report_type='subject', subject_label=self.subject_a.display_name,
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
        self.assertIn(miss_line, values['detail_entries'][self.subject_a.display_name])
        self.assertNotIn(self.line_recent, values['detail_entries'][self.subject_a.display_name])

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
        self.assertIn(miss_line, values['detail_entries'][self.subject_a.display_name])
        self.assertNotIn(self.line_recent, values['detail_entries'][self.subject_a.display_name])

    def test_include_strikes_toggles_detail_strikes(self):
        strike = self.env['ems.strike'].create({
            'student_id': self.student1.id, 'teacher_id': self.owner_employee.id,
            'attendance_session_line_id': self.line_recent.id,
        })
        on = self._wizard(report_type='subject', subject_label=self.subject_a.display_name,
                          group_ids=[(6, 0, [self.group1.id])], from_date=self.old_date, to_date=self.today,
                          include_strikes=True)
        on_values = self._values(on)
        self.assertIn(strike, on_values['detail_strikes'][self.student1])

        off = self._wizard(report_type='subject', subject_label=self.subject_a.display_name,
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

    def _shared_session(self):
        """A session of a template shared by group1 and group2, with a line for each group's student."""
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.owner_employee.id])], 'study_ids': [(6, 0, [self.study1.id, self.study2.id])],
            'subject_id': self.subject_a.id, 'group_ids': [(6, 0, [self.group1.id, self.group2.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '3',
            'start_time': 11.0, 'end_time': 12.0, 'space_id': self.space.id,
        })
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': self.today,
            'mode': 'manual', 'session_teacher_id': self.owner_employee.id,
        })
        line1, line2 = self.env['ems.attendance_session_line'].create([
            {'student_id': student.id, 'status_id': self.status_attended.id, 'attendance_session_id': session.id}
            for student in (self.student1, self.student2)
        ])
        return session, line1, line2


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
        self.assertEqual(set(values['lines']), {self.subject_a.display_name})

    def test_render_ignores_crafted_status_ids_for_plain_teacher(self):
        wizard = self._wizard(self.owner_user, report_type='student', student_id=self.student1.id,
                              from_date=self.other_date, to_date=self.today)
        values = self._values(wizard, status_ids=[self.line_recent.id, self.line_other.id])
        self.assertNotIn(self.subject_b.display_name, values['lines'])

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
        self.assertEqual(set(values['lines']), {self.subject_a.display_name, self.subject_b.display_name})
        # The detail rows read the other teacher's session header too.
        self.assertEqual(values['detail_entries'][self.subject_b.display_name][0].attendance_session_id.session_teacher_id,
                         self.other_employee)

    def test_chief_above_the_tutor_every_subject(self):
        line_ids, values = self._report_lines(self.chief_user)
        self.assertIn(self.line_other.id, line_ids)
        self.assertEqual(set(values['lines']), {self.subject_a.display_name, self.subject_b.display_name})

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
        wizard._onchange_subject_label()
        return wizard.from_date, wizard.to_date

    # --- by group ------------------------------------------------------------------------

    def test_tutor_finds_tutored_group_without_teaching_it(self):
        wizard = self._wizard(self.tutor_user, report_type='group')
        wizard._compute_allowed_ids()
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertNotIn(self.group2, wizard.allowed_group_ids)

    def test_group_tutor_every_subject(self):
        lines, values = self._lines(self.tutor_user, report_type='group', group_id=self.group1.id)
        # line_foreign is student2's (group2), in a group1 session: not a student of the group.
        self.assertEqual(set(lines.ids), {self.line_recent.id, self.line_old.id, self.line_other.id})
        self.assertEqual(set(values['lines']), {self.subject_a.display_name, self.subject_b.display_name})
        # The detail rows read the other teacher's session header too.
        self.assertEqual(values['detail_entries'][self.subject_b.display_name][0].attendance_session_id.session_teacher_id,
                         self.other_employee)

    def test_group_chief_above_the_tutor_every_subject(self):
        _lines, values = self._lines(self.chief_user, report_type='group', group_id=self.group1.id)
        self.assertEqual(set(values['lines']), {self.subject_a.display_name, self.subject_b.display_name})

    def test_group_plain_teacher_only_own_sessions(self):
        lines, values = self._lines(self.owner_user, report_type='group', group_id=self.group1.id)
        self.assertEqual(set(lines.ids), {self.line_recent.id, self.line_old.id})
        self.assertEqual(set(values['lines']), {self.subject_a.display_name})

    def test_group_report_follows_the_students_group_not_the_sessions(self):
        # A session shared by both groups: each group's report only has its own students.
        shared_session, line1, line2 = self._shared_session()
        group1_lines, _values = self._lines(self.env.user, report_type='group', group_id=self.group1.id)
        group2_lines, _values = self._lines(self.env.user, report_type='group', group_id=self.group2.id)
        self.assertIn(line1, group1_lines)
        self.assertNotIn(line2, group1_lines)
        self.assertIn(line2, group2_lines)
        self.assertNotIn(line1, group2_lines)

    def test_group_tutor_covers_a_tutee_in_another_groups_session(self):
        # student1 (group1) attends a session of group2 only, e.g. a subject taken with another group.
        line = self.env['ems.attendance_session_line'].create({
            'student_id': self.student1.id, 'status_id': self.status_attended.id,
            'attendance_session_id': self.line_group2.attendance_session_id.id,
        })
        lines, _values = self._lines(self.tutor_user, report_type='group', group_id=self.group1.id)
        self.assertIn(line, lines)

    def test_group_onchange_tutor_covers_every_session(self):
        self.assertEqual(self._onchange_dates(self.tutor_user, report_type='group', group_id=self.group1.id),
                         (self.other_date, self.today))

    def test_group_outside_tutor_scope_not_widened(self):
        # A group picked by hand outside the dropdown gets no sudo(): record rules decide.
        lines, _values = self._lines(self.tutor_user, report_type='group', group_id=self.group2.id)
        self.assertFalse(lines)

    # --- by subject ----------------------------------------------------------------------

    def _labels(self, user):
        wizard = self.env['ems.attendance_report_wizard'].with_user(user)
        return {label for label, _name in wizard._selection_subject_label()}

    def test_tutor_finds_subjects_taught_by_others_in_tutored_group(self):
        wizard = self._wizard(self.tutor_user, report_type='subject', subject_label=self.subject_b.display_name)
        self.assertLessEqual({self.subject_a.display_name, self.subject_b.display_name}, self._labels(self.tutor_user))
        # subject_a is also taken by group2's students, who are not in the tutor's scope.
        self.assertEqual(wizard._get_groups_teaching(self.subject_a.display_name), self.group1)

    def test_plain_teacher_subjects_and_groups(self):
        wizard = self._wizard(self.owner_user, report_type='subject', subject_label=self.subject_a.display_name)
        labels = self._labels(self.owner_user)
        self.assertIn(self.subject_a.display_name, labels)
        self.assertNotIn(self.subject_b.display_name, labels)
        self.assertEqual(wizard._get_groups_teaching(self.subject_a.display_name), self.group1 | self.group2)

    def test_subject_tutor_every_session_of_tutored_group(self):
        # line_foreign (student2, group2) shares the session but is neither a tutee nor in group1.
        lines, values = self._lines(self.tutor_user, report_type='subject', subject_label=self.subject_b.display_name,
                                    group_ids=[(6, 0, [self.group1.id])])
        self.assertEqual(lines, self.line_other)
        self.assertEqual(set(values['lines']), {self.student1})

    def test_subject_onchange_tutor_prefills_group_and_dates(self):
        wizard = self.env['ems.attendance_report_wizard'].with_user(self.tutor_user).new({
            'report_type': 'subject', 'subject_label': self.subject_b.display_name,
        })
        wizard._onchange_subject_label()
        self.assertEqual(wizard.group_ids._origin, self.group1)
        self.assertEqual((wizard.from_date, wizard.to_date), (self.other_date, self.other_date))

    def test_subject_outside_tutor_scope_not_widened(self):
        lines, _values = self._lines(self.tutor_user, report_type='subject', subject_label=self.subject_a.display_name,
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

    def test_group_filter_and_grouping_follow_the_students_group(self):
        # The pivot's "Group" filter and group-by: a session shared by both groups puts each line
        # under its own student's group only, never under every group of the session.
        _session, line1, line2 = self._shared_session()
        search_arch = self.env.ref('ems.view_attendance_report_analysis_search').arch
        self.assertIn('<field name="student_group_id"/>', search_arch)
        self.assertIn("'group_by': 'student_group_id'", search_arch)
        Line = self.env['ems.attendance_session_line']
        self.assertEqual(Line.search([('student_group_id', '=', self.group1.id), ('id', 'in', (line1 | line2).ids)]), line1)
        groups = Line.read_group([('id', 'in', (line1 | line2).ids)], ['__count'], ['student_group_id'])
        self.assertEqual({group['student_group_id'][0]: group['student_group_id_count'] for group in groups},
                         {self.group1.id: 1, self.group2.id: 1})

    def test_tutor_current_course_excludes_archived_session_of_another_teacher(self):
        self.session_other.action_archive()
        self.assertNotIn(self.line_other, self._search(self.tutor_user))

    def _fixture_ids(self):
        return {self.line_recent.id, self.line_old.id, self.line_other.id, self.line_foreign.id}


class TestAttendanceReportScopeLadder(AttendanceReportTutorScopeCommon):
    """Issue #633: one scope decides what the 'Reports' screen shows and what the PDF wizard offers
    and prints (_get_reports_domain). It escalates by the chain of command: a teacher sees the
    subjects they teach (never a roll-call taken on guard duty), a tutor every subject of their
    tutees, the chiefs above the tutor the same, a Department Chief and a Head of Studies the
    students of the studies their department or area manages; the Director, Guidance, Coexistence
    and Secretariat see the whole centre."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A roll-call of owner's subject_a in group1 taken by a teacher on guard duty.
        cls.guard_user = create_role_user(cls, 'teacher', 'test_guard_arw633', name='Test Guard (Attendance Reports)')
        guard_employee = create_role_employee(cls, cls.guard_user)
        session_guard = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': cls.today - timedelta(days=3),
            'mode': 'guard', 'session_teacher_id': guard_employee.id,
        })
        cls.line_guard = cls.env['ems.attendance_session_line'].create({
            'student_id': cls.student1.id, 'status_id': cls.status_attended.id,
            'attendance_session_id': session_guard.id,
        })

        # An area (top-level department, its manager is the Head of Studies) with a department that
        # manages study1 (group1); another area and another department managing nothing.
        def chief(role, login):
            user = create_role_user(cls, role, login, name=f'Test {login}')
            return user, create_role_employee(cls, user)
        cls.hos_user, hos = chief('head_of_studies', 'test_hos_arw633')
        cls.other_hos_user, other_hos = chief('head_of_studies', 'test_other_hos_arw633')
        cls.study_chief_user, study_chief = chief('department_chief', 'test_study_chief_arw633')
        cls.other_chief_user, other_chief = chief('department_chief', 'test_other_chief_arw633')
        Department = cls.env['hr.department']
        area = Department.create({'name': 'Test Area (Attendance Reports)', 'manager_id': hos.id, 'is_top_level': True})
        Department.create({'name': 'Test Other Area (Attendance Reports)', 'manager_id': other_hos.id, 'is_top_level': True})
        department = Department.create({
            'name': 'Test Department (Attendance Reports)', 'parent_id': area.id, 'manager_id': study_chief.id,
        })
        Department.create({'name': 'Test Other Department (Attendance Reports)', 'parent_id': area.id,
                           'manager_id': other_chief.id})
        cls.study1.managing_department_id = department

        cls.director_user = create_role_user(cls, 'director', 'test_director_arw633')
        create_role_employee(cls, cls.director_user)
        cls.orientation_user = create_role_user(cls, 'orientation', 'test_orientation_arw633')
        create_role_employee(cls, cls.orientation_user)
        # The coexistence post is held by a teacher (ems.role_coexistence is employee_type teacher).
        cls.coexistence_user = create_role_user(cls, 'coexistence', 'test_coexistence_arw633')
        cls.coexistence_user.groups_id = [(4, cls.group_teacher.id)]
        create_role_employee(cls, cls.coexistence_user)
        cls.secretary_user = create_role_user(cls, 'secretary', 'test_secretary_arw633')
        create_role_employee(cls, cls.secretary_user, employee_type='asp')

    def _fixture_lines(self):
        return (self.line_recent | self.line_old | self.line_group2 | self.line_other | self.line_foreign
                | self.line_guard)

    def _expected(self):
        everything = self._fixture_lines()
        student1 = self.line_recent | self.line_old | self.line_other | self.line_guard
        return {
            self.owner_user: self.line_recent | self.line_old | self.line_guard | self.line_group2,
            self.other_user: self.line_other | self.line_foreign,
            self.guard_user: self.env['ems.attendance_session_line'],
            self.tutor_user: student1,
            self.chief_user: student1,
            self.study_chief_user: student1,
            self.other_chief_user: self.env['ems.attendance_session_line'],
            self.hos_user: student1,
            self.other_hos_user: self.env['ems.attendance_session_line'],
            self.director_user: everything,
            self.orientation_user: everything,
            self.coexistence_user: everything,
            self.secretary_user: everything,
        }

    def _pivot_lines(self, user):
        action = self.env.ref('ems.action_attendance_reports_open').with_user(user).run()
        return self.env['ems.attendance_session_line'].with_user(user).search(action['domain']) & self._fixture_lines()

    def test_reports_screen_follows_the_chain_of_command(self):
        for user, expected in self._expected().items():
            with self.subTest(user=user.login):
                self.assertEqual(self._pivot_lines(user), expected)

    def test_pdf_wizard_offers_and_prints_exactly_what_the_reports_screen_shows(self):
        """The guarantee the two never drift apart again: for every profile, the students, groups and
        subjects the wizard offers are those of the lines on the 'Reports' screen, and the by-student
        PDFs of the students it offers add up to those very lines."""
        fixture_students, fixture_groups = self.student1 | self.student2, self.group1 | self.group2
        fixture_labels = {self.subject_a.display_name, self.subject_b.display_name}
        for user in self._expected():
            with self.subTest(user=user.login):
                pivot = self._pivot_lines(user)
                wizard = self._wizard(user, report_type='student', from_date=self.other_date, to_date=self.today)
                wizard._compute_allowed_ids()
                self.assertEqual(wizard.allowed_student_ids & fixture_students, pivot.student_id)
                self.assertEqual(wizard.allowed_group_ids & fixture_groups, pivot.student_group_id)
                labels = {label for label, _name in wizard._selection_subject_label()}
                self.assertEqual(labels & fixture_labels, set(pivot.mapped('subject_label')))
                printed = self.env['ems.attendance_session_line']
                for student in wizard.allowed_student_ids & fixture_students:
                    wizard.student_id = student
                    printed |= wizard._get_report_lines()
                self.assertEqual(printed.with_env(pivot.env) & self._fixture_lines(), pivot)

    def test_whole_centre_posts_print_the_three_reports(self):
        for user in (self.orientation_user, self.coexistence_user, self.secretary_user):
            for report_type, vals in (('student', {'student_id': self.student2.id}),
                                      ('group', {'group_id': self.group2.id}),
                                      ('subject', {'subject_label': self.subject_b.display_name,
                                                   'group_ids': [(6, 0, [self.group2.id])]})):
                with self.subTest(user=user.login, report_type=report_type):
                    wizard = self._wizard(user, report_type=report_type, from_date=self.other_date,
                                          to_date=self.today, **vals)
                    self.assertEqual(wizard.print()['type'], 'ir.actions.report')
                    values = self._values(wizard)
                    self.assertIn(self.line_foreign, values['main'].entries)

    def test_reports_cover_the_current_course_only(self):
        self.session_old.action_archive()
        self.assertNotIn(self.line_old, self._pivot_lines(self.orientation_user))
        for report_type, vals in (('student', {'student_id': self.student1.id}),
                                  ('group', {'group_id': self.group1.id}),
                                  ('subject', {'subject_label': self.subject_a.display_name,
                                               'group_ids': [(6, 0, [self.group1.id])]})):
            with self.subTest(report_type=report_type):
                wizard = self._wizard(self.orientation_user, report_type=report_type, from_date=self.old_date,
                                      to_date=self.today, **vals)
                self.assertNotIn(self.line_old, wizard._get_report_lines())

    def test_guard_duty_roll_call_belongs_to_the_template_teacher(self):
        self.assertNotIn(self.line_guard, self._pivot_lines(self.guard_user))
        self.assertIn(self.line_guard, self._pivot_lines(self.owner_user))
