# What's new

## Erasmus+ grants, provision of services and payments (phase 6):

- Each mobility gets its grant (calculated in the Beneficiary Module) and the services the centre pays directly out of it (flights, accommodation, course fees...); EMS shows what the participant actually receives.
- Supplier invoices are uploaded once and assigned to the participants they cover: the amount is split equally among them as provision of services, and each share can be adjusted by hand.
- The Erasmus team requests the payments from the mobility: a prefinancing (a percentage, 80 % by default) before leaving and the rest on return, or a single payment at 100 %. Any change of the grant or the services after the prefinancing is settled in the final payment.
- The Secretary has a new "Grant payments" list under Erasmus+ with each participant's IBAN, and registers each bank transfer with its receipt: one transfer can pay several grants at once, or an invoice (e.g. a travel agency's). A paid payment can no longer be changed, nor a paid invoice deleted.
- Participants see their grant on the portal: the grant, what the centre pays for them, what they receive and the state of each payment (art. 5 of the calls).

## Erasmus+ host entities and tutors (phase 6):

- New "Host entities" menu under Erasmus+: companies, schools and course providers that host participants, with their tutors as contacts (name and email). The Erasmus team can create and edit them, but no other contact.
- A mobility's host entity is chosen from that list; the tutor is filled in automatically when the entity has only one, and the tutor's email is shown on the mobility. Sending the Learning Agreement to the tutor to sign waits for the integrated e-signature.

## Erasmus+ project dossier in SEPIE's folders (phase 6):

- The centre's three active projects are loaded (2025 and 2026 KA121-VET, 2026 KA131-HED), each with its grant awarded and the date its documents must be kept until (3 or 5 years after it ends, as SEPIE asks).
- Each project can hold its own documents (application, preparatory visits, exceptional costs, dissemination...) in one of SEPIE's 13 folders.
- "Download the dossier (ZIP)" gathers every document of the project in SEPIE's folder structure: published calls and resolutions, the participants' application and mobility documents, invoices and transfer receipts. Nothing is copied, so no paper gets lost or duplicated; confidential documents are only included for the Erasmus team.
- Published resolutions are kept as a PDF; each mobility document of a call says which SEPIE folder it belongs to; a new optional "Tickets or boarding passes" return document; host entities have their Erasmus+ OID.

## Erasmus+ staff call only for FP teachers, validated by the FP Direction (also its later changes):

- A staff call says which levels' teachers it is for (every FP level by default: basic,
  intermediate and higher cycles, specialisation courses, PFI) and who validates the activities
  (filled in with the Director and the Head of Studies of FP). Only those teachers and those
  validators see the call and the portal's Erasmus+ card: not the administration staff nor ESO
  or Batxillerat teachers. The validators get the task for every applicant, whatever the
  organisation chart says.
- A validated staff activity can change until it starts (another course, host or dates): the
  teacher proposes it again from the portal, or the team changes it and asks the Direction again.
  It stays as validated until the Direction decides; the absence for training follows the new
  dates. The Direction can leave a comment when validating, shown in the email and the portal.
- The panel rates each plan by picking the descriptions of annex 2 of the call instead of
  0 / 0.5 / 1 (the points stay the same underneath).
- The mobility and transfer plan (annex 1) is written in the application form instead of uploaded
  as a PDF: activity, a concrete host entity or course (pointing to the centre's Erasmus+ website
  for options), destination, dates, why that choice, objectives and application to the job, all
  required to submit. The panel reads it on its rating screen, still without seeing anything else
  of the application. Dissemination is no longer part of the plan nor of the rubric: everyone
  publishes a news item on the website and shares it at a meeting if needed (two return steps).
  The "not found yet", "accompany students" and "department informed" options are gone.
- Staff calls have one modality per project (FP KA121-VET and higher education KA131-HED), with
  places and no period; staff never see them.
