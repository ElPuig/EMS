# Manual test of #879, #880 and #881 (FP evaluation, issue general #882)

**Status (2026-11-28): current.** Written at the end of the autopilot session that built #879, #880 and #881.
None of them has been tested by hand yet. Delete this file once the three issues are validated.

**Where:** branch `881-evaluation-board-decisions`, which contains 878 → 879 → 880 → 881 (each branch
starts from the previous one). Dev database `ems` (`ems.environment_type = dev`: every email goes to the
developer's redirect inbox).

**How to use it:** Juan runs the steps in the browser; the Claude session prepares the data, checks the
database when needed, fixes what fails (on the branch of the issue the bug belongs to, then carried up to the
next branches) and ticks the boxes here. A failed step is written under it as **FAIL:** with what happened.

## People and data

No names, logins or passwords here (this file is public): the Claude session looks them up in the dev
database at the start and tells Juan who to log in as.

| Role in the script | How to find them |
|---|---|
| **HoS** (Head of Studies) | the Head of Studies Juan usually tests with ("Fer") |
| **Tutor** | `ems.group` DAM2A's `tutor_id` (also teacher of 0486) |
| **Teacher A** | teacher of DAM2A's 0488 session |
| **Teacher B** | teacher of DAM2A's 0490 session (a teacher with no say on Teacher A's claims) |
| **Student** | the adult DAM2A student used in the #878 test (files claims himself in the portal) |

DAM2A, 1st evaluation: 7 sessions (0486, 0488, 0489, 0490, 0492, 1710, OPT3), state **Publicada**, 1 to 3
RAs graded per module, some provisional, invented comments. Its claims period is in the future
(14-18 Dec 2026), so step A1 moves it.

## Preparation (the Claude session, before Juan starts)

- [ ] `git status` clean on `881-evaluation-board-decisions`; `./upgrade.sh` clean.
- [ ] `ems.environment_type` is `dev`.
- [ ] No grade claims and no `JA` minutes yet (`ems_grade_claim`, `ems_minute` of type JA): a clean start.

## A. Grade claims (#879)

- [ ] **A1 Claims period.** HoS: **Planificació i qualificació → Qualificacions → Avaluació per grup i
  matèria**, filter DAM2A 1a, and set the claim dates from yesterday to 3 days from today (columns editable
  in the list). *Expected:* saved; a teacher cannot edit them.
- [ ] **A2 Portal.** Student: portal → **Qualificacions**. *Expected:* the grades table; the claims section
  explains that a claim is for a grade that does not match the calculation the teacher shared; only graded RAs
  of published sessions are offered (no final grade until every RA is graded).
- [ ] **A3 File a claim.** Student claims one 0488 RA with a reason. *Expected:* listed as pending; filing the
  same RA again is refused; Teacher A gets a task "answer the claim" (daily summary, no loose email).
- [ ] **A4 Deny (1st instance).** Teacher A: **Qualificacions → Reclamacions de notes**, open it,
  **Denegar**, reason *La nota coincideix amb el càlcul compartit*. Try **Altres** first with no text.
  *Expected:* "Altres" asks for the details; once denied, Student gets an email (redirect inbox) with the reason;
  the task is done.
- [ ] **A5 Second instance.** Student: portal shows the denial and its reason, and offers to take it to the
  tutor until the later of the end of the period and 2 school days after the denial. He does it with a text.
  *Expected:* state "tutor"; Tutor gets the task.
- [ ] **A6 Accept (2nd instance).** Tutor accepts with a new grade. *Expected:* the RA grade
  changes in the session and in the portal; Student gets the email; another teacher (Teacher B) cannot answer it.
- [ ] **A7 Head of Studies.** Student files a claim on a 0490 RA; HoS answers it from **Reclamacions de
  notes** (first instance). *Expected:* HoS can; Teacher B sees only claims of his own sessions.
- [ ] **A8 Finalising blocked.** With a claim pending, HoS tries **Accions → Canviar l'estat** to
  *Finalitzada* on that session. *Expected:* refused while the claim is pending; allowed once answered (then
  go back to Publicada).
- [ ] **A9 Denial reasons catalog.** HoS: **Gestió d'avaluacions → Motius de denegació de reclamacions**:
  reorder, add one, tick **Demana detalls**, archive it. *Expected:* the deny dialog follows the catalog.

## B. Evaluation board minute (#880)

