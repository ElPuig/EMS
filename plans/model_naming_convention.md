Status: PROPOSAL ONLY (2026-08-11) - raised by the developer while mid-implementation of
`plans/calendar_driven_attendance_templates.md`, comparing native `resource.calendar`/
`resource.calendar.attendance` (dot-separated) against EMS's own `ems.attendance_template`/
`ems.attendance_schedule` (underscore-joined). Nothing renamed yet - this file exists purely to
capture the standard, the concrete rename proposal, and (most importantly) the real migration
mechanics/risk, researched and verified against this box's actual installed Odoo 18 source before
any renaming is attempted. Re-verify against the current code before starting, since this plan may
go stale.

# The actual standard (grounded in Odoo core, not a literal quoted doc rule)

Odoo's own coding-guidelines page (https://www.odoo.com/documentation/18.0/contributing/
development/coding_guidelines.html) was checked before writing this - its fetchable content
covers file/directory naming (`_views.xml`, `_demo.xml`...) but the specific "dot vs underscore in
`_name`" rule did not come through in a fetchable form (the page's relevant section did not surface
in the tool's HTML→text conversion). The standard below is instead grounded in **observed,
consistent practice across core Odoo modules** - the same way this project's own "Odoo way first"
rule is normally applied when no single doc paragraph spells something out verbatim:

- **A dot (`.`) marks a genuine one-to-many parent→child relationship between two DIFFERENT
  models** - the child's name is built by appending `.<child_concept>` to the parent's own full
  name. Examples: `resource.calendar` → `resource.calendar.attendance`; `sale.order` →
  `sale.order.line`; `account.move` → `account.move.line`; `pos.order` → `pos.order.line`.
  Odoo does NOT always chain the FULL ancestor path for a 3+-level-deep hierarchy, though -
  `stock.move` belongs to `stock.picking` (via a plain `picking_id` FK) but is `stock.move`, not
  `stock.picking.move`; only `stock.move`'s OWN direct child chains onto IT (`stock.move.line`).
  Judgment call per level, not a mechanical "always prepend every ancestor" rule.
- **An underscore joins words WITHIN one indivisible compound concept** that isn't itself a
  parent/child split - e.g. `ir.actions.act_window` (an "action window" is one thing, not
  "action" → "window"), and, already in this codebase, `ems.hex_color_mixin`,
  `ems.non_teaching_type`, `ems.datetime_utils`.
- Wizards in this codebase already lean toward keeping their OWN name underscore-compound
  (`course_transition_wizard`, `em_grading_wizard`, `graduation_wizard`,
  `working_schedules_import_wizard`) while a genuine LINE/CHILD sub-model under one still uses a
  dot for that specific parent→child step (`ems.course_transition_wizard.line`,
  `ems.em_grading_wizard.line`, `ems.graduation_wizard.line`) - this specific pattern (wizard name
  stays underscore-compound, but its own child gets a dot) is worth keeping as-is; it already
  matches the standard above (the wizard name itself is one concept, the line IS a real child).

# EMS already mixes both styles today - full inventory (2026-08-11)

Not just the two attendance models the developer asked about - `grep`ing every `_name = "ems...."`
across `models/` shows the SAME inconsistency module-wide. Dot-separated (already following the
standard above): `ems.authorization` → `.field`/`.response`/`.template`; `ems.contact.relation.wizard`;
`ems.course_transition_wizard.line`; `ems.em_grading_wizard.line`/`.student`;
`ems.enrollment_view`(underscore, not this family); `ems.graduation_wizard.line`; `ems.notice.line`;
`ems.portal.access.wizard`/`.line`; `ems.strike.reason`; `ems.student.benefit`/`.document`/
`.year_record`(`.outcome`/`.subject`); `ems.working_schedules_import_wizard.*` (5 line/mixin
sub-models). Underscore-joined where a dot would arguably fit the standard better (the attendance
family the developer asked about, plus many more): `ems.attendance_template`,
`ems.attendance_schedule`, `ems.attendance_session_header`, `ems.attendance_session_line`,
`ems.attendance_status`, `ems.attendance_correction`, `ems.attendance_issue_tutor`/
`_student`/`_status`, `ems.attendance_justification`, `ems.attendance_report_wizard`,
`ems.limesurvey_header`/`_enrollment`/`_recipient`/`_block`, `ems.grade_session`/
`_outcome_line`/`_subject_line`/`_session_state_wizard`/`_session_wizard`, `ems.non_teaching_type`
(this one genuinely fits underscore - see standard above), `ems.student_import_wizard`,
`ems.student_update_wizard`, and more.

