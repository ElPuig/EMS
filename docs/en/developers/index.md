# EMS — Developer Documentation

Technical reference for developers working on the EMS module.

---

## Curriculum

| Model | Description |
|-------|-------------|
| [ems.level](curriculum/level.md) | Study levels (top of the curriculum hierarchy) |

---

## Employees

| Topic | Description |
|-------|-------------|
| [Academic role hierarchy](employees/role_hierarchy.md) | Teacher → Tutor → Department Chief → Head of Studies → Director → Administrator group chain and how roles sync to `res.users.groups_id` |
| [Teacher working schedules & schedule frameworks](employees/working_schedule.md) | The "Schedule" tab widget, schedule frameworks, the empty-slot rule, employee lifecycle hooks, the XML import wizard |

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

---

More information about the project on the [GitHub repository](https://github.com/ElPuig/EMS).
