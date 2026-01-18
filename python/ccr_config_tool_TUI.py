#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ccr_config_tool.py
Manage Claude Code Router config file (~/.claude-code-router/config.json)

Features:
- CRUD for top-level keys, Providers, Router
- Interactive menu mode with rich TUI
- CLI subcommands for scripting
- Relaxed JSON parser: supports // /* */ comments and trailing commas (JSON5-ish)
  NOTE: When writing back, it outputs standard JSON (comments will be lost).
- Automatic backup + atomic write
- Basic validation: provider/model references in Router

Dependencies:
  pip install rich InquirerPy --break-system-packages
"""

from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import os
import re
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_PATH = os.path.expanduser("~/.claude-code-router/config.json")

# ----------------------------
# Rich / InquirerPy imports (lazy)
# ----------------------------

_RICH_AVAILABLE = False
_INQUIRER_AVAILABLE = False

def _check_rich():
    global _RICH_AVAILABLE
    try:
        import rich
        _RICH_AVAILABLE = True
    except ImportError:
        _RICH_AVAILABLE = False
    return _RICH_AVAILABLE

def _check_inquirer():
    global _INQUIRER_AVAILABLE
    try:
        from InquirerPy import inquirer
        _INQUIRER_AVAILABLE = True
    except ImportError:
        _INQUIRER_AVAILABLE = False
    return _INQUIRER_AVAILABLE


# ----------------------------
# Relaxed JSON (JSON5-ish) loader
# ----------------------------

def _strip_json5_comments(text: str) -> str:
    """
    Remove // line comments and /* */ block comments, without touching strings.
    Simple state machine.
    """
    out = []
    i = 0
    n = len(text)
    in_str = False
    str_quote = ""
    escape = False

    while i < n:
        ch = text[i]

        if in_str:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == str_quote:
                in_str = False
            i += 1
            continue

        # not in string
        if ch in ("'", '"'):
            in_str = True
            str_quote = ch
            out.append(ch)
            i += 1
            continue

        # line comment //
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            i += 2
            while i < n and text[i] not in ("\n", "\r"):
                i += 1
            continue

        # block comment /* ... */
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2 if i + 1 < n else 0
            continue

        out.append(ch)
        i += 1

    return "".join(out)


_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")

def _remove_trailing_commas(text: str) -> str:
    # Remove trailing commas before } or ]
    # Repeat until stable for nested patterns
    prev = None
    cur = text
    while prev != cur:
        prev = cur
        cur = _TRAILING_COMMA_RE.sub(r"\1", cur)
    return cur


def load_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Try strict JSON first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Relaxed parse
    cleaned = _strip_json5_comments(raw)
    cleaned = _remove_trailing_commas(cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"[ERROR] Failed to parse config file (even after relaxing JSON).\n"
            f"File: {path}\n"
            f"Reason: {e}\n"
            f"Tip: Please fix the JSON/JSON5 syntax first."
        )


def ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def backup_config(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bkp = os.path.join(os.path.dirname(path), f"config.backup.{ts}.json")
    with open(path, "rb") as fr, open(bkp, "wb") as fw:
        fw.write(fr.read())
    return bkp


def atomic_write_json(path: str, data: Dict[str, Any], indent: int = 2) -> None:
    ensure_dir(path)
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".config.", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


# ----------------------------
# Utilities
# ----------------------------

def _as_bool(s: str) -> bool:
    ss = s.strip().lower()
    if ss in ("1", "true", "yes", "y", "on"):
        return True
    if ss in ("0", "false", "no", "n", "off"):
        return False
    raise ValueError(f"Not a bool: {s}")


def parse_typed_value(value: str, vtype: str) -> Any:
    if vtype == "str":
        return value
    if vtype == "int":
        return int(value)
    if vtype == "float":
        return float(value)
    if vtype == "bool":
        return _as_bool(value)
    if vtype == "json":
        return json.loads(value)
    if vtype == "auto":
        # try json, then bool/int/float fallback, else string
        vv = value.strip()
        try:
            return json.loads(vv)
        except Exception:
            pass
        try:
            return _as_bool(vv)
        except Exception:
            pass
        try:
            if re.fullmatch(r"[-+]?\d+", vv):
                return int(vv)
            if re.fullmatch(r"[-+]?\d+\.\d+", vv):
                return float(vv)
        except Exception:
            pass
        return value
    raise ValueError(f"Unknown type: {vtype}")


def get_providers(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    p = cfg.get("Providers")
    if isinstance(p, list):
        return p
    return []


def find_provider(cfg: Dict[str, Any], name: str) -> Tuple[int, Optional[Dict[str, Any]]]:
    providers = get_providers(cfg)
    for i, pr in enumerate(providers):
        if isinstance(pr, dict) and pr.get("name") == name:
            return i, pr
    return -1, None


def _provider_key(provider: Dict[str, Any], snake: str, camel: str) -> str:
    # Keep existing style if present
    if snake in provider:
        return snake
    if camel in provider:
        return camel
    # default to snake_case (matches README comprehensive example)
    return snake


def list_models_by_provider(cfg: Dict[str, Any]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for pr in get_providers(cfg):
        if not isinstance(pr, dict):
            continue
        name = pr.get("name")
        models = pr.get("models")
        if isinstance(name, str) and isinstance(models, list):
            out[name] = [m for m in models if isinstance(m, str)]
    return out


# ----------------------------
# Validation
# ----------------------------

def validate_config(cfg: Dict[str, Any]) -> List[str]:
    problems: List[str] = []
    providers = get_providers(cfg)
    if not providers:
        problems.append("Providers is missing or empty (need at least one provider).")

    seen = set()
    for idx, pr in enumerate(providers):
        if not isinstance(pr, dict):
            problems.append(f"Providers[{idx}] is not an object.")
            continue
        name = pr.get("name")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"Providers[{idx}].name is missing/invalid.")
            continue
        if name in seen:
            problems.append(f"Duplicate provider name: {name}")
        seen.add(name)

        models = pr.get("models")
        if not isinstance(models, list) or not any(isinstance(m, str) for m in models):
            problems.append(f"Provider '{name}' has no valid models list.")

    router = cfg.get("Router")
    if router is not None and not isinstance(router, dict):
        problems.append("Router is not an object.")
        return problems

    if isinstance(router, dict):
        model_map = list_models_by_provider(cfg)
        for k, v in router.items():
            # thresholds or non-route numeric fields: skip strict check
            if isinstance(v, (int, float, bool)) or v is None:
                continue
            if isinstance(v, str):
                # values like "provider,model"
                if "," not in v:
                    # could be custom router path or other strings
                    continue
                prov, model = [x.strip() for x in v.split(",", 1)]
                if prov and prov not in model_map:
                    problems.append(f"Router.{k} references unknown provider '{prov}'.")
                    continue
                if prov and model and prov in model_map and model not in model_map[prov]:
                    problems.append(f"Router.{k} references unknown model '{model}' under provider '{prov}'.")
            # other types: ignore

    return problems


# ----------------------------
# Commands: top-level CRUD
# ----------------------------

def cmd_show(cfg: Dict[str, Any], section: Optional[str]) -> None:
    if section in (None, "all"):
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return
    if section == "providers":
        print(json.dumps({"Providers": get_providers(cfg)}, ensure_ascii=False, indent=2))
        return
    if section == "router":
        print(json.dumps({"Router": cfg.get("Router", {})}, ensure_ascii=False, indent=2))
        return
    if section == "general":
        general = {k: v for k, v in cfg.items() if k not in ("Providers", "Router")}
        print(json.dumps(general, ensure_ascii=False, indent=2))
        return
    raise SystemExit(f"[ERROR] Unknown section: {section}")


def cmd_get(cfg: Dict[str, Any], key: str) -> None:
    if key not in cfg:
        raise SystemExit(f"[ERROR] Key not found: {key}")
    print(json.dumps(cfg[key], ensure_ascii=False, indent=2) if isinstance(cfg[key], (dict, list)) else cfg[key])


def cmd_set(cfg: Dict[str, Any], key: str, value: Any) -> None:
    cfg[key] = value


def cmd_del(cfg: Dict[str, Any], key: str) -> None:
    if key in cfg:
        del cfg[key]
    else:
        raise SystemExit(f"[ERROR] Key not found: {key}")


# ----------------------------
# Commands: Providers
# ----------------------------

def providers_list(cfg: Dict[str, Any]) -> None:
    ps = get_providers(cfg)
    if not ps:
        print("(no providers)")
        return
    for i, pr in enumerate(ps):
        if not isinstance(pr, dict):
            print(f"{i}: <invalid provider object>")
            continue
        name = pr.get("name", "<no-name>")
        models = pr.get("models", [])
        mcount = len(models) if isinstance(models, list) else 0
        print(f"{i}: {name}  (models: {mcount})")


def providers_show(cfg: Dict[str, Any], name: str) -> None:
    _, pr = find_provider(cfg, name)
    if pr is None:
        raise SystemExit(f"[ERROR] Provider not found: {name}")
    print(json.dumps(pr, ensure_ascii=False, indent=2))


def providers_add(cfg: Dict[str, Any], name: str, api_base_url: str, api_key: str,
                  models: List[str], transformer: Optional[Any]) -> None:
    if "Providers" not in cfg or not isinstance(cfg.get("Providers"), list):
        cfg["Providers"] = []
    idx, _ = find_provider(cfg, name)
    if idx != -1:
        raise SystemExit(f"[ERROR] Provider already exists: {name}")

    pr: Dict[str, Any] = {
        "name": name,
        "api_base_url": api_base_url,
        "api_key": api_key,
        "models": models,
    }
    if transformer is not None:
        pr["transformer"] = transformer
    cfg["Providers"].append(pr)


def providers_remove(cfg: Dict[str, Any], name: str) -> None:
    idx, _ = find_provider(cfg, name)
    if idx == -1:
        raise SystemExit(f"[ERROR] Provider not found: {name}")
    cfg["Providers"].pop(idx)


def providers_update(cfg: Dict[str, Any],
                     name: str,
                     rename: Optional[str],
                     api_base_url: Optional[str],
                     api_key: Optional[str],
                     models_add: List[str],
                     models_remove: List[str],
                     transformer: Optional[Any],
                     set_pairs: List[str]) -> None:
    idx, pr = find_provider(cfg, name)
    if pr is None:
        raise SystemExit(f"[ERROR] Provider not found: {name}")

    pr = copy.deepcopy(pr)

    # rename
    if rename:
        # check collision
        idx2, _ = find_provider(cfg, rename)
        if idx2 != -1:
            raise SystemExit(f"[ERROR] Another provider already named: {rename}")
        pr["name"] = rename

    # update URL/key, respecting existing style if present
    url_key = _provider_key(pr, "api_base_url", "baseUrl")
    key_key = _provider_key(pr, "api_key", "apiKey")

    if api_base_url is not None:
        pr[url_key] = api_base_url
        # also keep the other variant untouched; no forced sync

    if api_key is not None:
        pr[key_key] = api_key

    # models
    cur_models = pr.get("models")
    if not isinstance(cur_models, list):
        cur_models = []
    cur_models = [m for m in cur_models if isinstance(m, str)]

    for m in models_add:
        if m not in cur_models:
            cur_models.append(m)
    for m in models_remove:
        cur_models = [x for x in cur_models if x != m]
    pr["models"] = cur_models

    # transformer (replace)
    if transformer is not None:
        pr["transformer"] = transformer

    # generic set k=v for provider fields (value auto-typed)
    for pair in set_pairs:
        if "=" not in pair:
            raise SystemExit(f"[ERROR] Bad --set format (need k=v): {pair}")
        k, v = pair.split("=", 1)
        k = k.strip()
        v = v.strip()
        pr[k] = parse_typed_value(v, "auto")

    # write back
    cfg["Providers"][idx] = pr


# ----------------------------
# Commands: Router
# ----------------------------

def router_show(cfg: Dict[str, Any]) -> None:
    r = cfg.get("Router", {})
    if not isinstance(r, dict):
        raise SystemExit("[ERROR] Router is not an object.")
    print(json.dumps(r, ensure_ascii=False, indent=2))


def router_get(cfg: Dict[str, Any], key: str) -> None:
    r = cfg.get("Router", {})
    if not isinstance(r, dict):
        raise SystemExit("[ERROR] Router is not an object.")
    if key not in r:
        raise SystemExit(f"[ERROR] Router key not found: {key}")
    v = r[key]
    print(json.dumps(v, ensure_ascii=False, indent=2) if isinstance(v, (dict, list)) else v)


def router_set(cfg: Dict[str, Any], key: str, value: Any) -> None:
    if "Router" not in cfg or not isinstance(cfg.get("Router"), dict):
        cfg["Router"] = {}
    cfg["Router"][key] = value


def router_del(cfg: Dict[str, Any], key: str) -> None:
    r = cfg.get("Router", {})
    if not isinstance(r, dict):
        raise SystemExit("[ERROR] Router is not an object.")
    if key in r:
        del r[key]
    else:
        raise SystemExit(f"[ERROR] Router key not found: {key}")


# ============================================================
# Enhanced Interactive Mode with Rich TUI
# ============================================================

class RichUI:
    """Rich-based UI components for enhanced interactivity."""
    
    def __init__(self):
        self.console = None
        self.inquirer = None
        self._init_libs()
    
    def _init_libs(self):
        if _check_rich():
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel
            from rich.syntax import Syntax
            from rich.text import Text
            from rich import box
            self.console = Console()
            self._Table = Table
            self._Panel = Panel
            self._Syntax = Syntax
            self._Text = Text
            self._box = box
        
        if _check_inquirer():
            from InquirerPy import inquirer
            from InquirerPy.separator import Separator
            self.inquirer = inquirer
            self._Separator = Separator
    
    @property
    def available(self) -> bool:
        return self.console is not None and self.inquirer is not None
    
    def print_header(self, title: str, subtitle: str = ""):
        if self.console:
            text = self._Text()
            text.append("🔧 ", style="bold")
            text.append(title, style="bold cyan")
            if subtitle:
                text.append(f"\n{subtitle}", style="dim")
            self.console.print(self._Panel(text, box=self._box.ROUNDED, border_style="cyan"))
        else:
            print(f"=== {title} ===")
            if subtitle:
                print(subtitle)
    
    def print_success(self, msg: str):
        if self.console:
            self.console.print(f"[bold green]✓[/] {msg}")
        else:
            print(f"[OK] {msg}")
    
    def print_error(self, msg: str):
        if self.console:
            self.console.print(f"[bold red]✗[/] {msg}")
        else:
            print(f"[ERROR] {msg}")
    
    def print_warning(self, msg: str):
        if self.console:
            self.console.print(f"[bold yellow]⚠[/] {msg}")
        else:
            print(f"[WARN] {msg}")
    
    def print_info(self, msg: str):
        if self.console:
            self.console.print(f"[dim]ℹ[/] {msg}")
        else:
            print(f"[INFO] {msg}")
    
    def print_json(self, data: Any, title: str = ""):
        if self.console:
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            syntax = self._Syntax(json_str, "json", theme="monokai", line_numbers=False)
            if title:
                self.console.print(self._Panel(syntax, title=title, border_style="blue"))
            else:
                self.console.print(syntax)
        else:
            if title:
                print(f"\n{title}:")
            print(json.dumps(data, ensure_ascii=False, indent=2))
    
    def print_providers_table(self, cfg: Dict[str, Any]):
        providers = get_providers(cfg)
        if not providers:
            self.print_warning("No providers configured")
            return
        
        if self.console:
            table = self._Table(
                title="Providers",
                box=self._box.ROUNDED,
                show_header=True,
                header_style="bold magenta"
            )
            table.add_column("#", style="dim", width=3)
            table.add_column("Name", style="cyan", min_width=12)
            table.add_column("API Base URL", style="dim", max_width=40)
            table.add_column("Models", style="green")
            table.add_column("Transformer", style="yellow", width=12)
            
            for i, pr in enumerate(providers):
                if not isinstance(pr, dict):
                    table.add_row(str(i), "[red]<invalid>[/]", "", "", "")
                    continue
                name = pr.get("name", "<no-name>")
                url = pr.get("api_base_url", pr.get("baseUrl", ""))
                if len(url) > 38:
                    url = url[:35] + "..."
                models = pr.get("models", [])
                if isinstance(models, list):
                    model_str = ", ".join(models[:3])
                    if len(models) > 3:
                        model_str += f" (+{len(models)-3})"
                else:
                    model_str = "<invalid>"
                has_transformer = "✓" if pr.get("transformer") else ""
                table.add_row(str(i), name, url, model_str, has_transformer)
            
            self.console.print(table)
        else:
            providers_list(cfg)
    
    def print_router_table(self, cfg: Dict[str, Any]):
        router = cfg.get("Router", {})
        if not isinstance(router, dict) or not router:
            self.print_warning("Router not configured")
            return
        
        if self.console:
            table = self._Table(
                title="Router Configuration",
                box=self._box.ROUNDED,
                show_header=True,
                header_style="bold magenta"
            )
            table.add_column("Route Key", style="cyan", min_width=18)
            table.add_column("Value", style="green")
            
            for k, v in router.items():
                if isinstance(v, str):
                    table.add_row(k, v)
                elif isinstance(v, (int, float)):
                    table.add_row(k, f"[yellow]{v}[/]")
                elif isinstance(v, bool):
                    table.add_row(k, f"[magenta]{v}[/]")
                else:
                    table.add_row(k, f"[dim]{json.dumps(v)}[/]")
            
            self.console.print(table)
        else:
            router_show(cfg)
    
    def print_general_table(self, cfg: Dict[str, Any]):
        general = {k: v for k, v in cfg.items() if k not in ("Providers", "Router")}
        if not general:
            self.print_warning("No general settings configured")
            return
        
        if self.console:
            table = self._Table(
                title="General Settings",
                box=self._box.ROUNDED,
                show_header=True,
                header_style="bold magenta"
            )
            table.add_column("Key", style="cyan", min_width=20)
            table.add_column("Value", style="green")
            table.add_column("Type", style="dim", width=8)
            
            for k, v in general.items():
                vtype = type(v).__name__
                if isinstance(v, str):
                    # Mask API keys
                    display = v if "key" not in k.lower() or len(v) < 8 else v[:4] + "****" + v[-4:]
                    table.add_row(k, display, vtype)
                elif isinstance(v, bool):
                    table.add_row(k, f"[magenta]{v}[/]", vtype)
                elif isinstance(v, (int, float)):
                    table.add_row(k, f"[yellow]{v}[/]", vtype)
                else:
                    table.add_row(k, f"[dim]{json.dumps(v)[:50]}[/]", vtype)
            
            self.console.print(table)
        else:
            print(json.dumps(general, ensure_ascii=False, indent=2))
    
    def select(self, message: str, choices: List[dict], default: str = None) -> str:
        """
        Interactive selection menu.
        choices: List of {"name": "Display Name", "value": "return_value"}
        """
        if self.inquirer:
            return self.inquirer.select(
                message=message,
                choices=choices,
                default=default,
                pointer="❯",
                qmark="",
                amark="",
                instruction="(↑↓ to move, Enter to select)",
            ).execute()
        else:
            # Fallback to simple input
            print(f"\n{message}")
            for i, c in enumerate(choices):
                if isinstance(c, dict):
                    print(f"  {i+1}) {c.get('name', c.get('value', '?'))}")
                else:
                    print(f"  ---")
            while True:
                try:
                    idx = int(input("Select number: ").strip()) - 1
                    if 0 <= idx < len(choices):
                        c = choices[idx]
                        return c.get("value") if isinstance(c, dict) else None
                except (ValueError, IndexError):
                    print("Invalid selection")
    
    def input_text(self, message: str, default: str = "", validate: callable = None,
                   completer: dict = None, multiline: bool = False, is_password: bool = False) -> str:
        if self.inquirer:
            kwargs = {
                "message": message,
                "default": default,
                "qmark": "",
                "amark": "",
            }
            if validate:
                kwargs["validate"] = validate
            if completer:
                kwargs["completer"] = completer
            if multiline:
                kwargs["multiline"] = True
            if is_password:
                return self.inquirer.secret(**kwargs).execute()
            return self.inquirer.text(**kwargs).execute()
        else:
            prompt = f"{message}"
            if default:
                prompt += f" [{default}]"
            prompt += ": "
            val = input(prompt).strip()
            return val if val else default
    
    def confirm(self, message: str, default: bool = False) -> bool:
        if self.inquirer:
            return self.inquirer.confirm(
                message=message,
                default=default,
                qmark="",
                amark="",
            ).execute()
        else:
            suffix = " [Y/n]" if default else " [y/N]"
            val = input(message + suffix + ": ").strip().lower()
            if not val:
                return default
            return val in ("y", "yes", "1", "true")
    
    def checkbox(self, message: str, choices: List[dict], default: List[str] = None) -> List[str]:
        """Multi-select checkbox."""
        if self.inquirer:
            return self.inquirer.checkbox(
                message=message,
                choices=choices,
                default=default,
                pointer="❯",
                qmark="",
                amark="",
                instruction="(Space to select, Enter to confirm)",
            ).execute()
        else:
            print(f"\n{message} (enter numbers separated by space)")
            for i, c in enumerate(choices):
                if isinstance(c, dict):
                    mark = "[x]" if c.get("value") in (default or []) else "[ ]"
                    print(f"  {i+1}) {mark} {c.get('name', c.get('value', '?'))}")
            val = input("Select: ").strip()
            if not val:
                return default or []
            indices = [int(x)-1 for x in val.split() if x.isdigit()]
            return [choices[i].get("value") for i in indices if 0 <= i < len(choices)]
    
    def fuzzy_select(self, message: str, choices: List[str], default: str = None) -> str:
        """Fuzzy search selection."""
        if self.inquirer:
            return self.inquirer.fuzzy(
                message=message,
                choices=choices,
                default=default,
                pointer="❯",
                qmark="",
                amark="",
                instruction="(Type to filter)",
            ).execute()
        else:
            print(f"\n{message}")
            for i, c in enumerate(choices):
                print(f"  {i+1}) {c}")
            while True:
                val = input("Enter name or number: ").strip()
                if val.isdigit():
                    idx = int(val) - 1
                    if 0 <= idx < len(choices):
                        return choices[idx]
                elif val in choices:
                    return val
                print("Invalid selection")


# ----------------------------
# Enhanced Interactive Mode
# ----------------------------

def interactive_enhanced(cfg: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Enhanced interactive mode with Rich TUI."""
    ui = RichUI()
    
    if not ui.available:
        ui.print_warning("Enhanced UI requires 'rich' and 'InquirerPy' packages.")
        ui.print_info("Install with: pip install rich InquirerPy --break-system-packages")
        ui.print_info("Falling back to basic interactive mode...\n")
        return interactive_fallback(cfg)
    
    ui.print_header(
        "Claude Code Router Config Tool",
        f"Config: {path}"
    )
    
    modified = False
    
    while True:
        # Main menu
        action = ui.select(
            "What would you like to do?",
            [
                {"name": "📋 View Configuration", "value": "view"},
                {"name": "⚙️  General Settings", "value": "general"},
                {"name": "🔌 Providers", "value": "providers"},
                {"name": "🔀 Router", "value": "router"},
                {"name": "✅ Validate Config", "value": "validate"},
                {"name": "─" * 30, "value": None},  # separator
                {"name": "💾 Save & Exit", "value": "save"},
                {"name": "🚪 Exit without Saving", "value": "exit"},
            ]
        )
        
        if action is None:
            continue
        
        if action == "view":
            view_action = ui.select(
                "View what?",
                [
                    {"name": "Full Config (JSON)", "value": "all"},
                    {"name": "General Settings", "value": "general"},
                    {"name": "Providers", "value": "providers"},
                    {"name": "Router", "value": "router"},
                    {"name": "← Back", "value": "back"},
                ]
            )
            if view_action == "all":
                ui.print_json(cfg, "Full Configuration")
            elif view_action == "general":
                ui.print_general_table(cfg)
            elif view_action == "providers":
                ui.print_providers_table(cfg)
            elif view_action == "router":
                ui.print_router_table(cfg)
        
        elif action == "general":
            modified = _handle_general_menu(ui, cfg) or modified
        
        elif action == "providers":
            modified = _handle_providers_menu(ui, cfg) or modified
        
        elif action == "router":
            modified = _handle_router_menu(ui, cfg) or modified
        
        elif action == "validate":
            problems = validate_config(cfg)
            if not problems:
                ui.print_success("Configuration is valid!")
            else:
                ui.print_error("Validation issues found:")
                for p in problems:
                    ui.print_warning(f"  • {p}")
        
        elif action == "save":
            if modified:
                return cfg
            else:
                if ui.confirm("No changes made. Exit anyway?", default=True):
                    return cfg
        
        elif action == "exit":
            if modified:
                if ui.confirm("Discard unsaved changes?", default=False):
                    raise SystemExit("Exited without saving.")
            else:
                raise SystemExit("Exited.")


