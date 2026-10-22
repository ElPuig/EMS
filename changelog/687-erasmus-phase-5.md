# What's new

## Erasmus+ mobility preparation (destinations, documents and checklist after accepting a place):

- Accepting a place creates the participant's mobility (Erasmus+ > Mobilities, and a "Mobilities" button on the call). It holds the destination, the host entity (a reusable company contact) and its contact person, the dates, the documents to hand in before leaving and on return, and a checklist of steps.
- Students' calls get a "Destinations" tab (modality, country, city, places, the levels each one suits, dates). "Open destination choice", after the definitive resolution, starts the choice of art. 15: a modality with one destination is assigned directly; otherwise the selected choose on the portal by turns in rank order, with an email when their turn comes and a configurable time (72 hours by default). No answer in the turn passes it to the next one (hourly cron) and the student chooses among the destinations left once the others have chosen, keeping the place; rejecting every destination puts the student back on the reserve list with their score, after the other reserves. Freed places are still offered by the team with "Offer a free place".
- A selected student can propose their own destination on the portal, with the host entity's written commitment; the Erasmus team validates it or rejects it with a reason, and the student goes back to the centre's destinations.
- A staff member's mobility starts with the activity proposed in the application, waiting for the Director's validation (staff call art. 4 and 14). The Director validates it or rejects it with a reason, and the staff member proposes another one on the portal. Pending proposals give the validators a to-do.
- Calls get a "Mobility documents" tab (before leaving / on return, per modality, and who signs each one: participant, legal guardian, centre, host entity; signed outside EMS and uploaded) and a "Checklist" tab (preparation sessions, OLS, GS virtual component, EU Survey, dissemination...). New calls come with the documents and steps of the calls preset, editable. The team reviews each document as for applications, ticks the steps, emails the pending documents, and closes the mobility once the return is complete, or cancels it with a reason; the participant can renounce from the portal.
- Graduates doing a summer mobility keep their portal access through the course transition until their mobility is closed or cancelled; then EMS removes it as the transition would have done.

# Internal changes

## Erasmus+ call documents by stage:

- `ems.erasmus.call.document` has a `stage` (application, preparation, return). The call's and the application's `document_ids` show only the application ones, so phases 1-4 are unchanged; the mobility's lines are application document lines with `mobility_id` set.
- The course transition's "revoke the portal and archive the graduate" step is now `res.partner._ems_retire_graduate()`, shared with the release of a graduate whose Erasmus+ mobility ends.
