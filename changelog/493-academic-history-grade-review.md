# What's new

## Grade reviews: correcting an academic history after the course is closed:

Once a course is closed, the academic history (`ems.student.year_record` and its subject/outcome children) is a frozen copy and the live grade lines it came from no longer exist — the course transition deletes them. Until now nothing in the UI could touch it: the subjects one2many and both nested forms were `readonly="1"`, so the only editable fields in the whole history were `academic_result` and `title_obtained` at course level. A signed grade review resolving a module could not be registered anywhere.

A new wizard, `ems.grade_review_wizard`, is now the single write path into a closed file, reachable from a "Grade review" button on the year record form. Three operations:

- **Correct a subject** through its learning outcomes (RA): the operator sets the resolved grade of the outcomes the grade review resolves, and the subject's internal grade, state and final grade are recomputed.
- **Add a subject missing from the record**, with its weights and outcomes seeded from the `ems.planning` of the record's study.
- **Remove a subject line** from the record.

The wizard previews the recomputed internal grade, state and final grade before anything is written, and proposes the resulting course result (e.g. *Partially passed* → *Fully passed*) as a pre-checked option — never silently. `title_obtained` stays a manual decision, and `repeating`/`withdrawn` are left untouched since they come from the exit and the destination enrollment, not from the grades.

Real case behind it: a student's *MP 0156 Anglès professional* of 2025-2026 was stored as Not passed (RA3 and RA4 at 4, internal grade capped at 4). A grade review resolved the module as passed with a 5; setting those two outcomes to 5 in the wizard yields internal 5 / passed / final 5, which is exactly what the resolution says.

## Traceability of every grade review:

`ems.student.year_record.subject` gained `review_date`, `review_user_id` and `review_note`, shown on the record's subjects list and on the subject's own form, plus a "Corrected by a grade review" filter on the academic history search view. Those keep the **last** grade review applied to a subject; the full sequence is auditable in the student's chatter, where each grade review posts a note (via `_message_log`, so no email address is needed on whoever signed it) listing every outcome changed with its before → after, the resulting subject state and, when it changed, the course result.

# Changes

## Head of Studies and Director may now write on the academic history:

They were read-only on `ems.student.year_record` and its children. Both `ir.model.access` rows and the record rules now grant them write and create, so they can sign a grade review like the secretariat and the academic administration. The secretariat and Head of Studies also gained `unlink` on the subject and outcome lines (needed by the "remove a subject" operation); deleting a whole year record is still admin-only. Teachers stay read-only.

# Internal changes

## The grading formulas are shared with the frozen history instead of duplicated:

The internal-grade rule (weighted average over the scored outcomes, renormalized to their own ponderations, capped at 4 when any of them is below 5) was inlined in `ems.grade_subject_line._compute_internal_score`. It is now `_internal_from_outcomes()`, next to the already shared `_final_from_parts()`, and `ems.student.year_record.subject._values_from_outcomes()` sits on top of both. `_recompute_from_outcomes()` and the wizard's live preview both go through that single helper, so what the operator sees before applying and what gets written cannot diverge, and the live grades and the archived history can never drift apart on the rule itself.

`_recompute_from_outcomes()` also clears `is_overridden`: after a grade review the internal grade is the one its outcomes yield, not a teacher's manual override of them. A subject whose work placement (EM) is still ungraded becomes passed with its final pending, exactly as the freeze would have left it.

## Documentation and tests:

`docs/en/developers/grades/year_record.md` gained a "Grade reviews" section (with the recomputation diagram) and its CRUD/access-control tables were brought back in line with the code — the teacher row still described the pre-#393 tutor-only rule. The secretariat manual gained a step-by-step "Applying a grade review" section in the three languages, and the Head of Studies manual now states they can apply one too. The procedure is called "Revisió de qualificacions" in Catalan and "Revisión de calificaciones" in Spanish. New `tests/test_grade_review.py` (21 tests: the recomputation, the course-result cascade, the pending work placement, the stamping, the chatter log, the three operations and the per-role permissions) and `tests/test_grade_review_tour.py` + its tour, driven as a secretary rather than as admin.