def _handle_general_menu(ui: RichUI, cfg: Dict[str, Any]) -> bool:
    """Handle general settings submenu. Returns True if modified."""
    modified = False
    
    while True:
        ui.print_general_table(cfg)
        
        action = ui.select(
            "General Settings",
            [
                {"name": "➕ Add/Set Key", "value": "set"},
                {"name": "✏️  Edit Key", "value": "edit"},
                {"name": "🗑️  Delete Key", "value": "delete"},
                {"name": "← Back", "value": "back"},
            ]
        )
        
        if action == "back":
            return modified
        
        general_keys = [k for k in cfg.keys() if k not in ("Providers", "Router")]
        
        if action == "set":
            key = ui.input_text("Key name")
            if not key:
                continue
            
            value_type = ui.select(
                "Value type",
                [
                    {"name": "Auto-detect", "value": "auto"},
                    {"name": "String", "value": "str"},
                    {"name": "Integer", "value": "int"},
                    {"name": "Float", "value": "float"},
                    {"name": "Boolean", "value": "bool"},
                    {"name": "JSON", "value": "json"},
                ]
            )
            
            if value_type == "bool":
                value = ui.confirm(f"Value for '{key}'")
                cfg[key] = value
            else:
                value_str = ui.input_text("Value")
                try:
                    cfg[key] = parse_typed_value(value_str, value_type)
                    ui.print_success(f"Set {key} = {cfg[key]}")
                    modified = True
                except Exception as e:
                    ui.print_error(f"Invalid value: {e}")
        
        elif action == "edit":
            if not general_keys:
                ui.print_warning("No general keys to edit")
                continue
            
            key = ui.fuzzy_select("Select key to edit", general_keys)
            current = cfg.get(key)
            ui.print_info(f"Current value: {current}")
            
            value_str = ui.input_text("New value", default=str(current) if current is not None else "")
            try:
                cfg[key] = parse_typed_value(value_str, "auto")
                ui.print_success(f"Updated {key}")
                modified = True
            except Exception as e:
                ui.print_error(f"Invalid value: {e}")
        
        elif action == "delete":
            if not general_keys:
                ui.print_warning("No general keys to delete")
                continue
            
            key = ui.fuzzy_select("Select key to delete", general_keys)
            if ui.confirm(f"Delete '{key}'?", default=False):
                del cfg[key]
                ui.print_success(f"Deleted {key}")
                modified = True


