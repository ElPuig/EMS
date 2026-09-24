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

from odoo.tests.common import HttpCase, tagged

from .common import (
    DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user,
    mock_outgoing_email, next_student_id,
)


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
