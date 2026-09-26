# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Tutors user manuals.

Tagged '-standard' on purpose - see the NOTE in test_docs_screenshots.py for why. Run it by
hand when a documented screen changes its look:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsTutors' --stop-after-init -c /etc/odoo/odoo.conf"

One test method per manual (see docs/en/developers/shared/testing.md, "DocsScreenshotMixin"). Writes PNGs to
/tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR); copy them into docs/assets/tutors/
by hand afterwards. The academic-history manual reuses existing captures of the same screens
(teachers/secretary), so it has no method here.
"""
import json
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .common import (
    DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user,
    mock_outgoing_email, next_student_id,
)
from .test_contact_data_request import valid_dni


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsTutors(DocsScreenshotMixin, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Strikes e-mail the tutor and the family.
        mock_outgoing_email(cls)
        cls.tutor_user = create_role_user(cls, 'tutor', 'doc_shot_tutor', lang='ca_ES',
                                          name='Tutora Exemple', email='tutora@example.com')
        cls.tutor = create_role_employee(cls, cls.tutor_user, name='0000 Tutora Exemple')
        # The colleague who teaches the group: a tutor sees the strikes and the attendance of
        # their tutees whoever recorded them.
        cls.teacher = cls.env['hr.employee'].create({
            'name': '0000 Professor Exemple', 'employee_type': 'teacher',
        })
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'DOCTUT', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCTUT01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        cls.group.tutor_id = cls.tutor
        cls.other_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.env['hr.employee'].create({
                'name': '0000 Tutor Grup B', 'employee_type': 'teacher',
            }).id,
        })
        cls.student = cls._student('Nil Exemple Serra', email='nil.exemple@example.com')
        cls.classmate = cls._student('Aina Mostra Puig')

    @classmethod
    def _student(cls, name, **overrides):
        return cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
            **overrides,
        })

    def _student_url(self, student):
        # An action of our own, scoped to the fixture students, to open the form through.
        action = self.env['ir.actions.act_window'].create({
            'name': 'Alumnes', 'res_model': 'res.partner', 'view_mode': 'form',
            'domain': [('id', 'in', (self.student | self.classmate).ids)],
        })
        return '/odoo/action-%d/%d' % (action.id, student.id)

    def test_capture_attendance_reports(self):
        # The colleague's session, so the tutee's by-student report has a date range to fill in.
        subject = self.env['ems.subject'].create({
            'code': 'DOCTUTSUB', 'acronym': 'BD', 'name': 'Bases de dades',
            'study_ids': [(6, 0, [self.study.id])],
        })
        space = self.env['ems.space'].create({
            'code': 'DOCTUT-A', 'name': 'Aula Exemple',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, self.teacher.ids)], 'study_ids': [(6, 0, [self.study.id])],
            'subject_id': subject.id, 'group_ids': [(6, 0, [self.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '1',
            'start_time': 9.0, 'end_time': 10.0, 'space_id': space.id,
        })
        for day, status in ((2, 'ems.attendance_status_attended'), (9, 'ems.attendance_status_miss')):
            session = self.env['ems.attendance_session_header'].create({
                'attendance_schedule_id': schedule.id, 'date': datetime(2027, 3, day).date(),
                'mode': 'manual', 'session_teacher_id': self.teacher.id,
            })
            self.env['ems.attendance_session_line'].create({
                'student_id': self.student.id, 'status_id': self.env.ref(status).id,
                'attendance_session_id': session.id,
            })
        wizard_action = self.env['ir.actions.act_window'].create({
            'name': "Informe d'assistència",
            'res_model': 'ems.attendance_report_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_report_type': 'student', 'default_student_id': self.student.id},
        })
        self._capture(
            '/odoo/action-%d' % wizard_action.id,
            '.modal-content', 'tutor-informes-01-per-estudiant.png',
            login='doc_shot_tutor',
            wait_for=".modal-content .o_field_widget[name='student_id'] input",
        )

    def test_capture_change_student_group(self):
        # Two subjects enrolled through the current group: the ones the warning says will move.
        self.env['ems.enrollment'].create([{
            'student_id': self.student.id, 'group_id': self.group.id,
            'subject_id': self.env['ems.subject'].create({
                'code': code, 'acronym': acronym, 'name': name,
                'study_ids': [(6, 0, [self.study.id])],
            }).id,
        } for code, acronym, name in (
            ('DOCTUTGRP1', 'BD', 'Bases de dades'),
            ('DOCTUTGRP2', 'PRG', 'Programació'),
        )])
        # Type the destination group's name into Main group and pick it: the warning shows up
        # before saving.
        type_group = (
            "(function () { var input = document.querySelector(\"div[name='main_group_id'] input\");"
            " input.focus(); input.value = %s;"
            " input.dispatchEvent(new Event('input', {bubbles: true})); })();"
            % json.dumps(self.other_group.display_name)
        )
        pick_group = "document.querySelector('.o-autocomplete--dropdown-item a').click();"
        open_tab = "document.querySelector(\".o_notebook .nav-link[name='studies']\").click();"
        self._capture(
            self._student_url(self.student),
            '.o_notebook', 'canvi-grup-01-avis.png',
            login='doc_shot_tutor', wait_for='.o_notebook',
            run=[open_tab, type_group, pick_group],
            wait_after=[
                "div[name='main_group_id'] input",
                '.o-autocomplete--dropdown-item a',
                '.tab-pane.active .alert-warning',
            ],
        )

    def test_capture_family_contacts(self):
        mother = self.env['res.partner'].create({
            'name': 'Marta Serra Vila', 'contact_type': 'family',
            'email': 'marta.serra@example.com', 'mobile': '600 000 001',
        })
        father = self.env['res.partner'].create({
            'name': 'Pere Exemple Soler', 'contact_type': 'family',
            'email': 'pere.exemple@example.com', 'mobile': '600 000 002',
        })
        self.env['res.partner.relation'].create([{
            'left_partner_id': mother.id,
            'type_id': self.env.ref('ems.relation_type_mother').id,
            'right_partner_id': self.student.id,
        }, {
            'left_partner_id': father.id,
            'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': self.student.id,
        }])
        # res.partner.relation.all is a SQL view: flush so the tab sees the rows.
        self.env.flush_all()
        url = self._student_url(self.student)
        self._capture(
            url, '.o_notebook', 'contactes-familia-01-pestanya.png',
            login='doc_shot_tutor', wait_for='.o_notebook',
            click=".o_notebook .nav-link[name='contact_addresses']",
            wait_after=".o_field_widget[name='relation_all_ids'] .o_data_row + .o_data_row",
        )
        # With the relation dropdown open: an empty many2one draws no border until hovered, so
        # the shot would otherwise show the labels with nothing next to them.
        self._capture(
            url, '.modal-content', 'contactes-familia-02-afegir.png',
            login='doc_shot_tutor', wait_for='.o_notebook',
            run=["document.querySelector(\".o_notebook .nav-link[name='contact_addresses']\").click();",
                 "document.querySelector(\"button[name='action_open_relation_wizard']\").click();",
                 # Typed rather than just opened, so the short filtered list fits in the dialog.
                 "(function () { var input = document.querySelector("
                 "\".modal-content div[name='type_selection_id'] input\"); input.focus();"
                 " input.value = 'Mare'; input.dispatchEvent(new Event('input', {bubbles: true})); })();"],
            wait_after=["button[name='action_open_relation_wizard']",
                        ".modal-content div[name='type_selection_id'] input",
                        '.modal-content .o-autocomplete--dropdown-item'],
        )

    def test_capture_strike(self):
        strikes = self.env['ems.strike'].create([{
            'student_id': self.student.id, 'teacher_id': self.teacher.id,
            'reason_id': self.env.ref('ems.strike_reason_material').id,
            'date': datetime(2027, 3, 2, 9, 15),
            'notes': "No ha portat l'ordinador per tercera vegada.",
        }, {
            'student_id': self.student.id, 'teacher_id': self.teacher.id,
            'reason_id': self.env.ref('ems.strike_reason_behaviour').id,
            'date': datetime(2027, 3, 9, 11, 40), 'kicked_out': True,
        }, {
            'student_id': self.classmate.id, 'teacher_id': self.teacher.id,
            'reason_id': self.env.ref('ems.strike_reason_device_misuse').id,
            'date': datetime(2027, 3, 5, 12, 5),
        }])
        # The native list has no domain (record rules scope it): our own, scoped to the fixtures.
        list_action = self.env['ir.actions.act_window'].create({
            'name': 'Amonestacions', 'res_model': 'ems.strike', 'view_mode': 'list,form',
            'domain': [('id', 'in', strikes.ids)],
        })
        self._capture(
            '/odoo/action-%d' % list_action.id,
            '.o_list_table', 'amonestacions-01-llista.png',
            login='doc_shot_tutor', wait_for='.o_list_renderer .o_data_row + .o_data_row',
        )
        self._capture(
            self._student_url(self.student),
            '.o_action_manager', 'amonestacions-02-boto-fitxa.png',
            login='doc_shot_tutor', wait_for="button[name='action_view_strikes']",
            max_height=240,
        )

    def test_capture_enrollment_proposals(self):
        # Next year's group and a template for it, with the subjects it enrolls in.
        self.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'level_id': self.level.id, 'study_id': self.study.id,
        })
        subjects = self.env['ems.subject'].create([{
            'code': code, 'acronym': acronym, 'name': name, 'study_ids': [(6, 0, [self.study.id])],
        } for code, acronym, name in (
            ('DOCTUTPRO1', 'DI', "Desenvolupament d'interfícies"),
            ('DOCTUTPRO2', 'PMDM', 'Programació multimèdia i dispositius mòbils'),
            ('DOCTUTPRO3', 'SGE', "Sistemes de gestió empresarial"),
        )])
        template = self.env['sale.order.template'].create({
            'name': 'DAM-2', 'ems_study_id': self.study.id, 'study_year': 2,
            'sale_order_template_line_ids': [(0, 0, {'product_id': subject.product_id.id})
                                             for subject in subjects],
        })
        students = self.student | self.classmate | self.env['res.partner'].browse([
            self._student(name).id for name in ('Pol Exemple Casas', 'Júlia Mostra Font')])
        students.write({'study_id': self.study.id})
        url = '/odoo/action-ems.action_student_group_enrollment'

        # Step 1: select the approved students and click Enrollment proposal.
        self._capture(
            url, '.o_action_manager', 'propostes-01-llista-alumnes.png', login='doc_shot_tutor',
            max_height=300,
            wait_for='.o_data_row + .o_data_row + .o_data_row + .o_data_row',
            click=['.o_data_row:nth-child(1) .o_list_record_selector input',
                   '.o_data_row:nth-child(2) .o_list_record_selector input',
                   '.o_data_row:nth-child(4) .o_list_record_selector input'],
            wait_after=['.o_data_row.o_data_row_selected',
                        '.o_data_row.o_data_row_selected + .o_data_row.o_data_row_selected',
                        "button[name='action_enrollment_proposal']"],
            # (1) is the group in the left panel, as the manual's text says.
            marks=[('.o_search_panel .o_search_panel_category_value:last-child .o_search_panel_label_title', '1', 'right'),
                   ("button[name='action_enrollment_proposal']", '2', 'top')],
        )

        # Step 2: the proposal dialog, with the next-course template picked.
        # The same three ticked in step 1 (rows sort by name: Aina, Júlia, Nil, Pol).
        selected = self.classmate | students[2] | students[3]
        wizard_action = self.env['ir.actions.act_window'].create({
            'name': 'Proposta de matrícula', 'res_model': 'ems.enrollment_proposal_wizard',
            'view_mode': 'form', 'target': 'new',
            'context': {'active_ids': selected.ids, 'default_template_id': template.id},
        })
        self._capture(
            '/odoo/action-%d' % wizard_action.id, '.modal-content', 'propostes-02-dialeg-plantilla.png',
            login='doc_shot_tutor',
            wait_for=".modal-content .o_field_widget[name='student_ids'] .o_data_row + .o_data_row",
            marks=[(".modal-content div[name='template_id']", '1', 'top'),
                   ("button[name='action_create_enrollments']", '2', 'top')],
        )

        # The pre-enrollments created, as the tutor would have with that dialog.
        self.env['ems.enrollment_proposal_wizard'].with_user(self.tutor_user).with_context(
            active_ids=selected.ids).create({'template_id': template.id}).action_create_enrollments()
        self._capture(
            url, '.o_action_manager', 'propostes-03-llista-alumnes-pre-matricules-creades.png',
            login='doc_shot_tutor', max_height=300,
            wait_for=".o_data_row td[name='ems_current_enrollment_id']",
            marks=[(".o_data_row:nth-child(1) td[name='ems_current_enrollment_id']", '1', 'top')],
        )

        # Adjusting one pre-enrollment: remove (1) and add (2) subjects.
        order = self.env['sale.order'].search([('partner_id', '=', self.classmate.id),
                                               ('sale_order_template_id', '=', template.id)])
        order_action = self.env['ir.actions.act_window'].create({
            'name': 'Matrícula', 'res_model': 'sale.order', 'view_mode': 'form',
            'domain': [('id', '=', order.id)],
        })
        self._capture(
            '/odoo/action-%d/%d' % (order_action.id, order.id), '.o_form_sheet',
            'propostes-04-edicio_matricula.png', login='doc_shot_tutor',
            wait_for=".o_field_widget[name='order_line'] .o_data_row + .o_data_row",
            # EMS's own per-line delete button (views/academic_management/enrollment/enrollment_form.xml).
            marks=[(".o_field_widget[name='order_line'] .o_data_row button[name='unlink']", '1', 'right'),
                   (".o_field_widget[name='order_line'] .o_field_x2many_list_row_add a", '2', 'left')],
        )

    def test_capture_board_and_work_placement(self):
        # Two subjects with a work-placement (EM) share, graded by outcome in round 1 (open).
        subjects = self.env['ems.subject'].create([{
            'code': code, 'acronym': acronym, 'name': name, 'study_ids': [(6, 0, [self.study.id])],
        } for code, acronym, name in (('DOCTUTGR1', 'BD', 'Bases de dades'),
                                      ('DOCTUTGR2', 'PRG', 'Programació'))])
        for subject in subjects:
            outcomes = self.env['ems.outcome'].create([{
                'code': '%s_0%dRA' % (subject.code, n), 'acronym': 'RA%d' % n,
                'name': "Resultat d'aprenentatge %d" % n, 'subject_id': subject.id,
            } for n in (1, 2, 3)])
            self.env['ems.planning'].create({
                'study_id': self.study.id, 'subject_id': subject.id,
                'internal_ponderation': 90.0, 'external_ponderation': 10.0,
                'planning_outcome_ids': [(0, 0, {'outcome_id': outcome.id, 'ponderation': weight})
                                         for outcome, weight in zip(outcomes, (40.0, 30.0, 30.0))],
            })
        students = self.student | self.classmate | self.env['res.partner'].browse([
            self._student(name).id for name in ('Pol Exemple Casas', 'Júlia Mostra Font')])
        self.env['ems.enrollment'].create([{
            'student_id': student.id, 'group_id': self.group.id, 'subject_id': subject.id,
        } for student in students for subject in subjects])
        grades = {'BD': {'RA1': 7, 'RA2': 4}, 'PRG': {'RA1': 8, 'RA2': 6, 'RA3': 5}}
        for subject in subjects:
            session = self.env['ems.grade_session'].create({
                'group_id': self.group.id, 'subject_id': subject.id, 'round': '1',
                'teacher_id': self.teacher.id,
            })
            session.fill_students()
            for line in session.grade_outcome_line_ids:
                score = grades[subject.acronym].get(line.outcome_id.acronym)
                if score is not None:
                    line.write({'score': score, 'is_scored': True})

        section = ".o_main_navbar [data-menu-xmlid='ems.menu_grades']"
        # --- Evaluation for tutors ---
        self._capture(
            '/odoo/action-ems.action_grade_tutor_matrix', '.o_web_client', 'JuntaAvaluacio-tutors-01.png',
            login='doc_shot_tutor', wait_for='.o_grade_tutor_pager', max_height=110,
            marks=[(section, '1', 'right')],
        )
        self._capture(
            '/odoo/action-ems.action_grade_tutor_matrix', '.o_grade_matrix', 'JuntaAvaluacio-tutors-02.png',
            login='doc_shot_tutor', wait_for='.o_grade_tutor_scroll tbody tr',
            marks=[('.o_grade_tutor_scope', '1', 'left'),
                   ('.o_grade_tutor_count', '2', 'right'),
                   ('.o_grade_tutor_navbtn:last-of-type', '3', 'left')],
        )
        edit = ("(function () { var cell = document.querySelectorAll("
                "'.o_grade_tutor_scroll tbody tr:first-child td.o_grade_matrix_cell')[2];"
                " cell.dispatchEvent(new MouseEvent('dblclick', {bubbles: true})); })();")
        self._capture(
            '/odoo/action-ems.action_grade_tutor_matrix', '.o_grade_matrix', 'JuntaAvaluacio-tutors-03.png',
            login='doc_shot_tutor', wait_for='.o_grade_tutor_scroll tbody tr',
            run=edit, wait_after='input.o_grade_matrix_input',
            marks=[('input.o_grade_matrix_input', '1', 'right')],
        )

        # --- Work placement evaluation (EM) ---
        em_url = '/odoo/action-ems.action_em_grading_wizard'
        self._capture(
            em_url, '.o_web_client', 'Posar-Nota-EM-01.png', login='doc_shot_tutor',
            wait_for=".o_field_widget[name='group_id']", max_height=110,
            marks=[(section, '1', 'right')],
        )
        # A tutor picks the group straight away: only the ones they tutor are offered.
        self._capture(
            em_url, '.o_action_manager', 'Posar-Nota-EM-02-Tutor.png', login='doc_shot_tutor',
            wait_for=".o_field_widget[name='group_id'] input", max_height=380,
            click=".o_field_widget[name='group_id'] input", wait_after='.o-autocomplete--dropdown-item',
        )
        # The secretariat first narrows the groups down by study.
        create_role_user(self, 'secretary', 'doc_shot_tutor_sec', lang='ca_ES', name='Secretaria Exemple')
        type_study = ("(function () { var input = document.querySelector(\".o_field_widget[name='study_id'] input\");"
                      " input.focus(); input.value = 'Desenvolupament'; input.dispatchEvent(new Event('input', {bubbles: true})); })();")
        self._capture(
            em_url, '.o_action_manager', 'Posar-Nota-EM-03-AdminoSecretaria.png', login='doc_shot_tutor_sec',
            wait_for=".o_field_widget[name='study_id'] input", max_height=380,
            run=type_study, wait_after='.o-autocomplete--dropdown-item',
        )
        # The matrix of a group.
        matrix_action = self.env['ir.actions.act_window'].create({
            'name': "Avaluació de l'estada a l'empresa (EM)", 'res_model': 'ems.em_grading_wizard',
            'view_mode': 'form', 'target': 'current', 'context': {'default_group_id': self.group.id},
        })
        self._capture(
            '/odoo/action-%d' % matrix_action.id, '.o_form_sheet', 'Posar-Nota-EM-04.png',
            login='doc_shot_tutor', wait_for=".o_field_widget[name='student_line_ids'] tbody tr",
        )

    def test_capture_portal_access(self):
        # Each tutee has a family member with an e-mail, so the dialog has recipients to preview.
        for student, (name, email) in zip(self.student | self.classmate,
                                          (('Marta Serra Vila', 'marta.serra@example.com'),
                                           ('Jordi Puig Soler', 'jordi.puig@example.com'))):
            family = self.env['res.partner'].create({'name': name, 'contact_type': 'family', 'email': email})
            self.env['res.partner.relation'].create({
                'left_partner_id': family.id, 'type_id': self.env.ref('ems.relation_type_mother').id,
                'right_partner_id': student.id,
            })
        self.env.flush_all()
        tutees = self.student | self.classmate
        # The native Students screen, scoped to the tutees for this (rolled-back) test.
        self.env.ref('ems.action_student_kanban').domain = str([('id', 'in', tutees.ids)])
        tag_portal = ("(function () { var el = Array.from(document.querySelectorAll('.o-dropdown--menu .dropdown-item'))"
                      ".find(function (e) { return e.textContent.indexOf('portal') !== -1; });"
                      " if (el) { el.id = 'ems-mark-portal'; } })();")
        self._capture(
            '/odoo/action-ems.action_student_kanban?view_type=list', '.o_action_manager',
            'tutor-accesalportal0.png', login='doc_shot_tutor', wait_for='.o_data_row + .o_data_row',
            max_height=420,
            run=["document.querySelector('thead .o_list_record_selector input').click();",
                 "document.querySelector('.o_control_panel .o_cp_action_menus button:has(.fa-cog)').click();",
                 tag_portal],
            wait_after=['.o_data_row.o_data_row_selected + .o_data_row.o_data_row_selected',
                        '.o-dropdown--menu .dropdown-item', '#ems-mark-portal'],
            marks=[('.o_search_panel .o_search_panel_category_value:last-child .o_search_panel_label_title', '1', 'right'),
                   ('thead .o_list_record_selector', '2', 'right'),
                   ('#ems-mark-portal', '3', 'right')],
        )
        wizard_action = self.env['ir.actions.act_window'].create({
            'name': 'Accés al portal', 'res_model': 'ems.portal.access.wizard', 'view_mode': 'form',
            'target': 'new', 'context': {'active_ids': tutees.ids, 'active_model': 'res.partner'},
        })
        self._capture(
            '/odoo/action-%d' % wizard_action.id, '.modal-content', 'tutor-accesalportal1.png',
            login='doc_shot_tutor', wait_for=".modal-content .o_field_widget[name='line_ids'] .o_data_row",
            marks=[(".modal-content div[name='mode']", '1', 'text-right'),
                   (".modal-content button[name='action_apply']", '2', 'top')],
        )

    def test_capture_contact_data_requests(self):
        """contact-data-requests (issue #507): the menu, the send assistant, the follow-up list and
        an answer to review, as the group's tutor - all on three invented students."""
        course = self.env['res.partner']._ems_running_course() \
            or self.env['ems.course'].create({'start': 2096, 'end': 2097, 'is_current': True})
        mother, father = self.env.ref('ems.relation_type_mother'), self.env.ref('ems.relation_type_father')
        minor_age = date.today() - relativedelta(years=15)
        bruna = self._student('Bruna Prova Vidal', email='bruna.prova@example.com',
                              street="Carrer de l'Exemple 3", zip='08921', city='Santa Coloma de Gramenet',
                              document_id=valid_dni(10000102))
        pupils = self.student | self.classmate | bruna
        pupils.write({'birth_date': minor_age})
        # The assistant asks the students enrolled in the group's course.
        self.env['sale.order'].create([{
            'partner_id': pupil.id, 'ems_study_id': self.study.id, 'ems_course_id': course.id,
        } for pupil in pupils])
        mothers = []
        for pupil, (firstname, lastname, mobile) in zip(pupils, (
                ('Marta', 'Serra Puig', '+34 600 000 011'),
                ('Núria', 'Puig Ribas', '+34 600 000 012'),
                ('Anna', 'Vidal Soler', '+34 600 000 013'))):
            contact = self.env['res.partner'].create({
                'firstname': firstname, 'lastname': lastname, 'contact_type': 'family', 'mobile': mobile,
                'email': '%s.%s@example.com' % (firstname.lower().replace('ú', 'u'), lastname.split()[0].lower()),
            })
            self.env['res.partner.relation'].create({
                'left_partner_id': contact.id, 'type_id': mother.id, 'right_partner_id': pupil.id})
            mothers.append(contact)
        self.env.flush_all()
        login = 'doc_shot_tutor'

        # The assistant on the tutor's group, before anything is sent: what is missing and who is emailed.
        wizard_action = self.env['ir.actions.act_window'].create({
            'name': 'Sol·licita dades de contacte', 'res_model': 'ems.contact.data.request.send.wizard',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_target': 'scope', 'default_group_ids': [(6, 0, self.group.ids)],
                        'default_course_id': course.id, 'default_only_incomplete': False},
        })
        # Opening the form builds no preview: ticking "only incomplete" (its default) does.
        only_incomplete = ".modal-content div[name='only_incomplete'] input"
        self._capture(
            '/odoo/action-%d' % wizard_action.id, '.modal-content', 'dades-contacte-02-assistent.png',
            login=login, wait_for=only_incomplete, click=only_incomplete,
            wait_after=".modal-content div[name='line_ids'] .o_data_row",
        )

        # One request of every state: still waiting, answered (a new address and document, a new
        # mobile for the mother, and a father added) and confirmed as it was.
        # Sent in Catalan, as this centre's tutor would: what was missing is stored in the sender's language.
        Request = self.env['ems.contact.data.request'].with_context(lang='ca_ES')
        now = datetime.now()
        pending = Request._ems_open_for(self.student, course)
        pending._ems_mark_sent()
        answered = Request._ems_open_for(self.classmate, course)
        answered._ems_mark_sent()
        data = self.classmate._ems_contact_data()
        data['student'].update(street="Carrer de l'Exemple 12", zip='08921', city='Santa Coloma de Gramenet',
                               document_id=valid_dni(10000101))
        data['family'][0]['mobile'] = '+34 600 000 112'
        data['family'].append({
            'key': 'n0', 'id': False, 'remove': False, 'relation_type_id': father.id, 'firstname': 'Jordi',
            'lastname': 'Mostra Ribas', 'mobile': '+34 600 000 113', 'email': 'jordi.mostra@example.com'})
        # The mother answered from her own portal account. Creating the user re-splits her name.
        mother_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': mothers[1].name, 'login': 'doc_shot_mother_aina', 'password': 'doc_shot_mother_aina',
            'lang': 'ca_ES', 'partner_id': mothers[1].id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        mothers[1].write({'firstname': 'Núria', 'lastname': 'Puig Ribas'})
        answered.with_user(mother_user).sudo()._ems_submit(data)
        confirmed = Request._ems_open_for(bruna, course)
        confirmed._ems_mark_sent()
        confirmed._ems_submit(bruna._ems_contact_data())
        # Spread over the last days, so the list and the form read like a real follow-up.
        pending.write({'sent_date': now - relativedelta(days=8)})
        answered.write({'sent_date': now - relativedelta(days=3), 'submitted_date': now - relativedelta(days=1)})
        confirmed.write({'sent_date': now - relativedelta(days=5), 'submitted_date': now - relativedelta(days=4)})

        # The real follow-up action, scoped to these students for this (rolled-back) test.
        self.env.ref('ems.action_ems_contact_data_request').domain = str([('student_id', 'in', pupils.ids)])
        action_url = '/odoo/action-ems.action_ems_contact_data_request'
        students_section = ".o_menu_sections button[data-menu-xmlid='ems.menu_students_root']"
        student_data = ".o-dropdown--menu .dropdown-item[data-menu-xmlid='ems.menu_contact_data_requests']"
        self._capture(
            # Opened once the list has loaded: the navbar redraws then, and would close the dropdown.
            action_url, '.o_web_client', 'dades-contacte-01-menu.png', login=login,
            wait_for='.o_list_renderer .o_data_row', max_height=230, beyond_viewport=False,
            click='mouse:' + students_section, wait_after=student_data,
            marks=[(students_section, '1', 'top'), (student_data, '2', 'text-right')],
        )
        self._capture(
            action_url, '.o_action_manager', 'dades-contacte-03-seguiment.png', login=login,
            wait_for='.o_list_renderer .o_data_row + .o_data_row + .o_data_row',
        )
        self._capture(
            '%s/%d' % (action_url, answered.id), '.o_form_view', 'dades-contacte-04-revisio.png',
            login=login, wait_for='.o_form_view .o_statusbar_status',
            marks=[(".o_form_statusbar button[name='action_approve']", '1', 'top'),
                   (".o_form_statusbar button[name='action_open_reject_wizard']", '2', 'top')],
        )
