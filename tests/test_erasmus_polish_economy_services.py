from lxml import etree

from odoo.tests import Form
from odoo.tests.common import HttpCase, tagged

from .test_erasmus_pocket_money import ErasmusPocketMoneyCase


@tagged('post_install', '-at_install')
class TestErasmusEconomyServices(ErasmusPocketMoneyCase):
    """Issue #791 - services paid by the centre and project expenses."""

    def test_one_question_for_whom(self):
        """11.2: a group mobility or participants, and the other answer emptied."""
        self._ready()
        invoice = self._collective(500)
        self.assertEqual(invoice.covers, 'group', "Existing group invoices answer it already.")
        form = Form(self.env['ems.erasmus.invoice'].with_user(self.technician_user))
        form.name = 'F-791'
        form.amount = 100
        form.project_id = self.project
        self.assertEqual(form.covers, 'participants')
        form.covers = 'group'
        form.group_mobility_id = self.mobility
        form.covers = 'participants'
        self.assertFalse(form.group_mobility_id, "Never both: it would count twice.")
        form.covers = 'group'
        form.group_mobility_id = self.mobility
        self.assertEqual(form.save().unassigned_amount, 0)

    def test_the_secretary_enters_a_group_service(self):
        """11.11: the Secretary enters the services paid by the centre, a group's too."""
        self._ready()
        invoice = self.env['ems.erasmus.invoice'].with_user(self.secretary_user).create({
            'name': 'F-791-SEC', 'amount': 1000, 'project_id': self.project.id, 'covers': 'group',
            'group_mobility_id': self.mobility.id})
        self.assertEqual(invoice.group_mobility_id.with_user(self.secretary_user).name, self.mobility.name)
        self.mobility.invalidate_recordset()
        self.assertEqual(self.mobility.expense_amount, 1000)

    def test_names_warning_history_and_tabs(self):
        """11.1, 11.7: named by what they do, a warning when nobody is covered, the history shown and the
        project's expenses next to its services."""
        Invoice = self.env['ems.erasmus.invoice']
        form = etree.fromstring(Invoice.get_view(self.env.ref('ems.view_erasmus_invoice_form').id)['arch'])
        self.assertEqual(form.get('string'), "Service paid by the centre")
        self.assertTrue(form.xpath("//div[contains(@class, 'alert-warning')][contains(@invisible, 'mobility_ids')]"))
        self.assertTrue(form.xpath('//chatter'))
        payment = etree.fromstring(self.env['ems.erasmus.payment'].get_view(
            self.env.ref('ems.view_erasmus_payment_form').id)['arch'])
        self.assertTrue(payment.xpath('//chatter'))
        project = etree.fromstring(self.env['ems.erasmus.project'].get_view(
            self.env.ref('ems.view_erasmus_project_form').id)['arch'])
        pages = [page.get('name') for page in project.xpath('//notebook/page')]
        self.assertEqual(pages[pages.index('invoices') + 1], 'expenses')
        self.assertFalse(project.xpath("//page[@name='economy']//field[@name='expense_ids']"))
        menus = self.env.ref('ems.menu_erasmus_section_finances').with_context(lang='en_US').child_id
        self.assertEqual(set(menus.mapped('name')), {'Grant payments', 'Services paid by the centre', 'Project expenses'})


@tagged('post_install', '-at_install')
class TestErasmusEconomyServicesTour(HttpCase, ErasmusPocketMoneyCase):
    """Issue #791 - the Secretary enters a service paid by the centre for a group mobility."""

    def test_secretary_enters_a_service(self):
        self._ready()
        self.secretary_user.lang = 'en_US'
        self.start_tour('/odoo/action-ems.action_erasmus_invoice/new', 'ems_erasmus_polish_economy_services',
                        login=self.secretary_user.login)
        invoice = self.env['ems.erasmus.invoice'].search([('name', '=', 'F-TOUR-791')])
        self.assertEqual((invoice.covers, invoice.group_mobility_id), ('group', self.mobility))
