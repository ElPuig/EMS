from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email, next_student_id


@tagged('post_install', '-at_install')
class TestPortalViewOnly(HttpCase):
    """A minor on his own portal account only consults (res.partner._ems_portal_is_view_only,
    controllers/portal_view_only.py): schedule, profile and the messages addressed to him.
    Enrollment, authorizations, convalidations and documentation, and the native quotation/order/
    invoice pages, stay with his family."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.minor, cls.family, cls.adult = cls.env['res.partner'].create([{
            'name': 'View Only Minor', 'contact_type': 'student', 'student_id': next_student_id(),
            'email': 'view.only.minor@example.com',
            'birth_date': date.today() - relativedelta(years=15),
        }, {
            'name': 'View Only Family', 'contact_type': 'family', 'email': 'view.only.family@example.com',
        }, {
            'name': 'View Only Adult', 'contact_type': 'student', 'student_id': next_student_id(),
            'email': 'view.only.adult@example.com',
            'birth_date': date.today() - relativedelta(years=20),
        }])
        cls.env['res.partner.relation'].create({
            'left_partner_id': cls.family.id, 'type_id': cls.env.ref('ems.relation_type_father').id,
            'right_partner_id': cls.minor.id,
        })
        cls.minor_user, cls.family_user, cls.adult_user = cls.env['res.users'].with_context(
            no_reset_password=True).create([{
                'name': partner.name, 'login': login, 'password': login, 'partner_id': partner.id,
                'lang': 'en_US', 'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
            } for partner, login in (
                (cls.minor, 'test_view_only_minor'),
                (cls.family, 'test_view_only_family'),
                (cls.adult, 'test_view_only_adult'),
            )])
        course = cls.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1) \
            or cls.env['ems.course'].create({'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        subject = cls.env['ems.subject'].create({
            'code': 'TVOSUB', 'acronym': 'TVO', 'name': 'View Only Subject',
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.minor.id, 'ems_course_id': course.id,
            'order_line': [(0, 0, {'product_id': subject.product_id.id})],
        })
        cls.order.action_quotation_sent()

    def _login(self, user):
        self.authenticate(user.login, user.login)

    def _lands_on(self, url, path):
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200, url)
        self.assertTrue(response.url.split('?')[0].endswith(path), f'{url} -> {response.url}')
        return response

    def test_the_rule(self):
        self.assertTrue(self.minor._ems_portal_is_view_only())
        self.assertFalse(self.family._ems_portal_is_view_only())
        self.assertFalse(self.adult._ems_portal_is_view_only())

    def test_minor_is_sent_home_from_every_managing_page(self):
        self._login(self.minor_user)
        for url in ('/my/gestion-matriculas', '/my/documentacion', '/my/convalidaciones'):
            self._lands_on(url, '/my/home')

    def test_minor_cannot_post_managing_actions(self):
        self._login(self.minor_user)
        response = self.url_open('/my/documentacion/renew-iban',
                                 data={'csrf_token': Request.csrf_token(self)})
        self.assertTrue(response.url.endswith('/my/home'))
        self.assertFalse(self.env['ems.student.document'].search([('partner_id', '=', self.minor.id)]))

    def test_minor_keeps_the_consulting_pages(self):
        self._login(self.minor_user)
        self._lands_on('/my/asistencia', '/my/asistencia')
        self._lands_on('/my/account', '/my/account')
        self._lands_on('/my/comunicaciones', '/my/comunicaciones')

    def test_minor_home_and_menu_hide_the_managing_entries(self):
        self._login(self.minor_user)
        page = self._lands_on('/my/home', '/my/home').text
        self.assertIn('href="/my/asistencia"', page)
        for url in ('/my/gestion-matriculas', '/my/documentacion', '/my/convalidaciones'):
            self.assertNotIn(f'href="{url}"', page)

    def test_family_keeps_every_entry_and_page(self):
        """The cached header must not leak the minor's trimmed menu to anyone else."""
        self._login(self.minor_user)
        self.url_open('/my/home')
        self._login(self.family_user)
        page = self._lands_on('/my/home', '/my/home').text
        for url in ('/my/gestion-matriculas', '/my/documentacion', '/my/convalidaciones'):
            # One link in the (cached) header menu, one on the home card.
            self.assertEqual(page.count(f'href="{url}"'), 2, url)
        self._lands_on('/my/gestion-matriculas', '/my/gestion-matriculas')
        self._lands_on('/my/documentacion', '/my/documentacion')

    def test_adult_student_keeps_his_managing_pages(self):
        self._login(self.adult_user)
        self._lands_on('/my/gestion-matriculas', '/my/gestion-matriculas')
        self._lands_on('/my/documentacion', '/my/documentacion')

    def test_minor_cannot_open_his_enrollment_natively(self):
        self._login(self.minor_user)
        response = self.url_open(f'/my/orders/{self.order.id}')
        self.assertNotIn(self.order.name, response.text)
        self.assertNotIn(self.order.name, self.url_open('/my/quotes').text)
        self.url_open(f'/my/orders/{self.order.id}/decline',
                      data={'csrf_token': Request.csrf_token(self), 'decline_message': 'No'})
        self.assertEqual(self.order.state, 'sent')

    def test_minor_communications_only_show_what_is_addressed_to_him(self):
        self.order.message_post(body='Enrollment thread message', message_type='comment',
                                subtype_xmlid='mail.mt_comment')
        self.minor.message_post(body='Addressed to the minor', message_type='comment',
                                subtype_xmlid='mail.mt_comment', partner_ids=self.minor.ids)
        self._login(self.minor_user)
        page = self.url_open('/my/comunicaciones').text
        self.assertIn('Addressed to the minor', page)
        self.assertNotIn('Enrollment thread message', page)
        self._login(self.family_user)
        page = self.url_open('/my/comunicaciones').text
        self.assertIn('Addressed to the minor', page)
        self.assertIn('Enrollment thread message', page)

    def test_header_student_switcher_is_never_served_to_another_family(self):
        """The header menu is inside a t-cache block shared by every user: without the user in
        its key, a family with several children would see another family's children in the
        student switcher (same page, neither with a selected student yet)."""
        Partner = self.env['res.partner']
        father = self.env.ref('ems.relation_type_father')
        users = self.env['res.users']
        for label in ('A', 'B'):
            family = Partner.create({'name': f'Switcher Family {label}', 'contact_type': 'family'})
            for child in (1, 2):
                student = Partner.create({
                    'name': f'Switcher Child {label}{child}', 'contact_type': 'student',
                    'student_id': next_student_id(),
                    'birth_date': date.today() - relativedelta(years=12),
                })
                self.env['res.partner.relation'].create({
                    'left_partner_id': family.id, 'type_id': father.id,
                    'right_partner_id': student.id,
                })
            login = f'test_switcher_family_{label.lower()}'
            users |= self.env['res.users'].with_context(no_reset_password=True).create({
                'name': family.name, 'login': login, 'password': login, 'partner_id': family.id,
                'lang': 'en_US', 'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
            })
        self._login(users[0])
        self.assertIn('Switcher Child A1', self.url_open('/my/home').text)
        self._login(users[1])
        page = self.url_open('/my/home').text
        self.assertIn('Switcher Child B1', page)
        self.assertNotIn('Switcher Child A1', page)
