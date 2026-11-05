# -*- coding: utf-8 -*-
"""Role crawlers for the Erasmus+ roles, which EMS's own crawlers (tests/test_role_smoke_*_tour.py)
do not cover. Each class logs in as one role and runs EMS's generic crawler tour
(`ems_role_smoke_teacher`, static/tests/tours/role_smoke_common.js): it opens every window action
of that session's menu in every view mode and fails on any client error. The tour's name says
"teacher" but the crawl only depends on who is logged in."""

from odoo.tests.common import HttpCase, tagged

from odoo.addons.ems.tests.common import create_role_employee, create_role_user, mock_outgoing_email

CRAWLER_TOUR = 'ems_role_smoke_teacher'


class ErasmusRoleCrawler(HttpCase):
    # (role in ROLE_GROUP_XMLIDS, extra group xmlids, has an employee file)
    _audit_role = None
    _audit_extra_groups = ()
    _audit_employee = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        login = f'audit_crawler_{cls._audit_role}_{len(cls._audit_extra_groups)}'
        cls.crawler_user = create_role_user(cls, cls._audit_role, login, name=f'Audit {cls.__name__}')
        if cls._audit_extra_groups:
            cls.crawler_user.groups_id = [(4, cls.env.ref(xmlid).id) for xmlid in cls._audit_extra_groups]
        if cls._audit_employee:
            create_role_employee(cls, cls.crawler_user, name=f'Audit {cls.__name__}')

    def _crawl(self):
        self.start_tour('/odoo', CRAWLER_TOUR, login=self.crawler_user.login, timeout=300)


@tagged('post_install', '-at_install')
class TestAuditCrawlerErasmusCoordinator(ErasmusRoleCrawler):
    """The role "Erasmus coordinator" (a teacher): ems.group_erasmus_coordinator on a teacher."""
    _audit_role = 'teacher'
    _audit_extra_groups = ('ems.group_erasmus_coordinator',)

    def test_crawl(self):
        self._crawl()


@tagged('post_install', '-at_install')
class TestAuditCrawlerErasmusTechnician(ErasmusRoleCrawler):
    """The role "Erasmus mobility technician": ems.group_erasmus alone (may not be a teacher)."""
    _audit_role = 'erasmus'
    _audit_employee = False

    def test_crawl(self):
        self._crawl()


@tagged('post_install', '-at_install')
class TestAuditCrawlerHeadOfStudies(ErasmusRoleCrawler):
    _audit_role = 'head_of_studies'

    def test_crawl(self):
        self._crawl()


@tagged('post_install', '-at_install')
class TestAuditCrawlerDirector(ErasmusRoleCrawler):
    _audit_role = 'director'

    def test_crawl(self):
        self._crawl()


@tagged('post_install', '-at_install')
class TestAuditCrawlerErasmusEvaluator(ErasmusRoleCrawler):
    """A teacher with interviews or mobility plans to rate (the hidden group EMS manages)."""
    _audit_role = 'teacher'
    _audit_extra_groups = ('ems.group_erasmus_evaluator',)

    def test_crawl(self):
        self._crawl()


@tagged('post_install', '-at_install')
class TestAuditCrawlerGroupTeacher(ErasmusRoleCrawler):
    """A teacher who leads or accompanies a group mobility (the hidden group EMS manages)."""
    _audit_role = 'teacher'
    _audit_extra_groups = ('ems.group_erasmus_group_teacher',)

    def test_crawl(self):
        self._crawl()
