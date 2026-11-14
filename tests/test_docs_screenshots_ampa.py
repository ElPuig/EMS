# -*- coding: utf-8 -*-
"""Regenerates the screenshot of the tutors' AMPA manual (issue #820).

Same contract as tests/test_docs_screenshots.py: '-standard' keeps it out of every normal run,
the fixtures are invented and rolled back, and the PNG lands in /tmp/ems_doc_screenshots to be
copied into docs/assets/tutors/ by hand. Run it with:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable \
        --test-tags='*/ems:TestDocsScreenshotsAmpa' --stop-after-init -c /etc/odoo/odoo.conf"
"""
from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin
from .test_ampa_membership import AmpaMembershipFixtures


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsAmpa(AmpaMembershipFixtures, DocsScreenshotMixin, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_ampa_fixtures()
        cls.tutor.lang = 'ca_ES'
        cls.member.name = 'Laia Puig Serra'
        cls.non_member.name = 'Marc Vidal Roca'
        cls._pay(cls._order(cls._student('Nora Camps Ferrer', cls.group)))

    # The list has many more columns: the shot keeps the ones the manual talks about.
    KEEP_COLUMNS_JS = (
        "document.querySelectorAll('.o_list_table th, .o_list_table td').forEach(cell => {"
        " const name = cell.dataset.name || cell.getAttribute('name');"
        " if (!cell.classList.contains('o_list_record_selector')"
        " && !['firstname', 'lastname', 'main_group_id', 'ems_ampa_member'].includes(name)) {"
        " cell.style.display = 'none'; } })")

    def test_ampa_list(self):
        self._capture(
            '/odoo/action-ems.action_student_kanban?view_type=list', '.o_list_table',
            'tutor-ampa-list.png', login=self.tutor.login,
            wait_for=".o_data_cell[name='ems_ampa_member']",
            run=self.KEEP_COLUMNS_JS, wait_after=".o_list_table",
            marks=[(".o_list_table th[data-name='ems_ampa_member']", '1', 'text-right')])

    def test_ampa_filters(self):
        self._capture(
            '/odoo/action-ems.action_student_kanban?view_type=list', '.o_filter_menu',
            'tutor-ampa-filters.png', login=self.tutor.login,
            wait_for=".o_data_cell[name='ems_ampa_member']",
            run=["document.querySelector('.o_searchview_dropdown_toggler').click()",
                 # querySelector has no :contains, so the filter is tagged to place its mark.
                 "[...document.querySelectorAll('.o_filter_menu .o-dropdown-item')]"
                 ".find(item => item.textContent.trim() === 'Associat AMPA').id = 'ems-ampa-filter'"],
            wait_after=['.o_filter_menu', '#ems-ampa-filter'],
            marks=[('#ems-ampa-filter', '1', 'right')])
