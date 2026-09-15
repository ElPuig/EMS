# Fixes

## Student ID (IDALU) required for new students and unique across all contacts:

- A new student (or applicant, alumni, withdrawal, expelled contact) can no longer be created
  without a Student ID (IDALU), and a family/provider contact can't be turned into a student
  without one. Removing the IDALU of a student is refused too.
- The rule applies going forward only: students that were created before without an IDALU keep
  working normally (editing, course transition, withdrawal, graduation) and get their IDALU filled
  in whenever it is available.
- The IDALU is unique across every contact, archived ones included. Typing one that already
  belongs to someone shows who holds it (e.g. an archived former student coming back), so that
  record is reopened instead of registering the same student twice. Enforced both in Python
  (before saving, so the message can name the holder) and with a database `UNIQUE` constraint.
- The IDALU is stripped of surrounding spaces, and a blank one is stored as empty.
- Merging two contacts (Odoo's "Merge" action) now hands the source's IDALU over to the destination
  contact instead of failing on the new unique constraint, which is how an existing duplicate
  student gets fixed.
- The student form marks the IDALU as required while creating a student.
- Before deploying, production must have no repeated IDALU (verified on the 2026-09-14 21:52
  dump: none). If one slipped in, the upgrade logs an ERROR and skips the database constraint,
  while the Python check keeps protecting new records.

## Test suite failed to load (two imports merged into one line):

- `tests/__init__.py` had `test_portal_schedule_tour` and `test_guard_duty_board` imports glued
  together on a single line (a syntax error), so no EMS test module could be imported at all.

# Internal changes

## Test fixtures get a unique IDALU:

- `tests/common.py::next_student_id()` returns a unique `TEST000001`-style IDALU; every test
  fixture creating a student-lifecycle contact now uses it (it can never match a real, digits-only
  IDALU in the development database).
- The demo students (`demo/contacts/student.xml`) got an IDALU too.
