# Technical Reference: `google.workspace.mixin` (`models/shared/google_workspace_mixin.py`)

## Overview

`GoogleWorkspaceMixin` (`_name = 'google.workspace.mixin'`) holds the model-agnostic pieces of
the Google Workspace Directory API integration shared by the two concrete provisioning flows —
staff accounts (`hr.employee`, see
[`google_workspace_staff.md`](../employees/google_workspace_staff.md)) and student accounts
(`res.partner`, see [`google_workspace_student.md`](../contacts/google_workspace_student.md)).
This page documents only the mixin's own API; the actual account-creation/sync business logic,
data model, and access control live in those two consumer docs.

Already fully DTON'd as part of Phase 5 of the retroactive rollout (before this shared-mixins
consolidation pass) — this page exists for indexing/discoverability, no code changes made here.

## Methods

| Method | Purpose |
|--------|---------|
| `_gw_normalize(text)` | Lowercase, strip accents (`ñ→n`, `ç→c`...) via Unicode NFKD decomposition, keep only alphanumerics. Used to derive a Workspace username/email-local-part candidate from a person's name. |
| `_gw_random_password(length=12)` | A random password guaranteed to contain a lowercase, an uppercase, and a digit — generated with `secrets` (not `random`), suitable for a one-time credential a user must change. |
| `_gw_get_service()` | Builds the authenticated Directory API client from the company's service-account JSON (`env.company.google_ws_sa_json`, Fernet-encrypted at rest — same pattern as `limesurvey_pwd`). Deliberately **no domain-wide delegation / `.with_subject()` impersonation** — the service account uses a custom admin role scoped to the managed OUs instead, a narrower blast radius if the credentials ever leak. Raises a clear `UserError` if the `google-api-python-client`/`google-auth` libraries aren't installed, or the JSON is missing/invalid — both are optional-at-import-time (see the module-level `try/except ImportError` guarding `GOOGLE_LIBS_AVAILABLE`) so the module always loads even where Google integration isn't configured at all. |
| `_gw_format_phone(raw)` | E.164 formatting (`+34...`) via the `phonenumbers` library if installed, else returns the raw value unchanged; returns `False` for an invalid/unparseable number. |

## Tests

Not duplicated here — already covered extensively by each consumer's own test suite
(`tests/test_employee_google_workspace.py`, `tests/test_student_google_workspace.py`), which
mock `_gw_get_service` and exercise every one of these helpers indirectly through the real
provisioning flow.
