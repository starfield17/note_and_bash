#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
codex_config_tool.py
CRUD tool for ~/.codex/config.toml used by Codex CLI/IDE.

Features:
- List/show current config (root / providers / profiles)
- Get/set root config (model, model_provider, etc.)
- Add/update/delete providers under [model_providers.<id>]
- Add/update/delete profiles under [profiles.<name>]
- Interactive wizard mode
- Creates ~/.codex dir if missing
- Makes timestamped backup before writing (unless --no-backup)
- Optional: uses tomlkit if installed (better formatting preservation)
"""

from __future__ import annotations

import argparse
import ast
import datetime as _dt
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.codex/config.toml")


# -----------------------------
# TOML load/save (tomlkit optional)
# -----------------------------

def _try_import_tomlkit():
    try:
        import tomlkit  # type: ignore
        return tomlkit
    except Exception:
        return None


def load_toml(path: str) -> Tuple[Dict[str, Any], Optional[Any]]:
    """
    Returns (data_dict, tomlkit_doc_or_none)
    If tomlkit is available, returns parsed doc to preserve formatting.
    Otherwise uses tomllib/tomli and returns plain dict.
    """
    tomlkit = _try_import_tomlkit()
    if not os.path.exists(path):
        return {}, None

    with open(path, "rb") as f:
        raw = f.read()

    if tomlkit is not None:
        doc = tomlkit.parse(raw.decode("utf-8"))
        # Convert to plain dict for logic, but keep doc for nicer save if you want.
        # We'll still write with our dumper by default (predictable output),
        # unless user passes --use-tomlkit.
        return _tomlkit_to_plain(doc), doc

    # stdlib tomllib (py>=3.11) or tomli fallback
    try:
        import tomllib  # py3.11+
        data = tomllib.loads(raw.decode("utf-8"))
    except Exception:
        try:
            import tomli  # type: ignore
            data = tomli.loads(raw.decode("utf-8"))
        except Exception as e:
            raise RuntimeError(
                "Failed to parse TOML. Install tomlkit or tomli, or fix config.toml."
            ) from e
    return data, None


def _tomlkit_to_plain(obj: Any) -> Any:
    # tomlkit types are dict-like; convert recursively
    if isinstance(obj, dict):
        return {str(k): _tomlkit_to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_tomlkit_to_plain(x) for x in obj]
    return obj


def _toml_escape_string(s: str) -> str:
    # Use basic string with escapes
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{s}"'


def _toml_dump_value(v: Any) -> str:
    if v is None:
        raise ValueError("TOML has no null; remove the key instead.")
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        # TOML float
        return repr(v)
    if isinstance(v, str):
        return _toml_escape_string(v)
    if isinstance(v, list):
        return "[ " + ", ".join(_toml_dump_value(x) for x in v) + " ]"
    if isinstance(v, dict):
        # inline dict only (used for http_headers etc.)
        # only allow scalar/list values inside inline dict for safety
        parts = []
        for k, vv in v.items():
            if not isinstance(k, str):
                k = str(k)
            if isinstance(vv, dict):
                raise ValueError("Nested dict not supported in inline dict.")
            parts.append(f"{k} = {_toml_dump_value(vv)}")
        return "{ " + ", ".join(parts) + " }"
    raise TypeError(f"Unsupported type for TOML dump: {type(v)}")


def dump_toml(data: Dict[str, Any]) -> str:
    """
    Deterministic TOML writer for our limited needs.
    - root scalar/list/inline-dict keys first
    - then [model_providers.<id>]
    - then [profiles.<name>]
    - then other nested dicts as tables
    """
    lines: List[str] = []

    # 1) root simple keys
    def is_simple_value(x: Any) -> bool:
        return isinstance(x, (str, int, float, bool, list, dict))

    root_keys = [k for k, v in data.items() if not isinstance(v, dict) or k in ("model_providers", "profiles")]
    # Actually, model_providers/profiles are dict, but we handle later; exclude here.
    root_simple = []
    for k, v in data.items():
        if k in ("model_providers", "profiles"):
            continue
        if isinstance(v, dict):
            # other dict tables handled later
            continue
        if is_simple_value(v):
            root_simple.append(k)

    for k in sorted(root_simple):
        lines.append(f"{k} = {_toml_dump_value(data[k])}")

    # 2) model_providers
    mp = data.get("model_providers")
    if isinstance(mp, dict) and mp:
        for pid in sorted(mp.keys()):
            pv = mp[pid]
            if not isinstance(pv, dict):
                continue
            lines.append("")
            lines.append(f"[model_providers.{pid}]")
            for kk in sorted(pv.keys()):
                vv = pv[kk]
                if isinstance(vv, dict):
                    # keep inline dict (e.g., http_headers)
                    lines.append(f"{kk} = {_toml_dump_value(vv)}")
                else:
                    lines.append(f"{kk} = {_toml_dump_value(vv)}")

    # 3) profiles
    pf = data.get("profiles")
    if isinstance(pf, dict) and pf:
        for name in sorted(pf.keys()):
            pv = pf[name]
            if not isinstance(pv, dict):
                continue
            lines.append("")
            lines.append(f"[profiles.{name}]")
            for kk in sorted(pv.keys()):
                vv = pv[kk]
                if isinstance(vv, dict):
                    lines.append(f"{kk} = {_toml_dump_value(vv)}")
                else:
                    lines.append(f"{kk} = {_toml_dump_value(vv)}")

    # 4) other dict tables (top-level)
    other_tables = [k for k, v in data.items() if isinstance(v, dict) and k not in ("model_providers", "profiles")]
    for table_name in sorted(other_tables):
        table_val = data[table_name]
        if not isinstance(table_val, dict):
            continue
        # Only one-level table supported here; nested dicts are written as subtables recursively
        lines.extend(_dump_table_recursive([table_name], table_val))

    return "\n".join(lines).strip() + "\n"


def _dump_table_recursive(path_parts: List[str], table: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    # separate scalars vs nested dict
    scalars: Dict[str, Any] = {}
    nested: Dict[str, Dict[str, Any]] = {}

    for k, v in table.items():
        if isinstance(v, dict):
            nested[k] = v
        else:
            scalars[k] = v

    out.append("")
    out.append("[" + ".".join(path_parts) + "]")
    for k in sorted(scalars.keys()):
        out.append(f"{k} = {_toml_dump_value(scalars[k])}")

    for nk in sorted(nested.keys()):
        out.extend(_dump_table_recursive(path_parts + [nk], nested[nk]))
    return out


def ensure_parent_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def backup_file(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{path}.{ts}.bak"
    with open(path, "rb") as fsrc, open(bak, "wb") as fdst:
        fdst.write(fsrc.read())
    return bak


def save_toml(path: str, data: Dict[str, Any], *, make_backup: bool = True) -> Optional[str]:
    ensure_parent_dir(path)
    bak = backup_file(path) if make_backup else None
    content = dump_toml(data)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return bak


# -----------------------------
# Helpers: key path get/set
# -----------------------------

_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def parse_kv(s: str) -> Tuple[str, str]:
    if "=" not in s:
        raise argparse.ArgumentTypeError("Expected KEY=VALUE")
    k, v = s.split("=", 1)
    k = k.strip()
    v = v.strip()
    if not k:
        raise argparse.ArgumentTypeError("Empty key in KEY=VALUE")
    return k, v


def smart_parse_value(raw: str) -> Any:
    """
    Parse CLI values:
    - "true"/"false" -> bool
    - numbers -> int/float
    - strings remain strings
    - If starts with '[' or '{' -> ast.literal_eval to list/dict
      (Use Python literal syntax, e.g. {"A":"B"} or ["x","y"])
    - If wrapped in quotes, keep as string (handled naturally)
    """
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False

    # number?
    if re.fullmatch(r"-?\d+", raw):
        try:
            return int(raw)
        except Exception:
            pass
    if re.fullmatch(r"-?\d+\.\d+", raw):
        try:
            return float(raw)
        except Exception:
            pass

    if raw.startswith("[") or raw.startswith("{"):
        try:
            v = ast.literal_eval(raw)
            return v
        except Exception as e:
            raise ValueError(f"Failed to parse literal value: {raw}") from e

    return raw


def get_path(data: Dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    cur: Any = data
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            raise KeyError(path)
        cur = cur[p]
    return cur


def set_path(data: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur: Any = data
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def del_path(data: Dict[str, Any], path: str) -> None:
    parts = path.split(".")
    cur: Any = data
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            raise KeyError(path)
        cur = cur[p]
    if parts[-1] not in cur:
        raise KeyError(path)
    del cur[parts[-1]]


# -----------------------------
# Templates for providers
# -----------------------------

PROVIDER_TEMPLATES = {
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "wire_api": "chat",
        "http_headers": {},  # user may add HTTP-Referer / X-Title
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "wire_api": "chat",
    },
    "gemini": {
        "name": "Gemini (OpenAI-compatible)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "env_key": "GEMINI_API_KEY",
        "wire_api": "chat",
    },
}


# -----------------------------
# Printing
# -----------------------------

def print_summary(data: Dict[str, Any]) -> None:
    print("== Root ==")
    for k in ("model_provider", "model"):
        if k in data:
            print(f"- {k}: {data.get(k)}")
    extra = [k for k in data.keys() if k not in ("model_provider", "model", "model_providers", "profiles")]
    if extra:
        print(f"- other root keys: {', '.join(sorted(extra))}")

    print("\n== Providers (model_providers) ==")
    mp = data.get("model_providers", {})
    if not isinstance(mp, dict) or not mp:
        print("(none)")
    else:
        for pid in sorted(mp.keys()):
            pv = mp.get(pid, {})
            if isinstance(pv, dict):
                print(f"- {pid}: base_url={pv.get('base_url')!r}, env_key={pv.get('env_key')!r}, wire_api={pv.get('wire_api')!r}")
            else:
                print(f"- {pid}: (invalid entry)")

    print("\n== Profiles ==")
    pf = data.get("profiles", {})
    if not isinstance(pf, dict) or not pf:
        print("(none)")
    else:
        for name in sorted(pf.keys()):
            pv = pf.get(name, {})
            if isinstance(pv, dict):
                print(f"- {name}: model_provider={pv.get('model_provider')!r}, model={pv.get('model')!r}")
            else:
                print(f"- {name}: (invalid entry)")


# -----------------------------
# Interactive wizard
# -----------------------------

def prompt(msg: str, default: Optional[str] = None) -> str:
    if default is not None:
        s = input(f"{msg} [{default}]: ").strip()
        return s if s else default
    return input(f"{msg}: ").strip()


def interactive_mode(path: str, data: Dict[str, Any], *, make_backup: bool = True) -> None:
    while True:
        print("\n------------------------------")
        print(f"Config: {path}")
        print_summary(data)
        print("------------------------------")
        print("1) Set root model/model_provider")
        print("2) Manage providers (add/update/delete)")
        print("3) Manage profiles (add/update/delete)")
        print("4) Get a key path")
        print("5) Set a key path")
        print("6) Delete a key path")
        print("7) Save & exit")
        print("0) Exit without saving")
        choice = input("Choose: ").strip()

        if choice == "1":
            mp = prompt("root model_provider", str(data.get("model_provider", "")) or None)
            m = prompt("root model", str(data.get("model", "")) or None)
            if mp:
                data["model_provider"] = mp
            if m:
                data["model"] = m

        elif choice == "2":
            print("\nProviders:")
            mp = data.setdefault("model_providers", {})
            if not isinstance(mp, dict):
                data["model_providers"] = {}
                mp = data["model_providers"]
            for pid in sorted(mp.keys()):
                print(f"- {pid}")
            print("a) add   u) update   d) delete   b) back")
            sub = input("Choose: ").strip().lower()
            if sub == "a":
                pid = prompt("provider id (e.g., openrouter)")
                tmpl = prompt("template (openrouter/deepseek/gemini/none)", "none").lower()
                pv = {}
                if tmpl in PROVIDER_TEMPLATES:
                    pv.update(PROVIDER_TEMPLATES[tmpl])
                name = prompt("name", pv.get("name", pid))
                base_url = prompt("base_url", pv.get("base_url", ""))
                env_key = prompt("env_key", pv.get("env_key", ""))
                wire_api = prompt("wire_api (chat/responses)", pv.get("wire_api", "chat"))
                pv["name"] = name
                pv["base_url"] = base_url
                pv["env_key"] = env_key
                pv["wire_api"] = wire_api

                # headers
                headers = pv.get("http_headers", {})
                if not isinstance(headers, dict):
                    headers = {}
                while True:
                    addh = prompt("Add http header KEY=VALUE (empty to stop)", "")
                    if not addh:
                        break
                    k, v = parse_kv(addh)
                    headers[k] = v
                if headers:
                    pv["http_headers"] = headers
                mp[pid] = pv
                print(f"Provider '{pid}' added/updated.")

            elif sub == "u":
                pid = prompt("provider id to update")
                if pid not in mp or not isinstance(mp[pid], dict):
                    print("Not found.")
                    continue
                pv = mp[pid]
                pv["name"] = prompt("name", pv.get("name", pid))
                pv["base_url"] = prompt("base_url", pv.get("base_url", ""))
                pv["env_key"] = prompt("env_key", pv.get("env_key", ""))
                pv["wire_api"] = prompt("wire_api (chat/responses)", pv.get("wire_api", "chat"))
                headers = pv.get("http_headers", {})
                if not isinstance(headers, dict):
                    headers = {}
                while True:
                    print(f"Current headers: {headers}")
                    op = prompt("headers: (a)dd (r)emove (b)ack", "b").lower()
                    if op == "b":
                        break
                    if op == "a":
                        kv = prompt("KEY=VALUE")
                        k, v = parse_kv(kv)
                        headers[k] = v
                    if op == "r":
                        hk = prompt("Header key to remove")
                        headers.pop(hk, None)
                if headers:
                    pv["http_headers"] = headers
                else:
                    pv.pop("http_headers", None)
                mp[pid] = pv
                print(f"Provider '{pid}' updated.")

            elif sub == "d":
                pid = prompt("provider id to delete")
                if pid in mp:
                    del mp[pid]
                    print("Deleted.")
                else:
                    print("Not found.")

        elif choice == "3":
            print("\nProfiles:")
            pf = data.setdefault("profiles", {})
            if not isinstance(pf, dict):
                data["profiles"] = {}
                pf = data["profiles"]
            for name in sorted(pf.keys()):
                print(f"- {name}")
            print("a) add   u) update   d) delete   b) back")
            sub = input("Choose: ").strip().lower()
            if sub == "a":
                name = prompt("profile name (e.g., ds)")
                mp = prompt("model_provider", "")
                m = prompt("model", "")
                pv = {}
                if mp:
                    pv["model_provider"] = mp
                if m:
                    pv["model"] = m
                pf[name] = pv
                print(f"Profile '{name}' added/updated.")

            elif sub == "u":
                name = prompt("profile name to update")
                if name not in pf or not isinstance(pf[name], dict):
                    print("Not found.")
                    continue
                pv = pf[name]
                pv["model_provider"] = prompt("model_provider", pv.get("model_provider", ""))
                pv["model"] = prompt("model", pv.get("model", ""))
                pf[name] = pv
                print(f"Profile '{name}' updated.")

            elif sub == "d":
                name = prompt("profile name to delete")
                if name in pf:
                    del pf[name]
                    print("Deleted.")
                else:
                    print("Not found.")

        elif choice == "4":
            p = prompt("Key path (e.g., model_providers.openrouter.base_url)")
            try:
                v = get_path(data, p)
                print(f"{p} = {v!r}")
            except KeyError:
                print("Not found.")

        elif choice == "5":
            p = prompt("Key path")
            rv = prompt("Value (supports true/false, numbers, [..], {..})")
            try:
                v = smart_parse_value(rv)
                set_path(data, p, v)
                print("Set.")
            except Exception as e:
                print(f"Error: {e}")

        elif choice == "6":
            p = prompt("Key path to delete")
            try:
                del_path(data, p)
                print("Deleted.")
            except KeyError:
                print("Not found.")

        elif choice == "7":
            bak = save_toml(path, data, make_backup=make_backup)
            if bak:
                print(f"Saved. Backup: {bak}")
            else:
                print("Saved.")
            return

        elif choice == "0":
            print("Exit without saving.")
            return

        else:
            print("Invalid choice.")


# -----------------------------
# CLI actions
# -----------------------------

def apply_sets(target: Dict[str, Any], sets: List[str]) -> None:
    for s in sets:
        k, raw = parse_kv(s)
        target[k] = smart_parse_value(raw)


def cmd_list(args: argparse.Namespace) -> int:
    data, _ = load_toml(args.config)
    print_summary(data)
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    data, _ = load_toml(args.config)
    try:
        v = get_path(data, args.path)
        print(v)
        return 0
    except KeyError:
        print("NOT_FOUND", file=sys.stderr)
        return 2


def cmd_set_root(args: argparse.Namespace) -> int:
    data, _ = load_toml(args.config)

    if args.model_provider is not None:
        data["model_provider"] = args.model_provider
    if args.model is not None:
        data["model"] = args.model
    if args.set:
        apply_sets(data, args.set)

    bak = save_toml(args.config, data, make_backup=not args.no_backup)
    if bak:
        print(f"OK (backup: {bak})")
    else:
        print("OK")
    return 0


def _ensure_dict(d: Dict[str, Any], key: str) -> Dict[str, Any]:
    v = d.get(key)
    if v is None:
        d[key] = {}
        return d[key]
    if not isinstance(v, dict):
        d[key] = {}
        return d[key]
    return v


def cmd_provider_add_or_update(args: argparse.Namespace, *, update_only: bool) -> int:
    data, _ = load_toml(args.config)
    mp = _ensure_dict(data, "model_providers")

    if update_only and args.provider_id not in mp:
        print("NOT_FOUND", file=sys.stderr)
        return 2

    pv: Dict[str, Any] = {}
    if args.template and args.template in PROVIDER_TEMPLATES:
        pv.update(PROVIDER_TEMPLATES[args.template])

    # merge existing if update
    if args.provider_id in mp and isinstance(mp[args.provider_id], dict):
        existing = mp[args.provider_id]
        pv = {**existing, **pv}

    if args.name is not None:
        pv["name"] = args.name
    else:
        pv.setdefault("name", args.provider_id)

    if args.base_url is not None:
        pv["base_url"] = args.base_url
    if args.env_key is not None:
        pv["env_key"] = args.env_key
    if args.wire_api is not None:
        pv["wire_api"] = args.wire_api

    # headers
    if args.header:
        headers = pv.get("http_headers")
        if not isinstance(headers, dict):
            headers = {}
        for kv in args.header:
            k, v = parse_kv(kv)
            headers[k] = v
        pv["http_headers"] = headers

    # generic sets
    if args.set:
        for s in args.set:
            k, raw = parse_kv(s)
            pv[k] = smart_parse_value(raw)

    mp[args.provider_id] = pv

    bak = save_toml(args.config, data, make_backup=not args.no_backup)
    if bak:
        print(f"OK (backup: {bak})")
    else:
        print("OK")
    return 0


def cmd_provider_delete(args: argparse.Namespace) -> int:
    data, _ = load_toml(args.config)
    mp = data.get("model_providers")
    if not isinstance(mp, dict) or args.provider_id not in mp:
        print("NOT_FOUND", file=sys.stderr)
        return 2
    del mp[args.provider_id]
    bak = save_toml(args.config, data, make_backup=not args.no_backup)
    if bak:
        print(f"OK (backup: {bak})")
    else:
        print("OK")
    return 0


def cmd_profile_add_or_update(args: argparse.Namespace, *, update_only: bool) -> int:
    data, _ = load_toml(args.config)
    pf = _ensure_dict(data, "profiles")

    if update_only and args.profile not in pf:
        print("NOT_FOUND", file=sys.stderr)
        return 2

    pv: Dict[str, Any] = {}
    if args.profile in pf and isinstance(pf[args.profile], dict):
        pv = dict(pf[args.profile])

    if args.model_provider is not None:
        pv["model_provider"] = args.model_provider
    if args.model is not None:
        pv["model"] = args.model
    if args.set:
        apply_sets(pv, args.set)

    pf[args.profile] = pv

    bak = save_toml(args.config, data, make_backup=not args.no_backup)
    if bak:
        print(f"OK (backup: {bak})")
    else:
        print("OK")
    return 0


def cmd_profile_delete(args: argparse.Namespace) -> int:
    data, _ = load_toml(args.config)
    pf = data.get("profiles")
    if not isinstance(pf, dict) or args.profile not in pf:
        print("NOT_FOUND", file=sys.stderr)
        return 2
    del pf[args.profile]
    bak = save_toml(args.config, data, make_backup=not args.no_backup)
    if bak:
        print(f"OK (backup: {bak})")
    else:
        print("OK")
    return 0


def cmd_delete_path(args: argparse.Namespace) -> int:
    data, _ = load_toml(args.config)
    try:
        del_path(data, args.path)
    except KeyError:
        print("NOT_FOUND", file=sys.stderr)
        return 2

    bak = save_toml(args.config, data, make_backup=not args.no_backup)
    if bak:
        print(f"OK (backup: {bak})")
    else:
        print("OK")
    return 0


def cmd_interactive(args: argparse.Namespace) -> int:
    data, _ = load_toml(args.config)
    interactive_mode(args.config, data, make_backup=not args.no_backup)
    return 0


# -----------------------------
# Main
# -----------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="codex_config_tool",
        description="CRUD tool for Codex ~/.codex/config.toml (root/providers/profiles).",
    )
    p.add_argument("--config", default=DEFAULT_CONFIG_PATH, help=f"Config path (default: {DEFAULT_CONFIG_PATH})")
    p.add_argument("--no-backup", action="store_true", help="Do not create timestamped .bak backup on write")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="Show summary of config")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("get", help="Get a value by path (dot-separated)")
    sp.add_argument("path", help="e.g. model, model_providers.openrouter.base_url, profiles.ds.model")
    sp.set_defaults(func=cmd_get)

    sp = sub.add_parser("set-root", help="Set root model/model_provider and/or arbitrary root keys")
    sp.add_argument("--model", help="Set root 'model'")
    sp.add_argument("--model_provider", help="Set root 'model_provider'")
    sp.add_argument("--set", action="append", default=[], help="Set arbitrary root key: KEY=VALUE (repeatable)")
    sp.set_defaults(func=cmd_set_root)

    sp = sub.add_parser("delete-path", help="Delete a key by path")
    sp.add_argument("path", help="e.g. profiles.ds, model_providers.openrouter.http_headers")
    sp.set_defaults(func=cmd_delete_path)

    # provider add/update/delete
    sp = sub.add_parser("provider-add", help="Add a provider under [model_providers.<id>]")
    sp.add_argument("provider_id", help="Provider id, e.g. openrouter/deepseek/gemini")
    sp.add_argument("--template", choices=list(PROVIDER_TEMPLATES.keys()), help="Use a provider template")
    sp.add_argument("--name", help="Provider display name")
    sp.add_argument("--base_url", help="Provider base_url")
    sp.add_argument("--env_key", help="Environment variable name for API key")
    sp.add_argument("--wire_api", choices=["chat", "responses"], help="Wire API: chat or responses")
    sp.add_argument("--header", action="append", default=[], help="Add http header KEY=VALUE (repeatable)")
    sp.add_argument("--set", action="append", default=[], help="Set arbitrary provider key: KEY=VALUE (repeatable)")
    sp.set_defaults(func=lambda a: cmd_provider_add_or_update(a, update_only=False))

    sp = sub.add_parser("provider-update", help="Update an existing provider")
    sp.add_argument("provider_id")
    sp.add_argument("--template", choices=list(PROVIDER_TEMPLATES.keys()), help="Use a provider template as defaults")
    sp.add_argument("--name")
    sp.add_argument("--base_url")
    sp.add_argument("--env_key")
    sp.add_argument("--wire_api", choices=["chat", "responses"])
    sp.add_argument("--header", action="append", default=[])
    sp.add_argument("--set", action="append", default=[])
    sp.set_defaults(func=lambda a: cmd_provider_add_or_update(a, update_only=True))

    sp = sub.add_parser("provider-delete", help="Delete a provider")
    sp.add_argument("provider_id")
    sp.set_defaults(func=cmd_provider_delete)

    # profile add/update/delete
    sp = sub.add_parser("profile-add", help="Add a profile under [profiles.<name>]")
    sp.add_argument("profile", help="Profile name, e.g. ds/or")
    sp.add_argument("--model", help="Set profile 'model'")
    sp.add_argument("--model_provider", help="Set profile 'model_provider'")
    sp.add_argument("--set", action="append", default=[], help="Set arbitrary profile key: KEY=VALUE (repeatable)")
    sp.set_defaults(func=lambda a: cmd_profile_add_or_update(a, update_only=False))

    sp = sub.add_parser("profile-update", help="Update an existing profile")
    sp.add_argument("profile")
    sp.add_argument("--model")
    sp.add_argument("--model_provider")
    sp.add_argument("--set", action="append", default=[])
    sp.set_defaults(func=lambda a: cmd_profile_add_or_update(a, update_only=True))

    sp = sub.add_parser("profile-delete", help="Delete a profile")
    sp.add_argument("profile")
    sp.set_defaults(func=cmd_profile_delete)

    sp = sub.add_parser("interactive", help="Interactive wizard mode")
    sp.set_defaults(func=cmd_interactive)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
