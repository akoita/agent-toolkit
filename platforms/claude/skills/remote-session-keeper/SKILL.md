---
name: remote-session-keeper
description: >-
  Persist and recover Claude Code sessions on a remote host so the desktop GUI
  losing them on restart never costs you your conversation history. Use when
  working over SSH — especially the Windows desktop app connected into WSL or a
  remote box — and a session's content disappears after the GUI is closed and
  reopened, or when the user wants to set up tmux-backed persistent remote
  sessions, or asks how to resume/continue a session that "vanished". It
  installs a per-project tmux launcher (`claude-persist.sh`) so remote sessions
  survive client disconnects, and documents the `claude --continue` /
  `--resume` recovery path plus where transcripts live on the remote host. Do
  NOT use for purely local projects — the desktop app restores those on its
  own — or to recover a session on a different machine (transcripts are
  per-host, per-directory).
---

# Remote Session Keeper — never lose a remote Claude Code session again

## The problem this works around

The Claude Code **desktop GUI** does not restore a **remote (SSH) session's**
history when the app is closed and relaunched. Local projects restore fine
because their transcripts live on the client machine; a remote session's
transcript lives on the **remote host** (e.g. the WSL/Ubuntu box you SSH into),
under `~/.claude/projects/<project-dir-hash>/<session-id>.jsonl`, and the client
does not re-attach to it after a restart. The session still shows in the list,
but its content is gone from the GUI.

This is a documented client-side limitation, tracked as
[anthropics/claude-code#49790](https://github.com/anthropics/claude-code/issues/49790).
A skill cannot patch the desktop app — but it **can** make the loss a non-event:
keep the remote session alive across disconnects, and give a reliable recovery
path when one was lost.

**Honest scope:** this is *prevention + fast recovery*, not a GUI fix. The
transcript is never actually lost — it is always on the remote host — so even
without this skill the history is recoverable from a terminal.

## When to reach for this

- User works over SSH (commonly the Windows desktop app → WSL) and a session's
  content disappears after the GUI is stopped and restarted.
- User asks how to resume, continue, or recover a session that "vanished".
- User wants remote sessions to survive disconnects going forward.

Skip it for purely local projects, and note that recovery only works on the
**same host** and **same project directory** that produced the session.

## What to do

Work in the remote host's shell (where `claude` and the project live — for a
Windows-desktop-into-WSL setup, that is the **WSL terminal**, not PowerShell).

### 1. Immediate recovery of a lost session

The transcript is on the remote host, so resume it from a terminal:

```bash
cd /path/to/the/project      # the SAME directory the session ran in
claude --continue            # resume the most recent session for this dir
# or, to choose from a list:
claude --resume
```

If the user is unsure which directory, list what exists:

```bash
ls -t ~/.claude/projects/*/ 2>/dev/null | head    # most-recent transcripts first
```

`--continue` / `--resume` read the local (remote-host) transcript directly and
reattach the full context — independent of the GUI.

### 2. Prevent it recurring — tmux-backed persistent sessions

Wrap `claude` in a per-project tmux session so closing the desktop app (or
dropping the SSH connection) leaves the session running on the host. Install the
bundled launcher on the remote host:

```bash
# from this skill directory on the remote host
install -m 0755 scripts/claude-persist.sh ~/.local/bin/claude-persist
# ensure ~/.local/bin is on PATH (add to ~/.bashrc / ~/.zshrc if needed):
#   export PATH="$HOME/.local/bin:$PATH"
```

Then start Claude Code through it, from the project directory:

```bash
cd /path/to/the/project
claude-persist               # create-or-attach a persistent session for this dir
```

- Detach any time with the tmux prefix then `d` (default `Ctrl-b d`) — the
  session keeps running on the host.
- Reconnect later (new SSH login, or a fresh desktop-app terminal) and run
  `claude-persist` again from the same directory: it re-attaches to the live
  session, full history intact.
- `claude-persist --list` shows the running keeper sessions.
- It is idempotent and derives the tmux session name from the project directory,
  so each project gets its own persistent session; re-running from that
  directory **attaches to the live session** rather than starting a second one.
- With no arguments it starts a fresh `claude`. To resume a prior session in a
  new keeper (e.g. after a host reboot killed the tmux server), pass the flag
  through: `claude-persist --continue` or `claude-persist --resume`.

Requires `tmux` on the remote host (`sudo apt-get install -y tmux` on
Debian/Ubuntu/WSL). The script fails clearly if `tmux` or `claude` is missing.

### 3. Optional: a shell alias

Suggest, but do not silently write, an alias so persistence is the default:

```bash
# in ~/.bashrc or ~/.zshrc on the remote host
alias claude='claude-persist'
```

Only add this if the user agrees — some users want plain `claude` for one-off
runs. Preview the exact line before editing their shell rc.

## Caveats

- **Same host, same directory.** Session lookup is per-host and per-directory;
  you cannot recover a remote session from a different machine or a moved repo.
- **tmux must run on the remote host**, not the Windows client — the whole point
  is that the process outlives the client.
- This does not change how Claude Code authenticates or bills; it only changes
  where the process runs.
- Track the upstream fix at
  [anthropics/claude-code#49790](https://github.com/anthropics/claude-code/issues/49790);
  retire this workaround once the desktop app restores remote sessions natively.
