# Ex officio withdrawal circuit (baixa d'ofici) - requirements

**Status: phase 1 (requirements), in progress - 2026-10-29.** Issue #726. Not implemented yet.
Source of truth: the centre's *Pla de comunicació*, revision 7 (29/10/2026), table "Baixes
d'alumnat", plus the decisions agreed with the developer recorded below. Phases: 1 requirements,
2 fit with EMS, 3 slides for the management team (with screenshots), 4 implementation.

## Scope

| Level | Circuit | In this work |
|---|---|---|
| CFGB | Compulsory | Yes |
| CFGM, CFGS, EFPS (specialisation courses), PFI | Post-compulsory | Yes |
| ESO | Compulsory (same as CFGB) | Designed for, not tested: ESO does not take roll call in EMS yet |
| BTX | Post-compulsory (same as CFGM/CFGS) | Designed for, not tested, same reason |

The circuit a study follows is configured on its level (`ems.level`), so ESO/BTX only need
configuring the day they take roll call in EMS.

Out of scope: a student assigned a place who never enrols (the plan's first row): they are
usually not in EMS. The Pedagogical Coordination role (ESO's responsible) is created when ESO
comes in.

## Definitions

- **Day of absence:** a school day on which the student has roll-call lines and none of them is
  an attendance (every line is an unjustified absence). A day with no sessions for the student
  does not count either way.
- **Justified absences do not count.** A justification (`ems.attendance_justification`) covering
  days of a run removes them from it.
- **Run:** consecutive days of absence, counted from the first one (D0). Any attendance breaks
  it (see "An attendance during the circuit").
- **Deadlines are calendar days from D0**, as the plan says (1 week, 15 days, 1 month, 1.5
  months, 2 months). Pending: confirm with the developer, see open questions.

## Actors

| Actor | EMS role |
|---|---|
| Tutor | The student's group tutor (`tutor_scope_user_ids` chain above them can act too) |
| COCOBE of CCFF | Coexistence (`ems.group_coexistence`) |
| Management team | Director, Head of Studies / Deputy Head of Studies, Secretary, Pedagogical Coordination (no role yet) |
| Secretariat | `ems.group_secretary` |
| Direction | `ems.group_director` |

Where the plan says "COCOBE de CCFF o alguna persona de l'equip directiu", any of them can act.

## Flow

### 1. Detection and proposal

EMS watches the roll calls. When a student's run reaches the first threshold, it creates an
**ex officio withdrawal proposal** (a case file for that student) and notifies the tutor, who
decides:

- **Start the procedure:** the case file advances to the circuit's first step.
- **Dismiss it with a reason.** If the reason is a justifiable one (e.g. a hospital stay), EMS
  opens the justification form already filled with the student and the run's dates, so the
  absences become justified and the run disappears.

### 2. Steps

Every step has a responsible actor. EMS **never advances a step on its own**: it notifies the
responsible when the step is due; the responsible accepts continuing, ticks the off-EMS actions
done (phone call, eNotum, Esfera/SAGA...) and may attach evidence and/or write notes. Each email
a step carries is sent from a template when its responsible accepts continuing (as the
convalidation circuit does). Template contents are still to be agreed.

**Compulsory circuit (CFGB, later ESO):**

| Due | Responsible | Action in EMS | Email sent | Off-EMS (checkbox) |
|---|---|---|---|---|
| Before day 15 | Tutor | Contact with the family recorded | - | Phone call |
| Day 15 | COCOBE / management team (ESO: Pedagogical Coordination) | Contact with the family recorded | - | Phone call (ESO: iEduca) |
| 1 month | Same responsible -> Secretariat | Hands over to the Secretariat | Secretariat -> family | - |
| 1 month | COCOBE / management team (ESO: Pedagogical Coordination) | Notifies Social Services | -> Social Services | - |
| 1.5 months | Secretariat | Warning: withdrawal in 15 days | -> family | eNotum |
| 2 months | Direction | Approves the withdrawal | -> Inspection (procedure followed) | - |
| After approval | Secretariat | Executes the withdrawal (withdrawal wizard, kind *ex officio*) | - | Esfera |

**Post-compulsory circuit (CFGM, CFGS, EFPS, PFI, later BTX):**

| Due | Responsible | Action in EMS | Email sent | Off-EMS (checkbox) |
|---|---|---|---|---|
| 1 week | Tutor | Contact recorded; if the student will not continue, urge a voluntary withdrawal | Confirmation, or "we could not reach you by phone" | Phone call |
| 15 days | Tutor / COCOBE / management team | Notifies the Secretariat (2 weeks of uninterrupted absences) | - | - |
| 15 days | Secretariat | Warning: if they do not come back, ex officio withdrawal; urges a voluntary one | -> family / adult student | - |
| 1 month | Direction | Approves the withdrawal | - | - |
| After approval | Secretariat | Executes the withdrawal (kind *ex officio*) | -> family / adult student: withdrawal done | Esfera, SAGA, eNotum |

Recipients "family / adult student": the student when adult, the family when a minor (same rule
as the rest of EMS's family notifications).

### 3. An attendance during the circuit

Nothing closes on its own. When an attendance is recorded for a student with an open case file,
the tutor is notified and must check with the teachers concerned:

- **The student did come:** the tutor confirms it, the case file is cancelled and the run starts
  again from zero (some students exploit this, but the regulation requires it).
- **It was a mistake:** EMS offers the tutor to correct those lines (attendance -> absence) and
  the circuit carries on. The reverse correction (absences that were really attendances) is
  offered too.

### 4. Justification during the circuit

A justification covering days of an open case file removes them from the run. If what is left no
longer reaches the threshold of the step already reached, the case file is cancelled.

### 5. Voluntary withdrawal during the circuit

The case file is closed and the Secretariat registers the voluntary withdrawal with the usual
withdrawal wizard.

### 6. Ending

Direction approves, then the Secretariat executes (the convalidation pattern). The withdrawal
wizard gets a new kind, **ex officio**, distinct from voluntary, so reports can tell them apart.
The case file keeps the whole history (steps, dates, who, evidence): it is the "Registre" column
of the plan and what Direction sends to Inspection.

## Open questions

- Calendar vs school days (see answer to the developer: recommendation is to keep calendar days).
- First detection threshold of the compulsory circuit: the plan has the tutor contacting the
  family "before" day 15 with no date. Proposal: 1 week, as post-compulsory.
- Reminders when a step is due and its responsible has not acted.
- Who is notified, and how (email + EMS activity?), at each step besides the responsible.
- Adult students who authorised sharing with their family: email the family too?
- Contents of every email template (to be agreed).
- Detection for students starting the course late, or with a run spanning a holiday period.
