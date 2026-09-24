# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Secretariat user manuals.

Tagged '-standard' on purpose - see the NOTE in test_docs_screenshots.py for why. Run it by
hand when a documented screen changes its look:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsSecretary' --stop-after-init -c /etc/odoo/odoo.conf"

One test method per manual (see docs/en/developers/shared/testing.md, "DocsScreenshotMixin"). Writes PNGs to
/tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR); copy them into
docs/assets/secretary/ by hand afterwards. The absences and attendance-reports manuals, and the
family-contacts part of student-contacts, reuse existing captures of the same screens (Head of
Studies, teachers, tutors), so they have no method here.
"""
import base64
import io
import json
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .common import (
    DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user,
    mock_outgoing_email, next_student_id,
)

FAKE_PDF = base64.b64encode(b'%PDF-1.4 x')


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsSecretary(DocsScreenshotMixin, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.secretary_user = create_role_user(cls, 'secretary', 'doc_shot_secretary', lang='ca_ES',
                                              name='Secretaria Exemple', email='secretaria@example.com')
        create_role_employee(cls, cls.secretary_user, employee_type='asp',
                             name='0000 Secretaria Exemple')
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'DOCSEC', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOCSEC01', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        # A second-year group, so the study has a last course to graduate from.
        cls.last_group = cls.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })

    @classmethod
    def _student(cls, name, group=None, **overrides):
        return cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': (group or cls.group).id,
            'email': '%s@example.com' % name.split()[0].lower(),
            'birth_date': date.today() - relativedelta(years=19),
            **overrides,
        })

    def _wizard_url(self, model, name, context=None, res_id=None):
        action = self.env['ir.actions.act_window'].create({
            'name': name, 'res_model': model, 'view_mode': 'form', 'target': 'new',
            'context': context or {}, 'res_id': res_id or False,
        })
        return '/odoo/action-%d' % action.id

    def test_capture_graduation_withdrawal(self):
        graduating = self._student('Júlia Exemple Font', group=self.last_group)
        first_year = self._student('Marc Mostra Riera')
        self._capture(
            self._wizard_url('ems.graduation_wizard', 'Graduació',
                             {'active_ids': (graduating | first_year).ids}),
            '.modal-content', 'graduacio-01-assistent.png', login='doc_shot_secretary',
            wait_for=".modal-content .o_field_widget[name='line_ids'] .o_data_row + .o_data_row",
        )

        leaving = self._student('Pol Exemple Casas')
        # A not-yet-confirmed enrollment, which the wizard warns it will cancel.
        course = self.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1) \
            or self.env['ems.course'].create({'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        self.env['sale.order'].create({'partner_id': leaving.id, 'ems_course_id': course.id})
        self._capture(
            self._wizard_url('ems.withdrawal_wizard', 'Baixa', {'active_ids': leaving.ids}),
            '.modal-content', 'baixa-01-assistent.png', login='doc_shot_secretary',
            wait_for=".modal-content .o_field_widget[name='line_ids'] .o_data_row",
        )

    def test_capture_student_contacts(self):
        student = self._student('Nil Exemple Serra')
        self.env['ems.student.benefit'].create([{
            'student_id': student.id, 'benefit_type': 'large_family_gen',
            'document': FAKE_PDF, 'document_name': 'titol_familia_nombrosa.pdf',
            'renewal_date': date.today() + relativedelta(years=2),
        }, {
            'student_id': student.id, 'benefit_type': 'scholarship',
            'document': FAKE_PDF, 'document_name': 'beca_ministeri.pdf',
            'renewal_date': date.today() + relativedelta(months=9),
        }])
        action = self.env['ir.actions.act_window'].create({
            'name': 'Alumnes', 'res_model': 'res.partner', 'view_mode': 'form',
            'domain': [('id', '=', student.id)],
        })
        self._capture(
            '/odoo/action-%d/%d' % (action.id, student.id),
            '.o_notebook', 'contactes-01-bonificacions.png', login='doc_shot_secretary',
            wait_for='.o_notebook',
            click=".o_notebook .nav-link[name='secretary']",
            wait_after=".o_field_widget[name='benefit_ids'] .o_data_row + .o_data_row",
        )

    def test_capture_student_documents(self):
        first = self._student('Laia Exemple Soler')
        second = self._student('Aina Mostra Puig')
        Document = self.env['ems.student.document']
        documents = Document.create([
            {'partner_id': first.id, 'doc_type': 'iban', 'doc_value': 'ES9121000418450200051332',
             'doc_value2': 'Marta Soler Vila'},
            {'partner_id': first.id, 'doc_type': 'benefit', 'benefit_type': 'large_family_gen',
             'doc_file': FAKE_PDF, 'doc_file_name': 'titol_familia_nombrosa.pdf'},
            {'partner_id': second.id, 'doc_type': 'dni', 'doc_file': FAKE_PDF,
             'doc_file_name': 'dni.pdf', 'expiry_date': date.today() + relativedelta(years=5)},
        ])
        # Already reviewed: hidden by the default Pending filter, as the manual explains.
        approved = Document.create({'partner_id': second.id, 'doc_type': 'medical',
                                    'doc_file': FAKE_PDF, 'doc_file_name': 'tis.pdf'})
        approved.action_approve()
        # The native action has no domain: our own, scoped to the fixtures, same default filter.
        action = self.env['ir.actions.act_window'].create({
            'name': "Documents de l'alumnat", 'res_model': 'ems.student.document',
            'view_mode': 'list,form', 'context': {'search_default_pending': 1},
            'domain': [('id', 'in', (documents | approved).ids)],
        })
        self._capture(
            '/odoo/action-%d' % action.id,
            '.o_list_table', 'documents-01-pendents.png', login='doc_shot_secretary',
            wait_for='.o_list_renderer .o_data_row + .o_data_row + .o_data_row',
        )
        self._capture(
            '/odoo/action-%d/%d' % (action.id, documents[0].id),
            '.o_form_sheet_bg', 'documents-02-revisio.png', login='doc_shot_secretary',
            wait_for="button[name='action_approve']",
        )

    def test_capture_student_import_esfera(self):
        self._capture(
            '/odoo/action-ems.action_student_import_wizard',
            '.modal-content', 'esfera-01-assistent.png', login='doc_shot_secretary',
            wait_for=".modal-content .o_field_widget[name='file']",
        )

    def test_capture_student_update_csv(self):
        header = 'idalu,nom,telefon,correu,iban,titular\n'
        row = '1234567,Nil Exemple Serra,930000001,nil@example.com,ES9121000418450200051332,Marta Serra Vila\n'
        # Created as the secretary: a transient record is only readable by whoever created it.
        wizard = self.env['ems.student_update_wizard'].with_user(self.secretary_user).create({
            'file': base64.b64encode((header + row).encode()), 'file_name': 'alumnes.csv',
        })
        wizard.action_load_columns()
        columns = {column.name: column for column in wizard.env['ems.csv_column'].search(
            [('wizard_id', '=', wizard.id)])}
        wizard.write({
            'col_student_id': columns['idalu'].id, 'col_name': columns['nom'].id,
            'col_phone': columns['telefon'].id, 'col_email': columns['correu'].id,
            'col_iban': columns['iban'].id, 'col_acc_holder': columns['titular'].id,
        })
        self._capture(
            self._wizard_url('ems.student_update_wizard', 'Actualitzar alumnes des de CSV',
                             res_id=wizard.id),
            '.modal-content', 'actualitzacio-csv-01-columnes.png', login='doc_shot_secretary',
            wait_for=".modal-content .o_field_widget[name='col_student_id']",
        )

    @staticmethod
    def _tag(selector, text, element_id):
        """JS that gives the first `selector` element whose text contains `text` an id, so a
        mark (or a click) can target a dropdown entry that has no stable attribute of its own."""
        return ("(function () { var el = Array.from(document.querySelectorAll(%s)).find("
                "function (e) { return e.textContent.indexOf(%s) !== -1; }); if (el) { el.id = %s; } })();"
                % (json.dumps(selector), json.dumps(text), json.dumps(element_id)))

    @staticmethod
    def _js_click(selector):
        return "document.querySelector(%s).click();" % json.dumps(selector)

    def _gedac_xlsx(self, rows):
        import openpyxl
        headers = ['Nom', 'Primer cognom', 'Segon cognom', 'Ident. RALC', 'Telèfon',
                   'Correu electrònic', 'Curs', 'Centre assignat', 'Codi ensenyament assignat',
                   'Nom ensenyament assignat', 'Torn assignat']
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(headers)
        for row in rows:
            sheet.append([row.get(header) for header in headers])
        buffer = io.BytesIO()
        workbook.save(buffer)
        return base64.b64encode(buffer.getvalue())

    def test_capture_preinscription(self):
        # --- Fixtures: a made-up study GEDAC can resolve ('CFPM    DOCSMX' -> tail DOCSMX) ---
        self.env.company.center_code = '8028047'
        level, study, group = create_level_study_group(self, 'DOCPRE', level={
            'name': 'Cicles formatius (proves)',
        }, study={
            'code': 'CFGM_DOCSMX', 'acronym': 'SMXP', 'name': 'Sistemes microinformàtics i xarxes (proves)',
        }, group={'acronym': 'A', 'course': 1})
        subjects = self.env['ems.subject'].create([{
            'code': code, 'acronym': acronym, 'name': name, 'study_ids': [(6, 0, [study.id])],
        } for code, acronym, name in (('DOCPRE1', 'MME', "Muntatge i manteniment d'equips"),
                                      ('DOCPRE2', 'XL', 'Xarxes locals'))])
        template = self.env['sale.order.template'].create({
            'name': 'SMXP-1', 'ems_study_id': study.id, 'study_year': 1,
            'sale_order_template_line_ids': [(0, 0, {'product_id': subject.product_id.id}) for subject in subjects],
        })

        # --- GEDAC import, run as the secretary (a transient record is only readable by its
        # creator) so its result screen can be opened afterwards ---
        people = [('Laia', 'Puig', 'Roca', 'Matí', 1), ('Marc', 'Vidal', 'Soler', 'Matí', 1),
                  ('Aina', 'Ferrer', 'Mas', 'Matí', 1), ('Pol', 'Serra', 'Font', 'Tarda', 1),
                  ('Júlia', 'Casas', 'Riera', 'Matí', 2)]
        rows = [{'Nom': first, 'Primer cognom': last1, 'Segon cognom': last2,
                 'Ident. RALC': 9900000001 + index, 'Correu electrònic': '%s@example.com' % first.lower(),
                 'Curs': course, 'Centre assignat': 8028047, 'Codi ensenyament assignat': 'CFPM    DOCSMX',
                 'Nom ensenyament assignat': study.name, 'Torn assignat': shift}
                for index, (first, last1, last2, shift, course) in enumerate(people)]
        import_wizard = self.env['ems.applicant_import_wizard'].with_user(self.secretary_user).create({
            'file': self._gedac_xlsx(rows), 'file_name': 'gedac_assignats.xlsx',
        })
        import_wizard.action_import()
        applicants = self.env['res.partner'].search([('student_id', 'in', [str(r['Ident. RALC']) for r in rows])])
        # Two current students GEDAC assigned a destination to (the internal continuers).
        continuers = self.env['res.partner'].browse([self._student(name, group).id for name in
                                                     ('Nil Exemple Serra', 'Aina Mostra Puig')])
        continuers.write({'preinscription_study_id': study.id, 'preinscription_shift': 'morning',
                          'preinscription_course': '2'})

        # The native screens, scoped to these fixtures for the rest of this (rolled-back) test:
        # the menus, filters and buttons are the real ones, the rows are only made-up people.
        self.env.ref('ems.action_ems_applicants').domain = str([('id', 'in', applicants.ids)])
        login = 'doc_shot_secretary'
        applicants_url = '/odoo/action-ems.action_ems_applicants'

        # 01: the gear menu with Import from GEDAC.
        self._capture(
            applicants_url, '.o_action_manager', 'preinscrpcio-Secretaria-01.png', login=login,
            wait_for='.o_group_header', max_height=330,
            run=[self._js_click('.o_control_panel .o_cp_action_menus button:has(.fa-cog)'),
                 self._tag('.o-dropdown--menu .dropdown-item', 'GEDAC', 'ems-mark-gedac')],
            wait_after=['.o-dropdown--menu .dropdown-item', '#ems-mark-gedac'],
            marks=[('#ems-mark-gedac', '1', 'right')],
        )
        # 02: the import window.
        self._capture(
            '/odoo/action-ems.action_applicant_import_wizard', '.modal-content', 'preinscrpcio-Secretaria-02.png',
            login=login, wait_for=".modal-content button[name='action_import']",
            marks=[('.modal-content .o_select_file_button', '1', 'right'),
                   (".modal-content button[name='action_import']", '2', 'top')],
        )
        # 03: its result.
        self._capture(
            self._wizard_url('ems.applicant_import_wizard', 'Importar des de GEDAC', res_id=import_wizard.id),
            '.modal-content', 'preinscrpcio-Secretaria-03.png', login=login,
            wait_for=".modal-content .o_field_widget[name='result_html']",
        )
        # 04: the study panel (1), grouped by shift (2) and, within it, by course (3).
        self._capture(
            applicants_url, '.o_action_manager', 'preinscrpcio-Secretaria-04.png', login=login,
            wait_for='.o_group_header', max_height=360,
            click='.o_group_header', wait_after='.o_group_header.o_group_open + .o_group_header',
            marks=[('.o_search_panel .o_search_panel_category_value:last-child .o_search_panel_label_title', '1', 'right'),
                   ('.o_group_header.o_group_open .o_group_name', '2', 'text-right'),
                   ('.o_group_header.o_group_open + .o_group_header .o_group_name', '3', 'text-right')],
        )
        # 05: applicants selected and the Enrollment proposal button.
        self._capture(
            applicants_url, '.o_action_manager', 'preinscrpcio-Secretaria-05.png', login=login,
            wait_for='.o_group_header', max_height=360,
            click=['.o_group_header', '.o_group_header.o_group_open + .o_group_header',
                   '.o_data_row .o_list_record_selector input',
                   '.o_data_row + .o_data_row .o_list_record_selector input'],
            wait_after=['.o_group_header.o_group_open + .o_group_header', '.o_data_row',
                        '.o_data_row.o_data_row_selected', "button[name='action_enrollment_proposal']"],
            marks=[("button[name='action_enrollment_proposal']", '1', 'top')],
        )
        # 04b: the internal continuers, in Enrollment proposals with the GEDAC filter.
        self.env.ref('ems.action_student_group_enrollment').code = (
            "action = env.ref('ems.act_window_student_group_enrollment').sudo().read()[0]\n"
            "action['domain'] = [('id', 'in', %s)]\n"
            "action['context'] = {'search_default_gedac_assignment': 1}" % continuers.ids)
        self._capture(
            '/odoo/action-ems.action_student_group_enrollment', '.o_action_manager',
            'preinscrpcio-Secretaria-04b.png', login=login, wait_for='.o_data_row', max_height=300,
            marks=[('.o_searchview_facet', '1', 'right')],
        )
        # 06: the proposal window for the morning first-year applicants.
        morning_first = applicants.filtered(lambda a: a.preinscription_shift == 'morning'
                                            and a.preinscription_course == '1')
        proposal_action = self.env['ir.actions.act_window'].create({
            'name': 'Proposta de matrícula', 'res_model': 'ems.enrollment_proposal_wizard',
            'view_mode': 'form', 'target': 'new',
            'context': {'active_ids': morning_first.ids, 'default_template_id': template.id},
        })
        self._capture(
            '/odoo/action-%d' % proposal_action.id, '.modal-content', 'preinscrpcio-Secretaria-06.png',
            login=login, wait_for=".modal-content .o_field_widget[name='student_ids'] .o_data_row",
            marks=[("button[name='action_create_enrollments']", '1', 'top')],
        )
        # 07: the Actions menu with Portal access, applicants selected.
        self._capture(
            applicants_url, '.o_action_manager', 'preinscrpcio-Secretaria-07.png', login=login,
            wait_for='.o_group_header', max_height=420,
            run=[self._js_click('.o_group_header'),
                 self._js_click('.o_group_header.o_group_open + .o_group_header'),
                 self._js_click('.o_data_row .o_list_record_selector input'),
                 self._js_click('.o_control_panel .o_cp_action_menus button:has(.fa-cog)'),
                 self._tag('.o-dropdown--menu .dropdown-item', 'portal', 'ems-mark-portal')],
            wait_after=['.o_group_header.o_group_open + .o_group_header', '.o_data_row',
                        '.o_data_row.o_data_row_selected', '.o-dropdown--menu .dropdown-item',
                        '#ems-mark-portal'],
            marks=[('#ems-mark-portal', '1', 'right')],
        )

        # The draft enrollments that proposal creates, and one already confirmed.
        self.env['ems.enrollment_proposal_wizard'].with_context(active_ids=morning_first.ids).create({
            'template_id': template.id}).action_create_enrollments()
        drafts = self.env['sale.order'].search([('partner_id', 'in', morning_first.ids)])
        confirmed_student = self._student('Pere Exemple Soler', group)
        confirmed = self.env['sale.order'].create({
            'partner_id': confirmed_student.id, 'ems_study_id': study.id,
            'ems_course_id': drafts[:1].ems_course_id.id,
            'order_line': [(0, 0, {'product_id': subjects[0].product_id.id})],
        })
        confirmed.action_confirm()
        enrollments = self.env.ref('ems.action_ems_enrollments')
        enrollments.domain = str([('id', 'in', (drafts | confirmed).ids)])
        enrollments.context = str({'ems_enrollment': 1, 'search_default_sense_enviar': 1})
        enrollments_url = '/odoo/action-ems.action_ems_enrollments'

        # 08: Enrollment > Enrollments (1) with the Not sent filter (2).
        self._capture(
            enrollments_url, '.o_web_client', 'preinscrpcio-Secretaria-08.png', login=login,
            wait_for='.o_data_row + .o_data_row', max_height=340,
            marks=[(".o_main_navbar [data-menu-xmlid='ems.menu_ems_enrollment']", '1', 'right'),
                   ('.o_searchview_facet', '2', 'right')],
        )
        # 09: enrollments ticked (1) and Send enrollment (2).
        self._capture(
            enrollments_url, '.o_action_manager', 'preinscrpcio-Secretaria-09.png', login=login,
            wait_for='.o_data_row + .o_data_row', max_height=300,
            click=['.o_data_row .o_list_record_selector input',
                   '.o_data_row + .o_data_row .o_list_record_selector input'],
            wait_after=['.o_data_row.o_data_row_selected', "button[name='action_send_enrollment_proposal']"],
            marks=[('.o_data_row .o_list_record_selector', '1'),
                   ("button[name='action_send_enrollment_proposal']", '2', 'top')],
        )
        # 10-11: Re-apply Benefits on a confirmed enrollment, and its confirmation.
        confirmed_url = '%s/%d' % (enrollments_url, confirmed.id)
        self._capture(
            confirmed_url, '.o_action_manager', 'preinscrpcio-Secretaria-10.png', login=login,
            wait_for="button[name='action_ems_reapply_benefits']", max_height=260,
            marks=[("button[name='action_ems_reapply_benefits']", '1', 'top')],
        )
        self._capture(
            confirmed_url, '.modal-content', 'preinscrpcio-Secretaria-11.png', login=login,
            wait_for="button[name='action_ems_reapply_benefits']",
            click="button[name='action_ems_reapply_benefits']", wait_after='.modal-content',
        )

