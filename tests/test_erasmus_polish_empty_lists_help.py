from lxml import etree

from odoo.tests.common import TransactionCase, tagged

from .test_erasmus_group_mobility import ErasmusGroupMobilityCase
from .test_erasmus_satisfaction import ErasmusSatisfactionCase


@tagged('post_install', '-at_install')
class TestErasmusEmptyListsHelp(TransactionCase):
    """Issue #783 - empty lists say why, and the teacher's call screens show what matters."""

    def test_empty_lists_say_what_is_missing(self):
        for xmlid in ('action_erasmus_my_interviews', 'action_erasmus_claim',
                      'action_erasmus_mobility_to_validate', 'action_erasmus_group_mobility'):
            action = self.env.ref(f'ems.{xmlid}')
            self.assertIn('o_view_nocontent_smiling_face', action.help or '', xmlid)

    def test_teacher_call_screens(self):
        Call = self.env['ems.erasmus.call']
        listed = etree.fromstring(Call.get_view(self.env.ref('ems.view_erasmus_call_staff_list').id)['arch'])
        self.assertFalse(listed.xpath("//field[@name='is_accepting']"), "P01: the status already says it.")
        form = etree.fromstring(Call.get_view(self.env.ref('ems.view_erasmus_call_staff_form').id)['arch'])
        self.assertEqual(form.xpath("//field[@name='is_accepting']")[0].get('invisible'), '1',
                         "P02: no grey checkbox, only what the Apply button needs.")
        self.assertTrue(form.xpath("//separator[@string='Information for applicants']"))

    def test_staff_call_has_no_preparation_step(self):
        steps = self.env['ems.erasmus.call']._ems_preparation_tasks('staff')
        self.assertEqual({vals['stage'] for _c, _i, vals in steps}, {'return'})


@tagged('post_install', '-at_install')
class TestErasmusGroupFollowUpNames(ErasmusGroupMobilityCase):
    """Issue #783 (9.12) - inside its own group mobility, a participant is only their name."""

    def test_participant_name_only_in_its_mobility(self):
        Participant = self.env['ems.erasmus.group.participant']
        participant = Participant.new({'partner_id': self.students[0].id, 'group_mobility_id': self.mobility.id})
        self.assertIn(self.mobility.name, participant.display_name)
        short = participant.with_context(ems_participant_name_only=True)
        self.assertEqual(short.display_name, self.students[0].name)


@tagged('post_install', '-at_install')
class TestErasmusQualityPanelHelp(ErasmusSatisfactionCase):
    """Issue #783 (12.4) - each indicator explains itself on hover."""

    def test_each_indicator_has_its_help(self):
        panel = self.env['ems.erasmus.quality.panel'].with_user(self.technician_user).create({})
        self.assertEqual(panel.indicators_html.count('fa-info-circle'), 4)
        self.assertIn('title="Surveys answered out of the stays over."', panel.indicators_html)

