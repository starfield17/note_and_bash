#!/usr/bin/env python3
"""
Claude Code Configuration Manager
Used to configure the ~/.claude/settings.json file for Claude Code.
Supports both interactive menu and command-line argument modes.

Optimized UI version with better visual feedback and navigation.
"""

import argparse
import json
import os
import sys
import shutil
from pathlib import Path
from typing import Any, Optional, Tuple

# ========================
#       Constants
# ========================
CONFIG_DIR = Path.home() / ".claude"
CONFIG_FILE = CONFIG_DIR / "settings.json"
CLAUDE_JSON_FILE = Path.home() / ".claude.json"

# Preset Configurations
PRESETS = {
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api",
        "description": "Supports various models (GPT/Gemini/Claude, etc.)",
        "env": {
            "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        },
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/anthropic",
        "description": "High cost-performance models",
        "env": {
            "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
            "ANTHROPIC_MODEL": "deepseek-chat",
            "ANTHROPIC_SMALL_FAST_MODEL": "deepseek-chat",
            "API_TIMEOUT_MS": "600000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        },
    },
    "zhipu": {
        "name": "Zhipu AI (BigModel)",
        "base_url": "https://open.bigmodel.cn/api/anthropic",
        "description": "GLM series models",
        "env": {
            "ANTHROPIC_BASE_URL": "https://open.bigmodel.cn/api/anthropic",
            "API_TIMEOUT_MS": "3000000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        },
    },
    "anthropic": {
        "name": "Anthropic (Official)",
        "base_url": "https://api.anthropic.com",
        "description": "Anthropic Official API",
        "env": {
            "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
        },
    },
}

# Environment Variable Descriptions
ENV_VARS_INFO = {
    "ANTHROPIC_BASE_URL": "API Base URL",
    "ANTHROPIC_AUTH_TOKEN": "Bearer Token Auth (Recommended)",
    "ANTHROPIC_API_KEY": "X-Api-Key Auth",
    "ANTHROPIC_MODEL": "Default Model",
    "ANTHROPIC_SMALL_FAST_MODEL": "Small/Fast Model",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "Sonnet Tier Model Mapping",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "Opus Tier Model Mapping",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "Haiku Tier Model Mapping",
    "API_TIMEOUT_MS": "API Timeout (milliseconds)",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "Disable Non-essential Traffic",
}


# ========================
#       UI Components
# ========================
class Colors:
    """Terminal Colors with more options"""
    # Basic colors
    BLACK = '\033[30m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    
    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    
    # Reset
    END = '\033[0m'
    
    # Semantic colors
    SUCCESS = GREEN
    ERROR = RED
    WARNING = YELLOW
    INFO = BLUE
    ACCENT = CYAN
    MUTED = DIM


class Box:
    """Box drawing characters for UI"""
    # Single line
    H = '─'
    V = '│'
    TL = '┌'
    TR = '┐'
    BL = '└'
    BR = '┘'
    LT = '├'
    RT = '┤'
    TT = '┬'
    BT = '┴'
    X = '┼'
    
    # Double line
    DH = '═'
    DV = '║'
    DTL = '╔'
    DTR = '╗'
    DBL = '╚'
    DBR = '╝'
    
    # Rounded
    RTL = '╭'
    RTR = '╮'
    RBL = '╰'
    RBR = '╯'


class UI:
    """UI Helper Functions"""
    
    @staticmethod
    def get_terminal_size() -> Tuple[int, int]:
        """Get terminal size (columns, rows)"""
        size = shutil.get_terminal_size((80, 24))
        return size.columns, size.lines
    
    @staticmethod
    def clear_screen() -> None:
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def center_text(text: str, width: int) -> str:
        """Center text within given width"""
        return text.center(width)
    
    @staticmethod
    def draw_box(title: str, content: list[str], width: int = 60, style: str = "rounded") -> str:
        """Draw a box with title and content"""
        if style == "rounded":
            tl, tr, bl, br = Box.RTL, Box.RTR, Box.RBL, Box.RBR
        elif style == "double":
            tl, tr, bl, br = Box.DTL, Box.DTR, Box.DBL, Box.DBR
        else:
            tl, tr, bl, br = Box.TL, Box.TR, Box.BL, Box.BR
        
        h = Box.DH if style == "double" else Box.H
        v = Box.DV if style == "double" else Box.V
        
        inner_width = width - 2
        lines = []
        
        # Top border with title
        if title:
            title_display = f" {title} "
            padding = inner_width - len(title_display)
            left_pad = padding // 2
            right_pad = padding - left_pad
            lines.append(f"{tl}{h * left_pad}{Colors.BOLD}{Colors.ACCENT}{title_display}{Colors.END}{h * right_pad}{tr}")
        else:
            lines.append(f"{tl}{h * inner_width}{tr}")
        
        # Content
        for line in content:
            # Strip ANSI codes for length calculation
            import re
            clean_line = re.sub(r'\033\[[0-9;]*m', '', line)
            padding = inner_width - len(clean_line)
            lines.append(f"{v}{line}{' ' * padding}{v}")
        
        # Bottom border
        lines.append(f"{bl}{h * inner_width}{br}")
        
        return '\n'.join(lines)
    
    @staticmethod
    def draw_separator(char: str = Box.H, width: int = 60) -> str:
        """Draw a horizontal separator"""
        return f"{Colors.DIM}{char * width}{Colors.END}"
    
    @staticmethod
    def format_menu_item(number: str, text: str, hint: str = "", selected: bool = False) -> str:
        """Format a menu item"""
        if selected:
            prefix = f"{Colors.ACCENT}{Colors.BOLD}▶{Colors.END}"
        else:
            prefix = " "
        
        num_display = f"{Colors.ACCENT}{Colors.BOLD}[{number}]{Colors.END}"
        text_display = f"{Colors.WHITE}{text}{Colors.END}"
        
        if hint:
            hint_display = f"{Colors.DIM}  {hint}{Colors.END}"
            return f" {prefix} {num_display} {text_display}{hint_display}"
        return f" {prefix} {num_display} {text_display}"
    
    @staticmethod
    def prompt(text: str, default: str = "") -> str:
        """Display a styled prompt and get input"""
        default_hint = f" {Colors.DIM}[{default}]{Colors.END}" if default else ""
        try:
            result = input(f"\n {Colors.ACCENT}▸{Colors.END} {text}{default_hint}: ").strip()
            return result if result else default
        except EOFError:
            return default
    
    @staticmethod
    def confirm(text: str, default: bool = False) -> bool:
        """Display a confirmation prompt"""
        hint = "[Y/n]" if default else "[y/N]"
        try:
            result = input(f"\n {Colors.WARNING}?{Colors.END} {text} {Colors.DIM}{hint}{Colors.END}: ").strip().lower()
            if not result:
                return default
            return result in ('y', 'yes')
        except EOFError:
            return default
    
    @staticmethod
    def print_success(msg: str) -> None:
        print(f"\n {Colors.SUCCESS}✓{Colors.END} {msg}")
    
    @staticmethod
    def print_error(msg: str) -> None:
        print(f"\n {Colors.ERROR}✗{Colors.END} {msg}", file=sys.stderr)
    
    @staticmethod
    def print_warning(msg: str) -> None:
        print(f"\n {Colors.WARNING}!{Colors.END} {msg}")
    
    @staticmethod
    def print_info(msg: str) -> None:
        print(f"\n {Colors.INFO}ℹ{Colors.END} {msg}")
    
    @staticmethod
    def wait_for_key(msg: str = "Press Enter to continue...") -> None:
        """Wait for user to press Enter"""
        try:
            input(f"\n {Colors.DIM}{msg}{Colors.END}")
        except EOFError:
            pass


# ========================
#       Helper Functions
# ========================
def ensure_config_dir() -> None:
    """Ensure configuration directory exists"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load configuration file"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            UI.print_warning("Config file format error, creating new configuration.")
            return {}
    return {}


def save_config(config: dict) -> bool:
    """Save configuration file"""
    try:
        ensure_config_dir()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        UI.print_error(f"Failed to save config: {e}")
        return False


def load_claude_json() -> dict:
    """Load ~/.claude.json file"""
    if CLAUDE_JSON_FILE.exists():
        try:
            with open(CLAUDE_JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_claude_json(config: dict) -> bool:
    """Save ~/.claude.json file"""
    try:
        with open(CLAUDE_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        UI.print_error(f"Failed to save ~/.claude.json: {e}")
        return False


# ========================
#       Config Operations
# ========================
def get_env_value(config: dict, key: str) -> Optional[str]:
    """Get environment variable value"""
    return config.get("env", {}).get(key)


def set_env_value(config: dict, key: str, value: str) -> dict:
    """Set environment variable value"""
    if "env" not in config:
        config["env"] = {}
    config["env"][key] = value
    return config


def delete_env_value(config: dict, key: str) -> dict:
    """Delete environment variable"""
    if "env" in config and key in config["env"]:
        del config["env"][key]
    return config


def mask_sensitive(key: str, value: str) -> str:
    """Mask sensitive values for display"""
    if "TOKEN" in key or "KEY" in key:
        if len(value) > 10:
            return value[:6] + "•" * 8 + value[-4:]
        elif len(value) > 4:
            return value[:2] + "•" * (len(value) - 4) + value[-2:]
    return value


def display_config(config: dict) -> None:
    """Display configuration in a formatted box"""
    env = config.get("env", {})
    
    if not env:
        UI.print_warning("No environment variables configured.")
        return
    
    content = []
    for key, value in env.items():
        desc = ENV_VARS_INFO.get(key, "Custom")
        display_value = mask_sensitive(key, value)
        
        content.append(f" {Colors.CYAN}{key}{Colors.END}")
        content.append(f"   {Colors.DIM}├─{Colors.END} {desc}")
        content.append(f"   {Colors.DIM}└─{Colors.END} {Colors.GREEN}{display_value}{Colors.END}")
        content.append("")
    
    # Remove last empty line
    if content and content[-1] == "":
        content.pop()
    
    print()
    print(UI.draw_box("Current Configuration", content, width=70))


def apply_preset(config: dict, preset_name: str, api_key: Optional[str] = None) -> dict:
    """Apply preset configuration"""
    if preset_name not in PRESETS:
        UI.print_error(f"Unknown preset: {preset_name}")
        return config
    
    preset = PRESETS[preset_name]
    if "env" not in config:
        config["env"] = {}
    
    # Apply preset environment variables
    for key, value in preset["env"].items():
        config["env"][key] = value
    
    # Set API Key if provided
    if api_key:
        config["env"]["ANTHROPIC_AUTH_TOKEN"] = api_key
    
    UI.print_success(f"Applied preset: {preset['name']}")
    return config


def complete_onboarding() -> None:
    """Complete Claude Code onboarding"""
    claude_json = load_claude_json()
    claude_json["hasCompletedOnboarding"] = True
    if save_claude_json(claude_json):
        UI.print_success("Onboarding configuration completed.")


# ========================
#       Interactive Menu
# ========================
def draw_header() -> None:
    """Draw the application header"""
    width, _ = UI.get_terminal_size()
    box_width = min(70, width - 4)
    
    title_lines = [
        "",
        f"{Colors.BOLD}Claude Code Configuration Manager{Colors.END}",
        "",
        f"{Colors.DIM}Config: {CONFIG_FILE}{Colors.END}",
        "",
    ]
    
    print(UI.draw_box("", title_lines, width=box_width, style="double"))


def draw_main_menu() -> None:
    """Draw the main menu"""
    print()
    print(f" {Colors.BOLD}Main Menu{Colors.END}")
    print(UI.draw_separator(width=50))
    print()
    print(UI.format_menu_item("1", "View Current Config", "Show all settings"))
    print(UI.format_menu_item("2", "Use Preset Config", "Quick setup ★"))
    print(UI.format_menu_item("3", "Set Environment Variable"))
    print(UI.format_menu_item("4", "Delete Environment Variable"))
    print()
    print(f" {Colors.DIM}── Quick Settings ──{Colors.END}")
    print()
    print(UI.format_menu_item("5", "Set API Key"))
    print(UI.format_menu_item("6", "Set Base URL"))
    print(UI.format_menu_item("7", "Set Model"))
    print()
    print(f" {Colors.DIM}── Other ──{Colors.END}")
    print()
    print(UI.format_menu_item("8", "Complete Onboarding"))
    print(UI.format_menu_item("9", "Reset Configuration", "⚠ Danger"))
    print(UI.format_menu_item("0", "Exit", "Ctrl+C"))
    print()


def interactive_menu() -> None:
    """Interactive Configuration Menu"""
    while True:
        UI.clear_screen()
        draw_header()
        draw_main_menu()
        
        choice = UI.prompt("Select an option", "0")
        
        if choice == "0":
            UI.clear_screen()
            print(f"\n {Colors.SUCCESS}Goodbye! 👋{Colors.END}\n")
            break
        elif choice == "1":
            menu_view_config()
        elif choice == "2":
            menu_apply_preset()
        elif choice == "3":
            menu_set_env()
        elif choice == "4":
            menu_delete_env()
        elif choice == "5":
            menu_set_api_key()
        elif choice == "6":
            menu_set_base_url()
        elif choice == "7":
            menu_set_model()
        elif choice == "8":
            complete_onboarding()
            UI.wait_for_key()
        elif choice == "9":
            menu_reset_config()
        else:
            UI.print_error("Invalid selection, please try again.")
            UI.wait_for_key()


def menu_view_config() -> None:
    """Menu: View Configuration"""
    UI.clear_screen()
    print(f"\n {Colors.BOLD}📋 Current Configuration{Colors.END}")
    print(UI.draw_separator(width=50))
    
    config = load_config()
    display_config(config)
    
    UI.wait_for_key()


def menu_apply_preset() -> None:
    """Menu: Apply Preset Configuration"""
    UI.clear_screen()
    print(f"\n {Colors.BOLD}⚡ Quick Setup - Select Preset{Colors.END}")
    print(UI.draw_separator(width=50))
    print()
    
    presets_list = list(PRESETS.items())
    for i, (key, preset) in enumerate(presets_list, 1):
        print(UI.format_menu_item(str(i), preset['name']))
        print(f"      {Colors.DIM}{preset['description']}{Colors.END}")
        print(f"      {Colors.DIM}URL: {preset['base_url']}{Colors.END}")
        print()
    
    print(UI.format_menu_item("0", "Back"))
    print()
    
    choice = UI.prompt("Select a preset", "0")
    
    if choice == "0":
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(presets_list):
            preset_key = presets_list[idx][0]
            preset_name = presets_list[idx][1]['name']
            
            print()
            print(f" {Colors.INFO}ℹ{Colors.END} Setting up {Colors.ACCENT}{preset_name}{Colors.END}")
            
            # Ask for API Key
            api_key = UI.prompt("Enter API Key (leave blank to skip)")
            
            config = load_config()
            config = apply_preset(config, preset_key, api_key if api_key else None)
            
            if save_config(config):
                UI.print_success("Configuration saved!")
            
            # Ask to complete onboarding
            if UI.confirm("Also complete onboarding?", default=True):
                complete_onboarding()
            
            UI.wait_for_key()
        else:
            UI.print_error("Invalid selection")
            UI.wait_for_key()
    except ValueError:
        UI.print_error("Please enter a valid number")
        UI.wait_for_key()


def menu_set_env() -> None:
    """Menu: Set Environment Variable"""
    UI.clear_screen()
    print(f"\n {Colors.BOLD}🔧 Set Environment Variable{Colors.END}")
    print(UI.draw_separator(width=50))
    print()
    print(f" {Colors.DIM}Common variables:{Colors.END}")
    print()
    
    for key, desc in ENV_VARS_INFO.items():
        print(f"   {Colors.CYAN}{key}{Colors.END}")
        print(f"   {Colors.DIM}└─ {desc}{Colors.END}")
        print()
    
    key = UI.prompt("Variable name (or 0 to cancel)")
    if not key or key == "0":
        return
    
    value = UI.prompt("Value")
    if not value:
        UI.print_warning("Value cannot be empty")
        UI.wait_for_key()
        return
    
    config = load_config()
    config = set_env_value(config, key, value)
    if save_config(config):
        UI.print_success(f"Set {key}")
    UI.wait_for_key()


def menu_delete_env() -> None:
    """Menu: Delete Environment Variable"""
    config = load_config()
    env = config.get("env", {})
    
    if not env:
        UI.print_warning("No environment variables configured.")
        UI.wait_for_key()
        return
    
    UI.clear_screen()
    print(f"\n {Colors.BOLD}🗑️  Delete Environment Variable{Colors.END}")
    print(UI.draw_separator(width=50))
    print()
    
    keys = list(env.keys())
    for i, key in enumerate(keys, 1):
        value = mask_sensitive(key, env[key])
        print(UI.format_menu_item(str(i), key))
        print(f"      {Colors.DIM}= {value}{Colors.END}")
        print()
    
    print(UI.format_menu_item("0", "Back"))
    print()
    
    choice = UI.prompt("Select variable to delete", "0")
    
    if choice == "0":
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(keys):
            key = keys[idx]
            if UI.confirm(f"Delete {Colors.CYAN}{key}{Colors.END}?", default=False):
                config = delete_env_value(config, key)
                if save_config(config):
                    UI.print_success(f"Deleted {key}")
        else:
            UI.print_error("Invalid selection")
    except ValueError:
        UI.print_error("Please enter a valid number")
    
    UI.wait_for_key()


def menu_set_api_key() -> None:
    """Menu: Set API Key"""
    UI.clear_screen()
    print(f"\n {Colors.BOLD}🔑 Set API Key{Colors.END}")
    print(UI.draw_separator(width=50))
    print()
    print(f" {Colors.DIM}Authentication Method:{Colors.END}")
    print()
    print(UI.format_menu_item("1", "ANTHROPIC_AUTH_TOKEN", "Bearer Token ★"))
    print(UI.format_menu_item("2", "ANTHROPIC_API_KEY", "X-Api-Key"))
    print()
    print(UI.format_menu_item("0", "Back"))
    print()
    
    choice = UI.prompt("Select auth method", "1")
    
    if choice == "0":
        return
    elif choice == "1":
        key_name = "ANTHROPIC_AUTH_TOKEN"
    elif choice == "2":
        key_name = "ANTHROPIC_API_KEY"
    else:
        UI.print_error("Invalid selection")
        UI.wait_for_key()
        return
    
    api_key = UI.prompt("Enter API Key")
    if not api_key:
        UI.print_warning("API Key cannot be empty")
        UI.wait_for_key()
        return
    
    config = load_config()
    config = set_env_value(config, key_name, api_key)
    if save_config(config):
        UI.print_success(f"Set {key_name}")
    UI.wait_for_key()


def menu_set_base_url() -> None:
    """Menu: Set Base URL"""
    UI.clear_screen()
    print(f"\n {Colors.BOLD}🌐 Set Base URL{Colors.END}")
    print(UI.draw_separator(width=50))
    print()
    print(f" {Colors.DIM}Common URLs:{Colors.END}")
    print()
    
    for i, (key, preset) in enumerate(PRESETS.items(), 1):
        print(UI.format_menu_item(str(i), preset['name']))
        print(f"      {Colors.DIM}{preset['base_url']}{Colors.END}")
        print()
    
    print(UI.format_menu_item("c", "Custom URL"))
    print(UI.format_menu_item("0", "Back"))
    print()
    
    choice = UI.prompt("Select or enter 'c' for custom", "0")
    
    if choice == "0":
        return
    
    preset_list = list(PRESETS.values())
    
    if choice == "c":
        url = UI.prompt("Enter custom Base URL")
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(preset_list):
                url = preset_list[idx]['base_url']
            else:
                UI.print_error("Invalid selection")
                UI.wait_for_key()
                return
        except ValueError:
            UI.print_error("Invalid input")
            UI.wait_for_key()
            return
    
    if not url:
        UI.print_warning("URL cannot be empty")
        UI.wait_for_key()
        return
    
    config = load_config()
    config = set_env_value(config, "ANTHROPIC_BASE_URL", url)
    if save_config(config):
        UI.print_success(f"Set ANTHROPIC_BASE_URL = {url}")
    UI.wait_for_key()


def menu_set_model() -> None:
    """Menu: Set Model"""
    UI.clear_screen()
    print(f"\n {Colors.BOLD}🤖 Set Model{Colors.END}")
    print(UI.draw_separator(width=50))
    print()
    print(f" {Colors.DIM}Model Variables:{Colors.END}")
    print()
    print(UI.format_menu_item("1", "ANTHROPIC_MODEL", "Default Model"))
    print(UI.format_menu_item("2", "ANTHROPIC_DEFAULT_SONNET_MODEL", "Sonnet Tier"))
    print(UI.format_menu_item("3", "ANTHROPIC_DEFAULT_OPUS_MODEL", "Opus Tier"))
    print(UI.format_menu_item("4", "ANTHROPIC_DEFAULT_HAIKU_MODEL", "Haiku Tier"))
    print(UI.format_menu_item("5", "Custom", "Enter env var name"))
    print()
    print(UI.format_menu_item("0", "Back"))
    print()

    choice = UI.prompt("Select model variable", "0")

    if choice == "0":
        return

    model_vars = {
        "1": "ANTHROPIC_MODEL",
        "2": "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "3": "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "4": "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    }

    if choice == "5":
        var_name = UI.prompt("Variable name (e.g. ANTHROPIC_MODEL)")
        if not var_name:
            UI.print_warning("Variable name cannot be empty")
            UI.wait_for_key()
            return

        var_name = var_name.upper()
        if not (var_name[0].isalpha() or var_name[0] == "_") or not all(
            ch.isalnum() or ch == "_" for ch in var_name
        ):
            UI.print_error("Invalid variable name (use letters/numbers/underscore, start with a letter/_).")
            UI.wait_for_key()
            return
    elif choice in model_vars:
        var_name = model_vars[choice]
    else:
        UI.print_error("Invalid selection")
        UI.wait_for_key()
        return

    model = UI.prompt("Enter model name")
    if not model:
        UI.print_warning("Model name cannot be empty")
        UI.wait_for_key()
        return

    config = load_config()
    config = set_env_value(config, var_name, model)
    if save_config(config):
        UI.print_success(f"Set {var_name} = {model}")
    UI.wait_for_key()


def menu_reset_config() -> None:
    """Menu: Reset Configuration"""
    print()
    print(f" {Colors.WARNING}⚠ Warning: This will delete all configuration!{Colors.END}")
    
    if UI.confirm("Are you sure you want to reset all configurations?", default=False):
        if save_config({}):
            UI.print_success("Configuration reset to empty")
    else:
        UI.print_info("Reset cancelled")
    
    UI.wait_for_key()


# ========================
#       CLI Argument Handler
# ========================
def create_parser() -> argparse.ArgumentParser:
    """Create Command Line Argument Parser"""
    parser = argparse.ArgumentParser(
        description="Claude Code Configuration Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Colors.BOLD}Examples:{Colors.END}
  %(prog)s                              # Start interactive menu
  %(prog)s --preset openrouter --key sk-xxx  # Use OpenRouter preset
  %(prog)s --preset deepseek --key sk-xxx    # Use DeepSeek preset
  %(prog)s --baseurl https://api.example.com --key sk-xxx
  %(prog)s --set ANTHROPIC_MODEL=gpt-4       # Set environment variable
  %(prog)s --delete ANTHROPIC_MODEL          # Delete environment variable
  %(prog)s --list                            # List current config
  %(prog)s --reset                           # Reset config
        """
    )
    
    parser.add_argument(
        "--preset", "-p",
        choices=list(PRESETS.keys()),
        help="Use preset configuration (openrouter/deepseek/zhipu/anthropic)"
    )
    
    parser.add_argument(
        "--baseurl", "-b",
        metavar="URL",
        help="Set ANTHROPIC_BASE_URL"
    )
    
    parser.add_argument(
        "--key", "-k",
        metavar="KEY",
        help="Set API Key (ANTHROPIC_AUTH_TOKEN)"
    )
    
    parser.add_argument(
        "--model", "-m",
        metavar="MODEL",
        help="Set default model (ANTHROPIC_MODEL)"
    )
    
    parser.add_argument(
        "--sonnet-model",
        metavar="MODEL",
        help="Set Sonnet tier model"
    )
    
    parser.add_argument(
        "--opus-model",
        metavar="MODEL",
        help="Set Opus tier model"
    )
    
    parser.add_argument(
        "--haiku-model",
        metavar="MODEL",
        help="Set Haiku tier model"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        metavar="MS",
        help="Set API timeout (milliseconds)"
    )
    
    parser.add_argument(
        "--set", "-s",
        action="append",
        metavar="KEY=VALUE",
        help="Set environment variable (can be used multiple times)"
    )
    
    parser.add_argument(
        "--delete", "-d",
        action="append",
        metavar="KEY",
        help="Delete environment variable (can be used multiple times)"
    )
    
    parser.add_argument(
        "--get", "-g",
        metavar="KEY",
        help="Get value of environment variable"
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all current configurations"
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all configurations"
    )
    
    parser.add_argument(
        "--onboarding",
        action="store_true",
        help="Complete onboarding configuration"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Force interactive mode"
    )
    
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )
    
    return parser


