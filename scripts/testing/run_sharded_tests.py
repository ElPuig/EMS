#!/usr/bin/env python3
"""Runs the full EMS test suite locally, sharded in parallel across throwaway clones of the
`ems` database - the local-dev counterpart to ci-unit-testing.yml's matrix. Only invoked by
test.sh's no-argument ("run everything") form; a scoped run (a class name or an explicit
--test-tags expression) stays sequential against the real `ems` database directly (see
test.sh) - cloning overhead isn't worth paying for a run that's already a few seconds long.

Each shard's clone uses Postgres "CREATE DATABASE ... TEMPLATE ems", not pg_dump/restore -
empirically much faster (a few seconds even for a sizeable dev database) and pg_dump/restore
was tried first and found too slow/lock-contentious when cloning several times concurrently
from one live source (see chat history 2026-07-31). Clones (database + filestore copy) are
always dropped again at the end, pass or fail - this never writes to the real `ems` database,
only reads from it once per shard to seed the clone.

Must run with the real Odoo service already stopped (test.sh does this before calling in) -
CREATE DATABASE ... TEMPLATE requires no other connections to the template database.

Browser (tour) shard concurrency is throttled based on THIS machine's own CPU/RAM, unlike
CI's fixed shard count - see max_concurrent_chrome_shards() below for why the two can't use
the same knob: CI gives each shard its own dedicated runner (no shared-resource contention
possible between shards), while every local shard fights the same physical cores/RAM. Even
throttled, CPU contention between concurrently-running Chrome instances can still
occasionally push one past the tour engine's fixed step timeout - a real, if rare, resource
ceiling, not a script bug (see chat history 2026-07-31: the identical shard split always runs
clean sequentially, and CI never hits this at all since every one of its shards gets its own
dedicated runner).

A failed shard escalates through up to 3 attempts before being reported as a real failure -
each level trading a bit more time for a bit more isolation, since a failed shard retried
under the exact same contention that caused it has no particular reason to fare better:
  1. First pass - all shards at the resource-based concurrency limit (max_concurrent_chrome_
     shards()), tuned for speed.
  2. Retry - only the shards that failed pass 1, all launched together with NO throttling
     (there's real spare CPU/RAM now that most of the first pass has already finished).
  3. Second retry - anything that still failed runs one at a time, fully serial - the same
     isolation a sequential run gets, so this level is expected to always succeed baring a
     genuine bug (not a resource one).
This is deliberately a LOCAL-ONLY leniency the developer explicitly asked for (dev
environment, not CI: "esas cosas se pueden asumir [...] pero en GitHub, ahí sí que debería
funcionar bien a la primera" - CI's own workflow never retries, a first-try CI failure there
is always a real signal). Never silent: which level a shard finally passed at is always
called out by name in the final summary.
"""
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from compute_test_shards import compute_shards

FILESTORE_ROOT = Path("/var/lib/odoo/.local/share/Odoo/filestore")
BASE_HTTP_PORT = 18069
RESULT_RE = re.compile(r"odoo\.tests\.result: (\d+) failed, (\d+) error\(s\) of (\d+) tests")

# Empirically found 2026-07-31 on a 12-core/~13GB-available machine: level-1 concurrency drives
# the failure rate NON-linearly, not gently - 2 concurrent Chrome-driven (tour) shards produced
# 1-2 flaky failures out of 8-9 shards, but 4 concurrent produced 6 (mostly the same class of
# "TIMEOUT step failed to complete within 10000 ms." tour-step failure, CPU/RAM contention
# between browsers, not a script bug - the identical shard split always runs clean sequentially,
# and CI never hits this at all since every shard there gets its own dedicated runner). Since
# every level-1 failure gets fully redone at level 2, a high level-1 failure rate roughly
# doubles the work for those shards - so level 1 is deliberately tuned CONSERVATIVE (favor most
# shards passing first try) rather than aggressive-with-retry-as-safety-net; the latter measured
# strictly worse in wall-clock terms (20m45s vs. 10m19s for an otherwise-equal 2-concurrent run
# with a simpler single retry) despite the 3-level escalation itself working exactly as
# intended (every shard eventually passed, none needed level 3).
#
# RAM is the deliberately dominant factor here (developer's explicit request 2026-07-31), with
# CPU cores only as a looser backstop - each concurrent Chrome+Odoo pair's realistic memory
# footprint matters more directly than raw core count for how many can safely coexist. Tune
# both ratios based on observed flakiness on a given machine: raise GB_PER_CHROME_SHARD /
# CORES_PER_CHROME_SHARD if flaky failures keep showing up even at level 1 (more headroom per
# shard, fewer concurrent), lower them if level 1 comfortably passes clean and finishes with
# spare capacity to spend.
CORES_PER_CHROME_SHARD = 2
GB_PER_CHROME_SHARD = 6