**This means the attendance family isn't a special case worth fixing in isolation** - if the
standard is worth adopting, it's a real, module-wide normalization pass, on the same scale as the
DTON rollout already completed (`project_dton_rollout_roadmap` in memory). Recommend scoping the
FIRST pass to the attendance family alone (since it's already mid-redesign per the calendar-driven
plan, and touching it twice - once for the FK, once for the rename - would be wasted churn if
renamed later instead of now) and treating the rest of the module as a separate, later,
lower-priority normalization pass - confirm this scoping with the developer before starting either.

# Concrete rename proposal for the attendance family

| Current | Proposed | Why |
|---|---|---|
| `ems.attendance_template` | `ems.attendance.template` | top of the domain, no further split needed |
| `ems.attendance_schedule` | `ems.attendance.schedule` | child of template (NOT `.template.schedule` - matches `stock.move`, not `stock.picking.move`, per the "don't always chain the full ancestor path" rule above) |
| `ems.attendance_session_header` | `ems.attendance.session` | `_header` dropped entirely - matches `account.move`/`pos.order`'s own convention: the PARENT record is never suffixed `_header`, only the child gets `.line` |
| `ems.attendance_session_line` | `ems.attendance.session.line` | genuine child of session |
| `ems.attendance_status` | `ems.attendance.status` | a plain lookup table, no further split |
| `ems.attendance_correction` | `ems.attendance.correction` | no further split |
| `ems.attendance_justification` | `ems.attendance.justification` | no further split |
| `ems.attendance_issue_tutor` | `ems.attendance.issue.tutor` | top of a genuine 3-level chain (tutor → student → status), "issue" used as a namespace the same way EMS's own `ems.student.*` family already does without a bare `ems.student` model existing |
| `ems.attendance_issue_student` | `ems.attendance.issue.student` | child of issue.tutor |
| `ems.attendance_issue_status` | `ems.attendance.issue.status` | child of issue.student - NOTE: distinct from `ems.attendance.status` above, an unrelated plain lookup model; keep both names carefully distinguished in code review once this is attempted, easy to eyeball-confuse |
| `ems.attendance_report_wizard` | `ems.attendance.report_wizard` | dot for the domain, underscore kept for "report_wizard" as one compound technical term - matches how other wizards in this codebase keep their own name underscore-compound |
| `ems.attendance_mixin` | left as-is | not a "domain.concept" name at all - a mixin, correctly underscore-compound already (same category as `ems.hex_color_mixin`) |

Every field currently declaring `comodel_name="ems.attendance_template"` (etc.) across the WHOLE
codebase (contacts/, employees/, planning/, grades/, limesurvey/, views/, JS, tests) would need the
literal string updated to match - this is the bulk of the actual line-count in this change, not the
model files themselves.

# Migration mechanics - verified against this box's actual installed Odoo 18 source (2026-08-11)

Read `odoo/addons/base/models/ir_model.py` (`IrModel._reflect_models`/`_update_xmlids`,
`model_xmlid()`) directly on this box before writing anything below - not assumed from memory.

