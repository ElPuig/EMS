# -*- coding: utf-8 -*-
"""Regenerates the screenshots of the ex officio withdrawal manuals (issue #726): the tutors',
the secretariat's and the Head of Studies' / Direction's, each taken as that role.

Tagged '-standard' on purpose - see the NOTE in test_docs_screenshots.py. Run it by hand:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsExOfficioWithdrawal' --stop-after-init -c /etc/odoo/odoo.conf"

Writes PNGs to /tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR); copy them into
docs/assets/<role>/ by hand afterwards. Fictitious data only, created in the test's own
transaction.
"""
from datetime import date, datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import HttpCase, tagged

from odoo.addons.ems.models.contacts.ex_officio_withdrawal import STEP_CATALOG

from .common import (DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user,
                     mock_outgoing_email, next_student_id, shift_ems_clock)

ACTIONS_TOGGLE = '.o_form_view .o_form_statusbar .o_ems_actions_toggle'


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsExOfficioWithdrawal(DocsScreenshotMixin, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.today = shift_ems_clock(cls, weekdays=(0, 1, 2, 3, 4)).date()
        cls.Withdrawal = cls.env['ems.ex_officio_withdrawal']
        _level, cls.study, cls.group = create_level_study_group(cls, 'DOCBO', level={
            'name': 'Cicles formatius de grau mitjà', 'education_stage': 'post_compulsory',
        }, study={'code': 'DOCBO01', 'acronym': 'SMX', 'name': 'Sistemes microinformàtics i xarxes'},
            group={'acronym': 'A', 'course': 1})
        _level, cls.comp_study, cls.comp_group = create_level_study_group(cls, 'DOCBOC', level={
            'name': 'Cicles formatius de grau bàsic', 'education_stage': 'compulsory',
        }, study={'code': 'DOCBOC01', 'acronym': 'IMO', 'name': 'Informàtica d\'oficina'},
            group={'acronym': 'A', 'course': 1})
        cls.tutor_user = create_role_user(cls, 'tutor', 'doc_shot_bo_tutor', lang='ca_ES', name='Tutora Exemple')
        cls.tutor = create_role_employee(cls, cls.tutor_user, name='0000 Tutora Exemple')
        (cls.group | cls.comp_group).tutor_id = cls.tutor
        cls.secretary_user = create_role_user(cls, 'secretary', 'doc_shot_bo_secretary', lang='ca_ES',
                                              name='Secretaria Exemple')
        cls.director_user = create_role_user(cls, 'director', 'doc_shot_bo_director', lang='ca_ES',
                                             name='Directora Exemple')
        cls.coexistence_user = create_role_user(cls, 'coexistence', 'doc_shot_bo_coexistence', lang='ca_ES',
                                                name='Coordinador Convivència Exemple')
        create_role_employee(cls, cls.coexistence_user, name='0000 Coordinador Convivència Exemple',
                             role_ids=[(4, cls.env.ref('ems.role_coexistence').id)])
        cls.student = cls._student('Nil Exemple Serra', cls.group)
        cls.comp_student = cls._student('Aina Mostra Puig', cls.comp_group)
        cls.other_student = cls._student('Pau Prova Vidal', cls.group)
        cls.comp_student2 = cls._student('Joan Mostra Roca', cls.comp_group)

    @classmethod
    def _student(cls, name, group):
        return cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': group.id,
            'email': f"{name.split()[0].lower()}.exemple@example.com", 'lang': 'ca_ES',
        })

    def _url(self, case_file):
        action = self.env['ir.actions.act_window'].create({
            'name': "Baixes d'ofici", 'res_model': 'ems.ex_officio_withdrawal', 'view_mode': 'list,form',
            'domain': [('student_id', 'in', (self.student | self.comp_student | self.other_student
                                             | self.comp_student2).ids)],
        })
        return f'/odoo/action-{action.id}/{case_file.id}' if case_file else f'/odoo/action-{action.id}'

    def _case_at(self, student, code, origin='detected'):
        """A case file of `student` whose `code` step opens today, every earlier step done on its
        own day (so nothing is late)."""
        circuit = 'compulsory' if student.main_group_id == self.comp_group else 'post_compulsory'
        deadline = next(step[2] for step in STEP_CATALOG[circuit] if step[0] == code)
        first = self.today
        while self.Withdrawal.new({'first_absence_date': first, 'circuit': circuit})._ems_due_date(deadline) > self.today:
            first -= timedelta(days=1)
        case_file = self.Withdrawal.create({'student_id': student.id, 'first_absence_date': first, 'origin': origin})
        case_file.action_start()
        responsible = {'tutor': self.tutor_user, 'coexistence': self.coexistence_user,
                       'secretariat': self.secretary_user, 'direction': self.director_user}
        while case_file.current_step_id.code != code:
            step = case_file.current_step_id
            day = step.due_date
            # Done by its responsible, on its own day, so the history reads as a real one.
            with patch.object(type(self.env['ems.datetime_utils']), 'get_local_today', return_value=day), \
                    patch.object(fields.Datetime, 'now', return_value=datetime(day.year, day.month, day.day, 10)):
                pending = case_file.current_check_ids.filtered(lambda check: not check.done)
                pending.write({'done': True, 'date': day})
                pending.filtered(lambda check: check.code == 'phone').call_outcome = 'reached'
                case_file.with_user(responsible[step.responsible]).action_accept_step()
        self.Withdrawal._cron_ems_due_step_tasks()
        return case_file

    def _roll_call(self, student, day, status, hour):
        """One finished session of `student` on `day` with `status`."""
        if not getattr(self, '_template', None):
            subject = self.env['ems.subject'].create({
                'code': 'DOCBO001', 'acronym': 'XAR', 'name': 'Xarxes locals', 'study_ids': [(6, 0, self.study.ids)]})
            self._space = self.env['ems.space'].create({
                'code': 'DOCBO-A', 'name': 'Aula 21', 'space_type_id': self.env.ref('ems.space_type_classroom').id,
                'work_location_id': self.env.ref('ems.work_location_main').id})
            self._template = self.env['ems.attendance_template'].create({
                'teacher_ids': [(6, 0, self.tutor.ids)], 'study_ids': [(6, 0, self.study.ids)],
                'subject_id': subject.id, 'group_ids': [(6, 0, self.group.ids)],
                'start_date': date(2020, 1, 1), 'end_date': date(2045, 12, 31)})
            self.env.company.attendance_manual_justified = True
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': self._template.id, 'weekday': str(day.weekday()), 'start_time': hour,
            'end_time': hour + 1, 'space_id': self._space.id, 'student_ids': [(6, 0, student.ids)]})
        self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': day, 'mode': 'scheduled', 'session_teacher_id': self.tutor.id,
            'attendance_session_line_ids': [(0, 0, {
                'student_id': student.id, 'status_id': self.env.ref(f'ems.attendance_status_{status}').id})]})

    def test_capture_tutors(self):
        proposal = self.Withdrawal.create({'student_id': self.other_student.id, 'origin': 'detected',
                                           'first_absence_date': self.today - timedelta(days=7)})
        case_file = self._case_at(self.student, 'tutor_contact')
        self._capture(self._url(False), '.o_list_renderer', 'baixa-ofici-01-llista.png', login='doc_shot_bo_tutor',
                      wait_for='.o_list_renderer .o_data_row')
        # A proposal: the tutor starts it or dismisses it from Actions.
        self._capture(self._url(proposal), '.o_content', 'baixa-ofici-02-proposta.png', login='doc_shot_bo_tutor',
                      wait_for=ACTIONS_TOGGLE, click=ACTIONS_TOGGLE,
                      wait_after=".o_ems_actions_menu button[name='action_start']", max_height=420,
                      beyond_viewport=False)
        self._capture(self._url(case_file), "div[name='current_step']", 'baixa-ofici-03-pas-tutor.png',
                      login='doc_shot_bo_tutor', wait_for="div[name='current_step'] button[name='action_open_contact']")
        reached = "div[name='current_step'] button[name='action_open_contact']"
        self._capture(self._url(case_file), '.modal-content', 'baixa-ofici-04-trucada.png', login='doc_shot_bo_tutor',
                      wait_for=reached, click=reached, wait_after=".modal .o_field_widget[name='call_date']")
        # The roll-calls say otherwise: one attendance and one justified absence to review.
        first_day = case_file.first_absence_date + timedelta(days=1)
        while first_day.weekday() > 4:
            first_day += timedelta(days=1)
        self._roll_call(self.student, first_day, 'attended', 9.0)
        self._roll_call(self.student, first_day, 'justified', 11.0)
        case_file._ems_collect_reviews()
        self._capture(self._url(case_file), '#ems-clip', 'baixa-ofici-05-revisio.png', login='doc_shot_bo_tutor',
                      wait_for="div[name='justification_review']",
                      run=self._union_clip_js(["div[name='attendance_review']", "div[name='justification_review']"]),
                      wait_after='#ems-clip')

    def test_capture_secretary(self):
        warning = self._case_at(self.student, 'secretariat_warning')
        self._capture(self._url(warning), "div[name='current_step']", 'baixa-ofici-06-pas-secretaria.png',
                      login='doc_shot_bo_secretary', wait_for="div[name='current_step'] .o_field_widget[name='current_check_ids']")
        withdrawal = self._case_at(self.comp_student, 'withdrawal')
        with patch.object(type(self.env['ems.datetime_utils']), 'get_local_today', return_value=self.today):
            withdrawal.current_check_ids.write({'done': True, 'date': self.today})
        # Its only action, so the Actions dropdown shows it as a button of its own.
        self._capture(self._url(withdrawal), '.o_content', 'baixa-ofici-07-tramitar.png', login='doc_shot_bo_secretary',
                      wait_for=".o_form_statusbar button[name='action_open_withdrawal_wizard']", max_height=560)

    def test_capture_head_of_studies(self):
        approval = self._case_at(self.comp_student, 'direction_approval')
        self._capture(self._url(approval), "div[name='current_step']", 'baixa-ofici-08-direccio.png',
                      login='doc_shot_bo_director', wait_for="div[name='current_step'] button[name='action_print_case_file']")
        # Below the fold: scrolled into view, captured within the viewport.
        self._capture(self._url(approval), '.o_ems_withdrawal_history', 'baixa-ofici-09-historial.png',
                      login='doc_shot_bo_director', wait_for='.o_ems_withdrawal_history',
                      run=["document.querySelector('.o_ems_withdrawal_history').scrollIntoView()"],
                      wait_after=['.o_ems_withdrawal_history'], beyond_viewport=False)
        # The compulsory circuit's notice to Social Services: a text to copy, for Coexistence.
        social = self._case_at(self.comp_student2, 'social_services')
        self._capture(self._url(social), "div[name='current_step']", 'baixa-ofici-10-serveis-socials.png',
                      login='doc_shot_bo_coexistence', wait_for="div[name='current_step'] .o_field_widget[name='copy_text']")
