# What's new

## Guard board proposals say what still needs a guard, and applying them asks who goes (#710):

- A proposal that does not solve every class of its groups now says so under its steps: "It still
  leaves 1A (09:00) without a teacher: once applied, you will choose the guard teacher." Worked out
  by the planner (`ArrangementPlanner.gaps()`): the classes still to come that the plan leaves
  without anybody and that no change told to the families frees the group from (a longer break
  still needs a guard, as in the ranking).
- Applying a proposal (all of it or only some steps) returns the classes the applied steps still
  leave to a guard, and the board opens the guard assignment of each one in turn, offering only
  "Send a guard teacher": the proposal already decided how to organise the day, and another one
  from there would branch off into its own gaps (developer's decision). Closing one moves on to the
  next; a class on another shift or already covered
  is skipped, and nothing opens when a notice could not be sent (its draft opens instead).
- Planner evaluation refactored so the ranking and the new gaps share the same rules
  (`_windows()`, `_needs_guard()`); tour helpers for hourly absences and a student with a family
  extracted (they were duplicated).
- Tests: the plan's gaps and its text, a plan that solves everything says nothing, applying part of
  a plan returns both gaps; a new tour applies a proposal that leaves the 9:00 class empty and sends
  the guard from the dialog that opens.
- ca/es translations, developer doc and teachers' manual (ca/es/en).