**Genuinely good news: the underlying PostgreSQL table does NOT need to change.** `BaseModel._table`
defaults to `_name.replace('.', '_')` - `'ems.attendance_schedule'` and `'ems.attendance.schedule'`
both collapse to the identical `ems_attendance_schedule` table name. Same for the auto-generated
`ir.model`/`ir.model.fields` xmlids (`model_xmlid()`: `'%s.model_%s' % (module, model_name.replace
('.', '_'))` - also identical either way). No table rename, no column rename, no data-loss risk on
the storage layer itself.

**Real risk: a naive rename (just changing the Python `_name` string and re-running `-u ems`) DOES
NOT self-heal - it silently orphans data.** Traced `IrModel._reflect_models(model_names)`: it
queries for an EXISTING `ir_model` row whose `model` column TEXT value equals the NEW `_name`
string exactly (`select_en(self, ..., model_names)`). Since the DB still has the OLD string, this
query finds nothing, so `upsert_en` INSERTS A BRAND NEW `ir_model` row for the new name - leaving
the OLD row (still `model='ems.attendance_schedule'`) as orphaned garbage, no Python class pointing
at it any more. `_update_xmlids()` is then called for the NEW row using `model_xmlid()` - which,
because dots and underscores collapse identically (see above), computes the EXACT SAME xmlid
string the OLD row already owns (`ems.model_ems_attendance_schedule`) - so the upsert on
`ir_model_data` (keyed by `(module, name)`) REPOINTS that existing xmlid's `res_id` from the OLD
`ir_model` row to the brand new one. Net result: the OLD `ir_model` row becomes a permanently
orphaned, untracked row (no xmlid points to it, `_process_end`'s own removed-xmlid cleanup - see
`CLAUDE.md`'s "Why `__import__`" section - never touches it either, since its own xmlid wasn't
removed, it was repointed elsewhere) - and everything that referenced the OLD model BY NAME
(`ir.model.fields.relation` on every OTHER model's Many2one/One2many/Many2many pointing at this
one, `ir.model.access.model_id`, `ir.rule`, saved filters, report/view `model=` attributes stored
as plain text) keeps pointing at whichever `ir_model.id` it already had - the OLD, now-orphaned
one for most of them, since only the freshly-reflected NEW row gets the xmlid.

**What an actual safe migration needs to do** (not attempted here - this is the shape of the
follow-up work, once this proposal is confirmed): rename `ir_model.model` **in place** (`UPDATE
ir_model SET model = 'ems.attendance.schedule' WHERE model = 'ems.attendance_schedule'`) in a
`pre-migrate.py`, BEFORE the new code's `-u ems` gets to `_reflect_models` - so the reflection step
finds the row ALREADY matching the new name and treats it as unchanged, instead of creating a
duplicate. Also needs: every `ir_model_fields.relation` column (any OTHER model's field pointing at
this one, core Odoo models included if any ever do), any `ir_model_fields.model`/`ir_model.model`
for the model's OWN fields if not already covered by the same rename, `ir.rule`/`ir.actions.*`
domains stored as literal Python-expression text mentioning the old model name (unlikely for this
specific case, but must be checked, not assumed absent), and any real DATA records of the model
itself that carry their own `ir_model_data` xmlid (own `model` column on THAT `ir_model_data` row,
separate from the `ir_model`-describing one). **`openupgradelib`'s `rename_models()` helper
(OCA/openupgradelib, widely used across the Odoo ecosystem specifically for this) already
implements this whole dance correctly and should be evaluated/used rather than hand-rolling every
edge case from scratch** - check whether it's already available/installable in this environment
before deciding to replicate its logic by hand.

# Full module-wide scope (developer's own request, 2026-08-11: "revisaría todo el alcance para
dejar un plan a futuro preparado" - applying only to attendance now, but wants the rest surveyed
so a future pass has a ready-made plan instead of starting from zero)

