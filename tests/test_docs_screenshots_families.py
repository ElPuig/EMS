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
import json
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
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(), 'lang': 'ca_ES',
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

    def test_capture_manual_dades_contacte(self):
        """manual-dades-contacte (issue #507): the Profile tab's button, the student's card, the
        family section and the form marked in red after sending it incomplete."""
        # The family contact as the secretariat would have entered it. Creating the user
        # rewrote the name split in this class's fixtures: set it explicitly.
        self.family.write({'firstname': 'Marc', 'lastname': 'Exemple Vidal', 'mobile': '+34 600 000 003'})
        login = 'doc_shot_family'

        # The read-only profile, with the button that opens the review.
        self._capture(
            '/my/account', '.o_portal_details', 'dades-contacte-01-perfil.png', login=login,
            wait_for=".o_portal_details a[href='/my/dades-contacte']",
            marks=[(".o_portal_details a[href='/my/dades-contacte']", '1', 'left')],
        )

        url = '/my/dades-contacte'
        wait = '.o_ems_contact_data_form'
        self._capture(url, '.o_ems_contact_data_form .card:not(.o_ems_family_entry)',
                      'dades-contacte-02-alumne.png', login=login, wait_for=wait)
        self._capture(
            url, '#ems-clip', 'dades-contacte-03-familia.png', login=login, wait_for=wait,
            run=self._union_clip_js(['.o_ems_contact_data_form h4', '.o_ems_add_family']),
            wait_after='#ems-clip',
        )

        # Sent as it is: the student's address is still to be filled in.
        self._capture(
            url, '#ems-clip', 'dades-contacte-04-errors.png', login=login, wait_for=wait,
            run=["document.querySelector('.o_ems_contact_data_submit').click()",
                 self._union_clip_js(['.o_ems_contact_data_errors',
                                      '.o_ems_contact_data_form .card:not(.o_ems_family_entry)'])],
            wait_after=['.o_ems_contact_data_errors', '#ems-clip'],
        )

        # A second child's contact: adding a family contact offers the other child, and one that
        # repeats a contact of that child is pointed out.
        mother = self.env['res.partner'].create({
            'firstname': 'Núria', 'lastname': 'Exemple Vidal', 'contact_type': 'family',
            'mobile': '+34 600 000 004', 'email': 'nuria.exemple@example.com'})
        self.env['res.partner.relation'].create({
            'left_partner_id': mother.id, 'type_id': self.env.ref('ems.relation_type_mother').id,
            'right_partner_id': self.sibling.id})
        self.env.flush_all()
        add_contact = "document.querySelector('.o_ems_add_family').click()"
        self._capture(
            url, '.o_ems_new_family_container .o_ems_family_entry', 'dades-contacte-05-altres-fills.png',
            login=login, wait_for=wait, run=add_contact,
            wait_after='.o_ems_new_family_container .o_ems_family_entry',
        )
        fill_and_send = (
            "(function () {"
            " document.querySelector('.o_ems_add_family').click();"
            " var card = document.querySelector('.o_ems_new_family_container .o_ems_family_entry');"
            " var set = function (name, value) { card.querySelector('[name=\"' + name + '\"]').value = value; };"
            " var select = card.querySelector('select[name=\"n0_relation_type_id\"]');"
            " var mare = Array.from(select.options).find(function (o) { return o.text.trim() === 'Mare'; });"
            " select.value = mare ? mare.value : select.options[1].value;"
            " set('n0_firstname', 'Núria'); set('n0_lastname', 'Exemple Vidal'); set('n0_mobile', '+34 600 000 004');"
            " document.querySelector('.o_ems_contact_data_submit').click();"
            "})()")
        self._capture(
            url, ".o_ems_family_entry[data-key='n0']", 'dades-contacte-06-contacte-repetit.png',
            login=login, wait_for=wait, run=fill_and_send, wait_after='.o_ems_contact_match',
        )

    def test_capture_portal_onboarding(self):
        """manual-portal-alumne: the welcome e-mail, the password form it leads to, and the
        portal's home once signed in - for a made-up student granted access here."""
        student = self.student
        # The e-mail's footer shows the company's address: the centre's public one, not whatever
        # a development box has rewritten it to.
        self.env.company.email = 'iespuigcastellar@xtec.cat'
        wizard = self.env['portal.wizard'].with_context(active_ids=student.ids).create({})
        wizard_user = wizard.user_ids.filtered(lambda line: line.partner_id == student)
        wizard_user.action_grant_access()
        user = student.with_context(active_test=False).user_ids[:1]
        user.write({'lang': 'ca_ES'})

        # Step 1: the welcome e-mail, rendered from the same template the invitation sends and
        # drawn into a blank page to capture it.
        # A fresh signup token, forced into the URL: without it the link falls back to the plain
        # login page for a partner that already has a user.
        student.signup_prepare(signup_type='signup')
        signup_url = student.with_context(signup_force_type_in_url='signup', lang='ca_ES')._get_signup_url_for_action()[student.id]
        template = self.env.ref('portal.mail_template_data_portal_welcome')
        body = template.with_context(portal_url=signup_url, lang='ca_ES')._render_field(
            'body_html', wizard_user.ids, compute_lang=True)[wizard_user.id]
        draw = ("document.open(); document.write(%s); document.close();"
                % json.dumps('<html><body style="background:#f1f1f1;padding:16px;">%s</body></html>' % body))
        self._capture(
            '/web/login', 'body > table, body > div, body', 'manual-portal-alumne-email.png',
            wait_for='.o_login_auth, form', run=draw, wait_after='body table',
        )

        # Step 2: the password form behind the e-mail's button.
        path = '/' + signup_url.split('/', 3)[3]
        self._capture(
            path, 'form.oe_signup_form', 'manual-portal-alumne-01.png',
            wait_for="input[name='confirm_password']",
            marks=[("input[name='login']", '1', 'right'), ("input[name='name']", '2', 'right'),
                   ("input[name='password']", '3', 'right'), ("input[name='confirm_password']", '4', 'right'),
                   ("form.oe_signup_form button[type='submit']", '5', 'right')],
        )

        # Step 4: the portal's home, signed in.
        user.password = user.login
        self._capture(
            '/my', '#wrapwrap', 'manual-portal-alumne-02.png', login=user.login,
            wait_for='.o_portal_wrap, .o_portal', max_height=680,
        )

    def _enrollment_fixture(self, student, study, course, terms, fee, extras, subjects):
        order = self.env['sale.order'].create({
            'partner_id': student.id, 'ems_course_id': course.id, 'ems_study_id': study.id})
        # Lines after create(): the fee line prices itself from the order's subject lines.
        order.order_line = [(0, 0, {'product_id': product.id}) for product in extras] + [
            (0, 0, {'product_id': subject.product_id.id}) for subject in subjects] + [
            (0, 0, {'product_id': fee.product_variant_id.id})]
        return order

    def test_capture_enrollment_confirmation(self):
        """manual-confirmacio-matricula, from no proposal at all to a paid installment."""
        from .common import create_level_study
        family_login = 'doc_shot_family'
        url = '/my/gestion-matriculas'

        # Step 1: the portal home, and the Enrollment page with no proposal yet.
        self._capture(
            '/my', '#wrapwrap', 'Matricula-confirmacio-00.png', login=family_login,
            wait_for='.o_portal_my_home', max_height=460,
            marks=[(".ems-custom-navbar a[href='/my/gestion-matriculas']", '1', 'text-right')],
        )
        self._capture(url, '#enrollment_content, #wrapwrap main', 'Matricula-confirmacio-01.png',
                      login=family_login, wait_for='#wrapwrap main', max_height=300)

        # A proposal sent to the family: authorization, items (with a fee) and payment plans -
        # built in Catalan, as the secretariat would (the fee line's wording is stored).
        self.env = self.env(context=dict(self.env.context, lang='ca_ES'))
        course = self.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1) \
            or self.env['ems.course'].create({'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        __, study = create_level_study(self, 'DOCMAT', level={'name': 'Cicles formatius (proves)'}, study={
            'code': 'DOCMAT01', 'acronym': 'ASIXP', 'name': 'Administració de sistemes informàtics en xarxa (proves)'})
        subjects = self.env['ems.subject'].create([{
            'code': code, 'acronym': code, 'name': name, 'study_ids': [(6, 0, [study.id])],
        } for code, name in (('0369', 'Implantació de sistemes operatius'),
                             ('0370', 'Planificació i administració de xarxes'),
                             ('0372', 'Gestió de bases de dades'))])
        fee = self.env['product.template'].create({
            'name': 'Taxa CFGS (proves)', 'type': 'service', 'invoice_policy': 'order',
            'is_generic': True, 'ems_is_enrollment_fee': True,
            'list_price': 360.0, 'ems_subject_unit_cost': 120.0})
        # Generic, like the centre's own: not counted as subjects by the fee.
        extras = self.env['product.product'].create([{
            'name': name, 'type': 'service', 'invoice_policy': 'order', 'list_price': price,
            'is_generic': True,
        } for name, price in (('Matrícula (proves)', 75.0), ('Quota AMPA (proves)', 15.0))])
        Term = self.env['account.payment.term']
        terms = Term.search([('ems_portal_visible', '=', True)])
        single = terms.filtered(lambda t: not t.ems_requires_fees)[:1] or Term.create({
            'name': 'Pagament únic (juliol)', 'ems_portal_visible': True,
            'line_ids': [(0, 0, {'value': 'percent', 'value_amount': 100.0, 'nb_days': 0})]})
        split = terms.filtered('ems_requires_fees')[:1] or Term.create({
            'name': 'Pagament en dos terminis (juliol i setembre)', 'ems_portal_visible': True,
            'ems_requires_fees': True, 'line_ids': [
                (0, 0, {'value': 'percent', 'value_amount': 50.0, 'nb_days': 0}),
                (0, 0, {'value': 'percent', 'value_amount': 50.0, 'nb_days': 60})]})
        # Only this made-up form applies to enrollments here (the centre's own ones would join
        # it otherwise); rolled back with the rest of the test.
        Template = self.env['ems.authorization.template']
        Template.search([('apply_on_enrollment', '=', True)]).write(
            {'apply_on_enrollment': False, 'sendable_during_course': True})
        Template.create({
            'name': "Drets d'imatge i so", 'is_required': True,
            'legal_text': "<p>Autoritzo l'ús de la imatge de {{student_name}} en activitats del centre.</p>",
        })
        order = self._enrollment_fixture(self.student, study, course, terms, fee, extras, subjects)
        # Settle the fee line now, in this (Catalan) environment: left pending, it would be
        # computed later in whatever context happens to flush it.
        self.env.flush_all()
        order.ems_authorization_ids = order._get_authorization_commands()
        order.action_quotation_sent()

        # Step 2: the authorizations to answer.
        self._capture(url, '#portal_authorizations', 'Matricula-confirmacio-02-autoritzacions.png',
                      login=family_login, wait_for='#portal_authorizations .ems-auth-answer',
                      marks=[('#portal_authorizations .ems-auth-answer', '1', 'left')])
        # Step 3: the items and their total.
        self._capture(url, '#ems-clip', 'Matricula-confirmacio-03-itemsMatriculaOK.png',
                      login=family_login, wait_for='.ems-comment-check',
                      run=self._union_clip_js(['.card:has(.ems-comment-check) .card-header',
                                               '.card:has(.ems-comment-check) .row.justify-content-end']),
                      wait_after='#ems-clip')
        # Step 4: a line ticked for a comment (1), the comments box (2) and its button (3).
        tick = ("(function () { var box = document.querySelector('.ems-comment-check'); box.click();"
                " var text = document.getElementById('ems-comments');"
                " text.value = 'Voldria canviar el mòdul de bases de dades per un altre.'; })();")
        self._capture(url, '#ems-clip', 'Matricula-confirmacio-04-itemsMatricula_Canvi.png',
                      login=family_login, wait_for='.ems-comment-check',
                      run=[tick, self._union_clip_js(['.card:has(.ems-comment-check) .card-header',
                                                      '#ems-comments-block'])],
                      wait_after=['#ems-comments-block[style*="block"], #ems-comments-block:not([style*="none"])', '#ems-clip'],
                      marks=[('.ems-comment-check', '1', 'left'), ('#ems-comments', '2', 'left')])
        self._capture(url, '#ems-clip', 'Matricula-confirmacio-04-itemsMatricula_Canvi_2.png',
                      login=family_login, wait_for='.ems-comment-check',
                      run=[tick, self._union_clip_js(['#ems-comments-block', '#ems-comment-btn'])],
                      wait_after=['#ems-comment-btn:not([style*="none"])', '#ems-clip'],
                      marks=[('#ems-comment-btn', '3', 'right')])
        # Step 5: the payment plan and method, with no bank account yet.
        payment = ['.border-top:has(input[name="payment_term_id"])', '#pm-direct-debit-details']
        self._capture(url, '#ems-clip', 'Matricula-confirmacio-05-Pagament01.png',
                      login=family_login, wait_for='input[name="payment_term_id"]',
                      run=self._union_clip_js(payment), wait_after='#ems-clip')

        # Step 6: the IBAN, first with no account on file, then with one (renew (1) or update (2)).
        docs = '/my/documentacion'
        iban_card = '.card:has(form[action="/my/documentacion/submit"] input[name="doc_type"][value="iban"])'
        self._capture(docs, iban_card, 'Matricula-confirmacio-06-Documentacio-00.png',
                      login=family_login, wait_for=iban_card)
        self.env['ems.student.document'].create({
            'partner_id': self.student.id, 'doc_type': 'iban', 'doc_value': 'ES9121000418450200051332',
            'doc_value2': 'Marc Exemple Vidal',
        }).action_approve()
        self._capture(docs, '.card:has(form[action="/my/documentacion/renew-iban"])',
                      'Matricula-confirmacio-06-Documentacio-01-IBAN.png', login=family_login,
                      wait_for='form[action="/my/documentacion/renew-iban"]',
                      marks=[('form[action="/my/documentacion/renew-iban"] button', '1', 'top'),
                             ('form[action="/my/documentacion/submit"]:has(input[value="iban"]) input[name="doc_value"]', '2', 'top')])

        # Step 7: back in Enrollment - plan (1) and the registered account (2); with the
        # authorization accepted, Confirm (3) is enabled.
        pick_split = "document.getElementById('term_%d').click();" % split.id
        self._capture(url, '#ems-clip', 'Matricula-confirmacio-07-PagamentOK.png',
                      login=family_login, wait_for='input[name="payment_term_id"]',
                      run=[pick_split, self._union_clip_js(payment)],
                      wait_after=['#ems-installment-breakdown:not([style*="none"])', '#ems-clip'],
                      marks=[('#term_%d' % split.id, '1', 'left'), ('#pm-direct-debit-details', '2', 'left')])
        order.ems_authorization_ids.write({'status': 'yes', 'signed_document': base64.b64encode(b'%PDF-1.4 x'),
                                           'signed_document_name': 'drets_imatge.pdf'})
        self._capture(url, '#ems-clip', 'Matricula-confirmacio-08-ConfirmacioOK.png',
                      login=family_login, wait_for='input[name="payment_term_id"]',
                      run=[pick_split, self._union_clip_js(['#pm-direct-debit-details', '#ems-confirm-btn'])],
                      wait_after=['#ems-confirm-btn:not([disabled])', '#ems-clip'],
                      marks=[('#ems-confirm-btn', '3', 'right')])

        # After confirming: the invoice's two installments, pending.
        order.write({'payment_term_id': split.id, 'ems_payment_method': 'direct_debit'})
        order.action_confirm()
        order._ems_generate_enrollment_invoice()
        self._capture(url, '#portal_enrollment_payment', 'Matricula-confirmacio-09-CalendariPagaments.png',
                      login=family_login, wait_for="#portal_enrollment_payment [data-installment-state='pending']")
        # ...and a single payment already collected, on the other child's enrollment.
        other = self._enrollment_fixture(self.sibling, study, course, terms, fee, extras, subjects)
        other.write({'payment_term_id': single.id, 'ems_payment_method': 'direct_debit'})
        other.action_confirm()
        invoice = other._ems_generate_enrollment_invoice()
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({'payment_date': date.today()})._create_payments()
        self.family.selected_student_id = self.sibling
        self._capture(url, '#portal_enrollment_payment', 'Matricula-confirmacio-10-PagamentPagat.png',
                      login=family_login, wait_for="#portal_enrollment_payment [data-installment-state='paid']")

