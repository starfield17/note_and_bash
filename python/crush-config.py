#!/usr/bin/env python3
"""
Crush Configuration Management Tool
For managing provider and model configurations in Crush config files.

Config search order (lowest -> highest precedence):
- ~/.config/crush/crush.json          (global config)
- ~/.local/share/crush/crush.json     (data/ephemeral config; often contains API keys)
- ./crush.json                        (project config; searched upward from CWD)
- ./.crush.json                       (project config; highest precedence)

Supports:
- Interactive mode (default)
- Command line argument mode
- CRUD operations for providers and provider models
- Manage selected models (large/small tiers)

Notes:
- Crush config schema: https://charm.land/crush.json
- Provider config uses `providers` (map) and provider `models` is a list of model objects.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# JSONC Parser (supports JSON with comments)
# ═══════════════════════════════════════════════════════════════════════════════

def strip_jsonc_comments(text: str) -> str:
    """Remove comments from JSONC, keeping valid JSON (including // and /* in strings)."""
    result: List[str] = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(text):
        ch = text[i]

        # Inside string
        if in_string:
            result.append(ch)
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        # String start
        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue

        # Single-line comment //
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue

        # Multi-line comment /* */
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2  # skip */
            continue

        result.append(ch)
        i += 1

    # Remove trailing commas (JSON doesn't allow, but JSONC often does)
    text = "".join(result)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def load_jsonc(filepath: Path) -> dict:
    """Load JSON/JSONC file."""
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    stripped = strip_jsonc_comments(content)
    try:
        return json.loads(stripped) if stripped.strip() else {}
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON parsing error in {filepath}: {e}")
        return {}


def save_json(filepath: Path, data: dict) -> bool:
    """Save JSON file (pretty-printed)."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        return True
    except Exception as e:
        print(f"❌ Save failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration File Paths
# ═══════════════════════════════════════════════════════════════════════════════

def get_global_config_path() -> Path:
    """~/.config/crush/crush.json (or $XDG_CONFIG_HOME/crush/crush.json)"""
    xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg_config) / "crush" / "crush.json"


def get_global_data_config_path() -> Path:
    """~/.local/share/crush/crush.json (or $XDG_DATA_HOME/crush/crush.json)"""
    xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return Path(xdg_data) / "crush" / "crush.json"


def get_project_config_path() -> Path:
    """
    Project config:
      - prefer .crush.json if it exists
      - otherwise use crush.json
    """
    hidden = Path.cwd() / ".crush.json"
    visible = Path.cwd() / "crush.json"
    if hidden.exists():
        return hidden
    return visible


def get_config_path(scope: str) -> Path:
    """Resolve config path based on scope."""
    if scope == "global":
        return get_global_config_path()
    if scope == "data":
        return get_global_data_config_path()
    return get_project_config_path()


# ═══════════════════════════════════════════════════════════════════════════════
# Small TUI helpers
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"


def color(text: str, *styles: str) -> str:
    return "".join(styles) + text + Colors.RESET if sys.stdout.isatty() else text


def print_header(text: str):
    print(f"\n{color('═' * 64, Colors.DIM)}")
    print(f"  {color(text, Colors.BOLD, Colors.CYAN)}")
    print(f"{color('═' * 64, Colors.DIM)}\n")


def prompt(text: str, default: str = None) -> str:
    if default is not None and default != "":
        text = f"{text} [{default}]"
    result = input(f"{color('?', Colors.CYAN)} {text}: ").strip()
    return result if result else (default or "")


def prompt_int(text: str, default: Optional[int] = None) -> Optional[int]:
    default_str = str(default) if default is not None else ""
    result = prompt(text, default_str)
    if not result:
        return None
    try:
        return int(result)
    except ValueError:
        print("⚠️  Invalid number, skipping")
        return None


def prompt_confirm(text: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    result = input(f"{color('?', Colors.YELLOW)} {text} {suffix}: ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes")


def prompt_choice(text: str, choices: List[str], default: int = 0) -> int:
    print(f"\n{color(text, Colors.BOLD)}")
    for i, choice in enumerate(choices):
        marker = "→" if i == default else " "
        print(f"  {color(marker, Colors.GREEN)} {i + 1}. {choice}")

    while True:
        result = input(f"\n{color('?', Colors.CYAN)} Choose [1-{len(choices)}]: ").strip()
        if not result:
            return default
        try:
            idx = int(result) - 1
            if 0 <= idx < len(choices):
                return idx
        except ValueError:
            pass
        print(f"⚠️  Please enter a number between 1-{len(choices)}")


def _parse_kv_pairs(items: Optional[List[str]]) -> Dict[str, str]:
    """
    Parse repeated --header KEY:VALUE or KEY=VALUE arguments.
    """
    headers: Dict[str, str] = {}
    if not items:
        return headers
    for item in items:
        if ":" in item:
            k, v = item.split(":", 1)
        elif "=" in item:
            k, v = item.split("=", 1)
        else:
            print(f"⚠️  Ignoring invalid key/value: {item!r}")
            continue
        k = k.strip()
        v = v.strip()
        if not k:
            print(f"⚠️  Ignoring invalid key/value: {item!r}")
            continue
        headers[k] = v
    return headers


def _mask_secret(val: str) -> str:
    if not val:
        return "-"
    if val.startswith("$"):
        return val  # env var syntax
    if len(val) <= 8:
        return "********"
    return val[:4] + "…" + val[-2:]


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Operations Core
# ═══════════════════════════════════════════════════════════════════════════════

def _make_model_config(
    model_id: str,
    name: Optional[str] = None,
    context_window: Optional[int] = None,
    default_max_tokens: Optional[int] = None,
    can_reason: bool = False,
    supports_attachments: bool = False,
) -> Dict[str, Any]:
    """
    Create a model object with required-ish fields filled.

    Crush's schema includes many required model metadata fields. When you don't
    care about pricing metadata, keeping them at 0 is usually fine.
    """
    ctx = context_window if context_window is not None else 128000
    mx = default_max_tokens if default_max_tokens is not None else 4096

    return {
        "id": model_id,
        "name": name or model_id,
        "cost_per_1m_in": 0,
        "cost_per_1m_out": 0,
        "cost_per_1m_in_cached": 0,
        "cost_per_1m_out_cached": 0,
        "context_window": int(ctx),
        "default_max_tokens": int(mx),
        "can_reason": bool(can_reason),
        "supports_attachments": bool(supports_attachments),
        "options": {},
    }


class CrushConfig:
    """Crush Configuration Manager"""

    SCHEMA_URL = "https://charm.land/crush.json"

    def __init__(self, scope: str = "project"):
        self.scope = scope
        self.path = get_config_path(scope)
        self.data = load_jsonc(self.path)

    def ensure_schema(self):
        if "$schema" not in self.data:
            self.data["$schema"] = self.SCHEMA_URL

    def ensure_provider_section(self):
        if "providers" not in self.data or not isinstance(self.data.get("providers"), dict):
            self.data["providers"] = {}

    def ensure_selected_models_section(self):
        if "models" not in self.data or not isinstance(self.data.get("models"), dict):
            self.data["models"] = {}

    def save(self) -> bool:
        self.ensure_schema()
        return save_json(self.path, self.data)

    # ─────────────────────────────────────────────────────────────────────────
    # Provider Operations
    # ─────────────────────────────────────────────────────────────────────────

    def list_providers(self) -> dict:
        return self.data.get("providers", {})

    def get_provider(self, provider_id: str) -> Optional[dict]:
        return self.data.get("providers", {}).get(provider_id)

    def add_provider(
        self,
        provider_id: str,
        name: Optional[str] = None,
        provider_type: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        disable: Optional[bool] = None,
    ) -> bool:
        self.ensure_provider_section()

        if provider_id in self.data["providers"]:
            print(f"⚠️  Provider '{provider_id}' already exists, use update command to modify")
            return False

        provider_config: Dict[str, Any] = {}
        if name:
            provider_config["name"] = name
        if provider_type:
            provider_config["type"] = provider_type
        if base_url:
            provider_config["base_url"] = base_url
        if api_key:
            provider_config["api_key"] = api_key
        if extra_headers:
            provider_config["extra_headers"] = extra_headers
        if disable is not None:
            provider_config["disable"] = bool(disable)

        self.data["providers"][provider_id] = provider_config
        return self.save()

    def update_provider(
        self,
        provider_id: str,
        name: Optional[str] = None,
        provider_type: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        disable: Optional[bool] = None,
    ) -> bool:
        if provider_id not in self.data.get("providers", {}):
            print(f"❌ Provider '{provider_id}' does not exist")
            return False

        provider = self.data["providers"][provider_id]
        if name is not None:
            if name == "":
                provider.pop("name", None)
            else:
                provider["name"] = name
        if provider_type is not None:
            if provider_type == "":
                provider.pop("type", None)
            else:
                provider["type"] = provider_type
        if base_url is not None:
            if base_url == "":
                provider.pop("base_url", None)
            else:
                provider["base_url"] = base_url
        if api_key is not None:
            if api_key == "":
                provider.pop("api_key", None)
            else:
                provider["api_key"] = api_key
        if extra_headers is not None:
            if not extra_headers:
                provider.pop("extra_headers", None)
            else:
                provider["extra_headers"] = extra_headers
        if disable is not None:
            provider["disable"] = bool(disable)

        return self.save()

    def delete_provider(self, provider_id: str) -> bool:
        if provider_id not in self.data.get("providers", {}):
            print(f"❌ Provider '{provider_id}' does not exist")
            return False

        del self.data["providers"][provider_id]

        # Clean selected models referencing this provider
        models = self.data.get("models", {})
        for tier in ("large", "small"):
            if isinstance(models, dict) and isinstance(models.get(tier), dict):
                if models[tier].get("provider") == provider_id:
                    models.pop(tier, None)

        return self.save()

    # ─────────────────────────────────────────────────────────────────────────
    # Provider Model Operations (provider.models is a list)
    # ─────────────────────────────────────────────────────────────────────────

    def list_models(self, provider_id: str) -> Dict[str, dict]:
        provider = self.get_provider(provider_id)
        if not provider:
            return {}
        models = provider.get("models", [])
        if not isinstance(models, list):
            return {}
        out: Dict[str, dict] = {}
        for m in models:
            if isinstance(m, dict) and "id" in m:
                out[str(m["id"])] = m
        return out

    def get_model(self, provider_id: str, model_id: str) -> Optional[dict]:
        return self.list_models(provider_id).get(model_id)

    def _ensure_provider_models_list(self, provider: dict):
        if "models" not in provider or not isinstance(provider.get("models"), list):
            provider["models"] = []

    def add_model(
        self,
        provider_id: str,
        model_id: str,
        name: Optional[str] = None,
        context_window: Optional[int] = None,
        default_max_tokens: Optional[int] = None,
        can_reason: Optional[bool] = None,
        supports_attachments: Optional[bool] = None,
    ) -> bool:
        provider = self.get_provider(provider_id)
        if not provider:
            print(f"❌ Provider '{provider_id}' does not exist, please add provider first")
            return False

        self._ensure_provider_models_list(provider)
        existing = self.list_models(provider_id)
        if model_id in existing:
            print(f"⚠️  Model '{model_id}' already exists in '{provider_id}'")
            return False

        model_obj = _make_model_config(
            model_id=model_id,
            name=name,
            context_window=context_window,
            default_max_tokens=default_max_tokens,
            can_reason=bool(can_reason) if can_reason is not None else False,
            supports_attachments=bool(supports_attachments) if supports_attachments is not None else False,
        )
        provider["models"].append(model_obj)
        return self.save()

    def update_model(
        self,
        provider_id: str,
        model_id: str,
        name: Optional[str] = None,
        context_window: Optional[int] = None,
        default_max_tokens: Optional[int] = None,
        can_reason: Optional[bool] = None,
        supports_attachments: Optional[bool] = None,
    ) -> bool:
        provider = self.get_provider(provider_id)
        if not provider:
            print(f"❌ Provider '{provider_id}' does not exist")
            return False

        self._ensure_provider_models_list(provider)
        found = None
        for m in provider["models"]:
            if isinstance(m, dict) and str(m.get("id")) == model_id:
                found = m
                break
        if not found:
            print(f"❌ Model '{model_id}' does not exist in '{provider_id}'")
            return False

        if name is not None and name != "":
            found["name"] = name
        if context_window is not None:
            found["context_window"] = int(context_window)
        if default_max_tokens is not None:
            found["default_max_tokens"] = int(default_max_tokens)
        if can_reason is not None:
            found["can_reason"] = bool(can_reason)
        if supports_attachments is not None:
            found["supports_attachments"] = bool(supports_attachments)

        # Ensure required fields exist (best-effort)
        for k, v in _make_model_config(model_id=model_id, name=found.get("name", model_id)).items():
            found.setdefault(k, v)

        return self.save()

    def delete_model(self, provider_id: str, model_id: str) -> bool:
        provider = self.get_provider(provider_id)
        if not provider:
            print(f"❌ Provider '{provider_id}' does not exist")
            return False

        self._ensure_provider_models_list(provider)
        before = len(provider["models"])
        provider["models"] = [m for m in provider["models"] if not (isinstance(m, dict) and str(m.get("id")) == model_id)]
        after = len(provider["models"])
        if before == after:
            print(f"❌ Model '{model_id}' does not exist in '{provider_id}'")
            return False

        # Clean selected models referencing this provider/model
        models = self.data.get("models", {})
        for tier in ("large", "small"):
            if isinstance(models, dict) and isinstance(models.get(tier), dict):
                if models[tier].get("provider") == provider_id and models[tier].get("model") == model_id:
                    models.pop(tier, None)

        return self.save()

    # ─────────────────────────────────────────────────────────────────────────
    # Selected Model (tier) Operations
    # ─────────────────────────────────────────────────────────────────────────

    def get_selected_model(self, tier: str) -> Optional[dict]:
        models = self.data.get("models", {})
        if not isinstance(models, dict):
            return None
        v = models.get(tier)
        return v if isinstance(v, dict) else None

    def set_selected_model(self, tier: str, provider_id: str, model_id: str) -> bool:
        tier = tier.lower()
        if tier not in ("large", "small"):
            print("❌ Tier must be 'large' or 'small'")
            return False

        # Validate provider/model existence (best-effort)
        provider = self.get_provider(provider_id)
        if not provider:
            print(f"❌ Provider '{provider_id}' does not exist")
            return False
        if model_id not in self.list_models(provider_id):
            print(f"⚠️  Model '{model_id}' not found under provider '{provider_id}'. "
                  f"Crush may ignore this selection until the model exists.")
            # Still allow writing selection

        self.ensure_selected_models_section()
        self.data["models"][tier] = {"provider": provider_id, "model": model_id}
        return self.save()

    def clear_selected_model(self, tier: str) -> bool:
        tier = tier.lower()
        if tier not in ("large", "small"):
            print("❌ Tier must be 'large' or 'small'")
            return False
        if "models" in self.data and isinstance(self.data["models"], dict):
            self.data["models"].pop(tier, None)
        return self.save()


# ═══════════════════════════════════════════════════════════════════════════════
# Pretty print
# ═══════════════════════════════════════════════════════════════════════════════

def print_config_summary(config: CrushConfig):
    scope_text = {"project": "Project", "global": "Global", "data": "Data"}.get(config.scope, config.scope)
    print(f"📁 Config location: {color(str(config.path), Colors.BLUE)} ({scope_text})")

    providers = config.list_providers()
    print(f"📦 Provider count: {color(str(len(providers)), Colors.YELLOW)}")

    for tier in ("large", "small"):
        sm = config.get_selected_model(tier)
        if sm:
            print(f"🎯 {tier} model: {color(sm.get('provider','?') + '/' + sm.get('model','?'), Colors.GREEN)}")
    print()


def print_provider(provider_id: str, provider: dict, indent: int = 0):
    prefix = "  " * indent
    print(f"{prefix}{color('◆', Colors.GREEN)} {color(provider_id, Colors.BOLD, Colors.YELLOW)}")
    print(f"{prefix}  Name:   {provider.get('name', '-')}")
    print(f"{prefix}  Type:   {color(str(provider.get('type', 'openai')), Colors.DIM)}")
    if provider.get("base_url"):
        print(f"{prefix}  URL:    {color(str(provider.get('base_url')), Colors.BLUE)}")
    if provider.get("api_key"):
        print(f"{prefix}  APIKey: {color(_mask_secret(str(provider.get('api_key'))), Colors.DIM)}")
    if provider.get("disable") is True:
        print(f"{prefix}  Disabled: {color('true', Colors.RED)}")

    headers = provider.get("extra_headers", {})
    if isinstance(headers, dict) and headers:
        print(f"{prefix}  Headers: {color(str(len(headers)), Colors.DIM)}")

    models = provider.get("models", [])
    if isinstance(models, list) and models:
        print(f"{prefix}  Models ({len(models)}):")
        for m in models:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("id", "-"))
            mname = str(m.get("name", mid))
            ctx = m.get("context_window")
            mx = m.get("default_max_tokens")
            meta = []
            if ctx is not None:
                meta.append(f"ctx:{ctx}")
            if mx is not None:
                meta.append(f"max:{mx}")
            meta_str = f" ({', '.join(meta)})" if meta else ""
            print(f"{prefix}    • {color(mid, Colors.MAGENTA)}: {mname}{color(meta_str, Colors.DIM)}")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# Interactive operations
# ═══════════════════════════════════════════════════════════════════════════════

def interactive_view_config(config: CrushConfig):
    print_header("Current Configuration")
    print_config_summary(config)
    providers = config.list_providers()
    if providers:
        print(f"{color('Providers:', Colors.BOLD)}\n")
        for provider_id, provider in providers.items():
            print_provider(provider_id, provider)
    else:
        print(f"{color('(No provider configured)', Colors.DIM)}\n")


def interactive_add_provider(config: CrushConfig):
    print_header("Add New Provider")

    provider_id = prompt("Provider ID (e.g., myprovider)")
    if not provider_id:
        print("❌ ID cannot be empty")
        return

    name = prompt("Display name", provider_id.title())
    provider_type = prompt("Provider type (openai|openai-compat|anthropic|gemini|azure|vertexai)", "openai-compat")
    base_url = prompt("API Base URL (e.g., https://api.example.com/v1)", "")
    api_key = prompt("API key (or $ENV_VAR, leave empty to skip)", "")
    headers_raw = prompt("Extra headers (optional, KEY:VALUE;KEY2:VALUE2)", "")

    headers = {}
    if headers_raw:
        for part in headers_raw.split(";"):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                k, v = part.split(":", 1)
                headers[k.strip()] = v.strip()

    if config.add_provider(
        provider_id,
        name=name or None,
        provider_type=provider_type or None,
        base_url=base_url or None,
        api_key=api_key or None,
        extra_headers=headers or None,
    ):
        print(f"\n✅ Provider '{provider_id}' added successfully!")

        if prompt_confirm("Add a model to this provider now?", default=True):
            interactive_add_model(config, provider_id_hint=provider_id)


def interactive_add_model(config: CrushConfig, provider_id_hint: Optional[str] = None):
    print_header("Add New Model (to a Provider)")

    providers = config.list_providers()
    if not providers:
        print("❌ No available provider. Please add a provider first.")
        return

    provider_ids = list(providers.keys())
    if provider_id_hint and provider_id_hint in provider_ids:
        provider_id = provider_id_hint
    else:
        idx = prompt_choice("Select Provider:", provider_ids)
        provider_id = provider_ids[idx]

    model_id = prompt("Model ID (e.g., gpt-4o)")
    if not model_id:
        print("❌ Model ID cannot be empty")
        return

    name = prompt("Display name", model_id)
    context_window = prompt_int("Context window (tokens)", 128000)
    default_max_tokens = prompt_int("Default max tokens (output)", 4096)
    can_reason = prompt_confirm("Supports reasoning mode?", default=False)
    supports_attachments = prompt_confirm("Supports image attachments?", default=False)

    if config.add_model(
        provider_id,
        model_id,
        name=name or None,
        context_window=context_window,
        default_max_tokens=default_max_tokens,
        can_reason=can_reason,
        supports_attachments=supports_attachments,
    ):
        print(f"\n✅ Model '{model_id}' added to '{provider_id}' successfully!")


def interactive_update_provider(config: CrushConfig):
    print_header("Modify Provider")

    providers = config.list_providers()
    if not providers:
        print("❌ No provider to modify")
        return

    provider_ids = list(providers.keys())
    idx = prompt_choice("Select Provider to modify:", provider_ids)
    provider_id = provider_ids[idx]
    provider = providers[provider_id]

    print("\nCurrent configuration:")
    print_provider(provider_id, provider)

    name = prompt("New name (leave empty to keep unchanged)", provider.get("name", ""))
    provider_type = prompt("New type (leave empty to keep unchanged)", provider.get("type", ""))
    base_url = prompt("New Base URL (leave empty to keep unchanged)", provider.get("base_url", ""))
    api_key = prompt("New API key (or $ENV_VAR; leave empty to keep unchanged)", provider.get("api_key", ""))
    headers_raw = prompt("New headers (KEY:VALUE;...; leave empty to keep unchanged)", "")

    headers = None
    if headers_raw:
        hdr = {}
        for part in headers_raw.split(";"):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                k, v = part.split(":", 1)
                hdr[k.strip()] = v.strip()
        headers = hdr

    if config.update_provider(
        provider_id,
        name=name if name != provider.get("name", "") else None,
        provider_type=provider_type if provider_type != provider.get("type", "") else None,
        base_url=base_url if base_url != provider.get("base_url", "") else None,
        api_key=api_key if api_key != provider.get("api_key", "") else None,
        extra_headers=headers,
    ):
        print(f"\n✅ Provider '{provider_id}' updated")


def interactive_update_model(config: CrushConfig):
    print_header("Modify Model")

    providers = config.list_providers()
    if not providers:
        print("❌ No available provider")
        return

    provider_ids = list(providers.keys())
    idx = prompt_choice("Select Provider:", provider_ids)
    provider_id = provider_ids[idx]

    models = config.list_models(provider_id)
    if not models:
        print(f"❌ Provider '{provider_id}' has no models")
        return

    model_ids = list(models.keys())
    idx = prompt_choice("Select Model to modify:", model_ids)
    model_id = model_ids[idx]
    model = models[model_id]

    print(f"\nCurrent configuration: {model_id} = {json.dumps(model, indent=2, ensure_ascii=False)}")

    name = prompt("New name (leave empty to keep unchanged)", model.get("name", ""))
    context_window = prompt_int("New context window (leave empty to keep unchanged)", model.get("context_window"))
    default_max_tokens = prompt_int("New default max tokens (leave empty to keep unchanged)", model.get("default_max_tokens"))
    can_reason = prompt_confirm("Supports reasoning mode?", default=bool(model.get("can_reason", False)))
    supports_attachments = prompt_confirm("Supports image attachments?", default=bool(model.get("supports_attachments", False)))

    if config.update_model(
        provider_id,
        model_id,
        name=name if name != model.get("name", "") else None,
        context_window=context_window,
        default_max_tokens=default_max_tokens,
        can_reason=can_reason,
        supports_attachments=supports_attachments,
    ):
        print(f"\n✅ Model '{model_id}' updated")


def interactive_delete_provider(config: CrushConfig):
    print_header("Delete Provider")

    providers = config.list_providers()
    if not providers:
        print("❌ No provider to delete")
        return

    provider_ids = list(providers.keys())
    idx = prompt_choice("Select Provider to delete:", provider_ids)
    provider_id = provider_ids[idx]

    if prompt_confirm(f"Are you sure you want to delete '{provider_id}' and all its models?", default=False):
        if config.delete_provider(provider_id):
            print(f"\n✅ Provider '{provider_id}' deleted")


def interactive_delete_model(config: CrushConfig):
    print_header("Delete Model")

    providers = config.list_providers()
    if not providers:
        print("❌ No available provider")
        return

    provider_ids = list(providers.keys())
    idx = prompt_choice("Select Provider:", provider_ids)
    provider_id = provider_ids[idx]

    models = config.list_models(provider_id)
    if not models:
        print(f"❌ Provider '{provider_id}' has no models")
        return

    model_ids = list(models.keys())
    idx = prompt_choice("Select Model to delete:", model_ids)
    model_id = model_ids[idx]

    if prompt_confirm(f"Are you sure you want to delete '{provider_id}/{model_id}'?", default=False):
        if config.delete_model(provider_id, model_id):
            print(f"\n✅ Model '{model_id}' deleted")


def interactive_set_selected_model(config: CrushConfig):
    print_header("Set Model Tier (large/small)")

    tier = prompt("Tier (large|small)", "large").strip().lower()
    if tier not in ("large", "small"):
        print("❌ Tier must be 'large' or 'small'")
        return

    providers = config.list_providers()
    if not providers:
        print("❌ No available provider")
        return

    # Collect models
    all_models: List[str] = []
    for pid in providers.keys():
        for mid in config.list_models(pid).keys():
            all_models.append(f"{pid}/{mid}")

    if not all_models:
        print("❌ No available models (add at least one provider model first)")
        return

    all_models.insert(0, f"(Clear {tier} model)")
    idx = prompt_choice(f"Select {tier} model:", all_models)

    if idx == 0:
        if config.clear_selected_model(tier):
            print(f"\n✅ Cleared {tier} model selection")
    else:
        pid, mid = all_models[idx].split("/", 1)
        if config.set_selected_model(tier, pid, mid):
            print(f"\n✅ {tier} model set to '{pid}/{mid}'")


def interactive_export_config(config: CrushConfig):
    print_header("Export Configuration")
    print(json.dumps(config.data, indent=2, ensure_ascii=False))


def interactive_menu(scope: str):
    config = CrushConfig(scope)

    while True:
        scope_name = {"project": "Project", "global": "Global", "data": "Data"}.get(scope, scope)
        print_header(f"Crush Configuration Management ({scope_name})")
        print_config_summary(config)

        choices = [
            "📋 View Config",
            "➕ Add Provider",
            "➕ Add Model",
            "✏️  Modify Provider",
            "✏️  Modify Model",
            "🗑️  Delete Provider",
            "🗑️  Delete Model",
            "🎯 Set Model Tier (large/small)",
            "📤 Export JSON",
            "🔄 Switch Config Scope",
            "❌ Exit",
        ]

        idx = prompt_choice("Choose operation:", choices)

        if idx == 0:
            interactive_view_config(config)
        elif idx == 1:
            interactive_add_provider(config)
        elif idx == 2:
            interactive_add_model(config)
        elif idx == 3:
            interactive_update_provider(config)
        elif idx == 4:
            interactive_update_model(config)
        elif idx == 5:
            interactive_delete_provider(config)
        elif idx == 6:
            interactive_delete_model(config)
        elif idx == 7:
            interactive_set_selected_model(config)
        elif idx == 8:
            interactive_export_config(config)
        elif idx == 9:
            scope = {"project": "global", "global": "data", "data": "project"}.get(scope, "project")
            config = CrushConfig(scope)
            print(f"\n✅ Switched to {scope}")
        else:
            print("\n👋 Goodbye!")
            break

        input(f"\n{color('Press Enter to continue...', Colors.DIM)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Command Line Interface
# ═══════════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crush-config",
        description="Crush Configuration Management Tool - Manage providers and models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                   # Interactive mode (project config)
  %(prog)s -g                                # Interactive mode (global config)
  %(prog)s --data                            # Interactive mode (data config, often API keys)
  %(prog)s list                              # List all providers
  %(prog)s add-provider myapi -t openai-compat -u http://localhost:8081/v1
  %(prog)s add-model myapi gpt-4o --name "My GPT-4o" --context 128000 --output 4096
  %(prog)s set-tier large myapi gpt-4o
  %(prog)s delete-model myapi gpt-4o
  %(prog)s export                            # Export config JSON
"""
    )

    scope_group = parser.add_mutually_exclusive_group()
    scope_group.add_argument(
        "-g", "--global", dest="scope", action="store_const",
        const="global", default="project",
        help="Use global config (~/.config/crush/crush.json)"
    )
    scope_group.add_argument(
        "--data", dest="scope", action="store_const",
        const="data",
        help="Use data config (~/.local/share/crush/crush.json)"
    )
    scope_group.add_argument(
        "-p", "--project", dest="scope", action="store_const",
        const="project",
        help="Use project config (.crush.json or crush.json, default)"
    )

    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    subparsers = parser.add_subparsers(dest="command", title="commands")

    # list
    list_cmd = subparsers.add_parser("list", aliases=["ls"], help="List all providers and models")
    list_cmd.add_argument("provider_id", nargs="?", help="Specify provider to list only its models")

    # add-provider
    ap = subparsers.add_parser("add-provider", aliases=["ap"], help="Add new provider")
    ap.add_argument("provider_id", help="Provider ID (map key)")
    ap.add_argument("--name", "-n", help="Display name")
    ap.add_argument("--type", "-t", dest="provider_type",
                    help="Provider type: openai|openai-compat|anthropic|gemini|azure|vertexai")
    ap.add_argument("--url", "-u", dest="base_url", help="API Base URL (base_url)")
    ap.add_argument("--api-key", dest="api_key", help="API key (or $ENV_VAR)")
    ap.add_argument("--header", action="append", dest="headers",
                    help="Extra header (repeatable): KEY:VALUE or KEY=VALUE")
    ap.add_argument("--disable", action="store_true", help="Disable this provider")

    # update-provider
    up = subparsers.add_parser("update-provider", aliases=["up"], help="Update provider")
    up.add_argument("provider_id", help="Provider ID")
    up.add_argument("--name", "-n", help="New name")
    up.add_argument("--type", "-t", dest="provider_type", help="New provider type")
    up.add_argument("--url", "-u", dest="base_url", help="New Base URL")
    up.add_argument("--api-key", dest="api_key", help="New API key (or $ENV_VAR)")
    up.add_argument("--header", action="append", dest="headers",
                    help="Replace headers (repeatable): KEY:VALUE or KEY=VALUE")
    up.add_argument("--disable", action="store_true", help="Disable this provider")
    up.add_argument("--enable", action="store_true", help="Enable this provider")

    # delete-provider
    dp = subparsers.add_parser("delete-provider", aliases=["dp"], help="Delete provider")
    dp.add_argument("provider_id", help="Provider ID")
    dp.add_argument("-f", "--force", action="store_true", help="Skip confirmation")

    # add-model
    am = subparsers.add_parser("add-model", aliases=["am"], help="Add new model to a provider")
    am.add_argument("provider_id", help="Provider ID")
    am.add_argument("model_id", help="Model ID")
    am.add_argument("--name", "-n", help="Display name")
    am.add_argument("--context", "-c", type=int, dest="context_window", help="Context window (tokens)")
    am.add_argument("--output", "-o", type=int, dest="default_max_tokens", help="Default max tokens (output)")
    am.add_argument("--can-reason", action="store_true", help="Model supports reasoning mode")
    am.add_argument("--attachments", action="store_true", help="Model supports image attachments")

    # update-model
    um = subparsers.add_parser("update-model", aliases=["um"], help="Update model in a provider")
    um.add_argument("provider_id", help="Provider ID")
    um.add_argument("model_id", help="Model ID")
    um.add_argument("--name", "-n", help="New name")
    um.add_argument("--context", "-c", type=int, dest="context_window", help="New context window")
    um.add_argument("--output", "-o", type=int, dest="default_max_tokens", help="New default max tokens")
    um.add_argument("--can-reason", action="store_true", help="Set can_reason=true")
    um.add_argument("--no-can-reason", action="store_true", help="Set can_reason=false")
    um.add_argument("--attachments", action="store_true", help="Set supports_attachments=true")
    um.add_argument("--no-attachments", action="store_true", help="Set supports_attachments=false")

    # delete-model
    dm = subparsers.add_parser("delete-model", aliases=["dm"], help="Delete model")
    dm.add_argument("provider_id", help="Provider ID")
    dm.add_argument("model_id", help="Model ID")
    dm.add_argument("-f", "--force", action="store_true", help="Skip confirmation")

    # set-tier
    st = subparsers.add_parser("set-tier", aliases=["st"], help="Set selected model tier (large/small)")
    st.add_argument("tier", choices=["large", "small"], help="Tier to set")
    st.add_argument("provider_id", help="Provider ID")
    st.add_argument("model_id", help="Model ID")

    # clear-tier
    ct = subparsers.add_parser("clear-tier", aliases=["ct"], help="Clear selected model tier")
    ct.add_argument("tier", choices=["large", "small"], help="Tier to clear")

    # export
    subparsers.add_parser("export", help="Export config JSON")

    return parser


