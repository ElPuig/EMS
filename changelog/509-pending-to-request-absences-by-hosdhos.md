# What's new

## Expected absences (Head of Studies / Deputy, issue #509):

- New screen, Absences > Management > Expected absences (`ems.absence_pending`), where the Head of Studies or their Deputy enters an absence they already know about (teacher + date/time range) before the teacher has requested it themselves.
- While expected, it shows on the guard duty schedule exactly like a requested absence still awaiting approval, so guard duty can be planned around it straight away (`ems.course._get_guard_duty_absence_intervals`, clipped to each day in the company's timezone).
- When the teacher files their own absence, every overlapping expected absence for that teacher is linked to it automatically (on create, and when the absence's dates, hours, employee or state change). The link is final: from then on only the real absence counts, with its own range and state; refusing, cancelling, moving or deleting it never brings the expected absence back, and a linked one can no longer be edited.
- Access follows the real hierarchy, not the role: only `ems.group_head_of_studies` has access (the Director implies it), narrowed by `rule_absence_pending_hierarchy` to teachers below the user through `parent_id` (`child_of user.employee_ids`). A Head of Studies or Deputy reaches only their own teachers; the Director reaches everyone; Department Chiefs, tutors and teachers have no access at all. Technical administrators (`base.group_system`, e.g. `admin`), who usually are not in the org chart, reach every teacher through a rule of their own.
- Odoo's own "Time Off" entry under Management is replaced by an EMS entry on the same action, "Requested absences", so the two kinds (expected vs requested) can be told apart in the menu.
- Tests (`TestAbsencePending`, `TestAbsencePendingTour` logged in as a Head of Studies), developer docs (`absence.md`, `guard_duty_board.md`), Head of Studies manual section and a note in the teachers' guard duty manual (en/ca/es), ca_ES/es_ES translations.

## Co-taught classes struck through on the guard duty absences table:

- When a class is co-taught (two teachers, same group, period and room) and only one of them is away, their line on the absences table (screen and PDF) stays listed but struck through, with a tooltip: someone is missing, but the other teacher is taking the class, so no guard is needed.
- A group split across two rooms, or a class where both teachers are away, is not marked: it still needs covering.

# Changes

## "Filed through ATRI" checkbox no longer shown on absence requests:

- The checkbox was visible to approvers but had no effect beyond the ATRI portal notice on the form, which it still drives invisibly. It always follows the absence type; a wrongly chosen type is corrected by changing the type itself, which recomputes it.
