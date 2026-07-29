# Technical Reference: `ems.base` (`models/shared/base.py`)

## Overview

`EmsBase` (`_name = 'ems.base'`) is the foundational `AbstractModel` inherited by most
business models in EMS (directly or via `ems.multithreading`, which also inherits it) — it
bundles `mail.thread`/`mail.activity.mixin`, an `active` field, permission-check helpers, and
the chatter/notification helpers used throughout the codebase (`notify()`, `chatter()`,
`chatter_exception()`).

Any model that needs Odoo's chatter (`message_ids`), the bus-based toast notification helper,
or the `user_is_admin`/`user_is_tutor` computed flags used across many views' `invisible`/
`readonly` attrs, inherits this mixin.

---

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `active` | `Boolean`, default `True` | Standard Odoo archive flag. |
| `user_is_admin` | `Boolean`, non-stored | `default=lambda self: self.get_user_is_admin()` — computed once at record-creation/read time in the client, not a real `@api.depends` compute. Used in views, not meant to be queried in Python (call `get_user_is_admin()` directly there). |
| `user_is_tutor` | `Boolean`, non-stored | Same pattern, backed by `get_user_is_tutor()`. |

---

## Methods

| Method | Purpose |
|--------|---------|
| `action_archive()` | Sets `active = False` on every record in `self`. |
| `get_user_is_admin()` | `self.env.user.has_group('ems.group_academic_admin')`. |
| `get_user_is_tutor()` | `True` if the current user has an `hr.employee` with any `tutorship_ids`. |
| `get_user_is_tutor_of_self()` | Only meaningful on a model that actually has a `tutor_id` field (checked via `'tutor_id' in self.env[self._name]._fields`) — returns `None` otherwise, since there's no explicit `return` for that branch. |
| `persistent_hash(data)` | `sha256(str(data))` — a hash stable across process restarts, unlike Python's own salted `hash()`. Used by `ems.limesurvey_header.compute_survey_data()` to derive a survey's `internal_id`. |
| `notify(title, message, notification_type, sticky=False)` | Fires a toast via `self.env.user._bus_send("simple_notification", ...)` — the **user** channel, not the partner channel, since the partner channel isn't reliably subscribed in Odoo v18 multi-worker production. `notification_type` is one of `success`/`warning`/`danger`/`info`. Doesn't touch `self` as a record at all — safe to call even on an empty/non-existent recordset. |
| `chatter(message)` | `message_post(body=message, message_type='notification', subtype_xmlid='mail.mt_note')` — a plain log line in the record's chatter. Needs a real, persisted record (uses `self.id`). |
| `chatter_exception(exception)` | Posts a red alert block with the exception message and full traceback, collapsed behind a `<details>` toggle. |
| `build_html_list(items)` | Safe `<ul><li>...</li></ul>` from a list of plain strings, each HTML-escaped. Doesn't touch `self` as a record — callable even from a model that doesn't inherit `ems.base` via `self.env['ems.base'].build_html_list(items)` (see the wizards below, all plain `TransientModel`s). |
| `compute_exclusion_ids(field_name, condition, mapped_path)` | Shared body for an "already in use, exclude from picker" `Many2many` compute: sets `field_name` to `False`, then to `record.mapped(mapped_path)` if `condition(record)` is truthy. The caller keeps its own `@api.depends(...)`-decorated method (Odoo requires the decorator on the concrete method) — only the body is one line. |

---

## Extracted duplicated patterns (this pass, 2026-07-29)

Both `build_html_list` and `compute_exclusion_ids` were extracted after the exact same code
shape turned up, hand-written, in multiple unrelated files during the DTON rollout — in both
cases the duplication had already independently caused (or risked) the same bug more than
once:

- **`build_html_list`** replaces the `Markup('').join(Markup('<li>{}</li>').format(x) for x in items)`
  idiom previously hand-written in `models/contacts/student_import_wizard.py`,
  `models/contacts/applicant_import_wizard.py`, and `models/grades/grade_import_wizard.py`'s
  `_build_result_html` methods — each of the three needed the identical fix during this
  rollout (a missing `Markup('')` on the `.join()` silently double-escapes and shows literal
  `&lt;li&gt;` text). None of these three wizards inherit `ems.base` (they're plain
  `TransientModel`s), so they call it via `self.env['ems.base'].build_html_list(...)` rather
  than `self.build_html_list(...)`.
