#!/bin/bash
set -euo pipefail

# ========================
#  Claude Code + Z.AI interactive config (macOS/Linux)
#  - No Node/Claude install checks
#  - Prompts are VISIBLE while typing (per your request)
#  - Safely merges JSON (requires python3)
# ========================

SCRIPT_NAME="$(basename "$0")"
CONFIG_DIR="$HOME/.claude"
SETTINGS_FILE="$CONFIG_DIR/settings.json"
CLAUDE_JSON_FILE="$HOME/.claude.json"

DEFAULT_BASE_URL="https://open.bigmodel.cn/api/anthropic"
DEFAULT_TIMEOUT_MS="3000000"
DEFAULT_MODEL="default"   # Claude Code model alias (can be "opus"/"sonnet"/"haiku"/"default" etc.)

API_KEY_URL="https://open.bigmodel.cn/usercenter/proj-mgmt/apikeys"

log() { echo "🔹 $*"; }
ok()  { echo "✅ $*"; }
err() { echo "❌ $*" >&2; }

require_python3() {
  if ! command -v python3 >/dev/null 2>&1; then
    err "python3 not found. Please install python3 first, then re-run."
    exit 1
  fi
}

ensure_dir() {
  mkdir -p "$CONFIG_DIR"
}

backup_if_exists() {
  local f="$1"
  if [ -f "$f" ]; then
    local ts
    ts="$(date +"%Y%m%d%H%M%S")"
    cp "$f" "$f.bak.$ts"
    ok "Backup created: $f.bak.$ts"
  fi
}

prompt_with_default() {
  local prompt="$1"
  local def="$2"
  local var
  read -r -p "$prompt [$def]: " var
  if [ -z "$var" ]; then
    echo "$def"
  else
    echo "$var"
  fi
}

main() {
  echo "🚀 Starting $SCRIPT_NAME"
  echo "   (macOS/Linux only)"
  echo

  require_python3
  ensure_dir

  echo "ℹ️  You can get your Z.AI API key from:"
  echo "   $API_KEY_URL"
  echo

  # Visible input (NOT -s)
  read -r -p "🔑 Enter API key (input will be visible): " CC_API_KEY
  if [ -z "${CC_API_KEY}" ]; then
    err "API key cannot be empty."
    exit 1
  fi

  CC_BASE_URL="$(prompt_with_default "🌐 Enter base_url" "$DEFAULT_BASE_URL")"
  CC_MODEL="$(prompt_with_default "🤖 Enter model (alias or full name)" "$DEFAULT_MODEL")"
  CC_TIMEOUT_MS="$(prompt_with_default "⏱  Enter API_TIMEOUT_MS" "$DEFAULT_TIMEOUT_MS")"

  echo
  read -r -p "🧩 Optional: enter ONE GLM model to map opus/sonnet/haiku to (leave blank to keep defaults): " CC_GLM_MAP || true

  echo
  log "Will write:"
  echo "   - $SETTINGS_FILE"
  echo "   - $CLAUDE_JSON_FILE"
  echo "   base_url: $CC_BASE_URL"
  echo "   model:    $CC_MODEL"
  echo "   timeout:  $CC_TIMEOUT_MS"
  if [ -n "${CC_GLM_MAP:-}" ]; then
    echo "   GLM map:  $CC_GLM_MAP (sets ANTHROPIC_DEFAULT_*_MODEL)"
  else
    echo "   GLM map:  (no change)"
  fi
  echo "   api_key:  ****(len=${#CC_API_KEY})"
  echo

  backup_if_exists "$SETTINGS_FILE"
  backup_if_exists "$CLAUDE_JSON_FILE"

  # Export to avoid putting secrets into argv
  export CC_API_KEY CC_BASE_URL CC_MODEL CC_TIMEOUT_MS CC_GLM_MAP SETTINGS_FILE CLAUDE_JSON_FILE

  python3 - <<'PY'
import json, os, sys
from pathlib import Path

settings_path = Path(os.environ["SETTINGS_FILE"]).expanduser()
claude_json_path = Path(os.environ["CLAUDE_JSON_FILE"]).expanduser()

api_key = os.environ["CC_API_KEY"]
base_url = os.environ["CC_BASE_URL"]
model = os.environ["CC_MODEL"]
timeout_ms = os.environ["CC_TIMEOUT_MS"]
glm_map = os.environ.get("CC_GLM_MAP", "").strip()

def load_json(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in {path}: {e}")

def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ----- settings.json -----
settings = load_json(settings_path)
env = settings.get("env")
if not isinstance(env, dict):
    env = {}

# Required by z.ai guide
env["ANTHROPIC_AUTH_TOKEN"] = api_key
env["ANTHROPIC_BASE_URL"] = base_url
env["API_TIMEOUT_MS"] = str(timeout_ms)
env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = 1

# Model config (Claude Code supports settings "model" + env ANTHROPIC_MODEL)
if model and model.strip():
    settings["model"] = model.strip()
    env["ANTHROPIC_MODEL"] = model.strip()

# Optional: Z.AI GLM mapping override (maps Claude aliases to GLM models)
if glm_map:
    env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = glm_map
    env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = glm_map
    env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = glm_map

settings["env"] = env
save_json(settings_path, settings)

# ----- ~/.claude.json -----
cj = load_json(claude_json_path)
cj["hasCompletedOnboarding"] = True
save_json(claude_json_path, cj)

print(f"OK: updated {settings_path}")
print(f"OK: updated {claude_json_path}")
PY

  # Cleanup env (best-effort)
  unset CC_API_KEY CC_BASE_URL CC_MODEL CC_TIMEOUT_MS CC_GLM_MAP SETTINGS_FILE CLAUDE_JSON_FILE

  echo
  ok "Done."
  echo "ℹ️  If changes don't take effect, close all Claude Code sessions and open a new terminal, then run: claude"
}

main "$@"
