# What's new

## Identity document and social security number in the employee's Private Information tab:
- A new "Identification" group in the teacher/ASP form's "Private Information" tab shows the
  identity document (DNI/NIE) and the social security number, which EMS used to hide from
  everyone.
- HR officers (Head of Studies/Deputy and above, TAC, the secretariat) edit them. The Head of
  Studies keeps writing teachers only (issue #391); the secretariat writes every staff member.
- A Department Chief (and Seminar Chief) now gets that tab, read-only and with only this group,
  on the employees of their own chain of command (hr.employee.tutor_scope_user_ids: the
  employee, every chief above them through parent_id, and the Director). Another department's
  chief, or a colleague, gets no tab. Served through read-only computed copies
  (scoped_identification_id, scoped_ssnid, can_view_identity), since the native fields'
  hr.group_hr_user gate is per field, not per record.
- Tests: tests/test_employee_identity_visibility.py plus Department Chief and secretariat tours.

# Changes

## Schedule is the first tab on the teacher and group forms:
- The "Schedule" tab is now the first one (and so the one open by default) on the teacher/ASP
  form and on the group form, the same as the My Profile screen already did. For an ASP
  employee, where the tab is hidden, the next tab opens instead.
- The employee and group tours assert it is the first, active tab on load.

## The secretariat gets Odoo's HR officer group:
- ems.group_secretary now implies hr.group_hr_user, like the Head of Studies and TAC already
  did (issue #391), so it reads and edits the staff's private information. A new record rule
  (rule_hr_employee_write_secretary) lets it write/create every staff member, ASP and teachers
  alike; it is added to rule_hr_employee_no_unlink_staff_manager, so it never deletes.
- Existing secretariat users get the group automatically on upgrade (implied_ids propagation),
  no migration needed.
