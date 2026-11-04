from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from odoo.addons.ems.controllers.student_card import EmsStudentCardController

from .common import create_level_study_group, next_student_id


@tagged('post_install', '-at_install')
class TestStudentCardCheck(HttpCase):
    """The public check page the QR on the back of a student card opens (issue #524): no login, only
    the least needed to compare it with the card, and nothing at all for a code that is not valid."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        __, __, group = create_level_study_group(cls, 'TSCC', study={'acronym': 'TSCCX'}, group={'course': 2})
        cls.student = cls.env['res.partner'].create({
            'firstname': 'Aina', 'lastname': 'Prova Inventada', 'contact_type': 'student',
            'student_id': '99000005678', 'main_group_id': group.id,
        })
        cls.student.sudo()._ems_ensure_card_token()
        cls.token = cls.student.sudo().ems_card_token

    def setUp(self):
        super().setUp()
        EmsStudentCardController._failed_checks.clear()
        self.addCleanup(EmsStudentCardController._failed_checks.clear)

    def _check(self, token):
        return self.url_open(f'/ems/card/{token}')

    def test_valid_card_shows_the_least(self):
        response = self._check(self.token)
        self.assertEqual(response.status_code, 200)
        page = response.text
        for expected in ('A. P. I.', '*******5678', 'TSCC', 'TSCCX', 'o_ems_check_status_valid',
                         'o_ems_check_exit_no'):
            self.assertIn(expected, page)
        for hidden in ('Aina', 'Inventada', '99000005678'):
            self.assertNotIn(hidden, page)
        self.assertIn('noindex', response.headers['X-Robots-Tag'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_revoked_card_shows_nothing(self):
        self.student.sudo()._ems_ensure_card_token(renew=True)
        page = self._check(self.token).text
        self.assertIn('o_ems_check_status_invalid', page)
        for hidden in ('P. I.', '5678', 'TSCC'):
            self.assertNotIn(hidden, page)

    def test_failed_checks_are_limited_valid_ones_are_not(self):
        with patch('odoo.addons.ems.controllers.student_card.MAX_FAILED_CHECKS', 3):
            for __ in range(5):
                self.assertEqual(self._check(self.token).status_code, 200)
            for __ in range(3):
                self.assertEqual(self._check('guessed-code').status_code, 200)
            # From then on that address gets nothing, a valid code included.
            blocked = self._check(self.token)
            self.assertEqual(blocked.status_code, 429)
            self.assertNotIn('A. P. I.', blocked.text)
