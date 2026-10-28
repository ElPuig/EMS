# -*- coding: utf-8 -*-
"""Screenshots of the student card screens (issue #524) for the secretary, tutors and admin manuals
(docs/{en,ca,es}/{secretary,tutors,admin}/student-card.md). Same mechanism and same rules as
`test_docs_screenshots.py`: tagged '-standard' (never part of a normal run), fixtures made up inside
the test's own rolled-back transaction so no real person can appear, PNGs written to
/tmp/ems_doc_screenshots and copied into docs/assets/<role>/ by hand. Run it with:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsStudentCard' --stop-after-init -c /etc/odoo/odoo.conf"
"""

import base64
import json

from odoo.tests.common import HttpCase, tagged

from .common import (
    DocsScreenshotMixin, create_role_employee, create_role_user, draw_invented_centre_stamp,
    draw_invented_student_photo, next_student_id,
)


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsStudentCard(DocsScreenshotMixin, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Catalan: the manuals are read at this centre in Catalan first.
        cls.secretary = create_role_user(cls, 'secretary', 'doc_shot_card_secretary', lang='ca_ES',
                                         name='Secretaria', email='secretaria@example.com')
        create_role_employee(cls, cls.secretary, employee_type='asp', name='0000 Secretaria')
        cls.tutor_user = create_role_user(cls, 'tutor', 'doc_shot_card_tutor', lang='ca_ES',
                                          name='Marina Exemple', email='marina@example.com')
        tutor = create_role_employee(cls, cls.tutor_user, name='Marina Exemple')
        cls.admin_user = create_role_user(cls, 'academic_admin', 'doc_shot_card_admin', lang='ca_ES',
                                          name='Administrador EMS', email='admin.ems@example.com')
        cls.admin_user.write({'groups_id': [(4, cls.env.ref('ems.group_settings_admin').id)]})

        # The official CFGM level and one of its studies (catalog data, nobody's personal data), in
        # an invented group of invented students.
        cls.level = cls.env.ref('ems.level_cfgm')
        study = cls.env['ems.study'].search([('level_id', '=', cls.level.id)], limit=1)
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'Z', 'level_id': cls.level.id, 'study_id': study.id, 'tutor_id': tutor.id,
        })
        names = (('Aina', 'Prova Inventada'), ('Pau', 'Exemple Mostra'), ('Laia', 'Mostra Prova'), ('Nil', 'Inventat Exemple'))
        cls.students = cls.env['res.partner'].create([{
            'firstname': firstname, 'lastname': lastname, 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': cls.group.id,
            'document_id': f'0000000{index}T', 'birth_date': f'2009-0{index + 1}-1{index}',
            'image_1920': base64.b64encode(draw_invented_student_photo()),
        } for index, (firstname, lastname) in enumerate(names)])
        cls.env.company.ems_card_stamp = base64.b64encode(draw_invented_centre_stamp())

        # An action of its own, scoped to these fixtures: it is what guarantees no real record can
        # appear in the shot, rather than trusting a crop.
        cls.list_action = cls.env['ir.actions.act_window'].create({
            'name': 'Alumnat',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'view_id': cls.env.ref('ems.view_student_list').id,
            'domain': [('id', 'in', cls.students.ids)],
        })

    @staticmethod
    def _tag_js(selector, text, element_id):
        """JS giving the element matching `selector` whose text contains `text` an id, so it can be
        marked: a menu entry has no attribute of its own to select it by."""
        return ("(function () { Array.from(document.querySelectorAll(%s)).find(function (el) {"
                " return el.textContent.indexOf(%s) !== -1; }).id = %s; })()"
                % (json.dumps(selector), json.dumps(text), json.dumps(element_id)))

    HIDE_CHATTER = "(function () { var c = document.querySelector('.o-mail-Form-chatter'); if (c) { c.style.display = 'none'; } })()"

    def test_capture_student_card_screens(self):
        # Students list: two students selected, the cog menu open on "Imprimir carnet d'estudiant".
        self._capture(f'/odoo/action-{self.list_action.id}', '.o_action_manager', 'student-card-list.png',
                      login='doc_shot_card_secretary', wait_for='.o_data_row',
                      run=["document.querySelectorAll('.o_data_row .o_list_record_selector input')[0].click()",
                           "document.querySelectorAll('.o_data_row .o_list_record_selector input')[1].click()",
                           "document.querySelector('.o_cp_action_menus button:has(.fa-cog)').click()",
                           self._tag_js('.o-dropdown--menu .o_menu_item', "Imprimir carnet", 'ems-card-print')],
                      wait_after=['.o_list_selection_box', '.o_list_selection_box',
                                  '.o-dropdown--menu .o_menu_item', '#ems-card-print'],
                      max_height=430, marks=[('#ems-card-print', 1, 'right')])
        # A student's form, as their tutor: the Actions dropdown open.
        self._capture(f'/odoo/res.partner/{self.students[0].id}', '.o_action_manager', 'student-card-student-form.png',
                      login='doc_shot_card_tutor', wait_for='.o_ems_actions_toggle',
                      run=[self.HIDE_CHATTER, "document.querySelector('.o_ems_actions_toggle').click()"],
                      wait_after=['.o_form_view', '.o_ems_actions_menu button[name=action_print_student_card]'],
                      # Within the viewport: capturing beyond it resizes the page, which closes the dropdown.
                      max_height=420, beyond_viewport=False,
                      marks=[('.o_ems_actions_menu button[name=action_print_student_card]', 1, 'right')])
        # The tutor's group: its only action, so a plain header button.
        self._capture(f'/odoo/ems.group/{self.group.id}', '.o_action_manager', 'student-card-group-form.png',
                      login='doc_shot_card_tutor', wait_for='button[name=action_print_student_cards]',
                      run=self.HIDE_CHATTER, wait_after='.o_form_view',
                      max_height=330, marks=[('button[name=action_print_student_cards]', 1, 'right')])

    def test_capture_student_card_admin_screens(self):
        # Settings > EMS: only the stamp's own setting (the rest of the block names real people).
        self._capture('/odoo/action-base_setup.action_general_configuration', '#ems_card_stamp',
                      'student-card-stamp-settings.png', login='doc_shot_card_admin', wait_for='a.tab[data-key="ems"]',
                      run=['document.querySelector(\'a.tab[data-key="ems"]\').click()',
                           "document.querySelector('#ems_card_stamp').scrollIntoView({block: 'center'})"],
                      wait_after=['#ems_card_stamp', '#ems_card_stamp img'],
                      beyond_viewport=False)
        # A level's form: its colour on the card.
        self._capture(f'/odoo/ems.level/{self.level.id}', '.o_form_sheet', 'student-card-level-colour.png',
                      login='doc_shot_card_admin', wait_for='.o_field_widget[name=card_color]',
                      max_height=260, marks=[('label[for^=card_color]', 1, 'left')])
