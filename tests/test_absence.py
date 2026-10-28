# -*- coding: utf-8 -*-

import base64
from datetime import timedelta
from unittest.mock import patch

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval

from ..models.employees.absence import TIME_OFF_GROUP_XMLIDS
from .common import create_role_employee, create_role_user, make_working_day, mock_outgoing_email

ATRI_OVERDUE = 'ems.mail_activity_absence_atri_overdue'

# The nine absence types seeded by data/cat/hr.leave.type.csv, with the native flags each one
# needs: (xmlid, requires a supporting document).
EXPECTED_LEAVE_TYPES = (
    ('ems.leave_type_sick_leave', True),
    ('ems.leave_type_health', False),
    ('ems.leave_type_medical_appointment', True),
    ('ems.leave_type_invasive_test', True),
    ('ems.leave_type_menstrual_flexibility', True),
    ('ems.leave_type_training', True),
    ('ems.leave_type_justified', True),
    ('ems.leave_type_service_assignment', True),
    ('ems.leave_type_atri', False),
)


class TestAbsence(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        # role_hos/role_dhos/role_secretary are unipersonal and the working database may already
        # have them assigned to a real employee - clear them so these tests stay self-contained
        # (same precaution as tests/test_department.py).
        for xmlid in ('ems.role_hos', 'ems.role_dhos', 'ems.role_secretary'):
            cls.env.ref(xmlid).sudo().with_context(ems_syncing_roles=True).write({'employee_ids': [(5, 0, 0)]})
        cls.env.company.director_id = False

    def _create_employee(self, name, department=False, with_user=False):
        vals = {'name': name, 'employee_type': 'teacher'}
        if department:
            vals['department_id'] = department.id
        if with_user:
            vals['user_id'] = self.env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': f'{name.lower().replace(" ", "_")}@absence.test',
            }).id
        return self.env['hr.employee'].create(vals)

    def _create_area(self, label, role='hos', area='academic'):
        """A top-level department with its Area Manager, plus one child department under it."""
        top = self.env['hr.department'].create({
            'name': f'Test Top {label}', 'is_top_level': True,
            'top_level_area': area, 'top_level_role': role,
        })
        manager = self._create_employee(f'Test Area Manager {label}', with_user=True)
        top.manager_id = manager.id
        child = self.env['hr.department'].create({'name': f'Test Child {label}', 'parent_id': top.id})
        return top, child, manager

    # --- Absence type catalogue -------------------------------------------------------------

    def test_leave_types_are_seeded(self):
        for xmlid, support_document in EXPECTED_LEAVE_TYPES:
            leave_type = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(leave_type, f'{xmlid} should be seeded by data/cat/hr.leave.type.csv')
            self.assertEqual(leave_type.support_document, support_document, xmlid)

    def test_leave_types_are_requested_in_hours(self):
        for xmlid, _support_document in EXPECTED_LEAVE_TYPES:
            self.assertEqual(self.env.ref(xmlid).request_unit, 'hour', xmlid)

    def test_leave_types_never_require_an_allocation(self):
        """The 15 h/course health allowance warns, it never blocks - so no type may be gated on
        an hr.leave.allocation, whose semantics are exactly that block."""
        for xmlid, _support_document in EXPECTED_LEAVE_TYPES:
            self.assertEqual(self.env.ref(xmlid).requires_allocation, 'no', xmlid)

    def test_leave_types_are_approved_by_the_employees_approver(self):
        for xmlid, _support_document in EXPECTED_LEAVE_TYPES:
            self.assertEqual(self.env.ref(xmlid).leave_validation_type, 'manager', xmlid)

    def test_absence_types_have_a_short_name(self):
        """The full legal wording belongs in the request form, where the employee reads what
        they are declaring. Everywhere else - lists, the calendar - shows what the Apps Script
        showed: the text up to the colon."""
        self.assertEqual(self.env.ref('ems.leave_type_atri').ems_short_name, 'ATRI')
        self.assertEqual(self.env.ref('ems.leave_type_health').ems_short_name, 'Health')

    def test_a_type_without_a_colon_keeps_its_whole_name(self):
        leave_type = self.env.ref('ems.leave_type_justified')

        self.assertEqual(leave_type.ems_short_name, leave_type.name)

    # --- Derived approver -------------------------------------------------------------------

    def test_leave_manager_is_the_top_level_area_manager(self):
        _top, child, manager = self._create_area('VET', role='dhos')
        employee = self._create_employee('Test Teacher (VET)', child)

        self.assertEqual(employee.leave_manager_id, manager.user_id)

    def test_leave_manager_resolves_through_nested_departments(self):
        top, child, manager = self._create_area('Nested')
        grandchild = self.env['hr.department'].create({'name': 'Test Grandchild', 'parent_id': child.id})
        employee = self._create_employee('Test Teacher (Nested)', grandchild)

        self.assertEqual(employee.leave_manager_id, manager.user_id)
        self.assertTrue(top.is_top_level)

    def test_the_area_manager_is_the_head_of_their_own_absence(self):
        """Issue #693: an Area Manager validates the Head's side of their own absence, and
        Direction reviews it afterwards like any other. Their attendance corrections still go
        to the Director: the issue is about absences only."""
        top, _child, manager = self._create_area('SelfApproval')
        director = self._create_employee('Test Director (SelfApproval)', with_user=True)
        self.env.company.director_id = director.id
        manager.department_id = top.id

        self.assertEqual(manager.leave_manager_id, manager.user_id)
        self.assertEqual(manager.attendance_manager_id, director.user_id)

        # A Director managing an area has nobody above them to send their corrections to.
        self.env.company.director_id = manager.id
        manager._compute_leave_manager()
        self.assertFalse(manager.attendance_manager_id)

    def test_leave_manager_is_not_the_department_chief(self):
        """Native hr_holidays derives leave_manager_id from parent_id, which in EMS is the
        Seminar Chief / Department Chief - the wrong person for an absence request."""
        _top, child, manager = self._create_area('NotChief')
        chief = self._create_employee('Test Chief (NotChief)', child, with_user=True)
        child.manager_id = chief.id
        employee = self._create_employee('Test Teacher (NotChief)', child)

        self.assertEqual(employee.parent_id, chief)
        self.assertEqual(employee.leave_manager_id, manager.user_id)

    def test_leave_manager_resyncs_when_the_area_manager_changes(self):
        top, child, _manager = self._create_area('Resync')
        employee = self._create_employee('Test Teacher (Resync)', child)
        replacement = self._create_employee('Test New Area Manager (Resync)', with_user=True)

        top.manager_id = replacement.id

        self.assertEqual(employee.leave_manager_id, replacement.user_id)

    def test_a_department_chief_never_keeps_the_approver_group(self):
        """Writing 'parent_id' makes hr_holidays hand its approver group to whoever that field
        names - the Department or Seminar Chief here - before EMS has said who really approves.
        Nothing native takes it back afterwards, so four Chiefs were still holding it on the
        development database, able to read every absence reason and document in their area."""
        approver_group = self.env.ref('hr_holidays.group_hr_holidays_responsible')
        top, child, _manager = self._create_area('ChiefGroup')
        chief = self._create_employee('Test Chief (ChiefGroup)', with_user=True)
        self._create_employee('Test Teacher (ChiefGroup)', child)

        child.manager_id = chief.id
        top.manager_id = self._create_employee('Test New Manager (ChiefGroup)', with_user=True).id

        self.assertNotIn(approver_group, chief.user_id.groups_id)

    def test_leave_manager_resyncs_for_archived_employees_too(self):
        """An archived employee left pointing at its old approver is not harmless: hr_holidays
        grants its approver group from any write of 'leave_manager_id', while
        '_ems_sync_time_off_groups' only counts active employees when deciding who is entitled
        to keep it - so the group kept coming back to people who no longer approve anything."""
        _top, child, manager = self._create_area('ArchivedResync')
        employee = self._create_employee('Test Archived (Resync)', child)
        employee.action_archive()
        replacement = self._create_employee('Test New Area Manager (Resync)', with_user=True)

        _top.manager_id = replacement.id

        self.assertEqual(employee.leave_manager_id, replacement.user_id)
        self.assertNotEqual(manager, replacement, 'sanity: the Area Manager really changed')

    def test_leave_manager_empty_without_a_top_level_ancestor(self):
        orphan = self.env['hr.department'].create({'name': 'Test Orphan Department'})
        employee = self._create_employee('Test Teacher (Orphan)', orphan)

        self.assertFalse(employee.leave_manager_id)

    def test_leave_manager_empty_without_a_department(self):
        self.assertFalse(self._create_employee('Test Teacher (No Department)').leave_manager_id)

    # --- Attendance approver mirrors the absence approver (issue #440) ----------------------

    def test_attendance_manager_matches_leave_manager(self):
        _top, child, manager = self._create_area('AttendanceSync')
        employee = self._create_employee('Test Teacher (AttendanceSync)', child)

        self.assertEqual(employee.attendance_manager_id, manager.user_id)
        self.assertEqual(employee.attendance_manager_id, employee.leave_manager_id)

    def test_attendance_manager_resyncs_when_the_area_manager_changes(self):
        top, child, _manager = self._create_area('AttendanceResync')
        employee = self._create_employee('Test Teacher (AttendanceResync)', child)
        replacement = self._create_employee('Test New Area Manager (AttendanceResync)', with_user=True)

        top.manager_id = replacement.id

        self.assertEqual(employee.attendance_manager_id, replacement.user_id)

    def test_attendance_manager_empty_without_a_department(self):
        self.assertFalse(self._create_employee('Test Teacher (No Department, Attendance)').attendance_manager_id)

    # --- Access control ---------------------------------------------------------------------

    def test_head_of_studies_manages_every_request(self):
        officer = self.env.ref('hr_holidays.group_hr_holidays_user')
        self.assertIn(officer, self.env.ref('ems.group_head_of_studies').trans_implied_ids)

    def test_absence_menu_opens_on_my_time_off(self):
        """Clicking "Absences" lands on the employee's own list: the native dashboard duplicates
        it for no benefit, and its parent level ("My Time") would be left holding nothing."""
        root = self.env.ref('hr_holidays.menu_hr_holidays_root')
        my_leaves = self.env.ref('hr_holidays.hr_leave_menu_my')

        self.assertEqual(my_leaves.parent_id, root)
        self.assertEqual(root.action.id, self.env.ref('hr_holidays.hr_leave_action_my').id)
        self.assertFalse(self.env.ref('hr_holidays.hr_leave_menu_new_request').active)
        self.assertFalse(self.env.ref('hr_holidays.menu_hr_holidays_my_leaves').active)

    def test_my_absences_are_not_grouped_by_month(self):
        """Odoo groups them by month by default, which buries a handful of requests under a fold
        per month on a list that is short and already sorted by date."""
        context = self.env.ref('hr_holidays.hr_leave_action_my').context

        self.assertNotIn('search_default_group_date_from', context)

    def test_centre_wide_calendar_is_for_absence_managers_only(self):
        """It shows who is missing across the centre - which is what an absence manager needs
        and what an employee's own record rules would empty out anyway."""
        overview = self.env.ref('hr_holidays.menu_hr_holidays_dashboard')

        self.assertEqual(overview.groups_id, self.env.ref('hr_holidays.group_hr_holidays_responsible'))

    def test_absences_menu_hangs_from_employee_attendances(self):
        self.assertEqual(
            self.env.ref('hr_holidays.menu_hr_holidays_root').parent_id,
            self.env.ref('hr_attendance.menu_hr_attendance_root'))

    def _create_user(self, login, groups=()):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': f'{login}@absence.test',
            'groups_id': [Command.link(group.id) for group in groups],
        })

    def test_installing_holidays_does_not_leave_everyone_an_officer(self):
        """hr_holidays grants its Administrator group to 'base.default_user', which Odoo
        propagates to every existing user at install time - on this database that made all 37
        internal users able to read every colleague's absence reason."""
        officer = self.env.ref('hr_holidays.group_hr_holidays_user')
        plain = self._create_user('plain_teacher', [self.env.ref('ems.group_teacher'), officer])

        self.env['res.users']._ems_sync_time_off_groups()

        self.assertNotIn(officer, plain.groups_id)
        self.assertNotIn(self.env.ref('hr.group_hr_user'), plain.groups_id,
                         'and the HR Officer group the officer group implied goes with it')
        self.assertIn(self.env.ref('ems.group_teacher'), plain.groups_id, 'their own role stays')

    def test_the_user_template_keeps_no_time_off_group(self):
        """'base.default_user' is the record hr_holidays actually grants its Administrator group
        to, and 'res.users._default_groups' copies that template's groups onto every user
        created from then on - so leaving it alone meant every new account was born able to read
        every colleague's absence reason and supporting document. It is an archived user, and
        'res.groups.users' skips archived ones, which is exactly how it was missed."""
        template = self.env.ref('base.default_user')
        template.sudo().write({'groups_id': [
            Command.link(self.env.ref(xmlid).id) for xmlid in TIME_OFF_GROUP_XMLIDS]})

        self.env['res.users']._ems_sync_time_off_groups()

        for xmlid in TIME_OFF_GROUP_XMLIDS:
            self.assertNotIn(self.env.ref(xmlid), template.sudo().groups_id, xmlid)
        self.assertFalse(
            self.env['res.users']._default_groups() & self.env.ref('hr_holidays.group_hr_holidays_user'),
            'so a brand-new user is not an officer either')

    def test_an_archived_employee_is_not_spared_either(self):
        """Same reason, and the way back is the role hierarchy: an archived account that comes
        back gets its groups from '_sync_security_groups', not from what was left on it."""
        officer = self.env.ref('hr_holidays.group_hr_holidays_user')
        former = self._create_user('former_teacher', [self.env.ref('ems.group_teacher'), officer])
        former.action_archive()

        self.env['res.users']._ems_sync_time_off_groups()

        self.assertNotIn(officer, former.sudo().groups_id)

    def test_restricting_time_off_groups_spares_entitled_users(self):
        head = self._create_user('head_of_studies', [self.env.ref('ems.group_head_of_studies')])

        self.env['res.users']._ems_sync_time_off_groups()

        self.assertIn(self.env.ref('hr_holidays.group_hr_holidays_user'), head.groups_id)

    def test_the_secretariat_is_not_an_absence_approver(self):
        """Approving absences is not something the secretariat does as a body - only the ASP
        area's own manager does, and they get it from the approval relation below."""
        secretary = self._create_user('secretariat', [self.env.ref('ems.group_secretary')])

        self.env['res.users']._ems_sync_time_off_groups()

        self.assertNotIn(self.env.ref('hr_holidays.group_hr_holidays_responsible'), secretary.groups_id)
        self.assertNotIn(self.env.ref('hr_holidays.group_hr_holidays_user'), secretary.groups_id)

    def test_whoever_approves_absences_gets_the_approver_group(self):
        """Who approves is not a role anybody holds: it is whoever an employee names as their
        leave_manager_id. Granting from that relation keeps it exact as Area Managers change."""
        _top, child, manager = self._create_area('ApproverGroup', role='secretary', area='asp')
        self._create_employee('Test Teacher (ApproverGroup)', child)

        self.env['res.users']._ems_sync_time_off_groups()

        self.assertIn(self.env.ref('hr_holidays.group_hr_holidays_responsible'), manager.user_id.groups_id)

    def test_absences_menu_opens_directly_for_an_employee(self):
        """Odoo renders a menu entry as a link only when it has no children the reader can see
        (web.NavBar.SectionsMenu), so an employee must see none of them for one click to land on
        their own list."""
        root = self.env.ref('hr_holidays.menu_hr_holidays_root')
        employee = self._create_user('plain_for_menu', [self.env.ref('ems.group_teacher')])
        self.env['res.users']._ems_sync_time_off_groups()

        self.assertTrue(root.action, 'the parent menu carries the action itself')
        self.assertEqual(root.action.id, self.env.ref('hr_holidays.hr_leave_action_my').id)
        children = root.child_id.filtered('active')
        self.assertTrue(children, 'sanity: the manager-facing entries still exist')
        for child in children:
            self.assertTrue(child.groups_id, f'"{child.name}" is visible to everyone')
            self.assertFalse(child.groups_id & employee.groups_id,
                             f'an employee sees "{child.name}", so the parent stays a dropdown')

    def test_restricting_time_off_groups_is_idempotent(self):
        first = self.env['res.users']._ems_sync_time_off_groups()
        second = self.env['res.users']._ems_sync_time_off_groups()

        self.assertFalse(second, f'a second pass must revoke nothing (first revoked {first})')

    def test_teacher_does_not_manage_other_requests(self):
        implied = self.env.ref('ems.group_teacher').trans_implied_ids
        self.assertNotIn(self.env.ref('hr_holidays.group_hr_holidays_user'), implied)
        self.assertNotIn(self.env.ref('hr_holidays.group_hr_holidays_responsible'), implied)


