# What's new

## Evaluation sessions: "Published" state, claims period and provisional grades:

- New "Published" state between the board and the final state: the grades become read-only (except for an administrator) and, in a later step, visible in the student portal.
- The Head of Studies manages the evaluation sessions (until now only the administrator): creates them, changes their state and sets the claims period and whether provisional grades are allowed.
- The creation wizard no longer asks for the round (the next one is computed) and requires the claims period (two clearly labelled dates); the fourth round is now the extraordinary evaluation (2a convocatòria).
- States move one step at a time, forwards or backwards, and the state wizard only offers the states the sessions can reach; publishing needs the claims period and warns (without blocking) about subjects with no outcome graded at all.
- State changes from the sessions' list on the selected sessions (Actions > Change state) and from each session's Actions dropdown; the claims period and the provisional switch can be edited in bulk from the list.
- Teachers can mark an outcome's grade as provisional by typing `6*` or `6p`, or ticking "Provisional" on the outcome's column, which stays ticked and makes every grade entered later in that outcome provisional too; allowed by default, the Head of Studies can turn it off per session.

## Published grades in the student portal:

- The portal's Grades page (until now "under construction") shows the student's published and final evaluations, newest first: a table like the tutors' view with each module's grade (or the provisional one while an outcome is still pending), one column per learning outcome (greyed where the module has none) and the teacher's comment. Families see their child's, also in view-only mode.
- The grades can be downloaded as a non-official PDF.
- When publishing, the Head of Studies can tick "Announce the publication": every student, and the family of a minor, gets one email per evaluation with a link to the portal and the claims period, never the grades. The emails are prepared in the background, so publishing a whole round does not keep the screen waiting.

# Fixes

## Tutors' evaluation view shows the tutor's own students:

- The view listed every student of the sessions of the tutor's groups, including students of other tutors attending one of their modules, and missed the tutor's own students' modules in other groups. It now shows the students the tutor follows, with every module they take in any group, and the tutor can edit those grades.

## Grade screens much faster:

- Creating the sessions of a study went from 28 s to 6 s, and opening the tutors' view from 12 s to 0.2 s.

## Grade grid empty after moving to another session:

- Moving from one evaluation session to another with the form's arrows showed the new session's grid with empty cells (the grid kept the previous session's data) until the page was reloaded. Moving away with unapplied grade changes now asks first, as leaving the screen already did.

## Wizard overlay stuck after changing states from the list:

- The "Changing the state..." overlay stayed on screen forever when the wizard closed itself and went back to the list, and the long-running wizards (session creation, imports, course transition) showed their "in progress" overlay forever when a required field was left empty.

# Internal changes

## Student portal pages share how they resolve the student:

- The schedule and grades pages read the student the portal user is looking at through one shared helper instead of a copy each.
