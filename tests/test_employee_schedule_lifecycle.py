from odoo.tests.common import TransactionCase


class TestEmployeeScheduleLifecycle(TransactionCase):

    def test_create_teacher_gets_personal_calendar_from_default_framework(self):
        employee = self.env['hr.employee'].create({
            'name': 'Test New Teacher (Employee Schedule Lifecycle)',
            'employee_type': 'teacher',
        })

        self.assertTrue(employee.resource_calendar_id)
        self.assertFalse(employee.resource_calendar_id.is_framework)
        self.assertEqual(employee.resource_calendar_id.source_framework_id, self.env.company.default_schedule_framework_id)

    def test_two_teachers_never_share_a_calendar(self):
        employee_a = self.env['hr.employee'].create({
            'name': 'Test Teacher A (Employee Schedule Lifecycle)',
            'employee_type': 'teacher',
        })
        employee_b = self.env['hr.employee'].create({
            'name': 'Test Teacher B (Employee Schedule Lifecycle)',
            'employee_type': 'teacher',
        })

        self.assertNotEqual(employee_a.resource_calendar_id, employee_b.resource_calendar_id)

    def test_rename_teacher_renames_personal_calendar(self):
        employee = self.env['hr.employee'].create({
            'name': 'Test Rename A (Employee Schedule Lifecycle)',
            'employee_type': 'teacher',
        })
        old_name = employee.resource_calendar_id.name

        employee.write({'name': 'Test Rename B (Employee Schedule Lifecycle)'})

        self.assertNotEqual(employee.resource_calendar_id.name, old_name)
        self.assertIn('Test Rename B (Employee Schedule Lifecycle)', employee.resource_calendar_id.name)

    def test_create_teacher_calendar_gets_employee_id_and_course_id(self):
        # Added 2026-08-06 - see plans/course_transition_teacher_schedule_archival.md: a personal
        # calendar's own 'employee_id'/'course_id' make it a queryable historical record on its own
        # terms, set once at creation.
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee Id (Employee Schedule Lifecycle)',
            'employee_type': 'teacher',
        })

        self.assertEqual(employee.resource_calendar_id.employee_id, employee)
        self.assertEqual(employee.resource_calendar_id.course_id, self.env.company.current_course_id)

    def test_get_employee_prefers_stored_employee_id_over_a_superseded_link(self):
        # The whole point of storing 'employee_id' (rather than only ever reverse-searching
        # 'hr.employee.resource_calendar_id') is that it keeps working once this calendar is no
        # longer any employee's *current* one - simulated here by pointing the employee at a
        # different calendar afterwards, without touching the original's own 'employee_id'.
        employee = self.env['hr.employee'].create({
            'name': 'Test Superseded Calendar (Employee Schedule Lifecycle)',
            'employee_type': 'teacher',
        })
        original_calendar = employee.resource_calendar_id
        employee.resource_calendar_id = self.env['resource.calendar'].create({'name': 'Test Next Course Calendar (Employee Schedule Lifecycle)'})

        self.assertEqual(original_calendar.get_employee(), employee)

    def test_rename_does_not_touch_framework_calendar(self):
        employee = self.env['hr.employee'].create({
            'name': 'Test Rename Framework (Employee Schedule Lifecycle)',
            'employee_type': 'teacher',
        })
        framework = self.env.company.default_schedule_framework_id
        employee.resource_calendar_id = framework
        framework_name = framework.name

        employee.write({'name': 'Test Rename Framework Renamed (Employee Schedule Lifecycle)'})

        self.assertEqual(framework.name, framework_name)

    def test_unlink_teacher_deletes_personal_calendar(self):
        employee = self.env['hr.employee'].create({
            'name': 'Test Unlink (Employee Schedule Lifecycle)',
            'employee_type': 'teacher',
        })
        calendar = employee.resource_calendar_id

        employee.unlink()

        self.assertFalse(calendar.exists())

    def test_unlink_teacher_does_not_delete_framework_calendar(self):
        employee = self.env['hr.employee'].create({
            'name': 'Test Unlink Framework (Employee Schedule Lifecycle)',
            'employee_type': 'teacher',
        })
        framework = self.env.company.default_schedule_framework_id
        employee.resource_calendar_id = framework

        employee.unlink()

        self.assertTrue(framework.exists())

    def test_unlink_one_of_two_employees_sharing_a_calendar_keeps_it(self):
        shared_calendar = self.env['resource.calendar'].create({'name': 'Test Shared Calendar (Employee Schedule Lifecycle)'})
        employee_a = self.env['hr.employee'].create({
            'name': 'Test Shared A (Employee Schedule Lifecycle)',
            'employee_type': 'teacher',
        })
        employee_a.resource_calendar_id = shared_calendar
        employee_b = self.env['hr.employee'].create({
            'name': 'Test Shared B (Employee Schedule Lifecycle)',
            'employee_type': 'asp',
        })
        employee_b.resource_calendar_id = shared_calendar

        employee_a.unlink()

        self.assertTrue(shared_calendar.exists())
