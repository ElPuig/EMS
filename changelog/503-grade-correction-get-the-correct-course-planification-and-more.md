# What's new

## "Show only mine" filter on the Plannings list:
Since Head of Studies/Deputy now see every planning centre-wide, the Plannings list defaults to
"Show only mine" (the subjects the logged-in user personally teaches), with the usual
searchbar facet to remove it and see everything - same pattern already used elsewhere (e.g.
Communications). A second default filter, "Show only current course", limits it to the current
academic year; removing its facet reaches every other year's plannings.

## Grading ponderations now belong to an academic year:
Grading ponderations (internal/external split and per-outcome weighting) used to be a single,
timeless configuration per study+subject, shared by every academic year past and future. They
now belong to a specific course, so a change made this year no longer silently rewrites how
grades were computed in previous years. Existing configuration was automatically replicated
across every course up to and including the current one, so nothing already recorded changes
meaning. Moving to a new academic year now also copies the previous year's ponderations forward
automatically as part of the course transition. The planning form shows its course (read-only,
first field) and now has a chatter that tracks every change to the study, subject, course and
internal/external ponderations.

## Force the internal grade manually to match Esfera:
When correcting a closed academic year's grades, the internal grade ("Nota del centre") can now
be typed in directly instead of always being calculated from the learning outcomes - useful when
Esfera's official record differs slightly (typically a rounding difference) from what the
outcome-based calculation gives. The review screen shows the calculated grade, the grade that
will actually be applied, and the final grade side by side on one row - the same
calculated/applied shape already used for each learning outcome's own grade - so typing a
different value into the applied field is all it takes, no separate checkbox involved. The final
grade is still recalculated automatically from whichever value is in force, and the correction
can never flip whether the subject is actually passed - only the exact number can be adjusted,
never the pass/fail outcome the learning outcomes already determine.

# Fixes

## Head of Studies / Deputy could not see every planning:
Head of Studies and Deputy Head of Studies only inherited the teacher-scoped `ir.rule` on
`ems.planning`/`ems.planning_outcome`, so they only saw plannings for subjects they personally
teach via `ems.teaching` - not every planning in the centre, as their role requires. Added a
dedicated rule (and matching `ir.model.access.csv` rows) granting them read/write/create over
every planning, with unlink still reserved to `academic_admin`.

## Grade correction could use the wrong year's ponderations:
Correcting or completing a closed academic year's grades could silently pick up today's grading
ponderations instead of the ones that were actually in force during that year, since
ponderations were never tied to a specific course before (see above). Both the correction wizard
and the live grading screen now use the ponderation of their own course.

## A centre's own ponderation edits could be silently undone on the next update:
Rebalancing a module's grading weights through the app (e.g. after a new learning outcome was
added to the curriculum) could be silently reverted by the next update, since the centre's
seeded ponderation data was being treated as configuration this repository keeps re-pushing
rather than a one-time starting template. It's now protected the same way a group's classroom
assignment already is, so an edit made through the app stays in place.

## One module's grading ponderations summed to 106%, not 100%:
Five plannings for the same module ("MP 1665: Digitalització aplicada als sectors productius")
had grading weights across their learning outcomes that added up to 106% instead of 100%, dating
back to an outcome added to the curriculum without its weight being reconciled against the
others. Corrected to the intended split (15/20/15/20/15/15 across its six learning outcomes).
