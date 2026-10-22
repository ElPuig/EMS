# What's new

## Guard duty board: the group's tutor gets a copy of every notice (tutors told about class movements):
- Every notice the guard duty board sends about a group's day (to the families: later entry,
  earlier leave, longer break or no classes; to the students: lessons that change time because of
  a swap or a moved lesson) now also reaches the group's tutor, as an Odoo message (inbox or email,
  per their own preference) with a copy of the notice's text, so they know how their group's day
  changes. A reinforcement group has no tutor: the tutors of its main groups are told.
- Told when the notice actually goes out (draft notices tell nobody), and told again if a
  scheduled notice is cancelled before it goes out. Corrections are notices too, so the tutor gets
  them as well.
- Hooked on the notice's own state change (`ems.notice.write()` → `_notify_group_tutors()`),
  independent of `ems_skip_arrangement_notify`, which only defers the involved teachers' messages.
  Tests in `TestAbsenceCoverage`; teachers' guard duty manual (en/ca/es) and developer doc updated;
  ca/es translations added.

# Related with
- Closes #658
