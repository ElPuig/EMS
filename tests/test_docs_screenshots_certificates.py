# -*- coding: utf-8 -*-
"""Regenerates the screenshots of the certificate request manuals (issue #835): secretariat,
VET coordinator, Director, families and administrator.

Tagged '-standard' on purpose - see the NOTE in test_docs_screenshots.py. Run it by hand:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsCertificates' --stop-after-init -c /etc/odoo/odoo.conf"

Writes PNGs to /tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR); copy each into
docs/assets/<role>/ by hand afterwards. Made-up people only, in the test's rolled-back
transaction; the backend list opens an action limited to these fixtures, so no real request of
the database shows."""
from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, create_role_user, mock_outgoing_email, next_student_id

ACTIONS_TOGGLE = '.o_form_view .o_form_statusbar .o_ems_actions_toggle'


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsCertificates(DocsScreenshotMixin, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.admin_user = create_role_user(cls, 'academic_admin', 'doc_shot_cert_admin', lang='ca_ES',
                                          name='Administració Exemple')
        cls.secretary = create_role_user(cls, 'secretary', 'doc_shot_cert_secretary', lang='ca_ES',
                                         name='Secretaria Exemple')
        cls.certificate_type = cls.env.ref('ems.certificate_type_fct')
        # Only FCT is offered, whatever other types the database has.
        cls.env['ems.certificate.type'].search([('id', '!=', cls.certificate_type.id)]).active = False
        cls.steps = cls.certificate_type.step_ids.sorted('sequence')
        cls.agreement_document = cls.certificate_type._ems_documents()[:1]
        # As seeded (noupdate, so a database may have changed it): the agreement is required before issuing.
        cls.agreement_document.required_step_id = cls.steps[1]
        cfgs = cls.env.ref('ems.level_cfgs')
        cls.study = cls.env['ems.study'].search([('level_id', '=', cfgs.id)], limit=1)
        group = cls.env['ems.group'].create({'course': 2, 'acronym': 'Z', 'level_id': cfgs.id,
                                             'study_id': cls.study.id})
        cls.student = cls.env['res.partner'].create({
            'name': 'Pau Exemple Soler', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id, 'birth_date': '2004-05-10', 'document_id': '12345678Z',
            'email': 'pau.exemple@example.com', 'lang': 'ca_ES',
        })
        cls.portal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': cls.student.name, 'login': 'doc_shot_cert_student', 'password': 'doc_shot_cert_student',
            'partner_id': cls.student.id, 'lang': 'ca_ES',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.company = cls.env['res.partner'].create({
            'name': 'Empresa Exemple, SL', 'contact_type': 'company', 'is_company': True, 'vat': 'B00000000',
        })
        Certificate = cls.env['ems.certificate'].with_context(lang='ca_ES')
        applicant = {'student_id': cls.student.id, 'student_name': cls.student.name, 'student_document': '12345678Z',
                     'study_id': cls.study.id, 'origin': 'portal', 'type_id': cls.certificate_type.id}
        year = {'school_year': '2025-2026'}
        # On the first step: as the student filed it, with the agreement attached.
        cls.on_first_step = Certificate.create({**applicant, 'applicant_form_open': True})
        cls.on_first_step._ems_set_values({**year, 'company': {'value_char': 'Empresa Exemple'}})
        cls.on_first_step._ems_submit()
        cls._attach(cls.on_first_step, 'conveni-fct.pdf')
        # On the step that issues it: the training completed by the VET coordinator.
        training = {**year, 'company': cls.company.id, 'start': '2026-03-02', 'end': '2026-06-12', 'hours': 380,
                    'agreement': '2026000001'}
        cls.to_issue = Certificate.create(applicant)
        cls.to_issue._ems_set_values(training)
        cls.to_issue._ems_submit()
        cls._attach(cls.to_issue, 'conveni-fct.pdf')
        cls.to_issue.sudo().write({'step_id': cls.steps[1].id})
        # On the Director's step.
        cls.to_approve = Certificate.create(applicant)
        cls.to_approve._ems_set_values(training)
        cls.to_approve._ems_submit()
        cls._attach(cls.to_approve, 'conveni-fct.pdf')
        cls.to_approve.sudo().write({'step_id': cls.steps[2].id, 'name': 'CERT-2026-27-0007'})
        # A former student who is not in EMS, just registered by the secretariat.
        cls.former = Certificate.create({'type_id': cls.certificate_type.id, 'origin': 'secretariat',
                                         'student_name': 'Joan Exemple Puig',
                                         'applicant_email': 'joan.exemple@example.com'})
        # One already issued (its PDF is not part of these shots).
        cls.issued = Certificate.create(applicant)
        cls.issued._ems_set_values(training)
        cls.issued.sudo().write({'state': 'issued', 'name': 'CERT-2026-27-0003', 'submission_date': '2026-10-05'})
        cls.action = cls.env['ir.actions.act_window'].create({
            'name': 'Certificats', 'res_model': 'ems.certificate', 'view_mode': 'list,form',
            'domain': [('id', 'in', (cls.on_first_step | cls.to_issue | cls.to_approve | cls.former | cls.issued).ids)],
        })

    @classmethod
    def _attach(cls, certificate, name):
        line = certificate.document_ids.filtered(lambda line: line.type_document_id == cls.agreement_document)
        line.attachment_ids = [(0, 0, {'name': name, 'raw': b'%PDF-1.4', 'mimetype': 'application/pdf',
                                       'res_model': line._name, 'res_id': line.id})]

    def _form(self, certificate):
        return f'/odoo/action-{self.action.id}/{certificate.id}'

    def test_capture_certificate_screenshots(self):
        admin, secretary = 'doc_shot_cert_admin', 'doc_shot_cert_secretary'
        # Secretariat: the list, a former student's new request and the Actions of a request.
        self._capture(f'/odoo/action-{self.action.id}', '.o_list_renderer', 'certificats-01-llista.png',
                      login=secretary, wait_for='.o_list_renderer .o_data_row + .o_data_row')
        self._capture(self._form(self.former), '.o_form_sheet', 'certificats-02-exalumne.png', login=secretary,
                      wait_for=".o_form_view .o_field_widget[name='applicant_email']", max_height=420)
        # The step's holder (here the administrator, who may do any step) sees its button.
        self._capture(self._form(self.to_issue), '.o_content', 'certificats-03-expedir.png', login=admin,
                      wait_for=ACTIONS_TOGGLE, click=ACTIONS_TOGGLE,
                      wait_after=".o_ems_actions_menu button[name='action_done_step']", max_height=420,
                      beyond_viewport=False)
        # VET coordinator: the certificate details and the documentation of a request.
        self._capture(self._form(self.on_first_step), '.o_notebook', 'certificats-04-formacio.png', login=admin,
                      wait_for='.o_notebook', click=".o_notebook .nav-link[name='details']",
                      wait_after=".o_field_widget[name='value_ids'] .o_data_row")
        self._capture(self._form(self.on_first_step), '.o_notebook', 'certificats-05-documentacio.png', login=admin,
                      wait_for='.o_notebook', click=".o_notebook .nav-link[name='documentation']",
                      wait_after=".o_field_widget[name='document_ids'] .o_data_row")
        # Director: approving.
        self._capture(self._form(self.to_approve), '.o_content', 'certificats-06-aprovar.png', login=admin,
                      wait_for=ACTIONS_TOGGLE, click=ACTIONS_TOGGLE,
                      wait_after=".o_ems_actions_menu button[name='action_done_step']", max_height=420,
                      beyond_viewport=False)
        # Administrator: the certificate type.
        self._capture(f'/odoo/action-ems.action_certificate_type/{self.certificate_type.id}', '.o_form_sheet',
                      'certificats-07-tipus.png', login=admin,
                      wait_for=".o_field_widget[name='step_ids'] .o_data_row + .o_data_row")
        # Families and students: the portal list, the new request and a request's page.
        student = 'doc_shot_cert_student'
        self._capture('/my/certificats', '.o_ems_portal_certificates', 'certificats-08-portal.png', login=student,
                      wait_for='.o_ems_certificate_request')
        self._capture('/my/certificats?new=1', '.o_ems_certificate_new', 'certificats-09-sollicitud.png',
                      login=student, wait_for='.o_ems_certificate_new .collapse.show')
        self._capture(self.on_first_step.get_portal_url(), '.o_ems_portal_certificate', 'certificats-10-resum.png',
                      login=student, wait_for='.o_ems_certificate_summary', max_height=900)
