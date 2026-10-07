# Changes:

## Justifying a severe delay turns it into a minor delay (issue #578):
- A severe delay counts as an absence, but a justification only ever converted plain misses
  (into "Justified Miss"), so severe delays had no way of being justified at all.
- A justification now also picks up every severe delay in its period (the "Affected sessions"
  tab lists them) and turns each into a "Minor Delay", linked to the justification (so it is
  locked in the roll-call, like a justified miss) and noted "Severe delay justified by: <tutor>".
- Removing the justification, or shrinking its period so it no longer covers the line, turns it
  back into a "Severe Delay"; plain misses still go back to "Miss".
- Previsions (justifications for days still to come) are unchanged: the student is
  pre-marked as "Justified Miss".
- Tutor manuals (ca/es/en) and the developer doc updated; ca/es translation of the new note
  added.
- The roll-call's lock tooltip on a justified line now reads "Justified: status and notes are
  locked." (it said "Justified absence", which no longer fits a justified delay).
