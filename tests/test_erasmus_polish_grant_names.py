from lxml import etree

from odoo.tests.common import HttpCase, tagged

from .test_erasmus_mobility import ErasmusMobilityCase, ErasmusStaffMobilityCase
from .test_erasmus_pocket_money import ErasmusPocketMoneyCase


def form_arch(env, model, xmlid):
    return etree.fromstring(env[model].get_view(env.ref(xmlid).id, 'form')['arch'])


def block(arch, xpath):
    """The field names of a block of the form, in order."""
    return [node.get('name') for node in arch.xpath(xpath + "//field") if node.get('invisible') != '1']


@tagged('post_install', '-at_install')
class TestErasmusGrantNames(ErasmusMobilityCase):
    """Issue #790 (11.9, 5.13, 8.10) - the mobility's grant in the order the money flows."""

    def test_grant_then_payments_to_the_person(self):
        arch = form_arch(self.env, 'ems.erasmus.mobility', 'ems.view_erasmus_mobility_form')
        self.assertEqual(block(arch, "//group[@name='grant_block']"), ['grant_amount', 'provision_amount', 'grant_net'])
        self.assertEqual(block(arch, "//group[@name='payments_block']")[:3],
                         ['grant_paid', 'grant_to_receive', 'prefinancing_percent'])
        self.assertTrue(arch.xpath("//div[@name='econ_state_tag']/field[@name='econ_state']"))
        for name in ('econ_forecast', 'econ_committed', 'econ_paid', 'econ_pending'):
            self.assertFalse(arch.xpath(f"//field[@name='{name}']"), f"{name} is the project's figure.")
        self.assertTrue(arch.xpath("//details//field[@name='support_type']"), "Folded away (5.13).")

    def test_transferred_and_pending(self):
        first, _second = self._accepted()
        first.sudo().write({'state': 'preparing', 'grant_amount': 1000})
        Payment = self.env['ems.erasmus.payment'].sudo()
        Payment.create({'mobility_id': first.id, 'kind': 'prefinancing', 'amount': 800}).state = 'paid'
        Payment.create({'mobility_id': first.id, 'kind': 'final', 'amount': 200})
        first.invalidate_recordset()
        self.assertEqual((first.grant_net, first.grant_paid, first.grant_to_receive), (1000, 800, 200))


@tagged('post_install', '-at_install')
class TestErasmusGrantNamesStaff(ErasmusStaffMobilityCase):
    """Issue #790 - the teacher's grant counts in their project."""

    def test_a_teacher_grant_counts_in_the_project(self):
        """The journey's C32/C33 didn't show Marta's grant: her mobility was in another test (the staff
        journey) with another project of the same name, so the project shown never had her. In one
        database it counts like any other mobility."""
        mobility = self._validated_staff()
        mobility.sudo().write({'state': 'preparing', 'grant_amount': 1260})
        project = self.staff_vet_project.sudo()
        project.invalidate_recordset()
        self.assertIn(mobility, project.mobility_ids)
        self.assertEqual(mobility.sudo().econ_committed, 1260)
        self.assertGreaterEqual(project.committed_amount, 1260)


@tagged('post_install', '-at_install')
class TestErasmusGrantNamesGroup(ErasmusPocketMoneyCase):
    """Issue #790 (11.10, 9.14) - the group's grant with the same names."""

    def test_group_totals(self):
        participants = self._ready()
        active = participants.filtered(lambda participant: participant.state == 'active')
        grants = sum(active.mapped('grant_amount'))
        self._collective(len(active) * 100)
        self.mobility.invalidate_recordset()
        self.assertEqual(self.mobility.expense_amount, len(active) * 100)
        self.assertEqual(self.mobility.pocket_total, grants - len(active) * 100)
        self.assertEqual((self.mobility.pocket_paid_total, self.mobility.pocket_pending_total),
                         (0, self.mobility.pocket_total))
        arch = form_arch(self.env, 'ems.erasmus.group.mobility', 'ems.view_erasmus_group_mobility_form')
        page = arch.xpath("//page[@name='expenses']")[0]
        self.assertEqual(page.get('string'), "Grant and expenses")
        self.assertEqual(block(arch, "//group[@name='grant_block']"), ['grant_amount', 'expense_amount', 'pocket_total'])
        self.assertFalse(arch.xpath("//field[@name='econ_committed']"))


@tagged('post_install', '-at_install')
class TestErasmusSubsidy(ErasmusMobilityCase):
    """Issue #790 (10.3, 10.4) - the project's subsidy in one block."""

    def test_subsidy_block(self):
        arch = form_arch(self.env, 'ems.erasmus.project', 'ems.view_erasmus_project_form')
        group = arch.xpath("//group[@name='subsidy']")[0]
        self.assertEqual(group.get('string'), "Subsidy")
        self.assertEqual([node.get('name') for node in group.xpath('.//field')],
                         ['budget', 'grant_current', 'received_amount', 'to_receive_amount', 'final_grant',
                          'final_payment_date'])
        budget = arch.xpath("//group[@string='Budget']")[0]
        names = [node.get('name') for node in budget.xpath('.//field')]
        self.assertEqual(names[names.index('committed_amount') + 1], 'other_expense_amount')
        self.assertEqual(names[-1], 'available_amount')


@tagged('post_install', '-at_install')
class TestErasmusGrantNamesTour(HttpCase, ErasmusPocketMoneyCase):
    """Issue #790 - the coordinator reads the group's Grant and expenses tab and the project's subsidy."""

    def test_group_and_project(self):
        self._ready()
        self.technician_user.lang = 'en_US'
        self.start_tour(f'/odoo/action-ems.action_erasmus_group_mobility/{self.mobility.id}',
                        'ems_erasmus_polish_grant_names_group', login=self.technician_user.login)
        self.start_tour(f'/odoo/action-ems.action_erasmus_project/{self.project.id}',
                        'ems_erasmus_polish_grant_names_project', login=self.technician_user.login)
