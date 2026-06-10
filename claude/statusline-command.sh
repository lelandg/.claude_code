#!/usr/bin/env bash
# Claude Code statusLine command
# Derived from ~/.bashrc PS1: bold green user@host, colon, bold blue cwd
# Plus Claude Code session info (model, context usage, git branch, vim mode, PR)
# Plus messaging service indicators (Discord, Telegram) when connected

input=$(cat)

user=$(whoami)
host=$(hostname -s)
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
[ -z "$cwd" ] && cwd=$(pwd)

# Substitute /mnt/d/Documents/Code/ -> ~/code for brevity
cwd="${cwd/#\/mnt\/d\/Documents\/Code\//\~\/code\/}"
# Trim trailing slash introduced by substitution when it's exactly the base path
cwd="${cwd%/}"

model=$(echo "$input" | jq -r '.model.display_name // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
vim_mode=$(echo "$input" | jq -r '.vim.mode // empty')
pr_num=$(echo "$input" | jq -r '.pr.number // empty')
pr_state=$(echo "$input" | jq -r '.pr.review_state // empty')
branch=$(echo "$input" | jq -r '.worktree.branch // empty')
# Fall back to git branch when not in a worktree session
if [ -z "$branch" ]; then
  branch=$(git -C "${cwd/#\~\/code\///mnt/d/Documents/Code/}" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
fi

# Line 1: Bold green user@host, colon, bold blue cwd, git branch
printf '\033[01;32m%s@%s\033[00m' "$user" "$host"
printf ':\033[01;34m%s\033[00m' "$cwd"

if [ -n "$branch" ] && [ "$branch" != "HEAD" ]; then
  printf ' \033[00;35m(%s)\033[00m' "$branch"
fi

printf '\n'

# Line 2: Model, context %, PR badge, vim mode — stays visible even when path is long
line2=""
if [ -n "$model" ]; then
  line2+=$(printf '\033[00;36m[%s]\033[00m' "$model")
fi

if [ -n "$used" ]; then
  line2+=$(printf ' \033[00;33mctx:%.0f%%\033[00m' "$used")
fi

# Open PR badge (green=approved, yellow=pending, red=changes_requested, white=draft/open)
if [ -n "$pr_num" ]; then
  case "$pr_state" in
    approved)          pr_color='\033[01;32m' ;;
    changes_requested) pr_color='\033[01;31m' ;;
    draft)             pr_color='\033[00;37m' ;;
    *)                 pr_color='\033[01;33m' ;;
  esac
  line2+=$(printf " ${pr_color}PR#%s\033[00m" "$pr_num")
fi

# Vim mode indicator (bold white)
if [ -n "$vim_mode" ]; then
  line2+=$(printf ' \033[01;37m[%s]\033[00m' "$vim_mode")
fi

# Messaging channel indicators — Discord blue 63 (#5865F2), Telegram blue 39 (#2AABEE).
# Shown ONLY while the CURRENT session has the channel attached (live), not merely
# paired. The claude session process that spawned this statusline runs each attached
# channel plugin as a direct child (bun .../claude-plugins-official/<service>/...),
# so walk up our ancestor chain and look for such a child.
channel_live() {
  local pattern="$1" pid=$$ i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d '[:space:]')
    case "$pid" in ''|*[!0-9]*) return 1 ;; esac
    [ "$pid" -le 1 ] && return 1
    if pgrep -P "$pid" -f "$pattern" >/dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}

messaging=""
if channel_live "claude-plugins-official/discord"; then
  messaging+=$(printf '\033[38;5;63mDiscord\033[00m')
fi
if channel_live "claude-plugins-official/telegram"; then
  [ -n "$messaging" ] && messaging+=" "
  messaging+=$(printf '\033[38;5;39mTelegram\033[00m')
fi
# Single "active" suffix, only when at least one channel is shown
[ -n "$messaging" ] && messaging+=$(printf '\033[00;37m active\033[00m')

if [ -n "$messaging" ]; then
  printf '%s %s\n' "$line2" "$messaging"
else
  printf '%s\n' "$line2"
fi
