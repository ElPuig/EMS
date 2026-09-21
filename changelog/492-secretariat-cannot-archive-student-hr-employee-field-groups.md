# Fixes

## Secretariat could not archive (register the withdrawal of) a student:

Archiving a student from the contact list/form, or pressing "Withdrawal" in the Enrollment
proposal screen, failed for the secretariat with "The fields ..., which you are trying to read,
are not available for employee public profiles." Both entry points run the same withdrawal
wizard, and the wizard broke halfway through, while freezing the student's academic history.

Root cause: `ems.group_secretary` has no access to `hr.employee`, so Odoo serves the group's
tutor through the `hr.employee.public` mirror. Reading any employee field in Python
(`ems.student.year_record._generate_one()`'s `group.tutor_id.name`) makes the ORM prefetch every
field the user may access, and the eight fields EMS adds to `hr.employee` without a `groups=`
restriction - `schedule_import_code`, `pending_identification` and the six stored `google_ws_*`
ones - were pulled into that batch and rejected. This is the rule stated in Odoo's own
`hr.employee` class docstring: any field that exists on `hr.employee` and not on
`hr.employee.public` must be group-restricted.

The fix declares `groups="base.group_system,hr.group_hr_user,ems.group_teacher"` (the trio
already used by `employee_type`) on all eleven EMS-only employee fields, so they are no longer
prefetched for users who reach an employee through the public profile. This closes the whole
class of failure, not just the withdrawal screen: any server-side code path reading an employee
field from a secretariat session was exposed to the same error.

# Internal changes

## Year-record generator now elevates its arguments, not only the model:

`ems.student.year_record._generate_one()` applies `sudo()` to the `student`/`group` it receives.
Every caller already reaches the generator through `.sudo()` - the operator registering an exit
is a secretary, with no rights over grades, attendance or employees - but that only elevates
`self`, while the records passed in still carried the caller's own environment.

## Structural guard over `hr.employee` field permissions:

A new test fails, listing the offending field names, whenever a field is added to `hr.employee`
(and not to `hr.employee.public`) without a `groups=` restriction. The failure it prevents
surfaces far from its cause - in any unrelated feature that happens to read an employee field -
so it is not something code review reliably catches. The withdrawal flow itself also gains a
regression test that applies the wizard as a secretary user; its existing coverage ran entirely
as an administrator, which is why this reached production unnoticed.
