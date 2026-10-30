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

# Fixes

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
- Any leader or accompanying teacher of any group mobility could read the draws of every group mobility, with the students tied and whether they had fewer opportunities accredited. The draws are now readable only by the leader of their own mobility, and that flag only by the Erasmus team, as on the enrolment.

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