- **`compute_exclusion_ids`** replaces the identical reset-then-conditionally-`.mapped()` body
  duplicated across `models/attendance/attendance_session.py::_compute_inuse_student_ids`,
  `models/contacts/enrollment.py::_compute_inuse_subject_ids`, and both
  `EmsLimesurveyRecipient._compute_inuse_student_ids`/`EmsLimesurveyEnrollment._compute_inuse_subject_ids`
  in `models/communications/limesurvey.py`. `models/employees/teaching.py::_compute_inuse_group_ids`
  is a genuine variant (builds its list via a nested loop, not a single `.mapped()`) and was
  deliberately left as-is rather than forced into this shape.

## Tests

`tests/test_shared_mixins.py::TestEmsBase` (13 tests) — `build_html_list`'s empty-input and
per-item-escaping behavior tested directly; `compute_exclusion_ids` is covered indirectly
through each consumer's own existing field-level tests (no behavior changed, only the
implementation body moved).

## Fixed in this pass (2026-07-29)

**`chatter_exception()` built its HTML via an f-string wrapped in `Markup(...)`, which never
escapes the interpolated exception text.** An f-string's substitutions happen at the plain
`str` level, before `Markup()` ever sees the result — `Markup()` only marks a string as
"already safe," it does not sanitize on wrapping. Since exception messages can echo raw
user/DB-derived content (several import wizards elsewhere in this codebase build
`ValidationError` messages directly from an uploaded file's cell values), this could inject
literal, unescaped HTML into the chatter — the same class of bug already found and fixed four
times in `*_html`-building wizards during this rollout (see `grade_import_wizard.md` for the
established pattern), just not previously checked in this shared helper despite it being
called from many `except Exception as e: self.chatter_exception(e)` sites across the codebase.

Fixed with the same established pattern: `Markup(template_with_placeholders).format(*args)` —
`Markup.format()` auto-escapes each plain-`str` argument, unlike a plain f-string.
Regression-tested in `tests/test_shared_mixins.py::TestEmsBase::test_chatter_exception_escapes_untrusted_content`
(an exception message containing `<script>`/`<b>` tags; asserts the posted chatter body has no
literal unescaped `<script>` and does contain the HTML-escaped `&lt;script&gt;`).

Also: `persistent_hash`'s local variables `bytes`/`hash` shadowed the Python builtins of the
same name (harmless here — the method never needed the real `bytes`/`hash` builtins inside its
own body — but the same latent-trap pattern flagged and renamed elsewhere in this rollout, e.g.
`LimesurveyApi.count_participants`'s `list` variable). Renamed to `data_bytes`/`digest`. Class
renamed `ems_base` → `EmsBase` (two direct class-level call sites in
`models/contacts/contact.py`'s `_get_read_only_user`/`_get_is_tutor_readonly` — which call
`base.ems_base.get_user_is_admin(self)` as an unbound method rather than instantiating the
mixin — updated accordingly). Loop variables normalized (`rec`→`record` in `action_archive`,
`e`→`employee` in `get_user_is_tutor`). Tabs → spaces.

**Found by the Phase D lint sweep (2026-07-29):** `notify()`'s `type` parameter shadowed the
Python builtin — the one finding from running `pylint --disable=all --enable=redefined-builtin
models/` across the whole codebase (see CLAUDE.md's coding-standards section for how to
re-run it). Renamed to `notification_type`; verified no caller anywhere in `models/` passes it
as a keyword argument (`grep`'d for `type=` on every `.notify(...)` call site — none), so this
was a safe, non-breaking rename.

## Tests

`tests/test_shared_mixins.py::TestEmsBase` (new, 9 tests) — `get_user_is_admin`/
`get_user_is_tutor`/`get_user_is_tutor_of_self` tested directly against the empty `ems.base`
recordset (none of these three need a real record); `notify` likewise (it only touches
`self.env.user`); `chatter`/`chatter_exception`/`action_archive` against a real
`ems.limesurvey_header` record, an arbitrary already-DTON'd consumer.
