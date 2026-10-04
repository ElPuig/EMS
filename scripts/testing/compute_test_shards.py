#!/usr/bin/env python3
"""Splits EMS's test classes into parallel CI shards, balanced by measured duration:
"backend-N" shards (everything except browser tours) and "tours-N" shards (only the tour
classes from tests/*_tour.py).

Self-maintaining by design: test classes are discovered from tests/test_*.py at run time, not
hardcoded here. A class with no measured duration yet (a new test) is counted at the median of
its kind, and the last backend shard is "every ems test not listed elsewhere", so a class this
script fails to see still runs. Durations come from test_timings.json next to this file,
regenerated from a CI run's logs with update_test_timings.py (issue #565).

Used by two consumers, both invoked with the repo root as the working directory:
- CI (ci-unit-testing.yml): `python3 scripts/testing/compute_test_shards.py` prints a single
  JSON line, `{"include": [{"name": ..., "tags": ..., "needs_chrome": bool}, ...]}`, for
  GitHub Actions' `strategy.matrix: ${{ fromJson(...) }}`.
- Local dev (test.sh's no-argument "run everything" form, via run_sharded_tests.py, which
  lives alongside this file): imports `compute_shards()` directly to drive the same split
  against local database clones.
"""
import glob
import json
import os
import re
import statistics

# More shards = less wall-clock time, but each CI shard pays its own setup again (~3 min: a
# full "install Odoo + EMS") and GitHub's Free tier runs at most 20 jobs at once across the
# whole account; locally, run_sharded_tests.py throttles how many Chrome shards run at once.
# Pick these from a real CI run: the slowest shard sets the wall-clock time.
BACKEND_SHARDS = 2
TOUR_SHARDS = 8

TIMINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_timings.json')


def classes_in(path):
    with open(path) as handle:
        return re.findall(r'^class\s+(\w+)\s*\(', handle.read(), re.M)


def discover_classes():
    """Returns (backend classes, tour classes), each sorted."""
    backend, tours = set(), set()
    for path in glob.glob('tests/test_*.py'):
        (tours if path.endswith('_tour.py') else backend).update(classes_in(path))
    return sorted(backend - tours), sorted(tours)


def load_timings():
    try:
        with open(TIMINGS_FILE) as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}


def balance(classes, shard_count, timings):
    """Longest-first greedy split into shard_count lists of classes with similar total time."""
    known = [timings[cls] for cls in classes if cls in timings]
    default = statistics.median(known) if known else 1.0
    shards = [{'classes': [], 'seconds': 0.0} for _ in range(shard_count)]
    for cls in sorted(classes, key=lambda cls: (-timings.get(cls, default), cls)):
        lightest = min(shards, key=lambda shard: shard['seconds'])
        lightest['classes'].append(cls)
        lightest['seconds'] += timings.get(cls, default)
    return [sorted(shard['classes']) for shard in shards]


def compute_shards():
    backend_classes, tour_classes = discover_classes()
    timings = load_timings()

    # "name" must be safe as a job-display suffix, an artifact name and (locally) a database
    # name suffix: no spaces or punctuation beyond '-'.
    # The last backend shard uses a leading '/ems' positive selector, required, not decorative:
    # a --test-tags expression made of ONLY negative selectors means "everything in the current
    # default test scope except these", which pulls in every other installed module's own tests
    # too (confirmed the hard way, 2026-07-31: it once ran Odoo core's 'web' JS suite for 38
    # minutes). '/ems' alone means "every ems test".
    include = []
    backend_shards = balance(backend_classes, BACKEND_SHARDS, timings)
    listed = []
    for index, shard_classes in enumerate(backend_shards[:-1], start=1):
        listed += shard_classes
        include.append({
            'name': f'backend-{index}',
            'tags': ','.join(f'/ems:{cls}' for cls in shard_classes),
            'needs_chrome': False,
        })
    include.append({
        'name': f'backend-{BACKEND_SHARDS}',
        'tags': '/ems,' + ','.join(f'-/ems:{cls}' for cls in tour_classes + listed),
        'needs_chrome': False,
    })
    for index, shard_classes in enumerate(balance(tour_classes, TOUR_SHARDS, timings), start=1):
        if shard_classes:
            include.append({
                'name': f'tours-{index}',
                'tags': ','.join(f'/ems:{cls}' for cls in shard_classes),
                'needs_chrome': True,
            })
    return include


if __name__ == '__main__':
    print(json.dumps({'include': compute_shards()}))
