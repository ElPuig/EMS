# What's new

## Erasmus+ staff call (vocational training staff apply from the portal, a panel rates their mobility plans):

- A call is now for students or for staff. Staff with an employee file see the staff call on `/my/erasmus` and apply once, with their own form (activity, host entity or course, destination, dates, centre projects, interest in accompanying students, confidential support and care needs) and documents.
- Each staff call has a panel configured per call. "Send plans to the panel" creates one rating per admitted application and panel member; every member rates every mobility plan with annex 2's rubric, from Erasmus+ > My plan ratings, seeing only the plan. A member who is a candidate abstains automatically and the team sets the substitute the Director appoints; a candidate can never rate. A pending rating blocks the score.
- The team records criteria 2-6 of art. 11 (last staff mobility, merits with their justification and maximums, languages, seniority). Everyone is ranked in one list for the whole call, with the staff tie-breaks; the selected are those within the call's total places, and the team assigns each one a project and period afterwards.
- Resolutions, offers and the participants spreadsheet work as for students: lists without names (identity document from the employee file), free places offered from the whole call's reserve list, export data from the employee file.

# Internal changes

## Shared evaluator workflow for interviews and plan ratings:

- The submit / reopen / lock / activity / evaluator-group logic of `ems.erasmus.interview` moved to an abstract `ems.erasmus.evaluation`, inherited by the interviews and the new `ems.erasmus.plan_rating`. The call's "Interview review deadline" is now "Evaluation review deadline", for both.
