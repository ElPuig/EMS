from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .common import next_student_id


@tagged('post_install', '-at_install')
class TestPortalViewOnlyTour(HttpCase):
    """A view-only portal account renders in a browser - a minor's own, or a family looking at its
    adult child who authorized sharing with it: the managing entries are gone from the home and
    the header, and the consulting pages open from what is left. The routes themselves are
    covered by test_portal_view_only.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.minor, cls.family, cls.adult, cls.adult_family = cls.env['res.partner'].create([{
            'name': 'View Only Tour Minor', 'contact_type': 'student', 'student_id': next_student_id(),
            'birth_date': date.today() - relativedelta(years=15),
        }, {
            'name': 'View Only Tour Family', 'contact_type': 'family',
        }, {
            'name': 'View Only Tour Adult', 'contact_type': 'student', 'student_id': next_student_id(),
            'birth_date': date.today() - relativedelta(years=19),
        }, {
            'name': 'View Only Tour Adult Family', 'contact_type': 'family',
        }])
        cls.env['res.partner.relation'].create([{
            'left_partner_id': family.id, 'type_id': cls.env.ref('ems.relation_type_father').id,
            'right_partner_id': student.id,
        } for family, student in ((cls.family, cls.minor), (cls.adult_family, cls.adult))])
        # auth_share is a stored compute read from the student's accepted 'share' authorization;
        # set it directly, as tests/test_strike.py does.
        cls.env.cr.execute("UPDATE res_partner SET auth_share = TRUE WHERE id = %s", (cls.adult.id,))
        cls.adult.invalidate_recordset(['auth_share'])
        cls.env['res.users'].with_context(no_reset_password=True).create([{
            'name': partner.name, 'login': login, 'password': login, 'partner_id': partner.id,
            'lang': 'en_US', 'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        } for partner, login in ((cls.minor, 'test_view_only_tour_minor'),
                                 (cls.adult_family, 'test_view_only_tour_adult_family'))])

    def test_view_only_minor_tour(self):
        self.start_tour("/my/home", "ems_portal_view_only", login="test_view_only_tour_minor")

    def test_view_only_family_of_adult_tour(self):
        self.start_tour("/my/home", "ems_portal_view_only", login="test_view_only_tour_adult_family")
