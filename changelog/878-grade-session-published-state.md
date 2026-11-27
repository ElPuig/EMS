# What's new

## Evaluation sessions: "Published" state, claims period and provisional grades:

- New "Published" state between the board and the final state: the grades become read-only (except for an administrator) and, in a later step, visible in the student portal.
- The Head of Studies manages the evaluation sessions (until now only the administrator): creates them, changes their state and sets the claims period and whether provisional grades are allowed.
- The creation wizard no longer asks for the round (the next one is computed) and requires the claims period (two clearly labelled dates); the fourth round is now the extraordinary evaluation (2a convocatòria).
- States move one step at a time, forwards or backwards, and the state wizard only offers the states the sessions can reach; publishing needs the claims period and warns (without blocking) about sessions with empty outcome grades.
- State changes from the sessions' list on the selected sessions (Actions > Change state) and from each session's Actions dropdown; the claims period and the provisional switch can be edited in bulk from the list.
- Teachers can mark an outcome's grade as provisional by typing `6*` or `6p`, or ticking "Provisional" on the outcome's column, which stays ticked and makes every grade entered later in that outcome provisional too; allowed by default, the Head of Studies can turn it off per session.

# Fixes

## Tutors' evaluation view shows the tutor's own students:

- The view listed every student of the sessions of the tutor's groups, including students of other tutors attending one of their modules, and missed the tutor's own students' modules in other groups. It now shows the students the tutor follows, with every module they take in any group, and the tutor can edit those grades.

## Grade screens much faster:

- Creating the sessions of a study went from 28 s to 6 s, and opening the tutors' view from 12 s to 0.2 s.

## Wizard overlay stuck after changing states from the list:

- The "Changing the state..." overlay stayed on screen forever when the wizard closed itself and went back to the list, and the long-running wizards (session creation, imports, course transition) showed their "in progress" overlay forever when a required field was left empty.
