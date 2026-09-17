# Fixes:

## Student form missing three EMS cog-menu actions:
- The student form's cog ⚙ menu was missing "Portal access (students/families)", "Send authorizations" and "Download Google credentials" - all three were reachable from the students list but not from a single student's own form, even though their underlying logic already worked fine on one record.
- Root cause: their `ir.actions.server` bindings had `binding_view_types` hand-restricted to `list` only. Changed to `list,form` (Odoo's own default) for all three.
- Audited the whole project for the same gap via a DB query cross-referencing `binding_model_id`: these were the only 3 EMS-added action bindings affected.
- Added tour coverage opening each action from the student's own form, not just the list.

## Catalan translation typo ("Correu electrìnic"):
- Fixed a wrong accent in the shared Catalan translation for the "Email" label, affecting several fields at once (including the portal access wizard's recipient email column).

# Internal changes:

## New coding standard: EMS actions must be reachable from both list and form:
- Documented in CLAUDE.md that any action EMS itself adds and binds to a model must declare `binding_view_types` as `list,form`, so this doesn't regress for future actions. Native Odoo and third-party/OCA module actions are left untouched, as before.
