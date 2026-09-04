# Fixes

## The working-schedules "Import planner data" cogwheel entry was invisible outside English:

`ImportPlannerCogMenuItem.isDisplayed` (`static/src/js/backend/import_planner_cog_menu.js`) gated
visibility on `config.actionName === "Working Schedules"` - a plain string comparison against the
act_window's own translated display name. Odoo translates `ir.actions.act_window.name`
per-user-language, so this only ever matched when the current user's UI language was English;
in `ca_ES`/`es_ES` the action's name arrives already translated and the comparison silently
always failed, hiding the whole cog entry (developer report 2026-09-04, mid-investigation of
issue #398).

Fixed to match by the menu's own xmlid (`ems.menu_work_locations`) resolved via
`env.services.menu.getAll()`, the same language-independent pattern already used by
`ImportStudentCogMenu`/`ImportGedacCogMenu` in this module - never compare UI code against a
translatable string. Verified via a clean `./upgrade.sh` (no errors/warnings); no automated test
added yet for the language-specific regression itself (the existing
`working_schedules_import_wizard_tour.js` runs the admin user in its default `en_US`, so it never
exercised the broken branch) - worth a follow-up if this class of cog-menu bug recurs.

## Issue #398 ("wrong group shown on collision") investigated, not reproduced:

Walked a real (anonymized/corrected) planner XML through the working-schedules import wizard to
the "internal_conflicts" screen and cross-checked every single reported collision line (~90
lines across co-teaching, split-session and room-conflict kinds) against the source file's actual
per-teacher/day/hour data, accounting for the developer's own manual corrections made in the
wizard (group renames, a couple of subject/group mismatches). Every line's displayed group
matched the source exactly - no mismatch found anywhere in `_entry_label`/`_find_internal_
conflicts`/`_classify_conflict_kind` (`models/employees/working_schedule.py`). Most likely
explanation per the developer's own account: a late-night misread of a group label, not a real
bug. Leaving the issue open for the developer to close or reopen with a fresh repro if it
resurfaces - no code change was made for this part, only the cogwheel fix above landed.
