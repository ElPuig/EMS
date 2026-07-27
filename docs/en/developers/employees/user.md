# Technical Reference: `res.users` (EMS extension)

## Overview

`models/employees/user.py` extends `res.users` with the profile-picture disable switch (`image_disabled`, see [Photo visibility](photo_visibility.md) — already documented and tested) and `_sync_ems_implied_groups()`, a compensating mechanism for a real gap in Odoo's own group-implication system.

**Module file:** `models/employees/user.py`

---

## `_sync_ems_implied_groups()` — revoking what Odoo's own `implied_ids` never revokes

Odoo's native group-implication (`GroupsImplied.write`) is **grant-only**: adding a group automatically grants everything in its `implied_ids`, but removing that group never revokes them again. For EMS's role groups — several of which imply real, consequential native Odoo access (`hr.group_hr_manager`, `sales_team.group_sale_salesman_all_leads`, `base.group_system`, etc. — see `security/groups.xml`) — that means demoting a user (e.g. un-assigning Secretary) would otherwise leave them permanently holding HR Manager access with no way to remove it short of a manual, ad hoc unassignment.

`write()` detects when `groups_id` (or the `sel_groups_*`/`in_group_*` virtual fields the Settings UI uses) is being touched, snapshots each user's groups **before** the write, and afterwards calls `_sync_ems_implied_groups(before)`:

```mermaid
flowchart TD
    A[write vals touches groups_id] --> B[Snapshot groups_id per user, before super().write]
    B --> C[super().write — Odoo's own implied-group grants happen here]
    C --> D[For each user: which EMS groups did they have before,\nbut not anymore, after the write?]
    D --> E{Any EMS groups removed?}
    E -- No --> F[Nothing to do]
    E -- Yes --> G[orphaned = those groups' own direct implied_ids,\nminus any group in the EMS category itself]
    G --> H[still_justified = trans_implied_ids of the EMS groups\nthe user STILL holds]
    H --> I[Revoke: orphaned - still_justified,\nintersected with what the user currently has]
```

### Deliberate scope limits (see the method's own docstring for the full reasoning)

- **Depth-1 only**, not the full transitive closure of `implied_ids` — chasing the whole chain would also revoke generic, foundational groups (e.g. `base.group_user`) that virtually every internal user needs regardless of EMS role, and could lock a demoted user out entirely. Depth 1 matches exactly what `security/groups.xml` itself documents as "granted by this EMS group."
- **Never touches a group outside the EMS category** that an admin granted manually and unrelated to any EMS group the user ever held — there's no way to distinguish that from an EMS-implied grant once both are plain rows in `res_groups_users_rel`. Documented, accepted limitation, not a bug.
- Re-entrant writes triggered by this method itself (revoking groups is itself a `write()`) are guarded by the `ems_syncing_groups` context key, so it doesn't recurse into itself.

**Test coverage note:** `tests/test_user_implied_groups.py` covers the revoke-on-removal path and the "never touch an unrelated group" guarantee. The `still_justified` branch (an implied group kept because another currently-held EMS group also implies it) is sound on code reading but wasn't independently pinned down by its own test — a `base.group_partner_manager` grant kept silently not sticking via `write()` in a way this pass didn't get to the bottom of before time ran out, unrelated to the method's own logic as far as could be told. Worth a fresh look if this method is ever touched again.

---

## Access Control

No EMS-specific `ir.model.access.csv` rows for `res.users` — standard Odoo user administration access applies.

---

## Views

No dedicated EMS view for `res.users` itself beyond `views/settings/res_users_form.xml` (the "My Profile" `image_disabled` toggle — see [Photo visibility](photo_visibility.md)).
