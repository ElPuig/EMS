# EMS — Developer Documentation

Technical reference for developers working on the EMS module.

---

## Curriculum

| Model | Description |
|-------|-------------|
| [ems.level](curriculum/level.md) | Study levels (top of the curriculum hierarchy) |
| [ems.study](curriculum/study.md) | Study programmes under a level: subjects, curriculum documents, the `uses_enrollment_flow` derived flag |
| [ems.subject](curriculum/subject.md) | Subjects: the most widely referenced curriculum node, and the automatic `product.product` sync on create/write |
| [ems.outcome](curriculum/outcome.md) | Learning outcomes nested in a subject's form — no menu of its own; the `subject_id` dangling-compute bug fix |
| [ems.criteria](curriculum/criteria.md) | Evaluation criteria nested two levels deep (subject → outcome popup → criteria popup); the identical dangling-compute bug fix on `outcome_id` |
| [ems.content](curriculum/content.md) | Content items with a real self-referencing "Composite" hierarchy; fixes a view-context bug where adding a nested child silently created a sibling instead |

---

## Settings

| Model | Description |
|-------|-------------|
| [ems.course](settings/course.md) | Academic year windows; known limitation — no course-management UI exists yet (only the "Current course" selector), see the doc for the unbuilt "Setup next course" TODO |
| [res.company (EMS extension)](settings/company.md) | Every centre-wide config field EMS adds, grouped by area with cross-links to their owning feature docs; the Fernet-encrypted credential pattern (`limesurvey_pwd`, `google_ws_sa_json`) and a real `NameError` bug fixed in its inverse method |
| [res.config.settings (EMS extension)](settings/settings.md) | The related-field proxy that makes every `res.company` field above editable from Settings; `set_values()`'s EMS auto-checkout cron activation |

---

## Facilities

| Model | Description |
|-------|-------------|
| [ems.space_type](facilities/space_type.md) | Kinds of physical space (classroom, lab...); removed a stale TODO comment about a config page that already existed |
| [ems.space](facilities/space.md) | Physical spaces, widely referenced by scheduling/attendance/documentation models |

---

## Contacts

| Model | Description |
|-------|-------------|
| [ems.group](contacts/group.md) | The core class-group model — one of the most widely-referenced in EMS; `group_type` switching, the tutor-role sync bug fix, the side-effecting `enrollment_view_ids` compute |
| [Group schedule (read-only aggregation)](contacts/group_schedule.md) | The group form's "Schedule" tab: aggregating teachers' `resource.calendar.attendance` rows by `group_ids`, deriving the break period from the level's schedule framework, the "Subject → Teacher(s)" co-teaching summary, and the PDF export |

---

## Employees