def _handle_providers_menu(ui: RichUI, cfg: Dict[str, Any]) -> bool:
    """Handle providers submenu. Returns True if modified."""
    modified = False
    
    while True:
        ui.print_providers_table(cfg)
        
        action = ui.select(
            "Providers",
            [
                {"name": "➕ Add Provider", "value": "add"},
                {"name": "✏️  Edit Provider", "value": "edit"},
                {"name": "📋 View Provider Details", "value": "view"},
                {"name": "🗑️  Remove Provider", "value": "remove"},
                {"name": "← Back", "value": "back"},
            ]
        )
        
        if action == "back":
            return modified
        
        provider_names = [pr.get("name") for pr in get_providers(cfg) if isinstance(pr, dict) and pr.get("name")]
        
        if action == "add":
            name = ui.input_text("Provider name (e.g., openrouter, deepseek)")
            if not name:
                continue
            if name in provider_names:
                ui.print_error(f"Provider '{name}' already exists")
                continue
            
            api_url = ui.input_text("API Base URL")
            api_key = ui.input_text("API Key (can use $ENV_VAR)")
            
            models_str = ui.input_text("Models (comma separated)")
            models = [m.strip() for m in models_str.split(",") if m.strip()]
            
            if ui.confirm("Add transformer config?", default=False):
                transformer_str = ui.input_text("Transformer JSON", multiline=True)
                try:
                    transformer = json.loads(transformer_str) if transformer_str else None
                except json.JSONDecodeError as e:
                    ui.print_error(f"Invalid JSON: {e}")
                    transformer = None
            else:
                transformer = None
            
            try:
                providers_add(cfg, name, api_url, api_key, models, transformer)
                ui.print_success(f"Added provider '{name}'")
                modified = True
            except SystemExit as e:
                ui.print_error(str(e))
        
        elif action == "edit":
            if not provider_names:
                ui.print_warning("No providers to edit")
                continue
            
            name = ui.fuzzy_select("Select provider to edit", provider_names)
            _, pr = find_provider(cfg, name)
            
            ui.print_json(pr, f"Current: {name}")
            
            edit_action = ui.select(
                f"Edit {name}",
                [
                    {"name": "Rename", "value": "rename"},
                    {"name": "Change API URL", "value": "url"},
                    {"name": "Change API Key", "value": "key"},
                    {"name": "Manage Models", "value": "models"},
                    {"name": "Edit Transformer", "value": "transformer"},
                    {"name": "← Back", "value": "back"},
                ]
            )
            
            if edit_action == "back":
                continue
            
            if edit_action == "rename":
                new_name = ui.input_text("New name", default=name)
                if new_name and new_name != name:
                    try:
                        providers_update(cfg, name, rename=new_name, api_base_url=None,
                                       api_key=None, models_add=[], models_remove=[],
                                       transformer=None, set_pairs=[])
                        ui.print_success(f"Renamed to '{new_name}'")
                        modified = True
                    except SystemExit as e:
                        ui.print_error(str(e))
            
            elif edit_action == "url":
                current_url = pr.get("api_base_url", pr.get("baseUrl", ""))
                new_url = ui.input_text("API Base URL", default=current_url)
                if new_url:
                    providers_update(cfg, name, rename=None, api_base_url=new_url,
                                   api_key=None, models_add=[], models_remove=[],
                                   transformer=None, set_pairs=[])
                    ui.print_success("Updated API URL")
                    modified = True
            
            elif edit_action == "key":
                new_key = ui.input_text("API Key")
                if new_key:
                    providers_update(cfg, name, rename=None, api_base_url=None,
                                   api_key=new_key, models_add=[], models_remove=[],
                                   transformer=None, set_pairs=[])
                    ui.print_success("Updated API Key")
                    modified = True
            
            elif edit_action == "models":
                current_models = pr.get("models", [])
                ui.print_info(f"Current models: {', '.join(current_models)}")
                
                models_action = ui.select(
                    "Model management",
                    [
                        {"name": "Add model", "value": "add"},
                        {"name": "Remove model", "value": "remove"},
                        {"name": "Replace all models", "value": "replace"},
                        {"name": "← Back", "value": "back"},
                    ]
                )
                
                if models_action == "add":
                    new_model = ui.input_text("Model name to add")
                    if new_model:
                        providers_update(cfg, name, rename=None, api_base_url=None,
                                       api_key=None, models_add=[new_model], models_remove=[],
                                       transformer=None, set_pairs=[])
                        ui.print_success(f"Added model '{new_model}'")
                        modified = True
                
                elif models_action == "remove":
                    if current_models:
                        to_remove = ui.checkbox(
                            "Select models to remove",
                            [{"name": m, "value": m} for m in current_models]
                        )
                        if to_remove:
                            providers_update(cfg, name, rename=None, api_base_url=None,
                                           api_key=None, models_add=[], models_remove=to_remove,
                                           transformer=None, set_pairs=[])
                            ui.print_success(f"Removed {len(to_remove)} model(s)")
                            modified = True
                
                elif models_action == "replace":
                    models_str = ui.input_text("New models (comma separated)")
                    new_models = [m.strip() for m in models_str.split(",") if m.strip()]
                    if new_models:
                        # Remove all, add new
                        providers_update(cfg, name, rename=None, api_base_url=None,
                                       api_key=None, models_add=new_models,
                                       models_remove=current_models,
                                       transformer=None, set_pairs=[])
                        ui.print_success("Replaced models")
                        modified = True
            
            elif edit_action == "transformer":
                current_tf = pr.get("transformer")
                if current_tf:
                    ui.print_json(current_tf, "Current transformer")
                
                tf_action = ui.select(
                    "Transformer",
                    [
                        {"name": "Replace transformer", "value": "replace"},
                        {"name": "Remove transformer", "value": "remove"},
                        {"name": "← Back", "value": "back"},
                    ]
                )
                
                if tf_action == "replace":
                    tf_str = ui.input_text("Transformer JSON", multiline=True)
                    try:
                        tf = json.loads(tf_str) if tf_str else None
                        providers_update(cfg, name, rename=None, api_base_url=None,
                                       api_key=None, models_add=[], models_remove=[],
                                       transformer=tf, set_pairs=[])
                        ui.print_success("Updated transformer")
                        modified = True
                    except json.JSONDecodeError as e:
                        ui.print_error(f"Invalid JSON: {e}")
                
                elif tf_action == "remove":
                    # Set transformer to empty dict to remove
                    idx, _ = find_provider(cfg, name)
                    if idx >= 0 and "transformer" in cfg["Providers"][idx]:
                        del cfg["Providers"][idx]["transformer"]
                        ui.print_success("Removed transformer")
                        modified = True
        
        elif action == "view":
            if not provider_names:
                ui.print_warning("No providers")
                continue
            name = ui.fuzzy_select("Select provider", provider_names)
            _, pr = find_provider(cfg, name)
            ui.print_json(pr, f"Provider: {name}")
        
        elif action == "remove":
            if not provider_names:
                ui.print_warning("No providers to remove")
                continue
            
            name = ui.fuzzy_select("Select provider to remove", provider_names)
            if ui.confirm(f"Remove provider '{name}'?", default=False):
                try:
                    providers_remove(cfg, name)
                    ui.print_success(f"Removed provider '{name}'")
                    modified = True
                except SystemExit as e:
                    ui.print_error(str(e))