Every `ems.*` model, categorized. "No change" entries are already correct under the standard above
(dotted where there's a real parent-child relationship, or correctly a single compound concept) -
listed so a future pass doesn't have to re-derive that they were already checked and are fine.

**Already dotted, no change needed:** `ems.authorization` → `.field`/`.response`/`.template`;
`ems.contact.relation.wizard`; `ems.course_transition_wizard.line`; `ems.em_grading_wizard.line`/
`.student`; `ems.graduation_wizard.line`; `ems.notice.line`; `ems.portal.access.wizard`/`.line`;
`ems.strike.reason`; `ems.student.benefit`/`.document`/`.year_record`(`.outcome`/`.subject`);
`ems.working_schedules_import_wizard.*` (6 line/mixin sub-models).

**Single compound concept or standalone curriculum/domain word, correctly underscore or bare
already, no change needed:** `ems.applicant_import_wizard`, `ems.attendance_mixin`, `ems.base`,
`ems.course_transition_wizard`/`ems.em_grading_wizard`/`ems.graduation_wizard`/
`ems.grade_session_wizard`/`ems.grade_session_state_wizard`/`ems.grade_import_wizard`/
`ems.enrollment_proposal_wizard`/`ems.student_import_wizard`/`ems.student_update_wizard`/
`ems.withdrawal_wizard`/`ems.working_schedules_import_wizard` (every wizard's OWN top-level name -
matches the established "wizard name stays one compound concept" pattern), `ems.csv_column`,
`ems.datetime_utils`, `ems.hex_color_mixin`, `ems.multithreading`, `ems.schedule_report_mixin`,
`ems.non_teaching_type`, `ems.space_type`, and every bare single-word curriculum/domain model
already fine as-is (`ems.level`, `ems.study`, `ems.subject`, `ems.content`, `ems.criteria`,
`ems.outcome`, `ems.tracking`, `ems.course`, `ems.group`, `ems.space`, `ems.role`, `ems.workgroup`,
`ems.minute`, `ems.teaching`, `ems.enrollment`, `ems.planning`, `ems.planning_outcome`) - these are
independent top-level concepts cross-referenced by FK/M2M, not cascade-owned children of each
other, so there's no hierarchy to express with a dot in the first place.

**Genuine parent-child families found (verified via `ondelete="cascade"` Many2one, not guessed from
the name alone) - real candidates for a future rename pass, same treatment as the attendance family:**

| Family | Current | Proposed |
|---|---|---|
| Attendance (this pass) | see table above | see table above |
| Grades | `ems.grade_session` (parent) | `ems.grade.session` |
| | `ems.grade_outcome_line` (child, `grade_session_id` cascade) | `ems.grade.session.outcome_line` |
| | `ems.grade_subject_line` (child, `grade_session_id` cascade) | `ems.grade.session.subject_line` |
| Limesurvey | `ems.limesurvey_header` (top) | `ems.limesurvey.header` |
| | `ems.limesurvey_block` (child of header) | `ems.limesurvey.block` |
| | `ems.limesurvey_recipient` (child of header) | `ems.limesurvey.recipient` |
| | `ems.limesurvey_enrollment` (child of recipient, cascade) | `ems.limesurvey.enrollment` |

Limesurvey deliberately does NOT chain the full ancestor path (`.header.recipient.enrollment`) -
same "domain-level prefix, not full ancestor chaining" choice already made for `ems.attendance_issue_*`
above and matching this codebase's own existing `ems.student.*` family (benefit/document/year_record
sit directly under the `student` domain, not chained through a nonexistent `ems.student` parent
record). Only a tight, single-level "detail line of THIS specific parent" pair (e.g. `grade.session`
→ `.outcome_line`, matching `account.move.line`) chains directly onto its immediate parent's own
full name.

**Not checked in this pass (lower priority, or genuinely ambiguous without a closer read) -
flag for whoever picks up the future module-wide pass rather than guessing now:** `ems.enrollment_view`
(possibly a SQL-view variant of `ems.enrollment` - `.view` suffix might already be the right call,
or might deserve folding into `ems.enrollment.view` for consistency - not verified), `ems.job`,
`ems.user`, `ems.department` (if these exist as EMS's own models rather than `hr.*` extensions -
not verified in this pass), `ems.strike`/`ems.strike_reason_other` (check whether `strike_reason_other`
is a real second model or just a field name - not verified).