| Topic | Description |
|-------|-------------|
| [hr.employee (EMS extension)](employees/employee.md) | Map of the whole model — cross-links every already-documented area (roles, schedule, photo, Google Workspace) plus a real `compute_sudo` bug fix on `read_only`, new `get_report_role_lines()` branch coverage, and a flagged `ems.group.create()` gap |
| [Academic role hierarchy](employees/role_hierarchy.md) | Teacher → Tutor → Department Chief → Head of Studies → Director → Administrator group chain and how roles sync to `res.users.groups_id` |
| [Department Chief / Seminar Chief / Head of Studies / Director cascade](employees/department.md) | `hr.department.manager_id`/`seminar_chief_id`/`is_top_level`/`top_level_role` (Head of Studies/Deputy/Secretary) plus `res.company.director_id` driving `hr.employee.parent_id` (between departments and up to the Director) and the `role_dchieff`/`role_seminar`/`role_hos`/`role_dhos`/`role_secretary`/`role_director` roles automatically |
| [hr.job (EMS extension)](employees/job.md) | Two fields only (`employee_type`, `group_id`) — the security-group auto-grant is consumed and already tested from `hr.employee`'s side |
| [ems.workgroup](employees/workgroup.md) | Simple free-form employee grouping (project teams, committees) — no business logic |
| [ems.teaching](employees/teaching.md) | Ternary teacher/group/subject relation, derived from and kept in sync with the schedule via `sync_from_schedule()` |
| [ems.non_teaching_type](employees/non_teaching_type.md) | Catalogue of non-subject schedule period types (breaks, guard duties); note the admin group is `group_department_chief`, not the usual `group_academic_admin` |
| [hr.attendance auto-checkout (EMS extension)](employees/attendance_autocheckout.md) | Closing stale open attendances on check-in, and the EMS nightly cron mode using the employee's real schedule instead of fixed hours |
| [res.users (EMS extension)](employees/user.md) | `_sync_ems_implied_groups()` — compensates for Odoo's own implied-group grants being permanent/never auto-revoked |
| [ems.tracking](employees/tracking.md) | Free-form student follow-up notes; flags a possible access-scope mismatch (teachers described as able to "add" notes but only granted read access) |
| [Teacher working schedules & schedule frameworks](employees/working_schedule.md) | The "Schedule" tab widget, schedule frameworks, the empty-slot rule, employee lifecycle hooks, the XML import wizard |
| [Google Workspace staff integration & EMS user auto-creation](employees/google_workspace_staff.md) | Corporate Google account creation (Directory API), automatic `res.users` with OAuth pre-link, lifecycle sync (archive ↔ suspend), required-fields chain |
| [Profile picture disable switch](employees/photo_visibility.md) | The `res.users.image_disabled` toggle, keeping `hr.employee`/`res.users` photos in sync, and the `write_photo()` mimetype-safety helper |

---

## Attendance

| Model | Description |
|-------|-------------|
| [ems.attendance_template](attendance/attendance_template.md) | Who teaches what, where and for whom: schedule sync/reconciliation from the "Schedule" tab and the XML importer, co-teaching, external-conflict detection |
| [ems.attendance_status](attendance/attendance_status.md) | Archivable model replacing the old hardcoded status enum; `status_id` field rename across the session line, justification, issue-notification and reporting code; the "Issue" status retirement now that `ems.strike` covers it |

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

## Shared

| Topic | Description |
|-------|-------------|
| [Free-pick color widget](shared/color_widget.md) | `widget="color"` + the `ems_color_swatch` styling, the `role_color_tags` badge widget, and `ems.hex_color_mixin` — used by `ems.role`, `ems.attendance_template`, and `hr.department`'s `custom_color` |
| [Task assignment](shared/task_assignment.md) | `mail.activity.type`'s `ems_task_assignment`/`ems_assignee_ids` — an explicit, config-driven recipient list decoupled from security groups |
| [`ems.base`](shared/base.md) | Chatter/notification helpers (`notify`, `chatter`, `chatter_exception`), permission checks (`get_user_is_admin`/`_tutor`), `persistent_hash` — the foundational mixin inherited by most business models |
| [`ems.datetime_utils`](shared/datetime_utils.md) | Timezone-aware ↔ naive-UTC ↔ float-hour conversions shared by every attendance/schedule model |
| [`ems.multithreading`](shared/multithreading.md) | The `run_in_thread()` setup/compute/store/callback engine behind the LimeSurvey integration's long-running actions |
| [`ems.schedule_report_mixin`](shared/schedule_report_mixin.md) | Color-per-item and time-label helpers shared by the weekly-schedule PDF reports |
| [`google.workspace.mixin`](shared/google_workspace_mixin.md) | The Directory API client, password policy, and text/phone normalization shared by the staff and student Google Workspace integrations |
| [Shared test utilities](shared/testing.md) | `tests/common.py`: `create_level_study(_group)`, `mock_outgoing_email`, `make_synchronous_run_in_thread` — fixture/mock boilerplate extracted after it was found duplicated across dozens of test files |

---

## Tooling

| Topic | Description |
|-------|-------------|
| [AI agent test notifications when running inside a container](tooling/ai_agent_test_notifications.md) | Why push/desktop notifications from an AI coding agent don't reach you inside an LXC/Incus/Docker container reached via an editor extension, and how to bridge them with a host-side file-drop watcher + a Claude Code hook |

---

More information about the project on the [GitHub repository](https://github.com/ElPuig/EMS).
