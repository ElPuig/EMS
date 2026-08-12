from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestEnrollmentCollectionsTour(HttpCase):

    def test_enrollment_collections_open_tour(self):
        self.start_tour("/odoo", "ems_enrollment_collections_open", login="admin")
