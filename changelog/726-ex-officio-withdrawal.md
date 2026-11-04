# What's new

## Ex officio withdrawal case files (phase 1: opened by hand):
- Implements the centre's protocol for students who stop coming (Pla de comunicació, table "Baixes d'alumnat", and Resolució EDF/293/2026, point 8.6), as validated by Direction on 2026-11-03. Each level says which educational stage it belongs to, as the regulation sets it (`ems.level.education_stage`, part of the catalog in `data/cat/ems.level.csv`, read-only on the form): compulsory (CFGB, ESO) or post-compulsory (CFGM, CFGS, EFPS, PFI, BTX). The case file picks its circuit from the stage of the student's level, a criterion other decisions will use too.
- New `ems.ex_officio_withdrawal` case file (number `BO-<course>-NNNN`, student, group, level, circuit, first day of absence, origin, state, cancel reason), `ems.ex_officio_withdrawal.step` (step, responsible, day, notes, done by/on) and `ems.ex_officio_withdrawal.check` (each action a step asks its responsible to confirm, with the day it was done). One open case file per student.
- The tutor (and the chain above them) opens a case file by hand, then starts the procedure (the circuit's steps are created with their deadlines) or dismisses it with a reason. Post-compulsory deadlines are school days (5, 10, 15; weekends, holidays and school breaks skipped, read from the public holidays calendar), compulsory ones calendar days and months (7 and 15 days, 1, 1.5 and 2 months).
- Access: the tutor scope sees its own students' case files; Coexistence, Guidance, Head of Studies, Director and the Secretariat see every one; other teachers none. New menu Academic management > Ex officio withdrawals, a smart button on the student form and the educational stage on the level form.

## Ex officio withdrawal steps and tasks (phase 2):
- "Accept and continue" closes the current step of a case file: never before its due date, and only once every action it asks for is confirmed with its day (phone call, email to the family, eNotum, Esfera, SAGA, emails to Social Services and the Inspection, Direction's green light); it records who and when, logs it in the chatter and hands over to the next step. The state follows the current step (Pending Direction, Pending the Secretariat). The withdrawal step itself is left for the withdrawal wizard (phase 4).
- Each responsible gets a task on the step's own date (hourly cron), shown in My tasks and the daily summary: the tutor, the Coexistence coordinator under the tutor's Head/Deputy Head of Studies, the whole secretariat, the Director. The tutor gets a task to decide the proposal until it is started or dismissed.
- Who may do each step: the administrators always; tutor's and Coexistence's steps, also the Head of Studies and the Director; the Secretariat's, the secretariat; Direction's, the Director.

## The case file form, per responsible (2026-11-04):
- Whoever does the current step gets a block with what to do and from which day until which one (late or not yet open is said), each action to confirm as a sentence with its day (today by default), ticked and saved in as many goes as needed, and their notes; "Accept and continue" only works once every action is confirmed. Before the step's day the block only informs (read-only, no button). Everybody else gets one line saying whose turn it is.
- The steps list is replaced by a read-only history: every step in order with its due day (and the protocol's day when it was moved) and when it was really done and by whom, each action with its day and the notes; the current one in bold and the pending ones greyed out.
- The protocol's waits are always kept: a step accepted late moves the following ones, each due on the later of its protocol day and the previous step's real day plus the wait between them (school days in post-compulsory, calendar days in compulsory). A tutor who contacts the family a month late no longer lets the Secretariat and Direction do their steps the same day.
- A new case file only offers the user's own students (their tutor scope; everyone for the Head of Studies and the administrators) whose level has a circuit.
- The tutor can request an ex officio withdrawal from the student's form (Actions), for a student whose level has a circuit and no open case file.

## Emails to the family, texts to copy and the case file PDF (phase 3):
- In the steps that write to the family, the email is offered right below what to do, one button per text: the text is the template's, filled in and in the family's language, editable before sending. It goes to the student, and to the family while a minor or when the student authorised sharing; it is never sent on its own, it is required (one per step), and sending it is the only way its check gets ticked, keeping the text sent in the case file. The post-compulsory tutor has two buttons, "I reached them" and "I did not reach them": each asks the day of the phone call and shows its own email (both remind the family that fifteen school days of unjustified absence mean an ex officio withdrawal); sending it ticks the call, with how it went, and the email. "I did not reach them" can instead "try again tomorrow": the attempt stays in the case file and the step moves to the next school day. Every phone call of the protocol works the same way (the compulsory tutor's and Coexistence's too, with no email): one button per outcome, the day of the call, the outcome in the case file, and trying again the next school day.
- Social Services and the Inspection get no email from EMS: their text, filled in and in the centre language, is shown in the step's box with a copy button, and Direction can download the case file PDF to attach it.
- New case file PDF (Actions > Print the case file): every step with its due day, who did it and when, what was done and the notes.
- The email texts are drafts until Direction gives the final ones.

# Changes

## Levels: tidier form, convalidations set in Settings:
- The level form shows the main data (acronym, name) and below it the configuration: the educational stage (read-only, set by the regulation) and the schedule declaration code, then the student card colour.
- Which levels allow convalidations is now set as one list in Settings > Convalidations (Levels that allow convalidations) instead of a checkbox on each level. It is no longer part of EMS's catalog, so an upgrade never reverts the centre's choice; a new installation starts with CFGM and CFGS, and existing ones keep what they have.
- The convalidation settings are reordered: first the requests (levels, request period, attendance notice), then the resolution in the order of the document (grounds of law, appeal, signed by delegation).

# Fixes

## The settings page opens for a user with only the Settings role:
- Reading the levels was refused to a user with the Settings role and no EMS role, which broke the whole settings page once it listed levels; they can now read them.

# Internal changes

## Student and family recipients shared:
- `res.partner._ems_student_and_family_recipients()` (formerly `_ems_convalidation_recipients()`) decides who hears about convalidations and ex officio withdrawals: the student, and the family while a minor or when the student authorised sharing.

## Per-course registry numbers shared:
- `ems.base.next_course_number()` now builds the per-course registry numbers (one `ir.sequence` per kind and course) used by convalidations (CONV) and ex officio withdrawals (BO), instead of convalidations keeping their own copy.
- `resource.calendar.leaves._ems_holiday_dates()` returns, in one search, the company's days covered by a public holiday or school break in a date range.

## Task recipients shared:
- `ems.base.task_users()`, `role_task_users()` and `secretariat_task_users()` resolve who gets a task held by a position or by the secretariat, now shared by convalidations and ex officio withdrawals. `hr.employee._ems_coexistence_coordinators()` (the coordinators under the same Head/Deputy Head of Studies) is shared by strikes and ex officio withdrawals, and reads the coordinators in one batch instead of one search each.
