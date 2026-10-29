# Ex officio withdrawal circuit (baixa d'ofici) - requirements

**Status: phase 1 (requirements) closed; phase 2 (fit with EMS) agreed; phase 3 deck drafted (https://claude.ai/artifact/B1dazs3tA6njF2tEwq2YTY, mockups with fictitious data) - 2026-10-29.** Issue #726. Not implemented yet.
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
  it (see "An attendance during the circuit"). It never starts before the student's enrolment
  date; the enrolment itself plays no other part.
- **Deadlines are calendar days from D0**, as the plan says (1 week, 15 days, 1 month, 1.5
  months, 2 months). Known effect, for Direction to decide in the phase 3 slides (keep calendar
  days or switch to school days): a student missing from 15 December reaches "1 month" on 15
  January with about 11 school days missed (assuming the Christmas break runs 23 December - 7
  January), against about 21 in a month without holidays.

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

EMS watches the roll calls. When a student's run reaches **1 week** (both circuits: the tutor
must contact the family a week after the first absence), it creates an
**ex officio withdrawal proposal** (a case file for that student) and notifies the tutor, who
decides:

- **Start the procedure:** the case file advances to the circuit's first step.
- **Dismiss it with a reason.** If the reason is a justifiable one (e.g. a hospital stay), EMS
  opens the justification form already filled with the student and the run's dates, so the
  absences become justified and the run disappears.

**Manual start.** The tutor can also open a case file by hand, giving the date of the first
absence, when they know the student is not coming although the roll calls say otherwise (e.g. a
teacher who always marks everyone present). The attendances recorded in that period are then
listed for the tutor to verify with the teachers concerned, with the same correction tool as in
"An attendance during the circuit".
A manually started case file never moves past the tutor's step until the tutor decides so; the
pending verification stays in the tutor's to-do tray (and so in the daily digest) meanwhile.

### 2. Steps

Every step has a responsible actor. EMS **never advances a step on its own**: it notifies the
responsible when the step is due; the responsible accepts continuing, ticks the off-EMS actions
done (phone call, eNotum, Esfera/SAGA...) and may attach evidence and/or write notes. Each email
a step carries is sent from a template when its responsible accepts continuing (as the
convalidation circuit does). Template contents are still to be agreed.

**Compulsory circuit (CFGB, later ESO):**

| Due | Responsible | Action in EMS | Email sent | Off-EMS (checkbox) |
|---|---|---|---|---|
| 1 week | Tutor | Contact with the family recorded | - | Phone call |
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

### 7. Notifications and reminders

Every notification to staff (proposal to the tutor, a step due, an attendance to verify) is an
EMS activity in the responsible's to-do tray, never an email of its own. A pending one shows up
in the existing daily pending-tasks digest (`docs/en/developers/shared/task_digest.md`), sent
at the start of each person's working day, which is also the reminder when a step is overdue.

Emails to families follow EMS's standard: the student when adult (and the family too when the
student authorised sharing with it), the family when a minor.

## Open questions

- Postponing a pending task so the daily digest stops listing it for a while: to be decided as
  a general mechanism for every task in the digest, not only this circuit.
- Contents of every email template (phase 2).

# Phase 2 - fit with EMS

## What is reused

| Need | EMS piece | Notes |
|---|---|---|
| Absences per day | `ems.attendance_session_line` (`student_id`, `date`, `status_id`, stored `level_id`) | A day of absence = the student has lines that day and every one is `ems.attendance_status_miss`. A severe delay (`delayed_severe`, category absence) means the student did come to the centre: it breaks the run. `justified` never counts. |
| Justifying from a dismissal | `ems.attendance_justification_wizard` | Opened pre-filled (student, first and last day of the run). Creating the justification re-marks the lines as justified, which is what removes the days from the run. Only the student's tutor (or an admin) can justify: the same person who decides on the proposal. |
| Tasks and reminders | `mail.activity` + `ems.base` task pattern of `ems.convalidation` (`_ems_schedule_task`, `_ems_close_tasks`, `mail_activity_quick_update`) + daily digest | One activity type per kind of task (proposal to decide, step due, attendance to verify). No email per task. |
| Who gets the family emails | `res.partner._ems_notification_recipients()` | Adult: the student; minor: the family. Extended for this circuit with the family of an adult who authorised sharing (`auth_share`), as agreed. |
| Who acts | `tutor_scope_user_ids` (tutor and the chain above), `ems.group_coexistence` (COCOBE), `ems.group_director`, `ems.group_head_of_studies`, `ems.group_secretary` | The administrator is always on top (CLAUDE.md rule). |
| Approve, then execute | Convalidation circuit (Director resolves, Secretariat registers) | Same split: Direction approves, the Secretariat runs the withdrawal. |
| The withdrawal itself | `ems.withdrawal_wizard` / `res.partner._ems_register_exit()` | Gets the case file's student and date pre-filled. New exit kind **ex officio** (`exit_type` gains `ex_officio_withdrawal`, or a separate flag; see decisions). Everything else (history frozen, portal revoked, archive) unchanged. |
| Circuit per level | `ems.level` | New selection `withdrawal_circuit`: `compulsory` / `post_compulsory` / empty. Seeded in `data/cat/ems.level.csv`: CFGB and ESO compulsory, CFGM, CFGS, EFPS, PFI and BTX post-compulsory. ESO and BTX produce nothing until they take roll call in EMS. |
| Email templates | `mails/` folder pattern (one record per language) | Catalan wording first; Spanish and English for the multilingual pattern. |