- Staff never see the modality, places or periods (the team's planning); the date fields explain
  the rule (non-teaching period, or another week with the Direction's validation).

# Changes

## Erasmus+ portal: the call page links the published call:

- The link to the published call (PDF) is now also on the application page, not only on the list of calls.

## Erasmus+ students' call: conduct checked from EMS's own warnings, no manual sanction check:

- The Head of Studies / Director no longer record a "no serious sanction" check on each
  application (fields, filter, tour and the Head of Studies manual removed; they only read the
  applications now). EMS has no register of disciplinary sanctions, so art. 6 is applied from the
  conduct warnings (ems.strike): a student with as many warnings during the call's course as the
  coexistence escalation threshold (res.company.strike_escalation_threshold, 3) or more cannot
  apply. The portal shows them a notice instead of "Apply"; creating or submitting the application
  is refused; and admitting is refused if the warnings came after submitting (the form warns the
  team to exclude it). Criterion F (the penalty per warning) is unchanged. Agreed with adriamt
  2026-10-23: "3 o más este curso", without touching anything of coexistence.

## Erasmus+ tasks for the team and the Secretary:

- A corrected application (submitted again after a subsanation) gives each member of the Erasmus
  team a to-do to review it, done when they admit, exclude or ask for corrections again. New
  applications give none (adriamt: only corrections).
- Every grant payment requested and every invoice created gives whoever holds the Secretary role
  a to-do ("transfer X to Y" / "pay the invoice N"), done when the transfer is registered and
  scheduled again if it is undone; the Secretary sees them every working day in the existing
  daily pending-tasks digest. Payments and invoices inherit ems.base (chatter and activities).

## Erasmus+ contact email for the replies:

- New company setting (Settings > Center Data > Erasmus+), defaulting to erasmus@elpuig.xeill.net
  and the same for every call (adriamt: "siempre será ese"): the reply-to of the Erasmus+ emails
  sent with nobody of the team behind them (the application receipt, which had none, and the
  reminders and cron emails).

## Erasmus+ mobility documents say who signs for the centre:
- A mobility document's "centre" signer is now two: the Director (by default, the grant agreement) and the Erasmus
  coordinator (by default, the learning agreement and the staff mobility programme), as the centre actually signs
  them. Shown in the call's Mobility documents tab and on the participant's portal card.

# Fixes

## Erasmus+ students' call: issues found walking through it as every role:

- The Erasmus team could not close a call: freezing the record average created the grade lines
  without sudo (only the administrator may create them), an AccessError.
- A minor could never sign their own commitment letter on the portal: the form was chained after
  the family's notices, so it only showed when neither applied; an adult got the form again after
  signing. It now shows exactly while the participant's signature is missing.
- The result emails' header showed "ems.erasmus.resolution.line,<id>": the line is now named
  "<applicant> - <resolution>" and described as "Erasmus+ result".
- Assigning a destination with a single host entity sets it on the mobility, with its tutor when
  the entity has a single contact (it stayed empty).
- The portal home card's text of Erasmus+ was untranslated.

## Erasmus+ staff call: issues found in the manual test run:

- A staff call always gets a minimum score of 0 (it was 50 unless created from the form's
  onchange, so everyone ended up "not selected": the staff criteria add up to 10); the field is
  hidden on staff calls.
- The panel gets two weeks after closing: a staff call sets its score correction deadline to the
  closing date + 14 days (following the closing date unless changed by hand). "Send plans to the
  panel" needs it; the panel's tasks are due that day (company timezone) instead of "today", and
  changing the deadline moves the open interview and plan-rating tasks.
- The task to validate a staff member's proposal no longer goes to every Head of Studies and the
  administrator: only to the call's validators (see above); only they (and the administrator)
  can validate it.
- The portal shows the application states and resolution results translated (they were raw
  English selection labels); same for the resolution PDF's results and the claims' names.
- Wording for staff: the mobility state "Choosing the destination" becomes "Defining the
  mobility", and a validated staff activity sends its own email ("your activity has been
  validated", with host, place, dates and the training absence) instead of "your destination".
