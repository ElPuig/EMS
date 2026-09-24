# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Secretariat user manuals.

Tagged '-standard' on purpose - see the NOTE in test_docs_screenshots.py for why. Run it by
hand when a documented screen changes its look:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsSecretary' --stop-after-init -c /etc/odoo/odoo.conf"

One test method per manual (see plans/user_manual_screenshots.md). Writes PNGs to
/tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR); copy them into
docs/assets/secretary/ by hand afterwards. The absences and attendance-reports manuals, and the
family-contacts part of student-contacts, reuse existing captures of the same screens (Head of
Studies, teachers, tutors), so they have no method here.
"""
import base64
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
