from datetime import datetime, timedelta

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import create_head_of_studies_branch, create_role_employee, create_role_user, mock_outgoing_email


class TestEmployeeAttendanceAccess(TransactionCase):
    """Issue #543 - who sees and corrects the staff's own attendance (hr.attendance), and who
    decides its correction requests: an employee their own, a Department Chief their chain of
    command (read-only), a Head of Studies their own branch (the chain of command and the area
    they manage) unless the centre lets them read everybody's, the Director and the administrator
    the whole centre. And how a past course's attendance gets archived."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Deciding a request notifies whoever filed it - see CLAUDE.md's "Email safety in tests".
        mock_outgoing_email(cls)
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_teacher_tea', name='TEA Teacher')
        cls.teacher = create_role_employee(cls, cls.teacher_user)
        # teacher -> department_chief -> head_of_studies; other_department_chief hangs from the
        # same Head of Studies and other_head_of_studies has nobody below.
        create_head_of_studies_branch(cls, 'TEA', cls.teacher)
        cls.outsider_user = create_role_user(cls, 'teacher', 'test_outsider_tea', name='TEA Outsider')
        cls.outsider = create_role_employee(cls, cls.outsider_user)
        cls.director_user = create_role_user(cls, 'director', 'test_director_tea', name='TEA Director')
        create_role_employee(cls, cls.director_user)
        cls.admin_user = create_role_user(cls, 'academic_admin', 'test_admin_tea', name='TEA Administrator')
        for user in (cls.teacher_user | cls.outsider_user | cls.director_user | cls.admin_user | cls.head_of_studies
                     | cls.other_head_of_studies | cls.department_chief | cls.other_department_chief):
            user.email = f'{user.login}@example.com'
        # Yesterday morning (07:00-10:00 UTC), never relative to the time the suite runs at: the
        # correction requests below ask for a 14:00 check-out, which must come after the check-in.
        check_in = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0) - timedelta(days=1)
        check_out = check_in + timedelta(hours=3)
        Attendance = cls.env['hr.attendance']
        cls.attendance = Attendance.create({
            'employee_id': cls.teacher.id, 'check_in': check_in, 'check_out': check_out})
        cls.outsider_attendance = Attendance.create({
            'employee_id': cls.outsider.id, 'check_in': check_in, 'check_out': check_out})
        cls.env.company.ems_hos_all_attendances = False

    def _visible(self, user):
        return self.env['hr.attendance'].with_user(user).search(
            [('id', 'in', (self.attendance | self.outsider_attendance).ids)])

    def _can_write(self, user, attendance):
        try:
            attendance.with_user(user).check_access('write')
        except AccessError:
            return False
        return True

    # --- the attendance itself -------------------------------------------------

    def test_an_employee_only_reads_their_own(self):
        self.assertEqual(self._visible(self.teacher_user), self.attendance)
        self.assertFalse(self._can_write(self.teacher_user, self.attendance))

    def test_a_department_chief_reads_their_chain_of_command_only(self):
        self.assertEqual(self._visible(self.department_chief), self.attendance)
        self.assertFalse(self._visible(self.other_department_chief), "another department's chief")
        self.assertFalse(self._can_write(self.department_chief, self.attendance), "read-only")

    def test_a_head_of_studies_manages_their_own_branch_only(self):
        self.assertEqual(self._visible(self.head_of_studies), self.attendance)
        self.assertTrue(self._can_write(self.head_of_studies, self.attendance))
        self.assertFalse(self._visible(self.other_head_of_studies), "nobody of theirs")
        self.assertFalse(self._can_write(self.other_head_of_studies, self.attendance))

    def test_the_setting_lets_every_head_of_studies_read_everybody(self):
        self.env.company.ems_hos_all_attendances = True
        self.assertTrue(self.env.ref('ems.rule_hr_attendance_hos_read_all').active)

        self.assertEqual(self._visible(self.other_head_of_studies), self.attendance | self.outsider_attendance)
        self.assertFalse(self._can_write(self.other_head_of_studies, self.attendance),
                         "to know who is in, not to correct another branch's attendance")
        self.assertEqual(self._visible(self.department_chief), self.attendance, "only the Heads of Studies")

        self.env.company.ems_hos_all_attendances = False
        self.assertFalse(self._visible(self.other_head_of_studies))

    def test_the_manager_of_an_area_manages_its_attendance(self):
        """The other way somebody is a Head of Studies' own: not above them in the chain of
        command, but the one who approves their area's attendance (hr_attendance's own rule)."""
        self.outsider.sudo().write({'attendance_manager_id': self.other_head_of_studies.id})

        self.assertEqual(self._visible(self.other_head_of_studies), self.outsider_attendance)
        self.assertTrue(self._can_write(self.other_head_of_studies, self.outsider_attendance))

    def test_the_director_and_the_administrator_manage_the_whole_centre(self):
        for user in (self.director_user, self.admin_user):
            self.assertEqual(self._visible(user), self.attendance | self.outsider_attendance)
            self.assertTrue(self._can_write(user, self.outsider_attendance))

    # --- the correction requests ------------------------------------------------

    def _request(self, attendance=None):
        attendance = attendance or self.attendance
        return self.env['ems.attendance_correction'].with_user(attendance.employee_id.user_id).create({
            'attendance_id': attendance.id, 'requested_check_out': 14.0, 'reason': 'Forgot to check out',
        })

    def test_only_the_branch_decides_a_correction_request(self):
        request = self._request()
        Correction = self.env['ems.attendance_correction']

        self.assertIn(request, Correction.with_user(self.head_of_studies).search([]))
        self.assertNotIn(request, Correction.with_user(self.other_head_of_studies).search([]))
        self.assertTrue(request.with_user(self.head_of_studies).is_approver)
        with self.assertRaises(Exception):
            request.with_user(self.other_head_of_studies).action_accept()
        request.with_user(self.head_of_studies).action_accept()
        self.assertEqual(request.state, 'accepted')

    def test_the_setting_does_not_let_another_branch_decide(self):
        self.env.company.ems_hos_all_attendances = True
        request = self._request()

        self.assertNotIn(request, self.env['ems.attendance_correction'].with_user(self.other_head_of_studies).search([]))
        self.assertFalse(request.sudo().with_user(self.other_head_of_studies)._check_is_approver())

    def test_the_manager_of_the_area_decides_too(self):
        self.outsider.sudo().write({'attendance_manager_id': self.other_head_of_studies.id})
        request = self._request(self.outsider_attendance)

        self.assertEqual(request.sudo()._find_approver(), self.other_head_of_studies,
                         "nobody above them is a Head of Studies: routed to their area's manager")
        request.with_user(self.other_head_of_studies).action_reject()
        self.assertEqual(request.state, 'rejected')

    def test_the_director_and_the_administrator_decide_any_request(self):
        request = self._request(self.outsider_attendance)

        self.assertTrue(request.with_user(self.director_user).is_approver)
        request.with_user(self.admin_user).action_accept()
        self.assertEqual(request.state, 'accepted')

    # --- the list ------------------------------------------------------------------

    def test_the_list_is_flat_for_an_employee_and_grouped_for_a_manager(self):
        action = self.env.ref('hr_attendance.hr_attendance_action')
        self.assertIn('search_default_ems_manager_date', action.context)
        self.assertNotIn('search_default_employee', action.context)
        search_view = self.env.ref('hr_attendance.hr_attendance_view_filter')

        def filters(user):
            arch = self.env['hr.attendance'].with_user(user).get_view(search_view.id, 'search')['arch']
            return {name for name in ('ems_manager_date', 'ems_manager_employee', 'groupby_name', 'employee', 'inactive')
                    if f'name="{name}"' in arch}

        # The defaults the action switches on only exist for the managers: a plain employee, who
        # only ever sees their own attendance, gets a flat list (and the native group-bys by hand).
        self.assertEqual(filters(self.teacher_user), {'groupby_name', 'employee', 'inactive'})
        self.assertEqual(filters(self.department_chief), {'ems_manager_date', 'ems_manager_employee', 'inactive'})

    # --- archiving a past course -----------------------------------------------------

    def test_a_past_course_attendance_is_archived(self):
        course = self.env.company.get_current_course_or_raise()
        start = course.date_range()[0]
        old = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id,
            'check_in': datetime.combine(start - timedelta(days=30), datetime.min.time()) + timedelta(hours=8),
            'check_out': datetime.combine(start - timedelta(days=30), datetime.min.time()) + timedelta(hours=14),
        })

        self.env['hr.attendance']._ems_archive_before_course(course)

        self.assertFalse(old.active)
        self.assertTrue(self.attendance.active, "the current course's stays")
        self.assertNotIn(old, self.env['hr.attendance'].search([('employee_id', '=', self.teacher.id)]))
        self.assertIn(old, self.env['hr.attendance'].search([('employee_id', '=', self.teacher.id), ('active', '=', False)]))

    # --- the migration's group clean-up -------------------------------------------------

    def test_stale_attendance_administrators_are_revoked(self):
        manager = self.env.ref('hr_attendance.group_hr_attendance_manager')
        # What an existing database holds: the group came with the Head of Studies' one.
        (self.head_of_studies | self.outsider_user).write({'groups_id': [(4, manager.id)]})

        revoked = self.env['res.users']._ems_revoke_stale_attendance_admin()

        self.assertIn(self.head_of_studies.login, revoked)
        self.assertNotIn(manager, self.head_of_studies.groups_id)
        self.assertIn(manager, self.director_user.groups_id, "the Director's group implies it")
        self.assertIn(manager, self.outsider_user.groups_id, "granted by hand, not a Head of Studies: kept")

    def test_a_fresh_installation_leaves_nobody_an_unearned_attendance_administrator(self):
        """hr_attendance grants its Administrator group to 'base.default_user', the (archived)
        template every new user is copied from: on a fresh installation every account would be
        born seeing everybody's attendance."""
        manager = self.env.ref('hr_attendance.group_hr_attendance_manager')
        officer = self.env.ref('hr_attendance.group_hr_attendance_officer')
        template = self.env.ref('base.default_user')
        (template | self.teacher_user).sudo().write({'groups_id': [(4, manager.id)]})

        self.env['res.users']._ems_revoke_unearned_attendance_groups()

        for user in (template.sudo(), self.teacher_user):
            self.assertFalse(user.groups_id & (manager | officer), user.login)
        self.assertFalse(self.env['res.users']._default_groups() & (manager | officer),
                         'so a brand-new user is no attendance administrator either')
        self.assertIn(manager, self.director_user.groups_id, 'the Director keeps the whole centre')
        self.assertIn(officer, self.head_of_studies.groups_id, 'a Head of Studies keeps their branch')
        self.assertIn(manager, self.env.ref('base.user_admin').groups_id)
