#!/usr/bin/env bash
# Claude Code statusLine command
# Line 1: user@host:cwd (branch) [worktree]
# Line 2: [Model] ctx:N%  rate-limits  PR#N  session-name  vim-mode

input=$(cat)

user=$(whoami)
host=$(hostname -s)
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
[ -z "$cwd" ] && cwd=$(pwd)

# Shorten /mnt/d/Documents/Code/ -> ~/code for brevity
cwd="${cwd/#\/mnt\/d\/Documents\/Code\//\~\/code\/}"
cwd="${cwd%/}"

model=$(echo "$input" | jq -r '.model.display_name // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
vim_mode=$(echo "$input" | jq -r '.vim.mode // empty')
pr_num=$(echo "$input" | jq -r '.pr.number // empty')
pr_state=$(echo "$input" | jq -r '.pr.review_state // empty')
session_name=$(echo "$input" | jq -r '.session_name // empty')
worktree_name=$(echo "$input" | jq -r '.worktree.name // empty')
five_h=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
seven_d=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

# Git branch: prefer worktree.branch, then live git
branch=$(echo "$input" | jq -r '.worktree.branch // empty')
if [ -z "$branch" ]; then
  real_cwd="${cwd/#\~\/code\///mnt/d/Documents/Code/}"
  branch=$(git -C "$real_cwd" --no-optional-locks rev-parse --abbrev-ref HEAD 2>/dev/null || true)
fi

# ── Line 1: user@host:cwd (branch) [worktree] ──────────────────────────────
printf '\033[01;32m%s@%s\033[00m' "$user" "$host"
printf ':\033[01;34m%s\033[00m' "$cwd"

if [ -n "$branch" ] && [ "$branch" != "HEAD" ]; then
  printf ' \033[00;35m(%s)\033[00m' "$branch"
fi

if [ -n "$worktree_name" ]; then
  printf ' \033[00;33m[wt:%s]\033[00m' "$worktree_name"
fi

printf '\n'

# ── Line 2: [Model] ctx:N%  limits  PR  session  vim ───────────────────────
line2=""

if [ -n "$model" ]; then
  line2+=$(printf '\033[00;36m[%s]\033[00m' "$model")
fi

if [ -n "$used" ]; then
  # Color: green <50%, yellow 50-79%, red >=80%
  used_int=$(printf '%.0f' "$used")
  if [ "$used_int" -ge 80 ]; then
    ctx_color='\033[01;31m'
  elif [ "$used_int" -ge 50 ]; then
    ctx_color='\033[00;33m'
  else
    ctx_color='\033[00;32m'
  fi
  line2+=$(printf " ${ctx_color}ctx:%d%%\033[00m" "$used_int")
fi

# Rate-limit badges (only shown when present — Claude.ai subscribers)
rl_str=""
if [ -n "$five_h" ]; then
  rl_str+=$(printf '5h:%.0f%%' "$five_h")
fi
if [ -n "$seven_d" ]; then
  [ -n "$rl_str" ] && rl_str+=" "
  rl_str+=$(printf '7d:%.0f%%' "$seven_d")
fi
if [ -n "$rl_str" ]; then
  line2+=$(printf ' \033[00;33m[%s]\033[00m' "$rl_str")
fi

# PR badge (green=approved, yellow=pending/open, red=changes_requested, grey=draft)
if [ -n "$pr_num" ]; then
  case "$pr_state" in
    approved)          pr_color='\033[01;32m' ;;
    changes_requested) pr_color='\033[01;31m' ;;
    draft)             pr_color='\033[00;37m' ;;
    *)                 pr_color='\033[01;33m' ;;
  esac
  line2+=$(printf " ${pr_color}PR#%s\033[00m" "$pr_num")
fi

# Session name (only when /rename has been used)
if [ -n "$session_name" ]; then
  line2+=$(printf ' \033[00;37m"%s"\033[00m' "$session_name")
fi

# Vim mode (bold white)
if [ -n "$vim_mode" ]; then
  line2+=$(printf ' \033[01;37m[%s]\033[00m' "$vim_mode")
fi

printf '%s\n' "$line2"
