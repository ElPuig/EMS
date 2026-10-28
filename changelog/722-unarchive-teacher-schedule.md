# Fixes

## Unarchiving a teacher restores their schedule:
- Archiving a teacher archives their personal calendar and every block on it; unarchiving only reactivated the calendar, so the teacher came back with an empty schedule and without their roll-calls.
- The blocks archived together with the calendar are now marked (`archived_with_calendar` on `resource.calendar.attendance`), and unarchiving the teacher reactivates exactly those through the ORM, so the roll-calls, the groups' reference classroom and the public schedule PDF follow. A block archived earlier for another reason (a superseded version, a lost room conflict, archived by hand) stays archived.
- Teachers archived before this version are not covered (no migration, decided with the developer): if one of them comes back, their blocks can be restored by hand from `odoo shell`.