- [ ] **B1 Minute created.** HoS moves the 7 DAM2A 1a sessions **Publicada → Junta d'avaluació**
  (**Gestió d'avaluacions → Canviar l'estat de la sessió d'avaluació**). *Expected:* one minute
  "Acta de junta d'avaluació" for DAM2A, 1a avaluació, written by Tutor, who gets a quiet task.
  Moving back and forth does not create a second one.
- [ ] **B2 Contents.** Tutor: **Reunions → Actes i registres**, open it. *Expected:* attendance =
  teaching team; the 4 difficulty areas; statistics (term from 1 Sept, withdrawals, absences >25%,
  unjustified >5%); one row per tutored student with RA aprovats / avaluats; no "Decisió de la junta" column
  in the 1st evaluation.
- [ ] **B3 Fill in.** Difficulties, **Treballa** on two students (the counter follows), teaching team
  comments, a family comment for Student. Change a grade in a session and press **Actualitza els RA a partir de
  les notes**. *Expected:* counts update; PDF of the minute prints difficulties, statistics and the teaching
  team comments, never the family comment.
- [ ] **B4 Send for approval.** *Expected:* the writing task is done; the usual approval flow.
- [ ] **B5 Family comment in the portal.** HoS moves the sessions back to **Publicada**. Student: portal →
  Qualificacions and its PDF. *Expected:* the tutor's comment under the 1st evaluation table; nothing else
  of the minute. While in Junta, the portal showed no grades of that round.
- [ ] **B6 Privacy.** A teacher outside DAM2A's team cannot open the minute nor its student lines.

## C. Board decisions (#881)

- [ ] **C1 Extraordinary sessions.** HoS: **Crea sessions d'avaluació**, DAM2A, round *Avaluació
  extraordinària*, claim dates. *Expected:* 7 sessions, grades carried over from the 1st evaluation.
  Then move them to **Junta d'avaluació**. *Expected:* a second minute, extraordinary evaluation.
- [ ] **C2 Options.** Tutor opens it. *Expected:* column "Decisió de la junta" with only
  **Titula / Repeteix / Abandona** (DAM2A is the study's last course; a 1st-year group would show
  Promociona instead of Titula).
- [ ] **C3 Repeteix.** Student → **Repeteix**. *Expected:* **Matrícula recomanada** fills with the modules
  he has failed (an RA below 5 or ungraded; the work placement never fails a module); editable; changing the
  decision away empties it, coming back refills it.
- [ ] **C4 Abandona.** Another student → **Abandona**. *Expected:* a **Baixa prevista** button on the row
  (only for the tutor and the chain above, the secretary, admin); it opens the usual wizard (cancel it, or
  confirm and undo it afterwards from the student's form). Nothing is marked on its own.
- [ ] **C5 Titula** on a third student. Save; print the minute's PDF. *Expected:* decision + recommended
  modules' acronyms in the students' table. Nothing of it in the portal.
- [ ] **C6 Enrollment proposal.** Admin: **Configuració → Gestió EMS → Ajustos de gestió de cursos**: set
  **Curs de matriculació** to 2027-2028 and a **Període de preinscripció** that includes today (note the
  current values to restore them). Tutor: **Gestió acadèmica → Matrícula → Propostes de
  matrícula**, select Student → the list button **Propostes de matrícula**. *Expected:* "Junta d'avaluació:
  Repeteix (1)"; the 2nd-year DAM template preselected; the created enrollment holds only the recommended
  modules plus the tutorship and the fee lines.
- [ ] **C7 Transition warning.** Change Student's decision to **Titula**. Admin: **Configuració → Gestió EMS →
  Preparar el curs següent**, outgoing 2026-2027, incoming 2027-2028, study DAM, **preview only** (never
  apply). *Expected:* the warning "... enrollment ... does not match the extraordinary evaluation board's
  decision ..." naming Student. With **Repeteix** back, the warning goes away.
- [ ] **C8 Academic record (optional).** The decision is copied when the record is generated (transition
  apply or an exit). Register a withdrawal of the "Abandona" student, check **Històric acadèmic →
  Decisió de la junta**, then **Desfés la baixa**.

## Cleanup

- [ ] Restore **Curs de matriculació** and the **Període de preinscripció**; cancel/delete the test
  enrollment of C6.
- [ ] Leave the extraordinary sessions or delete them, as Juan prefers.
- [ ] Report each FAIL fixed (issue, commit) and push the affected branches.
