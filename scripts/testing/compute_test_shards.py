#!/usr/bin/env python3
"""Splits EMS's test classes into parallel CI shards: one "fast" shard (everything except
browser tour tests) plus N "tour" shards (only tour/HttpCase classes, round-robin split).

Self-maintaining by design: tour classes are discovered from tests/*_tour.py at CI run time
(this repo's own established naming convention - see CLAUDE.md's testing conventions), not
hardcoded here. Adding a new *_tour.py file with new test classes is automatically picked up
on the next CI run, no workflow/script edit needed.

Used by two consumers, both invoked with the repo root as the working directory (the
`tests/*_tour.py` glob below is relative to that, not to this file's own location):
- CI (ci-unit-testing.yml): `python3 scripts/testing/compute_test_shards.py` prints a single
  JSON line, `{"include": [{"name": ..., "tags": ..., "needs_chrome": bool}, ...]}`, for
  GitHub Actions' `strategy.matrix: ${{ fromJson(...) }}`.
- Local dev (test.sh's no-argument "run everything" form, via run_sharded_tests.py, which
  lives alongside this file): imports `compute_shards()` directly to drive the same split
  against local database clones.
"""
import glob
import json
import re

# Tune this based on observed wall-clock time (CI: the "ci" job's per-shard duration in the
# Actions run summary; local: run_sharded_tests.py's own per-shard timing): more shards = more
# parallel wall-clock reduction, but each shard pays its own setup cost again (CI: a full
# "install Odoo + Chrome + EMS"; local: a database+filestore clone) - past a point, that fixed
# overhead dominates and further splitting stops helping. This repo's GitHub repo is public
# and on GitHub's Free tier (confirmed by the developer 2026-07-31), so CI's Actions minutes
# are free either way - the only real cost of raising this is GitHub's account-wide concurrent
# job budget (20 on Free, shared across every repo/workflow the account runs, not just this
# one) and longer runner-queue contention there, or local CPU/RAM contention here (throttled
# automatically for the local path - see run_sharded_tests.py's max_concurrent_chrome_shards -
# raising this constant only changes how many *total* shards exist, not how many run at once
# on one machine). 8 is the developer's own confirmed choice (up from an initial default of 4),
# not a measured optimum - revisit after seeing a real CI run's per-shard timing.
TOUR_SHARDS = 8


def classes_in(path):
    with open(path) as handle:
        return re.findall(r'^class\s+(\w+)\s*\(', handle.read(), re.M)


def compute_shards():
    tour_classes = set()
    for path in sorted(glob.glob('tests/*_tour.py')):
        tour_classes.update(classes_in(path))
    tour_classes = sorted(tour_classes)

    shards = [[] for _ in range(TOUR_SHARDS)]
    for index, cls in enumerate(tour_classes):
        shards[index % TOUR_SHARDS].append(cls)

    # "name" must be safe to use as a job-display suffix, an artifact name, and (locally) a
    # database name suffix - no spaces or punctuation beyond '-'. Artifact names must also be
    # unique across a CI workflow run, which this already guarantees.
    # The leading '/ems' positive selector is required, not decorative: a --test-tags
    # expression made of ONLY negative selectors doesn't mean "everything in ems except
    # these" - it means "everything in the current default test scope except these", which
    # pulls in every other installed module's own tests too (confirmed the hard way,
    # 2026-07-31: an earlier version of this line without the '/ems' anchor made this shard
    # spend 38 minutes running Odoo core's own 'web' module JS/HOOT test suite - thousands of
    # unrelated frontend framework tests - instead of the ~2 minutes its actual EMS scope
    # takes). '/ems' alone (no ':Class') already means "every ems test", matching the
    # positive-only selector test.sh's own default (no-argument) invocation already used
    # before this file existed.
    include = [{
        'name': 'fast',
        'tags': '/ems,' + ','.join(f'-/ems:{cls}' for cls in tour_classes),
        'needs_chrome': False,
    }]
    for shard_index, shard_classes in enumerate(shards, start=1):
        if not shard_classes:
            continue
        include.append({
            'name': f'tour-{shard_index}',
            'tags': ','.join(f'/ems:{cls}' for cls in shard_classes),
            'needs_chrome': True,
        })

    return include


if __name__ == '__main__':
    print(json.dumps({'include': compute_shards()}))
