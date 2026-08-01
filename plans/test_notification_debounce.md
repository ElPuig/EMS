**Status: not yet implemented — design note only, picked up 2026-08-01, still current as of that date.**

# Debounce test-launch notifications

## Problem

The test-launch notification hook (`/root/.claude/hooks/ems-test-notify.sh`, wired via
`~/.claude/settings.json`'s `PreToolUse`/`Bash` hook — see
`docs/en/developers/tooling/ai_agent_test_notifications.md`) already correctly fires only for
tour/`HttpCase` runs (fixed 2026-08-01), but when several such runs happen in quick succession
(e.g. iterating on a failing tour, upgrade → test → fix → upgrade → test several times in a
row), each one still fires its own desktop notification. The developer flagged this as annoying:
*"si se lanzan muchas seguidas es un tanto molesto."*

## Requested behavior

- Add a debounce/cooldown window (developer's suggestion: **1 minute**) around the **test-launch**
  notification specifically: if another test-launch notification already fired within the last
  60s, skip writing a new trigger file for this one.
- Do **NOT** debounce the other two notification types (task-done, waiting-on-you) — the
  developer explicitly said these can still fire every time, since they don't happen back-to-back
  the way test launches do: *"Si es una notificación de que has terminado o que me estás haciendo
  una pregunta, esas si se pueden acumular, porque no son tan seguidas como las otras."*

## Implementation sketch (not yet built)

In `ems-test-notify.sh`, before writing a `test-*.txt` trigger file:
1. Track the last test-notification time in a small state file (e.g.
   `/root/.claude/hooks/.last-test-notify` — NOT under `/mnt/claude-notify/`, since that directory
   is the trigger-file drop zone the host watcher consumes and deletes from, not a place for
   persistent state).
2. Compare current time (`date +%s`) against the stored timestamp; if the difference is below the
   threshold (60s), skip writing the trigger file entirely (still exit 0 normally).
3. If not skipped (or no state file yet), write the trigger file as today AND update the state
   file with the current timestamp.

Keep the threshold as an easily-tweakable variable at the top of the script (e.g.
`DEBOUNCE_SECONDS=60`) in case the developer wants to adjust it later.

## Testing notes

Follow the same dry-run discipline already documented in
`docs/en/developers/tooling/ai_agent_test_notifications.md` ("When testing changes to the
script, never pipe sample commands through it with the real `/mnt/claude-notify` path live") —
this applies doubly here, since testing debounce logic means firing the script multiple times in
quick succession by design, which is exactly the scenario that would spam real notifications if
tested against the live bridge. Use a scratch path for both the trigger-file directory and the
new last-notified state file while iterating.

## Once implemented

- Update `docs/en/developers/tooling/ai_agent_test_notifications.md`'s hook script listing to
  match.
- Update `CLAUDE.md`'s trigger-1 description if the debounce behavior is worth a one-line mention
  there too.
- Delete this plan file (per the `plans/` convention in `CLAUDE.md` — fold anything still
  relevant into the docs above, then remove the stale plan).
