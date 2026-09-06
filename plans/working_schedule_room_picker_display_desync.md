# Room-picker AutoComplete display/data desync in the working-schedules import wizard

**Status: current, not yet fixed.** Found live 2026-09-06 while helping the developer debug a
real "merge mode" import stuck on the "File conflicts" screen with `Continue` disabled despite
a full manual review finding nothing wrong.

## What was found

On `ems_grouped_conflict_lines_field` (`static/src/js/backend/grouped_conflict_lines_field.js`),
the two `AutoComplete` room pickers shown for a `reassign_rooms` row (`left_space_id`/
`right_space_id`) can end up **displaying two different-looking classroom names while the
underlying record data for both fields is actually identical** (still the untouched default
room both fields are pre-filled with at line-creation time). Confirmed on a real 66-row "Room
conflict" card: 7 rows visually looked fully resolved (distinct-looking aula text on both
sides) but `_resolution_is_valid()`'s equivalent check on the real client-side record data
(`left_space_id[0] !== right_space_id[0]`) failed for all 7 - both still `[59, "Aula 2.17
(2.17)"]`.

**Confirmed NOT the cause:** the widget's own record-loading (`_ensureAllRecordsLoaded`,
already fixed 2026-08-11 for the >80/>1000 row pagination bug) - all 100 rows were genuinely
loaded (`list.count` matched). Not a stale/missing-record problem.

**Suspected root cause** (not yet confirmed by a minimal repro, only by reading
`@web/core/autocomplete/autocomplete.js`): `AutoComplete.onWillUpdateProps` only syncs the
visible `<input>` text from a new `value` prop when `this.inEdition` is `false`:

```js
onWillUpdateProps((nextProps) => {
    if (this.props.value !== nextProps.value || this.forceValFromProp) {
        this.forceValFromProp = false;
        if (!this.inEdition) {
            this.state.value = nextProps.value;
            this.inputRef.el.value = nextProps.value;
        }
        this.close();
    }
});
```

`inEdition` is set `true` on `onInput` (any keystroke/typing) and only reset `false` in
`selectOption()` or `onInputBlur()`. `selectOption()` itself calls `this.props.onSelect(...)`
(here, `EmsGroupedConflictLinesField.onSpaceSelect` → `record.update(...)`) **without awaiting
it** - the actual field write is an async onchange round-trip. If the input re-enters
`inEdition` (e.g. the user clicks/types into it again) before that round-trip's resulting new
`value` prop arrives, the prop update is silently dropped and the input keeps showing stale
text that no longer matches `record.data`. With ~66 near-identical rows (same two teachers/
subjects, only the weekday differs) in one subgroup, this kind of rapid, repetitive editing is
exactly the scenario likely to trigger it. Not yet proven with a deliberate repro - worth doing
before attempting a fix, since the real cause could instead be something specific to how two
`AutoComplete` instances share very similar surrounding markup within the same row.

## Why this matters

This is worse than a merely-missing visual cue (which is what the "color the row by validity"
UX request below already addresses) - the row's own displayed text was actively **wrong**,
telling the user their pick was fine when it wasn't. Diagnosing it required bypassing the DOM
entirely and reading the real OWL component/record data via `window.__OWL_DEVTOOLS__.apps`
(Owl's own official devtools hook, confirmed present in this Odoo version's bundled
`owl.js`) - a DOM-based check (reading `<input>.value`) cannot distinguish "genuinely resolved"
from "displays stale text that no longer matches the record."

## Related, still-pending UX requests from the same session (not yet implemented)

1. **Color-code each conflict row by whether it currently passes the same validity check
   `_resolution_is_valid()` runs server-side** (client-side mirror already exists in the widget
   as `allowedResolutionsByKind` + the `reassign_rooms` room-equality check - see the diagnostic
   script used to find this bug for the exact logic to reuse). Would have caught this exact
   desync (or at least the underlying invalidity) immediately instead of requiring OWL
   devtools archaeology to find it. Developer-requested 2026-09-06.
2. **Show the class-group name (e.g. "AD1A"/"AD1B") directly next to each classroom value**, not
   to reorder left/right (developer explicitly chose to keep left = this card's own subgroup
   teacher, right = the counterpart - confirmed via AskUserQuestion 2026-09-06) but purely so a
   room value that legitimately differs row-to-row (because the same teacher teaches two
   different groups in two different rooms) reads as obviously explained rather than arbitrary.

## How to apply

Before implementing either of the two UX items above, first write a deliberate repro test for
the display/data desync itself (a tour that rapidly edits two AutoComplete pickers within the
same subgroup, asserting the DOM text actually matches `record.data` after each edit) so a fix
can be verified, not just assumed. Do this as a normal Red/Green/Refactor cycle per this repo's
Development workflow - `docs/en/developers/employees/working_schedule.md`'s grouped-conflict-
lines section is the right place to document whatever the confirmed root cause and fix turn out
to be.

Do not touch this on this branch while the developer's own live import is still open with
unsaved progress (`./upgrade.sh` restarts the Odoo service, which would lose it) - wait for
confirmation the wizard has been closed/completed first.