def disable_colors() -> None:
    """Disable all colors"""
    for attr in dir(Colors):
        if not attr.startswith('_'):
            setattr(Colors, attr, '')


def run_cli(args: argparse.Namespace) -> int:
    """Run CLI Mode"""
    if args.no_color:
        disable_colors()
    
    config = load_config()
    modified = False
    
    # Reset Config
    if args.reset:
        if save_config({}):
            UI.print_success("Configuration reset")
            return 0
        return 1
    
    # Get Single Value
    if args.get:
        value = get_env_value(config, args.get)
        if value:
            if args.json:
                print(json.dumps({args.get: value}))
            else:
                print(value)
            return 0
        else:
            UI.print_error(f"Environment variable not found: {args.get}")
            return 1
    
    # List Config
    if args.list:
        if args.json:
            print(json.dumps(config, indent=2, ensure_ascii=False))
        else:
            display_config(config)
        return 0
    
    # Apply Preset
    if args.preset:
        config = apply_preset(config, args.preset, args.key)
        modified = True
    elif args.key:
        config = set_env_value(config, "ANTHROPIC_AUTH_TOKEN", args.key)
        modified = True
    
    # Set Base URL
    if args.baseurl:
        config = set_env_value(config, "ANTHROPIC_BASE_URL", args.baseurl)
        modified = True
    
    # Set Models
    if args.model:
        config = set_env_value(config, "ANTHROPIC_MODEL", args.model)
        modified = True
    
    if args.sonnet_model:
        config = set_env_value(config, "ANTHROPIC_DEFAULT_SONNET_MODEL", args.sonnet_model)
        modified = True
    
    if args.opus_model:
        config = set_env_value(config, "ANTHROPIC_DEFAULT_OPUS_MODEL", args.opus_model)
        modified = True
    
    if args.haiku_model:
        config = set_env_value(config, "ANTHROPIC_DEFAULT_HAIKU_MODEL", args.haiku_model)
        modified = True
    
    # Set Timeout
    if args.timeout:
        config = set_env_value(config, "API_TIMEOUT_MS", str(args.timeout))
        modified = True
    
    # Set Custom Environment Variables
    if args.set:
        for item in args.set:
            if "=" in item:
                key, value = item.split("=", 1)
                config = set_env_value(config, key.strip(), value.strip())
                modified = True
            else:
                UI.print_error(f"Invalid format: {item} (Should be KEY=VALUE)")
    
    # Delete Environment Variables
    if args.delete:
        for key in args.delete:
            config = delete_env_value(config, key)
            modified = True
            UI.print_info(f"Deleted {key}")
    
    # Complete Onboarding
    if args.onboarding:
        complete_onboarding()
    
    # Save Config
    if modified:
        if save_config(config):
            UI.print_success("Configuration saved!")
            if args.json:
                print(json.dumps(config, indent=2, ensure_ascii=False))
            else:
                display_config(config)
            return 0
        return 1
    
    return 0


# ========================
#       Main Function
# ========================
def main() -> int:
    """Main Function"""
    parser = create_parser()
    args = parser.parse_args()
    
    if args.no_color:
        disable_colors()
    
    # If no arguments or forced interactive mode, enter interactive menu
    if args.interactive or (
        not any([
            args.preset, args.baseurl, args.key, args.model,
            args.sonnet_model, args.opus_model, args.haiku_model,
            args.timeout, args.set, args.delete, args.get,
            args.list, args.reset, args.onboarding
        ])
    ):
        try:
            interactive_menu()
            return 0
        except KeyboardInterrupt:
            UI.clear_screen()
            print(f"\n {Colors.INFO}Cancelled{Colors.END}\n")
            return 0
    else:
        return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