def _handle_router_menu(ui: RichUI, cfg: Dict[str, Any]) -> bool:
    """Handle router submenu. Returns True if modified."""
    modified = False
    
    # Predefined route types for convenience
    ROUTE_TYPES = ["default", "background", "think", "longContext", "webSearch", "longContextThreshold"]
    
    while True:
        ui.print_router_table(cfg)
        
        action = ui.select(
            "Router",
            [
                {"name": "➕ Add/Set Route", "value": "set"},
                {"name": "✏️  Edit Route", "value": "edit"},
                {"name": "🗑️  Delete Route", "value": "delete"},
                {"name": "🔄 Quick Setup (Interactive)", "value": "quick"},
                {"name": "← Back", "value": "back"},
            ]
        )
        
        if action == "back":
            return modified
        
        router = cfg.get("Router", {})
        existing_keys = list(router.keys()) if isinstance(router, dict) else []
        model_map = list_models_by_provider(cfg)
        provider_names = list(model_map.keys())
        
        if action == "set" or action == "edit":
            if action == "edit" and not existing_keys:
                ui.print_warning("No routes to edit")
                continue
            
            # Select or enter key
            if action == "edit":
                key = ui.fuzzy_select("Select route to edit", existing_keys)
            else:
                key_choices = [{"name": k, "value": k} for k in ROUTE_TYPES if k not in existing_keys]
                key_choices.append({"name": "Custom key...", "value": "_custom"})
                
                key = ui.select("Route type", key_choices)
                if key == "_custom":
                    key = ui.input_text("Custom key name")
            
            if not key:
                continue
            
            # Determine value type
            if key == "longContextThreshold":
                value = ui.input_text("Threshold value (integer)", default=str(router.get(key, 60000)))
                try:
                    router_set(cfg, key, int(value))
                    ui.print_success(f"Set {key} = {value}")
                    modified = True
                except ValueError:
                    ui.print_error("Invalid integer")
            else:
                # Route value: provider,model
                if not provider_names:
                    ui.print_warning("No providers configured. Add providers first.")
                    continue
                
                provider = ui.fuzzy_select("Select provider", provider_names)
                models = model_map.get(provider, [])
                
                if not models:
                    ui.print_warning(f"Provider '{provider}' has no models")
                    continue
                
                model = ui.fuzzy_select("Select model", models)
                value = f"{provider},{model}"
                
                router_set(cfg, key, value)
                ui.print_success(f"Set {key} = {value}")
                modified = True
        
        elif action == "delete":
            if not existing_keys:
                ui.print_warning("No routes to delete")
                continue
            
            key = ui.fuzzy_select("Select route to delete", existing_keys)
            if ui.confirm(f"Delete route '{key}'?", default=False):
                try:
                    router_del(cfg, key)
                    ui.print_success(f"Deleted route '{key}'")
                    modified = True
                except SystemExit as e:
                    ui.print_error(str(e))
        
        elif action == "quick":
            # Quick setup wizard
            if not provider_names:
                ui.print_warning("No providers configured. Add providers first.")
                continue
            
            ui.print_info("Quick Router Setup - Configure common routes")
            
            for route_type in ["default", "background", "think", "longContext", "webSearch"]:
                if ui.confirm(f"Configure '{route_type}' route?", default=(route_type == "default")):
                    provider = ui.fuzzy_select(f"Provider for {route_type}", provider_names)
                    models = model_map.get(provider, [])
                    if models:
                        model = ui.fuzzy_select(f"Model for {route_type}", models)
                        router_set(cfg, route_type, f"{provider},{model}")
                        ui.print_success(f"Set {route_type}")
                        modified = True
            
            if ui.confirm("Set longContextThreshold?", default=True):
                threshold = ui.input_text("Threshold", default="60000")
                try:
                    router_set(cfg, "longContextThreshold", int(threshold))
                    modified = True
                except ValueError:
                    ui.print_error("Invalid number")


