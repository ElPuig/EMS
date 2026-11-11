from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email
from .test_erasmus_group_mobility import create_group_mobility_fixtures


@tagged('post_install', '-at_install')
class TestErasmusDefaultDataTour(HttpCase):
    """Issue #780 - a Spanish-speaking Mobility technician reads in Spanish the default texts of a
    call and a group mobility created in English, from the list and the form."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        # The group mobility is created by a coordinator whose language is English.
        create_group_mobility_fixtures(cls)
        cls.technician = create_role_user(cls, 'erasmus', 'test_default_data_tour_technician', lang='es_ES')
        # The team's members are teachers too (see erasmus.md).
        cls.technician.groups_id = [(4, cls.env.ref('ems.group_teacher').id)]

    def test_call_default_data_tour(self):
        now = fields.Datetime.now()
        self.env['ems.erasmus.call'].with_context(lang='en_US').create({
            'name': 'Test default data tour call', 'date_open': now, 'date_close': now + timedelta(days=10)})
        self.start_tour('/odoo/action-ems.action_erasmus_call', 'ems_erasmus_default_data_call',
                        login=self.technician.login)

    def test_group_default_data_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_group_mobility', 'ems_erasmus_default_data_group',
                        login=self.technician.login)
