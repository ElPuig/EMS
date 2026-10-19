# Performance audit (pending)

**Status:** pending, not started (issue #641). Written 2026-10-15 (issue #637), when the guard duty board's RPC
turned out to take 14-17s on the dev service (~1.6s without the debugger) and dropped to ~0.15-0.2s
once fixed. Nobody has reviewed the rest of EMS with the same eye yet.

## Why

The developer's standing rule (CLAUDE.md, Coding standards, "Efficiency first"): runtime speed
first (the users), then memory and resources (the sysadmin), always within the Odoo way. New code
follows it from 2026-10-15; this audit is for everything written before.

## What to look for (the patterns found on the guard duty board)

- `filtered()`/`search()` inside a loop over the same data (rows x columns x records shapes): index
  once, look up.
- A whole-centre `search()` then filtered in Python, where a search domain would do it in SQL.
- Fields read record by record (lost prefetch: `browse(ids)` without `with_prefetch()`, recordsets
  built one at a time), each read a query - and, on `hr.employee`, a per-read field access check.
- The same structure recomputed several times in one request.
- Non-stored computes read in list/kanban views over many records; `search_count`/`read_group`
  candidates; missing indexes on fields used in domains of frequent searches.
- Client side: RPCs called in loops, components re-rendering large lists, data fetched twice.

## How

1. List the heavy screens and RPCs (centre-wide aggregations first: guard duty board, attendance
   reports, attendance sessions/roll call, group and teacher schedules, grade sessions, enrolment,
   working schedule import, course transition, crons and queue jobs).
2. Measure each one on real data, cold (`odoo shell` + `cProfile`, `env.invalidate_all()` first),
   and record time and query count before touching anything. The dev service runs under `debugpy`
   (~10x slower Python), so its log is a relative signal only.
3. Fix by priority (most used x slowest), one issue per area, each with its before/after numbers in
   the PR changelog and a test that guards the behaviour.

Delete this file once the audit is done and its findings are in issues.