# ----------------------------
# Fallback Interactive mode (no rich/inquirer)
# ----------------------------

def _prompt(msg: str, default: Optional[str] = None) -> str:
    if default is None:
        return input(msg + ": ").strip()
    s = input(f"{msg} [{default}]: ").strip()
    return s if s else default


def interactive_fallback(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Basic interactive mode without rich TUI."""
    print("=== Claude Code Router Config Tool (Interactive) ===")
    print(f"Config path: {DEFAULT_PATH}")
    print("Note: reading supports JSON5-ish comments; writing outputs standard JSON (comments removed).")
    print("")

    while True:
        print("\nMain Menu:")
        print("  1) View config")
        print("  2) General (top-level keys)")
        print("  3) Providers")
        print("  4) Router")
        print("  5) Validate")
        print("  6) Save & Exit")
        print("  7) Exit without saving")
        choice = _prompt("Select", "1")

        if choice == "1":
            cmd_show(cfg, "all")

        elif choice == "2":
            print("\nGeneral keys (excluding Providers/Router):")
            general = {k: v for k, v in cfg.items() if k not in ("Providers", "Router")}
            print(json.dumps(general, ensure_ascii=False, indent=2))
            print("\nActions:")
            print("  a) set key")
            print("  b) delete key")
            print("  c) back")
            act = _prompt("Select", "c")
            if act == "a":
                k = _prompt("Key")
                vt = _prompt("Type (auto/str/int/float/bool/json)", "auto")
                v = _prompt("Value")
                cmd_set(cfg, k, parse_typed_value(v, vt))
                print("[OK] updated")
            elif act == "b":
                k = _prompt("Key")
                try:
                    cmd_del(cfg, k)
                    print("[OK] deleted")
                except SystemExit as e:
                    print(str(e))
            else:
                continue

        elif choice == "3":
            while True:
                print("\nProviders:")
                providers_list(cfg)
                print("\nActions:")
                print("  a) add provider")
                print("  b) edit provider")
                print("  c) remove provider")
                print("  d) show provider")
                print("  e) back")
                act = _prompt("Select", "e")
                if act == "a":
                    name = _prompt("name")
                    url = _prompt("api_base_url")
                    key = _prompt("api_key (can be $ENV_VAR)")
                    models_raw = _prompt("models (comma separated)")
                    models = [m.strip() for m in models_raw.split(",") if m.strip()]
                    transformer_raw = _prompt("transformer JSON (empty to skip)", "")
                    transformer = json.loads(transformer_raw) if transformer_raw else None
                    providers_add(cfg, name, url, key, models, transformer)
                    print("[OK] provider added")
                elif act == "b":
                    name = _prompt("provider name to edit")
                    _, pr = find_provider(cfg, name)
                    if pr is None:
                        print("[ERROR] provider not found")
                        continue
                    print(json.dumps(pr, ensure_ascii=False, indent=2))
                    print("Edit fields:")
                    rename = _prompt("rename (empty to skip)", "")
                    url = _prompt("api_base_url (empty to skip)", "")
                    key = _prompt("api_key (empty to skip)", "")
                    addm = _prompt("models add (comma, empty skip)", "")
                    delm = _prompt("models remove (comma, empty skip)", "")
                    tr = _prompt("replace transformer JSON (empty skip)", "")
                    setkv = _prompt("extra set k=v (comma separated, empty skip)", "")

                    providers_update(
                        cfg,
                        name=name,
                        rename=rename or None,
                        api_base_url=url or None,
                        api_key=key or None,
                        models_add=[x.strip() for x in addm.split(",") if x.strip()],
                        models_remove=[x.strip() for x in delm.split(",") if x.strip()],
                        transformer=json.loads(tr) if tr else None,
                        set_pairs=[x.strip() for x in setkv.split(",") if x.strip()],
                    )
                    print("[OK] provider updated")
                elif act == "c":
                    name = _prompt("provider name to remove")
                    try:
                        providers_remove(cfg, name)
                        print("[OK] provider removed")
                    except SystemExit as e:
                        print(str(e))
                elif act == "d":
                    name = _prompt("provider name")
                    try:
                        providers_show(cfg, name)
                    except SystemExit as e:
                        print(str(e))
                else:
                    break

        elif choice == "4":
            while True:
                print("\nRouter:")
                try:
                    router_show(cfg)
                except SystemExit as e:
                    print(str(e))
                print("\nActions:")
                print("  a) set route")
                print("  b) delete route key")
                print("  c) get route key")
                print("  d) back")
                act = _prompt("Select", "d")
                if act == "a":
                    k = _prompt("Router key (e.g., default/background/think/longContext/webSearch/longContextThreshold)")
                    vt = _prompt("Type (auto/str/int/float/bool/json)", "auto")
                    v = _prompt("Value (e.g., provider,model)")
                    router_set(cfg, k, parse_typed_value(v, vt))
                    print("[OK] router updated")
                elif act == "b":
                    k = _prompt("Router key to delete")
                    try:
                        router_del(cfg, k)
                        print("[OK] router key deleted")
                    except SystemExit as e:
                        print(str(e))
                elif act == "c":
                    k = _prompt("Router key")
                    try:
                        router_get(cfg, k)
                    except SystemExit as e:
                        print(str(e))
                else:
                    break

        elif choice == "5":
            probs = validate_config(cfg)
            if not probs:
                print("[OK] validation passed")
            else:
                print("[WARN] validation problems:")
                for p in probs:
                    print(" - " + p)

        elif choice == "6":
            return cfg

        elif choice == "7":
            raise SystemExit("Exit without saving.")

        else:
            print("[ERROR] invalid choice")


# ----------------------------
# Argument parsing & main
# ----------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ccr_config_tool.py",
        description="CRUD tool for Claude Code Router config (~/.claude-code-router/config.json)",
    )
    p.add_argument("--file", default=DEFAULT_PATH, help=f"config path (default: {DEFAULT_PATH})")
    p.add_argument("--dry-run", action="store_true", help="do not write file")
    p.add_argument("--no-backup", action="store_true", help="do not create backup before writing")
    p.add_argument("--basic", action="store_true", help="use basic interactive mode (no rich TUI)")

    sub = p.add_subparsers(dest="cmd")

    # show/get/set/del
    sp = sub.add_parser("show", help="print config")
    sp.add_argument("--section", choices=["all", "general", "providers", "router"], default="all")

    sp = sub.add_parser("get", help="get top-level key")
    sp.add_argument("key")

    sp = sub.add_parser("set", help="set top-level key")
    sp.add_argument("key")
    sp.add_argument("value")
    sp.add_argument("--type", choices=["auto", "str", "int", "float", "bool", "json"], default="auto")

    sp = sub.add_parser("del", help="delete top-level key")
    sp.add_argument("key")

    # providers
    sp = sub.add_parser("providers", help="manage Providers")
    ssub = sp.add_subparsers(dest="providers_cmd")

    ssub.add_parser("list", help="list providers")

    sp2 = ssub.add_parser("show", help="show provider")
    sp2.add_argument("name")

    sp2 = ssub.add_parser("add", help="add provider")
    sp2.add_argument("--name", required=True)
    sp2.add_argument("--api-base-url", required=True)
    sp2.add_argument("--api-key", required=True)
    sp2.add_argument("--model", action="append", default=[], help="repeatable model name")
    sp2.add_argument("--models", default="", help="comma separated models (alternative to --model)")
    sp2.add_argument("--transformer-json", default=None, help="transformer as JSON string")
    sp2.add_argument("--transformer-file", default=None, help="transformer JSON file path")

    sp2 = ssub.add_parser("update", help="update provider")
    sp2.add_argument("name")
    sp2.add_argument("--rename", default=None)
    sp2.add_argument("--api-base-url", default=None)
    sp2.add_argument("--api-key", default=None)
    sp2.add_argument("--models-add", action="append", default=[], help="repeatable add model")
    sp2.add_argument("--models-remove", action="append", default=[], help="repeatable remove model")
    sp2.add_argument("--transformer-json", default=None, help="replace transformer with JSON string")
    sp2.add_argument("--transformer-file", default=None, help="replace transformer with JSON file")
    sp2.add_argument("--set", action="append", default=[], help="extra set provider_field=value (repeatable)")

    sp2 = ssub.add_parser("remove", help="remove provider")
    sp2.add_argument("name")

    # router
    sp = sub.add_parser("router", help="manage Router")
    ssub = sp.add_subparsers(dest="router_cmd")

    ssub.add_parser("show", help="show router")

    sp2 = ssub.add_parser("get", help="get router key")
    sp2.add_argument("key")

    sp2 = ssub.add_parser("set", help="set router key")
    sp2.add_argument("key")
    sp2.add_argument("value")
    sp2.add_argument("--type", choices=["auto", "str", "int", "float", "bool", "json"], default="auto")

    sp2 = ssub.add_parser("del", help="delete router key")
    sp2.add_argument("key")

    # validate
    sub.add_parser("validate", help="validate config (exit code 0 ok, 1 problems)")

    # interactive
    sub.add_parser("interactive", help="interactive menu editor")

    return p


def _load_transformer(args) -> Optional[Any]:
    if getattr(args, "transformer_json", None):
        return json.loads(args.transformer_json)
    if getattr(args, "transformer_file", None):
        with open(args.transformer_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    path = os.path.expanduser(args.file)
    cfg = load_config(path)

    # default to interactive if no command
    if not args.cmd:
        args.cmd = "interactive"

    modified = False

    if args.cmd == "show":
        cmd_show(cfg, args.section)
        return

    if args.cmd == "get":
        cmd_get(cfg, args.key)
        return

    if args.cmd == "set":
        cmd_set(cfg, args.key, parse_typed_value(args.value, args.type))
        modified = True

    elif args.cmd == "del":
        cmd_del(cfg, args.key)
        modified = True

    elif args.cmd == "providers":
        if args.providers_cmd == "list":
            providers_list(cfg)
            return
        if args.providers_cmd == "show":
            providers_show(cfg, args.name)
            return
        if args.providers_cmd == "add":
            models = []
            if args.models.strip():
                models.extend([m.strip() for m in args.models.split(",") if m.strip()])
            models.extend(args.model or [])
            transformer = _load_transformer(args)
            providers_add(cfg, args.name, args.api_base_url, args.api_key, models, transformer)
            modified = True
        elif args.providers_cmd == "update":
            transformer = _load_transformer(args)
            providers_update(
                cfg,
                name=args.name,
                rename=args.rename,
                api_base_url=args.api_base_url,
                api_key=args.api_key,
                models_add=args.models_add or [],
                models_remove=args.models_remove or [],
                transformer=transformer,
                set_pairs=args.set or [],
            )
            modified = True
        elif args.providers_cmd == "remove":
            providers_remove(cfg, args.name)
            modified = True
        else:
            raise SystemExit("[ERROR] providers needs a subcommand (list/show/add/update/remove)")

    elif args.cmd == "router":
        if args.router_cmd == "show":
            router_show(cfg)
            return
        if args.router_cmd == "get":
            router_get(cfg, args.key)
            return
        if args.router_cmd == "set":
            router_set(cfg, args.key, parse_typed_value(args.value, args.type))
            modified = True
        elif args.router_cmd == "del":
            router_del(cfg, args.key)
            modified = True
        else:
            raise SystemExit("[ERROR] router needs a subcommand (show/get/set/del)")

    elif args.cmd == "validate":
        probs = validate_config(cfg)
        if not probs:
            print("[OK] validation passed")
            sys.exit(0)
        print("[WARN] validation problems:")
        for p in probs:
            print(" - " + p)
        sys.exit(1)

    elif args.cmd == "interactive":
        # Check if using basic mode or if rich/inquirer unavailable
        if getattr(args, "basic", False):
            cfg = interactive_fallback(cfg)
        else:
            cfg = interactive_enhanced(cfg, path)
        modified = True

    else:
        raise SystemExit(f"[ERROR] Unknown command: {args.cmd}")

    # write if modified
    if modified:
        if args.dry_run:
            print("[DRY-RUN] Would write config:")
            print(json.dumps(cfg, ensure_ascii=False, indent=2))
            return

        if not args.no_backup:
            bkp = backup_config(path)
            if bkp:
                print(f"[OK] Backup created: {bkp}")

        atomic_write_json(path, cfg, indent=2)
        print(f"[OK] Written: {path}")
        # suggest restart
        print("Tip: after changing config, restart router (e.g., `ccr restart`).")


if __name__ == "__main__":
    main()
