#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash change_proxy.sh [--shell SHELL] [--clear] [-h|--help]

What it does:
  - Ask for proxy address (format: IP:port or host:port)
  - Print a paste-ready command snippet for the target shell (fish/zsh/bash/etc.)

Options:
  --shell SHELL   Force target shell (fish|zsh|bash|sh|ksh|dash|csh|tcsh). Default: auto-detect parent shell.
  --clear         If proxy input is empty, print commands to unset proxy variables (instead of printing nothing).
  -h, --help      Show this help.

Examples:
  bash change_proxy.sh
  bash change_proxy.sh --shell fish
  bash change_proxy.sh --shell zsh
  bash change_proxy.sh --clear
EOF
}

normalize_shell() {
  local s="${1##*/}"
  case "$s" in
    fish|zsh|bash|sh|ksh|dash|csh|tcsh) printf '%s' "$s" ;;
    *) printf '%s' "bash" ;; # fallback
  esac
}

detect_parent_shell() {
  local parent=""
  parent="$(ps -p "${PPID}" -o comm= 2>/dev/null || true)"
  parent="${parent##*/}"

  case "$parent" in
    fish|zsh|bash|sh|ksh|dash|csh|tcsh)
      printf '%s' "$parent"
      return
      ;;
  esac

  # Fallback to $SHELL if parent process name isn't a shell
  if [[ -n "${SHELL:-}" ]]; then
    printf '%s' "$(normalize_shell "$SHELL")"
  else
    printf '%s' "bash"
  fi
}

escape_for_dq() {
  # Escape for double-quoted strings: \" and \\ are the key ones.
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  printf '%s' "$s"
}

gen_set_cmds() {
  local sh="$1"
  local proxy_raw="$2"
  local proxy
  proxy="$(escape_for_dq "$proxy_raw")"
  local no_proxy_val="localhost,127.0.0.1,::1"

  case "$sh" in
    fish)
      cat <<EOF
# Target shell: fish
# Paste the following lines:
set -gx http_proxy "http://$proxy"
set -gx https_proxy "https://$proxy"
set -gx ftp_proxy "ftp://$proxy"
set -gx socks_proxy "socks://$proxy"
set -gx no_proxy "$no_proxy_val"
EOF
      ;;
    csh|tcsh)
      cat <<EOF
# Target shell: $sh
# Paste the following lines:
setenv http_proxy "http://$proxy"
setenv https_proxy "https://$proxy"
setenv ftp_proxy "ftp://$proxy"
setenv socks_proxy "socks://$proxy"
setenv no_proxy "$no_proxy_val"
EOF
      ;;
    bash|zsh|sh|ksh|dash|*)
      cat <<EOF
# Target shell: $sh
# Paste the following lines:
export http_proxy="http://$proxy"
export https_proxy="https://$proxy"
export ftp_proxy="ftp://$proxy"
export socks_proxy="socks://$proxy"
export no_proxy="$no_proxy_val"
EOF
      ;;
  esac
}

gen_unset_cmds() {
  local sh="$1"
  case "$sh" in
    fish)
      cat <<'EOF'
# Target shell: fish
# Paste the following lines to clear proxy:
set -e http_proxy
set -e https_proxy
set -e ftp_proxy
set -e socks_proxy
set -e no_proxy
EOF
      ;;
    csh|tcsh)
      cat <<'EOF'
# Target shell: csh/tcsh
# Paste the following lines to clear proxy:
unsetenv http_proxy
unsetenv https_proxy
unsetenv ftp_proxy
unsetenv socks_proxy
unsetenv no_proxy
EOF
      ;;
    bash|zsh|sh|ksh|dash|*)
      cat <<'EOF'
# Target shell: sh-family (bash/zsh/etc.)
# Paste the following lines to clear proxy:
unset http_proxy
unset https_proxy
unset ftp_proxy
unset socks_proxy
unset no_proxy
EOF
      ;;
  esac
}

target_shell=""
do_clear=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --shell|-s)
      target_shell="${2:-}"
      shift 2
      ;;
    --clear)
      do_clear=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$target_shell" ]]; then
  target_shell="$(detect_parent_shell)"
else
  target_shell="$(normalize_shell "$target_shell")"
fi

read -r -p "If you need to use a proxy, enter proxy address (format: IP:port), otherwise press Enter to skip: " proxy

if [[ -z "$proxy" ]]; then
  if [[ "$do_clear" -eq 1 ]]; then
    gen_unset_cmds "$target_shell"
  else
    # Print only comments so it's safe even if pasted accidentally
    cat <<EOF
# Target shell: $target_shell
# No proxy entered. Nothing to set.
# Tip: run with --clear to print commands that unset proxy variables.
EOF
  fi
  exit 0
fi

gen_set_cmds "$target_shell" "$proxy"
