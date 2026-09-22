# Fixes

## Head of Studies / Deputy could not see every planning:
Head of Studies and Deputy Head of Studies only inherited the teacher-scoped `ir.rule` on
`ems.planning`/`ems.planning_outcome`, so they only saw plannings for subjects they personally
teach via `ems.teaching` - not every planning in the centre, as their role requires. Added a
dedicated rule (and matching `ir.model.access.csv` rows) granting them read/write/create over
every planning, with unlink still reserved to `academic_admin`.

# What's new

## "Show only mine" filter on the Plannings list:
Since Head of Studies/Deputy now see every planning centre-wide, the Plannings list defaults to
"Show only mine" (the subjects the logged-in user personally teaches), with the usual
searchbar facet to remove it and see everything - same pattern already used elsewhere (e.g.
Communications).