## What is new

- **`ems.ex_officio_withdrawal`** (the case file): student, study and level (circuit), tutor, first day
  of absence (D0), origin (`detected` / `manual`), state, current step, history in the chatter,
  attachments. States: `proposal` (waiting for the tutor), `in_progress`, `direction` (waiting for
  approval), `secretariat` (approved, waiting for execution), `done`, `cancelled` (with the reason:
  student came back, justified, voluntary withdrawal, dismissed by the tutor).
- **`ems.ex_officio_withdrawal.step`** (one line per step of the case file): what the plan's row
  asks, due date (D0 + offset), responsible, checklist of off-EMS actions, notes, evidence files,
  done by / on, email sent.
- **Steps catalog**: what each circuit's steps are, in code.
- **Daily detection cron**: one grouped read of the roll-call lines of the last ~2 months for the
  levels with a circuit (one query, indexed by student and date, per the efficiency rule), the
  current run per student, and a proposal for each student whose run reached 1 week without an
  open case file. Runs at night, after the day's roll calls.
- **Attendance hook**: when a line of a student with an open case file becomes an attendance, an
  activity for the tutor ("verify this attendance"), with the correction offer. Hooked where
  `ems.attendance_session_line` already reacts to status changes (`_update_notification`).
- **Correction wizard for the tutor**: lists the lines of the period, lets them flip attendance <->
  absence after talking to the teachers. Writes under `sudo()` after checking the user acts as the
  student's tutor (`ems.base.user_acts_as_tutor`), since the lines belong to other teachers'
  sessions. Every change is logged in the case file and in the line's chatter.
- **Menu**: *Academic management > Ex officio withdrawals* (next to convalidations), plus a smart
  button on the student's form. Tutors reach their own case files through the activity and the
  student form.

## Decisions (phase 2, agreed 2026-10-29)

1. **Steps catalog in code**, not data: no configuration until the circuit works well.
2. **Exit kind**: `exit_type` stays `withdrawal`; a new flag says *voluntary* or *ex officio*, so
   every existing withdrawal filter keeps working.
3. **The Inspection email** carries a PDF of the case file (steps, dates, who).
4. **Who sees the case files**: the tutor (own students, tutor scope), Coexistence (COCOBE),
   Guidance (same as Coexistence), the management team and the Secretariat: all of them; other
   teachers: none.
5. **Social Services and Inspection addresses**: settings fields (`res.config.settings`).
6. **Email texts**: reviewed later; the drafts below are placeholders.

## Email drafts (Catalan, to agree)

Placeholders in brackets. Not yet checked with LanguageTool (no key in this environment).

- **Tutor, 1 week (post-compulsory), after a phone call:** *Assumpte: Faltes d'assistència de [alumne].*
  Benvolguda família / Benvolgut [alumne]: tal com hem parlat per telèfon, us confirmem que [alumne]
  no assisteix a classe des del [D0]. Si no té intenció de continuar els estudis, us demanem que
  feu la baixa voluntària a la secretaria del centre.
- **Same, unreachable:** ... us escrivim perquè no us hem pogut localitzar per telèfon. [alumne] no
  assisteix a classe des del [D0]. Poseu-vos en contacte amb el tutor o la tutora tan aviat com
  pugueu.
- **Secretariat, 15 days (post-compulsory):** [alumne] no assisteix al centre des del [D0]. Si no
  s'hi torna a incorporar, el centre en tramitarà la baixa d'ofici. Si no voleu continuar els
  estudis, us demanem que en feu la baixa voluntària a la secretaria.
- **Secretariat, 1 month (compulsory):** [alumne] no assisteix al centre des del [D0]. Us
  recordem que l'escolarització és obligatòria i us demanem que us poseu en contacte amb el centre.
- **Secretariat, 1.5 months (compulsory, besides eNotum):** si [alumne] no s'incorpora al centre,
  d'aquí a quinze dies se'n tramitarà la baixa d'ofici.
- **Social Services, 1 month (compulsory):** comunicació de la no assistència de [alumne], [grup],
  des del [D0], i de les actuacions fetes pel centre.
- **Inspection, 2 months (compulsory):** comunicació del procediment seguit amb [alumne] i que es
  procedeix a la baixa d'ofici, amb el PDF de l'expedient adjunt.
- **Secretariat, withdrawal done:** us comuniquem que s'ha tramitat la baixa d'ofici de [alumne] amb
  data [data].

