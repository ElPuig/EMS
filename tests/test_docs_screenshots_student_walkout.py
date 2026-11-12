# -*- coding: utf-8 -*-
"""Regenerates the screenshots of the student walkout manuals (issue #800): the students' and
families' portal, the tutor's abort wizard and the Head of Studies' closed call. Tagged
'-standard' on purpose - see the NOTE in test_docs_screenshots.py. Run it by hand:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsStudentWalkout' --stop-after-init -c /etc/odoo/odoo.conf"

Writes the PNGs to /tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR); copy them into
docs/assets/{families,tutors,head_of_studies}/ by hand afterwards. Fictitious people only.
"""
from datetime import timedelta

from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, mock_outgoing_email
from .test_student_walkout import create_walkout_fixtures, end_phase, open_walkout


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsStudentWalkout(DocsScreenshotMixin, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_walkout_fixtures(cls, 'DOC')
        names = {cls.delegate: 'Pau Exemple Soler', cls.subdelegate: 'Laia Exemple Vidal',
                 cls.classmate: 'Nil Exemple Puig', cls.offline: 'Joana Exemple Mas',
                 cls.family: 'Marta Vidal Exemple'}
        for partner, name in names.items():
            partner.name = name
        cls.tutor.write({'name': 'Jordi Tutor Exemple', 'lang': 'ca_ES'})
        cls.group.tutor_id.name = 'Jordi Tutor Exemple'
        cls.head_of_studies.write({'name': 'Rosa Cap Exemple', 'lang': 'ca_ES'})
        students = cls.env['res.users'].search([('partner_id', 'in', [p.id for p in names])])
        students.write({'lang': 'ca_ES'})
        cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': cls.family.name, 'login': 'doc_shot_walkout_family', 'password': 'doc_shot_walkout_family',
            'lang': 'ca_ES', 'partner_id': cls.family.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.env.flush_all()
        # Three calls of the group, one per state shown: voting, joining (a minor joined, her
        # family still has to ratify it) and closed (waiting for the Head of Studies).
        notes = "Vaga general d'estudiants convocada pel Sindicat d'Estudiants."
        cls.voting = open_walkout(cls, days=9, notes=notes)
        cls.joining = open_walkout(cls, days=8, notes=notes)
        for student in (cls.delegate, cls.subdelegate):
            cls.joining._ems_portal_vote(student, 'yes')
        cls.joining._ems_portal_join(cls.subdelegate, True)
        cls.closed = open_walkout(cls, days=7, notes=notes)
        for student in (cls.delegate, cls.classmate):
            cls.closed._ems_portal_vote(student, 'yes')
        cls.closed._ems_portal_join(cls.delegate, True)
        cls.closed._ems_portal_join(cls.classmate, True)
        cls.closed._ems_portal_ratify(cls.family, cls.closed.line_ids.filtered(
            lambda line: line.student_id == cls.classmate), True)
        end_phase(cls.closed)
        # end_phase() moves the end to a second ago; show the phase it really had.
        cls.closed.join_until = cls.closed.join_start + timedelta(days=1)

    def _login(self, partner):
        return self.env['res.users'].search([('partner_id', '=', partner.id)]).login

    def test_capture_portal(self):
        self._capture('/my/vagues/nova', '.o_ems_portal_walkout_new', 'walkout-portal-new.png',
                      login=self._login(self.delegate))
        self._capture(f'/my/vagues/{self.voting.id}', '.o_ems_portal_walkout', 'walkout-portal-vote.png',
                      login=self._login(self.classmate))
        self._capture(f'/my/vagues/{self.joining.id}', '.o_ems_portal_walkout', 'walkout-portal-join.png',
                      login=self._login(self.subdelegate))
        self._capture('/my/vagues', '.o_ems_portal_walkout_family', 'walkout-portal-family.png',
                      login='doc_shot_walkout_family')

    def test_capture_tutor_abort(self):
        self._capture(f'/odoo/action-ems.action_student_walkout/{self.voting.id}', '.modal-content',
                      'tutor-walkout-abort.png', login=self.tutor.login,
                      wait_for='.o_form_view .o_form_statusbar',
                      click="button[name='action_open_reject_wizard']", wait_after='.modal .alert-warning')

    def test_capture_head_of_studies_closed(self):
        # beyond_viewport=False: resizing the page for a taller shot would close the dropdown.
        self._capture(f'/odoo/action-ems.action_student_walkout/{self.closed.id}', '.o_action_manager',
                      'hos-walkout-closed.png', login=self.head_of_studies.login,
                      wait_for='.o_form_view .o_ems_actions_toggle',
                      click='.o_ems_actions_toggle', wait_after='.o_ems_actions_menu',
                      beyond_viewport=False, max_height=860)
