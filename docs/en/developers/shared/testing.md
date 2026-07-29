# Technical Reference: shared test utilities (`tests/common.py`)

## Overview

Extracted 2026-07-29 after the DTON rollout's own DTON pass over the test suite itself found
the same fixture/mock boilerplate hand-written identically across dozens of files —
`tests/` had grown to more lines than `models/` (17,576 vs. 14,773), and several of these
exact patterns had already independently drifted or been subtly wrong in more than one file
before being unified here. Not a test framework — just four plain functions imported where
needed (`from .common import ...`), no base class required.

## `create_level_study(cls, prefix, **overrides)` / `create_level_study_group(cls, prefix, **overrides)`

The single most duplicated fixture in the suite: a level+study(+group) triple with unique
codes, needed by nearly every test touching curriculum-adjacent data. `create_level_study`
returns `(level, study)`; `create_level_study_group` composes on top of it and additionally
returns `group`.

```python
cls.level, cls.study = create_level_study(cls, 'TAI', study={'name': 'Test Study (Attendance Issue)'})
cls.level, cls.study, cls.group = create_level_study_group(cls, 'TCF', level={'name': '...'}, study={'code': 'TCF001', ...})
```

`prefix` becomes the level's and study's `acronym` by default (`f'{prefix}-01'` for the
study's `code`); pass `level=`/`study=`/`group=` sub-dicts to override any field that doesn't
match a given file's actual fixture data — most callers need at least a `name` override, and
several need `code`/`acronym` overrides too since not every file used the same value for both.

**Why two functions, not one:** the majority of real call sites create a `subject` (or some
other record) *between* `study` and `group` — `create_level_study_group` alone didn't fit
roughly half the files this was extracted from, so `create_level_study` (level+study only) is
the primary building block; call it directly and create `group` by hand afterward whenever
something needs to happen in between.

**Not a fit for:** tests of `ems.level`/`ems.study`/`ems.group` themselves that exercise
validation edge cases (missing required fields, duplicate acronyms, etc.) — those need
deliberately incomplete/colliding data, the opposite of what a "give me a valid one" factory
provides. `tests/test_level.py` was left unmigrated for exactly this reason.

## `mock_outgoing_email(cls)`

The mechanism CLAUDE.md's "Email safety in tests" section already mandates
(`patch('...ir_mail_server.IrMailServer.send_email', return_value='test-message-id')`,
started in `setUpClass`, stopped via `addClassCleanup`), as a one-line call instead of a
copy-pasted five-line block — reduces the chance a future test forgets it, since forgetting it
means a real SMTP send to a real address (see CLAUDE.md for why this environment's mail
servers are real and credentialed).

```python
mock_outgoing_email(cls)
# or, if a test needs to assert on the mock itself (call count, reset_mock()):
cls.mail_transport = mock_outgoing_email(cls)
```

## `make_synchronous_run_in_thread(record)`

Every LimeSurvey test that exercises `run_action()`/action methods needs `run_in_thread`
mocked to run `setup`/`compute`/`store`/`callback` synchronously against a real record instead
of spawning a real thread (see [`multithreading.md`](multithreading.md) for why real threading
can't be exercised in `TransactionCase` at all). This factory returns exactly that
`side_effect` function, closing over `record`:

```python
with patch.object(type(header), 'run_in_thread', side_effect=make_synchronous_run_in_thread(header), autospec=True):
    ...
```

**Only fits when the record already exists at patch-setup time.** One test in
`tests/test_limesurvey_recipient.py` (`test_create_manual_on_uploaded_header_triggers_upload_without_real_api`)
creates the recipient *inside* the mocked block itself (`create()`'s manual-state flow
triggers `action_upload()` synchronously) — that one keeps its own inline closure using the
actual `self_recipient` argument autospec passes at call time, since there's no pre-existing
record to close over.

## Tests

No dedicated test file for `tests/common.py` itself — these are test utilities, exercised
implicitly by every test file that imports and uses them (all of `tests/`, effectively).
