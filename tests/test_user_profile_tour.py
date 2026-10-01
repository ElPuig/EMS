# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestUserProfileTour(HttpCase):
    """Browser side of issue #440: a real teacher's own "My Profile" screen must render
    correctly for both an ordinary self-viewing user (read-only main form/Location, hidden HR
    Settings) and an administrator (same fields stay editable/visible - developer feedback
    2026-09-10), plus the unconditionally-read-only Approvers/Manager/Coach and the new Schedule
    tab for both - none of which any other tour exercises."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.work_location = cls.env['hr.work.location'].create({
            'name': 'Test Profile Tour Office',
            'address_id': cls.env.company.partner_id.id,
        })
        # A real Area Manager/department hierarchy (tests/test_absence.py's own _create_area())
        # would work here too, but the actual derivation (department -> top-level ancestor ->
        # manager_id) is already thoroughly covered there - both tours below only need a
        # non-empty, real value on both approver fields to verify their read-only/avatar
        # rendering, so a direct assignment is simpler and avoids this dev DB's already-assigned
        # unipersonal top-level roles (hos/dhos/secretary) that _create_area() would collide with
        # outside test_absence.py's own role-clearing setUpClass.
        cls.approver = cls.env['hr.employee'].create({
            'name': 'Test Profile Tour Approver',
            'employee_type': 'teacher',
            'user_id': cls.env['res.users'].with_context(no_reset_password=True).create({
                'name': 'Test Profile Tour Approver', 'login': 'test_440_profile_tour_approver',
            }).id,
        })

    def _create_teacher_login(self, name, login, extra_group_xmlids=()):
        teacher = self.env['hr.employee'].create({
            'name': name,
            'employee_type': 'teacher',
            # Every field either tour asserts is read-only/editable needs a real, non-empty
            # value: an empty readonly Char/Many2one widget can render with zero visible height,
            # which makes the tour's own CSS-selector trigger time out even though the attribute
            # is correctly applied - found while building this tour (job_title and
            # work_location_id were originally left blank and both hit exactly this).
            'job_title': 'Test Profile Tour Job Title',
            'work_location_id': self.work_location.id,
        })
        teacher.leave_manager_id = self.approver.user_id
        teacher.attendance_manager_id = self.approver.user_id
        teacher.user_id = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': name,
            'login': login,
            'password': login,
            # Pinned so the tour's ":contains('...')" tab/label selectors do not depend on
            # whatever language this database happens to default to - see CLAUDE.md's
            # "Tour tests and language".
            'lang': 'en_US',
            'groups_id': [
                (4, self.env.ref('base.group_user').id),
                (4, self.env.ref('ems.group_teacher').id),
                *[(4, self.env.ref(xmlid).id) for xmlid in extra_group_xmlids],
            ],
        }).id
        return teacher

    def test_user_profile_tabs_tour_ordinary_user(self):
        # No extra groups: matches a real, ordinary teacher account on this dev DB (e.g.
        # caridadcastillo@elpuig.xeill.net, confirmed to hold only Teacher+Tutor). An earlier
        # version of this test suspected such an account couldn't open "My Profile" at all - a
        # false conclusion, caused by a flawed reproduction (see docs/en/developers/employees/
        # user_profile.md's "A false bug found and retracted" section) - this tour, with the
        # correct user-menu navigation, is the actual proof it works fine.
        teacher = self._create_teacher_login('Ordinary Profile Tour Teacher', 'test_440_profile_tour_ordinary')
        # To watch this tour in a real browser during development, add watch=True below.
        self.start_tour("/odoo", "ems_user_profile_tabs_ordinary_user", login='test_440_profile_tour_ordinary')
        # The tour turns off their own daily pending-tasks digest (models/shared/task_digest.py).
        self.assertFalse(teacher.user_id.ems_task_digest)

    def test_user_profile_tabs_tour_administrator(self):
        # 'ems.group_academic_admin' is used here rather than 'hr.group_hr_user' directly,
        # since that's the real EMS role an administrator holds - it already implies
        # 'hr.group_hr_user' transitively (group_academic_admin -> group_director ->
        # group_head_of_studies -> hr.group_hr_user, security/groups.xml), which is what
        # actually makes "can_edit" True - confirmed empirically, see the dev doc.
        self._create_teacher_login(
            'Administrator Profile Tour Teacher', 'test_440_profile_tour_admin',
            extra_group_xmlids=('ems.group_academic_admin',))
        self.start_tour("/odoo", "ems_user_profile_tabs_administrator", login='test_440_profile_tour_admin')