# Recommendation on timing (developer's own question, 2026-08-11): before or after phases 1-3?

**Recommend AFTER finishing the remaining phases 1-3 of `plans/calendar_driven_attendance_templates.md`**,
as the closing Normalize step for the whole `#372` issue, not before. Reasoning:

1. **The model shape isn't settled yet.** Phases 1-3 still have open, unresolved design questions
   (permissions for point 1, the M2M uniqueness algorithm for point 2, the write-order restructuring
   for point 3's own locking mechanism). Renaming now means renaming a model that's about to change
   shape again shortly after - a moving target, not the stable end-state a rename should target.
2. **Already-completed, tested work would need re-verifying for no functional reason.** Phase 4 (the
   FK) just passed 331 tests across 8 classes. Renaming now means re-running every one of those
   again purely to confirm the rename itself didn't break anything - overhead with zero functional
   benefit, since that same re-verification is needed regardless of WHEN the rename happens. Doing
   it once, at the very end, means paying that verification cost exactly once instead of twice.
3. **Isolates risk.** The rename is a mechanical, wide-blast-radius, cross-cutting change (every
   `comodel_name`/`env['...']`/XML `model=` reference, plus the `ir_model`/`ir_model_fields`
   migration mechanics documented above) - genuinely unrelated in KIND to the remaining functional
   work (moving `student_ids`, a uniqueness constraint, locking manual creation). Mixing a risky
   structural rename with active feature changes on the SAME models makes it harder to bisect a
   regression to "the rename" vs. "the new business logic" if something breaks.
4. **Matches this repo's own established methodology.** The Development workflow's own "Normalize"
   (N) step is explicitly the LAST step of a cycle, applied to what's already built and tested - not
   a prerequisite gate before functional work starts. The original DTON rollout followed the same
   order project-wide (`project_dton_rollout_roadmap` in memory): build/test first, normalize after.
5. **The "avoid touching the same lines twice" concern (raised when this plan file was first
   written) is weaker than it first looked.** Phases 1-3 mostly ADD new code (new fields, a new
   constraint, permission changes) rather than rewriting most of the EXISTING lines in
   `attendance_template.py`/`attendance_schedule.py` - the model-NAME STRING itself is a trivial,
   uniform find-and-replace across whatever the final file state is, so doing it once at the end
   costs roughly the same as doing it twice across two smaller windows, without the added
   coordination cost of tracking a rename mid-flight through unfinished, still-changing code.

**The full-scope audit above (grades/limesurvey families, the categorization of every other model)
carries none of this risk** - it's pure research/documentation, not a code change, so there's no
reason to wait on doing THAT part; it's already done, in this same file, ready for whenever a future
session picks it up.

# Recommendation for whoever picks this up

This is a genuine, worthwhile normalization - EMS's own naming is already inconsistent regardless
of whether this specific proposal is adopted, so doing nothing isn't "staying consistent" either.
But it's a real migration risk class (Odoo's own ecosystem needed a dedicated library for exactly
this), not a quick find-and-replace, and every `comodel_name`/`env['...']`/XML `model=` reference
across the whole codebase needs updating regardless of the migration script's own correctness.
Confirm with the developer: (1) scope - attendance family only for now, vs. full module-wide; (2)
whether `openupgradelib` is acceptable as a new dependency for the migration script, or whether the
rename logic should be replicated by hand; (3) timing relative to
`plans/calendar_driven_attendance_templates.md`'s own remaining phases (1-3) - doing the rename
BEFORE finishing that plan means less code touches the old names only to be renamed again shortly
after; doing it AFTER means the calendar-driven plan's own remaining work doesn't have to dodge a
second concurrent renaming effort.
