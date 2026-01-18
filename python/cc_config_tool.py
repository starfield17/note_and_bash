#!/usr/bin/env python3
"""
Claude Code Configuration Manager
Used to configure the ~/.claude/settings.json file for Claude Code.
Supports both interactive menu and command-line argument modes.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

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
        "description": "OpenRouter - Supports various models (GPT/Gemini/Claude, etc.)",
        "env": {
            "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        },
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/anthropic",
        "description": "DeepSeek - High cost-performance models",
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
        "description": "Zhipu AI - GLM series models",
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
#       Helper Functions
# ========================
class Colors:
    """Terminal Colors"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_info(msg: str) -> None:
    print(f"{Colors.BLUE}🔹 {msg}{Colors.END}")


def print_success(msg: str) -> None:
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")


def print_error(msg: str) -> None:
    print(f"{Colors.RED}❌ {msg}{Colors.END}", file=sys.stderr)


def print_warning(msg: str) -> None:
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")


def print_header(msg: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*50}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {msg}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*50}{Colors.END}\n")


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
            print_warning(f"Config file format error, creating new configuration.")
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
        print_error(f"Failed to save config: {e}")
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
        print_error(f"Failed to save ~/.claude.json: {e}")
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


def list_env_vars(config: dict) -> None:
    """List all environment variables"""
    env = config.get("env", {})
    if not env:
        print_warning("No environment variables configured.")
        return
    
    print_header("Current Environment Configuration")
    for key, value in env.items():
        desc = ENV_VARS_INFO.get(key, "")
        # Mask sensitive information
        display_value = value
        if "TOKEN" in key or "KEY" in key:
            if len(value) > 10:
                display_value = value[:6] + "..." + value[-4:]
        print(f"  {Colors.CYAN}{key}{Colors.END}")
        if desc:
            print(f"    Description: {desc}")
        print(f"    Value: {Colors.GREEN}{display_value}{Colors.END}")
        print()


def apply_preset(config: dict, preset_name: str, api_key: Optional[str] = None) -> dict:
    """Apply preset configuration"""
    if preset_name not in PRESETS:
        print_error(f"Unknown preset: {preset_name}")
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
    
    print_success(f"Preset applied: {preset['name']}")
    return config


def complete_onboarding() -> None:
    """Complete Claude Code onboarding"""
    claude_json = load_claude_json()
    claude_json["hasCompletedOnboarding"] = True
    if save_claude_json(claude_json):
        print_success("Onboarding configuration completed.")


# ========================
#       Interactive Menu
# ========================
def interactive_menu() -> None:
    """Interactive Configuration Menu"""
    while True:
        print_header("Claude Code Configuration Manager")
        print(f"  Config File: {CONFIG_FILE}")
        print()
        print("  1. View Current Config")
        print("  2. Use Preset Config (Recommended)")
        print("  3. Set Environment Variable")
        print("  4. Delete Environment Variable")
        print("  5. Set API Key")
        print("  6. Set Base URL")
        print("  7. Set Model")
        print("  8. Complete Onboarding")
        print("  9. Reset Configuration")
        print("  0. Exit")
        print()
        
        choice = input(f"{Colors.CYAN}Please select an option [0-9]: {Colors.END}").strip()
        
        if choice == "0":
            print_success("Goodbye!")
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
        elif choice == "9":
            menu_reset_config()
        else:
            print_error("Invalid selection, please try again.")


def menu_view_config() -> None:
    """Menu: View Configuration"""
    config = load_config()
    list_env_vars(config)
    input("\nPress Enter to continue...")


def menu_apply_preset() -> None:
    """Menu: Apply Preset Configuration"""
    print_header("Select Preset Configuration")
    
    presets_list = list(PRESETS.items())
    for i, (key, preset) in enumerate(presets_list, 1):
        print(f"  {i}. {preset['name']}")
        print(f"     {Colors.CYAN}{preset['description']}{Colors.END}")
        print(f"     URL: {preset['base_url']}")
        print()
    
    print("  0. Back")
    print()
    
    choice = input(f"{Colors.CYAN}Please select a preset [0-{len(presets_list)}]: {Colors.END}").strip()
    
    if choice == "0":
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(presets_list):
            preset_key = presets_list[idx][0]
            
            # Ask for API Key
            api_key = input(f"\n{Colors.CYAN}Enter API Key (Leave blank to skip): {Colors.END}").strip()
            
            config = load_config()
            config = apply_preset(config, preset_key, api_key if api_key else None)
            
            if save_config(config):
                print_success("Configuration saved!")
            
            # Ask to complete onboarding
            complete = input(f"\n{Colors.CYAN}Complete Onboarding as well? [Y/n]: {Colors.END}").strip().lower()
            if complete != "n":
                complete_onboarding()
        else:
            print_error("Invalid selection")
    except ValueError:
        print_error("Please enter a valid number")


def menu_set_env() -> None:
    """Menu: Set Environment Variable"""
    print_header("Set Environment Variable")
    print("Common Variables:")
    for key, desc in ENV_VARS_INFO.items():
        print(f"  {Colors.CYAN}{key}{Colors.END}: {desc}")
    print()
    
    key = input(f"{Colors.CYAN}Enter Variable Name: {Colors.END}").strip()
    if not key:
        return
    
    value = input(f"{Colors.CYAN}Enter Value: {Colors.END}").strip()
    if not value:
        print_warning("Value cannot be empty")
        return
    
    config = load_config()
    config = set_env_value(config, key, value)
    if save_config(config):
        print_success(f"Set {key}")


