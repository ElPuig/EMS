# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Administrator/tutor/family/secretary user manuals.

Tagged '-standard' on purpose (see the NOTE below the imports) so `./test.sh` (no args) and the
CI shards never run it. Run it by hand when a documented screen changes its look:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshots' --stop-after-init -c /etc/odoo/odoo.conf"

It writes PNGs to /tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR) and they are
then copied into docs/assets/ by hand - the test process runs as the `odoo` user, which has
no write access to the repository.

Why a test and not a standalone script: every screenshot needs a logged-in browser against a
database holding the right records, and an HttpCase already provides exactly that. Crucially,
its fixtures live in a transaction that is rolled back, so the screenshots show made-up
people and nothing from this box's real data - which is what makes them publishable at all
(see CLAUDE.md, "Screenshots must never expose real personal data"). Each shot is clipped to
one element for the same reason, plus it is what makes the image readable in a manual.

The actual `_capture()`/`_trim()`/`_appear_code()` machinery lives in
`tests.common.DocsScreenshotMixin` - shared with the other per-role screenshot files (e.g.
`test_docs_screenshots_head_of_studies.py`) once a second one needed the exact same methods.
"""
import base64
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .common import (
    DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user, next_student_id,
)


# NOTE: '-standard' is required, not just historical - it is the ONLY thing keeping this class
# out of the full, unscoped './test.sh' run. The "fast" shard's own --test-tags expression
# (scripts/testing/compute_test_shards.py) is built as '/ems,-/ems:TourClassA,...' - a bare
# '/ems' selector with no explicit tag component implicitly requires the 'standard' tag (Odoo's
# own TagsSelector, odoo/tests/tag_selector.py: "including /module:class.method implicitly
# requires 'standard'"), and this file isn't a '*_tour.py' file so the tour-class exclusion list
# never catches it either. Confirmed empirically 2026-09-16: dropping '-standard' here to make
# the plain './test.sh ClassName' shorthand work (which needs that SAME 'standard' tag) would
# silently pull real-browser screenshot regeneration into every normal full-suite run instead -
# the opposite of what this file needs. Keep '-standard', and use the explicit
# '*/ems:ClassName' raw invocation above instead (see feedback_screenshot_self_verify_use_
# chromebrowser_pattern in project memory for the general gotcha).
@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshots(DocsScreenshotMixin, HttpCase):
    # A tour preparing a shot ends on a filled-in, unsaved form on purpose - that is the state
    # being photographed. Odoo's own switch for it (ChromeBrowser._handle_console skips its
    # end-of-tour dirty-form check when the test case sets this).
    allow_end_on_form = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Catalan: the manuals are read at this centre in Catalan first, so every screen is shot in
        # it - users in ca_ES, and the invented data written in Catalan too.
        cls.secretary = create_role_user(cls, 'secretary', 'doc_shot_secretary', lang='ca_ES',
                                         name='Secretaria', email='secretaria@example.com')
        create_role_employee(cls, cls.secretary, employee_type='asp', name='0000 Secretaria')

        Course = cls.env['ems.course']
        cls.course = Course.search([('is_current', '=', True)], limit=1) \
            or Course.create({'start': 2096, 'end': 2097, 'is_current': True})
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'DOC', level={
            'name': 'Formació professional',
        }, study={
            'code': 'DOC001', 'acronym': 'DAM', 'name': "Desenvolupament d'aplicacions multiplataforma",
        }, group={'acronym': 'A', 'course': 1})
        cls.subject = cls.env['ems.subject'].create({
            'code': 'DOCSUB', 'acronym': 'DSB', 'name': 'Bases de dades',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        # Invented people, on an invented group: these end up in a published manual.
        cls.students = cls.env['res.partner']
        for name in ('Marina Exemple', 'Pau Mostra', 'Nerea Prova'):
            cls.students |= cls._student(name)

        # A tutor of that same invented group, for the tutors' manual.
        cls.tutor = create_role_user(cls, 'tutor', 'doc_shot_tutor', lang='ca_ES',
                                     name='Tutor de grup', email='tutor@example.com')
        cls.group.tutor_id = create_role_employee(cls, cls.tutor, name='0000 Tutor de grup')

        cls.template = cls.env['ems.authorization.template'].create({
            'name': 'Visita al museu (novembre)',
            'apply_on_enrollment': False, 'sendable_during_course': True,
            'legal_text': "<p>Autoritzo {{student_name}}, matriculat/da a {{study_name}} el curs "
                          "{{academic_year}}, a participar en la visita al museu.</p>",
            'field_ids': [(0, 0, {'label': "Telèfon d'emergència", 'field_type': 'char',
                                  'placeholder': 'p. ex. 600 123 456'})],
        })
        # One already answered and one still pending, so the follow-up list shows both states.
        cls.env['ems.authorization'].create([{
            'partner_id': student.id, 'course_id': cls.course.id, 'template_id': cls.template.id,
        } for student in cls.students])
        answered = cls.env['ems.authorization'].search([
            ('template_id', '=', cls.template.id), ('partner_id', '=', cls.students[1].id)])
        answered.write({'status': 'yes', 'signed_document': base64.b64encode(b'%PDF-1.4 x'),
                        'signed_document_name': 'Cert_visita_museu.pdf'})

        # Not sent to anybody yet, so the assistant's preview has something to show.
        cls.pending_template = cls.env['ems.authorization.template'].create({
            'name': 'Activitat de piscina (2n trimestre)',
            'apply_on_enrollment': False, 'sendable_during_course': True,
            'legal_text': "<p>Autoritzo {{student_name}} a participar en l'activitat.</p>",
        })

        # The portal shot needs a student who can log in and who has one authorization to
        # answer, on top of a confirmed enrollment.
        cls.portal_student = cls._student('Alex Exemple')
        cls.portal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Alex Exemple', 'login': 'doc_shot_portal', 'password': 'doc_shot_portal',
            'lang': 'ca_ES', 'partner_id': cls.portal_student.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.env['ems.authorization'].create({
            'partner_id': cls.portal_student.id, 'course_id': cls.course.id,
            'template_id': cls.template.id,
        })

        # Actions of their own, scoped to these fixtures: it is what guarantees no real record
        # can appear in the shot, rather than trusting a crop.
        cls.list_action = cls.env['ir.actions.act_window'].create({
            'name': 'Seguiment',
            'res_model': 'ems.authorization',
            'view_mode': 'list,form',
            'search_view_id': cls.env.ref('ems.view_ems_authorization_search').id,
            'domain': [('template_id', '=', cls.template.id)],
        })
        # Opened on groups with the authorization preloaded, the way a form's own "Send to Students"
        # button opens it; the tour (ems_doc_shot_tutor_send) only types and picks the group.
        cls.tutor_wizard_action = cls.env['ir.actions.act_window'].create({
            'name': 'Enviar autoritzacions',
            'res_model': 'ems.authorization.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_target': 'scope',
                'default_template_ids': [(6, 0, cls.pending_template.ids)],
            },
        })
        cls.wizard_action = cls.env['ir.actions.act_window'].create({
            'name': 'Enviar autoritzacions',
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
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
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

    def test_capture_manual_screenshots(self):
        self._capture(
            '/odoo/action-ems.action_ems_authorization_template/%d' % self.template.id,
            '.o_form_sheet', 'authorizations-template-form.png',
            login='doc_shot_secretary',
            wait_for=".o_form_sheet div[name='sendable_during_course']",
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
            '/odoo/action-%d' % self.tutor_wizard_action.id,
            '.modal-content', 'authorizations-tutor-send.png',
            login='doc_shot_tutor',
            tour='ems_doc_shot_tutor_send',
        )
        self._capture(
            '/my/gestion-matriculas', '#portal_authorizations',
            'authorizations-portal.png',
            login='doc_shot_portal',
            wait_for='#portal_authorizations .ems-auth-answer',
        )
