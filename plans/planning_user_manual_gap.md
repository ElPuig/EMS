# `ems.planning` (grading ponderations) has no user manual page at all

**Status: current, found 2026-09-23, NOT written.** Pre-existing gap, not introduced by issue
#503 — surfaced while doing that issue's own Close step (docs/i18n).

## What's missing

No `docs/{en,ca,es}/<role>/*.md` page documents the "Plannings" screen
(`ems.planning`/`ems.planning_outcome` — internal/external grading ponderation config per
study+subject+course) at all. `docs/{en,ca,es}/admin/curriculum-subjects.md` and
`curriculum-studies.md` don't mention it either, despite covering closely related curriculum
screens.

## Why this surfaced now

Issue #503 changed this screen meaningfully (HOS/DHOS can now see and edit every planning, not
just their own taught subjects' - `plans/planning_course_link.md` phase 1; plannings are now
course-scoped and roll forward automatically at course transition - phase 2) and per this
project's own Development workflow, a change like this should come with a user-doc Close step.
Writing that properly would mean creating the FIRST-EVER manual page for this screen from
scratch (in `admin` and `head_of_studies`, trilingual) - a bigger, adjacent-scope undertaking
than issue #503's own 4 requirements, so it was deliberately deferred rather than rushed through
during that issue's own overnight session.

## What's needed

A new `docs/{en,ca,es}/admin/planning.md` (or folded into `curriculum-subjects.md` as a new
section - whichever the developer prefers) covering:
- What a planning is (internal/external ponderation split, per learning outcome breakdown).
- That it's now scoped per academic year (issue #503) and rolls forward automatically when a
  course transitions, with a manual admin/HOS-editable copy at each yearly checkpoint.
- The "Show only mine"/"Taught by me" filter on the list.
- HOS/DHOS's now-centre-wide read/write access (mention in a `head_of_studies`-facing page too,
  or a cross-reference if the admin page is the canonical one).

## How to apply

Bring this up with the developer before writing it — ask whether it belongs as its own page or
as a section of an existing curriculum doc, and confirm the split between `admin`/
`head_of_studies` content before drafting three languages' worth of prose and (if the screen
warrants one) a screenshot.