def menu_delete_env() -> None:
    """Menu: Delete Environment Variable"""
    config = load_config()
    env = config.get("env", {})
    
    if not env:
        print_warning("No environment variables configured.")
        return
    
    print_header("Delete Environment Variable")
    keys = list(env.keys())
    for i, key in enumerate(keys, 1):
        print(f"  {i}. {key}")
    print("  0. Back")
    print()
    
    choice = input(f"{Colors.CYAN}Select variable to delete [0-{len(keys)}]: {Colors.END}").strip()
    
    if choice == "0":
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(keys):
            key = keys[idx]
            confirm = input(f"{Colors.YELLOW}Are you sure you want to delete {key}? [y/N]: {Colors.END}").strip().lower()
            if confirm == "y":
                config = delete_env_value(config, key)
                if save_config(config):
                    print_success(f"Deleted {key}")
        else:
            print_error("Invalid selection")
    except ValueError:
        print_error("Please enter a valid number")


def menu_set_api_key() -> None:
    """Menu: Set API Key"""
    print_header("Set API Key")
    print("Authentication Method:")
    print("  1. ANTHROPIC_AUTH_TOKEN (Bearer Token, Recommended)")
    print("  2. ANTHROPIC_API_KEY (X-Api-Key)")
    print()
    
    choice = input(f"{Colors.CYAN}Select Auth Method [1/2]: {Colors.END}").strip()
    
    if choice == "1":
        key_name = "ANTHROPIC_AUTH_TOKEN"
    elif choice == "2":
        key_name = "ANTHROPIC_API_KEY"
    else:
        print_error("Invalid selection")
        return
    
    api_key = input(f"{Colors.CYAN}Enter API Key: {Colors.END}").strip()
    if not api_key:
        print_warning("API Key cannot be empty")
        return
    
    config = load_config()
    config = set_env_value(config, key_name, api_key)
    if save_config(config):
        print_success(f"Set {key_name}")


def menu_set_base_url() -> None:
    """Menu: Set Base URL"""
    print_header("Set Base URL")
    print("Common URLs:")
    for key, preset in PRESETS.items():
        print(f"  {Colors.CYAN}{preset['name']}{Colors.END}: {preset['base_url']}")
    print()
    
    url = input(f"{Colors.CYAN}Enter Base URL: {Colors.END}").strip()
    if not url:
        print_warning("URL cannot be empty")
        return
    
    config = load_config()
    config = set_env_value(config, "ANTHROPIC_BASE_URL", url)
    if save_config(config):
        print_success(f"Set ANTHROPIC_BASE_URL = {url}")


def menu_set_model() -> None:
    """Menu: Set Model"""
    print_header("Set Model")
    print("Model Variables:")
    print("  1. ANTHROPIC_MODEL (Default Model)")
    print("  2. ANTHROPIC_DEFAULT_SONNET_MODEL (Sonnet Tier)")
    print("  3. ANTHROPIC_DEFAULT_OPUS_MODEL (Opus Tier)")
    print("  4. ANTHROPIC_DEFAULT_HAIKU_MODEL (Haiku Tier)")
    print()
    
    choice = input(f"{Colors.CYAN}Please select [1-4]: {Colors.END}").strip()
    
    model_vars = {
        "1": "ANTHROPIC_MODEL",
        "2": "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "3": "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "4": "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    }
    
    if choice not in model_vars:
        print_error("Invalid selection")
        return
    
    var_name = model_vars[choice]
    model = input(f"{Colors.CYAN}Enter Model Name: {Colors.END}").strip()
    if not model:
        print_warning("Model name cannot be empty")
        return
    
    config = load_config()
    config = set_env_value(config, var_name, model)
    if save_config(config):
        print_success(f"Set {var_name} = {model}")


def menu_reset_config() -> None:
    """Menu: Reset Configuration"""
    confirm = input(f"{Colors.YELLOW}Are you sure you want to reset all configurations? [y/N]: {Colors.END}").strip().lower()
    if confirm == "y":
        if save_config({}):
            print_success("Configuration reset")


# ========================
#       CLI Argument Handler
# ========================
def create_parser() -> argparse.ArgumentParser:
    """Create Command Line Argument Parser"""
    parser = argparse.ArgumentParser(
        description="Claude Code Configuration Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
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
    
    return parser


def run_cli(args: argparse.Namespace) -> int:
    """Run CLI Mode"""
    config = load_config()
    modified = False
    
    # Reset Config
    if args.reset:
        if save_config({}):
            print_success("Configuration reset")
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
            print_error(f"Environment variable not found: {args.get}")
            return 1
    
    # List Config
    if args.list:
        if args.json:
            print(json.dumps(config, indent=2, ensure_ascii=False))
        else:
            list_env_vars(config)
        return 0
    
    # Apply Preset
    if args.preset:
        config = apply_preset(config, args.preset, args.key)
        modified = True
    elif args.key:
        # Set key individually
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
                print_error(f"Invalid format: {item} (Should be KEY=VALUE)")
    
    # Delete Environment Variables
    if args.delete:
        for key in args.delete:
            config = delete_env_value(config, key)
            modified = True
            print_info(f"Deleted {key}")
    
    # Complete Onboarding
    if args.onboarding:
        complete_onboarding()
    
    # Save Config
    if modified:
        if save_config(config):
            print_success("Configuration saved!")
            if args.json:
                print(json.dumps(config, indent=2, ensure_ascii=False))
            else:
                list_env_vars(config)
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
            print("\n")
            print_info("Cancelled")
            return 0
    else:
        return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