def available_ram_gb():
    try:
        with open('/proc/meminfo') as handle:
            for line in handle:
                if line.startswith('MemAvailable:'):
                    return int(line.split()[1]) / (1024 * 1024)
    except OSError:
        pass
    return 4.0  # conservative fallback if /proc/meminfo is ever unavailable


def max_concurrent_chrome_shards(chrome_shard_count):
    cpu = os.cpu_count() or 2
    ram_gb = available_ram_gb()
    limit = max(1, min(
        cpu // CORES_PER_CHROME_SHARD or 1,
        int(ram_gb // GB_PER_CHROME_SHARD) or 1,
        chrome_shard_count,
    ))
    return limit, cpu, ram_gb


def sh(cmd, **kwargs):
    return subprocess.run(cmd, shell=True, **kwargs)


def clone_shard_db(db_name):
    sh(f"sudo -u odoo dropdb --if-exists {db_name}", check=True)
    sh(f"sudo -u odoo psql -d postgres -c 'CREATE DATABASE {db_name} TEMPLATE ems;'",
       check=True, stdout=subprocess.DEVNULL)
    sh(f"sudo -u odoo rm -rf {FILESTORE_ROOT / db_name}")
    sh(f"sudo -u odoo cp -r {FILESTORE_ROOT / 'ems'} {FILESTORE_ROOT / db_name}", check=True)


def drop_shard_db(db_name):
    sh(f"sudo -u odoo dropdb --if-exists {db_name}")
    sh(f"sudo -u odoo rm -rf {FILESTORE_ROOT / db_name}")


class ShardRun:
    def __init__(self, shard, db_name, log_path, log_file, proc):
        self.shard = shard
        self.db_name = db_name
        self.log_path = log_path
        self.log_file = log_file
        self.proc = proc


class ShardBatchRunner:
    """Runs a list of shards with the same non-browser-unthrottled /
    browser-throttled-by-N-at-a-time policy, reusable for both the first pass and the
    retry-failed-shards pass. Every ShardRun it launches (across every call to run()) is
    tracked in self.all_runs so the caller can guarantee cleanup regardless of how many
    passes actually happened."""

    def __init__(self, work_dir):
        self.work_dir = work_dir
        self.port_counter = 0
        self.all_runs = []

    def _launch(self, shard):
        db_name = f"ems_shard_{shard['name'].replace('-', '_')}"
        clone_shard_db(db_name)
        log_path = self.work_dir / f"{shard['name']}-{len(self.all_runs)}.log"
        port = BASE_HTTP_PORT + self.port_counter
        self.port_counter += 1
        cmd = (
            "sudo -u odoo bash -c "
            f"\"odoo -d {db_name} --test-enable --test-tags='{shard['tags']}' "
            f"--http-port={port} --stop-after-init -c /etc/odoo/odoo.conf\""
        )
        log_file = open(log_path, 'w')
        proc = subprocess.Popen(cmd, shell=True, stdout=log_file, stderr=subprocess.STDOUT)
        run = ShardRun(shard, db_name, log_path, log_file, proc)
        self.all_runs.append(run)
        return run

    def run(self, shards, chrome_limit):
        """Runs `shards` to completion (browser ones throttled to `chrome_limit` at a time,
        non-browser ones launched immediately/unthrottled) and returns the finished ShardRuns."""
        chrome_shards = [s for s in shards if s['needs_chrome']]
        other_shards = [s for s in shards if not s['needs_chrome']]
        queue = list(chrome_shards)

        active = [self._launch(shard) for shard in other_shards]
        active += [self._launch(shard) for shard in queue[:chrome_limit]]
        queue = queue[chrome_limit:]

        finished = []
        while active:
            time.sleep(1)
            still_active = []
            for shard_run in active:
                if shard_run.proc.poll() is None:
                    still_active.append(shard_run)
                    continue
                shard_run.log_file.close()
                finished.append(shard_run)
                if queue:
                    still_active.append(self._launch(queue.pop(0)))
            active = still_active
        return finished

    def cleanup(self):
        for shard_run in self.all_runs:
            drop_shard_db(shard_run.db_name)
            if not shard_run.log_file.closed:
                shard_run.log_file.close()


def shard_passed(shard_run):
    text = shard_run.log_path.read_text(errors='replace')
    match = RESULT_RE.search(text)
    ok = bool(match) and match.group(1) == '0' and match.group(2) == '0'
    return ok, text, match


# (limit, level label, description) for each escalation level - see the module docstring.
# Level 1's limit is computed at runtime from actual CPU/RAM; levels 2/3 are fixed policies
# (no throttling, then fully serial) rather than resource-based, since by the time either
# runs there are only a handful of shards left and the goal shifts from "fast" to "isolated".
LEVEL_NAMES = {1: "first attempt", 2: "retry (loosened)", 3: "retry (serial)"}


def main():
    shards = compute_shards()
    chrome_shard_count = sum(1 for s in shards if s['needs_chrome'])
    level1_limit, cpu, ram_gb = max_concurrent_chrome_shards(chrome_shard_count)

    print(f"Detected {cpu} CPU core(s), {ram_gb:.1f} GB available RAM.")
    print(f"Level 1: running {len(shards) - chrome_shard_count} non-browser shard(s) "
          f"immediately, plus up to {level1_limit} of {chrome_shard_count} "
          f"browser-tour shard(s) at a time.")

    work_dir = Path(tempfile.mkdtemp(prefix="ems_test_shards_"))
    runner = ShardBatchRunner(work_dir)
    try:
        results = {}  # name -> (ok, text, match, level)
        pending = list(shards)
        level = 1
        level_limit = level1_limit

        while pending:
            for shard_run in runner.run(pending, level_limit):
                ok, text, match = shard_passed(shard_run)
                results[shard_run.shard['name']] = (ok, text, match, level)

            pending = [s for s in pending if not results[s['name']][0]]
            if not pending:
                break

            level += 1
            if level > 3:
                break
            level_limit = len(pending) if level == 2 else 1  # 2: all together, unthrottled; 3: serial
            names = ', '.join(s['name'] for s in pending)
            print(f"\n{len(pending)} shard(s) still failing, escalating to level {level} "
                  f"({LEVEL_NAMES[level]}, {level_limit} at a time): {names}")

        overall_ok = True
        escalated = []
        for shard in shards:
            ok, text, match, level_reached = results[shard['name']]
            suffix = f" ({LEVEL_NAMES[level_reached]})" if level_reached > 1 else ""
            print(f"\n===== shard: {shard['name']}{suffix} =====")
            print(text)
            if ok:
                if level_reached > 1:
                    escalated.append(f"{shard['name']} (level {level_reached})")
                continue
            overall_ok = False
            label = ("no clean result line found" if not match else
                     f"{match.group(1)} failed, {match.group(2)} error(s)")
            print(f"===== shard {shard['name']}: FAILED even at level {level_reached} "
                  f"({label}) - this is no longer presumed to be resource contention =====")

        if escalated:
            print(f"\nNOTE: needed escalation to pass: {', '.join(escalated)} - if this keeps "
                  "happening, this machine's CORES_PER_CHROME_SHARD/GB_PER_CHROME_SHARD "
                  "(run_sharded_tests.py) may need to be more conservative.")

        return 0 if overall_ok else 1
    finally:
        runner.cleanup()
        subprocess.run(f"rm -rf {work_dir}", shell=True)


if __name__ == '__main__':
    sys.exit(main())
