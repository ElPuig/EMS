# Breaking changes

## New dependency on OCA's sign_oca (OCA/sign, branch 18.0):

- EMS now depends on `sign_oca`. Before upgrading production, clone `https://github.com/OCA/sign.git` (branch 18.0) next to `queue` and `partner-contact` (`/root/myModules/sign`) and add it to the `addons_path` of `/etc/odoo/odoo.conf`; the upgrade then installs `sign_oca` on its own. `install.sh`, the CI and `/deploy-check` already include it.

# What's new

## Erasmus+ documents signed electronically in EMS (sign_oca):

- A call document (grant agreement, learning or mobility agreement, certificate of stay, Europass, report) can have a signature template: the SEPIE model with the place of each signer's signature, placed once with one sign role per Erasmus+ signer.
- From the participant's record the Erasmus team clicks Send to sign on the filled-in PDF: EMS prepares the request with whoever still signs (participant, family of a minor, Director, Erasmus coordinator, host entity's contact person), lists anything missing (a signer, an email, a box), and the team checks and sends it.
- Every signer signs from a personal link, without an EMS account (the host entity too); the portal shows Sign it here to the participant. Each signature ticks its line (it can't be unticked) and, once everybody has signed, the signed PDF is added to the document for the team to mark it valid.
- The commitment letter keeps its acceptance on the portal and the sBID documents are still signed in sBID.

## Erasmus+ free places and over-full rectifications (decided by the Erasmus coordinator):

- When a renunciation, an offer left unanswered or a rectification frees a place that a reserve can take, every member of the Erasmus team gets a task on the call ("free place in GM: offer it to the next reserve"), marked done once the place is offered. EMS still never offers it on its own.
- A rectification that would leave more people with a place than places (an accepted place is never withdrawn) shows a warning and cannot be published until the team decides what to do, e.g. adds a place to the modality.

## Erasmus+ staff call: the Direction sees no points while the panel rates:

- The Head of Studies and the Director sit in the staff call's panel and could open any staff application and see the running mean of the plan ratings already submitted before giving theirs. Outside the Erasmus team, the plan score, the six criteria and the total of a staff application now read as 0 until every plan of the call is rated.

## Erasmus+ menus in sections, the portal entry and each person's Erasmus+ history (review by Juan Morote and Fernando Porrino, 2026-11-02):

- The Erasmus+ app's 14 loose menus are grouped like the rest of EMS: Calls (calls, applications, ranking, claims, resolutions, place offers), Mobilities (individual and group), Financial management (projects, invoices, grant payments) and Configuration (host entities). Each section only shows to whoever sees one of its entries (the Secretary sees only Financial management); the personal entries (My evaluations, My plan ratings, My group mobilities) stay loose on the bar.
- The student portal's top menu has an Erasmus+ entry, under the same rule as its card: students who cannot apply (PFI, CFGB) see neither.
- New read-only Erasmus+ history (ems.erasmus.history, an SQL view over the individual mobilities and the group mobility participants, cancelled and withdrawn ones left out): shown under the academic history on the student form, to the same roles that read that history plus the Erasmus team, and on the application next to First mobility. It holds names, country, city, dates and Planned/Completed only, so no access to the Erasmus+ app is needed.
- The application form no longer asks the student whether they took part in Erasmus+ before (fields previous_mobility and previous_mobility_details removed, never released): First mobility stays the Erasmus team's, checked against that history from next year on.

## Erasmus+ on the portal shows where each application is and what to do now (review by the Erasmus coordinator, 2026-11-02):

- Each application has a step bar (application, document check, interview or plan rating, resolution, place, preparation, stay, return), with the step where it ended crossed out, and a "what to do now" box with the deadline, which replaces the separate notices for corrections and the interview (ems.erasmus.application._ems_portal_progress).
- The state badge is coloured (green selected or accepted, amber corrections or reserve, red excluded); the Erasmus+ page lists the person's applications first, then the open calls, and folds the rest under Other calls.
- Once an application can no longer change, the call's text and the form fold away at the end; of the published results only the newest is open.
- A defined mobility is split into tabs (Summary, My record with how many documents are missing, Steps, During the stay, On return), opened on the one with something to do.
- Backend: the user menu has My Erasmus+ application for a staff member with a call to apply to or an application (session_info's ems_erasmus_portal); the call form has buttons to its interviews or plan ratings, resolutions, claims and place offers, so Interviews and Plan ratings leave the menu; an interviewer and a panel member now have separate hidden groups (ems.group_erasmus_panel is new), so each only sees their own My ... entry.

## Erasmus+ notice of an open call and reminder before it closes (asked by the Erasmus coordinator, 2026-11-02):

- Actions > Notify who can apply on a published call opens a wizard (ems.erasmus.call.announce) with how many people get it (and how many have no email) and emails the call to each of them alone, with its dates and the link to apply: students of the modalities' levels not ruled out by conduct warnings, or, in a staff call, the teachers of its levels and the Direction that validates (_ems_eligible_partners, the portal's rule in the other direction). The family is not emailed. It can be sent again; the wizard warns it was already sent.
- Reminder (days before closing), 3 by default: an hourly cron (ir_cron_erasmus_remind_closing) emails, from 9:00 on that day, whoever can apply and has not submitted (a draft does not count), once per call and only if the notice was sent from EMS (0: none). The call records when each email went out and to how many people.
- Rendered once per language and one mail.mail per recipient: about 515 students in 0.5 s and 59 staff in 0.1 s on the dev database; the conduct-warning check for the whole list is one grouped query (_ems_conduct_blocked_partners, sharing _ems_course_start with the per-student count).

## Erasmus+ review of the whole process by role (2026-11-02):

- Portal: the applicant's own row is highlighted in the published lists (with a note on ties), they claim from the portal with files (EMS records when it arrived and the team gets a to-do; the response shows on the portal), a reserve sees their reserve number, a student below the minimum is told so, the badge shows the provisional result, the place offer shows the modality's period and destinations, the destination choice shows country, city and "1 free place", the availability question shows the period, the buttons say Send the changes / Send the corrections, the plan sections count characters, and a student's image consent is their authorisation of the course instead of a question.
- Mobility record: only what the participant has to do now is red (a document the team uploads says so; one not due yet says "Not yet"); return documents are folded until then; not applicable documents are hidden; the backend list has fewer columns and "2 / 3" signatures; "Needs changes" only on a document with a file.
- Call form: buttons by phase (none hidden in "More"), tabs in two blocks (selection, mobility), the tie warning on top, dates without seconds, no bin on resolutions. Applications from the call grouped by modality, with documents to review; the ranking shows the cut of the places and the menu's ranking is ordered by call, with its column.
- Interviews scheduled in bulk (Actions > Schedule interviews), the rubric written on the form, Submit and next for interviews and plan ratings, abstentions shown as such and a pivot of the ratings. Resolutions with a colour legend and no rank or score on excluded lines.
- Head of Studies and Director: Mobilities > Pending validation, a note instead of zeros while the panel rates, no place offers nor claims in their menu (and the interviewers no longer see My plan ratings): the groups taken away from a menu are removed explicitly, since an upgrade only adds them. On a group mobility they no longer see Request the exception, Renounce nor EU Survey answered, which only the team or the leader can use. The staff proposal takes the country from the application. The emails are headed "Erasmus+". The user-menu entry is "Erasmus+".

## Erasmus+ appeals answered by the student's own Head of Studies, and the applicant told of every claim and place answer (review by role, 2026-11-03):
- The definitive resolution and every rectification (email and portal, and the group mobilities' result email) now say they can be appealed before the Head of Studies within one month, as art. 14 of the calls requires (the calls' text was changed from the Director to the Head of Studies of FP).
- An appeal gets a to-do for the applicant's own Head or Deputy Head of Studies, resolved up the chain from the student's group tutor (from the teacher in a staff call; the Director if the applicant is that Head of Studies; the administrators if it is the Director); only they and the administrator answer it, writing just the response (Head of Studies get write access on claims, guarded in write()). The Erasmus team still records and sees it, without a task.
- Every claim and appeal emails the applicant a receipt with the moment it arrived and, once resolved, the response.
- Accepting or renouncing a place emails a confirmation; an offer that expires emails the applicant that the deadline passed, and the portal and the rectification email say "you did not answer in time" instead of "you renounced" (ems.erasmus.application._ems_offer_expired).
- A minor's family gets a copy (email_cc) of the place offered (definitive list or free place) and of the answer to it; the other lists and the claims still go to the student only.
- The group tutor gets a notice (message_notify on the student, not a to-do) when their student accepts a place.
- Excluding an application once the admission list is published (e.g. not attending the interview) emails the reason, and the portal shows it instead of pointing to results that do not exist yet.

## Erasmus+ group claims from the portal, one notice per evaluator and the accepted places at a glance (review by role, 2026-11-03):

- A student of a group mobility claims against the provisional list from the portal card, with files, as in the calls (before: by replying to the result email). They get the receipt and the answer by email, the Erasmus team gets a task to answer it, the claims show in the mobility's Selection tab and in Erasmus+ > Calls > Claims, and the selection cannot be approved while one is open.
- Scheduling interviews in bulk sends each evaluator a single notice with the whole list (date and time, place and applicant) instead of one "activity assigned" email per interview; the tasks, one per interview, still close when scored.
- The call shows how many places are accepted out of the total (a stat button) and how many offers still wait for an answer, to know when to open the destination choice.
- When the coordinator rejects a substitution in a group mobility, the leader teacher gets a task to propose a substitute again.
- Wording: a reserve's result email gives their number on the reserve list of their modality; the selected read "Tens plaça" / "Tienes plaza" instead of "seleccionat o seleccionada"; an admitted or excluded applicant is no longer told to look at the detail of a score they do not have; every Catalan and Spanish email says "portal del centre" / "portal del centro"; the rectification's notes warn not to write anyone's name, since they are emailed to everyone on the list.

## Erasmus+ place offers show the destinations and their places:

- Before accepting a place, a student sees the destinations of their modality with their places (and dates when known) on the portal's offer card, the selected's result email and a free place's offer email, plus their position in the modality on the portal: the destination is chosen later by turns in rank order, so they know what they may get before accepting instead of renouncing late.

## Erasmus+ app for every teacher, with a "My participation" section (2026-11-03):

- Every teacher now has the Erasmus+ app, right below Meetings, with My participation > My application, which opens their portal page to apply to the staff call and follow their mobility. The Erasmus+ team's own entries (My evaluations, My plan ratings, My group mobilities) moved into that section too, so a coordinator who also applies to the staff call tells their participant view from their management one (Calls, Mobilities, Financial management) at a glance. The section goes after the management ones so the team still lands on the calls when opening the app.

## Erasmus+ result emails copied to the family of an adult who shares with it (2026-11-03):

- The copy of the place offered and of the answer to it now goes to the family whenever EMS keeps it informed about the student, with the same rule as convalidations: a minor, or an adult who authorized sharing their information with the family (before, only minors).

## Erasmus+ conduct warnings no longer rule a student out of a call (2026-11-03):

- A student with as many conduct warnings this course as the coexistence threshold can now apply, submit and be admitted like anyone else. The application form warns the Erasmus team ("Conduct to review"), who may exclude it with the reason after hearing the teaching team and the coexistence team, as the new art. 6 of the call says. Each warning still takes points off the score (criterion F). Group mobilities follow the same rule: enrolling is never blocked, and the coordinator excludes with an exception and its reason.

## Erasmus+ staff application, shorter and friendlier (2026-11-03):

- The staff form has four short blocks: two required proposals in the teacher's own words (A, the main one, and B, a backup if A falls through, each saying the activity, the host, where and when), one text with what they want to learn and how they will apply it, a few facts about them, and an optional folded part (support needs, image, notes). The panel reads the two proposals and the text and gives one score; once selected, the teacher writes the exact entity and dates in the mobility's proposal, which starts with both proposals.
- The last staff mobility is no longer asked by month: the teacher only ticks that they never had one at the Puig, and the Erasmus team sets the others. The date at the centre is still asked.
- No CV nor identity document is asked to apply: the identity document is now asked only of whoever goes, among the mobility's documents. The call's rules (art. 8, criterion 2, annex 1) were updated to match.

## Erasmus+ staff get a task, not a weekly email, for what they still have to hand in (2026-11-03):

- During the preparation, a staff member gets one EMS task listing what is still missing (documents, commitment letter, weekly self-assessments), updated every week and removed once everything is handed in. Students keep the weekly email, since they only use the portal.

## Erasmus+ students' application form, clearer and documents first (2026-11-03):

- The form starts with the documents, each with what it must contain: the Europass CV in English (PDF only, with a link to the Europass editor and what to include: studies, what you learn in the cycle, strong points, "About me", a photo) and the presentation video, now handed in as a Google Drive link with the steps to share it with the school. Each call document can be set to accept any file, PDF only or a link, with a link for its instructions; a new students' call brings these documents ready.
- Fewer opportunities: a short summary of the situations that count, and the field to upload the evidence appears only when the student ticks the box (then it is required). Anything else for the team goes at the end. The availability question is gone: the dates are in the call's rules.
- The call's PDF field is now labelled "Call rules (PDF)", with a help explaining that applicants download it from the portal.

## Erasmus+ quality: interest and satisfaction indicators, satisfaction survey and improvement actions (asked by the Erasmus coordinator, 2026-11-04):

- New menu Erasmus+ › Quality (Erasmus team): an Indicators screen with the two indicators of the Erasmus+ quality system and the Mobilitat FP report, with their target and whether it is met: student interest (applicants / every student of the call's levels, GM + GS + specialisation, target > 5 %), staff interest (applicant teachers / the FP teachers plus the Direction that validates) and satisfaction (average 1-10, target > 8.5, with n and median), plus the survey response rate, satisfaction by participant type and by host entity, each call's funnel (applications, admitted, with a place, done, renounced) in total and by cycle, and the evolution by course. Filters: course, call, project, participant type, cycle, host entity. No minimum group size (decided by the coordinator).
- The interest counts are frozen on the call when its definitive resolution is published, so the history never changes.
- Every participant (individual students and staff, every member of a group mobility) answers one question on the portal when the stay is over, "In general, how satisfied are you with your Erasmus+ mobility experience?" from 1 to 10, with an optional comment; 6 or lower asks for confirmation and a mandatory "What did not work?". Students get an email and reminders at 3 and 7 days; staff a to-do in their daily summary.
- A mobility (individual or group) only closes with its surveys answered, or closed without an answer by the coordinator with a reason.
- The team reads the answers without names (only the coordinator and the administrator see who answered). A low score becomes, with one button, an improvement action of the Quality app without the participant's name: the ISO evidence.
- Quality report (PDF) from the indicators screen, for any filters: figures, improvement actions, calculation criteria and date, no names; it also goes by itself into each project's ZIP (folder 05).
- Mobilitat FP evidence (ZIP) per course, laid out like the network's Drive (1-gestio: the Erasmus+ team's minutes of the workgroup set in Settings; 2-documentacio: calls with their calendar and rules, totals of each published list, % of participants with complete documentation; 3-mobilitats: the quality report; 4-difusio: the diffusion actions and their evidence). No personal data.
- Diffusion actions register: every call notice and closing reminder EMS emails is recorded by itself; the team adds the rest by hand (sessions, ErasmusDays, web, social media).
- Earlier courses (manual load, with their source) feed the evolution by course; the coordination's figures for 2022-2023 to 2025-2026 are seeded as centre data.

## Usage test by role, second batch (files, corrections, families, staff call, team):

- Repeated files: a call document is handed in as **One file** by default (unticked for the language certificates); its newest upload counts and the earlier ones show as *Earlier version* with their dates, on the portal and in the backend (*Files*, optional *Every version*), and the receipt lists only the newest. While the application is a draft the student removes a file uploaded by mistake from the portal.
- The receipt and the backend show a link document's address, not "Video (link)".
- Corrections can only be requested with a corrections deadline still to come (the email had no date and the corrections never closed).
- A document line without any file can never be *Valid* (it let an application be admitted without the document).
- The application's documents show their status (missing, to review, complete...) and the ones that do not apply are greyed out, instead of every line saying "Pending review"; a draft no longer counts documents to review.
- "Offer a free place" comes with a default answer deadline: as long as the definitive offers had, or three days.
- A staff call published without places warns the team (it still opens without them, as the call allows); admitting a teacher without a DNI in their employee file warns the team to ask the Secretary; preparing a resolution says what is missing of each incomplete score.
- The family of a minor reads its own sentence above the commitment letter, sees the application read only on its portal from the start, and downloads a call document's **Model to download** (e.g. the family authorisation).
- A member of the Erasmus team who is not a teacher lands on the calls instead of an access error, and creating an improvement action no longer opens a screen they cannot read.
- A teacher sees the activity proposal they sent while it waits for validation.
- Smaller: Catalan "de" elided before a name in the to-dos' subjects ("d'Alumna"), one interviews notice for evaluators with the same list, a new call shows its documents and steps before saving (also when switching between students and staff), and the panel's options show their points.

## Students apply without a family authorisation (the family gets the receipt instead):

- A new students' call no longer brings the "Family authorisation to take part" document (decided 2026-11-05 with adriamt): the family's consent comes once the place is accepted (commitment letter and travel authorisation, both signed by the family).
- Instead, the application's receipt goes with a copy to the family whenever EMS keeps it informed about the student (a minor, or an adult who shares with the family), like the result, the place offered and the answer already did.

# Fixes

## Erasmus+ result and free-place emails reached Catalan and Spanish readers in English (2026-11-03):

- The emails of a published list and of a free place offered had lost their Catalan and Spanish translations after their last change; they are translated again.

## Erasmus+ documents' "Signed" column showed a technical text (2026-11-03):

- A document that needs no signature showed "ems.erasmus.document.signature()" in the Signed column of the application and mobility forms; the cell is now empty.

## Erasmus+ health card twice in a staff mobility, and the administrator in the Erasmus team:

- Validating a staff proposal as the Director added the European Health Insurance Card again: the documents still missing were looked up with the Director's rights, which hide confidential documents. They are looked up as superuser now.
- The administrator was in the Erasmus team, so every team to-do went to them too. They are out of the team groups and keep every right as administrator. The Head of Studies and the Director no longer see the review buttons (Valid, Needs changes, Signatures, Remove a file) on a mobility's record, which they could not use.

## Erasmus+ students' call: claims, ties and rectifications found in the end-to-end test of the selection:

- The definitive resolution can no longer be prepared or published before the call's claims deadline, nor while a claim of the call is still open (art. 14): it was only shown to applicants and never checked.
- A claim upheld after the draw that tied someone with applications already drawn put the newcomer first with no draw (its draw order 0 sorted first). The whole tied set now needs a draw again, and the coordinator can draw ties also after the definitive resolution, so a rectification is never blocked by a tie it creates.
- A rectification now withdraws the offers still waiting of whom it no longer selects (they could still accept a place the list gave to someone else), with a note in the application's chatter; a reserve keeps an offer made for a free place unless they fall below the minimum score.
- The result email of a rectification tells who already accepted that they keep their place (it said they were on the reserve list), and who renounced that the list does not change it.

## Erasmus+ staff call and published lists, found in the end-to-end test of the staff selection:

- Printing a published list as PDF (students' and staff calls) failed with "Report template 'Published list' has an issue": the report keeps each published list's PDF for the project's records, and its template did not name the record on each page. The project's records export, which includes those PDFs, failed for the same reason.
- Staff call: a tie after the mobility plan score is now broken by who has been at the centre longer, by the month and year of joining declared in the form (art. 11), not by the points of criterion 5. Two people with 25 and 6 years at the centre both get 2 points and used to go to a draw.

## Erasmus+ group mobilities, found in the end-to-end test of a group mobility:

- The coordinator could approve the selection (definitive list) right after publishing the provisional one, with the claims deadline still open. Approving now waits for that deadline, as the calls' definitive resolution does.
- A reserve who did not want a free place blocked every reserve after them: rejecting the substitution only made EMS propose the same reserve again. The enrolments in the Selection tab now have a Renounce button (Erasmus team and leader teacher, with the reason) for a selected student who tells them they cannot go (before, only the student could, from the portal) and for a reserve who does not want the place: the reserve leaves the list and the next one is proposed.
- A reserve who does not want a place can also leave the reserve list by themselves from their portal card, with an optional reason (decided by the Erasmus coordinator).
- The published lists of a group mobility head the record average column as Average (it read Score, as in the calls, although a group mobility ranks by the average).
- Any leader or accompanying teacher of any group mobility could read the draws of every group mobility, with the students tied and whether they had fewer opportunities accredited. The draws are now readable only by the leader of their own mobility, and that flag only by the Erasmus team, as on the enrolment.

## Erasmus+ interviews of an excluded applicant left open (review by role, 2026-11-03):
- Excluding an application now deletes its interviews and plan ratings still to score, with the evaluators' to-dos.

## Erasmus+ usage test by role (2026-11-04):

- A call created from the app had no documents, mobility documents, checklist, self-assessment questions nor commitment letter: the defaults were only added when the form did not send those fields, and it always sends them (empty). Now they are added whenever they come empty, for students' and staff calls.
- The portal showed a generic "it could not be saved" for every refused action; it now shows the real reason (which required document is missing, a CV that is not a PDF, a link without https://), on the application and the group mobility pages.
- A refused file no longer loses the rest of the same form (e.g. the video link pasted with a CV that is not a PDF): valid documents are kept and the refused ones listed together.
- After choosing a destination, signing the commitment letter, uploading mobility documents or answering a self-assessment, the portal no longer says "remember to submit the application before the closing date".
- To-dos created by the scheduled jobs (staff satisfaction survey, staff "hand in what is missing", the team's "a place is free") are written in the recipient's language, not in English.

## Erasmus+ group mobilities usage test by role (2026-11-05):

- A group mobility created from the app asked for no document (the same cause as the calls': the form always sends the field, empty). Now it gets the default KA121-VET documents.
- The default selection criteria said students with too many conduct warnings were left out, which is no longer the rule (2026-11-03): the text now says only the period, the eligible group, the average, the fewer opportunities and the draw.
- A student the coordinator excludes with an exception stayed in the ranking, so their place was lost (one student fewer selected than places, with no warning). Now they leave the ranking and the next one moves up.
- The leader teacher could not save an exception request from the Selection tab, and that also blocked sending the proposal.
- A photo attached to the follow-up during the stay (or the leader's EU Survey evidence) could only be read by whoever uploaded it: the leader and the Erasmus team got an access error opening the mobility. The files now follow the mobility's access.
- On the portal, a withdrawn enrolment showed "Withdrawn" and "Enrolled" at once (and a published result also showed "Enrolled"): only one status is shown.
- Improvements agreed with adriamt after that test: the coordinator's task to answer a leader's exception request stays pending until the coordinator decides; the team can enter a corrected average for a student with grades (an upheld claim) and everyone sees the average the ranking uses; the mobility warns when more students are selected than places, when a student has a serious conduct record (only a warning, the coordinator decides) and, before the stay starts, who is not ready to leave (the button asks for confirmation); the team sees who enrolled during the enrolment; a new "Participants' documents" list shows every participant's documents on one screen (e.g. to upload the grant agreements at once), each line saying who signs it.
- Portal and emails: the family of a minor gets a copy of the provisional and definitive results; a reserve proposed for a free place is told so; documents the team uploads first say "The Erasmus team uploads it" instead of a red "Missing" and what does not apply is not listed; the card shows the exclusion reason and the reserve number; the commitment letter names the student instead of "the student"; the published list explains the group's tie-break; a teacher who answers their last satisfaction survey sees the thanks.

# Internal changes

## sign_oca integration details:

- `models/erasmus/electronic_signature.py`; the Erasmus team group implies Sign's "All Documents" and can edit the templates; the sign role names are translatable.
- sign_oca 18.0's Odoo 16-style test tour is removed from `web.assets_tests` (it would fail every tour); the EMS portal landing now has priority 110, above sign_oca's portal home card.

## End-to-end test of the students' call:

- `tests/test_erasmus_student_call_e2e.py` runs a call with a GM (KA121-VET) and a GS (KA131-HED) modality, 2 places each, from publishing to the accepted places, with the real roles (technician, evaluators, coordinator, Head of Studies): conduct-warning block, missing document, corrections round trip, an exclusion for not correcting and one for not attending the interview, single interview with a reason, below the minimum score, an exact tie drawn, a claim upheld, the claims deadline, renouncing, a reserve offer expiring and the next reserve accepting.

## End-to-end test of the staff call:

- `tests/test_erasmus_staff_call_e2e.py` runs a staff call (2 VET + 1 HED places as one pool) from publishing to a rectification, with the real roles (technician, coordinator, a four-member panel with a candidate who abstains, Head of Studies): who can apply (FP teachers and Direction, not ESO teachers nor administration), the mobility plan required, a corrections round trip and an exclusion, the panel seeing only its own ratings, merits, both tie-breaks and a draw, places needed for the provisional list, a claim upheld, the claims deadline, accepting, renouncing, a reserve offer expiring, assigning the project, and a rectification blocked until a place is added.

## End-to-end test of a group mobility:

- `tests/test_erasmus_group_mobility_e2e.py` runs a KA121-VET group mobility (4 students, leader and accompanying teacher) from its creation to its closure with the real roles (technician, coordinator, leader, accompanying teacher, Head of Studies, students and a family on the portal): enrolling only from the eligible groups, the conduct-warning block before and after enrolling, a withdrawal, the frozen ranking with real grades, fewer opportunities accredited or not, two students with no grades (average entered with its source, and excluded by the coordinator), a tie drawn, the proposal sent back and sent again, the provisional list (masked DNIs, no names, emails), a claim upheld, the claims deadline, the definitive list, the commitment letter accepted provisionally and again after the destination is confirmed (student and family of a minor), renouncing, substitutions and a reserve who does not want the place, documents and who reviews them, insurance (own or collective), the optional documents, the participants' spreadsheet and the documents' ZIP, the stay, the programme question, the EU Survey and the closure; and what each role reads (read and search_read).
