# Changes

## Split-group halves can keep their own tutor and representatives:

- Issue #688. Since #676 the two halves of a split group ("Joins with") always shared their tutor, delegate and sub-delegate: linking them, or later changing one on either half, overwrote the other half's. Co-tutors or a delegate per half were impossible.
- Now the server only ever fills blanks: a half takes the other half's tutor, delegate or sub-delegate only where it has none, on linking and on any later change (`_mirror_joinable_groups()`, `_fill_joinable_blanks()`).
- When a save would replace a value the other half already has (linking a half with a different one, or changing a shared value), the group form asks: "Replicate" gives the other half the same one (`action_replicate_joinable_fields()`, called after saving with the `[half, field]` pairs `get_joinable_confirmation_message()` returned), "Keep each half's own" saves without touching it, and closing the dialog does not save. A difference already there (an existing co-tutor) is not asked about again unless that value changes.
- Tests in `TestGroup` (blanks only on link and on change, replicate only what was asked, when the form asks) and the `ems_group_joins_with` tour updated (keep on link, delegate filled without asking, replicate a new tutor). Admin manual (ca/es/en), developer doc and translations updated.
