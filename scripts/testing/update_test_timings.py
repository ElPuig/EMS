#!/usr/bin/env python3
"""Updates test_timings.json (read by compute_test_shards.py) from Odoo test logs.

Usage: python3 scripts/testing/update_test_timings.py <odoo test log>...

Typically the odoo-test.log of every shard of one CI run (the "odoo-logs-<shard>" artifacts:
`gh run download <run id> --pattern 'odoo-logs-*'`). A class's duration is the sum of the time
from each of its "Starting Class.test_x" lines to the next one (or to the end of the run), so
its setUpClass is counted too. The pause between at_install and post_install tests (asset
generation, "Starting post tests") is not counted for any class. Classes found in the logs are
updated; the others keep their previous value.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime

from compute_test_shards import TIMINGS_FILE, load_timings

LINE = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) \d+ \w+ \S+ (\S+): (.*)$')
START = re.compile(r'^Starting (\w+)\.test_\w+ \.\.\.')


def class_durations(path):
    durations = defaultdict(float)
    current, started = None, None
    with open(path, errors='replace') as handle:
        for line in handle:
            match = LINE.match(line)
            if not match:
                continue
            moment = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S,%f')
            message = match.group(3)
            start = START.match(message)
            boundary = message.startswith('Starting post tests') or match.group(2) == 'odoo.tests.result'
            if current and (start or boundary):
                durations[current] += (moment - started).total_seconds()
                current = None
            if start:
                current, started = start.group(1), moment
    return durations


def main(paths):
    timings = load_timings()
    measured = defaultdict(float)
    for path in paths:
        for cls, seconds in class_durations(path).items():
            measured[cls] += seconds
    timings.update({cls: round(seconds, 1) for cls, seconds in measured.items()})
    with open(TIMINGS_FILE, 'w') as handle:
        json.dump(dict(sorted(timings.items())), handle, indent=1)
        handle.write('\n')
    print(f"{len(measured)} classes measured, {len(timings)} in {TIMINGS_FILE}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
