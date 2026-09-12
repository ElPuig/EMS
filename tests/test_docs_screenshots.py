# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the user manuals.

Not part of the test suite: tagged '-standard', so `./test.sh` never runs it. Run it by hand
when a documented screen changes its look:

    ./test.sh '/ems:TestDocsScreenshots'

It writes PNGs to /tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR) and they are
then copied into docs/assets/ by hand - the test process runs as the `odoo` user, which has
no write access to the repository.

Why a test and not a standalone script: every screenshot needs a logged-in browser against a
database holding the right records, and an HttpCase already provides exactly that. Crucially,
its fixtures live in a transaction that is rolled back, so the screenshots show made-up
people and nothing from this box's real data - which is what makes them publishable at all
(see CLAUDE.md, "Screenshots must never expose real personal data"). Each shot is clipped to
one element for the same reason, plus it is what makes the image readable in a manual.
"""
import base64
import json
import os
from datetime import date

import werkzeug.urls
from dateutil.relativedelta import relativedelta

from odoo.tests.common import ChromeBrowser, HttpCase, tagged

from .common import create_level_study_group, create_role_employee, create_role_user

OUTPUT_DIR = os.environ.get('EMS_SCREENSHOT_DIR', '/tmp/ems_doc_screenshots')


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshots(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        cls.secretary = create_role_user(cls, 'secretary', 'doc_shot_secretary',
                                         name='Secretariat', email='secretariat@example.com')
        create_role_employee(cls, cls.secretary, employee_type='asp', name='0000 Secretariat')

        Course = cls.env['ems.course']
        cls.course = Course.search([('is_current', '=', True)], limit=1) \
            or Course.create({'start': 2096, 'end': 2097, 'is_current': True})
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'DOC', level={
            'name': 'Vocational Training',
        }, study={
            'code': 'DOC001', 'acronym': 'DAM', 'name': 'Multiplatform Application Development',
        }, group={'acronym': 'A', 'course': 1})
        cls.subject = cls.env['ems.subject'].create({
            'code': 'DOCSUB', 'acronym': 'DSB', 'name': 'Databases',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        # Invented people, on an invented group: these end up in a published manual.
        cls.students = cls.env['res.partner']
        for name in ('Marina Exemple', 'Pau Mostra', 'Nerea Prova'):
            cls.students |= cls._student(name)

        cls.template = cls.env['ems.authorization.template'].create({
            'name': 'Museum visit (November)',
            'apply_on': 'standalone',
            'legal_text': '<p>I authorise {{student_name}}, enrolled in {{study_name}} during '
                          '{{academic_year}}, to take part in the museum visit.</p>',
            'field_ids': [(0, 0, {'label': 'Emergency phone number', 'field_type': 'char',
                                  'placeholder': 'e.g. 600 123 456'})],
        })
        # One already answered and one still pending, so the follow-up list shows both states.
        cls.env['ems.authorization'].create([{
            'partner_id': student.id, 'course_id': cls.course.id, 'template_id': cls.template.id,
        } for student in cls.students])
        answered = cls.env['ems.authorization'].search([
            ('template_id', '=', cls.template.id), ('partner_id', '=', cls.students[1].id)])
        answered.write({'status': 'yes', 'signed_document': base64.b64encode(b'%PDF-1.4 x'),
                        'signed_document_name': 'Cert_museum.pdf'})

        # Not sent to anybody yet, so the assistant's preview has something to show.
        cls.pending_template = cls.env['ems.authorization.template'].create({
            'name': 'Swimming pool activity (term 2)',
            'apply_on': 'standalone',
            'legal_text': '<p>I authorise {{student_name}} to take part in the activity.</p>',
        })

        # The portal shot needs a student who can log in and who has one authorization to
        # answer, on top of a confirmed enrollment.
        cls.portal_student = cls._student('Alex Exemple')
        cls.portal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Alex Exemple', 'login': 'doc_shot_portal', 'password': 'doc_shot_portal',
            'lang': 'en_US', 'partner_id': cls.portal_student.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.env['ems.authorization'].create({
            'partner_id': cls.portal_student.id, 'course_id': cls.course.id,
            'template_id': cls.template.id,
        })

        # Actions of their own, scoped to these fixtures: it is what guarantees no real record
        # can appear in the shot, rather than trusting a crop.
        cls.list_action = cls.env['ir.actions.act_window'].create({
            'name': 'Authorizations',
            'res_model': 'ems.authorization',
            'view_mode': 'list,form',
            'search_view_id': cls.env.ref('ems.view_ems_authorization_search').id,
            'domain': [('template_id', '=', cls.template.id)],
        })
        cls.wizard_action = cls.env['ir.actions.act_window'].create({
            'name': 'Send Authorizations',
            'res_model': 'ems.authorization.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_target': 'students',
                'default_student_ids': [(6, 0, cls.students[:1].ids)],
                'default_template_ids': [(6, 0, cls.pending_template.ids)],
            },
        })

    @classmethod
    def _student(cls, name):
        student = cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'main_group_id': cls.group.id,
            'email': '%s@example.com' % name.split()[0].lower(),
            'birth_date': date.today() - relativedelta(years=19),
        })
        order = cls.env['sale.order'].create({
            'partner_id': student.id, 'ems_study_id': cls.study.id,
            'ems_course_id': cls.course.id,
            'order_line': [(0, 0, {'product_id': cls.subject.product_id.id})],
        })
        order.action_confirm()
        return student

    @staticmethod
    def _trim(path, margin=6):
        """Crop the uniform background off the edges - an element's bounding box routinely
        includes a large empty area (an unfilled list, the rest of a form sheet) that only
        makes the image smaller in the manual."""
        from PIL import Image, ImageChops
        image = Image.open(path).convert('RGB')
        background = Image.new('RGB', image.size, image.getpixel((image.width - 1, image.height - 1)))
        box = ImageChops.difference(image, background).getbbox()
        if not box:
            return
        left, top, right, bottom = box
        image.crop((
            max(left - margin, 0), max(top - margin, 0),
            min(right + margin, image.width), min(bottom + margin, image.height),
        )).save(path)

    @staticmethod
    def _appear_code(selector):
        """JS that signals success once `selector` is on the page (plus a beat for the
        rendering to settle), and fails loudly rather than hanging if it never shows up."""
        quoted = json.dumps(selector)
        return """
            (function () {
                var attempts = 0;
                var timer = setInterval(function () {
                    attempts++;
                    if (document.querySelector(%s)) {
                        clearInterval(timer);
                        setTimeout(function () { console.log('screenshot ready'); }, 700);
                    } else if (attempts > 100) {
                        clearInterval(timer);
                        console.error('never appeared: ' + %s);
                    }
                }, 200);
            })();
        """ % (quoted, quoted)

    def _capture(self, url_path, selector, filename, login, wait_for=None, padding=8,
                 click=None, wait_after=None):
        """Load url_path as `login`, wait for `wait_for` (defaults to `selector`), optionally
        click `click` and wait for `wait_after`, then write a PNG clipped to `selector` into
        OUTPUT_DIR.

        The click exists for the send assistant: its recipient preview is built by an onchange,
        which opening the form with defaults does not fire on its own.
        """
        browser = ChromeBrowser(self, headless=True, success_signal='screenshot ready')
        try:
            self.authenticate(login, login, browser=browser)
            self.cr.flush()
            self.cr.clear()
            # A taller viewport than the default 1366x768, set BEFORE navigating so the page
            # lays out against it: anything below the fold renders as a grey band otherwise,
            # even with captureBeyondViewport.
            browser._websocket_request('Emulation.setDeviceMetricsOverride', params={
                'width': 1400, 'height': 1600, 'deviceScaleFactor': 1, 'mobile': False,
            })
            url = werkzeug.urls.url_join(self.base_url(), url_path)
            browser.navigate_to(url, wait_stop=True)
            browser._wait_code_ok(self._appear_code(wait_for or selector), timeout=60)
            if click:
                browser._websocket_request('Runtime.evaluate', params={
                    'expression': 'document.querySelector(%s).click()' % json.dumps(click),
                })
                browser._wait_code_ok(self._appear_code(wait_after or selector), timeout=60)
            rect = browser._websocket_request('Runtime.evaluate', params={
                'expression': """JSON.stringify((function () {
                    var el = document.querySelector(%s);
                    var r = el.getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height};
                })())""" % json.dumps(selector),
                'returnByValue': True,
            })['result']['value']
            box = json.loads(rect)
            clip = {
                'x': max(box['x'] - padding, 0),
                'y': max(box['y'] - padding, 0),
                'width': box['width'] + padding * 2,
                'height': box['height'] + padding * 2,
                'scale': 1,
            }
            png = browser._websocket_request('Page.captureScreenshot', params={
                'clip': clip, 'captureBeyondViewport': True,
            }, timeout=30.0)['data']
            path = os.path.join(OUTPUT_DIR, filename)
            with open(path, 'wb') as handle:
                handle.write(base64.b64decode(png))
            self._trim(path)
            self.assertGreater(os.path.getsize(path), 2000, "%s looks empty" % filename)
            self._logger.info("Wrote %s", path)
        finally:
            browser.stop()
            self._wait_remaining_requests()

    def test_capture_manual_screenshots(self):
        self._capture(
            '/odoo/action-ems.action_ems_authorization_template/%d' % self.template.id,
            '.o_form_sheet', 'authorizations-template-form.png',
            login='doc_shot_secretary',
            wait_for=".o_form_sheet div[name='apply_on']",
        )
        self._capture(
            '/odoo/action-%d' % self.list_action.id,
            '.o_content', 'authorizations-list.png',
            login='doc_shot_secretary',
            wait_for='.o_list_renderer .o_data_row',
        )
        self._capture(
            '/odoo/action-%d' % self.wizard_action.id,
            '.modal-content', 'authorizations-send-wizard.png',
            login='doc_shot_secretary',
            wait_for=".modal-content div[name='target'] input[data-value='students']",
            click=".modal-content div[name='target'] input[data-value='students']",
            wait_after=".modal-content div[name='line_ids'] .o_data_row",
        )
        self._capture(
            '/my/gestion-matriculas', '#portal_authorizations',
            'authorizations-portal.png',
            login='doc_shot_portal',
            wait_for='#portal_authorizations .ems-auth-answer',
        )
