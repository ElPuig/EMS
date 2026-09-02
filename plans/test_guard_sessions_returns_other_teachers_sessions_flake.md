# `test_guard_sessions_returns_other_teachers_sessions` full-suite flake

**Status: current as of 2026-09-02.** Not yet investigated in depth — found incidentally
while running the full, unscoped `./test.sh` as the final gate for an unrelated branch
(386-strike-warn-the-family-only-when-kicked-out). Unrelated to that branch's own changes
(strike/company/settings files only) — this is a pre-existing gap in a different model's
test.

## What happened

`tests/test_attendance_session.py::TestAttendanceSessionHeader.test_guard_sessions_returns_other_teachers_sessions`
failed with `AssertionError: 2 != 1` when running the full `./test.sh` (all classes, one
shard, `ems_shard_fast`), but is presumably fine when run scoped/in isolation (not directly
re-verified here, but this class is not in any known flaky-test list).

## Root cause (traced from the code, not yet from a reproduction)

`ems.attendance_session_header.get_guard_sessions(date)`
(`models/attendance/attendance_session.py:451`) queries **every** session in the database
for the given date, excluding only sessions owned by the calling user's own employee — with
no scoping to a specific schedule, company, or test fixture:

```python
domain = [['date', '=', date]]
if own_emp:
    domain += ['!', '|', ['template_teacher_ids', 'in', own_emp.id], ['session_teacher_id', '=', own_emp.id]]
```

The test creates exactly one session dated `date.today()` and asserts `get_guard_sessions`
returns exactly 1 — but this only holds if no *other* test class running earlier in the same
shard/DB has also left behind (or is concurrently holding open, depending on transaction
timing) a session dated today that isn't owned by `other_teacher_user`'s employee. Any other
test creating an `ems.attendance_session_header` with today's date (there are several across
the suite — attendance sessions are dated `date.today()` by convention in many test fixtures)
is a candidate. `TransactionCase` rolls back each test method's own writes, so the leak would
have to come from `setUpClass`-level data in some other class that's still live during this
test's run (class execution order within a shard is deterministic per run but not obviously
tied to this test file).

## Not yet done

- Identify which other test class's `setUpClass` (or similar) leaves a `date.today()` session
  around during this test's execution — bisect by running `./test.sh` with an increasing
  subset of classes, or add a temporary print of the extra session's id/teacher in
  `get_guard_sessions` during a local repro.
- Decide the fix: either scope the test's own query more precisely (assert on the specific
  session id created, not just `len(result) == 1`), or scope `get_guard_sessions` itself if
  the "any session today, globally" domain turns out to be wrong for production too (unlikely
  — its own comment says "Guard teachers need to see all sessions for the day regardless of
  ownership" is deliberate; the test assertion is the more likely thing to fix).

## Next step

Investigate and fix in a dedicated branch/task — not scoped to 386's strike work.
