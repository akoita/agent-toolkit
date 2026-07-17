#!/usr/bin/env bash
# claude-persist.sh — run Claude Code inside a per-project tmux session so a
# remote (SSH/WSL) session survives the desktop GUI or SSH client disconnecting.
#
# The Claude Code desktop app does not restore a REMOTE session's history when
# it is closed and relaunched (anthropics/claude-code#49790): the transcript
# lives on the remote host, and the client does not re-attach to it. Wrapping
# `claude` in tmux keeps the process — and its live session — alive on the
# remote host across disconnects. Reconnect and you are exactly where you left
# off.
#
# Usage:
#   claude-persist.sh [claude args...]      # create-or-attach for the current dir
#   claude-persist.sh --list                # list this repo's keeper tmux sessions
#   claude-persist.sh --name NAME [args...] # override the derived session name
#
# It is idempotent: if a keeper session for this directory already exists it
# attaches to it; otherwise it creates one, launches `claude` inside, and
# attaches. Detach any time with the tmux prefix then `d` (default: Ctrl-b d) —
# the session keeps running on the host.

set -euo pipefail

if ! command -v tmux >/dev/null 2>&1; then
  echo "claude-persist: tmux is not installed on this host." >&2
  echo "  Debian/Ubuntu/WSL: sudo apt-get install -y tmux" >&2
  echo "  macOS (brew):      brew install tmux" >&2
  exit 127
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "claude-persist: the 'claude' CLI is not on PATH on this host." >&2
  exit 127
fi

# Derive a stable, tmux-safe session name from the current project directory.
# Same directory -> same session name -> reliable create-or-attach.
derive_name() {
  local base
  base="$(basename "$PWD")"
  # tmux session names may not contain '.' or ':'; keep it simple and unique-ish.
  printf 'claude-%s' "$(printf '%s' "$base" | tr -c 'A-Za-z0-9_-' '-')"
}

SESSION=""
case "${1:-}" in
  --list)
    tmux list-sessions 2>/dev/null | grep -E '^claude-' || echo "no keeper sessions running"
    exit 0
    ;;
  --name)
    SESSION="${2:?--name requires a value}"
    shift 2
    ;;
esac
[ -n "$SESSION" ] || SESSION="$(derive_name)"

if tmux has-session -t "=$SESSION" 2>/dev/null; then
  echo "claude-persist: attaching to existing session '$SESSION' (Ctrl-b d to detach)"
  exec tmux attach-session -t "=$SESSION"
fi

echo "claude-persist: starting persistent session '$SESSION' in $PWD (Ctrl-b d to detach)"
# Pass claude + args as DIRECT arguments to tmux so claude runs as the pane's
# own process. A shell string ("claude --continue || claude") does not track
# reliably as the pane process — tmux can leave a bare shell in the pane
# instead — so we avoid the compound form. Any args pass through, so
# `claude-persist --continue` / `--resume` resume a prior session; with no args
# a fresh session starts and then persists across disconnects.
tmux new-session -d -s "$SESSION" -c "$PWD" claude "$@"
exec tmux attach-session -t "=$SESSION"
