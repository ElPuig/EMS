# PLAN — `_build_csv`'s "department" column is a hardcoded literal, not real data

> **Status: flagged during the `limesurvey.py` DTON pass, Block 3 (2026-07-29), not
> implemented.** This is not a design for new work — it's an open question for whoever owns
> the LimeSurvey survey-results export to answer before any fix is written. Nothing below has
> been built. Verify file/line references against current code before acting, since the
> branch may have moved on since this was written.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete this file once the
> question is resolved (fixed, or explicitly decided as intentional and documented in
> `docs/en/developers/communications/limesurvey.md`).

## Problem

`_build_csv()` (`models/communications/limesurvey.py`, called from
`ems.limesurvey_header.action_download()`, block 4) builds a CSV of survey responses, one row
per numeric/text question. Every other column is pulled from the actual LimeSurvey response
dict via a per-question-group prefix (`level`, `topic`, `subject_code`, `subject_name`,
`degree`, `group`, `trainer`) — except `department`:

```python
department   = "DEPARTMENT"
```

This is a literal string, not read from `response` at all. Every exported CSV row therefore
has the literal text `"DEPARTMENT"` in its department column, regardless of which actual
department/subject the response belongs to.

## Why not fixed in this pass

Fixing this requires knowing where the real department value should come from — either a
survey response key following the same `f"{prefix}..."` convention as the other fields (in
which case the survey's question definitions need checking to find the right key, e.g.
`f"{prefix}department"` if it exists), or a lookup elsewhere (e.g. resolved from
`subject_code` against `ems.subject`/`ems.department` data). Guessing either would be
inventing business logic, not a normalization fix — this needs input from whoever knows the
actual LimeSurvey survey template's question keys and what "department" should mean here.

## Open questions

1. Does the LimeSurvey survey template (the `tsv_raw_text` uploaded via `action_upload`) even
   collect a per-question department value? If yes, what's its question code (does it follow
   the same `{prefix}xxx` naming as `level`/`topic`/etc.)?
2. If not collected directly, should it be derived (e.g. from `subject_code` via
   `ems.subject.department_id` or similar)?
3. Is this CSV export actually consumed anywhere that reads the department column, or is it
   currently ignored downstream (in which case this may be very low priority)?

## Where this is also documented

`docs/en/developers/communications/limesurvey.md`, Block 3 section — a one-line pointer to
this plan file. Also marked in the code itself with a `# TODO(gap):` comment pointing here.
