# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Families user manuals.

Tagged '-standard' on purpose - see the NOTE in test_docs_screenshots.py for why. Run it by
hand when a documented screen changes its look:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsFamilies' --stop-after-init -c /etc/odoo/odoo.conf"

One test method per manual (see docs/en/developers/shared/testing.md, "DocsScreenshotMixin"). Writes PNGs to
/tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR); copy them into docs/assets/families/
by hand afterwards.
"""
import base64
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, mock_outgoing_email, next_student_id


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsFamilies(DocsScreenshotMixin, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Approving/rejecting a document posts a comment to its follower (the student).
        mock_outgoing_email(cls)
        # Two children, so the header shows the student selector the manual talks about.
        cls.student = cls._student('Pau Exemple Soler', document_id='12345678Z',
                                   medical_id='EXSO 0000000000')
        cls.sibling = cls._student('Laia Exemple Soler')
        cls.family = cls.env['res.partner'].create({
            'name': 'Marc Exemple Vidal', 'contact_type': 'family',
            'email': 'marc.exemple@example.com',
        })
        cls.env['res.partner.relation'].create([{
            'left_partner_id': cls.family.id,
            'type_id': cls.env.ref('ems.relation_type_father').id,
            'right_partner_id': child.id,
        } for child in (cls.student, cls.sibling)])
        cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': cls.family.name, 'login': 'doc_shot_family', 'password': 'doc_shot_family',
            'lang': 'ca_ES', 'partner_id': cls.family.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        # res.partner.relation.all is a SQL view: flush so get_portal_students() sees the rows.
        cls.env.flush_all()

    @classmethod
    def _student(cls, name, **overrides):
        return cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'email': '%s@example.com' % name.split()[0].lower(),
            'birth_date': date.today() - relativedelta(years=15),
            **overrides,
        })

    @classmethod
    def _document(cls, doc_type, days_ago, file_name=None, **vals):
        document = cls.env['ems.student.document'].create({
            'partner_id': cls.student.id, 'doc_type': doc_type,
            'doc_file': base64.b64encode(b'%PDF-1.4 x') if file_name else False,
            'doc_file_name': file_name,
            **vals,
        })
        # Spread the submissions over time, so the history reads like a real one.
        document.upload_date = datetime.now() - relativedelta(days=days_ago)
        return document

    def test_capture_manual_documentacio(self):
        # One of every status the manual lists: an IBAN replaced by a later one (cancelled), an
        # approved IBAN, medical card and benefit, a rejected passport and a pending DNI plus
        # a pending benefit request.
        self._document('iban', 400, doc_value='ES7921000813610123456789',
                       doc_value2='Marc Exemple Vidal').action_cancel()
        self._document('iban', 380, doc_value='ES9121000418450200051332',
                       doc_value2='Marc Exemple Vidal',
                       expiry_date=date.today() + relativedelta(months=8)).action_approve()
        self._document('medical', 360, 'targeta_sanitaria.pdf',
                       expiry_date=date.today() + relativedelta(years=3)).action_approve()
        self._document('benefit', 350, 'titol_familia_nombrosa.pdf',
                       benefit_type='large_family_gen').action_approve()
        passport = self._document('passport', 20, 'passaport.jpg',
                                  rejection_reason="La imatge no es llegeix bé, torneu-la a pujar.")
        passport.action_reject()
        self._document('dni', 3, 'dni_pau.pdf', expiry_date=date.today() + relativedelta(years=5))
        self._document('benefit', 2, 'beca_ministeri.pdf', benefit_type='scholarship')

        url = '/my/documentacion'
        login = 'doc_shot_family'
        # The header with the student selector open, plus the "viewing documentation for" banner.
        self._capture(
            url, '#wrapwrap', 'documentacio-01-seleccio-alumne.png', login=login,
            wait_for='#documentation_content',
            click='.ems-custom-navbar .dropdown-toggle',
            wait_after='.ems-custom-navbar .dropdown-menu.show',
            max_height=260,
        )
        self._capture(
            url, '.card:has(button[data-bs-target="#modal-upload-passport"])',
            'documentacio-02-documents-oficials.png', login=login,
        )
        self._capture(
            url, '#modal-upload-passport .modal-content', 'documentacio-03-pujar-document.png',
            login=login, wait_for='#documentation_content',
            click='button[data-bs-target="#modal-upload-passport"]',
            wait_after='#modal-upload-passport.show',
        )
        self._capture(
            url, '.card:has(form[action="/my/documentacion/renew-iban"])',
            'documentacio-04-iban.png', login=login,
        )
        self._capture(
            url, '.card:has(button[data-bs-target="#modal-submit-benefit"])',
            'documentacio-05-bonificacions.png', login=login,
        )
        self._capture(
            url, '#modal-submit-benefit .modal-content', 'documentacio-06-sol-licitud-bonificacio.png',
            login=login, wait_for='#documentation_content',
            click='button[data-bs-target="#modal-submit-benefit"]',
            wait_after='#modal-submit-benefit.show',
        )
        self._capture(
            url, '.card:has(.fa-history)', 'documentacio-07-historial.png', login=login,
        )
