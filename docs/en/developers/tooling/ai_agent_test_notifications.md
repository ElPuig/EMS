# AI agent proactive notifications when running inside a container

An AI coding agent (e.g. Claude Code) working in this repo notifies you for exactly three reasons (see the project's `CLAUDE.md`, under *Development scripts*):

1. **A test launch that actually needs the browser-tab close/refresh** — right when it runs the full, unscoped `./test.sh`, or a scoped run of a `*Tour`/`HttpCase` class, so you know to close or refresh an open Odoo browser tab before the run starts. A scoped run of a plain `TransactionCase`-only class doesn't spin up a real browser at all, so it deliberately stays silent (changed 2026-08-01 — it used to fire unconditionally for every `test.sh` invocation; the developer found that too noisy once most day-to-day runs are scoped, non-tour classes).
2. **Task completion** — once it has finished everything you asked for in the current task, so you know it's ready to come back and review, even if you stepped away while it worked.
3. **Blocked waiting for your input** — an `AskUserQuestion` call, or any point where the agent has asked something and has nothing left to do but wait for your reply. Without this, "still working" and "stopped, waiting on you" look identical from outside the chat.

All three are delivered **only** through the host-side file-drop bridge documented below — this project deliberately does not use the agent's own push-notification tool for any of them. That tool proved unreliable in this specific setup (a container reached through an editor's native extension rather than the standalone terminal CLI): it silently self-suppresses when it judges the terminal "active" (wrong for a prompt to go do something in a *different* window), and neither of its normal delivery channels (mobile push, a direct DBus bridge) works here at all — see below. This was tried and abandoned; don't re-attempt it.

## Why the agent's own notification channels don't work in a container

- **Mobile push (Remote Control) is CLI-only.** It is not exposed anywhere in the VSCode native extension — no settings entry, no UI toggle, no `remote-control` subcommand if the standalone `claude` binary isn't separately installed in the container. There is currently no workaround; this is a product limitation, not a misconfiguration (tracked upstream as a feature request).
- **A direct DBus bridge to the host session bus is normally not viable in an *unprivileged* container.** These containers remap UIDs: the host user's UID (e.g. `1000`) is not in the container's mapped ID range, so a bind-mounted `/run/user/<uid>/bus` shows up owned by `nobody` inside the container, and the container's own root maps to some other, unrelated host UID. DBus's authentication handshake rejects the mismatch (`Did not receive a reply`). Confirm this quickly rather than debugging blind:
  ```bash
  dbus-send --session --dest=org.freedesktop.Notifications --type=method_call \
    --print-reply /org/freedesktop/Notifications org.freedesktop.Notifications.GetServerInformation
  ```
  A `ServiceUnknown`/auth failure here means this path is a dead end without deeper `raw.idmap` container surgery, which isn't worth it just for a notification.

## The fallback: a host-side file-drop bridge

Since a shared plain directory sidesteps the DBus UID problem entirely (`notify-send` only needs to run natively in the *host* user's own desktop session — no namespace involved), the working setup is:

```mermaid
sequenceDiagram
    participant Hook as Claude Code hook (PreToolUse/Bash, in container)
    participant Dir as Shared directory (bind mount)
    participant Watcher as Host watcher script (systemd --user)
    participant Desktop as Host desktop (notify-send + sound)

    Hook->>Dir: writes a trigger file when a Bash command contains "test.sh"
    Watcher->>Dir: inotifywait -m -e create
    Dir-->>Watcher: new file event
    Watcher->>Desktop: notify-send + sound
    Watcher->>Dir: rm the trigger file
```

### 1. Host: shared directory

```bash
mkdir -p ~/claude-notify
chmod 1777 ~/claude-notify   # world-writable + sticky bit: the container's remapped root needs write access
sudo apt install inotify-tools libnotify-bin
```

### 2. Host → container bind mount

Adapt to whichever tool manages the container. The container's own hostname is **not** necessarily its instance name — confirm the real instance name first (`incus list`, `docker ps`, etc.) rather than assuming.

```bash
# Incus/LXD
incus config device add <instance-name> notify-drop disk \
  source=/home/<user>/claude-notify path=/mnt/claude-notify

# raw LXC: add to the container's config file, then restart the container
# lxc.mount.entry = /home/<user>/claude-notify mnt/claude-notify none bind,create=dir 0 0

# Docker: add a bind mount
# -v /home/<user>/claude-notify:/mnt/claude-notify
```

### 3. Host: watcher script, run as your own user (never `sudo`)

`sudo` breaks this two ways at once: `~` expands to `/root` instead of your home directory inside the script, and `notify-send` run as `root` has no access to your real desktop session's DBus/display.

```bash
#!/bin/bash
# ~/claude-notify-watch.sh
mkdir -p ~/claude-notify
inotifywait -m -e create --format '%f' ~/claude-notify | while read -r f; do
  msg="$(cat ~/claude-notify/"$f" 2>/dev/null)"
  notify-send "Claude Code" "$msg"
  canberra-gtk-play -i dialog-information 2>/dev/null || \
    paplay /usr/share/sounds/freedesktop/stereo/dialog-information.oga 2>/dev/null
  rm -f ~/claude-notify/"$f"
done
```

Run it as a `systemd --user` service so it survives logout/login and doesn't need relaunching after every reboot:

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/claude-notify-watch.service << 'EOF'
[Unit]
Description=AI agent notify watcher (container bridge)

[Service]
ExecStart=/home/<user>/claude-notify-watch.sh
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now claude-notify-watch.service
```

Check with `systemctl --user status claude-notify-watch.service` — `active (running)`. Before assuming something's broken, check for a duplicated watcher first (`ps aux | grep claude-notify-watch`): a second instance running alongside the systemd-managed one fires every notification twice.

### 4. Container: Claude Code hook

Two pieces, both **user-level** (not the project's checked-in `.claude/settings.json` — paths/username here are specific to one developer's machine):

**a) The decision script**, `/root/.claude/hooks/ems-test-notify.sh` — reads the Bash command from stdin and only writes a trigger file when the run would actually exercise a tour/`HttpCase` test (checking the class name, if any, against `tests/*_tour.py`):

```bash
#!/bin/bash
REPO=/root/myModules/ems

# The Bash tool's command is very often multi-line (e.g. a leading "cd ..." line before the
# actual "./test.sh ..." line) - `read -r` only ever captures the FIRST line, which silently
# broke this exact case (confirmed 2026-08-01: a "cd /root/myModules/ems\n./test.sh ..."
# command produced no notification at all). `cmd=$(cat)` reads the whole stdin payload instead.
cmd=$(cat)
case "$cmd" in
    *test.sh*) ;;
    *) exit 0 ;;
esac

# Find the specific line that actually invokes test.sh (not necessarily the first line of the
# command), then extract whatever follows "test.sh" on THAT line as the first argument.
line=$(echo "$cmd" | grep -m1 'test\.sh')
arg=$(echo "$line" | sed -n 's/.*test\.sh[[:space:]]*//p' | awk '{print $1}' | tr -d "'\"")

