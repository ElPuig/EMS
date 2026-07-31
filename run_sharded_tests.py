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
dedicated runner). A failed shard is therefore retried once, fresh, before being reported as a
real failure - deliberately a LOCAL-ONLY leniency the developer explicitly asked for (dev
environment, not CI: "esas cosas se pueden asumir [...] pero en GitHub, ahí sí que debería
funcionar bien a la primera" - CI's own workflow never retries, a first-try CI failure is
always a real signal). Never silent: a shard that only passed after a retry is always called
out by name in the final summary.
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

# Empirically found 2026-07-31 on a 12-core/14GB machine: 4 concurrent Chrome-driven (tour)
# shards produced real, non-deterministic tour-step failures ("TIMEOUT step failed to complete
# within 10000 ms.", both "element not visible yet" and "element not found yet" flavors) - CPU
# contention between browsers slowing rendering/navigation past the tour engine's fixed 10s
# step timeout, not a script bug (the identical shard split runs clean sequentially, and CI
# never hits this since every one of its shards gets its own dedicated runner). Dropping
# concurrency further (3, then 2) measurably reduced but never fully eliminated the flakiness
# on this one machine, and each drop also cost real wall-clock time (more total shards means
# more clone overhead and less real parallelism) - hence the retry-once policy above instead of
# chasing a concurrency value that may not exist on every machine. These ratios are being tuned
# empirically here, not a generally proven formula - tune down further if flakiness still shows
# up on a given machine, or up if it comfortably handles more (worth re-testing before trusting
# a higher value blindly - this box may be more resource-contended than typical dev hardware,
# being a shared/virtualized container rather than dedicated physical cores).
CORES_PER_CHROME_SHARD = 6
GB_PER_CHROME_SHARD = 3


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


def main():
    shards = compute_shards()
    chrome_shard_count = sum(1 for s in shards if s['needs_chrome'])
    limit, cpu, ram_gb = max_concurrent_chrome_shards(chrome_shard_count)

    print(f"Detected {cpu} CPU core(s), {ram_gb:.1f} GB available RAM.")
    print(f"Running {len(shards) - chrome_shard_count} non-browser shard(s) immediately, plus "
          f"up to {limit} of {chrome_shard_count} browser-tour shard(s) at a time.")

    work_dir = Path(tempfile.mkdtemp(prefix="ems_test_shards_"))
    runner = ShardBatchRunner(work_dir)
    try:
        results = {}  # name -> (ok, text, match, retried)
        for shard_run in runner.run(shards, limit):
            ok, text, match = shard_passed(shard_run)
            results[shard_run.shard['name']] = (ok, text, match, False)

        failed_shards = [s for s in shards if not results[s['name']][0]]
        if failed_shards:
            names = ', '.join(s['name'] for s in failed_shards)
            print(f"\n{len(failed_shards)} shard(s) failed on the first attempt: {names}")
            print("Retrying them once, fresh - local runs tolerate a resource-contention "
                  "flake retried clean; CI never retries, a first-try CI failure is real.")
            for shard_run in runner.run(failed_shards, limit):
                ok, text, match = shard_passed(shard_run)
                results[shard_run.shard['name']] = (ok, text, match, True)

        overall_ok = True
        retried_but_passed = []
        for shard in shards:
            ok, text, match, retried = results[shard['name']]
            print(f"\n===== shard: {shard['name']}{' (retry)' if retried else ''} =====")
            print(text)
            if ok:
                if retried:
                    retried_but_passed.append(shard['name'])
                continue
            overall_ok = False
            label = ("no clean result line found" if not match else
                     f"{match.group(1)} failed, {match.group(2)} error(s)")
            attempts = "after a retry" if retried else "on the first attempt"
            print(f"===== shard {shard['name']}: FAILED {attempts} ({label}) =====")

        if retried_but_passed:
            print(f"\nNOTE: {', '.join(retried_but_passed)} only passed after a retry - "
                  "if this keeps happening, this machine's CORES_PER_CHROME_SHARD/"
                  "GB_PER_CHROME_SHARD (run_sharded_tests.py) may need to be more conservative.")

        return 0 if overall_ok else 1
    finally:
        runner.cleanup()
        subprocess.run(f"rm -rf {work_dir}", shell=True)


if __name__ == '__main__':
    sys.exit(main())
