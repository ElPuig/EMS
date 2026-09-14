# -*- coding: utf-8 -*-

from odoo.tests import HttpCase, tagged

from .common import create_level_study, create_role_user


@tagged('post_install', '-at_install')
class TestGroupPublicScheduleTour(HttpCase):
    """Issue #453 - browser coverage for the public schedule links on the group and study forms.
    Generation, triggers and the public routes themselves are covered by
    tests/test_group_public_schedule.py."""

    def test_group_public_schedule_tour(self):
        teacher = create_role_user(self, 'teacher', 'test_teacher_group_public_schedule_tour')
        self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'Tour Public Schedule TGPT'})
        self.start_tour("/odoo", "ems_group_public_schedule", login=teacher.login)

    def test_study_public_schedule_tour(self):
        teacher = create_role_user(self, 'teacher', 'test_teacher_study_public_schedule_tour')
        level, study = create_level_study(self, 'TSPT')
        self.env['ems.group'].create({'level_id': level.id, 'study_id': study.id, 'course': 1, 'acronym': 'A'})
        self.start_tour("/odoo", "ems_study_public_schedule", login=teacher.login)
