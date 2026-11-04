# Erasmus+ quality (indicators, satisfaction survey, Mobilitat FP evidence)

Status: phase 1 implemented on 2026-11-04 (branch 682-erasmus, see docs/en/developers/erasmus/quality.md);
phase 2 not started. Delete this file once phase 2 lands.

## Decisions (adriamt, 2026-11-04)

- Menu **Erasmus+ › Qualitat**, for the Erasmus+ team.
- Satisfaction scale **1-10**, one question, Catalan wording: "En general, quin és el teu grau de
  satisfacció amb la teva experiència de mobilitat Erasmus+?" (English source string, ca/es in .po).
  Target > 8.5. Global: students and staff (job shadowing, group mobilities and companions included).
- Interest, two indicators, numerator = **people who applied to the call** (submitted, not draft):
  - students: applicants / target students (GM + GS + specialisation course DEV), target > 5 %;
  - staff: applicant teachers / target teachers (teachers of the FP cycles).
  Denominator = the call's own `_ems_eligible_partners()` population, frozen on the call when the
  definitive list is published (so history never changes).
- **No minimum group size** (the "n < 3" rule is dropped): every breakdown shows whatever there is.
- Improvement actions are `ems.quality.action` (type `improvement`) of the Quality app, created from
  a low-score answer, so the ISO evidence lives where the quality coordinator already looks.
- No "reversible migrations": everything is new, nothing existing is changed or removed.

## Phase 1: survey, indicators, panel

- Survey on the portal, in the return step next to the EU Survey (which stays: SEPIE needs it).
  Opens at the mobility's end date; reminders at +3 and +7 days (students by email; staff as an
  activity in their daily summary). Score <= 6: confirmation screen + mandatory "Què no ha funcionat?";
  optional comment for every score. Group mobilities: each participant answers (students, leader,
  companions).
- A mobility closes only with EU Survey validated **and** satisfaction answered, or marked "not
  answered" by the coordinator with a reason.
- Panel (filters: course, call, project, participant type, cycle, destination/host): per indicator
  value, target, met/not met, n; satisfaction also median; response rate (answered / finished
  mobilities); satisfaction by participant type and by host; per-call funnel applications ->
  admitted -> mobilities done -> withdrawals, total and per cycle; evolution per course.
- Low scores list (<= 6) with reason and a button to create the improvement action.
- Permissions: `group_erasmus` sees aggregates and comments without names; `group_erasmus_coordinator`
  sees each participant's name, score and comments.

## Phase 2: exports, history, Mobilitat FP

- Per call and per course, PDF + Excel: both indicators with target and status, n, median, response
  rate, breakdown by type, improvement actions, generation date and calculation criteria. No names.
  The call's report is also added to the project ZIP, folder `05_Informe_final_i_auditoria`.
- Manual historical values form (coordinator): course, applications, target, mean satisfaction, n,
  marked "manual load" with its source.
- **Mobilitat FP evidence pack** (for the network's annual report and the A1704 annex), per course,
  a ZIP laid out like the network's Drive, no personal data:
  - `1-gestio`: Erasmus+ team meetings held in EMS (Quality app minutes), if any;
  - `2-documentacio`: calls published with date and calendar (2.1); counts of applications and
    admitted per published list/resolution, without names (2.1); % of mobilities with complete
    documentation (2.2, A1704 target >= 95 %);
  - `3-mobilitats`: interest (3.1), participants and satisfaction (3.3);
  - `4-difusio`: every Erasmus+ mailing sent from EMS (call notice, closing reminder, ...) with date,
    generic audience ("alumnat de GS") and count: one diffusion action each (4.1-4.2).
  Same numbers as the panel, so one report serves the network and the ISO audit.

## Staff target (adriamt, 2026-11-04)

Exactly the staff call's `_ems_eligible_partners()`: teachers of every FP level (CFGB and PFI
included, they are cycle teachers too) plus the Director and the Head of Studies of FP who validate.
