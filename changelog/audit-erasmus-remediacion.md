# Breaking changes

## Erasmus+ workflow fields only change through the actions (audit R-25):
- Every stored read-only field of the Erasmus+ models, plus their state, is written only by EMS's own actions as superuser (`models/erasmus/workflow.py`): a direct write or create by any user, through the UI or RPC, is refused with an access error. Covers calls, applications (frozen average and conduct warnings, who checked what), resolutions, claims, interviews and plan ratings, mobilities (state, destination, proposal decision, commitment letter signatures), group mobilities and participants.
- The context keys `ems_erasmus_state`, `ems_erasmus_payment_state` and `ems_erasmus_publish` no longer open anything: a client could send them with any RPC call and publish a resolution, mark a payment paid without the Secretary, forge a family's acceptance or close a group mobility as its leader. Internal writes use `sudo()` after their own checks.

# Fixes

## Erasmus+ evidence is never deleted (audit R-01, R-10):
- A document line with a file or valid, and any application, mobility, group mobility or participant holding one (or a signature, an earlier letter version, a payment, a self-assessment, an enrolment, a draw or a follow-up entry) can no longer be deleted, also through a database cascade from its parent. A submitted interview or plan rating cannot be deleted either.
- The file of a valid document, of a closed record or a paid transfer's receipt can no longer be deleted, overwritten or moved to another record directly on `ir.attachment`.

## Archived records stay in the Erasmus+ exports, and nothing is left out silently (audit R-02):
- Archived mobilities, group mobilities and participants are exported and counted, their index rows marked "Archived". Cancelled mobilities, group mobilities in draft or cancelled and withdrawn participants get an index row and an entry in the manifest's new `excluded` list.

## Head of Studies only reads Erasmus+ records, whatever other role they hold:
- Their record rules are read only: combined with the group teacher role, the previous write-all rule let a Head of Studies who teaches in a group mobility change any individual record's documents or any group's follow-up.

## Erasmus+ payments: undoing a transfer keeps its trace, and no duplicate first payment (audit R-24, R-13):
- Undoing a transfer posts who undid it, when it had been paid and by whom, with its receipts attached; the payment and invoice state is tracked. A paid invoice cannot change.
- A unique index keeps one first payment and one final payment per mobility: two requests at the same moment created two prefinancings. A payment is only requested for a mobility in preparation or closed.

## Own destination proposals refuse the files every other upload refuses (audit R-11):
- The host's written commitment goes through the same upload check (no HTML, SVG, scripts or programs).

# Internal changes

## Regression tests and audit probes for the Erasmus+ audit remediation:
- `tests/test_erasmus_integrity.py`: 21 tests, including a real JSON-RPC call with a forged context and the combined-roles cases. Of the first 20, 18 failed on the audited code; the 2 about roles taken away (a reassigned evaluator, a replaced leader) already passed and stay as guards. The upload check of proposals was added afterwards.
- `TestGuardDutyBoard.test_report_guard_duty_board_marks_a_wc_guard` now checks the "(WC)" marker inside each teacher's own badge: its fixed 200-byte window reached the next badge, another teacher's WC guard, on databases with real schedules for the same period.
- Audit annexes: hypotheses probe (`test_audit_hypotheses.py`), two-transaction concurrency probe and a guard duty board ordering probe, all under `docs/auditoria-erasmus/anexos/`.
