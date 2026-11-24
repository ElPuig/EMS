# What's new

## Teacher substitutions (substitute declared on the teacher's form):

- A teacher's form has a new "Substitute of" field (Teaching tab, under Substitution), set by whoever can edit teachers (Head of Studies, Deputy, Director, TAC, Secretariat, administrator). Setting it on the substitute replaces their schedule with a copy of the replaced teacher's (classes and guard duties), through the same path the Schedule tab saves by; a warning says so before saving. Clearing it when the replaced teacher comes back empties the substitute's schedule again (the roll-calls they took keep their history). A substitute can be replaced in turn (the chain is followed) and a teacher can have several substitutes.
- Both forms show a ribbon: "Substitute" (orange) on the substitute, "Substituted" (grey) on the replaced teacher, who also lists who replaces them. Optional "Substitute of" column in the Teachers list.
- Guard duty board: a substituted teacher no longer appears at all (no absence row, no "co-teaching, no cover needed" line, and their WC/break guards no longer ask for cover, since the substitute's copy holds them). They are not turned into detected absences either.
- The substitute acts as the replaced teacher: everything they see as a teacher (roll-call templates, schedule lines, sessions and lines, justifications, grade sessions and lines, attendance reports, "my groups") and as a tutor (every tutor-scope rule: students, attendance issues, documents...). The tutor's notices and tasks (daily attendance issues, expected withdrawals, Erasmus+ stays, contact data reviews, student walkout emails) go to the substitute. The replaced teacher's own absences, check-in corrections, strike declarations and roles (a Department Chief's substitute does not become Department Chief) stay theirs.
- Manuals: Head of Studies "Register a Substitution" (ca/es/en), the working schedules manual no longer suggests copying a schedule by hand for substitutions, and the guard duty manual explains why a substituted teacher is absent from it.

# Internal changes

## Substitution plumbing (hr.employee):

- New fields on hr.employee: substitute_of_id (tracked, indexed, no-cycle constraint), substituted_by_ids, substitution_label/substitution_color (ribbon) and, on hr.employee.base, the non-stored searchable acting_user_ids (own user plus the substitutes' users). tutor_scope_user_ids now includes the substitutes' users too (compute and _search, never the replaced teacher's chief rung or directorship). _ems_acting_teacher() resolves who acts as a teacher now.
- resource.calendar._ems_schedule_cells() turns a calendar's Mon-Fri blocks into apply_schedule_changes() cells.
- Record rules: the teacher "own" rules of attendance templates/schedules/sessions/lines/justifications and grade sessions/lines match on acting_user_ids instead of user_id.
- Performance, measured on this dev DB (129 employees, 4,790 sessions, odoo shell, cold/warm): the board's extra lookup of substituted teachers 5.6/0.6 ms; acting_user_ids search 3.1/0.3 ms; a tutor's visible sessions count 10.9/2.3 ms, grade sessions 7.4/1.4 ms.
- Tests: tests/test_employee_substitution.py (schedule copy and emptying, cycles, board, acting users through the chain, access granted and revoked, private absences, no chief rung) and the tour employee_substitution_tour.js as the Head of Studies.
