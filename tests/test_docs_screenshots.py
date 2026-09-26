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
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .test_convalidation import (close_convalidation_period, open_convalidation_period,
                                 set_convalidation_period)
from .common import (
    DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user,
    mock_outgoing_email, next_student_id,
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
    # The invented school day the tutors' justification manual is shot on.
    JUSTIFIED_DAY = date(2026, 3, 2)

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

        cls._setup_justifications()
        cls._setup_google_credentials()

    @classmethod
    def _setup_justifications(cls):
        """Two classes of the invented group on JUSTIFIED_DAY - one taught by the tutor, one by a
        colleague - with every student absent, and a justification already saved for Pau."""
        # Marking a line as a miss queues family notifications.
        mock_outgoing_email(cls)
        colleague = cls.env['hr.employee'].create({'name': 'Laia Docent', 'employee_type': 'teacher'})
        space = cls.env['ems.space'].create({
            'code': 'DOC-A', 'name': 'Aula 21',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        miss = cls.env.ref('ems.attendance_status_miss')
        for teacher, start_time in ((cls.group.tutor_id, 9.0), (colleague, 11.0)):
            template = cls.env['ems.attendance_template'].create({
                'teacher_ids': [(6, 0, teacher.ids)], 'study_ids': [(6, 0, cls.study.ids)],
                'subject_id': cls.subject.id, 'group_ids': [(6, 0, cls.group.ids)],
                'start_date': date(2020, 1, 1), 'end_date': date(2099, 12, 31),
            })
            schedule = cls.env['ems.attendance_schedule'].create({
                'attendance_template_id': template.id, 'weekday': str(cls.JUSTIFIED_DAY.weekday()),
                'start_time': start_time, 'end_time': start_time + 1, 'space_id': space.id,
                'student_ids': [(6, 0, cls.students.ids)],
            })
            session = cls.env['ems.attendance_session_header'].create({
                'attendance_schedule_id': schedule.id, 'date': cls.JUSTIFIED_DAY,
                'mode': 'scheduled', 'session_teacher_id': teacher.id,
            })
            for line in session.attendance_session_line_ids:
                line.status_id = miss

        pau = cls.students[1]
        cls.justification = cls.env['ems.attendance_justification'].create({
            'teacher_id': cls.group.tutor_id.id, 'student_id': pau.id,
            'start_date': datetime(2026, 3, 2, 7, 0), 'end_date': datetime(2026, 3, 2, 13, 0),
            'attendance_session_line_ids': [(6, 0, cls.env['ems.attendance_session_line'].search([
                ('student_id', '=', pau.id), ('date', '=', cls.JUSTIFIED_DAY)]).ids)],
            'notes': 'Visita mèdica',
        })
        cls.justification.attachment_ids = cls.env['ir.attachment'].create({
            'name': 'Justificant_metge.pdf', 'datas': base64.b64encode(b'%PDF-1.4 x'),
            'res_model': 'ems.attendance_justification', 'res_id': cls.justification.id,
        })
        cls.justification_action = cls.env['ir.actions.act_window'].create({
            'name': 'Justificants', 'res_model': 'ems.attendance_justification',
            'view_mode': 'list,form', 'domain': [('student_id', 'in', cls.students.ids)],
        })

    @classmethod
    def _setup_google_credentials(cls):
        """A credentials PDF for every invented student (plus a DNI the tutor must not see), and a
        students list scoped to them, for the tutors' Google credentials manual."""
        cls.env['ems.student.document'].create([{
            'partner_id': student.id, 'doc_type': 'google_credentials', 'status': 'approved',
            'doc_file': base64.b64encode(b'%PDF-1.4 x'),
            'doc_file_name': f'Credencials_Google_{student.student_id}.pdf',
        } for student in cls.students] + [{
            'partner_id': cls.students[0].id, 'doc_type': 'dni', 'status': 'approved',
        }])
        # An active Google account, so the TAC team gets the reset button on Marina's form.
        cls.students[0].student_email = 'marina.exemple@example.com'
        cls.tac = create_role_user(cls, 'tac', 'doc_shot_tac', lang='ca_ES',
                                   name='Coordinació TAC', email='tac@example.com')
        cls.student_list_action = cls.env['ir.actions.act_window'].create({
            'name': 'Estudiants', 'res_model': 'res.partner', 'view_mode': 'list,form',
            'domain': [('id', 'in', cls.students.ids)],
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

    def test_capture_tutor_justification_screenshots(self):
        self._capture(
            '/odoo/action-%d' % self.justification_action.id,
            '.o_content', 'justificants-01-llista.png',
            login='doc_shot_tutor',
            wait_for='.o_list_renderer .o_data_row',
        )
        self._capture(
            '/odoo/action-%d/new' % self.justification_action.id,
            '.o_form_sheet', 'justificants-02-nou.png',
            login='doc_shot_tutor',
            tour='ems_doc_shot_tutor_justification',
        )
        # Third tab of the notebook: Affected sessions, Affected teachers, Attached files, Notes.
        self._capture(
            '/odoo/action-%d/%d' % (self.justification_action.id, self.justification.id),
            '.o_form_sheet', 'justificants-03-adjunts.png',
            login='doc_shot_tutor',
            wait_for='.o_form_sheet .o_notebook',
            click='.o_notebook .nav-item:nth-child(3) .nav-link',
            wait_after=".o_field_widget[name='attachment_ids'] .o_data_row",
        )

    def test_capture_tutor_google_credentials_screenshots(self):
        self._capture(
            '/odoo/action-%d/%d' % (self.student_list_action.id, self.students[0].id),
            '.o_notebook', 'credencials-google-01-documentacio.png',
            login='doc_shot_tutor',
            wait_for=".o_notebook .nav-link[name='documentation']",
            click=".o_notebook .nav-link[name='documentation']",
            wait_after=".o_field_widget[name='document_ids'] .o_data_row a",
        )
        # The Actions dropdown is an overlay outside the list's own container, hence the body.
        self._capture(
            '/odoo/action-%d' % self.student_list_action.id,
            'body', 'credencials-google-02-accions.png',
            login='doc_shot_tutor',
            tour='ems_doc_shot_tutor_google_credentials',
            max_height=380,
        )
        # Written to the same folder; this one goes to docs/assets/admin/.
        self._capture(
            '/odoo/action-%d/%d' % (self.student_list_action.id, self.students[0].id),
            '.o_form_view', 'compte-google-alumne-capcalera.png',
            login='doc_shot_tac',
            wait_for=".o_form_statusbar button[name='action_reset_google_password']",
            max_height=200,
        )
        # The same header seen by the group's tutor: the reset button and nothing else (#490).
        self._capture(
            '/odoo/action-%d/%d' % (self.student_list_action.id, self.students[0].id),
            '.o_form_view', 'credencials-google-03-restablir.png',
            login='doc_shot_tutor',
            wait_for=".o_form_statusbar button[name='action_reset_google_password']",
            max_height=200,
        )
        # Pau has no Google account yet: the tutor gets the create button instead (#513).
        self._capture(
            '/odoo/action-%d/%d' % (self.student_list_action.id, self.students[1].id),
            '.o_form_view', 'credencials-google-04-crear.png',
            login='doc_shot_tutor',
            wait_for=".o_form_statusbar button[name='action_create_google_account']",
            max_height=200,
        )

    def test_capture_convalidation_screenshots(self):
        """Issue #276 - the Head of Studies' request form and list (a request resolved and ready
        to be validated), and the portal page."""
        self.level.allows_convalidation = True
        subjects = self.subject | self.env['ems.subject'].create([{
            'code': code, 'acronym': acronym, 'name': name, 'study_ids': [(6, 0, self.study.ids)],
        } for code, acronym, name in (
            ('DOCSUB2', 'DSP', 'Programació'),
            ('DOCSUB3', 'DSI', 'Sistemes informàtics'),
            ('DOCSUB4', 'DFO', 'Formació i orientació laboral'),
        )])
        head_of_studies = create_role_user(self, 'head_of_studies', 'doc_shot_hos', lang='ca_ES',
                                           name="Cap d'estudis", email='capestudis@example.com')
        create_role_employee(self, head_of_studies, name="0000 Cap d'estudis")
        request = self.env['ems.convalidation'].create({
            'student_id': self.portal_student.id, 'requester_id': self.portal_student.id,
            'study_id': self.study.id, 'course_id': self.course.id, 'basis': 'prior_studies',
            'student_notes': "Vaig cursar el CFGM de Sistemes microinformàtics i xarxes.",
            'line_ids': [(0, 0, {'subject_id': subject.id}) for subject in subjects[1:]],
            'attachment_ids': [(0, 0, {'name': 'Certificat_academic_SMX.pdf',
                                       'datas': base64.b64encode(b'%PDF-1.4 x')})],
        })
        request.line_ids[0].sudo().write({'state': 'granted', 'grade': 8,
                                          'resolution_notes': 'Mòdul equivalent a SMX'})
        request.line_ids[1].sudo().write({'state': 'rejected',
                                          'resolution_notes': "No acreditat a l'expedient"})
        list_action = self.env['ir.actions.act_window'].create({
            'name': 'Convalidacions',
            'res_model': 'ems.convalidation',
            'view_mode': 'list,form',
            'domain': [('id', '=', request.id)],
        })
        self._capture(
            '/odoo/action-ems.action_convalidation/%d' % request.id,
            '.o_form_sheet', 'convalidations-form.png',
            login='doc_shot_hos',
            wait_for=".o_form_sheet div[name='line_ids'] .o_data_row",
        )
        self._capture(
            '/odoo/action-%d' % list_action.id,
            '.o_content', 'convalidations-list.png',
            login='doc_shot_hos',
            wait_for='.o_list_renderer .o_data_row',
        )
        # The request period, open while the form is captured (the default one may well be
        # closed the day this runs), then closed for the notice that replaces it.
        open_convalidation_period(self.env)
        self._capture(
            '/my/convalidaciones?new=1', '.o_ems_convalidation_new',
            'convalidations-portal-new.png',
            login='doc_shot_portal',
            wait_for='#convalidation_new_body.show',
        )
        self._capture(
            '/my/convalidaciones', '.o_ems_convalidation_request',
            'convalidations-portal-request.png',
            login='doc_shot_portal',
        )
        close_convalidation_period(self.env)
        self._capture(
            '/my/convalidaciones', '.o_ems_convalidation_closed',
            'convalidations-portal-closed.png',
            login='doc_shot_portal',
        )
        # The period itself, in Settings (goes to docs/assets/admin/).
        create_role_user(self, 'settings_admin', 'doc_shot_settings_admin', lang='ca_ES',
                         name='Administrador')
        set_convalidation_period(self.env, (1, 10, 8.0), (31, 3, 23 + 59 / 60))
        self._capture(
            '/odoo/action-ems.action_settings', '#convalidation_period',
            'convalidations-settings.png',
            login='doc_shot_settings_admin',
        )