class TestAbsenceRequest(TransactionCase):
    """The centre's own absence rules on top of hr_holidays' request: the flags seeded from the
    absence type, the hour computation and the health allowance."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        # _monday() below needs a real course window - a fresh DB (CI, unlike this box's own dev
        # DB) has no "current course" configured at all, so this must be set explicitly rather
        # than assumed, matching every other test that needs one (test_guard_duty_board.py,
        # test_course_transition.py, test_year_record.py...).
        cls.course = cls.env.company.current_course_id
        if not cls.course:
            cls.course = cls.env['ems.course'].create({'start': 1999, 'end': 2000})
        cls.env.company.current_course_id = cls.course
        cls.type_health = cls.env.ref('ems.leave_type_health')
        cls.type_sick_leave = cls.env.ref('ems.leave_type_sick_leave')
        cls.type_training = cls.env.ref('ems.leave_type_training')
        cls.type_atri = cls.env.ref('ems.leave_type_atri')
        cls.type_justified = cls.env.ref('ems.leave_type_justified')
        cls.full_day_hours = cls.env.company._ems_full_day_hours()
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Absent Teacher', 'employee_type': 'teacher',
        })

    def _monday(self):
        """A Monday comfortably inside the current course's window, so the health allowance
        computation (which filters on that window) sees the requests these tests create."""
        window = self.env.company.current_course_id.date_range()
        day = window[0] + timedelta(days=30)
        while day.weekday() != 0:
            day += timedelta(days=1)
        return day

    def _create_leave(self, leave_type, date_from, date_to=None, hour_from=None, hour_to=None, **overrides):
        vals = {
            'employee_id': self.employee.id,
            'holiday_status_id': leave_type.id,
            'request_date_from': date_from,
            'request_date_to': date_to or date_from,
            # What the "Send request" button does: a request that has not been sent cannot be
            # saved at all, which is what stops Odoo's autosave filing one nobody asked for.
            'ems_submitted': True,
            'ems_responsible_declaration': True,
        }
        # "Whole day?" is the only control: unticked means a day plus times, ticked means a
        # range of whole days. Passing hours implies a partial absence; otherwise the flag is
        # left to whatever the absence type seeds, exactly as the form does.
        if hour_from is not None:
            vals.update({'ems_full_day': False,
                         'request_hour_from': hour_from, 'request_hour_to': hour_to})
        vals.update(overrides)
        return self.env['hr.leave'].create(vals)

    # --- Flags seeded from the absence type -------------------------------------------------

    def test_type_catalogue_flags(self):
        self.assertFalse(self.type_sick_leave.ems_counts_hours, 'sick leave stays out of the monthly report')
        self.assertTrue(self.type_atri.ems_counts_hours, 'ATRI is the biggest contributor to the monthly report')
        self.assertTrue(self.type_health.ems_counts_health_allowance)
        self.assertFalse(self.type_atri.ems_counts_health_allowance, 'only Salut consumes the 15 h allowance')
        self.assertTrue(self.type_health.ems_full_day_default)
        self.assertTrue(self.type_atri.ems_needs_atri)

    def test_request_seeds_its_flags_from_the_type(self):
        leave = self._create_leave(self.type_atri, self._monday())

        self.assertTrue(leave.ems_counts_hours)
        self.assertTrue(leave.ems_needs_atri)
        self.assertFalse(leave.ems_full_day, 'ATRI is not a whole-day type by default')

    def test_flags_are_seeded_even_when_another_one_is_set_on_create(self):
        """Regression: these three flags once shared a compute method, and Odoo skips such a
        method entirely for a record created with any one of its fields already set. Creating a
        request with "Whole day?" ticked therefore left the ATRI and monthly-report flags off,
        with nothing failing - the absence just went missing from the totals."""
        leave = self._create_leave(self.type_atri, self._monday(), ems_full_day=True)

        self.assertTrue(leave.ems_needs_atri, 'ATRI is derived from the type, not from the form')
        self.assertTrue(leave.ems_counts_hours)
        self.assertTrue(leave.ems_full_day, 'and the value that was passed in still wins')

    def test_manager_can_override_a_seeded_flag(self):
        """Employees miscategorise, so the manager corrects the flag by hand - exactly what the
        Apps Script's own 'Suma Hores?' column allowed."""
        leave = self._create_leave(self.type_atri, self._monday())
        leave.ems_counts_hours = False

        self.assertFalse(leave.ems_counts_hours)

    def test_direction_check_starts_undone(self):
        self.assertEqual(self._create_leave(self.type_justified, self._monday()).ems_direction_state, 'not_done')

    def test_responsible_declaration_is_enforced(self):
        """Required for every absence type, not just some: it is the employee asserting the
        reason they gave is true."""
        for leave_type in (self.type_health, self.type_justified, self.type_atri):
            with self.assertRaises(Exception, msg=leave_type.name):
                self._create_leave(leave_type, self._monday(), ems_responsible_declaration=False)

    def test_an_unsent_request_cannot_be_saved(self):
        """Odoo saves a form on its own after a while, even an untouched one - so merely opening
        the request screen to look at it would otherwise file a real absence."""
        with self.assertRaises(Exception):
            self._create_leave(self.type_justified, self._monday(), ems_submitted=False)

    # --- Hour computation -------------------------------------------------------------------

    def test_whole_day_is_worth_a_full_day(self):
        """However many lessons the employee actually had: a teacher with a single hour that day
        still consumes a whole day."""
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        self.assertEqual(leave.number_of_hours, self.full_day_hours)
        self.assertEqual(leave.number_of_days, 1)

    def test_partial_absence_counts_real_clock_time(self):
        leave = self._create_leave(self.type_justified, self._monday(), hour_from=9.0, hour_to=11.0)

        self.assertEqual(leave.number_of_hours, 2.0)

    def test_partial_absence_is_rounded_to_quarters(self):
        # 09:00 to 10:50 is 1 h 50 min, which rounds to 1 h 45 min.
        leave = self._create_leave(self.type_justified, self._monday(), hour_from=9.0, hour_to=10.0 + 50 / 60)

        self.assertEqual(leave.number_of_hours, 1.75)

    def test_multi_day_absence_counts_a_full_day_each(self):
        monday = self._monday()
        leave = self._create_leave(self.type_sick_leave, monday, monday + timedelta(days=2),
                                   ems_full_day=True)

        self.assertEqual(leave.number_of_hours, 3 * self.full_day_hours)

    def test_multi_day_absence_skips_the_weekend(self):
        """Monday to the following Monday is 8 calendar days but only 6 working ones."""
        monday = self._monday()
        leave = self._create_leave(self.type_sick_leave, monday, monday + timedelta(days=7),
                                   ems_full_day=True)

        self.assertEqual(leave.number_of_hours, 6 * self.full_day_hours)

    def test_a_range_needs_the_whole_day_flag(self):
        """Odoo collapses a request that carries times down to a single day
        (hr_leave.py::_compute_date_from_to), so asking for several days means ticking
        "Whole day?" - which is exactly what several days are."""
        monday = self._monday()
        leave = self._create_leave(self.type_justified, monday, monday + timedelta(days=1),
                                   hour_from=9.0, hour_to=11.0)

        self.assertEqual(leave.request_date_to, monday, 'collapsed back to one day')
        self.assertEqual(leave.number_of_hours, 2.0)

    def test_no_absence_type_is_preselected(self):
        """Odoo ticks the first available type on a new request. Here the type is the legal
        ground the employee is declaring, so it has to be a deliberate choice."""
        defaults = self.env['hr.leave'].default_get(['holiday_status_id'])

        self.assertFalse(defaults.get('holiday_status_id'))

    def test_a_new_request_asks_for_the_times(self):
        """"Whole day?" starts unticked, which is what makes the form ask for a start and an end
        time - the original form always did, as two full datetimes."""
        monday = self._monday()
        leave = self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': self.type_justified.id,
            'request_date_from': monday,
            'request_date_to': monday,
        })

        self.assertFalse(leave.ems_full_day)
        self.assertTrue(leave.request_unit_hours, 'so Odoo shows the hour fields')

    def test_whole_day_switches_off_the_hour_fields(self):
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        self.assertFalse(leave.request_unit_hours, 'a whole day is entered as dates, not times')

    def test_half_days_are_never_offered(self):
        """Odoo's other unit toggle. The centre has no use for it and the form does not show
        it, so no request should ever carry it."""
        self.assertFalse(self._create_leave(self.type_justified, self._monday()).request_unit_half)

    def test_whole_day_copies_the_start_date_to_the_end_date(self):
        """A whole-day absence is usually a single day, so the employee only has to touch the
        end date when they want several."""
        monday = self._monday()
        leave = self.env['hr.leave'].new({
            'employee_id': self.employee.id,
            'holiday_status_id': self.type_justified.id,
            'ems_full_day': True,
            'request_date_from': monday,
        })

        leave._onchange_ems_full_day_dates()

        self.assertEqual(leave.request_date_to, monday)

    def test_only_the_centres_own_absence_types_are_offered(self):
        """Odoo ships four absence types of its own (plus one from hr_holidays_attendance) that
        are none of the nine the original form offered."""
        self.env['hr.leave.type']._ems_deactivate_native_types()

        self.assertEqual(self.env['hr.leave.type'].search_count([]), 9)

    def test_deactivating_native_types_is_idempotent(self):
        self.env['hr.leave.type']._ems_deactivate_native_types()

        self.assertFalse(self.env['hr.leave.type']._ems_deactivate_native_types())

    def test_manager_can_still_fix_the_type_after_approval(self):
        """Employees pick the wrong type often enough that the manager has to be able to correct
        it afterwards, which Odoo's own readonly would prevent."""
        leave = self._create_leave(self.type_justified, self._monday())

        self.assertTrue(leave.is_absence_manager, 'admin is an officer')

    def test_only_direction_sets_the_direction_check(self):
        """The column shows in every absence list now, including the employee's own, so hiding
        the field in the view is not a barrier - the model has to be one."""
        owner = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Absence Owner', 'login': 'absence_owner@absence.test',
            'groups_id': [Command.link(self.env.ref('base.group_user').id),
                          Command.link(self.env.ref('ems.group_teacher').id)],
        })
        self.employee.user_id = owner.id
        leave = self._create_leave(self.type_justified, self._monday())

        with self.assertRaises(AccessError):
            leave.with_user(owner).write({'ems_direction_state': 'done'})

    def test_direction_can_set_the_direction_check(self):
        leave = self._create_leave(self.type_justified, self._monday())

        leave.ems_direction_state = 'done'

        self.assertEqual(leave.ems_direction_state, 'done')
        self.assertTrue(leave.is_absence_direction, 'admin is Direction')

    def test_an_employee_cannot_sneak_the_direction_check_in_on_create(self):
        owner = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Absence Creator', 'login': 'absence_creator@absence.test',
            'groups_id': [Command.link(self.env.ref('base.group_user').id),
                          Command.link(self.env.ref('ems.group_teacher').id)],
        })
        self.employee.user_id = owner.id

        leave = self._create_leave(self.type_justified, self._monday(), ems_direction_state='done')

        self.assertEqual(
            leave.with_user(owner).sudo().ems_direction_state, 'done',
            'admin created it, so it stands')
        sneaked = self.env['hr.leave'].with_user(owner).create({
            'employee_id': self.employee.id,
            'holiday_status_id': self.type_justified.id,
            'request_date_from': self._monday() + timedelta(days=1),
            'request_date_to': self._monday() + timedelta(days=1),
            'ems_submitted': True,
            'ems_responsible_declaration': True,
            'ems_direction_state': 'done',
        })

        self.assertEqual(sneaked.sudo().ems_direction_state, 'not_done')

    # --- The approvals: the Head's (acknowledgement, document), then Direction's -------------

    def _direction(self):
        """A Director who is not the approver of self.employee (who has no department, so no
        approver at all), set as the company's Director so notifications can find them."""
        user = create_role_user(self, 'director', 'absence_direction@absence.test',
                                email='absence_direction@example.com')
        self.env.company.director_id = create_role_employee(self, user).id
        return user

    def _attach(self, leave, user=None, name='justificant.pdf'):
        """What the form's attachment widget does: upload the file, then link it on save."""
        leave = leave.with_user(user) if user else leave
        attachment = self.env['ir.attachment'].with_user(leave.env.user).create({
            'name': name, 'datas': base64.b64encode(b'certificate'),
            'res_model': 'hr.leave', 'res_id': leave.id,
        })
        leave.write({'supported_attachment_ids': [Command.link(attachment.id)]})
        return attachment

    def _validated_by_head(self, leave):
        """Walks a request through the Head's whole side, whatever its type, and through the
        employee's own steps on the way, up to Direction."""
        leave.action_approve()
        if leave.ems_status == 'pending_document':
            self._attach(leave)
        if leave.ems_status == 'pending_validation':
            leave.action_ems_document_validate()
        if leave.ems_status == 'pending_atri':
            leave.action_ems_atri_requested()
        return leave

    def test_a_new_request_is_pending_for_both(self):
        leave = self._create_leave(self.type_justified, self._monday())

        self.assertEqual(leave.ems_head_state, 'pending')
        self.assertFalse(leave.ems_document_state, 'nobody has acknowledged it yet')
        self.assertEqual(leave.ems_direction_state, 'not_done')
        self.assertEqual(leave.ems_status, 'pending')

    def test_acknowledging_a_request_waits_for_its_document(self):
        """The Head cannot validate what they have not seen, and the document often only exists
        after the absence. Acknowledging it already takes effect, as the approval always did."""
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)

        leave.action_approve()

        self.assertEqual(leave.state, 'validate', 'it counts in the calendar from now on')
        self.assertEqual(leave.ems_document_state, 'awaiting')
        self.assertEqual(leave.ems_head_state, 'pending_document')
        self.assertEqual(leave.ems_status, 'pending_document')

    def test_a_document_filed_with_the_request_goes_straight_to_validation(self):
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        self._attach(leave)
        self.assertFalse(leave.ems_document_state, 'nothing moves before the Head acknowledges it')

        leave.action_approve()

        self.assertEqual(leave.ems_status, 'pending_validation')

    def test_a_type_without_a_document_goes_straight_to_direction(self):
        # Not ATRI, which needs no document either: it waits for the employee's confirmation
        # first (see the ATRI tests further down).
        for leave_type in (self.type_health,):
            with self.subTest(leave_type=leave_type.ems_short_name):
                leave = self._create_leave(leave_type, self._monday(), ems_full_day=True)

                leave.action_approve()

                self.assertEqual(leave.ems_document_state, 'not_required')
                self.assertEqual(leave.ems_head_state, 'approved')
                self.assertEqual(leave.ems_status, 'pending_direction')

    def test_attaching_the_document_hands_it_back_to_the_head(self):
        """No button for the employee to forget: attaching the file is the step."""
        owner = self._employee_user('Test Absence Attacher', 'absence_attacher@absence.test')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()

        self._attach(leave, owner)

        self.assertEqual(leave.ems_document_state, 'submitted')
        self.assertEqual(leave.ems_status, 'pending_validation')

    def test_the_employee_cannot_set_the_document_status_themselves(self):
        owner = self._employee_user('Test Absence Self Validator', 'absence_self_validator@absence.test')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()

        with self.assertRaises(AccessError):
            leave.with_user(owner).write({'ems_document_state': 'validated'})
        with self.assertRaises(AccessError):
            leave.with_user(owner).action_ems_document_validate()

    def test_the_whole_sequence(self):
        """Pending, awaiting the document, pending its validation, pending Direction, approved."""
        self._direction()
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        seen = [leave.ems_status]
        leave.action_approve()
        seen.append(leave.ems_status)
        self._attach(leave)
        seen.append(leave.ems_status)
        leave.action_ems_document_validate()
        seen.append(leave.ems_status)
        leave.action_ems_direction_done()
        seen.append(leave.ems_status)

        self.assertEqual(seen, ['pending', 'pending_document', 'pending_validation',
                                'pending_direction', 'approved'])
        self.assertEqual(leave.ems_head_state, 'approved')

    def test_direction_validates_only_after_the_head(self):
        """The order is fixed now: Direction's check is the last step."""
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        for step in (None, leave.action_approve, lambda: self._attach(leave)):
            if step:
                step()
            with self.subTest(status=leave.ems_status), self.assertRaises(UserError):
                leave.action_ems_direction_done()
        self.assertEqual(leave.ems_direction_state, 'not_done')

    def test_the_head_validates_only_a_submitted_document(self):
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()

        with self.assertRaises(UserError):
            leave.action_ems_document_validate()

    def _return_wizard(self, leave):
        """The dialog the button opens, with the defaults it is opened with."""
        action = leave.action_ems_document_insufficient()
        return self.env[action['res_model']].with_context(action['context']).new({})

    def _return_document(self, leave, reason="Test unreadable scan"):
        """Through the button and its dialog, as the Head or Direction would."""
        action = leave.action_ems_document_insufficient()
        wizard = self.env[action['res_model']].with_context(action['context']).create({'reason': reason})
        wizard.action_return()

    def test_an_insufficient_document_goes_back_to_the_employee(self):
        """From the Head validating it or from Direction reviewing it, with the reason why, and
        the reminders start over."""
        owner = self._employee_user('Test Absence Resubmitter', 'absence_resubmitter@absence.test')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        self._attach(leave)
        leave.sudo().write({'ems_document_reminder_date': self._monday(), 'ems_document_escalated': True})

        self._return_document(leave, "Test the doctor stamp is missing")
        self.assertEqual(leave.ems_status, 'pending_document')
        self.assertEqual(leave.ems_document_return_reason, "Test the doctor stamp is missing")
        self.assertFalse(leave.ems_document_reminder_date)
        self.assertFalse(leave.ems_document_escalated)
        message = leave.message_ids.sorted('id')[-1]
        self.assertIn(owner.partner_id, message.partner_ids, 'the employee is told')
        self.assertIn("stamp is missing", str(message.body), 'and why')
        activity = leave.activity_ids.filtered(
            lambda activity: activity.activity_type_id == self.env.ref('ems.mail_activity_absence_document_upload'))
        self.assertIn("stamp is missing", str(activity.note), "the employee's to-do says why too")

        self._attach(leave, owner, name='justificant2.pdf')
        leave.action_ems_document_validate()
        self._return_document(leave, "Test wrong dates")
        self.assertEqual(leave.ems_status, 'pending_document', "Direction's review sends it back too")
        self.assertEqual(leave.ems_document_return_reason, "Test wrong dates")
        self.assertEqual(leave.ems_direction_state, 'not_done')

    def test_the_previous_reason_is_offered_when_sending_it_back_again(self):
        """The Head looks at the new document and it is still wrong: the reason they wrote last
        time is the starting point. Validating the document clears it, so a later send-back
        (Direction's) starts from an empty one."""
        owner = self._employee_user('Test Absence Resent', 'absence_resent@absence.test')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        self._attach(leave)
        self.assertFalse(self._return_wizard(leave).reason, 'nothing to offer the first time')
        self._return_document(leave, "Test the stamp is missing")

        self._attach(leave, owner, name='justificant2.pdf')
        self.assertEqual(self._return_wizard(leave).reason, "Test the stamp is missing")

        leave.action_ems_document_validate()
        self.assertFalse(leave.ems_document_return_reason, 'validating the document clears it')
        self.assertFalse(self._return_wizard(leave).reason)

    def test_sending_a_document_back_requires_a_reason(self):
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        self._attach(leave)

        with self.assertRaises(Exception):
            self._return_document(leave, False)
        self.assertEqual(leave.ems_status, 'pending_validation')

    def test_resetting_a_request_clears_the_return_reason(self):
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        self._attach(leave)
        self._return_document(leave)
        leave.action_refuse()

        leave.action_reset_confirm()

        self.assertFalse(leave.ems_document_return_reason)

    def test_only_the_head_or_direction_send_a_document_back(self):
        owner = self._employee_user('Test Absence Not Insufficient', 'absence_not_insufficient@absence.test')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        self._attach(leave)

        with self.assertRaises(AccessError):
            leave.with_user(owner).action_ems_document_insufficient()

    # --- Waiving the supporting document (issue #634) ---------------------------------------

    def _awaiting_document(self, week=0):
        leave = self._create_leave(self.type_sick_leave, self._monday() + timedelta(weeks=week),
                                   ems_full_day=True)
        leave.action_approve()
        self.assertEqual(leave.ems_status, 'pending_document')
        return leave

    def test_waiving_the_document_sends_the_request_on_to_direction(self):
        """Recorded as waived, never as validated: nobody checked a document that never came.
        The employee stops being asked for it and is told."""
        self._direction()
        owner = self._employee_user('Test Absence Waived', 'absence_waived@absence.test')
        leave = self._awaiting_document()

        leave.action_ems_document_waive()

        self.assertEqual(leave.ems_document_state, 'waived')
        self.assertEqual(leave.ems_head_state, 'approved')
        self.assertEqual(leave.ems_status, 'pending_direction')
        upload = self.env.ref('ems.mail_activity_absence_document_upload')
        self.assertFalse(leave.activity_ids.filtered(lambda activity: activity.activity_type_id == upload),
                         "the employee's to-do is closed")
        message = leave.message_ids.sorted('id')[-1]
        self.assertIn(owner.partner_id, message.partner_ids, 'the employee is told')
        leave.action_ems_direction_done()
        self.assertEqual(leave.ems_status, 'approved', 'and Direction decides on it as usual')

    def test_only_a_request_awaiting_its_document_can_be_waived(self):
        pending = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        submitted = self._awaiting_document(week=1)
        self._attach(submitted)

        for leave in (pending, submitted):
            with self.subTest(status=leave.ems_status), self.assertRaises(UserError):
                leave.action_ems_document_waive()
            self.assertFalse(leave.ems_can_waive_document)

    def test_who_can_waive_a_document(self):
        """The Head, Direction above them and the administrator above everyone - not the
        employee, nor any other teacher."""
        direction = self._direction()
        head = create_role_user(self, 'head_of_studies', 'absence_waive_hos@absence.test',
                                email='absence_waive_hos@example.com')
        admin = create_role_user(self, 'academic_admin', 'absence_waive_admin@absence.test',
                                 email='absence_waive_admin@example.com')
        teacher = create_role_user(self, 'teacher', 'absence_waive_teacher@absence.test')
        owner = self._employee_user('Test Absence Waiver Owner', 'absence_waive_owner@absence.test')

        leave = self._awaiting_document()
        self.assertFalse(leave.with_user(owner).ems_can_waive_document)
        for user in (owner, teacher):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                leave.with_user(user).action_ems_document_waive()
        for week, user in enumerate((head, direction, admin), start=1):
            leave = self._awaiting_document(week=week)
            with self.subTest(user=user.login):
                self.assertTrue(leave.with_user(user).ems_can_waive_document)
                leave.with_user(user).action_ems_document_waive()
                self.assertEqual(leave.ems_document_state, 'waived')

    def test_undoing_a_waiver_waits_for_the_document_again(self):
        """With the reason it had been sent back for, if any, shown to the employee again."""
        leave = self._awaiting_document()
        self._attach(leave)
        self._return_document(leave, "Test the stamp is missing")
        leave.action_ems_document_waive()

        self.assertEqual(self._undo_statuses(leave, 1), ['pending_document'])
        self.assertEqual(leave.ems_document_state, 'awaiting')
        self.assertEqual(leave.ems_document_return_reason, "Test the stamp is missing")

    def test_a_head_refusal_refuses_the_request(self):
        leave = self._create_leave(self.type_justified, self._monday())

        leave.action_refuse()

        self.assertEqual(leave.ems_head_state, 'refused')
        self.assertEqual(leave.ems_direction_state, 'not_done')
        self.assertEqual(leave.ems_status, 'refused')

    def test_the_head_can_refuse_while_awaiting_the_document(self):
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()

        leave.action_refuse()

        self.assertEqual(leave.ems_status, 'refused')
        self.assertFalse(leave.activity_ids, 'nobody is left waiting on anything')

    def test_a_direction_refusal_refuses_the_whole_request(self):
        """Direction refusing is final, like the Head's - but it is Direction's refusal, not
        the Head's, and each column says who decided what."""
        for validated_first in (False, True):
            with self.subTest(validated_first=validated_first):
                leave = self._create_leave(
                    self.type_justified, self._monday() + timedelta(days=7 * validated_first),
                    ems_full_day=True)
                if validated_first:
                    self._validated_by_head(leave)

                leave.action_ems_direction_refuse()

                self.assertEqual(leave.state, 'refuse')
                self.assertEqual(leave.ems_direction_state, 'refused')
                self.assertEqual(leave.ems_head_state, 'approved' if validated_first else 'pending')
                self.assertEqual(leave.ems_status, 'refused')

    def test_resetting_a_head_refusal_clears_it(self):
        leave = self._create_leave(self.type_justified, self._monday())
        leave.action_refuse()

        leave.action_reset_confirm()

        self.assertEqual(leave.state, 'confirm')
        self.assertEqual(leave.ems_head_state, 'pending')
        self.assertEqual(leave.ems_direction_state, 'not_done')
        self.assertEqual(leave.ems_status, 'pending')

    def test_resetting_a_direction_refusal_also_clears_the_direction_check(self):
        """Odoo's own reset only ever touches 'state' - without this override,
        'ems_direction_state' would be stranded on 'refused' after the request is reopened,
        even though nothing on screen still says why it can't be approved again. The document
        status goes too: the Head acknowledges the reopened request afresh."""
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        self._validated_by_head(leave)
        leave.action_ems_direction_refuse()

        leave.action_reset_confirm()

        self.assertEqual(leave.state, 'confirm')
        self.assertEqual(leave.ems_head_state, 'pending')
        self.assertFalse(leave.ems_document_state)
        self.assertEqual(leave.ems_direction_state, 'not_done')
        self.assertEqual(leave.ems_status, 'pending')

    def test_direction_marks_its_check_from_buttons(self):
        leave = self._validated_by_head(self._create_leave(self.type_justified, self._monday(), ems_full_day=True))

        leave.action_ems_direction_done()
        self.assertEqual(leave.ems_direction_state, 'done')
        leave.action_ems_undo()
        self.assertEqual(leave.ems_direction_state, 'not_done')

    def test_only_direction_uses_the_direction_buttons(self):
        head = create_role_user(self, 'head_of_studies', 'absence_hos_buttons@absence.test')
        leave = self._validated_by_head(self._create_leave(self.type_justified, self._monday(), ems_full_day=True))

        for action in ('action_ems_direction_done', 'action_ems_direction_refuse',
                       'action_ems_document_insufficient'):
            with self.subTest(action=action), self.assertRaises(AccessError):
                getattr(leave.with_user(head), action)()
        self.assertEqual(leave.ems_status, 'pending_direction')

    def test_direction_does_not_approve_on_the_heads_behalf(self):
        """Direction holds the officer group through Head of Studies, so Odoo would let it
        approve every request - and the Approve button beside the Head's column is not
        Direction's review. It only gets to approve where it really is the approver."""
        direction = self._direction()
        leave = self._create_leave(self.type_justified, self._monday())

        self.assertFalse(leave.with_user(direction).can_approve)
        self.assertFalse(leave.with_user(direction).is_absence_head)

        self.employee.leave_manager_id = direction.id
        leave.invalidate_recordset(['can_approve', 'is_absence_head'])
        self.assertTrue(leave.with_user(direction).can_approve,
                        "an Area Manager's own absence is Direction's to approve")
        self.assertTrue(leave.with_user(direction).is_absence_head)

    def test_a_head_of_studies_still_approves(self):
        head = create_role_user(self, 'head_of_studies', 'absence_hos_approves@absence.test')
        leave = self._create_leave(self.type_justified, self._monday())

        self.assertTrue(leave.with_user(head).can_approve)
        self.assertTrue(leave.with_user(head).is_absence_head)

    def test_direction_is_told_when_the_request_reaches_it(self):
        """Not at the Head's acknowledgement while a document is still due: when the Head has
        validated it and it is Direction's to review (issue #632)."""
        direction = self._direction()
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)

        leave.action_approve()
        self.assertNotIn(direction.partner_id, leave.message_partner_ids)
        self._attach(leave)
        leave.action_ems_document_validate()

        self.assertIn(direction.partner_id, leave.message_partner_ids)
        email = self._emails_to(leave, direction)
        self.assertEqual(len(email), 1, "the summary, not Odoo's own activity email on top")
        self.assertIn('Pending Direction', email.body, 'the summary says what is still missing')
        self.assertIn('now in your hands', email.body)

    def test_direction_is_not_told_of_a_refusal(self):
        direction = self._direction()
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        leave.action_refuse()

        self.assertNotIn(direction.partner_id, leave.message_partner_ids)

    def test_direction_is_not_told_of_its_own_approval(self):
        """As the approver it already follows the request - hr_holidays subscribes whoever
        approves - and moving it on to itself tells it nothing it does not know."""
        direction = self._direction()
        self.employee.leave_manager_id = direction.id
        leave = self._create_leave(self.type_health, self._monday(), ems_full_day=True)
        before = self._emails_to(leave, direction)

        leave.with_user(direction).action_approve()

        self.assertEqual(leave.ems_status, 'pending_direction')
        self.assertIn(direction.partner_id, leave.message_partner_ids)
        self.assertEqual(self._emails_to(leave, direction), before)

    def test_direction_is_not_told_of_its_own_absence(self):
        """Nobody reviews it as Direction then: the Head keeps it throughout."""
        direction = self._direction()
        head = create_role_user(self, 'head_of_studies', 'absence_own_direction_head@absence.test')
        self.env.company.director_id.leave_manager_id = head.id
        leave = self._create_leave(self.type_health, self._monday(), ems_full_day=True,
                                   employee_id=self.env.company.director_id.id)

        leave.action_approve()

        self.assertEqual(leave._ems_stage_users(), head)
        self.assertIn(head.partner_id, leave.message_partner_ids)
        self.assertFalse(leave.message_ids.filtered(
            lambda message: direction.partner_id in message.partner_ids
            and 'now in your hands' in message.body), 'told as the employee, not as Direction')

    # --- Who is waiting on what ---------------------------------------------------------------

    def _activity_users(self, leave, xmlid):
        activity_type = self.env.ref(xmlid)
        return leave.activity_ids.filtered(lambda a: a.activity_type_id == activity_type).user_id

    def test_each_step_leaves_one_activity_for_whoever_is_next(self):
        direction = self._direction()
        owner = self._employee_user('Test Absence Activities', 'absence_activities@absence.test')
        head = create_role_user(self, 'head_of_studies', 'absence_activities_head@absence.test')
        self.employee.leave_manager_id = head.id
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)

        # Approved on the day of the absence: once that day is past the deadline is today instead
        # (max(today, day after)), which a fixed Monday of the course would reach as the year goes on.
        with patch.object(type(self.env['ems.datetime_utils']), 'get_local_today',
                          return_value=leave.request_date_from):
            leave.action_approve()
        self.assertEqual(self._activity_users(leave, 'ems.mail_activity_absence_document_upload'), owner)
        self.assertEqual(leave.activity_ids.date_deadline, leave.request_date_to + timedelta(days=1),
                         'due the day after the absence')

        self._attach(leave, owner)
        self.assertFalse(self._activity_users(leave, 'ems.mail_activity_absence_document_upload'))
        self.assertEqual(self._activity_users(leave, 'ems.mail_activity_absence_document_validate'), head)

        leave.action_ems_document_validate()
        self.assertEqual(self._activity_users(leave, 'ems.mail_activity_absence_direction_review'), direction)
        self.assertEqual(len(leave.activity_ids), 1)

        leave.action_ems_direction_done()
        self.assertFalse(leave.activity_ids)

    def test_waiting_for_direction_lists_what_direction_still_owes(self):
        """Every request the Head has validated and Direction has not, plus whatever Direction
        handles as the Head."""
        direction = self._direction()
        day = self._monday()
        reviewed = self._validated_by_head(self._create_leave(self.type_atri, day, ems_full_day=True))
        reviewed.action_ems_direction_done()
        unreviewed = self._validated_by_head(
            self._create_leave(self.type_atri, day + timedelta(days=7), ems_full_day=True))
        awaiting = self._create_leave(self.type_sick_leave, day + timedelta(days=14), ems_full_day=True)
        awaiting.action_approve()
        heads_pending = self._create_leave(self.type_justified, day + timedelta(days=21), ems_full_day=True)
        refused = self._create_leave(self.type_justified, day + timedelta(days=35), ems_full_day=True)
        refused.action_refuse()
        own_approver = self.env['hr.employee'].create({
            'name': 'Test Area Manager (Direction approves)', 'employee_type': 'teacher'})
        own_approver.leave_manager_id = direction.id
        directions_pending = self._create_leave(
            self.type_justified, day + timedelta(days=28), ems_full_day=True,
            employee_id=own_approver.id)

        search = etree.fromstring(self.env['hr.leave'].with_user(direction).get_view(
            self.env.ref('hr_holidays.hr_leave_view_search_manager').id, 'search')['arch'])
        [waiting] = search.xpath("//filter[@name='ems_waiting_for_direction']")
        domain = safe_eval(waiting.get('domain'), {'uid': direction.id})
        found = self.env['hr.leave'].search(domain)

        self.assertIn(unreviewed, found)
        self.assertIn(directions_pending, found)
        self.assertNotIn(awaiting, found, 'the Head has not validated it yet')
        self.assertNotIn(heads_pending, found, 'the Head goes first')
        self.assertNotIn(reviewed, found)
        self.assertNotIn(refused, found)
        self.assertFalse(search.xpath("//filter[@name='waiting_for_me_manager']"),
                         "the Head of Studies' own filter would list the Head's pending work")

    def test_waiting_for_the_head_includes_documents_to_validate(self):
        """Odoo's own filter only knows the acknowledgement; the Head's second step is theirs too."""
        head = create_role_user(self, 'head_of_studies', 'absence_waiting_head@absence.test')
        day = self._monday()
        pending = self._create_leave(self.type_sick_leave, day, ems_full_day=True)
        submitted = self._create_leave(self.type_sick_leave, day + timedelta(days=7), ems_full_day=True)
        submitted.action_approve()
        self._attach(submitted)
        awaiting = self._create_leave(self.type_sick_leave, day + timedelta(days=14), ems_full_day=True)
        awaiting.action_approve()

        search = etree.fromstring(self.env['hr.leave'].with_user(head).get_view(
            self.env.ref('hr_holidays.hr_leave_view_search_manager').id, 'search')['arch'])
        [waiting] = search.xpath("//filter[@name='waiting_for_me_manager']")
        found = self.env['hr.leave'].search(safe_eval(waiting.get('domain'), {'uid': head.id}))

        self.assertIn(pending, found)
        self.assertIn(submitted, found)
        self.assertNotIn(awaiting, found, "it is the employee's turn")

    # --- An Area Manager's own absence (issue #693) ------------------------------------------

    def _own_area_manager(self, role, login, **kwargs):
        """self.employee as an Area Manager: their own approver, as _compute_leave_manager
        makes them (see TestAbsence)."""
        user = create_role_user(self, role, login, email=login.replace('@absence.test', '@example.com'),
                                **kwargs)
        self.employee.user_id = user.id
        self.employee.leave_manager_id = user.id
        return user

    def test_an_area_manager_validates_their_own_absence_and_direction_reviews_it(self):
        direction = self._direction()
        head = self._own_area_manager('head_of_studies', 'absence_own_head@absence.test')
        leave = self._create_leave(self.type_health, self._monday(), ems_full_day=True).with_user(head)

        self.assertTrue(leave.can_approve)
        self.assertTrue(leave.is_absence_head)
        leave.invalidate_recordset(['can_approve', 'is_absence_head'])
        self.assertFalse(leave.with_user(direction).can_approve, 'Direction only reviews it')
        self.assertFalse(leave.with_user(direction).is_absence_head)

        leave.action_approve()
        self.assertEqual(leave.ems_status, 'pending_direction')
        self.assertIn(direction.partner_id, leave.message_partner_ids)

        leave.with_user(direction).action_ems_direction_done()
        self.assertEqual(leave.ems_status, 'approved')

    def test_an_area_manager_validates_the_document_of_their_own_absence(self):
        self._direction()
        head = self._own_area_manager('head_of_studies', 'absence_own_document@absence.test')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True).with_user(head)

        leave.action_approve()
        self.assertEqual(leave.ems_status, 'pending_document')
        self._attach(leave)
        self.assertEqual(leave.ems_status, 'pending_validation')
        leave.action_ems_document_validate()

        self.assertEqual(leave.ems_status, 'pending_direction')

    def test_the_secretary_validates_their_own_absence(self):
        """The Secretary approves as their area's approver only, without the officer group."""
        self._direction()
        secretary = self._own_area_manager('secretary', 'absence_own_secretary@absence.test',
                                           employee_type='asp')
        leave = self._create_leave(self.type_health, self._monday(), ems_full_day=True).with_user(secretary)

        leave.action_approve()

        self.assertEqual(leave.ems_status, 'pending_direction')

    def test_an_area_manager_still_cannot_edit_their_own_approved_absence(self):
        """Approving it is theirs; changing it afterwards stays as closed as for anybody else."""
        self._direction()
        head = self._own_area_manager('head_of_studies', 'absence_own_edit@absence.test')
        leave = self._create_leave(self.type_health, self._monday(), ems_full_day=True).with_user(head)
        leave.action_approve()

        with self.assertRaises(AccessError):
            leave.write({'holiday_status_id': self.type_justified.id})

    def test_an_area_managers_own_absence_waits_for_them(self):
        head = self._own_area_manager('head_of_studies', 'absence_own_waiting@absence.test')
        own = self._create_leave(self.type_health, self._monday(), ems_full_day=True)

        search = etree.fromstring(self.env['hr.leave'].with_user(head).get_view(
            self.env.ref('hr_holidays.hr_leave_view_search_manager').id, 'search')['arch'])
        [waiting] = search.xpath("//filter[@name='waiting_for_me_manager']")
        found = self.env['hr.leave'].search(safe_eval(waiting.get('domain'), {'uid': head.id}))

        self.assertIn(own, found)

    # --- Reminders ----------------------------------------------------------------------------

    def _run_reminders_on(self, today, hour=12.0):
        """Runs the reminders at `hour` of `today` in the company's time: each message waits for
        its reader's working day to start (issue #696)."""
        utils = self.env['ems.datetime_utils']
        now = utils.datetime_to_odoo(utils.time_float_to_utc_datetime(today, hour))
        with patch.object(type(utils), 'get_local_today', return_value=today), \
                patch.object(fields.Datetime, 'now', return_value=now):
            self.env['hr.leave']._cron_ems_document_reminder()

    def test_the_employee_is_reminded_every_day_once_the_absence_is_over(self):
        owner = self._employee_user('Test Absence Reminded', 'absence_reminded@absence.test')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        reminders = lambda: leave.message_ids.filtered(
            lambda m: owner.partner_id in m.partner_ids and 'Reminder' in m.body)

        self._run_reminders_on(leave.request_date_to)
        self.assertFalse(reminders(), 'not while the absence is still going on')
        self._run_reminders_on(leave.request_date_to + timedelta(days=1))
        self._run_reminders_on(leave.request_date_to + timedelta(days=1))
        self.assertEqual(len(reminders()), 1, 'once a day')
        self._run_reminders_on(leave.request_date_to + timedelta(days=2))
        self.assertEqual(len(reminders()), 2)

        self._attach(leave, owner)
        self._run_reminders_on(leave.request_date_to + timedelta(days=3))
        self.assertEqual(len(reminders()), 2, 'nothing once the document is in')

    def test_reminders_wait_for_the_working_day_to_start(self):
        """Issue #696: never outside the employee's working hours, nor on a day they don't work."""
        owner = self._employee_user('Test Absence Reminded Later', 'absence_reminded_later@absence.test')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        reminders = lambda: leave.message_ids.filtered(
            lambda m: owner.partner_id in m.partner_ids and 'Reminder' in m.body)
        saturday = leave.request_date_to + timedelta(days=5 - leave.request_date_to.weekday())
        make_working_day(self, saturday + timedelta(days=2))

        self._run_reminders_on(saturday, hour=12.0)
        self.assertFalse(reminders(), 'no working day on a Saturday')
        self._run_reminders_on(saturday + timedelta(days=2), hour=0.5)
        self.assertFalse(reminders(), 'not before their working day starts')
        self._run_reminders_on(saturday + timedelta(days=2), hour=12.0)
        self.assertEqual(len(reminders()), 1)

    def test_the_head_is_told_once_after_the_escalation_days(self):
        owner = self._employee_user('Test Absence Escalated', 'absence_escalated@absence.test')
        head = create_role_user(self, 'head_of_studies', 'absence_escalated_head@absence.test')
        self.employee.leave_manager_id = head.id
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        told = lambda: leave.message_ids.filtered(
            lambda m: head.partner_id in m.partner_ids and 'still not' in m.body)

        self._run_reminders_on(leave.request_date_to + timedelta(days=2))
        self.assertFalse(told())
        emailed_before = self._emails_to(leave, head)
        self._run_reminders_on(leave.request_date_to + timedelta(days=3))
        self._run_reminders_on(leave.request_date_to + timedelta(days=4))
        self.assertEqual(len(told()), 1)
        self.assertEqual(self._activity_users(leave, 'ems.mail_activity_absence_document_overdue'), head)
        self.assertEqual(self._emails_to(leave, head) - emailed_before, told(),
                         "the note is the Head's only email: the activity sends none")
        self.assertNotIn(owner.partner_id, told().partner_ids)

    def test_the_reminder_days_come_from_the_settings(self):
        self._employee_user('Test Absence Configured', 'absence_configured@absence.test')
        head = create_role_user(self, 'head_of_studies', 'absence_configured_head@absence.test')
        self.employee.leave_manager_id = head.id
        self.env.company.write({'ems_absence_document_reminder_days': 3,
                                'ems_absence_document_escalation_days': 1})
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        end = leave.request_date_to

        self._run_reminders_on(end + timedelta(days=1))
        self.assertTrue(leave.ems_document_escalated, 'reported to the Head after one day')
        self._run_reminders_on(end + timedelta(days=2))
        self.assertEqual(leave.ems_document_reminder_date, end + timedelta(days=1),
                         'the next reminder is three days after the last one')
        self._run_reminders_on(end + timedelta(days=4))
        self.assertEqual(leave.ems_document_reminder_date, end + timedelta(days=4))

    def test_reminders_do_not_reach_the_department_chief(self):
        """A note to the employee alone: the followers told of the approval are not spammed."""
        chief = self.env['hr.employee'].create({'name': 'Test Absence Quiet Chief', 'employee_type': 'teacher'})
        chief_user = create_role_user(self, 'department_chief', 'absence_quiet_chief@absence.test')
        chief.user_id = chief_user.id
        self.employee.department_id = self.env['hr.department'].create(
            {'name': 'Test Absence Quiet Dept', 'manager_id': chief.id}).id
        self._employee_user('Test Absence Quiet', 'absence_quiet@absence.test')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        self.assertIn(chief_user.partner_id, leave.message_partner_ids)

        self._run_reminders_on(leave.request_date_to + timedelta(days=1))

        reminder = leave.message_ids.sorted('id')[-1]
        self.assertEqual(reminder.subtype_id, self.env.ref('mail.mt_note'))
        self.assertFalse(reminder.notification_ids.filtered(
            lambda n: n.res_partner_id == chief_user.partner_id))

    def test_direction_lands_on_its_own_filter(self):
        context = safe_eval(self.env.ref('hr_holidays.hr_leave_action_action_approve_department').context,
                            {'uid': self.env.uid, 'allowed_company_ids': []})

        self.assertTrue(context.get('search_default_ems_waiting_for_direction'))

    # --- The supporting document ------------------------------------------------------------

    def _arch(self, xmlid, view_type):
        """The view as the client really receives it, with every inherit already applied."""
        return etree.fromstring(
            self.env['hr.leave'].get_view(self.env.ref(xmlid).id, view_type)['arch'])

    def test_the_supporting_document_is_offered_on_every_absence_type(self):
        """Odoo shows the attachment only for types whose 'support_document' is set, which reads
        the flag backwards: it says which types *require* a justification, not which ones accept
        one. The centre takes whatever the employee has, for any absence."""
        arch = self._arch('hr_holidays.hr_leave_view_form', 'form')

        nodes = arch.xpath("//field[@name='supported_attachment_ids'] | "
                           "//label[@for='supported_attachment_ids']")
        self.assertEqual(len(nodes), 2, 'the field and its label')
        for node in nodes:
            self.assertNotIn('leave_type_support_document', node.get('invisible') or '',
                             'the absence type does not decide whether a document can be filed')

    def test_the_supporting_document_stays_on_screen_after_the_approval(self):
        """Direction checks the document after the approval, so a field that disappears the
        moment the request is approved would leave a request awaiting its document stuck forever."""
        arch = self._arch('hr_holidays.hr_leave_view_form', 'form')

        for node in arch.xpath("//field[@name='supported_attachment_ids'] | "
                               "//label[@for='supported_attachment_ids']"):
            self.assertNotIn('state', node.get('invisible') or '',
                             'the approval state does not hide the justification')

    def test_the_employee_is_not_shown_each_approvers_column(self):
        """The overall Status is the employee's whole answer; the Head's and Direction's own
        columns only confuse it. Hidden as columns, so the fields stay loaded for conditions."""
        arch = self._arch('hr_holidays.hr_leave_view_tree_my', 'list')

        for name in ('ems_head_state', 'ems_direction_state'):
            [node] = arch.xpath(f"//field[@name='{name}']")
            self.assertEqual(node.get('column_invisible'), '1', name)
        [status] = arch.xpath("//field[@name='ems_status']")
        self.assertFalse(status.get('column_invisible'), 'the overall status stays')

        managers = self._arch('hr_holidays.hr_leave_view_tree', 'list')
        for name in ('ems_head_state', 'ems_direction_state'):
            self.assertFalse(managers.xpath(f"//field[@name='{name}']")[0].get('column_invisible'),
                             f'{name} stays on the managers\' list')

    def test_the_employee_is_not_shown_each_approvers_badge_on_the_form(self):
        owner = self._employee_user('Test Absence Badges', 'absence_badges@absence.test')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        arch = self._arch('hr_holidays.hr_leave_view_form', 'form')

        for name in ('ems_head_state', 'ems_document_state', 'ems_direction_state'):
            [node] = arch.xpath(f"//field[@name='{name}']")
            self.assertIn('not (is_absence_manager or is_absence_direction)', node.get('invisible'), name)
        mine = leave.with_user(owner)
        self.assertFalse(mine.is_absence_manager or mine.is_absence_direction,
                         'so an ordinary employee does not see them')

    def _employee_user(self, name, login):
        """A plain internal user for 'self.employee', with no Time Off group whatsoever.

        Spelled out rather than left to Odoo's default: 'base.default_user' still carries the
        Time Off groups hr_holidays hands out at install time, and a user copied from it would
        be an officer - proving nothing about what an ordinary employee can do.
        """
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            # English: the reminders are written in their reader's language.
            'name': name, 'login': login, 'lang': 'en_US',
            'groups_id': [Command.link(self.env.ref('base.group_user').id),
                          Command.link(self.env.ref('ems.group_teacher').id)],
        })
        self.employee.user_id = user.id
        return user

    def test_the_justification_can_be_filed_after_the_approval(self):
        """The other half of the same rule, server-side: a medical certificate is usually handed
        in days after the absence itself, and the "Awaiting documentation" status exists to
        chase exactly that. Odoo's own record rule stops an employee writing their own request
        once it is approved, so 'rule_absence_own_request_write' widens it."""
        owner = self._employee_user('Test Absence Filer', 'absence_filer@absence.test')
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        leave.action_approve()
        self.assertEqual(leave.state, 'validate')

        # The two steps the widget itself performs: the file is uploaded as its own
        # ir.attachment first, and only then linked to the request by the form's save.
        attachment = self.env['ir.attachment'].with_user(owner).create({
            'name': 'justificant.pdf', 'datas': base64.b64encode(b'certificate'),
            'res_model': 'hr.leave', 'res_id': leave.id,
        })
        leave.with_user(owner).write(
            {'supported_attachment_ids': [Command.link(attachment.id)]})

        self.assertEqual(leave.supported_attachment_ids.mapped('name'), ['justificant.pdf'])
        self.assertEqual(leave.attachment_ids, leave.supported_attachment_ids,
                         'and it lands on the request itself, not only on the widget')

    def test_an_approved_request_is_still_closed_to_everything_else(self):
        """The record rule above cannot name fields, so it necessarily opens the whole record.
        This is what closes it back down to the justification it was widened for."""
        owner = self._employee_user('Test Absence Editor', 'absence_editor@absence.test')
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        leave.action_approve()

        with self.assertRaises(AccessError):
            leave.with_user(owner).write({'request_date_to': self._monday() + timedelta(days=4)})
        with self.assertRaises(AccessError):
            leave.with_user(owner).write({'holiday_status_id': self.type_health.id})

    def test_an_officer_cannot_edit_their_own_approved_request_either(self):
        """The widened record rule reaches officers too, so the field-level check has to. Odoo's
        own officer rule carries the same carve-out for a user's own approved absence, and being
        Head of Studies is not supposed to make your own request editable after the fact."""
        officer = self._employee_user('Test Absence Officer', 'absence_officer@absence.test')
        officer.sudo().write({
            'groups_id': [Command.link(self.env.ref('hr_holidays.group_hr_holidays_user').id)]})
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        leave.action_approve()

        with self.assertRaises(AccessError):
            leave.with_user(officer).write({'holiday_status_id': self.type_health.id})
        # The justification is the exception, for them as much as for anybody else.
        attachment = self.env['ir.attachment'].with_user(officer).create({
            'name': 'justificant.pdf', 'datas': base64.b64encode(b'certificate'),
            'res_model': 'hr.leave', 'res_id': leave.id,
        })
        leave.with_user(officer).write(
            {'supported_attachment_ids': [Command.link(attachment.id)]})

        self.assertEqual(leave.supported_attachment_ids.mapped('name'), ['justificant.pdf'])

    def test_an_unapproved_request_is_still_the_employees_to_edit(self):
        """And nothing changes while it is still pending, which is the normal case."""
        owner = self._employee_user('Test Absence Owner', 'absence_owner@absence.test')
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        leave.with_user(owner).write({'request_date_to': self._monday() + timedelta(days=1)})

        self.assertEqual(leave.request_date_to, self._monday() + timedelta(days=1))

    # --- The chatter entry an employee sees when they file a request ---------------------------

    def test_the_approval_activity_names_the_type_briefly(self):
        """hr_holidays drops the absence type's full legal wording into the activity it
        schedules, so the first thing the employee reads after filing is a paragraph of
        legalese where a heading should be."""
        approver = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Activity Approver', 'login': 'activity_approver@absence.test',
            'groups_id': [Command.link(self.env.ref('base.group_user').id)],
        })
        self.employee.leave_manager_id = approver.id

        leave = self._create_leave(self.type_health, self._monday())

        self.assertTrue(leave.activity_ids, 'sanity: an approval activity was scheduled')
        for note in (str(activity.note or '') for activity in leave.activity_ids):
            self.assertIn(self.type_health.ems_short_name, note)
            self.assertNotIn(self.type_health.name, note, 'not the whole declaration')

    def test_the_catalan_name_of_the_approval_activity_is_repaired(self):
        """Odoo's own Catalan for these two is machine-generated nonsense ("Temps de
        desaprovaciÃ³"), and it is the heading of that same chatter entry. Both records are
        noupdate, so no .po entry can ever overwrite them."""
        if not self.env['res.lang'].search_count([('code', '=', 'ca_ES'), ('active', '=', True)]):
            self.skipTest("Catalan is not installed on this database")
        activity_type = self.env.ref('hr_holidays.mail_act_leave_approval').sudo()
        activity_type.with_context(lang='ca_ES').name = "Temps de desaprovació"

        self.env['mail.activity.type']._ems_fix_approval_activity_names()

        self.assertEqual(activity_type.with_context(lang='ca_ES').name, "Aprovació d'absències")
        self.assertEqual(activity_type.with_context(lang='en_US').name, "Time Off Approval",
                         'the source language is left alone')
        self.assertFalse(self.env['mail.activity.type']._ems_fix_approval_activity_names(),
                         'and it is idempotent')

    # --- Refusing asks first ------------------------------------------------------------------

    def test_refusing_a_request_asks_first_on_every_screen(self):
        """Every Refuse button opens the dialog that asks for the reason - which is also what
        stands between a stray click and a refused request - on all three screens."""
        for xmlid, view_type in (('hr_holidays.hr_leave_view_form', 'form'),
                                 ('hr_holidays.hr_leave_view_tree', 'list'),
                                 ('hr_holidays.hr_leave_view_kanban', 'kanban')):
            arch = self._arch(xmlid, view_type)

            buttons = arch.xpath("//button[@name='action_refuse' or @name='action_ems_direction_refuse']")
            self.assertTrue(buttons, xmlid)
            for button in buttons:
                self.assertIn('ems_ask_change_message', button.get('context') or '', f'{xmlid} ({view_type})')

    # --- Undoing the last decision (issue #614) ---------------------------------------------

    def _undo_statuses(self, leave, steps):
        seen = []
        for _step in range(steps):
            leave.action_ems_undo()
            seen.append(leave.ems_status)
        return seen

    def test_undo_walks_back_one_decision_at_a_time(self):
        self._direction()
        leave = self._validated_by_head(self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True))
        leave.action_ems_direction_done()
        self.assertEqual(leave.ems_status, 'approved')

        self.assertEqual(self._undo_statuses(leave, 3), ['pending_direction', 'pending_validation', 'pending'])
        self.assertEqual(leave.state, 'confirm')
        with self.assertRaises(UserError):
            leave.action_ems_undo()

    def test_undoing_the_only_step_of_a_type_without_document_goes_back_to_pending(self):
        leave = self._create_leave(self.type_health, self._monday())
        leave.action_approve()

        self.assertEqual(self._undo_statuses(leave, 1), ['pending'])
        leave.action_approve()
        self.assertEqual(leave.ems_status, 'pending_direction', 'and it can be decided again')

    def test_undoing_the_acknowledgement_takes_the_absence_out_of_the_calendar(self):
        leave = self._create_leave(self.type_health, self._monday())
        calendar_leaves = self.env['resource.calendar.leaves'].search
        leave.action_approve()
        self.assertTrue(calendar_leaves([('holiday_id', '=', leave.id)]))

        leave.action_ems_undo()

        self.assertFalse(calendar_leaves([('holiday_id', '=', leave.id)]))
        self.assertFalse(leave.first_approver_id)

    def test_undoing_a_refusal_returns_the_request_to_where_it_stood(self):
        direction = self._direction()
        pending = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        awaiting = self._create_leave(self.type_sick_leave, self._monday() + timedelta(days=7), ems_full_day=True)
        awaiting.action_approve()
        approved = self._validated_by_head(
            self._create_leave(self.type_atri, self._monday() + timedelta(days=14), ems_full_day=True))
        approved.action_ems_direction_done()
        (pending | awaiting).action_refuse()
        approved.with_user(direction).action_ems_direction_refuse()
        self.assertEqual((pending | awaiting | approved).mapped('ems_status'), ['refused'] * 3)

        (pending | awaiting | approved).action_ems_undo()

        self.assertEqual(pending.ems_status, 'pending')
        self.assertEqual(awaiting.ems_status, 'pending_document')
        self.assertEqual(awaiting.state, 'validate', 'in effect again')
        self.assertEqual(approved.ems_status, 'approved')
        self.assertEqual(approved.ems_head_state, 'approved')

    def test_undoing_a_refusal_forgets_its_reason(self):
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        leave.with_context(ems_change_message="Test refused by mistake").action_refuse()
        self.assertTrue(leave.ems_refusal_reason)

        leave.action_ems_undo()

        self.assertEqual(leave.ems_status, 'pending')
        self.assertFalse(leave.ems_refusal_reason)

    def test_undoing_a_request_refused_before_this_existed_reopens_it(self):
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        leave.action_approve()
        leave.action_refuse()
        leave.sudo().ems_decision_before = False

        leave.action_ems_undo()

        self.assertEqual(leave.ems_status, 'pending')
        self.assertFalse(leave.ems_document_state)

    def test_undoing_a_cancellation_returns_the_request_to_where_it_stood(self):
        leave = self._create_leave(self.type_health, self._monday())
        leave.action_approve()
        leave._force_cancel("Test cancelled by mistake")
        self.assertEqual(leave.ems_status, 'cancel')

        leave.action_ems_undo()

        self.assertEqual(leave.ems_status, 'pending_direction')

    def test_undoing_a_document_sent_back_returns_it_to_validation(self):
        direction = self._direction()
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        self._attach(leave)
        self._return_document(leave)
        self.assertEqual(leave.ems_status, 'pending_document')

        leave.action_ems_undo()
        self.assertEqual(leave.ems_status, 'pending_validation')
        self.assertFalse(leave.ems_document_return_reason)

        leave.action_ems_document_validate()
        self._return_document(leave.with_user(direction), "Test wrong dates")
        head = create_role_user(self, 'head_of_studies', 'absence_undo_return@absence.test',
                                email='absence_undo_return@example.com')
        with self.assertRaises(AccessError):
            leave.with_user(head).action_ems_undo()
        leave.with_user(direction).action_ems_undo()
        self.assertEqual(leave.ems_status, 'pending_direction', "Direction's send-back is Direction's to undo")

    def test_a_new_document_makes_the_send_back_final(self):
        """Once the employee has answered it, undoing follows the sequence: the Head's
        acknowledgement is the last decision left."""
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.action_approve()
        self._attach(leave)
        self._return_document(leave)
        self._attach(leave, name='justificant2.pdf')

        self.assertEqual(self._undo_statuses(leave, 1), ['pending'])

    def test_who_can_undo_follows_who_decided(self):
        """The Head their own decisions, Direction the Head's and its own, the administrator
        all of them - and nobody else."""
        direction = self._direction()
        head = create_role_user(self, 'head_of_studies', 'absence_undo_hos@absence.test',
                                email='absence_undo_hos@example.com')
        admin = create_role_user(self, 'academic_admin', 'absence_undo_admin@absence.test',
                                email='absence_undo_admin@example.com')
        teacher = create_role_user(self, 'teacher', 'absence_undo_teacher@absence.test')
        leave = self._create_leave(self.type_health, self._monday())
        self.assertFalse(leave.with_user(head).ems_can_undo, 'nothing decided yet')
        leave.with_user(head).action_approve()

        self.assertTrue(leave.with_user(head).ems_can_undo)
        self.assertTrue(leave.with_user(direction).ems_can_undo)
        self.assertTrue(leave.with_user(admin).ems_can_undo)
        with self.assertRaises(AccessError):
            leave.with_user(teacher).action_ems_undo()

        leave.with_user(direction).action_ems_direction_done()
        self.assertFalse(leave.with_user(head).ems_can_undo, "Direction's decision is not the Head's to undo")
        with self.assertRaises(AccessError):
            leave.with_user(head).action_ems_undo()
        self.assertTrue(leave.with_user(admin).ems_can_undo, 'the administrator is above Direction')
        leave.with_user(admin).action_ems_undo()
        self.assertEqual(leave.ems_status, 'pending_direction')
        leave.with_user(head).action_ems_undo()
        self.assertEqual(leave.ems_status, 'pending')

    def test_a_head_does_not_undo_a_decision_on_their_own_absence(self):
        head = create_role_user(self, 'head_of_studies', 'absence_undo_own@absence.test')
        self.employee.user_id = head.id
        leave = self._create_leave(self.type_health, self._monday())
        leave.action_approve()

        self.assertFalse(leave.with_user(head).ems_can_undo)

    def test_undoing_tells_the_employee(self):
        """The summary when the absence goes in or out of effect, a note with the new status
        otherwise: the employee's, either way."""
        self._direction()
        owner = self._employee_user('Test Absence Undone', 'absence_undone@absence.test')
        leave = self._create_leave(self.type_health, self._monday())
        leave.action_approve()
        leave.action_ems_direction_done()

        leave.action_ems_undo()
        note = self._last_note(leave)
        self.assertEqual(note.partner_ids, owner.partner_id)
        self.assertIn("Pending Direction", str(note.body))

        leave.action_ems_undo()
        summary = leave.message_ids.filtered(
            lambda message: message.partner_ids == owner.partner_id).sorted('id')[-1]
        self.assertNotEqual(summary, note)
        self.assertIn(self.employee.display_name, str(summary.body))
        self.assertIn("Pending", str(summary.body))

    def test_every_action_of_the_form_is_in_its_actions_dropdown(self):
        """Odoo's own buttons included; its Reset is the one left out, hidden for good, since
        Undo replaces it."""
        arch = self._arch('hr_holidays.hr_leave_view_form', 'form')

        loose = arch.xpath("//header/button")
        self.assertEqual([button.get('name') for button in loose], ['action_reset_confirm'])
        self.assertIn(loose[0].get('invisible'), ('1', 'True'))
        names = arch.xpath("//header/div[@name='ems_actions']/button/@name")
        for name in ('action_approve', 'action_refuse', 'action_cancel', 'action_ems_undo',
                     'action_ems_document_validate', 'action_ems_direction_done'):
            self.assertIn(name, names)
        self.assertFalse(arch.xpath("//button[@name='action_ems_direction_reset']"))

    def test_an_approved_request_is_corrected_by_undoing_it_first(self):
        """Odoo refuses any change that touches the dates of a request in effect, and the type
        recomputes them: the way to correct one is to take the approval back."""
        leave = self._create_leave(self.type_justified, self._monday(), hour_from=9, hour_to=11)
        leave.action_approve()
        with self.assertRaises(ValidationError):
            leave.holiday_status_id = self.type_training
            leave.flush_recordset()

        leave.action_ems_undo()
        leave.holiday_status_id = self.type_training
        leave.action_approve()

        self.assertEqual(leave.holiday_status_id, self.type_training)
        self.assertEqual(leave.ems_status, 'pending_document')

    # --- Who gets told ---------------------------------------------------------------------

    def test_the_department_chief_is_not_told_of_the_approval(self):
        """The Department Chief arranges the cover once the absence is filed; who approves it,
        and when, is not theirs to follow (issue #632)."""
        department = self.env['hr.department'].create({'name': 'Test Department (Notify)'})
        chief = self.env['hr.employee'].create({
            'name': 'Test Chief (Notify)', 'employee_type': 'teacher',
            'user_id': self.env['res.users'].with_context(no_reset_password=True).create({
                'name': 'Test Chief (Notify)', 'login': 'notify_chief@absence.test',
                'groups_id': [Command.link(self.env.ref('base.group_user').id)],
            }).id,
        })
        department.manager_id = chief.id
        self.employee.department_id = department.id
        # Its chief would approve it too, with no area above it: someone else does.
        self.employee.leave_manager_id = create_role_user(
            self, 'head_of_studies', 'notify_chief_head@absence.test').id
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        before = self._emails_to(leave, chief.user_id)

        leave.action_approve()

        self.assertNotIn(chief.user_id.partner_id, leave.message_partner_ids)
        self.assertEqual(self._emails_to(leave, chief.user_id), before)

    def test_the_outcome_message_carries_the_details(self):
        """"Status: Pending → Approved" tells a department chief nothing they can act on."""
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        leave.action_approve()
        body = leave.message_ids.sorted('id')[-1].body

        self.assertIn(self.employee.display_name, body)
        self.assertIn(self.type_justified.name, body)
        self.assertIn('7.50', body, 'the hours it is worth')

    def test_the_outcome_message_leaves_the_reason_out(self):
        """A chief is informed that a colleague is away and of what kind, not why."""
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True,
                                   name='A private matter nobody else should read')

        leave.action_approve()

        self.assertNotIn('private matter', leave.message_ids.sorted('id')[-1].body)

    def test_odoos_own_acceptance_note_is_replaced_not_duplicated(self):
        """Odoo posts a one-liner of its own on validation; ours replaces it rather than
        arriving alongside it."""
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        leave.action_approve()

        bodies = ' '.join(leave.message_ids.mapped('body'))
        self.assertNotIn('has been accepted', bodies)

    def test_a_chief_is_not_informed_of_their_own_absence(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Own)'})
        department.manager_id = self.employee.id
        self.employee.department_id = department.id
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        self.assertFalse(leave._ems_notify_partners())

    def test_an_employee_with_no_department_chief_notifies_nobody_extra(self):
        self.employee.department_id = self.env['hr.department'].create({'name': 'Test Department (Headless)'}).id
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        self.assertFalse(leave._ems_notify_partners())

    def _chiefed_department(self, label, seminar=False):
        """A department for 'self.employee' with a Department Chief and, optionally, a Seminar
        Chief, each with a user of their own."""
        def chief(kind):
            user = create_role_user(self, 'department_chief', f'{kind}_{label.lower()}@absence.test'.replace(' ', '_'))
            return create_role_employee(self, user, name=f'Test {kind} {label}').id

        department = self.env['hr.department'].create({'name': f'Test Department ({label})'})
        department.manager_id = chief('Chief')
        if seminar:
            department.seminar_chief_id = chief('Seminar')
        self.employee.department_id = department.id
        return department

    def test_the_chiefs_are_informed_when_an_absence_is_requested(self):
        """Covering the department is planned ahead: the chiefs hear of it when it is filed,
        not only once it has been decided."""
        department = self._chiefed_department('Requested', seminar=True)
        chiefs = (department.manager_id | department.seminar_chief_id).user_id.partner_id
        user = self._employee_user('Test Absence Requester', 'absence_requester@absence.test')

        leave = self.env['hr.leave'].with_user(user).create({
            'employee_id': self.employee.id, 'holiday_status_id': self.type_justified.id,
            'request_date_from': self._monday(), 'request_date_to': self._monday(),
            'ems_full_day': True, 'ems_submitted': True, 'ems_responsible_declaration': True,
            'name': 'A private matter nobody else should read',
        })

        self.assertEqual(leave.state, 'confirm')
        approver = leave._ems_head_users().partner_id
        self.assertFalse((chiefs - approver) & leave.message_partner_ids,
                         'told, not following it, unless they approve it too (issue #632)')
        # One each: with no area above this department its chief is also the approver, whose
        # summary is the one asking for the approval.
        for chief in chiefs:
            summary = leave.message_ids.filtered(lambda message: chief in message.partner_ids)
            self.assertEqual(len(summary), 1)
            self.assertIn(self.employee.display_name, summary.body)
            self.assertIn(self.type_justified.name, summary.body)
            self.assertNotIn('private matter', summary.body)

    def _emails_to(self, leave, user):
        """The messages about the request this user was emailed."""
        # Searched, not 'message_ids': that leaves out the emails of assigned activities.
        return self.env['mail.message'].search([
            ('model', '=', 'hr.leave'), ('res_id', '=', leave.id),
            ('notification_ids', 'any', [('res_partner_id', '=', user.partner_id.id),
                                         ('notification_type', '=', 'email')]),
        ])

    def test_a_request_emails_the_chiefs_and_the_approver_once_each(self):
        """Each gets the summary in a note of their own (the approver's asks for the approval),
        and the employee, who filed it, none."""
        department = self._chiefed_department('Alone')
        chief = department.manager_id.user_id
        owner = self._employee_user('Test Absence Alone', 'absence_alone@absence.test')
        head = create_role_user(self, 'head_of_studies', 'absence_alone_head@absence.test')
        self.employee.leave_manager_id = head.id

        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        for_chief, for_head = self._emails_to(leave, chief), self._emails_to(leave, head)
        self.assertEqual(len(for_chief), 1)
        self.assertEqual(len(for_head), 1)
        self.assertEqual(for_chief.partner_ids, chief.partner_id)
        self.assertEqual(for_head.partner_ids, head.partner_id)
        self.assertEqual((for_chief | for_head).subtype_id, self.env.ref('mail.mt_note'))
        self.assertNotIn('waiting for your approval', for_chief.body)
        self.assertFalse(self._emails_to(leave, owner))

    def test_the_approver_is_emailed_what_has_to_be_covered(self):
        """Odoo's own email for the approval activity only says a document was assigned: the
        approver gets the dates and the hours instead, to arrange the cover (issue #625)."""
        head = create_role_user(self, 'head_of_studies', 'absence_covered_head@absence.test')
        self.employee.leave_manager_id = head.id

        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True,
                                   name='A private matter nobody else should read')

        self.assertEqual(self._activity_users(leave, 'hr_holidays.mail_act_leave_approval'), head)
        email = self._emails_to(leave, head)
        self.assertEqual(len(email), 1, "not Odoo's own on top")
        self.assertIn(self.employee.display_name, email.body)
        self.assertIn(self.type_justified.name, email.body)
        self.assertIn(leave._ems_when(), email.body)
        self.assertIn('7.50', email.body)
        self.assertIn('waiting for your approval', email.body)
        self.assertNotIn('private matter', email.body)

    def test_an_approver_who_is_also_the_chief_gets_one_email(self):
        department = self._chiefed_department('Both')
        chief = department.manager_id.user_id
        self.employee.leave_manager_id = chief.id

        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        self.assertIn(chief.partner_id, leave.message_partner_ids)
        email = self._emails_to(leave, chief)
        self.assertEqual(len(email), 1)
        self.assertIn('waiting for your approval', email.body)

    def test_an_approval_emails_the_employee_once(self):
        """The summary, and not Odoo's "Status: Pending → Approved" as a second email."""
        owner = self._employee_user('Test Absence Once', 'absence_once@absence.test')
        # No supporting document, so no upload activity emailed alongside.
        leave = self._create_leave(self.type_health, self._monday(), ems_full_day=True)
        # Field tracking is written at commit time, which a test never reaches, and not at
        # all for a record created in the same transaction.
        self.env.cr.precommit.run()
        before = self._emails_to(leave, owner)

        leave.action_approve()
        self.env.cr.precommit.run()

        outcome = self._emails_to(leave, owner) - before
        self.assertEqual(len(outcome), 1)
        self.assertIn(self.employee.display_name, outcome.body)
        tracking = leave.message_ids.filtered(
            lambda message: 'state' in message.tracking_value_ids.field_id.mapped('name'))
        self.assertEqual(tracking.subtype_id, self.env.ref('mail.mt_note'),
                         'still on the request, as a note')

    def test_the_seminar_chief_is_informed_too(self):
        department = self._chiefed_department('Outcome', seminar=True)
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        self.assertEqual(leave._ems_notify_partners(),
                         (department.manager_id | department.seminar_chief_id).user_id.partner_id)

    def test_a_seminar_chief_is_not_informed_of_their_own_absence(self):
        department = self._chiefed_department('Own Seminar')
        department.seminar_chief_id = self.employee.id

        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        self.assertEqual(leave._ems_notify_partners(), department.manager_id.user_id.partner_id)

    # --- Whose hands the request is in (issue #632) -----------------------------------------

    def _stage_fixture(self, label):
        """An employee with a user, a Department Chief and a Seminar Chief, a Head and a
        Director, each with a user of their own: everybody the request can reach."""
        department = self._chiefed_department(label, seminar=True)
        slug = label.lower().replace(' ', '_')
        owner = self._employee_user(f'Test Absence {label}', f'absence_{slug}@absence.test')
        owner.email = f'absence_{slug}@example.com'
        head = create_role_user(self, 'head_of_studies', f'absence_{slug}_head@absence.test',
                                email=f'absence_{slug}_head@example.com')
        self.employee.leave_manager_id = head.id
        direction = self._direction()
        chiefs = (department.manager_id | department.seminar_chief_id).user_id
        return owner, head, direction, chiefs

    def _comment(self, leave, user, body):
        """What "Send message" on the request's chatter does."""
        return leave.with_user(user).message_post(
            body=body, message_type='comment', subtype_xmlid='mail.mt_comment')

    def _recipients(self, message):
        return message.notification_ids.res_partner_id

    def test_the_conversation_follows_the_stage(self):
        """The employee and whoever has the request in hand, nobody else: the Head until they
        pass it on to Direction, the Director from then on."""
        owner, head, direction, chiefs = self._stage_fixture('Stage')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        expected = lambda user: (owner | user).partner_id

        self.assertEqual(leave.message_partner_ids, expected(head))
        leave.with_user(head).action_approve()
        self.assertEqual(leave.ems_status, 'pending_document')
        self.assertEqual(leave.message_partner_ids, expected(head))
        self._attach(leave, owner)
        self.assertEqual(leave.message_partner_ids, expected(head))

        leave.with_user(head).action_ems_document_validate()

        self.assertEqual(leave.ems_status, 'pending_direction')
        self.assertEqual(leave.message_partner_ids, expected(direction))
        leave.with_user(direction).action_ems_direction_done()
        self.assertEqual(leave.ems_status, 'approved')
        self.assertEqual(leave.message_partner_ids, expected(direction))

    def test_a_message_on_the_request_reaches_only_the_other_side(self):
        owner, head, direction, chiefs = self._stage_fixture('Talk')
        leave = self._create_leave(self.type_health, self._monday(), ems_full_day=True)

        question = self._comment(leave, head, 'Test can you bring the certificate?')
        answer = self._comment(leave, owner, 'Test yes, tomorrow')

        self.assertEqual(self._recipients(question), owner.partner_id)
        self.assertEqual(self._recipients(answer), head.partner_id)

        leave.with_user(head).action_approve()
        self.assertEqual(leave.ems_status, 'pending_direction')
        later = self._comment(leave, owner, 'Test a question for Direction')
        self.assertEqual(self._recipients(later), direction.partner_id)

    def test_whoever_chose_to_follow_it_stays(self):
        """Only the Head and the Director change hands: anybody else following the request, or
        who wrote on it, keeps receiving it."""
        owner, head, direction, chiefs = self._stage_fixture('Kept')
        colleague = create_role_user(self, 'teacher', 'absence_kept_colleague@absence.test')
        leave = self._create_leave(self.type_health, self._monday(), ems_full_day=True)
        leave.message_subscribe(partner_ids=colleague.partner_id.ids)

        leave.with_user(head).action_approve()

        self.assertIn(colleague.partner_id, leave.message_partner_ids)

    def test_a_document_direction_sends_back_returns_to_the_head(self):
        """The new document is the Head's to validate again, so the request is theirs again,
        and they are told."""
        owner, head, direction, chiefs = self._stage_fixture('Bounce')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.with_user(head).action_approve()
        self._attach(leave, owner)
        leave.with_user(head).action_ems_document_validate()
        before = self._emails_to(leave, head)

        self._return_document(leave.with_user(direction))

        self.assertEqual(leave.ems_status, 'pending_document')
        self.assertEqual(leave._ems_stage_users(), head)
        self.assertIn(head.partner_id, leave.message_partner_ids)
        self.assertNotIn(direction.partner_id, leave.message_partner_ids)
        told = self._emails_to(leave, head) - before
        self.assertEqual(len(told), 1)
        self.assertIn('now in your hands', told.body)

    def test_an_atri_absence_waits_with_the_head_until_it_reaches_direction(self):
        owner, head, direction, chiefs = self._stage_fixture('Atri Head')
        leave = self._atri_leave()

        leave.with_user(head).action_approve()

        self.assertEqual(leave.ems_status, 'pending_atri')
        self.assertEqual(leave._ems_stage_users(), head)
        self.assertNotIn(direction.partner_id, leave.message_partner_ids)
        leave.with_user(owner).action_ems_atri_requested()
        self.assertEqual(leave._ems_stage_users(), direction)

    def test_an_atri_absence_direction_sends_back_stays_with_direction(self):
        """It is settled on the ATRI portal and comes straight back to Direction: the Head is
        not involved again."""
        owner, head, direction, chiefs = self._stage_fixture('Atri Back')
        leave = self._atri_leave()
        leave.with_user(head).action_approve()
        leave.with_user(owner).action_ems_atri_requested()

        self._not_in_atri(leave.with_user(direction))

        self.assertEqual(leave.ems_status, 'pending_atri')
        self.assertEqual(leave._ems_stage_users(), direction)
        self.assertIn(direction.partner_id, leave.message_partner_ids)
        self.assertNotIn(head.partner_id, leave.message_partner_ids)

        # The escalation goes to whoever has it, too.
        self._run_reminders_on(leave.request_date_to + timedelta(days=4))
        report = leave.message_ids.filtered(lambda m: 'still not confirmed' in m.body)
        self.assertEqual(report.partner_ids, direction.partner_id)
        self.assertEqual(self._activity_users(leave, ATRI_OVERDUE), direction)

    def test_undoing_direction_hands_it_back_to_the_head(self):
        owner, head, direction, chiefs = self._stage_fixture('Undo Stage')
        leave = self._create_leave(self.type_health, self._monday(), ems_full_day=True)
        leave.with_user(head).action_approve()
        self.assertEqual(leave.ems_status, 'pending_direction')
        before = self._emails_to(leave, head)

        leave.with_user(direction).action_ems_undo()

        self.assertEqual(leave.ems_status, 'pending')
        self.assertIn(head.partner_id, leave.message_partner_ids)
        self.assertNotIn(direction.partner_id, leave.message_partner_ids)
        told = self._emails_to(leave, head) - before
        self.assertEqual(len(told), 1, "the approval's own email says it, nothing on top")
        self.assertIn('waiting for your approval', told.body)

    def test_waiving_the_document_hands_it_to_direction(self):
        """Waiving (issue #634) passes it on like validating does (issue #632): the Director
        follows it and is told, and undoing the waiver gives it back to the Head."""
        owner, head, direction, chiefs = self._stage_fixture('Waive Stage')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.with_user(head).action_approve()
        self.assertEqual(leave.ems_status, 'pending_document')

        leave.with_user(head).action_ems_document_waive()

        self.assertEqual(leave.ems_status, 'pending_direction')
        self.assertEqual(leave.message_partner_ids, (owner | direction).partner_id)
        self.assertTrue(leave.message_ids.filtered(
            lambda message: direction.partner_id in message.partner_ids
            and 'It is now in your hands' in message.body))

        leave.with_user(head).action_ems_undo()

        self.assertEqual(leave.ems_status, 'pending_document')
        self.assertEqual(leave.message_partner_ids, (owner | head).partner_id)

    # --- What the Department Chief and the Seminar Chief hear afterwards ----------------------

    def _department_notes(self, leave, chiefs):
        return leave.message_ids.filtered(lambda message: chiefs.partner_id <= message.partner_ids)

    def test_the_department_is_told_when_the_absence_will_not_take_place(self):
        owner, head, direction, chiefs = self._stage_fixture('Refused Cover')
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        announced = self._department_notes(leave, chiefs)

        leave.with_user(head).with_context(ems_change_message='Test not this week').action_refuse()

        told = self._department_notes(leave, chiefs) - announced
        self.assertEqual(len(told), 1)
        self.assertIn('will not take place', told.body)
        self.assertNotIn('not this week', told.body, "the reason is the employee's alone")
        self.assertEqual(told.subtype_id, self.env.ref('mail.mt_note'))

        leave.with_user(head).action_ems_undo()

        reopened = self._department_notes(leave, chiefs) - announced - told
        self.assertEqual(len(reopened), 1)
        self.assertIn('going ahead again', reopened.body)

    def test_the_department_is_told_of_a_cancellation(self):
        owner, head, direction, chiefs = self._stage_fixture('Cancelled Cover')
        leave = self._create_leave(self.type_health, self._monday(), ems_full_day=True)
        announced = self._department_notes(leave, chiefs)

        leave._force_cancel('Test no longer needed')

        told = self._department_notes(leave, chiefs) - announced
        self.assertEqual(len(told), 1)
        self.assertIn('cancelled', told.body)

    def test_the_department_is_told_when_the_dates_or_the_type_change(self):
        owner, head, direction, chiefs = self._stage_fixture('Moved Cover')
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        announced = self._department_notes(leave, chiefs)
        next_day = leave.request_date_from + timedelta(days=1)

        leave.with_user(head).write({'request_date_from': next_day, 'request_date_to': next_day})

        told = self._department_notes(leave, chiefs) - announced
        self.assertEqual(len(told), 1)
        self.assertIn('have changed', told.body)
        self.assertIn(leave._ems_when(), told.body)

        leave.with_user(head).write({'holiday_status_id': self.type_health.id})
        self.assertEqual(len(self._department_notes(leave, chiefs) - announced), 2)

        leave.with_user(head).write({'request_date_from': next_day, 'name': 'Test same dates'})
        self.assertEqual(len(self._department_notes(leave, chiefs) - announced), 2,
                         'nothing that changes the cover, nothing to tell')

    def test_the_department_hears_nothing_else(self):
        """Approvals, the document, Direction's review: none of it is theirs."""
        owner, head, direction, chiefs = self._stage_fixture('Quiet Cover')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        announced = self._department_notes(leave, chiefs)

        leave.with_user(head).action_approve()
        self._attach(leave, owner)
        leave.with_user(head).action_ems_document_validate()
        leave.with_user(direction).action_ems_direction_done()

        self.assertEqual(self._department_notes(leave, chiefs), announced)
        for chief in chiefs:
            self.assertEqual(len(self._emails_to(leave, chief)), 1, 'the announcement alone')

    def test_the_department_is_told_when_a_pending_request_is_withdrawn(self):
        owner, head, direction, chiefs = self._stage_fixture('Withdrawn Cover')
        # Odoo only lets a request be deleted before it starts.
        day = self.env['ems.datetime_utils'].get_local_today() + timedelta(days=7)
        leave = self._create_leave(self.type_justified, day - timedelta(days=day.weekday()),
                                   ems_full_day=True)
        when = leave._ems_when()

        leave.unlink()

        told = self.env['mail.message'].search([
            ('partner_ids', 'in', chiefs.partner_id.ids), ('body', 'ilike', 'will not take place')])
        self.assertEqual(len(told), 1)
        self.assertEqual(told.partner_ids, chiefs.partner_id)
        self.assertIn(when, told.body)

    def test_resetting_the_followers_of_an_older_request(self):
        """What the upgrade does to requests filed before issue #632, which the Department
        Chief, the Seminar Chief and the Director followed from the start."""
        owner, head, direction, chiefs = self._stage_fixture('Legacy')
        leave = self._create_leave(self.type_sick_leave, self._monday(), ems_full_day=True)
        leave.message_subscribe(partner_ids=(chiefs | direction).partner_id.ids)
        refused = self._create_leave(self.type_justified, self._monday() + timedelta(days=7),
                                     ems_full_day=True)
        refused.action_refuse()
        refused.message_subscribe(partner_ids=(chiefs | direction).partner_id.ids)

        (leave | refused)._ems_reset_followers()

        self.assertEqual(leave.message_partner_ids, (owner | head).partner_id)
        self.assertFalse(chiefs.partner_id & refused.message_partner_ids)
        self.assertIn(direction.partner_id, refused.message_partner_ids,
                      'a closed request keeps whoever had it')

    # --- Per-employee report ---------------------------------------------------------------

    def test_absence_carries_the_school_year_it_falls_in(self):
        """A calendar year cuts a school year in half, so the report needs a course of its own
        to filter and group on."""
        leave = self._create_leave(self.type_justified, self._monday())

        self.assertEqual(leave.ems_course_id, self.env.company.current_course_id)

    def test_health_hours_are_reported_separately(self):
        """The figure the centre has to keep under the yearly allowance, as its own column so a
        report grouped by employee can total it."""
        health = self._create_leave(self.type_health, self._monday())
        other = self._create_leave(self.type_justified, self._monday() + timedelta(days=1),
                                   ems_full_day=True)

        self.assertEqual(health.ems_health_hours, health.number_of_hours)
        self.assertEqual(other.ems_health_hours, 0.0)

    def test_the_report_filters_by_course_not_calendar_year(self):
        context = self.env.ref('hr_holidays.action_hr_available_holidays_report').context

        self.assertIn('search_default_ems_current_course', context)
        self.assertNotIn('search_default_filter_date_from', context)

    def test_reported_hours_follow_the_monthly_report_flag(self):
        """The spreadsheet's 'Totals per mes' summed the hours of the rows the manager had
        ticked, and nothing else."""
        counted = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        not_counted = self._create_leave(self.type_sick_leave, self._monday() + timedelta(days=1),
                                         ems_full_day=True)

        self.assertTrue(counted.ems_counts_hours, 'sanity: this type does count')
        self.assertEqual(counted.ems_counted_hours, counted.number_of_hours)
        self.assertFalse(not_counted.ems_counts_hours, 'sick leave stays out of the report')
        self.assertEqual(not_counted.ems_counted_hours, 0.0)

    def test_unticking_the_flag_takes_the_hours_out_of_the_report(self):
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        leave.ems_counts_hours = False

        self.assertEqual(leave.ems_counted_hours, 0.0)

    def test_the_monthly_report_leaves_out_what_never_happened(self):
        """The spreadsheet's formula ignored the status column, so a cancelled request still
        contributed hours nobody was ever absent for."""
        domain = self.env.ref('ems.action_absence_monthly_report').domain

        self.assertIn("('ems_counts_hours', '=', True)", domain)
        self.assertIn("'refuse', 'cancel'", domain)

    # --- Health allowance -------------------------------------------------------------------

    def test_health_allowance_accumulates_over_the_course(self):
        monday = self._monday()
        self._create_leave(self.type_health, monday)
        second = self._create_leave(self.type_health, monday + timedelta(days=1))

        self.assertEqual(second.ems_health_hours_used, 2 * self.full_day_hours)

    def test_health_allowance_ignores_other_absence_types(self):
        monday = self._monday()
        self._create_leave(self.type_training, monday, ems_full_day=True)
        health = self._create_leave(self.type_health, monday + timedelta(days=1))

        self.assertEqual(health.ems_health_hours_used, self.full_day_hours)

    def test_health_allowance_flags_the_excess_without_blocking(self):
        monday = self._monday()
        allowance = self.env.company._ems_health_allowance_hours()
        needed = int(allowance // self.full_day_hours) + 1
        leaves = self.env['hr.leave']
        for offset in range(needed):
            leaves |= self._create_leave(self.type_health, monday + timedelta(days=offset))

        self.assertGreater(leaves[-1].ems_health_hours_used, allowance)
        self.assertTrue(leaves[-1].ems_health_allowance_exceeded, 'the excess is flagged')
        self.assertTrue(all(leave.id for leave in leaves), 'and never blocked')

    # --- Times covering the whole timetable are a whole day (issue #613) ---------------------

    def _add_slots(self, day, *slots):
        """Gives self.employee these (start, end) lessons on day's weekday."""
        calendar = self.employee.resource_calendar_id
        calendar.flexible_hours = False
        for hour_from, hour_to in slots:
            self.env['resource.calendar.attendance'].create({
                'calendar_id': calendar.id, 'name': 'Test Lesson', 'dayofweek': str(day.weekday()),
                'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
            })

    def _timed_leave(self, day, hour_from, hour_to, user=None, **overrides):
        """A request giving times and saying nothing about "Whole day?", as one filed from
        outside the form does."""
        return self.env['hr.leave'].with_user(user or self.env.user).create({
            'employee_id': self.employee.id, 'holiday_status_id': self.type_justified.id,
            'request_date_from': day, 'request_date_to': day,
            'request_hour_from': hour_from, 'request_hour_to': hour_to,
            'ems_submitted': True, 'ems_responsible_declaration': True, **overrides,
        })

    def test_times_covering_the_whole_timetable_are_filed_as_a_whole_day(self):
        """Not coming in at all is a whole day, even when the employee wrote it as the hours of
        their only lessons: it counts the full working day, not those hours."""
        monday = self._monday()
        # The next day, not the next week: a week later can be a public holiday, when nothing
        # is expected of anybody and no times cover anything.
        for day in (monday, monday + timedelta(days=1)):
            self._add_slots(day, (9.0, 11.0), (12.0, 13.0))

        exact = self._timed_leave(monday, 9, 13)
        wider = self._timed_leave(monday + timedelta(days=1), 8, 14.5)

        for leave in (exact, wider):
            self.assertTrue(leave.ems_full_day)
            self.assertEqual(leave.number_of_hours, self.full_day_hours)

    def test_times_leaving_part_of_the_timetable_stay_partial(self):
        monday = self._monday()
        for day in (monday, monday + timedelta(days=1)):
            self._add_slots(day, (9.0, 11.0), (12.0, 13.0))

        left_early = self._timed_leave(monday, 11, 13)
        came_late = self._timed_leave(monday + timedelta(days=1), 9, 12)

        self.assertFalse(left_early.ems_full_day)
        self.assertEqual(left_early.number_of_hours, 2.0)
        self.assertFalse(came_late.ems_full_day)
        self.assertEqual(came_late.number_of_hours, 3.0)

    def test_a_day_without_lessons_is_never_made_a_whole_day(self):
        monday = self._monday()
        self._add_slots(monday + timedelta(days=1), (9.0, 11.0))

        leave = self._timed_leave(monday, 9, 11)

        self.assertFalse(leave.ems_full_day, 'nothing to compare the times with on a Monday')

    def test_whole_day_is_proposed_not_imposed(self):
        """The requester's own answer stands: the lesson may only have been moved, which is
        what the guard duty board arranges for a teacher away at the time of their one lesson."""
        monday = self._monday()
        self._add_slots(monday, (9.0, 11.0))

        leave = self._timed_leave(monday, 9, 11, ems_full_day=False)

        self.assertFalse(leave.ems_full_day)
        self.assertEqual(leave.number_of_hours, 2.0)

    def test_the_form_ticks_whole_day_and_says_why(self):
        monday = self._monday()
        self._add_slots(monday, (9.0, 11.0))
        leave = self.env['hr.leave'].new({
            'employee_id': self.employee.id, 'holiday_status_id': self.type_justified.id,
            'request_date_from': monday, 'request_date_to': monday,
            'ems_full_day': False, 'request_hour_from': 10.0, 'request_hour_to': 11.0,
        })
        self.assertIsNone(leave._onchange_ems_whole_timetable(), 'still in for the first hour')

        leave.request_hour_from = 9.0
        result = leave._onchange_ems_whole_timetable()

        self.assertTrue(leave.ems_full_day)
        self.assertIn('warning', result)
        self.assertNotIn(
            '_onchange_ems_whole_timetable',
            [method.__name__ for method in leave._onchange_methods['ems_full_day']],
            'unticking the box afterwards is not answered by ticking it again')

    def test_a_teacher_filing_their_own_request_gets_the_same_rule(self):
        """Read with the teacher's own rights: the timetable is looked up for them."""
        owner = self._employee_user('Test Absence Whole Day', 'absence_whole_day@absence.test')
        monday = self._monday()
        self._add_slots(monday, (9.0, 11.0))

        leave = self._timed_leave(monday, 9, 11, user=owner)

        self.assertTrue(leave.ems_full_day)

    # --- Corrections to what the employee filed (issue #615) --------------------------------

    def _change_dialog(self, leave, method='action_approve', message=False):
        """The dialog a decision button opens on a corrected request, filled in."""
        action = getattr(leave.with_context(ems_ask_change_message=1), method)()
        self.assertEqual(action['res_model'], 'ems.absence.change_notice_wizard')
        return self.env[action['res_model']].with_context(action['context']).create({'message': message})

    def _partial_health_leave(self):
        """Two hours of a morning: a request whose dates stay as they are when its type is
        corrected, whatever the new type's own "whole day" default."""
        return self._create_leave(self.type_health, self._monday(), hour_from=9, hour_to=11)

    def _last_note(self, leave):
        return leave.message_ids.sorted('id')[-1]

    def test_a_decision_on_a_corrected_request_asks_for_a_message_first(self):
        """The Head changes the type the employee picked and explains why with the decision:
        the employee alone is told what changed, where the request stands and the message."""
        owner = self._employee_user('Test Absence Corrected', 'absence_corrected@absence.test')
        leave = self._partial_health_leave()
        leave.holiday_status_id = self.type_atri

        wizard = self._change_dialog(leave, message="Test file it on the portal too")
        self.assertEqual(leave.state, 'confirm', 'nothing is decided until the dialog is confirmed')
        self.assertIn(self.type_health.ems_short_name, str(wizard.changes))
        wizard.action_confirm()

        # Now an ATRI absence: validated, it waits for the employee's confirmation.
        self.assertEqual(leave.ems_status, 'pending_atri')
        note = self._last_note(leave)
        self.assertEqual(note.partner_ids, owner.partner_id, 'the requester, not every follower')
        self.assertEqual(note.subtype_id, self.env.ref('mail.mt_note'))
        body = str(note.body)
        self.assertIn(self.type_health.ems_short_name, body)
        self.assertIn(self.type_atri.ems_short_name, body)
        self.assertIn("file it on the portal too", body)
        self.assertIn("Pending ATRI confirmation", body)
        self.assertFalse(leave.ems_original_request, 'told once')

    def test_a_blank_message_sends_the_changes_alone(self):
        owner = self._employee_user('Test Absence Unexplained', 'absence_unexplained@absence.test')
        leave = self._create_leave(self.type_health, self._monday())
        tuesday = self._monday() + timedelta(days=1)
        leave.write({'request_date_from': tuesday, 'request_date_to': tuesday})

        self._change_dialog(leave).action_confirm()

        note = self._last_note(leave)
        self.assertEqual(note.partner_ids, owner.partner_id)
        self.assertIn("Dates:", str(note.body))
        self.assertNotIn("Message from", str(note.body))

    def test_a_decision_taken_from_code_reports_the_changes_without_asking(self):
        owner = self._employee_user('Test Absence Batch', 'absence_batch@absence.test')
        leave = self._partial_health_leave()
        leave.holiday_status_id = self.type_atri

        leave.action_approve()

        self.assertEqual(leave.state, 'validate')
        self.assertEqual(self._last_note(leave).partner_ids, owner.partner_id)

    def test_an_untouched_request_is_decided_without_a_dialog(self):
        leave = self._create_leave(self.type_health, self._monday())
        messages = len(leave.message_ids)

        leave.with_context(ems_ask_change_message=1).action_approve()

        self.assertEqual(leave.state, 'validate')
        new = leave.message_ids.sorted('id')[messages:]
        self.assertTrue(new)
        self.assertFalse([body for body in new.mapped('body') if 'Changes made' in str(body)],
                         'only the summaries, no notice of changes')

    def test_the_employees_own_edits_are_not_corrections(self):
        owner = self._employee_user('Test Absence Self Editor', 'absence_self_editor@absence.test')
        leave = self._partial_health_leave()

        leave.with_user(owner).write({'holiday_status_id': self.type_atri.id})

        self.assertFalse(leave.ems_original_request)

    def test_a_correction_that_is_undone_is_not_reported(self):
        leave = self._create_leave(self.type_justified, self._monday(), hour_from=9, hour_to=11)
        leave.holiday_status_id = self.type_training
        leave.holiday_status_id = self.type_justified

        leave.with_context(ems_ask_change_message=1).action_approve()

        self.assertEqual(leave.state, 'validate', 'no dialog: nothing differs any more')
        self.assertFalse(leave.ems_original_request)

    def test_a_correction_on_a_closed_request_is_reported_when_saved(self):
        """No decision is left to carry it, so the employee is told straight away."""
        owner = self._employee_user('Test Absence Late Fix', 'absence_late_fix@absence.test')
        leave = self._partial_health_leave()
        leave.action_refuse()

        leave.holiday_status_id = self.type_atri

        note = self._last_note(leave)
        self.assertEqual(note.partner_ids, owner.partner_id)
        self.assertIn(self.type_atri.ems_short_name, str(note.body))
        self.assertIn("Refused", str(note.body))
        self.assertFalse(leave.ems_original_request)

    def test_direction_explains_a_correction_when_refusing(self):
        direction = self._direction()
        owner = self._employee_user('Test Absence Refused Fix', 'absence_refused_fix@absence.test')
        leave = self._partial_health_leave()
        leave.with_user(direction).write({'holiday_status_id': self.type_atri.id})

        self._change_dialog(leave.with_user(direction), 'action_ems_direction_refuse',
                            "Test not on the portal").with_user(direction).action_confirm()

        self.assertEqual(leave.ems_status, 'refused')
        self.assertEqual(leave.ems_direction_state, 'refused')
        note = self._last_note(leave)
        self.assertEqual(note.partner_ids, owner.partner_id)
        self.assertIn("not on the portal", str(note.body))

    def test_the_dialog_only_takes_decisions(self):
        leave = self._partial_health_leave()
        leave.holiday_status_id = self.type_atri
        wizard = self._change_dialog(leave)
        wizard.method = 'unlink'

        with self.assertRaises(UserError):
            wizard.action_confirm()

    # --- The reason for a refusal -------------------------------------------------------------

    def test_refusing_from_a_button_asks_for_the_reason(self):
        """Always, corrected or not: the dialog is the confirmation too. The reason reaches the
        employee alone and stays on the request."""
        owner = self._employee_user('Test Absence Refused', 'absence_refused@absence.test')
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        wizard = self._change_dialog(leave, 'action_refuse', "Test the exams are that day")
        self.assertTrue(wizard.is_refusal)
        self.assertFalse(wizard.has_changes)
        self.assertEqual(leave.state, 'confirm', 'nothing is refused until the dialog is confirmed')
        wizard.action_confirm()

        self.assertEqual(leave.ems_status, 'refused')
        self.assertEqual(leave.ems_refusal_reason, "Test the exams are that day")
        note = self._last_note(leave)
        self.assertEqual(note.partner_ids, owner.partner_id, 'the requester, not every follower')
        self.assertIn("the exams are that day", str(note.body))
        self.assertNotIn("Changes made", str(note.body))

    def test_the_reason_is_optional(self):
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        messages = len(leave.message_ids)

        self._change_dialog(leave, 'action_refuse').action_confirm()

        self.assertEqual(leave.ems_status, 'refused')
        self.assertFalse(leave.ems_refusal_reason)
        self.assertEqual(len(leave.message_ids), messages + 1, 'only the outcome summary')

    def test_refusing_a_corrected_request_is_one_dialog_for_both(self):
        owner = self._employee_user('Test Absence Refused Both', 'absence_refused_both@absence.test')
        leave = self._partial_health_leave()
        leave.holiday_status_id = self.type_atri

        wizard = self._change_dialog(leave, 'action_refuse', "Test wrong type and not allowed")
        self.assertTrue(wizard.is_refusal and wizard.has_changes)
        wizard.action_confirm()

        body = str(self._last_note(leave).body)
        self.assertEqual(self._last_note(leave).partner_ids, owner.partner_id)
        self.assertIn(self.type_atri.ems_short_name, body)
        self.assertIn("wrong type and not allowed", body)
        self.assertEqual(leave.ems_refusal_reason, "Test wrong type and not allowed")

    def test_the_summary_for_the_chiefs_leaves_the_reason_out(self):
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        self._change_dialog(leave, 'action_refuse', "Test private reason").action_confirm()

        summary = leave.message_ids.filtered(
            lambda message: 'Absence request of' in str(message.body))
        self.assertTrue(summary)
        self.assertNotIn("private reason", "".join(str(body) for body in summary.mapped('body')))

    def test_refusing_from_code_asks_nothing(self):
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        leave.action_refuse()

        self.assertEqual(leave.state, 'refuse')
        self.assertFalse(leave.ems_refusal_reason)

    def test_reopening_a_refused_request_forgets_the_reason(self):
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)
        self._change_dialog(leave, 'action_refuse', "Test not this week").action_confirm()

        leave.action_reset_confirm()

        self.assertFalse(leave.ems_refusal_reason)

    # --- ATRI absences wait for the employee's confirmation (issue #619) ---------------------

    def _atri_leave(self, **overrides):
        return self._create_leave(self.type_atri, self._monday(), ems_full_day=True, **overrides)

    def _not_in_atri(self, leave, reason="Test it is not on the portal"):
        """Through Direction's button and its dialog."""
        action = leave.action_ems_atri_missing()
        self.assertEqual(action['context']['default_kind'], 'atri')
        self.env[action['res_model']].with_user(leave.env.user).with_context(action['context']).create(
            {'reason': reason}).action_return()

    def test_a_validated_atri_absence_always_waits_for_the_employees_confirmation(self):
        """The Head goes first, because employees pick ATRI for what is not and the other way
        round. Then it is in effect, but before Direction reviews it the employee confirms it
        is requested on the portal - always: nothing at filing time lets them skip it."""
        self._direction()
        owner = self._employee_user('Test Absence Atri', 'absence_atri@absence.test')
        leave = self._atri_leave()
        self.assertEqual(leave.ems_status, 'pending', "the Head's first, like any other request")
        self.assertFalse(leave.with_user(owner).ems_can_mark_atri, 'nothing to confirm before that')

        leave.action_approve()

        self.assertEqual(leave.state, 'validate', 'in effect, like any acknowledged absence')
        self.assertEqual(leave.ems_atri_state, 'awaiting')
        self.assertEqual(leave.ems_head_state, 'approved')
        self.assertEqual(leave.ems_status, 'pending_atri')
        self.assertEqual(self._activity_users(leave, 'ems.mail_activity_absence_atri_request'), owner)
        self.assertFalse(self._activity_users(leave, 'ems.mail_activity_absence_direction_review'))
        with self.assertRaises(UserError):
            leave.action_ems_direction_done()

    def test_other_absence_types_never_wait_for_atri(self):
        leave = self._create_leave(self.type_health, self._monday())

        leave.action_approve()

        self.assertEqual(leave.ems_atri_state, 'not_required')
        self.assertEqual(leave.ems_status, 'pending_direction')

    def test_a_type_corrected_into_atri_waits_too(self):
        leave = self._partial_health_leave()
        leave.holiday_status_id = self.type_atri

        leave.action_approve()

        self.assertEqual(leave.ems_status, 'pending_atri')

    def test_the_employee_confirms_and_it_reaches_direction(self):
        direction = self._direction()
        owner = self._employee_user('Test Absence Atri Done', 'absence_atri_done@absence.test')
        leave = self._atri_leave()
        leave.action_approve()
        self.assertTrue(leave.with_user(owner).ems_can_mark_atri)

        leave.with_user(owner).action_ems_atri_requested()

        self.assertEqual(leave.ems_atri_state, 'requested')
        self.assertEqual(leave.ems_status, 'pending_direction')
        self.assertFalse(self._activity_users(leave, 'ems.mail_activity_absence_atri_request'))
        self.assertEqual(self._activity_users(leave, 'ems.mail_activity_absence_direction_review'), direction)

    def test_nobody_else_confirms_and_the_status_is_never_written_by_hand(self):
        owner = self._employee_user('Test Absence Atri Guarded', 'absence_atri_guarded@absence.test')
        stranger = create_role_user(self, 'teacher', 'absence_atri_stranger@absence.test')
        head = create_role_user(self, 'head_of_studies', 'absence_atri_head@absence.test',
                                email='absence_atri_head@example.com')
        sneaked = self.env['hr.leave'].with_user(owner).create({
            'employee_id': self.employee.id, 'holiday_status_id': self.type_atri.id,
            'request_date_from': self._monday() + timedelta(days=1),
            'request_date_to': self._monday() + timedelta(days=1), 'ems_full_day': True,
            'ems_submitted': True, 'ems_responsible_declaration': True, 'ems_atri_state': 'requested',
        })
        self.assertFalse(sneaked.sudo().ems_atri_state, 'not something to file a request with')
        leave = self._atri_leave()
        leave.action_approve()

        self.assertFalse(leave.with_user(stranger).sudo(False).ems_can_mark_atri)
        with self.assertRaises(AccessError):
            leave.with_user(owner).write({'ems_atri_state': 'requested'})
        with self.assertRaises(AccessError):
            leave.with_user(head).write({'ems_atri_state': 'requested'})
        self.assertEqual(leave.ems_status, 'pending_atri')
        leave.with_user(head).action_ems_atri_requested()
        self.assertEqual(leave.ems_status, 'pending_direction', 'the Head may confirm it on their behalf')

    def test_direction_sends_it_back_as_not_in_atri(self):
        """What Direction finds when reviewing it: the employee is told why, it waits for their
        confirmation again and the reminders start over."""
        direction = self._direction()
        head = create_role_user(self, 'head_of_studies', 'absence_atri_back_head@absence.test',
                                email='absence_atri_back_head@example.com')
        owner = self._employee_user('Test Absence Atri Back', 'absence_atri_back@absence.test')
        leave = self._validated_by_head(self._atri_leave())
        self.assertEqual(leave.ems_status, 'pending_direction')
        leave.sudo().write({'ems_atri_reminder_date': self._monday(), 'ems_atri_escalated': True})
        with self.assertRaises(AccessError):
            leave.with_user(head).action_ems_atri_missing()

        self._not_in_atri(leave.with_user(direction), "Test the dates on the portal differ")

        self.assertEqual(leave.ems_status, 'pending_atri')
        self.assertEqual(leave.ems_atri_return_reason, "Test the dates on the portal differ")
        self.assertFalse(leave.ems_atri_reminder_date)
        self.assertFalse(leave.ems_atri_escalated)
        note = self._last_note(leave)
        self.assertEqual(note.partner_ids, owner.partner_id)
        self.assertIn("dates on the portal differ", str(note.body))
        activity = leave.activity_ids.filtered(
            lambda activity: activity.activity_type_id == self.env.ref('ems.mail_activity_absence_atri_request'))
        self.assertIn("dates on the portal differ", str(activity.note), "the employee's to-do says why too")

        leave.with_user(owner).action_ems_atri_requested()
        self.assertEqual(leave.ems_status, 'pending_direction')
        self.assertFalse(leave.ems_atri_return_reason, 'answered')

    def test_insufficient_documentation_of_an_atri_absence_goes_back_to_atri(self):
        """An ATRI absence is justified on the portal, so Direction's "Documentation
        insufficient" sends it to the employee's ATRI step and back to Direction - never to
        "Awaiting documentation", which is the Head's and asks for a file in EMS (issue #627)."""
        direction = self._direction()
        owner = self._employee_user('Test Absence Atri Docs', 'absence_atri_docs@absence.test')
        leave = self._validated_by_head(self._atri_leave())
        self.assertEqual(leave.ems_status, 'pending_direction')
        document_state = leave.ems_document_state

        action = leave.with_user(direction).action_ems_document_insufficient()
        self.assertEqual(action['context']['default_kind'], 'atri_document')
        self.env[action['res_model']].with_user(direction).with_context(action['context']).create(
            {'reason': "Test the certificate is missing on the portal"}).action_return()

        self.assertEqual(leave.ems_status, 'pending_atri')
        self.assertEqual(leave.ems_document_state, document_state, 'nothing is asked for in EMS')
        self.assertEqual(leave.ems_atri_return_reason, "Test the certificate is missing on the portal")
        note = self._last_note(leave)
        self.assertEqual(note.partner_ids, owner.partner_id)
        self.assertIn("documentation of your absence", str(note.body))
        self.assertIn("certificate is missing on the portal", str(note.body))

        leave.with_user(owner).action_ems_atri_requested()
        self.assertEqual(leave.ems_status, 'pending_direction', 'straight back to Direction')

    def test_an_atri_absence_is_never_sent_back_for_a_document_in_ems(self):
        direction = self._direction()
        leave = self._validated_by_head(self._atri_leave())

        with self.assertRaises(UserError):
            leave.with_user(direction)._ems_return_document("Test attach it here")

        self.assertEqual(leave.ems_status, 'pending_direction')

    def test_only_an_atri_absence_under_direction_is_sent_back_as_not_in_atri(self):
        self._direction()
        health = self._create_leave(self.type_health, self._monday())
        health.action_approve()
        waiting = self._create_leave(self.type_atri, self._monday() + timedelta(days=1), ems_full_day=True)
        waiting.action_approve()

        for leave in (health, waiting):
            with self.assertRaises(UserError):
                leave.action_ems_atri_missing()

    def test_the_employee_is_reminded_to_confirm_it(self):
        """Like the supporting document: every day once the absence is over, and the Head is
        told once a few days later."""
        owner = self._employee_user('Test Absence Atri Reminded', 'absence_atri_reminded@absence.test')
        head = create_role_user(self, 'head_of_studies', 'absence_atri_reminded_head@absence.test')
        self.employee.leave_manager_id = head.id
        leave = self._atri_leave()
        leave.action_approve()
        last_day = leave.request_date_to
        reminders = lambda: leave.message_ids.filtered(
            lambda m: owner.partner_id in m.partner_ids and 'Reminder' in m.body)
        told = lambda: leave.message_ids.filtered(
            lambda m: head.partner_id in m.partner_ids and 'still not' in m.body)

        self._run_reminders_on(last_day)
        self.assertFalse(reminders(), 'not while the absence is still going on')
        self._run_reminders_on(last_day + timedelta(days=1))
        self._run_reminders_on(last_day + timedelta(days=1))
        self.assertEqual(len(reminders()), 1, 'once a day')
        self.assertIn("ATRI", str(reminders().body))
        self.assertFalse(told())
        self._run_reminders_on(last_day + timedelta(days=3))
        self._run_reminders_on(last_day + timedelta(days=4))
        self.assertEqual(len(reminders()), 3)
        self.assertEqual(len(told()), 1, 'the Head once')
        self.assertEqual(self._activity_users(leave, 'ems.mail_activity_absence_atri_overdue'), head)

        leave.with_user(owner).action_ems_atri_requested()
        self._run_reminders_on(last_day + timedelta(days=5))
        self.assertEqual(len(reminders()), 3, 'nothing once it is confirmed')
        self.assertFalse(self._activity_users(leave, 'ems.mail_activity_absence_atri_overdue'))

    def test_undoing_around_the_atri_step(self):
        direction = self._direction()
        head = create_role_user(self, 'head_of_studies', 'absence_atri_undo_head@absence.test',
                                email='absence_atri_undo_head@example.com')
        leave = self._atri_leave()
        leave.action_approve()

        leave.with_user(head).action_ems_undo()
        self.assertEqual(leave.ems_status, 'pending', "the Head's validation is what there was to undo")

        leave.action_approve()
        self.assertEqual(leave.ems_status, 'pending_atri', 'never confirmed, so it waits again')
        leave.action_ems_atri_requested()
        self.assertEqual(self._undo_statuses(leave, 1), ['pending'])
        leave.action_approve()
        self.assertEqual(leave.ems_status, 'pending_direction', 'already confirmed: not asked twice')

        self._not_in_atri(leave.with_user(direction))
        self.assertFalse(leave.with_user(head).ems_can_undo, "sent back by Direction: not the Head's to undo")
        leave.with_user(direction).action_ems_undo()
        self.assertEqual(leave.ems_status, 'pending_direction')
        self.assertEqual(leave.ems_atri_state, 'requested')
        self.assertFalse(leave.ems_atri_return_reason)
