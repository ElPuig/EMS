# What's new

## Erasmus+ staff call (vocational training staff apply from the portal, a panel rates their mobility plans):

- A call is now for students or for staff. A staff call opens with just its dates: the documents of the call are added on their own, and the places (which may change with the projects) are only needed before the provisional resolution.
- Staff with an employee file see it on `/my/erasmus` and apply once, with their own form: activity, host entity or course, destination, dates, the month of their last Erasmus+ staff mobility from the centre (or never), the month they joined the centre, their highest language certificate, centre projects and confidential support needs.
- Each staff call has a panel (management and heads and seminar chiefs of the departments). "Send plans to the panel" creates one rating per admitted application and panel member; every member rates every mobility plan with annex 2's rubric, from Erasmus+ > My plan ratings, seeing only the plan. Candidates and members with a conflict of interest abstain, with no substitute: the plan score is the mean of the others. A pending rating blocks the score.
- Last mobility, seniority and languages are scored from what the applicant declares; the team only corrects them if they are wrong, and records the merits with their justification and maximums. Everyone is ranked in one list for the whole call (ties: mobility plan, then seniority, then the draw); the selected are those within the call's places, one place per person, and the team assigns each one a project and period afterwards.
- Resolutions, offers and the participants spreadsheet work as for students: lists without names (identity document from the employee file), free places offered from the whole call's reserve list, export data from the employee file.

# Internal changes

## Shared evaluator workflow for interviews and plan ratings:

- The submit / reopen / lock / activity / evaluator-group logic of `ems.erasmus.interview` moved to an abstract `ems.erasmus.evaluation`, inherited by the interviews and the new `ems.erasmus.plan_rating`. The call's "Interview review deadline" is now "Score correction deadline", for both.
