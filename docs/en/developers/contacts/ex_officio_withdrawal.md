# Ex officio withdrawal (baixa d'ofici)

Issue #726. A student who stops coming to the centre loses their place after a term set by the
regulation (Resolució EDF/293/2026, point 8.6) and the centre's communication plan (*Pla de
comunicació*, table "Baixes d'alumnat"). EMS keeps one **case file** per student that walks every
step of that protocol, with who did it and when.

Implemented in phases (see the issue). This page describes what exists now.

## Circuits

The circuit a student follows comes from their level: `ems.level.withdrawal_circuit`
(`compulsory` / `post_compulsory` / empty), seeded in `data/cat/ems.level.csv`.

| Level | Circuit |
|---|---|
| CFGB, ESO | Compulsory |
| CFGM, CFGS, EFPS, PFI, BTX | Post-compulsory |

A level without a circuit gets no case files.

## Steps and deadlines

The steps are a catalog in code (`STEP_CATALOG`, `models/contacts/ex_officio_withdrawal.py`), one
tuple per circuit, created when the procedure starts. Every deadline counts from the first day of
absence (D0) and is computed in one place, `ems.ex_officio_withdrawal._ems_due_date()`:

- **School days** (post-compulsory, as Direction decided: never less margin than the regulation's
  15 days): the N-th school day of absence, D0 included. A school day is Monday to Friday and not
  covered by a public holiday or school break (`resource.calendar.leaves` with no resource, read in
  one search by `resource.calendar.leaves._ems_holiday_dates()`).
- **Calendar days and months** (compulsory): D0 plus the offset (`relativedelta`).

Example: D0 = Tuesday 15 December 2026 with the Christmas break from 21 December to 7 January: the
15th school day is 22 January 2027.

**Post-compulsory**

| Step | Responsible | Deadline | Off-EMS checks |
|---|---|---|---|
| Contact with the family | Tutor | 5 school days | Phone call |
| Ex officio withdrawal warning | Secretariat | 10 school days | eNotum |
| Green light from Direction | Direction | 15 school days | - |
| Withdrawal | Secretariat | 15 school days | Esfera, SAGA, eNotum |

**Compulsory**

| Step | Responsible | Deadline | Off-EMS checks |
|---|---|---|---|
| Contact with the family | Tutor | 7 days | Phone call |
| Contact by Coexistence | COCOBE / management team | 15 days | Phone call |
| Notice to the family | Secretariat | 1 month | - |
| Notice to Social Services | COCOBE / management team | 1 month | External email sent |
| Ex officio withdrawal warning | Secretariat | 1.5 months | eNotum |
| Direction approval | Direction | 2 months | External email sent (Inspection) |
| Withdrawal | Secretariat | 2 months | Esfera |

## Case file

```mermaid
stateDiagram-v2
    [*] --> proposal: tutor opens it (manual)
    proposal --> in_progress: Start the procedure (steps created)
    proposal --> cancelled: Dismiss (reason)
    in_progress --> direction
    direction --> secretariat
    secretariat --> done
    in_progress --> cancelled
```

Only `proposal` → `in_progress` and `proposal` → `cancelled` exist so far; the rest come with the
next phases.

- `ems.ex_officio_withdrawal`: registration number `BO-<course start>-<end>-NNNN` (one
  `ir.sequence` per course, `ems.base.next_course_number()`, shared with convalidations), student,
  group, level and circuit (taken from the student's main group when created), tutor (the
  student's current one), first day of absence, origin (`manual` / `detected`), state, cancel
  reason and note. One open case file per student (`_check_one_open_per_student`).
- `ems.ex_officio_withdrawal.step`: step code, responsible, due date, off-EMS checks (only the
  ones the step asks for are shown: `needs_*`), notes, done by / on.
- The state and the student never change by plain write: only through the buttons, which write
  with `sudo()` after checking who acts.

## Access

| Role | Sees | Does |
|---|---|---|
| Tutor (and the chain above them: `tutor_scope_user_ids`) | Their students' case files | Opens one, starts or dismisses it |
| Coexistence (COCOBE), Guidance | All | Read (Coexistence will act on its steps) |
| Head of Studies / Deputy, Director | All | Open, start, dismiss |
| Secretariat | All | Read (will act on its steps) |
| Academic administrator | All | Everything, deletion included |
| Other teachers | None | - |

Record rules: `security/rules/ex_officio_withdrawal.xml` (tutor scope for `ems.group_tutor`,
everything for `ems.group_student_data_reader`, `ems.group_secretary` and
`ems.group_academic_admin`). Who may start or dismiss a proposal: `can_decide_proposal`
(non-stored, `depends_context('uid')`), checked again on the server.

## Screens

- *Academic management > Ex officio withdrawals*: list (open ones by default), form with the
  Actions dropdown and the steps.
- Student form: smart button with the student's case files.
- Level form: the circuit.
