# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Admin user manuals.

Split into one test METHOD per topical batch of manuals rather than one method for the whole
role, unlike test_docs_screenshots_head_of_studies.py's single method - 17 admin manuals is too
much fixture/capture work for one method to stay reviewable. See
docs/en/developers/shared/testing.md ("DocsScreenshotMixin") for the mechanism.

Tagged '-standard' on purpose - see the identical NOTE in test_docs_screenshots.py. Run a
single batch by hand, e.g.:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsAdmin.test_capture_batch1_absences_attendance_notice_strike' --stop-after-init -c /etc/odoo/odoo.conf"

Writes PNGs to /tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR); copy them into
docs/assets/admin/ by hand afterwards. See test_docs_screenshots.py's own module docstring for
the full rationale (rolled-back transaction, made-up people, one element per shot).
"""
import base64
from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .common import (
    DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user,
    next_student_id,
)


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsAdmin(HttpCase, DocsScreenshotMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Both 'academic_admin' (the EMS Academic-block Administrator role, needed for the
        # normal ems.* config screens) and base.group_system (needed for Odoo's own Settings
        # screen, res.config.settings - see CLAUDE.md-adjacent research this session:
        # ems.group_academic_admin does NOT imply base.group_system on its own, only
        # ems.group_settings_admin does) - one login covers every admin capture in this file,
        # matching how the real centre "Administrator" account actually holds both.
        cls.admin_user = create_role_user(cls, 'academic_admin', 'doc_shot_admin', lang='ca_ES',
                                          name='Administrador EMS', email='admin.ems@example.com')
        cls.admin_user.write({'groups_id': [(4, cls.env.ref('ems.group_settings_admin').id)]})

    @classmethod
    def _student(cls, name, group, age=15, **overrides):
        return cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
            'birth_date': date.today() - relativedelta(years=age),
            **overrides,
        })

    def test_capture_batch1_absences_attendance_notice_strike(self):
        # --- Notice (Communications > Notices > New) ---
        level, study, group = create_level_study_group(
            self, 'ADM', level={'name': 'Administració'}, study={'name': 'Estudi Notificacions'})
        student = self._student(
            'Marta Prova', group, age=15,
            student_email='marta.prova@example.com', email='marta.prova.personal@example.com')
        family = self.env['res.partner'].create({
            'name': 'Família Prova', 'contact_type': 'family', 'email': 'familia.prova@example.com',
        })
        self.env['res.partner.relation'].create({
            'left_partner_id': family.id,
            'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': student.id,
        })
        # res.partner.relation.all (what student.relation_all_ids actually reads) is a SQL VIEW
        # model, not a plain table - it does not see the res.partner.relation row just created
        # above within the same transaction unless explicitly flushed first. Without this,
        # _onchange_groups() below silently finds 0 relations and skips the family recipient
        # entirely (found by actually inspecting notice_line_ids - not a hypothetical).
        self.env.flush_all()
        self.env.invalidate_all()
        notice = self.env['ems.notice'].create({
            'subject': 'Reunió de pares i mares', 'message': '<p>Us convidem a la reunió trimestral.</p>',
            'recipient_type': 'both', 'group_ids': [(6, 0, [group.id])],
        })
        # Populates notice_line_ids the same way the form's own onchange does when a real user
        # picks Groups/Send to - see models/communications/notice.py's _onchange_groups(). Calling
        # it directly on a persisted record (not a NewId) is safe: the resulting field assignment
        # is a real write, not a virtual onchange preview.
        notice._onchange_groups()
        self._capture(
            '/odoo/action-ems.action_communication_list/%d' % notice.id,
            '.o_form_sheet', 'admin-notice-create-form.png',
            login='doc_shot_admin', wait_for='.o_form_sheet .o_field_widget[name="notice_line_ids"] .o_data_row',
        )

        # --- Attendance statuses (Attendance > Configuration > Sessions > Statuses) ---
        # No fixture needed: this is EMS's own shipped configuration data (roll-call button
        # catalogue), not personal data, so the real seeded rows are safe to screenshot directly.
        self._capture(
            '/odoo/action-ems.action_attendance_status_list',
            '.o_list_table', 'admin-attendance-status-list.png',
            login='doc_shot_admin', wait_for='.o_list_renderer .o_data_row',
        )

        # --- Strike reasons (Convivencia > Configuration > Strikes > Reasons) ---
        # Same as above - shipped configuration data, not personal, safe to capture directly.
        self._capture(
            '/odoo/action-ems.action_strike_reason_list',
            '.o_list_table', 'admin-strike-reasons-list.png',
            login='doc_shot_admin', wait_for='.o_list_renderer .o_data_row',
        )

        # --- Staff Absence Settings (Settings > EMS Management) ---
        # Odoo's own res.config.settings screen: a single page with one <app> tab per module,
        # each holding several named <block>s. Each <setting id="..."> renders with that same id
        # as a real DOM id (confirmed by reading web's settings_form_compiler.js /
        # form_compiler.js / setting.xml this session) - #ems_full_day_hours is stable to target.
        # Navigate on the default (first) tab, then click the "EMS Management" tab to reveal it.
        self._capture(
            '/odoo/action-base_setup.action_general_configuration',
            # ':has()' (Chrome 150 here, well past the ~105 baseline) selects the specific
            # settings block containing our target id - the <block> itself renders no stable
            # class/id of its own (only title text, not selector-safe), so this is the only way
            # to clip precisely to "Staff Absence Settings" without also grabbing its siblings.
            '.o_settings_container:has(#ems_full_day_hours)',
            'admin-absences-settings.png',
            login='doc_shot_admin', wait_for='a.tab[data-key="ems"]',
            # Scrolled into view after the tab switch, and captured within the viewport: the
            # settings page scrolls inside its own container, so a block below the viewport's
            # bottom edge is captured as blank, and capturing beyond the viewport resizes the
            # page, which undoes the scroll.
            run=['document.querySelector(\'a.tab[data-key="ems"]\').click()',
                 "document.querySelector('#ems_full_day_hours').scrollIntoView({block: 'start'})"],
            wait_after=['#ems_absence_document_escalation_days', '#ems_full_day_hours'],
            beyond_viewport=False,
        )

    # ------------------------------------------------------------------------------------------
    # Shared fixtures for batches 2-4: a small made-up study with two courses, a teacher and a
    # classroom. Everything personal on screen comes from here, never from this box's data.
    # ------------------------------------------------------------------------------------------

    def _curriculum_fixture(self):
        level, study, group = create_level_study_group(self, 'ADMB', level={
            'name': 'Formació professional (proves)',
        }, study={
            'code': 'ADMB01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        last_group = self.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id,
        })
        subjects = self.env['ems.subject'].create([{
            'code': code, 'acronym': acronym, 'name': name, 'study_ids': [(6, 0, [study.id])],
        } for code, acronym, name in (
            ('ADMBSUB1', 'BD', 'Bases de dades'),
            ('ADMBSUB2', 'PRG', 'Programació'),
        )])
        return level, study, group, last_group, subjects

    def _teacher(self, name):
        return self.env['hr.employee'].create({'name': name, 'employee_type': 'teacher'})

    def _form_url(self, model, record):
        action = self.env['ir.actions.act_window'].create({
            'name': record.display_name, 'res_model': model, 'view_mode': 'form',
            'domain': [('id', '=', record.id)],
        })
        return '/odoo/action-%d/%d' % (action.id, record.id)

    def test_capture_batch2_course_roles_groups(self):
        level, study, group, last_group, subjects = self._curriculum_fixture()

        # --- Current course (Settings > EMS Management > Course Management Settings) ---
        # Course names (2025-2026...) are configuration, not personal data.
        self._capture(
            '/odoo/action-base_setup.action_general_configuration',
            '.o_settings_container:has(#current_course_id)', 'admin-course-settings.png',
            login='doc_shot_admin', wait_for='a.tab[data-key="ems"]',
            click='a.tab[data-key="ems"]', wait_after='#current_course_id',
        )

        # --- Groups: a main group with its tutor, delegate, sub-delegate and students ---
        tutor = self._teacher('0000 Laia Prats Coll')
        group.tutor_id = tutor
        students = self.env['res.partner'].browse([
            self._student(name, group).id for name in ('Nil Exemple Serra', 'Aina Mostra Puig')])
        group.delegate_id = students[0]
        group.subdelegate_id = students[1]
        self._capture(
            self._form_url('ems.group', group), '.o_form_sheet', 'admin-groups-form.png',
            login='doc_shot_admin', wait_for=".o_form_sheet .o_field_widget[name='tutor_id']",
        )

        # --- Teacher roles: a teacher with two roles assigned by hand ---
        teacher = self._teacher('0000 Jordi Mostra Vidal')
        teacher.role_ids = [(6, 0, [self.env.ref('ems.role_tac').id, self.env.ref('ems.role_coexistence').id])]
        self._capture(
            self._form_url('hr.employee', teacher), ".o_form_sheet .o_inner_group:has(.o_field_widget[name='role_ids'])", 'admin-teacher-roles-employee.png',
            login='doc_shot_admin', wait_for=".o_field_widget[name='role_ids'] .badge",
        )
        # --- ...and a department with its Department Chief and Seminar Chief ---
        chief = self._teacher('0000 Marta Serra Font')
        seminar = self._teacher('0000 Pere Exemple Soler')
        department = self.env['hr.department'].create({
            'name': 'Informàtica (proves)', 'manager_id': chief.id, 'seminar_chief_id': seminar.id,
        })
        self._capture(
            self._form_url('hr.department', department), '.o_form_sheet', 'admin-teacher-roles-department.png',
            login='doc_shot_admin', wait_for=".o_field_widget[name='seminar_chief_id']",
        )

        # --- Course transition: preview over the made-up study only ---
        graduate = self._student('Júlia Exemple Font', last_group)
        self._student('Marc Mostra Riera', group)
        self.env['ems.graduation_wizard'].with_context(active_ids=graduate.ids).create({}).action_apply()
        target = self.env['ems.course'].search([('start', '=', 2098)], limit=1) \
            or self.env['ems.course'].create({'start': 2098, 'end': 2099})
        # Created as the admin: a transient record is only readable by its creator.
        wizard = self.env['ems.course_transition_wizard'].with_user(self.admin_user).create({
            'target_course_id': target.id, 'study_ids': [(6, 0, study.ids)],
        })
        # The "students with no group at all" warning is centre-wide (it names up to 10 of them,
        # whatever studies are picked): empty it for the shot, so no real student can appear.
        Wizard = self.env.registry['ems.course_transition_wizard']
        with patch.object(Wizard, '_orphan_students', lambda wizard: wizard.env['res.partner']):
            wizard.action_preview()
        action = self.env['ir.actions.act_window'].create({
            'name': 'Configurar el curs següent', 'res_model': 'ems.course_transition_wizard',
            'view_mode': 'form', 'target': 'new', 'res_id': wizard.id,
        })
        self._capture(
            '/odoo/action-%d' % action.id, '.modal-content', 'admin-course-transition-preview.png',
            login='doc_shot_admin', wait_for=".modal-content .o_field_widget[name='line_ids'] .o_data_row",
        )

    def test_capture_batch3_curriculum_workgroups(self):
        # --- Levels: the centre's own catalogue (configuration, not personal data), captured
        # before the made-up level below exists ---
        self._capture(
            '/odoo/action-ems.level_action', '.o_list_table', 'admin-levels-list.png',
            login='doc_shot_admin', wait_for='.o_list_renderer .o_data_row',
        )
        level, study, group, last_group, subjects = self._curriculum_fixture()

        # --- Studies: the made-up study, Subjects tab ---
        self._capture(
            self._form_url('ems.study', study), '.o_form_sheet', 'admin-study-form.png',
            login='doc_shot_admin', wait_for=".o_field_widget[name='subject_ids'] .o_data_row + .o_data_row",
        )

        # --- Subjects: a subject with its learning outcomes (Learning Outcome tab) ---
        subject = subjects[0]
        # An outcome's code must start with its subject's code.
        self.env['ems.outcome'].create([{
            'subject_id': subject.id, 'code': '%s_%s' % (subject.code, code), 'acronym': code, 'name': name,
        } for code, name in (
            ('RA1', "Reconeix els elements de les bases de dades analitzant-ne les funcions."),
            ('RA2', "Crea bases de dades definint-ne l'estructura i les característiques."),
            ('RA3', "Consulta la informació emmagatzemada fent servir assistents i llenguatges."),
        )])
        self._capture(
            self._form_url('ems.subject', subject), '.o_form_sheet', 'admin-subject-outcomes.png',
            login='doc_shot_admin', wait_for='.o_notebook',
            click='.o_notebook .nav-item:nth-child(2) .nav-link',
            wait_after=".o_field_widget[name='outcome_ids'] .o_data_row + .o_data_row",
        )

        # --- Workgroups: a workgroup with its members (Assigned to tab) ---
        members = self.env['hr.employee'].browse([self._teacher(name).id for name in (
            '0000 Laia Prats Coll', '0000 Jordi Mostra Vidal', '0000 Marta Serra Font')])
        workgroup = self.env['ems.workgroup'].create({
            'name': 'Comissió de qualitat (proves)', 'employee_ids': [(6, 0, members.ids)],
        })
        self._capture(
            self._form_url('ems.workgroup', workgroup), '.o_form_sheet', 'admin-workgroup-form.png',
            login='doc_shot_admin', wait_for=".o_field_widget[name='employee_ids'] .o_kanban_record",
        )

    def test_capture_batch4_facilities_import_schedules_survey(self):
        level, study, group, last_group, subjects = self._curriculum_fixture()

        # --- Space types: the ones EMS ships (a centre may have added its own) ---
        shipped = self.env['ir.model.data'].search([
            ('module', '=', 'ems'), ('model', '=', 'ems.space_type')]).mapped('res_id')
        types_action = self.env['ir.actions.act_window'].create({
            'name': "Tipus d'espai", 'res_model': 'ems.space_type', 'view_mode': 'list',
            'domain': [('id', 'in', shipped)],
        })
        self._capture(
            '/odoo/action-%d' % types_action.id, '.o_list_table', 'admin-space-types-list.png',
            login='doc_shot_admin', wait_for='.o_list_renderer .o_data_row',
        )

        # --- A classroom and the weekly schedule of the classes held in it ---
        space = self.env['ems.space'].create({
            'code': 'ADMB-A01', 'name': 'Aula 101 (proves)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        teacher = self._teacher('0000 Laia Prats Coll')
        teacher.resource_calendar_id.apply_schedule_changes([
            {'dayofweek': day, 'hour_from': start, 'hour_to': start + 1, 'day_period': 'morning',
             'subject_id': subject.id, 'group_ids': [group.id], 'space_id': space.id,
             'name': 'ADMB: %s' % subject.acronym}
            for day, start, subject in (('0', 8, subjects[0]), ('0', 9, subjects[1]),
                                        ('2', 8, subjects[1]), ('3', 10, subjects[0]))
        ])
        self._capture(
            self._form_url('ems.space', space), '.o_form_sheet', 'admin-space-schedule.png',
            login='doc_shot_admin', wait_for=".o_field_widget[name='schedule_attendance_ids']",
            max_height=610,
        )

        # --- A student's weekly schedule (Schedule tab), built from the same classes ---
        student = self._student('Nil Exemple Serra', group)
        # A student's schedule comes from their subject enrollments, not from the group alone.
        self.env['ems.enrollment'].create([{
            'student_id': student.id, 'group_id': group.id, 'subject_id': subject.id,
        } for subject in subjects])
        self._capture(
            self._form_url('res.partner', student), '.o_notebook', 'admin-student-schedule.png',
            login='doc_shot_admin', wait_for='.o_notebook',
            click=".o_notebook .nav-link[name='schedule']",
            wait_after=".o_field_widget[name='schedule_attendance_ids']",
            max_height=420,
        )

        # --- Importing grades from Esfera: the import window ---
        self._capture(
            '/odoo/action-ems.action_grade_import_wizard', '.modal-content', 'admin-grade-import.png',
            login='doc_shot_admin', wait_for='.modal-content .o_form_view',
        )

        # --- Surveys: a draft survey ---
        survey = self.env['ems.limesurvey_header'].create({
            'name': 'ENQ-ALUM-2026', 'title': "Enquesta de satisfacció de l'alumnat (proves)",
            'description': "Valoració del curs per part de l'alumnat de DAM",
            'target': 'students', 'study_ids': [(6, 0, study.ids)],
            'tsv_raw_text': "class\ttype/scale\tname\ttext\nS\t\tsat\tSatisfacció",
        })
        self._capture(
            self._form_url('ems.limesurvey_header', survey), '.o_form_sheet_bg', 'admin-survey-form.png',
            login='doc_shot_admin', wait_for=".o_field_widget[name='title']", max_height=460,
        )

    def test_capture_teacher_onboarding(self):
        # Step 1: the Teachers menu and the New button. Clipped just below the control panel, so
        # neither the real teachers' cards nor the per-department counts can show.
        self._capture(
            '/odoo/action-ems.action_employee_kanban', '.o_web_client', 'alta-professor-01-menu-nou.png',
            login='doc_shot_admin', wait_for='.o_control_panel .o-kanban-button-new', max_height=100,
            marks=[(".o_main_navbar a[data-menu-xmlid='ems.menu_teachers']", '1', 'right'),
                   ('.o_control_panel .o-kanban-button-new', '2', 'right')],
        )
        # Steps 2-3: the empty onboarding form - name, department, suggested Google username,
        # and the private email (required) under Manager on the main screen.
        new_url = '/odoo/action-ems.action_employee_kanban/new'
        self._capture(
            new_url, '.o_action_manager', 'alta-professor-02-dades-formulari.png',
            login='doc_shot_admin', wait_for="div[name='google_ws_login']", max_height=560,
            marks=[("div[name='name'] input", '1', 'center'),
                   ("div[name='department_id'] input", '2', 'center'),
                   ("div[name='google_ws_login'] input", '3', 'center')],
        )
        self._capture(
            new_url, '.o_action_manager', 'alta-professor-03-correu-privat.png',
            login='doc_shot_admin', wait_for="div[name='private_email'] input", max_height=560,
            marks=[("div[name='private_email'] input", '1', 'center')],
        )

    def test_capture_task_assignment(self):
        # Made-up assignees in place of whoever this box has on the list (rolled back).
        assignees = self.env['res.users'].browse([create_role_user(
            self, 'secretary', login, lang='ca_ES', name=name).id for login, name in (
            ('doc_shot_task_1', 'Secretaria Exemple'), ('doc_shot_task_2', 'Marta Soler Vila'))])
        self.env['mail.activity.type'].search([('ems_task_assignment', '=', True)]).write(
            {'ems_assignee_ids': [(6, 0, assignees.ids)]})
        self.admin_user.write({'groups_id': [(4, self.env.ref('ems.group_secretary_admin').id)]})
        self._capture(
            '/odoo/action-ems.action_task_assignment', '.o_web_client', 'Asignacio-de-tasques-01.png',
            login='doc_shot_admin', wait_for=".o_data_row td[name='ems_assignee_ids'] .badge",
            max_height=280,
            marks=[(".o_main_navbar [data-menu-xmlid='ems.menu_ems_configuration']", '1', 'right'),
                   (".o_data_row td[name='name']", '2', 'text-right'),
                   (".o_data_row td[name='ems_assignee_ids']", '3', 'text-right')],
        )


    def test_capture_working_schedules(self):
        # --- Fixtures. A made-up study ("INF") and classrooms ("E1"-"E3"): a clean install already
        # loads the centre's real groups (DAM1A...), and the wizard resolves group names by name. ---
        course = self.env.company.current_course_id
        level, study, group_1a = create_level_study_group(self, 'DOCWS', level={
            'acronym': 'CF', 'name': 'Formació professional',
        }, study={'code': 'DOCWS01', 'acronym': 'INF', 'name': "Informàtica (exemple)"},
            group={'acronym': 'A', 'course': 1})
        other_study = self.env['ems.study'].create({
            'code': 'DOCWS02', 'acronym': 'XEX', 'name': 'Xarxes (exemple)', 'level_id': level.id,
            'date': date(2024, 1, 1), 'deprecated': False,
        })
        room_1, room_2, room_3 = self.env['ems.space'].create([{
            'code': 'DOCWS-E%d' % n, 'name': 'Aula E%d' % n,
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        } for n in (1, 2, 3)])
        group_1a.space_id = room_1
        Group = self.env['ems.group']
        group_1b = Group.create({'course': 1, 'acronym': 'B', 'level_id': level.id, 'study_id': study.id,
                                 'space_id': room_2.id})
        group_1c = Group.create({'course': 1, 'acronym': 'C', 'level_id': level.id, 'study_id': study.id,
                                 'space_id': room_1.id})
        # No classroom: listed on "Resolve groups" as a group still missing one.
        group_2a = Group.create({'course': 2, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id})
        Subject = self.env['ems.subject']
        databases, programming = Subject.create([{
            'code': code, 'acronym': acronym, 'name': name, 'study_ids': [(6, 0, [study.id])],
        } for code, acronym, name in (('DOCWSBD', 'BD', 'Bases de dades'),
                                      ('DOCWSPRG', 'PRG', 'Programació'))])
        # Taught in another study only: a subject/group mismatch on "Resolve subjects".
        networks = Subject.create({'code': 'DOCWSXAR', 'acronym': 'XAR', 'name': 'Xarxes locals',
                                   'study_ids': [(6, 0, [other_study.id])]})
        Employee = self.env['hr.employee']
        laia, marc, pere = Employee.create([{
            'name': name, 'employee_type': 'teacher', 'work_email': email,
        } for name, email in (('0000 Laia Casas', 'laia.casas@example.com'),
                              ('0000 Marc Vidal', 'marc.vidal@example.com'),
                              ('0000 Pere Font', 'pere.font@example.com'))])

        # An already-active session of Pere's in room E1 on Monday 11:00, which the file's own
        # 11:00 class for Laia in INF1A (room E1 too) collides with: "Existing schedule conflicts".
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [pere.id])], 'subject_id': databases.id,
            'group_ids': [(6, 0, [group_1c.id])],
            'start_date': date(course.start, 9, 1), 'end_date': date(course.end, 6, 30),
        })
        existing = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '0',
            'start_time': 11.0, 'end_time': 12.0, 'space_id': room_1.id,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': pere.resource_calendar_id.id, 'name': 'BD: Bases de dades',
            'dayofweek': '0', 'hour_from': 11.0, 'hour_to': 12.0, 'day_period': 'morning',
            'group_ids': [group_1c.id], 'subject_id': databases.id, 'space_id': room_1.id,
            'attendance_schedule_id': existing.id,
        })

        def hour(start, subject, students):
            return ('<H name="1 %s"><Subject name="%s %s"/><Students name="%s"/></H>'
                    % (start, subject.code, subject.name, students))
        planner = (
            '<root>'
            '<T name="laia.casas@example.com Laia Casas"><D name="1 Monday">'
            + hour('08:00', databases, group_1a.name)
            # Matches no group by name: "Resolve groups".
            + hour('09:00', programming, 'INF 1r B')
            + hour('10:00', networks, group_2a.name)
            + hour('11:00', databases, group_1a.name)
            + '</D></T>'
            # Same room (E1) and time as Laia's 08:00 class: "File conflicts".
            '<T name="marc.vidal@example.com Marc Vidal"><D name="1 Monday">'
            + hour('08:00', programming, group_1c.name)
            # A following slot, so the 08:00 one ends at 09:00 like Laia's: an entry's end is the
            # next one's start, and a conflict needs the exact same times.
            + hour('09:00', programming, group_1c.name)
            + '</D></T>'
            # Neither is known yet: "Resolve teachers".
            '<T name="nou.docent@example.com Nou Docent"><D name="1 Monday">'
            '<H name="1 12:00"><NonTeaching name="G Guard"/></H></D></T>'
            '<T name="X1"><D name="2 Tuesday"><H name="1 08:00"><NonTeaching name="G Guard"/></H></D></T>'
            '</root>'
        )
        # A transient record is only readable by its creator: everything as the login user.
        admin_env = self.env(user=self.admin_user, context=dict(self.env.context, lang='ca_ES'))
        attachment = admin_env['ir.attachment'].create({
            'name': 'horaris_inf.xml', 'datas': base64.b64encode(planner.encode()),
        })
        wizard = admin_env['ems.working_schedules_import_wizard'].create({
            'attachment_ids': [(6, 0, attachment.ids)],
        })
        action = self.env['ir.actions.act_window'].create({
            'name': 'Importar dades del planificador (XML)',
            'res_model': 'ems.working_schedules_import_wizard', 'res_id': wizard.id,
            'view_mode': 'form', 'target': 'new', 'context': "{'dialog_size': 'extra-large'}",
        })

        def capture(filename, selector='.modal-content', **kwargs):
            wizard.flush_recordset()
            self._capture('/odoo/action-%d' % action.id, selector, filename,
                          login='doc_shot_admin', **{'wait_for': '.modal-content .o_form_view', **kwargs})

        capture('working-schedules-import-01-welcome.png',
                wait_for=".modal-content div[name='attachment_ids'] .o_attachment")
        wizard.action_continue()
        self.assertEqual(wizard.state, 'groups')
        capture('working-schedules-import-02-resolve-groups.png',
                wait_for=".modal-content div[name='space_line_ids'] .o_data_row")
        wizard.group_line_ids.group_id = group_1b
        capture('working-schedules-import-02b-resolve-groups-classroom.png',
                wait_for=".modal-content div[name='space_line_ids'] .o_data_row")
        wizard.space_line_ids.space_id = room_3
        wizard.action_continue()
        self.assertEqual(wizard.state, 'subjects')
        capture('working-schedules-import-03-resolve-subjects.png',
                wait_for=".modal-content div[name='subject_line_ids'] .o_data_row")
        wizard.subject_line_ids.subject_id = programming
        wizard.action_continue()
        self.assertEqual(wizard.state, 'teachers')
        capture('working-schedules-import-04-resolve-teachers.png',
                wait_for=".modal-content div[name='teacher_line_ids'] .o_data_row + .o_data_row")
        wizard.action_continue()
        self.assertEqual(wizard.state, 'internal_conflicts')
        wizard.internal_conflict_line_ids.write({
            'resolution': 'reassign_rooms', 'left_space_id': room_1.id, 'right_space_id': room_2.id,
        })
        capture('working-schedules-import-05-file-conflicts.png',
                wait_for=".modal-content div[name='internal_conflict_line_ids'] select")
        wizard.action_continue()
        self.assertEqual(wizard.state, 'db_conflicts')
        # Keeping the existing session: "New prevails" would already archive it on Continue.
        wizard.external_conflict_line_ids.resolution = 'prevail_right'
        capture('working-schedules-import-06-existing-schedule-conflicts.png',
                wait_for=".modal-content div[name='external_conflict_line_ids'] select")
        wizard.action_continue()
        self.assertEqual(wizard.state, 'summary')
        capture('working-schedules-import-07-overall-summary.png',
                wait_for=".modal-content div[name='overall_summary_html'] *")
        capture('working-schedules-import-07b-overall-summary-download.png', selector='#ems-clip',
                wait_for=".modal-content div[name='summary_file'] a",
                run=self._union_clip_js([".modal-content div[name='summary_file']",
                                         ".modal-content .modal-footer"]),
                wait_after='#ems-clip')

        # --- The teacher's Schedule tab: the same slot holding one subject until February and
        # another one from March (a mid-course handoff), as two cards on Monday. ---
        jordi = Employee.create({'name': '0000 Jordi Exemple', 'employee_type': 'teacher'})
        jordi.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
            'subject_id': subject.id, 'group_ids': [group_2a.id], 'space_id': room_3.id,
            'name': '%s: %s' % (subject.acronym, subject.name),
            'date_from': start, 'date_to': stop,
        } for subject, start, stop in (
            (databases, date(course.start, 9, 1), date(course.end, 2, 28)),
            (programming, date(course.end, 3, 1), date(course.end, 6, 30)),
        )])
        employee_action = self.env['ir.actions.act_window'].create({
            'name': 'Empleats', 'res_model': 'hr.employee', 'view_mode': 'form',
            'domain': [('id', '=', jordi.id)],
        })
        url = '/odoo/action-%d/%d' % (employee_action.id, jordi.id)
        grid = ".o_field_widget[name='schedule_attendance_ids']"
        self._capture(url, grid, 'working-schedules-midcourse-handoff.png', login='doc_shot_admin',
                      wait_for=".nav-link[name='schedule']", click=".nav-link[name='schedule']",
                      wait_after='.o_schedule_grid_entry + .o_schedule_grid_entry', max_height=140)
        # Only Monday's two filled cards: the framework's own blank slots fill the rest of the column.
        tag_cards = ("Array.from(document.querySelectorAll(\".o_schedule_grid_day_column[data-day='0']"
                     " .o_schedule_grid_card\")).filter(function (card) {"
                     " return card.querySelector('.o_schedule_grid_card_subject').value; })"
                     ".forEach(function (card, index) { card.id = 'ems-card-' + index; });")
        self._capture(url, '#ems-clip', 'working-schedules-edit-cards.png',
                      login='doc_shot_admin', wait_for=".nav-link[name='schedule']",
                      run=["document.querySelector(\".nav-link[name='schedule']\").click();",
                           "document.querySelector('.o_schedule_grid_toolbar button').click();",
                           tag_cards + self._union_clip_js(['#ems-card-0', '#ems-card-1'])],
                      wait_after=['.o_schedule_grid_toolbar button',
                                  '.o_schedule_grid_card_date', '#ems-clip'])
