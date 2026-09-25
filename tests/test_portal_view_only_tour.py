from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .common import next_student_id


@tagged('post_install', '-at_install')
class TestPortalViewOnlyTour(HttpCase):
    """A minor's own, view-only portal account renders in a browser: the managing entries are
    gone from the home and the header, and the consulting pages open from what is left. The
    routes themselves are covered by test_portal_view_only.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.minor, cls.family = cls.env['res.partner'].create([{
            'name': 'View Only Tour Minor', 'contact_type': 'student', 'student_id': next_student_id(),
            'birth_date': date.today() - relativedelta(years=15),
        }, {
            'name': 'View Only Tour Family', 'contact_type': 'family',
        }])
        cls.env['res.partner.relation'].create({
            'left_partner_id': cls.family.id, 'type_id': cls.env.ref('ems.relation_type_father').id,
            'right_partner_id': cls.minor.id,
        })
        cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': cls.minor.name, 'login': 'test_view_only_tour_minor',
            'password': 'test_view_only_tour_minor', 'partner_id': cls.minor.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def test_view_only_minor_tour(self):
        self.start_tour("/my/home", "ems_portal_view_only_minor", login="test_view_only_tour_minor")
