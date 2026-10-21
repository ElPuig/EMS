# -*- coding: utf-8 -*-
"""Screenshots of the minutes and of the agreements, for the teachers' manual
(docs/{en,ca,es}/teachers/minutes.md, shots in docs/assets/teachers/) and the quality manual
(docs/{en,ca,es}/quality/actions.md, shots in docs/assets/quality/). Same mechanism and same rules as
`test_docs_screenshots.py`: tagged '-standard' (never part of a normal run), every person and record
made up inside the test's own rolled-back transaction, in a department of its own so the minutes
preload nobody real, and PNGs written to /tmp/ems_doc_screenshots, copied into docs/assets/ by hand.
Run it with:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsMinutes' --stop-after-init -c /etc/odoo/odoo.conf"
"""

from datetime import datetime

from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, create_role_employee, create_role_user, mock_outgoing_email


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsMinutes(DocsScreenshotMixin, HttpCase):
    BROWSER_TIMEZONE = 'Europe/Madrid'
    # Shots of forms being filled in end on an unsaved form on purpose.
    allow_end_on_form = True

    TEACHER = 'doc_shot_minutes_teacher'
    COMMITTEE = 'doc_shot_minutes_committee'
    RESPONSIBLE = 'doc_shot_minutes_responsible'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.env.company.partner_id.write({'lang': 'ca_ES', 'tz': 'Europe/Madrid'})
        cls.course = cls.env['ems.course'].search([('is_current', '=', True)], limit=1)
        cls.department = cls.env['hr.department'].create({'name': 'Química'})
        cls.space = cls.env['ems.space'].create({
            'code': 'DOC-LAB', 'name': 'Laboratori 2', 'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })

        def _user(role, login, name, extra_groups=()):
            user = create_role_user(cls, role, login, lang='ca_ES', tz='Europe/Madrid', name=name,
                                    email=f'{login}@example.com')
            if extra_groups:
                user.groups_id = [(4, cls.env.ref(xmlid).id) for xmlid in extra_groups]
            return user

        # A department of invented people: its chief, a seminar chief below, and the teacher who
        # writes the minutes below that, plus colleagues so the attendance has some substance.
        cls.chief = _user('department_chief', 'doc_shot_minutes_chief', 'Marina Exemple')
        cls.chief_employee = create_role_employee(cls, cls.chief, name='Marina Exemple', department_id=cls.department.id)
        cls.department.manager_id = cls.chief_employee
        cls.seminar = _user('department_chief', cls.RESPONSIBLE, 'Pau Mostra')
        cls.seminar_employee = create_role_employee(cls, cls.seminar, name='Pau Mostra', department_id=cls.department.id)
        cls.seminar_employee.parent_id = cls.chief_employee
        cls.teacher = _user('teacher', cls.TEACHER, 'Nerea Prova')
        cls.teacher_employee = create_role_employee(cls, cls.teacher, name='Nerea Prova', department_id=cls.department.id,
                                                    parent_id=cls.seminar_employee.id)
        Employee = cls.env['hr.employee']
        cls.colleagues = Employee
        for name in ('Jordi Exemple', 'Laia Mostra', 'Arnau Prova', 'Berta Exemple', 'Oriol Mostra', 'Carla Prova'):
            cls.colleagues |= Employee.create({'name': name, 'employee_type': 'teacher', 'department_id': cls.department.id,
                                               'parent_id': cls.seminar_employee.id})
        cls.committee = _user('teacher', cls.COMMITTEE, 'Biel Exemple', extra_groups=('ems.group_quality',))
        create_role_employee(cls, cls.committee, name='Biel Exemple')

        Minute = cls.env['ems.minute']
        dep_type = cls.env.ref('__import__.minute_type_dep')
        public = cls.env['hr.employee.public']
        cls.teacher_public = public.browse(cls.teacher_employee.id)

        def _minute(start, **vals):
            return Minute.create({'type_id': dep_type.id, 'department_id': cls.department.id, 'course_id': cls.course.id,
                                  'start_datetime': start, 'duration': 1.5, 'space_id': cls.space.id,
                                  'redactor_employee_id': cls.teacher_public.id, **vals})

        # Last month's meeting, approved, with agreements still open and a pending topic: what the
        # next minute carries over by itself.
        cls.previous = _minute(datetime(2026, 9, 30, 15, 0))
        cls.previous.section_value_ids.filtered(lambda value: value.required).write({'content': '<p>Tractat.</p>'})
        Action = cls.env['ems.quality.action']
        cls.agreement_open = Action.create({
            'name': 'Revisar els criteris de les pràctiques de laboratori', 'minute_id': cls.previous.id,
            'deadline_date': datetime(2026, 11, 15).date(),
            'responsible_employee_ids': [(6, 0, public.browse(cls.seminar_employee.id).ids)],
            'involved_employee_ids': [(6, 0, public.browse(cls.colleagues.ids).ids)],
            'description': '<ul><li><p>Partiu dels criteris del curs passat, a la carpeta del departament.</p></li>'
                           '<li><p>Cada professor revisa els de les seves pràctiques.</p></li></ul>',
        })
        Action.create({'name': "Actualitzar l'inventari de reactius", 'minute_id': cls.previous.id,
                       'deadline_text': 'Abans de la reunió de desembre',
                       'responsible_employee_ids': [(6, 0, public.browse(cls.colleagues[1].id).ids)]})
        cls.env['ems.minute.pending.topic'].create({'minute_id': cls.previous.id, 'name': 'Sortida a la planta de tractament d\'aigües'})
        cls.previous.action_submit()
        cls.previous.action_approve()
        cls.env['ems.quality.followup'].create({
            'action_id': cls.agreement_open.id, 'date': datetime(2026, 10, 14).date(), 'state': 'in_progress',
            'description': 'Criteris de 1r revisats; queden els de 2n.',
            'author_employee_id': public.browse(cls.seminar_employee.id).id,
        })

        # This month's meeting, being prepared: the screen most of the manual is about.
        cls.draft = _minute(datetime(2026, 11, 4, 16, 0))
        cls.draft.agenda_ids = [(0, 0, {'name': 'Programació de les sortides del segon trimestre'}),
                                (0, 0, {'name': 'Proposta de compra de material de laboratori'})]
        cls.draft.guest_ids = [(0, 0, {'name': 'Montse', 'surname': 'Exemple Puig', 'email': 'montse.exemple@example.com',
                                       'organisation': 'Tècnica de la planta de tractament', 'send_call': True})]
        # The same meeting with the NFC tag, for its attendance box.
        cls.nfc = _minute(datetime(2026, 11, 4, 16, 0), attendance_mode='nfc')

        # A meeting being held, with an agreement of its own.
        cls.held = _minute(datetime(2026, 11, 4, 16, 0))
        cls.held.action_start_meeting()
        Action.create({'name': 'Organitzar la sortida a la planta de tractament', 'minute_id': cls.held.id,
                       'deadline_date': datetime(2027, 2, 26).date(),
                       'responsible_employee_ids': [(6, 0, cls.teacher_public.ids)],
                       'involved_employee_ids': [(6, 0, public.browse(cls.colleagues[:3].ids).ids)],
                       'description': '<p>Reserva de l\'autocar i autoritzacions de les famílies.</p>'})

        # The agreements screen, scoped to these fixtures so nothing real can show up in it.
        cls.agreements_action = cls.env['ir.actions.act_window'].create({
            'name': 'Accions i acords', 'res_model': 'ems.quality.action', 'view_mode': 'list,form',
            'search_view_id': cls.env.ref('ems.view_quality_action_search').id,
            'domain': [('id', 'in', Action.search([('department_id', '=', cls.department.id)]).ids)],
            'context': {'search_default_open': 1, 'search_default_current_course': 1},
        })

    HIDE_CHATTER = "(function () { var c = document.querySelector('.o-mail-Form-chatter'); if (c) { c.style.display = 'none'; } })()"

    @classmethod
    def _room(cls, selector, pixels=44):
        """Hide the chatter and widen the left margin of `selector`, so a numbered callout fits left
        of the labels instead of covering them."""
        return cls.HIDE_CHATTER + ";document.querySelector(%r).style.paddingLeft = '%dpx'" % (selector, pixels)

    @classmethod
    def _show(cls, selector):
        """Hide the chatter and bring `selector` to the top of the form: the form scrolls inside its
        own container, so a block below the first screen would otherwise come out blank."""
        return (cls.HIDE_CHATTER + ";document.querySelector(%r).scrollIntoView({block: 'start'})" % selector)

    def _minute_url(self, minute):
        return f'/odoo/action-ems.action_minute/{minute.id}'

    def test_capture_minutes(self):
        login = self.TEACHER
        self._capture('/odoo/action-ems.action_minute', '.o_action_manager', 'actes-01-llistat.png', login=login,
                      wait_for='.o_list_view .o_data_row', max_height=420)
        self._capture(self._minute_url(self.draft), '.o_form_sheet', 'actes-02-preparar.png', login=login,
                      wait_for='.o_field_widget[name=type_id]', run=self._room('.o_form_sheet', 64), wait_after='.o_form_sheet',
                      max_height=418,
                      marks=[('label[for^=type_id]', 1, 'left'), ('label[for^=department_id]', 2, 'left'),
                             ('label[for^=start_datetime]', 3, 'left'), ('label[for^=space_id]', 4, 'left'),
                             ('label[for^=attendance_mode]', 5, 'left')])
        self._capture(self._minute_url(self.draft), '.o_notebook', 'actes-03-assistencia.png', login=login,
                      wait_for='.o_field_widget[name=guest_ids] .o_data_row', run=self._room('.o_notebook .tab-content'), wait_after='.o_notebook',
                      marks=[('label[for^=attendee_ids]', 1, 'left'), ('.o_field_widget[name=guest_ids]', 2, 'top')])
        self._capture(self._minute_url(self.nfc), '.o_notebook', 'actes-04-nfc.png', login=login,
                      wait_for="button[name=action_open_attendance_kiosk]", run=self.HIDE_CHATTER, wait_after='.o_notebook',
                      max_height=260)
        self._capture(self._minute_url(self.draft), '.o_notebook', 'actes-05-punts.png', login=login,
                      wait_for=".o_notebook a.nav-link[name=agenda]", click=".o_notebook a.nav-link[name=agenda]",
                      wait_after='.o_field_widget[name=agenda_ids] .o_data_row')
        # The Actions dropdown is an overlay outside the form, hence the body; beyond_viewport=False
        # because the dropdown closes when Chrome resizes the page.
        self._capture(self._minute_url(self.draft), 'body', 'actes-06-accions.png', login=login,
                      wait_for='.o_form_statusbar .o_ems_actions_toggle', click='.o_form_statusbar .o_ems_actions_toggle',
                      wait_after=".o_ems_actions_menu button[name='action_send_call']", max_height=420, beyond_viewport=False)
        self._capture(self._minute_url(self.held), "div[name=block_reviews]", 'actes-07-seguiment-acords.png', login=login,
                      wait_for="div[name=block_reviews] .o_ems_record_card", run=self._show("div[name=block_reviews]"),
                      wait_after="div[name=block_reviews]", beyond_viewport=False)
        self._capture(self._minute_url(self.held), "div[name=block_agreements]", 'actes-08-acords.png', login=login,
                      wait_for="div[name=block_agreements] .o_ems_record_card", run=self._show("div[name=block_agreements]"),
                      wait_after="div[name=block_agreements]", beyond_viewport=False)
        self._capture(self._minute_url(self.held), ".o_group:has(.o_field_widget[name=approver_employee_id])",
                      'actes-09-signatures.png', login=login, wait_for='.o_field_widget[name=approver_employee_id]',
                      run=self._show(".o_group:has(.o_field_widget[name=approver_employee_id])")
                      + ";document.querySelector('.o_group:has(.o_field_widget[name=approver_employee_id]) .o_inner_group:last-child').style.paddingLeft = '40px'",
                      wait_after='.o_field_widget[name=approver_employee_id]', beyond_viewport=False,
                      marks=[('label[for^=approver_employee_id]', 1, 'left')])

    def test_capture_agreements(self):
        action = self.agreements_action.id
        self._capture(f'/odoo/action-{action}', '.o_action_manager', 'acords-01-llistat.png', login=self.COMMITTEE,
                      wait_for='.o_list_view .o_data_row', max_height=360)
        form = f'/odoo/action-{action}/{self.agreement_open.id}'
        self._capture(form, '.o_form_sheet', 'acords-02-formulari.png', login=self.COMMITTEE,
                      wait_for='.o_field_widget[name=involved_employee_ids]', run=self._room('.o_form_sheet', 64), wait_after='.o_form_sheet',
                      marks=[('label[for^=responsible_employee_ids]', 1, 'left'), ('label[for^=involved_employee_ids]', 2, 'left'),
                             ('label[for^=deadline_date]', 3, 'left'), ('label[for^=department_id]', 4, 'left')])
        self._capture(form, '.o_notebook', 'acords-03-seguiment.png', login=self.COMMITTEE,
                      wait_for=".o_notebook a.nav-link[name=followup]", click=".o_notebook a.nav-link[name=followup]",
                      wait_after='.o_field_widget[name=followup_ids] .o_data_row')
        # The responsible person: the agreement is theirs to report on, not to change. With a single
        # entry the Actions dropdown is shown as that one button.
        self._capture(form, '.modal-content', 'acords-04-afegeix-seguiment.png', login=self.RESPONSIBLE,
                      wait_for=".o_form_statusbar button[name='action_add_followup']",
                      run=["document.querySelector(\".o_form_statusbar button[name='action_add_followup']\").click()",
                           "(function () { var t = document.querySelector('.modal-content .o_field_widget[name=description] textarea');"
                           " t.value = 'Criteris de 2n revisats amb tot el departament.'; t.dispatchEvent(new Event('input', {bubbles: true})); })()"],
                      wait_after=['.modal-content .o_field_widget[name=description]', '.modal-content'], padding=0)