def cli_list(config: CrushConfig, args):
    if args.provider_id:
        models = config.list_models(args.provider_id)
        if args.json:
            print(json.dumps(models, indent=2, ensure_ascii=False))
        else:
            if models:
                print(f"\nModels of {args.provider_id}:")
                for model_id, model in models.items():
                    print(f"  • {model_id}: {model.get('name', model_id)}")
            else:
                print(f"Provider '{args.provider_id}' has no models or does not exist")
    else:
        providers = config.list_providers()
        if args.json:
            print(json.dumps(providers, indent=2, ensure_ascii=False))
        else:
            if providers:
                for provider_id, provider in providers.items():
                    print_provider(provider_id, provider)
            else:
                print("No configuration yet")


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Enter interactive mode when no subcommand provided
    if not args.command:
        interactive_menu(args.scope)
        return

    config = CrushConfig(args.scope)

    if args.command in ("list", "ls"):
        cli_list(config, args)

    elif args.command in ("add-provider", "ap"):
        headers = _parse_kv_pairs(args.headers)
        if config.add_provider(
            args.provider_id,
            name=args.name,
            provider_type=args.provider_type,
            base_url=args.base_url,
            api_key=args.api_key,
            extra_headers=headers or None,
            disable=True if getattr(args, "disable", False) else None,
        ):
            print(f"✅ Provider '{args.provider_id}' added successfully")

    elif args.command in ("update-provider", "up"):
        headers = _parse_kv_pairs(args.headers)
        disable = None
        if getattr(args, "disable", False):
            disable = True
        if getattr(args, "enable", False):
            disable = False

        if config.update_provider(
            args.provider_id,
            name=args.name,
            provider_type=args.provider_type,
            base_url=args.base_url,
            api_key=args.api_key,
            extra_headers=headers if args.headers is not None else None,
            disable=disable,
        ):
            print(f"✅ Provider '{args.provider_id}' updated successfully")

    elif args.command in ("delete-provider", "dp"):
        if not args.force:
            if not prompt_confirm(f"Are you sure you want to delete '{args.provider_id}'?", default=False):
                print("Cancelled")
                return
        if config.delete_provider(args.provider_id):
            print(f"✅ Provider '{args.provider_id}' deleted")

    elif args.command in ("add-model", "am"):
        if config.add_model(
            args.provider_id,
            args.model_id,
            name=args.name,
            context_window=args.context_window,
            default_max_tokens=args.default_max_tokens,
            can_reason=getattr(args, "can_reason", False),
            supports_attachments=getattr(args, "attachments", False),
        ):
            print(f"✅ Model '{args.model_id}' added successfully")

    elif args.command in ("update-model", "um"):
        can_reason = None
        if getattr(args, "can_reason", False):
            can_reason = True
        if getattr(args, "no_can_reason", False):
            can_reason = False

        attachments = None
        if getattr(args, "attachments", False):
            attachments = True
        if getattr(args, "no_attachments", False):
            attachments = False

        if config.update_model(
            args.provider_id,
            args.model_id,
            name=args.name,
            context_window=args.context_window,
            default_max_tokens=args.default_max_tokens,
            can_reason=can_reason,
            supports_attachments=attachments,
        ):
            print(f"✅ Model '{args.model_id}' updated successfully")

    elif args.command in ("delete-model", "dm"):
        if not args.force:
            if not prompt_confirm(f"Are you sure you want to delete '{args.provider_id}/{args.model_id}'?", default=False):
                print("Cancelled")
                return
        if config.delete_model(args.provider_id, args.model_id):
            print(f"✅ Model '{args.model_id}' deleted")

    elif args.command in ("set-tier", "st"):
        if config.set_selected_model(args.tier, args.provider_id, args.model_id):
            print(f"✅ {args.tier} model set to '{args.provider_id}/{args.model_id}'")

    elif args.command in ("clear-tier", "ct"):
        if config.clear_selected_model(args.tier):
            print(f"✅ Cleared {args.tier} model selection")

    elif args.command == "export":
        print(json.dumps(config.data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