notify=false
if [ -z "$arg" ]; then
    notify=true  # no argument: the full, sharded suite - always includes the tour shards
elif [[ "$arg" == /* || "$arg" == -* ]]; then
    notify=true  # an explicit --test-tags expression - can't cheaply tell if it includes a
                 # tour shard, so err on the side of notifying rather than risk a silent hang
else
    class="${arg%%.*}"  # drop a trailing ".test_method_name" if present
    # Anchored on "class Name(" - a plain substring match would wrongly let e.g. "TestGroup"
    # match inside "class TestGroupTour(", since "TestGroup" is a textual prefix of it.
    if grep -rlE "class ${class}\(" "$REPO"/tests/*_tour.py >/dev/null 2>&1; then
        notify=true
    fi
fi

if [ "$notify" = true ]; then
    echo "$(date +%H:%M:%S) EMS: launching test (close/refresh your Odoo tab) -> $cmd" \
        > /mnt/claude-notify/test-$(date +%s%N).txt
fi
```

Make it executable: `chmod +x /root/.claude/hooks/ems-test-notify.sh`.

**b) The hook wiring**, in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "jq -r '.tool_input.command' | /root/.claude/hooks/ems-test-notify.sh 2>/dev/null || true"
      }]
    }]
  }
}
```

Being a plain filesystem write triggered by the hook (not a call to the agent's notification tool), it's also not subject to that tool's own "you're probably still looking at this" self-suppression.

**When testing changes to the script, never pipe sample commands through it with the real `/mnt/claude-notify` path live** — each matching invocation writes a real trigger file, which the host watcher picks up and turns into a real desktop notification (this happened once, 2026-08-01: rapid-fire manual tests of the anchoring logic spammed several real notifications before the mistake was caught). Redirect to a scratch path while iterating, and only re-point at the real bridge for the final, one-time end-to-end check described in *Verifying each layer* below.

**Test with a genuinely multi-line command, not just single-line strings.** The `read -r cmd` → `cmd=$(cat)` bug above (2026-08-01) only showed up because every manual test during development happened to be a single-line string; the real Bash tool call that first exposed it was two lines (`cd /root/myModules/ems` then `./test.sh ...` on the next line), and `read -r` silently discarded everything past the first line with no error. A quick way to reproduce this class of bug: `printf 'cd /some/dir\n./test.sh TestSomethingTour' | ./ems-test-notify.sh` (pointed at a scratch path, per the note above) rather than `echo "./test.sh TestSomethingTour" | ...`.

### Covering triggers 2 and 3 too

The hook above only covers trigger 1 (any test launch), because it keys off a recognisable Bash command (`test.sh`). Triggers 2 (task completion) and 3 (blocked on your input) have no equivalent command to match on — neither "all requested work is done" nor "I just asked a question and am now waiting" is a tool call a `PreToolUse` hook can see coming. So the agent writes directly into the shared drop directory itself for both, e.g.:

```bash
echo "$(date +%H:%M:%S) EMS: task done — <short summary>" > /mnt/claude-notify/done-$(date +%s%N).txt
echo "$(date +%H:%M:%S) EMS: waiting on you — <short summary of what's being asked>" > /mnt/claude-notify/waiting-$(date +%s%N).txt
```

The same watcher (step 3 above) picks either up exactly like a hook-triggered file — there's nothing container-specific to add on the watcher or bind-mount side, this is purely about how the *agent* gets a message into the directory when there's no hook to rely on.

## Verifying each layer

Test bottom-up before declaring it done:
1. Write a file into the shared directory from inside the container (`echo test > /mnt/claude-notify/x.txt`) — confirms the bind mount and permissions.
2. Confirm the watcher consumes and deletes it, and that `notify-send`/sound actually reach the desktop.
3. Trigger the hook for real (a Bash command containing `test.sh`) — confirms the hook JSON is well-formed and wired to the right matcher.

## When to offer this

This bridge is already built and verified for the primary developer on this project — don't rebuild it from scratch; only revisit the steps above if a specific layer breaks (see *Verifying each layer*). For any other developer who mentions they're not noticing test-hang reminders or task-completion notifications, and their agent session is running inside a container rather than a bare-metal/VM terminal CLI install, that combination is the specific signature this fix addresses — offer to set it up rather than waiting to be asked, and rather than falling back to the agent's own push-notification tool (see the intro above for why that doesn't work here).
