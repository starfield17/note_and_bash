#!/usr/bin/env python3
"""
OpenCode Configuration Management Tool
For managing provider and model configurations in opencode.json/opencode.jsonc

Supports:
- Interactive mode (default)
- Command line argument mode
- CRUD operations for providers and models
- Global config (~/.config/opencode/opencode.json) or project config (./opencode.json)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# JSONC Parser (supports JSON with comments)
# ═══════════════════════════════════════════════════════════════════════════════

def strip_jsonc_comments(text: str) -> str:
    """Remove comments from JSONC, keeping valid JSON (including // and /* in strings)"""
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(text):
        char = text[i]

        # Handle inside string
        if in_string:
            result.append(char)
            if escape_next:
                escape_next = False
            elif char == '\\':
                escape_next = True
            elif char == '"':
                in_string = False
            i += 1
            continue

        # Detect string start
        if char == '"':
            in_string = True
            result.append(char)
            i += 1
            continue

        # Detect single line comment //
        if char == '/' and i + 1 < len(text) and text[i + 1] == '/':
            # Skip until end of line
            while i < len(text) and text[i] != '\n':
                i += 1
            continue

        # Detect multi-line comment /* */
        if char == '/' and i + 1 < len(text) and text[i + 1] == '*':
            i += 2
            while i + 1 < len(text) and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2  # Skip */
            continue

        result.append(char)
        i += 1

    # Remove trailing commas (JSON doesn't allow, but JSONC does)
    text = ''.join(result)
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    return text


def load_jsonc(filepath: Path) -> dict:
    """Load JSONC file"""
    if not filepath.exists():
        return {}
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    stripped = strip_jsonc_comments(content)
    try:
        return json.loads(stripped) if stripped.strip() else {}
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON parsing error: {e}")
        return {}


def save_json(filepath: Path, data: dict) -> bool:
    """Save JSON file (with formatting)"""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
        return True
    except Exception as e:
        print(f"❌ Save failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration File Paths
# ═══════════════════════════════════════════════════════════════════════════════

def get_global_config_path() -> Path:
    """Get global configuration path"""
    xdg_config = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    return Path(xdg_config) / 'opencode' / 'opencode.json'


def get_project_config_path() -> Path:
    """Get project configuration path (prefer .jsonc)"""
    jsonc_path = Path.cwd() / 'opencode.jsonc'
    json_path = Path.cwd() / 'opencode.json'
    if jsonc_path.exists():
        return jsonc_path
    return json_path


def get_config_path(scope: str) -> Path:
    """Get configuration path based on scope"""
    if scope == 'global':
        return get_global_config_path()
    return get_project_config_path()


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Operations Core
# ═══════════════════════════════════════════════════════════════════════════════

class OpenCodeConfig:
    """OpenCode Configuration Manager"""

    SCHEMA_URL = "https://opencode.ai/config.json"
    DEFAULT_NPM = "@ai-sdk/openai-compatible"

    def __init__(self, scope: str = 'project'):
        self.scope = scope
        self.path = get_config_path(scope)
        self.data = load_jsonc(self.path)

    def ensure_schema(self):
        """Ensure config has $schema"""
        if '$schema' not in self.data:
            self.data['$schema'] = self.SCHEMA_URL

    def ensure_provider_section(self):
        """Ensure provider field exists"""
        if 'provider' not in self.data:
            self.data['provider'] = {}

    def save(self) -> bool:
        """Save configuration"""
        self.ensure_schema()
        return save_json(self.path, self.data)

    # ─────────────────────────────────────────────────────────────────────────
    # Provider Operations
    # ─────────────────────────────────────────────────────────────────────────

    def list_providers(self) -> dict:
        """List all providers"""
        return self.data.get('provider', {})

    def get_provider(self, provider_id: str) -> Optional[dict]:
        """Get specified provider"""
        return self.data.get('provider', {}).get(provider_id)

    def add_provider(self, provider_id: str, name: str = None,
                     npm: str = None, base_url: str = None,
                     headers: dict = None) -> bool:
        """Add new provider"""
        self.ensure_provider_section()

        if provider_id in self.data['provider']:
            print(f"⚠️  Provider '{provider_id}' already exists, use update command to modify")
            return False

        provider_config = {
            'npm': npm or self.DEFAULT_NPM,
            'name': name or provider_id.title(),
            'options': {},
            'models': {}
        }

        if base_url:
            provider_config['options']['baseURL'] = base_url
        if headers:
            provider_config['options']['headers'] = headers

        self.data['provider'][provider_id] = provider_config
        return self.save()

    def update_provider(self, provider_id: str, name: str = None,
                        npm: str = None, base_url: str = None,
                        headers: dict = None) -> bool:
        """Update provider"""
        if provider_id not in self.data.get('provider', {}):
            print(f"❌ Provider '{provider_id}' does not exist")
            return False

        provider = self.data['provider'][provider_id]
        if name:
            provider['name'] = name
        if npm:
            provider['npm'] = npm
        if base_url:
            provider.setdefault('options', {})['baseURL'] = base_url
        if headers:
            provider.setdefault('options', {})['headers'] = headers

        return self.save()

    def delete_provider(self, provider_id: str) -> bool:
        """Delete provider"""
        if provider_id not in self.data.get('provider', {}):
            print(f"❌ Provider '{provider_id}' does not exist")
            return False

        del self.data['provider'][provider_id]
        return self.save()

    # ─────────────────────────────────────────────────────────────────────────
    # Model Operations
    # ─────────────────────────────────────────────────────────────────────────

    def list_models(self, provider_id: str) -> dict:
        """List all models of specified provider"""
        provider = self.get_provider(provider_id)
        if not provider:
            return {}
        return provider.get('models', {})

    def get_model(self, provider_id: str, model_id: str) -> Optional[dict]:
        """Get specified model"""
        models = self.list_models(provider_id)
        return models.get(model_id)

    def add_model(self, provider_id: str, model_id: str,
                  name: str = None, context_limit: int = None,
                  output_limit: int = None) -> bool:
        """Add new model"""
        if provider_id not in self.data.get('provider', {}):
            print(f"❌ Provider '{provider_id}' does not exist, please add provider first")
            return False

        provider = self.data['provider'][provider_id]
        if 'models' not in provider:
            provider['models'] = {}

        if model_id in provider['models']:
            print(f"⚠️  Model '{model_id}' already exists in '{provider_id}'")
            return False

        model_config = {}
        if name:
            model_config['name'] = name
        if context_limit:
            model_config.setdefault('limit', {})['context'] = context_limit
        if output_limit:
            model_config.setdefault('limit', {})['output'] = output_limit

        provider['models'][model_id] = model_config
        return self.save()

    def update_model(self, provider_id: str, model_id: str,
                     name: str = None, context_limit: int = None,
                     output_limit: int = None) -> bool:
        """Update model"""
        if provider_id not in self.data.get('provider', {}):
            print(f"❌ Provider '{provider_id}' does not exist")
            return False

        provider = self.data['provider'][provider_id]
        if model_id not in provider.get('models', {}):
            print(f"❌ Model '{model_id}' does not exist in '{provider_id}'")
            return False

        model = provider['models'][model_id]
        if name:
            model['name'] = name
        if context_limit:
            model.setdefault('limit', {})['context'] = context_limit
        if output_limit:
            model.setdefault('limit', {})['output'] = output_limit

        return self.save()

    def delete_model(self, provider_id: str, model_id: str) -> bool:
        """Delete model"""
        if provider_id not in self.data.get('provider', {}):
            print(f"❌ Provider '{provider_id}' does not exist")
            return False

        provider = self.data['provider'][provider_id]
        if model_id not in provider.get('models', {}):
            print(f"❌ Model '{model_id}' does not exist in '{provider_id}'")
            return False

        del provider['models'][model_id]
        return self.save()

    # ─────────────────────────────────────────────────────────────────────────
    # Default Model
    # ─────────────────────────────────────────────────────────────────────────

    def get_default_model(self) -> Optional[str]:
        """Get default model"""
        return self.data.get('model')

    def set_default_model(self, provider_id: str, model_id: str) -> bool:
        """Set default model"""
        self.data['model'] = f"{provider_id}/{model_id}"
        return self.save()

    def clear_default_model(self) -> bool:
        """Clear default model"""
        if 'model' in self.data:
            del self.data['model']
        return self.save()


# ═══════════════════════════════════════════════════════════════════════════════
# Display Formatting
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    """Terminal colors"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'


def color(text: str, *styles) -> str:
    """Apply color styles"""
    if not sys.stdout.isatty():
        return text
    return ''.join(styles) + text + Colors.RESET


def print_header(text: str):
    """Print header"""
    print(f"\n{color('═' * 60, Colors.DIM)}")
    print(f"  {color(text, Colors.BOLD, Colors.CYAN)}")
    print(f"{color('═' * 60, Colors.DIM)}\n")


def print_provider(provider_id: str, provider: dict, indent: int = 0):
    """Format print provider"""
    prefix = "  " * indent
    print(f"{prefix}{color('◆', Colors.GREEN)} {color(provider_id, Colors.BOLD, Colors.YELLOW)}")
    print(f"{prefix}  Name: {provider.get('name', '-')}")
    print(f"{prefix}  npm:  {color(provider.get('npm', '-'), Colors.DIM)}")

    options = provider.get('options', {})
    if 'baseURL' in options:
        print(f"{prefix}  URL:  {color(options['baseURL'], Colors.BLUE)}")

    models = provider.get('models', {})
    if models:
        print(f"{prefix}  Models ({len(models)}):")
        for model_id, model_config in models.items():
            model_name = model_config.get('name', model_id)
            limits = model_config.get('limit', {})
            limit_str = ""
            if limits:
                parts = []
                if 'context' in limits:
                    parts.append(f"ctx:{limits['context']}")
                if 'output' in limits:
                    parts.append(f"out:{limits['output']}")
                limit_str = f" ({', '.join(parts)})"
            print(f"{prefix}    • {color(model_id, Colors.MAGENTA)}: {model_name}{color(limit_str, Colors.DIM)}")
    print()


def print_config_summary(config: OpenCodeConfig):
    """Print configuration summary"""
    scope_text = "Global" if config.scope == 'global' else "Project"
    print(f"📁 Config location: {color(str(config.path), Colors.BLUE)} ({scope_text})")

    default_model = config.get_default_model()
    if default_model:
        print(f"🎯 Default model: {color(default_model, Colors.GREEN)}")

    providers = config.list_providers()
    print(f"📦 Provider count: {color(str(len(providers)), Colors.YELLOW)}")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# Interactive Menu
# ═══════════════════════════════════════════════════════════════════════════════

def prompt(text: str, default: str = None) -> str:
    """Interactive input prompt"""
    if default:
        text = f"{text} [{default}]"
    result = input(f"{color('?', Colors.CYAN)} {text}: ").strip()
    return result if result else (default or "")


def prompt_int(text: str, default: int = None) -> Optional[int]:
    """Interactive integer input"""
    default_str = str(default) if default else ""
    result = prompt(text, default_str)
    if not result:
        return None
    try:
        return int(result)
    except ValueError:
        print(f"⚠️  Invalid number, skipping")
        return None


def prompt_confirm(text: str, default: bool = False) -> bool:
    """Confirmation prompt"""
    suffix = "[Y/n]" if default else "[y/N]"
    result = input(f"{color('?', Colors.YELLOW)} {text} {suffix}: ").strip().lower()
    if not result:
        return default
    return result in ('y', 'yes')


def prompt_choice(text: str, choices: list, default: int = 0) -> int:
    """Selection menu"""
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


def interactive_add_provider(config: OpenCodeConfig):
    """Interactive add provider"""
    print_header("Add New Provider")

    provider_id = prompt("Provider ID (e.g., myprovider)")
    if not provider_id:
        print("❌ ID cannot be empty")
        return

    name = prompt("Display name", provider_id.title())
    npm = prompt("npm package name", config.DEFAULT_NPM)
    base_url = prompt("API Base URL (e.g., https://api.example.com/v1)")

    if config.add_provider(provider_id, name=name, npm=npm, base_url=base_url):
        print(f"\n✅ Provider '{provider_id}' added successfully!")
        print(f"💡 Tip: Remember to run /connect in opencode to configure API Key")


def interactive_add_model(config: OpenCodeConfig):
    """Interactive add model"""
    print_header("Add New Model")

    providers = config.list_providers()
    if not providers:
        print("❌ No available provider, please add provider first")
        return

    provider_ids = list(providers.keys())
    idx = prompt_choice("Select Provider:", provider_ids)
    provider_id = provider_ids[idx]

    model_id = prompt("Model ID (e.g., gpt-4o)")
    if not model_id:
        print("❌ Model ID cannot be empty")
        return

    name = prompt("Display name", model_id)
    context_limit = prompt_int("Context limit (tokens, leave empty to skip)")
    output_limit = prompt_int("Output limit (tokens, leave empty to skip)")

    if config.add_model(provider_id, model_id, name=name,
                        context_limit=context_limit, output_limit=output_limit):
        print(f"\n✅ Model '{model_id}' added to '{provider_id}' successfully!")


def interactive_delete_provider(config: OpenCodeConfig):
    """Interactive delete provider"""
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


def interactive_delete_model(config: OpenCodeConfig):
    """Interactive delete model"""
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


def interactive_set_default(config: OpenCodeConfig):
    """Interactive set default model"""
    print_header("Set Default Model")

    providers = config.list_providers()
    if not providers:
        print("❌ No available provider")
        return

    # Collect all models
    all_models = []
    for provider_id, provider in providers.items():
        for model_id in provider.get('models', {}).keys():
            all_models.append(f"{provider_id}/{model_id}")

    if not all_models:
        print("❌ No available models")
        return

    all_models.insert(0, "(Clear default model)")
    idx = prompt_choice("Select default model:", all_models)

    if idx == 0:
        if config.clear_default_model():
            print("\n✅ Default model cleared")
    else:
        parts = all_models[idx].split('/')
        if config.set_default_model(parts[0], parts[1]):
            print(f"\n✅ Default model set to '{all_models[idx]}'")


def interactive_view_config(config: OpenCodeConfig):
    """View current configuration"""
    print_header("Current Configuration")
    print_config_summary(config)

    providers = config.list_providers()
    if providers:
        print(f"{color('Providers:', Colors.BOLD)}\n")
        for provider_id, provider in providers.items():
            print_provider(provider_id, provider)
    else:
        print(f"{color('(No provider configured)', Colors.DIM)}\n")


def interactive_export_config(config: OpenCodeConfig):
    """Export configuration as JSON"""
    print_header("Export Configuration")
    print(json.dumps(config.data, indent=2, ensure_ascii=False))


def interactive_menu(scope: str):
    """Main interactive menu"""
    config = OpenCodeConfig(scope)

    while True:
        print_header(f"OpenCode Configuration Management ({'Global' if scope == 'global' else 'Project'})")
        print_config_summary(config)

        choices = [
            "📋 View Config",
            "➕ Add Provider",
            "➕ Add Model",
            "✏️  Modify Provider",
            "✏️  Modify Model",
            "🗑️  Delete Provider",
            "🗑️  Delete Model",
            "🎯 Set Default Model",
            "📤 Export JSON",
            "🔄 Switch Config Scope",
            "❌ Exit"
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
            interactive_set_default(config)
        elif idx == 8:
            interactive_export_config(config)
        elif idx == 9:
            scope = 'global' if scope == 'project' else 'project'
            config = OpenCodeConfig(scope)
            print(f"\n✅ Switched to {'Global' if scope == 'global' else 'Project'} configuration")
        else:
            print("\n👋 Goodbye!")
            break

        input(f"\n{color('Press Enter to continue...', Colors.DIM)}")


def interactive_update_provider(config: OpenCodeConfig):
    """Interactive modify provider"""
    print_header("Modify Provider")

    providers = config.list_providers()
    if not providers:
        print("❌ No provider to modify")
        return

    provider_ids = list(providers.keys())
    idx = prompt_choice("Select Provider to modify:", provider_ids)
    provider_id = provider_ids[idx]
    provider = providers[provider_id]

    print(f"\nCurrent configuration:")
    print_provider(provider_id, provider)

    name = prompt("New name (leave empty to keep unchanged)", provider.get('name', ''))
    npm = prompt("New npm package name (leave empty to keep unchanged)", provider.get('npm', ''))
    base_url = prompt("New Base URL (leave empty to keep unchanged)",
                      provider.get('options', {}).get('baseURL', ''))

    if config.update_provider(provider_id,
                              name=name if name != provider.get('name', '') else None,
                              npm=npm if npm != provider.get('npm', '') else None,
                              base_url=base_url if base_url != provider.get('options', {}).get('baseURL', '') else None):
        print(f"\n✅ Provider '{provider_id}' updated")


def interactive_update_model(config: OpenCodeConfig):
    """Interactive modify model"""
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

    print(f"\nCurrent configuration: {model_id} = {model}")

    name = prompt("New name (leave empty to keep unchanged)", model.get('name', ''))
    context_limit = prompt_int("New Context limit (leave empty to keep unchanged)",
                               model.get('limit', {}).get('context'))
    output_limit = prompt_int("New Output limit (leave empty to keep unchanged)",
                              model.get('limit', {}).get('output'))

    if config.update_model(provider_id, model_id,
                           name=name if name != model.get('name', '') else None,
                           context_limit=context_limit,
                           output_limit=output_limit):
        print(f"\n✅ Model '{model_id}' updated")


# ═══════════════════════════════════════════════════════════════════════════════
# Command Line Interface
# ═══════════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    """Build command line argument parser"""
    parser = argparse.ArgumentParser(
        prog='opencode-config',
        description='OpenCode Configuration Management Tool - Manage provider and model configurations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                         # Enter interactive mode
  %(prog)s -g                                      # Interactive mode (global config)
  %(prog)s list                                    # List all providers
  %(prog)s add-provider myapi --url https://api.example.com/v1
  %(prog)s add-model myapi gpt-4 --name "GPT-4" --context 128000
  %(prog)s set-default myapi gpt-4
  %(prog)s delete-model myapi gpt-4
  %(prog)s export                                  # Export config JSON
        """
    )

    # Global options
    parser.add_argument('-g', '--global', dest='scope', action='store_const',
                        const='global', default='project',
                        help='Use global config (~/.config/opencode/opencode.json)')
    parser.add_argument('-p', '--project', dest='scope', action='store_const',
                        const='project',
                        help='Use project config (./opencode.json, default)')
    parser.add_argument('--json', action='store_true',
                        help='Output in JSON format')

    subparsers = parser.add_subparsers(dest='command', title='commands')

    # list
    list_cmd = subparsers.add_parser('list', aliases=['ls'],
                                      help='List all providers and models')
    list_cmd.add_argument('provider_id', nargs='?',
                          help='Specify provider to list only its models')

    # add-provider
    add_provider = subparsers.add_parser('add-provider', aliases=['ap'],
                                          help='Add new provider')
    add_provider.add_argument('provider_id', help='Provider ID')
    add_provider.add_argument('--name', '-n', help='Display name')
    add_provider.add_argument('--npm', default='@ai-sdk/openai-compatible',
                               help='npm package name (default: @ai-sdk/openai-compatible)')
    add_provider.add_argument('--url', '-u', dest='base_url',
                               help='API Base URL')

    # update-provider
    update_provider = subparsers.add_parser('update-provider', aliases=['up'],
                                             help='Update provider')
    update_provider.add_argument('provider_id', help='Provider ID')
    update_provider.add_argument('--name', '-n', help='New name')
    update_provider.add_argument('--npm', help='New npm package name')
    update_provider.add_argument('--url', '-u', dest='base_url', help='New Base URL')

    # delete-provider
    delete_provider = subparsers.add_parser('delete-provider', aliases=['dp'],
                                             help='Delete provider')
    delete_provider.add_argument('provider_id', help='Provider ID')
    delete_provider.add_argument('-f', '--force', action='store_true',
                                  help='Skip confirmation')

    # add-model
    add_model = subparsers.add_parser('add-model', aliases=['am'],
                                       help='Add new model')
    add_model.add_argument('provider_id', help='Provider ID')
    add_model.add_argument('model_id', help='Model ID')
    add_model.add_argument('--name', '-n', help='Display name')
    add_model.add_argument('--context', '-c', type=int, dest='context_limit',
                            help='Context token limit')
    add_model.add_argument('--output', '-o', type=int, dest='output_limit',
                            help='Output token limit')

    # update-model
    update_model = subparsers.add_parser('update-model', aliases=['um'],
                                          help='Update model')
    update_model.add_argument('provider_id', help='Provider ID')
    update_model.add_argument('model_id', help='Model ID')
    update_model.add_argument('--name', '-n', help='New name')
    update_model.add_argument('--context', '-c', type=int, dest='context_limit',
                               help='New Context limit')
    update_model.add_argument('--output', '-o', type=int, dest='output_limit',
                               help='New Output limit')

    # delete-model
    delete_model = subparsers.add_parser('delete-model', aliases=['dm'],
                                          help='Delete model')
    delete_model.add_argument('provider_id', help='Provider ID')
    delete_model.add_argument('model_id', help='Model ID')
    delete_model.add_argument('-f', '--force', action='store_true',
                              help='Skip confirmation')

    # set-default
    set_default = subparsers.add_parser('set-default', aliases=['sd'],
                                         help='Set default model')
    set_default.add_argument('provider_id', help='Provider ID')
    set_default.add_argument('model_id', help='Model ID')

    # clear-default
    subparsers.add_parser('clear-default', aliases=['cd'],
                          help='Clear default model')

    # export
    subparsers.add_parser('export', help='Export config JSON')

    # show
    show_cmd = subparsers.add_parser('show', help='Show config details')
    show_cmd.add_argument('provider_id', nargs='?', help='Specify provider')

    return parser


def cli_list(config: OpenCodeConfig, args):
    """CLI: List configuration"""
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
    """Main entry point"""
    parser = build_parser()
    args = parser.parse_args()

    # Enter interactive mode when no arguments provided
    if not args.command:
        interactive_menu(args.scope)
        return

    config = OpenCodeConfig(args.scope)

    if args.command in ('list', 'ls'):
        cli_list(config, args)

    elif args.command in ('add-provider', 'ap'):
        if config.add_provider(args.provider_id, name=args.name,
                               npm=args.npm, base_url=args.base_url):
            print(f"✅ Provider '{args.provider_id}' added successfully")

    elif args.command in ('update-provider', 'up'):
        if config.update_provider(args.provider_id, name=args.name,
                                  npm=args.npm, base_url=args.base_url):
            print(f"✅ Provider '{args.provider_id}' updated successfully")

    elif args.command in ('delete-provider', 'dp'):
        if not args.force:
            if not prompt_confirm(f"Are you sure you want to delete '{args.provider_id}'?"):
                print("Cancelled")
                return
        if config.delete_provider(args.provider_id):
            print(f"✅ Provider '{args.provider_id}' deleted")

    elif args.command in ('add-model', 'am'):
        if config.add_model(args.provider_id, args.model_id, name=args.name,
                            context_limit=args.context_limit,
                            output_limit=args.output_limit):
            print(f"✅ Model '{args.model_id}' added successfully")

    elif args.command in ('update-model', 'um'):
        if config.update_model(args.provider_id, args.model_id, name=args.name,
                               context_limit=args.context_limit,
                               output_limit=args.output_limit):
            print(f"✅ Model '{args.model_id}' updated successfully")

    elif args.command in ('delete-model', 'dm'):
        if not args.force:
            if not prompt_confirm(f"Are you sure you want to delete '{args.provider_id}/{args.model_id}'?"):
                print("Cancelled")
                return
        if config.delete_model(args.provider_id, args.model_id):
            print(f"✅ Model '{args.model_id}' deleted")

    elif args.command in ('set-default', 'sd'):
        if config.set_default_model(args.provider_id, args.model_id):
            print(f"✅ Default model set to '{args.provider_id}/{args.model_id}'")

    elif args.command in ('clear-default', 'cd'):
        if config.clear_default_model():
            print("✅ Default model cleared")

    elif args.command == 'export':
        print(json.dumps(config.data, indent=2, ensure_ascii=False))

    elif args.command == 'show':
        if args.provider_id:
            provider = config.get_provider(args.provider_id)
            if provider:
                if args.json:
                    print(json.dumps(provider, indent=2, ensure_ascii=False))
                else:
                    print_provider(args.provider_id, provider)
            else:
                print(f"Provider '{args.provider_id}' does not exist")
        else:
            interactive_view_config(config)


if __name__ == '__main__':
    main()
