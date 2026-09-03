# -*- coding: utf-8 -*-

import base64
from datetime import timedelta

from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from ..models.employees.absence import TIME_OFF_GROUP_XMLIDS
from .common import mock_outgoing_email

# The nine absence types seeded by data/cat/hr.leave.type.csv, with the native flags each one
# needs: (xmlid, requires a supporting document).
EXPECTED_LEAVE_TYPES = (
    ('ems.leave_type_sick_leave', True),
    ('ems.leave_type_health', False),
    ('ems.leave_type_medical_appointment', True),
    ('ems.leave_type_invasive_test', True),
    ('ems.leave_type_menstrual_flexibility', False),
    ('ems.leave_type_training', False),
    ('ems.leave_type_justified', False),
    ('ems.leave_type_service_assignment', False),
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

    def test_leave_manager_of_the_area_manager_is_themselves_excluded(self):
        """The Area Manager cannot approve their own absence: their own leave_manager_id falls
        back to the Director rather than pointing at themselves."""
        top, _child, manager = self._create_area('SelfApproval')
        director = self._create_employee('Test Director (SelfApproval)', with_user=True)
        self.env.company.director_id = director.id
        manager.department_id = top.id

        self.assertNotEqual(manager.leave_manager_id, manager.user_id)
        self.assertEqual(manager.leave_manager_id, director.user_id)

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
        moment the request is approved would make 'Missing document' impossible to ever clear."""
        arch = self._arch('hr_holidays.hr_leave_view_form', 'form')

        for node in arch.xpath("//field[@name='supported_attachment_ids'] | "
                               "//label[@for='supported_attachment_ids']"):
            self.assertNotIn('state', node.get('invisible') or '',
                             'the approval state does not hide the justification')

    def _employee_user(self, name, login):
        """A plain internal user for 'self.employee', with no Time Off group whatsoever.

        Spelled out rather than left to Odoo's default: 'base.default_user' still carries the
        Time Off groups hr_holidays hands out at install time, and a user copied from it would
        be an officer - proving nothing about what an ordinary employee can do.
        """
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': name, 'login': login,
            'groups_id': [Command.link(self.env.ref('base.group_user').id),
                          Command.link(self.env.ref('ems.group_teacher').id)],
        })
        self.employee.user_id = user.id
        return user

    def test_the_justification_can_be_filed_after_the_approval(self):
        """The other half of the same rule, server-side: a medical certificate is usually handed
        in days after the absence itself, and Direction's "Missing document" check exists to
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

    # --- Refusing is final --------------------------------------------------------------------

    def test_refusing_a_request_asks_for_a_confirmation(self):
        """Nobody at the centre can undo it: Odoo reserves resetting a refused request to the
        Time Off Administrator group (hr.leave._check_approval_update), which
        res.users._ems_sync_time_off_groups deliberately leaves nobody holding. The employee has
        to file the whole request again, so the one stray click that causes that is confirmed
        first - on all three screens the button appears on."""
        for xmlid, view_type in (('hr_holidays.hr_leave_view_form', 'form'),
                                 ('hr_holidays.hr_leave_view_tree', 'list'),
                                 ('hr_holidays.hr_leave_view_kanban', 'kanban')):
            arch = self._arch(xmlid, view_type)

            buttons = arch.xpath("//button[@name='action_refuse']")
            self.assertTrue(buttons, xmlid)
            for button in buttons:
                self.assertTrue(button.get('confirm'), f'{xmlid} ({view_type})')

    def test_refusing_is_not_reversible_at_the_centre(self):
        """What the confirmation is warning about, asserted rather than assumed: this is the
        rule the wording of the dialog rests on."""
        leave = self._create_leave(self.type_justified, self._monday())
        leave.action_refuse()
        approver = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Absence Approver', 'login': 'absence_approver@absence.test',
            'groups_id': [Command.link(self.env.ref('base.group_user').id),
                          Command.link(self.env.ref('hr_holidays.group_hr_holidays_user').id)],
        })

        self.assertEqual(leave.state, 'refuse')
        self.assertFalse(leave.with_user(approver).can_reset,
                         'not even an officer gets the Reset button on a refused request')
        with self.assertRaises(Exception):
            leave.with_user(approver).action_reset_confirm()

    # --- Who gets told ---------------------------------------------------------------------

    def test_the_department_chief_is_informed_when_an_absence_is_approved(self):
        """The Google form asked for the department only to look up who to copy. EMS knows the
        employee's own chief, so the question went away and the answer is derived."""
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
        leave = self._create_leave(self.type_justified, self._monday(), ems_full_day=True)

        leave.action_approve()

        self.assertIn(chief.user_id.partner_id, leave.message_partner_ids)

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
