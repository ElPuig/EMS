# What's new

## Ex officio withdrawal case files (phase 1: opened by hand):
- Implements the centre's protocol for students who stop coming (Pla de comunicació, table "Baixes d'alumnat", and Resolució EDF/293/2026, point 8.6), as validated by Direction on 2026-11-03. Each level declares its circuit (`ems.level.withdrawal_circuit`, seeded in `data/cat/ems.level.csv`): compulsory (CFGB, ESO) or post-compulsory (CFGM, CFGS, EFPS, PFI, BTX).
- New `ems.ex_officio_withdrawal` case file (number `BO-<course>-NNNN`, student, group, level, circuit, first day of absence, origin, state, cancel reason) and `ems.ex_officio_withdrawal.step` (step, responsible, due date, off-EMS checks, notes, done by/on). One open case file per student.
- The tutor (and the chain above them) opens a case file by hand, then starts the procedure (the circuit's steps are created with their deadlines) or dismisses it with a reason. Post-compulsory deadlines are school days (5, 10, 15; weekends, holidays and school breaks skipped, read from the public holidays calendar), compulsory ones calendar days and months (7 and 15 days, 1, 1.5 and 2 months).
- Access: the tutor scope sees its own students' case files; Coexistence, Guidance, Head of Studies, Director and the Secretariat see every one; other teachers none. New menu Academic management > Ex officio withdrawals, a smart button on the student form and the circuit on the level form.

# Internal changes

## Per-course registry numbers shared:
- `ems.base.next_course_number()` now builds the per-course registry numbers (one `ir.sequence` per kind and course) used by convalidations (CONV) and ex officio withdrawals (BO), instead of convalidations keeping their own copy.
- `resource.calendar.leaves._ems_holiday_dates()` returns, in one search, the company's days covered by a public holiday or school break in a date range.
