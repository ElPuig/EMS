# -*- coding: utf-8 -*-
"""Screenshot of a registered substitution (issue #748) for the Head of Studies manual. Same
mechanism and rules as tests/test_docs_screenshots.py (invented data in a rolled-back transaction,
Catalan, the audience's own role); run by hand:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsSubstitution' --stop-after-init -c /etc/odoo/odoo.conf"

and copy the PNG from /tmp/ems_doc_screenshots into docs/assets/head_of_studies/ by hand.
"""
from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, create_role_employee, create_role_user


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsSubstitution(HttpCase, DocsScreenshotMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hos_user = create_role_user(cls, 'head_of_studies', 'doc_shot_sub_hos', lang='ca_ES',
                                        name='Cap Estudis', email='cap.estudis@example.com')
        create_role_employee(cls, cls.hos_user, name='0000 Cap Estudis')
        cls.titular = cls.env['hr.employee'].create({'name': 'Marta Exemple Prova', 'employee_type': 'teacher'})
        cls.substitute = cls.env['hr.employee'].create({
            'name': 'Joan Exemple Model', 'employee_type': 'teacher', 'substitute_of_id': cls.titular.id})
        cls.teachers_action = cls.env['ir.actions.act_window'].create({
            'name': 'Professors', 'res_model': 'hr.employee', 'view_mode': 'list,form',
            'domain': [('id', 'in', (cls.titular | cls.substitute).ids)],
        })

    def test_capture_substitution(self):
        open_teaching_tab = ("Array.from(document.querySelectorAll('.o_notebook .nav-link'))"
                             ".find(function (link) { return link.textContent.trim() === 'Ensenyament'; }).click()")
        self._capture(
            '/odoo/action-%d/%d' % (self.teachers_action.id, self.substitute.id), '#ems-clip',
            'hos-substitucio.png', login='doc_shot_sub_hos', wait_for='.o_form_view .ribbon',
            run=[open_teaching_tab,
                 self._union_clip_js(['.o_form_sheet .ribbon', '.o_form_sheet .oe_title',
                                     ".o_field_widget[name='substitute_of_id']"])],
            wait_after=[".o_field_widget[name='substitute_of_id']", '#ems-clip'],
        )
