# What's new

## Enrollment course selector in Settings:

`is_enrollment_default` had no UI path at all — it could only be changed by editing
`data/custom/ems.course.csv` and running an upgrade, or by SQL — which is what made it
unrecoverable when the transition used to clear it.

**Settings → EMS Management → Course Management Settings** now has an **Enrollment course**
selector next to the existing "Current course" one, built as its exact mirror:
`res.company.enrollment_course_id` with a `_sync_enrollment_course_flag()` that keeps
`ems.course.is_enrollment_default` in step, the same way `current_course_id` keeps `is_current`.

Moving the mark is a single action even though it is unipersonal: the sync clears the previous
course before setting the new one, so the operator never trips over the `@api.constrains` that
otherwise required an untick-then-tick dance.

`ems.course` still has no action or menu, on purpose — a second screen would be a second way in,
and an editable flag on a list bypasses the sync entirely. Its list and form views exist only to
serve the selectors ("Search more…" and "Create and edit…", the latter being the only way to
create a new academic year from the UI), with both flags readonly.

## Progress overlay on the grade wizards:

Creating the evaluation sessions of a round (232 sessions and ~24.000 grade lines at this
centre) and importing an Esfer@ file (minutes, several thousand rows) both ran behind nothing
but Odoo's small "Loading" pill, so the operator had no way of telling a long run from a frozen
screen. It looked hung repeatedly during the rehearsal.

The blocking overlay the course transition already used now covers **Create sessions**, **Change
evaluation state** and **Import grades** too, each naming the scope the operator has just chosen.
The controller was extracted to `blocking_action_form.js` and is shared by the four wizards
instead of being copied.

No live counter, by design: these run in a single transaction — which is what guarantees a
failure half-way leaves the database untouched — and nothing written inside it is visible until
it commits.

# Fixes

## Browser tours matched on translated text:

Two tours selected elements by their English label (`label:contains('By level')`,
`.o_error_dialog:contains('no gradeable rows')`). Both strings are translated, and this centre
runs in Catalan, so the tours only passed for as long as the `.po` files lagged behind the
code — they were already failing before this branch. They now select by value and by dialog
rather than by text.

Worth a sweep: any tour keyed on a translatable string is a green test waiting to break the day
someone translates it.

## Transition preview reports the students no run can see:

`_scope_students()` captures the scope through `main_group_id`, so an active student without
one belongs to **no run at all**, whatever studies are picked: step 0 freezes no academic
history for them and step 8 cleans nothing. The wizard hid that instead of surfacing it.

The preview now warns about them, listed by name, with its own counter. `study_id` is what
tells them apart from the hundreds of students a run legitimately leaves group-less:
`_apply_detach_unplaced()` keeps it on purpose when detaching, so **no group and no study**
means nobody ever placed them. Measured right after the rehearsal's full transition: 646
detached students (0 attendance lines, 653 year records) against 8 orphans holding 197
attendance lines and no academic record at all.

Warning, not blocker — the run is not unsafe and fixing the data is the operator's call. But
the transition is the last moment it is fixable, because afterwards the two groups are
indistinguishable.

## Transition preview no longer promises placements the apply does not make:

`_build_lines()` classified every student from the enrollments of the incoming course
regardless of study, while `_apply_placement()` only executes the ones whose study is in the
current run. A student holding a confirmed enrollment into a study **outside** the run was
therefore previewed as `place` — "Joins its group for the next course" — and then detached
instead, its placement left to that study's own run.

The destination group was already withheld in that case; the label was not, and the audit CSV
inherits the label. That CSV is the reference for undoing a case by hand, so it has to be
literally true. These lines are now a distinct action, **`place_later`** ("Joins when its own
study transitions"), with its own counter in the preview panel. `graduate_continue` keeps its
label — those students do graduate, only the placement is deferred.

Reproduced twice during the first full rehearsal: transitioning ESO/BTX/AO first listed 17
students as `place`, and all 17 finished the run with no group.

## Course transition no longer clears the enrollment default (September enrollments):

The global flip cleared `is_enrollment_default` on the incoming course, on the reasoning
that the running course is nobody's "next course" any more. Enrollments keep being
processed all through September for the course that has just started, so this left **no
course flagged at all**.

The flag is not merely a default value: `enrollment.py`, `enrollment_proposal_wizard`,
`graduation_wizard._next_course()`, `res.partner._compute_transition_status()` and
`year_record._academic_result()` all resolve "the enrollment course" with the same
`search([('is_enrollment_default', '=', True)], limit=1)`. After the flip every one of
them got an empty recordset, which among other things stopped the "students without
destination" report from working — with no UI to put the flag back.

The incoming course now keeps both `is_current` and `is_enrollment_default`. Opening the
following year's campaign becomes a deliberate act instead of a side effect of the
transition.

The same flag was also being reverted from the other side: `is_enrollment_default` was a
synced column of `data/custom/ems.course.csv`, so **every upgrade reapplied the value in
the file**. Moving the flag on to open the following year's campaign would have been
silently undone on the next deploy, and new enrollments would have started landing on the
wrong course. It is live application state, not configuration — exactly the carve-out
CLAUDE.md describes — so the column is gone from the file, and the initial value is now
seeded once by `ems.course._ems_seed_enrollment_default()`, called from `post_init_hook`
(fresh installs) and from the 18.0.0.22.0 post-migrate (existing ones). The helper only
acts when no course carries the flag, so it can never override a deliberate move.

Found during the first end-to-end rehearsal of the transition on a production copy.
