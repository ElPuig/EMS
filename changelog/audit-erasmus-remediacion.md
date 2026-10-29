# Breaking changes

## Erasmus+ workflow fields only change through the actions (audit R-25):
- Every stored read-only field of the Erasmus+ models, plus their state, is written only by EMS's own actions as superuser (`models/erasmus/workflow.py`): a direct write or create by any user, through the UI or RPC, is refused with an access error. Covers calls, applications (frozen average and conduct warnings, who checked what), resolutions, claims, interviews and plan ratings, mobilities (state, destination, proposal decision, commitment letter signatures), group mobilities and participants.
- The context keys `ems_erasmus_state`, `ems_erasmus_payment_state` and `ems_erasmus_publish` no longer open anything: a client could send them with any RPC call and publish a resolution, mark a payment paid without the Secretary, forge a family's acceptance or close a group mobility as its leader. Internal writes use `sudo()` after their own checks.

# What's new

## Erasmus+ signatures ticked per signer (audit D-1):
- Every line of a document someone signs outside EMS has one signature per signer the call document asks for (participant, legal guardian for minors only, Director, Erasmus coordinator, centre's tutor, host entity). The team (and, for a group mobility, its leader) ticks each one from *Signatures* when it is on the uploaded copy; EMS keeps who ticked it and when, in the record's chatter, and the portal shows each signer's state read only. A document is only marked valid once every required signature is ticked. Not an electronic signature; the commitment letter keeps its click acceptance.

## Erasmus+ EU Survey on individual mobilities, as on group ones (audit D-8):
- Each mobility has its EU Survey status (pending, answered, validated) and deadline (30 days after the end of the stay by default). Once the stay is over the portal asks the participant to answer it and they mark it answered; the team validates it. It replaces the checklist step "Final report (EU Survey)" in new calls. The state and its actions are a mixin shared with group mobilities (`ems.erasmus.eu.survey`).

## Erasmus+ individual tie draw run by EMS (audit D-13):
- *Actions > Draw the ties* on the call (Erasmus coordinator, before the definitive resolution) orders each tied set at random with a secure generator and keeps an immutable draw record, the same model as the group mobilities'. `draw_order` is now read only.

## Erasmus+ projects tell the coordination when the keeping period is over (audit D-12):
- A daily job gives the Erasmus coordinators a task, once per project, when its documents are past their keeping date and not on hold for an audit. Nothing is deleted automatically.

# Changes

## Closing an individual Erasmus+ mobility needs the whole record (audit D-5):
- Besides the return documents, closing now needs everything before leaving, the mobility on a project, the EU Survey validated and nothing left to pay (no payment or invoice to pay, the final payment requested and transferred). Closing frees a graduate's portal, so it waits for the last payment.

## Undoing an Erasmus+ transfer asks for a reason (audit D-18):
- *Undo: not paid yet* opens a wizard with a required reason, kept in the payment's or invoice's history with who undid it, when it had been paid and its receipts.

## Erasmus+ files and project documents (audit D-2):
- A file uploaded by mistake to a document not valid yet is removed with *Remove a file* and a required reason: the file stays attached to the record's history with who removed it and when. Any other removal is refused.
- A project document with files cannot be deleted.

## Head of Studies sees the Erasmus+ total score only (audit D-14, D-4):
- Criteria A, B, C, E and F of the student applications and resolution lines are now for the Erasmus team only, as D already was; the total and the rank stay visible. The declared fewer-opportunities box is hidden from them too; conduct warnings and exclusion reasons stay visible.

## Cancelled and withdrawn Erasmus+ records with evidence go in the project export (audit D-17):
- A cancelled mobility or group mobility, or a withdrawn group participant, with a payment made or a document validated or signed, goes in complete under `99_Cancellades_i_retirades/`; the others stay listed as excluded.

## Every download of the Erasmus+ participants' spreadsheet is logged (audit D-10):
- Each download is an export log line (who, when, how many people) and a message in the call's or group mobility's chatter.

## Community > Groups menu hidden from the Erasmus technician (audit D-6):
- Only the roles that work with the groups see it; the technician read it only to pick a group mobility's groups, and its form failed for them.

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

## Tests for the Erasmus+ audit decisions of 2026-10-29:
- `tests/test_erasmus_decisions.py`: one test per decision (access, records, group and draw cases); the audit addon's H-2 hypothesis now records the refusal. Existing tests tick the signatures before validating and undo transfers through the wizard.
