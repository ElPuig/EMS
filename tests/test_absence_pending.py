from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_head_of_studies_branch, create_role_employee, create_role_user, mock_outgoing_email


class TestAbsencePending(TransactionCase):
    """ems.absence_pending (issue #509): absences the teacher's chiefs (issue #604), the Head of
    Studies or their Deputy enter on a teacher's behalf until the teacher files the real
    request."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_teacher_tap', name='TAP Teacher')
        cls.teacher = create_role_employee(cls, cls.teacher_user)
        # Sets cls.head_of_studies, cls.department_chief (the teacher's own chief),
        # cls.other_department_chief and cls.other_head_of_studies.
        create_head_of_studies_branch(cls, 'TAP', cls.teacher)
        cls.other_teacher = cls.env['hr.employee'].create({
            'name': 'TAP Teacher Of Another Branch', 'employee_type': 'teacher',
            'parent_id': cls.other_head_of_studies.employee_ids.id,
        })
        cls.director = create_role_user(cls, 'director', 'test_director_tap', name='TAP Director')
        director_employee = create_role_employee(cls, cls.director)
        # Issue #569: a member of the management team (e.g. the Secretary) reports to the Director,
        # but teaches in a department of the Head of Studies' area: the Head of Studies reaches
        # them through that department, the other Head of Studies doesn't. Created before the
        # hierarchy below is set: an area's manager is re-parented by the department cascade.
        area = cls.env['hr.department'].create({
            'name': 'TAP Area', 'manager_id': cls.head_of_studies.employee_ids.id})
        teaching_department = cls.env['hr.department'].create({'name': 'TAP Teaching Department', 'parent_id': area.id})
        cls.management_teacher = cls.env['hr.employee'].create({
            'name': 'TAP Management Team Teacher', 'employee_type': 'teacher',
            'department_id': teaching_department.id,
        })
        (cls.head_of_studies | cls.other_head_of_studies).employee_ids.parent_id = director_employee
        cls.management_teacher.parent_id = director_employee
        cls.leave_type = cls.env.ref('ems.leave_type_justified')
        cls.Pending = cls.env['ems.absence_pending']
        cls.monday = cls.Pending.get_local_today() + timedelta(days=7)
        while cls.monday.weekday() != 0:
            cls.monday += timedelta(days=1)

    def _utc(self, day, hour):
        return self.Pending._utc_bounds(day, 0.0, hour)[1]

    def _pending(self, employee=None, hour_from=9.0, hour_to=11.0, day=None, user=None):
        day = day or self.monday
        Pending = self.Pending.with_user(user) if user else self.Pending
        return Pending.create({
            'employee_id': (employee or self.teacher).id,
            'date_from': self._utc(day, hour_from),
            'date_to': self._utc(day, hour_to),
        })

    def _leave(self, day=None, hour_from=None, hour_to=None, employee=None, user=None):
        day = day or self.monday
        vals = {
            'employee_id': (employee or self.teacher).id,
            'holiday_status_id': self.leave_type.id,
            'request_date_from': day,
            'request_date_to': day,
            'ems_submitted': True,
            'ems_responsible_declaration': True,
        }
        if hour_from is None:
            vals['ems_full_day'] = True
        else:
            vals.update({'ems_full_day': False, 'request_hour_from': hour_from, 'request_hour_to': hour_to})
        Leave = self.env['hr.leave'].with_user(user) if user else self.env['hr.leave']
        return Leave.create(vals)

    # --- Access ---------------------------------------------------------------------------------

    def test_head_of_studies_manages_their_own_teachers(self):
        pending = self._pending(user=self.head_of_studies)

        self.assertEqual(self.Pending.with_user(self.head_of_studies).search([('id', '=', pending.id)]), pending)
        pending.with_user(self.head_of_studies).note = 'Known in advance'
        pending.with_user(self.head_of_studies).unlink()
        self.assertFalse(pending.exists())

    def test_head_of_studies_cannot_reach_another_branch(self):
        pending = self._pending()

        self.assertFalse(self.Pending.with_user(self.other_head_of_studies).search([('id', '=', pending.id)]))
        with self.assertRaises(AccessError):
            self._pending(user=self.head_of_studies, employee=self.other_teacher)

    def test_head_of_studies_reaches_a_teacher_of_their_area_reporting_elsewhere(self):
        """Issue #569: the hierarchy alone never reached the management team, who report to the
        Director: the department they teach in, under an area the user manages, does."""
        self.assertEqual(self.management_teacher.parent_id, self.director.employee_ids)
        pending = self._pending(user=self.head_of_studies, employee=self.management_teacher)

        self.assertEqual(self.Pending.with_user(self.head_of_studies).search([('id', '=', pending.id)]), pending)
        self.assertFalse(self.Pending.with_user(self.other_head_of_studies).search([('id', '=', pending.id)]))
        with self.assertRaises(AccessError):
            self._pending(user=self.other_head_of_studies, employee=self.management_teacher)

    def test_director_reaches_every_branch(self):
        mine, theirs = self._pending(), self._pending(employee=self.other_teacher)

        self.assertEqual(self.Pending.with_user(self.director).search([('id', 'in', (mine | theirs).ids)]), mine | theirs)

    def test_technical_administrator_reaches_every_teacher(self):
        """Not in the org chart at all, as 'admin' usually is not."""
        system = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'TAP System Admin', 'login': 'test_system_tap',
            'groups_id': [(4, self.env.ref('base.group_user').id), (4, self.env.ref('base.group_system').id)],
        })
        mine, theirs = self._pending(), self._pending(user=system, employee=self.other_teacher)

        self.assertEqual(self.Pending.with_user(system).search([('id', 'in', (mine | theirs).ids)]), mine | theirs)
        offered = self.env['hr.employee'].with_user(system).search(self.Pending.with_user(system)._domain_employee_id())
        self.assertIn(self.teacher, offered)
        self.assertIn(self.other_teacher, offered)

    def test_department_chief_manages_their_own_teachers(self):
        """Issue #604: a teacher's own Department Chief announces their absences too."""
        pending = self._pending(user=self.department_chief)

        self.assertEqual(self.Pending.with_user(self.department_chief).search([('id', '=', pending.id)]), pending)
        pending.with_user(self.department_chief).note = 'Phoned in'
        pending.with_user(self.department_chief).unlink()
        self.assertFalse(pending.exists())

    def test_department_chief_cannot_reach_another_department(self):
        pending = self._pending()

        self.assertFalse(self.Pending.with_user(self.other_department_chief).search([('id', '=', pending.id)]))
        with self.assertRaises(AccessError):
            self._pending(user=self.other_department_chief)
        with self.assertRaises(AccessError):
            self._pending(user=self.department_chief, employee=self.other_teacher)

    def test_chiefs_reach_the_teachers_of_their_own_department(self):
        """Through the department itself, as the department form sets it up: both its Department
        Chief and its Seminar Chief reach every teacher of it, a member of the management team who
        reports to the Director included."""
        chief = create_role_user(self, 'department_chief', 'test_dept_chief_tap', name='TAP Dept Chief')
        seminar_chief = create_role_user(self, 'department_chief', 'test_seminar_chief_tap', name='TAP Seminar Chief')
        department = self.env['hr.department'].create({'name': 'TAP Department'})
        member = self.env['hr.employee'].create({
            'name': 'TAP Department Member', 'employee_type': 'teacher', 'department_id': department.id})
        department.write({
            'manager_id': create_role_employee(self, chief).id,
            'seminar_chief_id': create_role_employee(self, seminar_chief, department_id=department.id).id,
        })
        self.assertEqual(member.parent_id, seminar_chief.employee_ids)
        # A member of the management team (e.g. the Secretary) who teaches in this department
        # reports to the Director, out of both chiefs' branch: the department still reaches them.
        director = self.director.employee_ids
        management_member = self.env['hr.employee'].create({
            'name': 'TAP Department Secretary', 'employee_type': 'teacher',
            'department_id': department.id, 'parent_id': director.id})
        management_member.parent_id = director

        for user in (chief, seminar_chief):
            self._pending(user=user, employee=management_member)
            pending = self._pending(user=user, employee=member)
            self.assertEqual(self.Pending.with_user(user).search([('id', '=', pending.id)]), pending)
            offered = self.env['hr.employee'].with_user(user).search(self.Pending.with_user(user)._domain_employee_id())
            self.assertIn(member, offered)
            self.assertIn(management_member, offered)
            self.assertNotIn(self.teacher, offered)
            with self.assertRaises(AccessError):
                self._pending(user=user)

    def test_teachers_have_no_access(self):
        self._pending()
        with self.assertRaises(AccessError):
            self.Pending.with_user(self.teacher_user).search([])
        with self.assertRaises(AccessError):
            self._pending(user=self.teacher_user)

    def test_department_chief_menu_shows_only_expected_absences_under_management(self):
        """Management opens to a chief for Expected absences alone, and "Absences" becoming a
        dropdown for them must keep their own absences one click away."""
        # Not self.department_chief: setting the fixture's parent_id directly hands them
        # hr_holidays' approver group, which the department cascade would take back.
        chief = self.other_department_chief
        self.assertFalse(chief.has_group('hr_holidays.group_hr_holidays_responsible'))
        visible = self.env['ir.ui.menu'].with_user(chief)._visible_menu_ids()

        self.assertIn(self.env.ref('ems.menu_absence_pending').id, visible)
        self.assertIn(self.env.ref('hr_holidays.menu_hr_holidays_management').id, visible)
        self.assertIn(self.env.ref('hr_holidays.hr_leave_menu_my').id, visible)
        self.assertNotIn(self.env.ref('ems.menu_absence_requested').id, visible)
        self.assertNotIn(self.env.ref('ems.menu_absence_pending').id,
                         self.env['ir.ui.menu'].with_user(self.teacher_user)._visible_menu_ids())

    def test_end_must_come_after_start(self):
        with self.assertRaises(ValidationError):
            self._pending(hour_from=11.0, hour_to=9.0)

    def test_defaults_to_today_school_day_in_company_timezone(self):
        pending = self.Pending.with_user(self.head_of_studies).new({})
        today = self.Pending.get_local_today()

        self.assertEqual(pending.date_from, self._utc(today, 8.0))
        self.assertEqual(pending.date_to, self._utc(today, 15.0))

    # --- Linking to the teacher's own request --------------------------------------------------

    def test_the_teacher_filing_an_overlapping_absence_links_it(self):
        pending = self._pending()

        leave = self._leave(user=self.teacher_user)

        self.assertEqual(pending.state, 'linked')
        self.assertEqual(pending.leave_id, leave)

    def test_a_partial_absence_links_only_what_it_overlaps(self):
        morning, afternoon = self._pending(hour_from=9.0, hour_to=11.0), self._pending(hour_from=15.0, hour_to=17.0)

        leave = self._leave(hour_from=10.0, hour_to=12.0)

        self.assertEqual(morning.leave_id, leave)
        self.assertEqual(afternoon.state, 'pending')

    def test_another_day_or_another_teacher_is_not_linked(self):
        pending = self._pending()

        self._leave(day=self.monday + timedelta(days=1))
        self._leave(employee=self.other_teacher)

        self.assertEqual(pending.state, 'pending')

    def test_moving_an_absence_onto_a_pending_one_links_it(self):
        pending = self._pending(day=self.monday + timedelta(days=1))
        leave = self._leave()
        self.assertEqual(pending.state, 'pending')

        leave.write({'request_date_from': self.monday + timedelta(days=1),
                     'request_date_to': self.monday + timedelta(days=1)})

        self.assertEqual(pending.leave_id, leave)

    def test_the_link_is_final(self):
        """Once the teacher has filed it, the entry has done its job: whatever becomes of the
        real request afterwards, it never goes back to pending."""
        tuesday = self.monday + timedelta(days=1)
        refused, deleted = self._pending(), self._pending(day=tuesday)
        refused_leave, deleted_leave = self._leave(), self._leave(day=tuesday)

        refused_leave.action_refuse()
        deleted_leave.unlink()

        self.assertEqual(refused.state, 'linked')
        self.assertEqual(deleted.state, 'linked')
        self.assertFalse(deleted.leave_id)

    def test_a_linked_entry_can_no_longer_be_edited(self):
        pending = self._pending()
        self._leave()

        with self.assertRaises(ValidationError):
            pending.with_user(self.head_of_studies).date_to = self._utc(self.monday, 13.0)

    # --- What the guard duty board reads -------------------------------------------------------

    def test_local_hours_are_clipped_to_each_day(self):
        tuesday = self.monday + timedelta(days=1)
        pending = self.Pending.create({
            'employee_id': self.teacher.id,
            'date_from': self._utc(self.monday, 12.0),
            'date_to': self._utc(tuesday, 10.5),
        })

        self.assertEqual(pending._get_local_hours(self.monday), (12.0, 24.0))
        self.assertEqual(pending._get_local_hours(tuesday), (0.0, 10.5))
        self.assertIsNone(pending._get_local_hours(self.monday - timedelta(days=1)))
        self.assertIsNone(pending._get_local_hours(tuesday + timedelta(days=1)))

    def test_an_entry_ending_at_midnight_does_not_touch_the_next_day(self):
        pending = self._pending(hour_from=20.0, hour_to=24.0)

        self.assertEqual(pending._get_local_hours(self.monday), (20.0, 24.0))
        self.assertIsNone(pending._get_local_hours(self.monday + timedelta(days=1)))

    def test_board_reads_pending_entries_only(self):
        pending = self._pending()
        course = self.env['ems.course']

        self.assertEqual(course._get_guard_duty_absence_intervals(self.monday, self.teacher),
                         {self.teacher.id: [(9.0, 11.0, 'pending')]})

        leave = self._leave(hour_from=10.0, hour_to=12.0)
        self.assertEqual(pending.leave_id, leave)
        self.assertEqual(course._get_guard_duty_absence_intervals(self.monday, self.teacher),
                         {self.teacher.id: [(10.0, 12.0, 'pending')]})

        leave.action_refuse()
        self.assertEqual(dict(course._get_guard_duty_absence_intervals(self.monday, self.teacher)), {})

    def test_teacher_picker_only_offers_the_own_branch(self):
        Pending = self.Pending.with_user(self.head_of_studies)
        offered = self.env['hr.employee'].with_user(self.head_of_studies).search(Pending._domain_employee_id())

        self.assertIn(self.teacher, offered)
        self.assertIn(self.management_teacher, offered)
        self.assertNotIn(self.other_teacher, offered)
