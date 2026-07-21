# EMS — Developer Documentation

Technical reference for developers working on the EMS module.

---

## Curriculum

| Model | Description |
|-------|-------------|
| [ems.level](curriculum/level.md) | Study levels (top of the curriculum hierarchy) |

---

## Contacts

| Model | Description |
|-------|-------------|
| [Group schedule (read-only aggregation)](contacts/group_schedule.md) | The group form's "Schedule" tab: aggregating teachers' `resource.calendar.attendance` rows by `group_ids`, deriving the break period from the level's schedule framework, the "Subject → Teacher(s)" co-teaching summary, and the PDF export |

---

## Employees

| Topic | Description |
|-------|-------------|
| [Academic role hierarchy](employees/role_hierarchy.md) | Teacher → Tutor → Department Chief → Head of Studies → Director → Administrator group chain and how roles sync to `res.users.groups_id` |
| [Department Chief / Seminar Chief / Head of Studies / Director cascade](employees/department.md) | `hr.department.manager_id`/`seminar_head_id`/`is_top_level`/`top_level_role` (Head of Studies/Deputy/Secretary) plus `res.company.director_id` driving `hr.employee.parent_id` (between departments and up to the Director) and the `role_dchieff`/`role_seminar`/`role_hos`/`role_dhos`/`role_secretary`/`role_director` roles automatically |
| [Teacher working schedules & schedule frameworks](employees/working_schedule.md) | The "Schedule" tab widget, schedule frameworks, the empty-slot rule, employee lifecycle hooks, the XML import wizard |
| [Google Workspace staff integration & EMS user auto-creation](employees/google_workspace_staff.md) | Corporate Google account creation (Directory API), automatic `res.users` with OAuth pre-link, lifecycle sync (archive ↔ suspend), required-fields chain |
| [Profile picture disable switch](employees/photo_visibility.md) | The `res.users.image_disabled` toggle, keeping `hr.employee`/`res.users` photos in sync, and the `write_photo()` mimetype-safety helper |

---

## Coexistence

| Model | Description |
|-------|-------------|
| [ems.strike](coexistence/strike.md) | Disciplinary notices issued from the roll-call view: recipient/authorization rules, HoS/DHoS-branch escalation matching, access control |

---

## Enrollment

| Model | Description |
|-------|-------------|
| [ems.enrollment_proposal_wizard](enrollment/enrollment_proposal_wizard.md) | Bulk draft enrollments from a student selection, and the secretary-only `allow_other_study` flag that enrolls a current student into a different study |
| [Enrollment benefits](enrollment/enrollment_benefits.md) | Fee bonifications/exemptions: draft-order recompute, freeze after confirmation and the secretary re-apply action that regenerates the invoice |

---

More information about the project on the [GitHub repository](https://github.com/ElPuig/EMS).
