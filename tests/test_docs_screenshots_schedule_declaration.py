# -*- coding: utf-8 -*-
"""Screenshots of the official schedule declaration (issue #723) for the Head of Studies,
administrator and teacher manuals. Same mechanism and rules as tests/test_docs_screenshots.py
(invented data in a rolled-back transaction, Catalan, the audience's own role); run by hand:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsScheduleDeclaration' --stop-after-init -c /etc/odoo/odoo.conf"

and copy the PNGs from /tmp/ems_doc_screenshots into docs/assets/ by hand.
"""
from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsScheduleDeclaration(HttpCase, DocsScreenshotMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hos_user = create_role_user(cls, 'head_of_studies', 'doc_shot_sd_hos', lang='ca_ES',
                                        name='Cap Estudis', email='cap.estudis@example.com')
        create_role_employee(cls, cls.hos_user, name='0000 Cap Estudis')
        cls.admin_user = create_role_user(cls, 'academic_admin', 'doc_shot_sd_admin', lang='ca_ES',
                                          name='Administració', email='admin@example.com')

        cls.level, study, cls.group_a = create_level_study_group(cls, 'DOCSD', level={
            'name': 'Secundària (exemple)', 'declaration_code': 'eso',
        }, study={'code': 'DOCSD01', 'acronym': 'ESX', 'name': 'Secundària obligatòria (exemple)'},
            group={'acronym': 'A', 'course': 1})
        cls.group_b = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': study.id,
        })
        # Its own framework, so the breaks shown are only this level's (10:00-10:25), not those of
        # every framework of the database (hr.employee._get_derived_break_entries).
        cls.env['resource.calendar'].create({
            'name': 'Marc Secundària (exemple)', 'is_framework': True, 'level_id': cls.level.id,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'name': 'Pati', 'dayofweek': day, 'hour_from': 10, 'hour_to': 10 + 25 / 60, 'day_period': 'morning',
                'non_teaching': cls.env.ref('ems.non_teaching_br').id,
            }) for day in '01234'],
        })
        Subject = cls.env['ems.subject']
        cls.math = Subject.create({'code': 'DOCSDMAT', 'acronym': 'MAT1', 'name': 'Matemàtiques (1r)',
                                   'study_ids': [(6, 0, study.ids)]})
        cls.science = Subject.create({'code': 'DOCSDCIE', 'acronym': 'CIE1', 'name': 'Ciències (1r)',
                                      'study_ids': [(6, 0, study.ids)]})
        cls.tutorship = Subject.create({'code': 'DOCSDTUT', 'acronym': 'TUT1', 'name': 'Tutoria (1r)',
                                        'study_ids': [(6, 0, study.ids)], 'is_tutorship': True})

        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Marta Exemple Prova', 'employee_type': 'teacher', 'identification_id': '00000000T',
        })
        cls.group_a.tutor_id = cls.teacher  # makes her a tutor, as her role says
        calendar = cls.env['resource.calendar'].create({
            'name': 'Marta Exemple Prova (exemple)', 'employee_id': cls.teacher.id, 'attendance_ids': [(5, 0, 0)],
        })
        cls.teacher.resource_calendar_id = calendar
        # A whole week: 18 lective hours (17 classes and the tutorship) and 6 fixed ones (three
        # guards, a break guard and the two Wednesday coordination meetings).
        nt = {code: cls.env.ref(f'ems.non_teaching_{code}') for code in ('g', 'gb', 'br', 'cm')}
        cls.env['ems.non_teaching_type']._ems_seed_declaration_codes()
        periods = [(8, 9), (9, 10), (10, 10 + 25 / 60), (10 + 25 / 60, 11 + 25 / 60), (11 + 25 / 60, 12 + 25 / 60),
                   (12 + 25 / 60, 13 + 25 / 60)]
        week = {
            '0': [cls.math, cls.science, 'gb', cls.math, 'g', cls.science],
            '1': [cls.science, cls.math, 'br', cls.tutorship, cls.math, None],
            '2': [cls.math, 'g', 'br', cls.science, cls.math, cls.science],
            '3': [None, cls.science, 'br', cls.math, cls.science, 'g'],
            '4': [cls.math, cls.science, 'br', None, cls.math, None],
        }
        entries = []
        for dayofweek, blocks in week.items():
            for index, ((hour_from, hour_to), block) in enumerate(zip(periods, blocks)):
                if block is None:
                    continue
                vals = {'dayofweek': dayofweek, 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
                        'name': 'DOCSD'}
                if isinstance(block, str):
                    vals['non_teaching'] = nt[block].id
                else:
                    vals.update(subject_id=block.id, group_ids=[(cls.group_a if index % 2 else cls.group_b).id])
                entries.append(vals)
        for hour_from in (15 + 40 / 60, 16 + 40 / 60):
            entries.append({'dayofweek': '2', 'hour_from': hour_from, 'hour_to': hour_from + 1,
                            'day_period': 'afternoon', 'non_teaching': nt['cm'].id, 'name': 'DOCSD'})
        calendar.apply_schedule_changes(entries)
        cls.colleague = cls.env['hr.employee'].create({'name': 'Joan Exemple Model', 'employee_type': 'teacher'})
        cls.teachers_action = cls.env['ir.actions.act_window'].create({
            'name': 'Professors', 'res_model': 'hr.employee', 'view_mode': 'list,form',
            'domain': [('id', 'in', (cls.teacher | cls.colleague).ids)],
        })

    def test_capture_schedule_declaration(self):
        summary = self.teacher.resource_calendar_id.get_schedule_declaration_summary()
        self.assertEqual((summary['lective_total'], summary['fixed_total']), (18, 6))

        # Head of Studies: several teachers from the list's Print menu...
        self._capture(
            '/odoo/action-%d' % self.teachers_action.id, '#ems-clip', 'hos-declaracio-horaria-llista.png',
            login='doc_shot_sd_hos', wait_for='.o_list_view .o_data_row', max_height=230,
            run=["document.querySelector('.o_list_view thead .o_list_record_selector input').click()",
                 "document.querySelector('.o_control_panel .o_cp_action_menus button:has(.fa-print)').click()",
                 self._union_clip_js(['.o_control_panel', '.o_list_view', '.o-dropdown--menu'])],
            wait_after=['.o_control_panel .o_cp_action_menus button:has(.fa-print)', '.o-dropdown--menu', '#ems-clip'],
        )
        # ...or one from the form's Actions dropdown.
        self._capture(
            '/odoo/action-%d/%d' % (self.teachers_action.id, self.teacher.id), '#ems-clip',
            'hos-declaracio-horaria-accions.png', login='doc_shot_sd_hos',
            wait_for='.o_form_statusbar .o_ems_actions_toggle',
            run=["document.querySelector('.o_form_statusbar .o_ems_actions_toggle').click()",
                 self._union_clip_js(['.o_form_statusbar', '.o_ems_actions_menu'])],
            wait_after=['.o_ems_actions_menu', '#ems-clip'],
            # Odoo closes an open dropdown when the page is resized, as capturing beyond the viewport does.
            beyond_viewport=False,
        )
        # The declaration itself, as printed (the report's HTML, the same page wkhtmltopdf prints).
        self._capture(
            '/report/html/ems.report_schedule_declaration/%d' % self.teacher.id, '.page',
            'declaracio-horaria-mostra.png', login='doc_shot_sd_hos', wait_for='.sd-summary',
        )

    def test_capture_declaration_codes(self):
        # Administrator: the codes on a non-teaching type and on a level.
        self._capture(
            '/odoo/action-ems.action_non_teaching_type_list/%d' % self.env.ref('ems.non_teaching_gb').id, '.o_form_sheet',
            'admin-declaracio-horaria-tipus-no-lectiu.png', login='doc_shot_sd_admin',
            wait_for=".o_field_widget[name='declaration_code']",
        )
        self._capture(
            '/odoo/action-ems.level_action/%d' % self.level.id, '.o_form_sheet .o_group', 'admin-declaracio-horaria-nivell.png',
            login='doc_shot_sd_admin', wait_for=".o_field_widget[name='declaration_code']",
        )
