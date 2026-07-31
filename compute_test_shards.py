#!/usr/bin/env python3
"""Splits EMS's test classes into parallel CI shards: one "fast" shard (everything except
browser tour tests) plus N "tour" shards (only tour/HttpCase classes, round-robin split).

Self-maintaining by design: tour classes are discovered from tests/*_tour.py at CI run time
(this repo's own established naming convention - see CLAUDE.md's testing conventions), not
hardcoded here. Adding a new *_tour.py file with new test classes is automatically picked up
on the next CI run, no workflow/script edit needed.

Run from the repo root: python3 .github/scripts/compute_test_shards.py
Prints a single JSON line: {"include": [{"name": ..., "tags": ..., "needs_chrome": bool}, ...]}
for GitHub Actions' `strategy.matrix: ${{ fromJson(...) }}`.
"""
import glob
import json
import re

# Tune this based on observed CI wall-clock time (see the "ci" job's per-shard duration in the
# Actions run summary): more shards = more parallel wall-clock reduction, but each shard pays
# its own full "install Odoo + Chrome + EMS" setup cost again - past a point, that fixed
# overhead dominates and further splitting stops helping. This repo's GitHub repo is public,
# so Actions minutes themselves are free either way (see CLAUDE.md/chat history 2026-07-31) -
# the only real cost of raising this is longer runner-queue contention, not billing.
TOUR_SHARDS = 4


def classes_in(path):
    with open(path) as handle:
        return re.findall(r'^class\s+(\w+)\s*\(', handle.read(), re.M)


def main():
    tour_classes = set()
    for path in sorted(glob.glob('tests/*_tour.py')):
        tour_classes.update(classes_in(path))
    tour_classes = sorted(tour_classes)

    shards = [[] for _ in range(TOUR_SHARDS)]
    for index, cls in enumerate(tour_classes):
        shards[index % TOUR_SHARDS].append(cls)

    # "name" must be safe to use as a job-display suffix and an artifact name (no spaces or
    # punctuation beyond '-') - artifact names must also be unique across the whole workflow
    # run, which this already guarantees.
    include = [{
        'name': 'fast',
        'tags': ','.join(f'-/ems:{cls}' for cls in tour_classes),
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

    print(json.dumps({'include': include}))


if __name__ == '__main__':
    main()
