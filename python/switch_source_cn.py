#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python Package Source Switcher (Cross-Platform)
===============================================
Supports: pip, conda
Platforms: Linux, Windows, macOS
Mirrors: Tsinghua, USTC, Aliyun, Tencent, Douban

Only uses Python standard library.
"""

import os
import sys
import platform
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple

# ==============================================================================
# Constants & Configuration
# ==============================================================================

# ANSI Colors (disabled on Windows CMD without ANSI support)
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

    @classmethod
    def disable(cls):
        """Disable colors for terminals that don't support ANSI."""
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.CYAN = cls.NC = ''


# Mirror Sources
PIP_MIRRORS: Dict[str, Tuple[str, str]] = {
    '1': ('https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple', 'Tsinghua (清华)'),
    '2': ('https://mirrors.ustc.edu.cn/pypi/simple', 'USTC (中科大)'),
    '3': ('https://mirrors.aliyun.com/pypi/simple/', 'Aliyun (阿里云)'),
    '4': ('https://mirrors.cloud.tencent.com/pypi/simple', 'Tencent (腾讯)'),
    '5': ('https://pypi.douban.com/simple', 'Douban (豆瓣)'),
}

CONDA_CONFIGS: Dict[str, Dict] = {
    'tsinghua': {
        'name': 'Tsinghua (清华)',
        'content': '''channels:
  - defaults
show_channel_urls: true
default_channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2
custom_channels:
  conda-forge: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  msys2: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  bioconda: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  menpo: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  pytorch: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  pytorch-lts: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  simpleitk: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
'''
    },
    'ustc': {
        'name': 'USTC (中科大)',
        'content': '''channels:
  - defaults
show_channel_urls: true
default_channels:
  - https://mirrors.ustc.edu.cn/anaconda/pkgs/main
  - https://mirrors.ustc.edu.cn/anaconda/pkgs/r
custom_channels:
  conda-forge: https://mirrors.ustc.edu.cn/anaconda/cloud
  bioconda: https://mirrors.ustc.edu.cn/anaconda/cloud
  msys2: https://mirrors.ustc.edu.cn/anaconda/cloud
  pytorch: https://mirrors.ustc.edu.cn/anaconda/cloud
'''
    }
}


# ==============================================================================
# Utility Functions
# ==============================================================================

def log_info(msg: str):
    print(f"{Colors.GREEN}[INFO]{Colors.NC} {msg}")

def log_warn(msg: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {msg}")

def log_error(msg: str):
    print(f"{Colors.RED}[ERR]{Colors.NC}  {msg}")

def log_title(msg: str):
    print(f"{Colors.CYAN}{msg}{Colors.NC}")


def get_system_info() -> Tuple[str, str]:
    """Get OS type and home directory."""
    system = platform.system().lower()
    home = Path.home()
    return system, str(home)


def check_command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    return shutil.which(cmd) is not None


def run_command(cmd: list, capture: bool = True) -> Tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            shell=(platform.system().lower() == 'windows')
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, '', str(e)


def backup_file(filepath: Path) -> bool:
    """Backup a file with timestamp."""
    if filepath.exists():
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = filepath.with_suffix(f'{filepath.suffix}.bak_{timestamp}')
        try:
            shutil.copy2(filepath, backup_path)
            log_info(f"已备份: {filepath} -> {backup_path.name}")
            return True
        except Exception as e:
            log_error(f"备份失败: {e}")
            return False
    return True


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if platform.system().lower() == 'windows' else 'clear')


def pause():
    """Pause and wait for user input."""
    input(f"\n{Colors.YELLOW}按 Enter 键继续...{Colors.NC}")


# ==============================================================================
# Path Configuration
# ==============================================================================

class PathConfig:
    """Platform-specific path configuration."""
    
    def __init__(self):
        self.system, self.home = get_system_info()
        self.home_path = Path(self.home)
        
    @property
    def pip_config_path(self) -> Path:
        """Get pip config file path based on OS."""
        if self.system == 'windows':
            return Path(os.environ.get('APPDATA', '')) / 'pip' / 'pip.ini'
        else:
            # Linux / macOS
            return self.home_path / '.config' / 'pip' / 'pip.conf'
    
    @property
    def conda_config_path(self) -> Path:
        """Get conda config file path (same for all OS)."""
        return self.home_path / '.condarc'
    
    def ensure_pip_config_dir(self):
        """Ensure pip config directory exists."""
        self.pip_config_path.parent.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# PIP Source Manager
# ==============================================================================

class PipSourceManager:
    """Manage pip package source configuration."""
    
    def __init__(self, path_config: PathConfig):
        self.config = path_config
        self.pip_available = check_command_exists('pip') or check_command_exists('pip3')
        
    def get_pip_cmd(self) -> str:
        """Get the correct pip command."""
        if check_command_exists('pip3'):
            return 'pip3'
        return 'pip'
    
    def set_source(self, url: str, name: str) -> bool:
        """Set pip source to specified mirror."""
        if not self.pip_available:
            log_error("pip 未安装或不在 PATH 中")
            return False
        
        log_info(f"正在设置 pip 源为: {name}")
        
        pip_cmd = self.get_pip_cmd()
        
        # Method 1: Use pip config command (preferred)
        ret, _, err = run_command([pip_cmd, 'config', 'set', 'global.index-url', url])
        
        if ret != 0:
            # Method 2: Write config file directly
            log_warn("pip config 命令失败，尝试直接写入配置文件...")
            return self._write_config_file(url)
        
        # Extract host for trusted-host
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        run_command([pip_cmd, 'config', 'set', 'global.trusted-host', host])
        
        log_info("pip 源设置成功!")
        return True
    
    def _write_config_file(self, url: str) -> bool:
        """Directly write pip config file."""
        try:
            self.config.ensure_pip_config_dir()
            backup_file(self.config.pip_config_path)
            
            from urllib.parse import urlparse
            host = urlparse(url).netloc
            
            content = f"""[global]
index-url = {url}
trusted-host = {host}
"""
            self.config.pip_config_path.write_text(content, encoding='utf-8')
            log_info(f"配置已写入: {self.config.pip_config_path}")
            return True
        except Exception as e:
            log_error(f"写入配置失败: {e}")
            return False
    
    def restore_default(self) -> bool:
        """Restore pip to default PyPI source."""
        if not self.pip_available:
            log_error("pip 未安装")
            return False
        
        log_info("正在恢复 pip 默认源...")
        
        pip_cmd = self.get_pip_cmd()
        run_command([pip_cmd, 'config', 'unset', 'global.index-url'])
        run_command([pip_cmd, 'config', 'unset', 'global.trusted-host'])
        
        # Also try to remove config file
        if self.config.pip_config_path.exists():
            backup_file(self.config.pip_config_path)
            try:
                self.config.pip_config_path.unlink()
            except:
                pass
        
        log_info("pip 已恢复为官方源 (PyPI)")
        return True
    
    def show_current_config(self):
        """Display current pip configuration."""
        if not self.pip_available:
            log_warn("pip 未安装")
            return
        
        print(f"\n{Colors.BLUE}当前 pip 配置:{Colors.NC}")
        print("-" * 40)
        
        pip_cmd = self.get_pip_cmd()
        ret, stdout, _ = run_command([pip_cmd, 'config', 'list'])
        
        if ret == 0 and stdout.strip():
            print(stdout)
        else:
            print("[使用默认 PyPI 源]")
        
        print("-" * 40)


# ==============================================================================
# Conda Source Manager
# ==============================================================================

class CondaSourceManager:
    """Manage conda package source configuration."""
    
    def __init__(self, path_config: PathConfig):
        self.config = path_config
        self.conda_available = check_command_exists('conda')
    
    def set_source(self, source_key: str) -> bool:
        """Set conda source to specified mirror."""
        if not self.conda_available:
            log_error("conda 未安装或不在 PATH 中")
            return False
        
        if source_key not in CONDA_CONFIGS:
            log_error(f"未知的源: {source_key}")
            return False
        
        source = CONDA_CONFIGS[source_key]
        log_info(f"正在设置 Conda 源为: {source['name']}")
        
        backup_file(self.config.conda_config_path)
        
        try:
            self.config.conda_config_path.write_text(
                source['content'], 
                encoding='utf-8'
            )
            log_info(f"Conda 配置已写入: {self.config.conda_config_path}")
            return True
        except Exception as e:
            log_error(f"写入配置失败: {e}")
            return False
    
    def restore_default(self) -> bool:
        """Restore conda to default channels."""
        if not self.conda_available:
            log_error("conda 未安装")
            return False
        
        log_info("正在恢复 Conda 默认源...")
        
        backup_file(self.config.conda_config_path)
        
        # Remove config keys
        run_command(['conda', 'config', '--remove-key', 'channels'])
        run_command(['conda', 'config', '--remove-key', 'default_channels'])
        run_command(['conda', 'config', '--remove-key', 'custom_channels'])
        
        # Remove .condarc file
        if self.config.conda_config_path.exists():
            try:
                self.config.conda_config_path.unlink()
            except:
                pass
        
        log_info("Conda 已恢复为官方默认源")
        return True
    
    def show_current_config(self):
        """Display current conda configuration."""
        print(f"\n{Colors.BLUE}当前 Conda 配置:{Colors.NC}")
        print("-" * 40)
        
        if self.config.conda_config_path.exists():
            try:
                content = self.config.conda_config_path.read_text(encoding='utf-8')
                print(content)
            except Exception as e:
                print(f"[读取配置失败: {e}]")
        else:
            print("[使用默认 Conda channels]")
        
        print("-" * 40)


# ==============================================================================
# Menu System
# ==============================================================================

class SourceSwitcher:
    """Main application class."""
    
    def __init__(self):
        self.path_config = PathConfig()
        self.pip_manager = PipSourceManager(self.path_config)
        self.conda_manager = CondaSourceManager(self.path_config)
        
        # Enable colors on Windows 10+ or disable for older Windows
        self._setup_terminal()
    
    def _setup_terminal(self):
        """Setup terminal for proper display."""
        system = platform.system().lower()
        
        if system == 'windows':
            # Enable ANSI colors on Windows 10+
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(
                    kernel32.GetStdHandle(-11), 
                    7
                )
            except:
                Colors.disable()
            
            # Set UTF-8 encoding
            try:
                os.system('chcp 65001 > nul 2>&1')
            except:
                pass
    
    def show_system_info(self):
        """Display system information."""
        system = platform.system()
        version = platform.version()
        python_ver = platform.python_version()
        
        print(f"\n{Colors.CYAN}系统信息:{Colors.NC}")
        print(f"  操作系统: {system} ({version[:30]}...)")
        print(f"  Python:   {python_ver}")
        print(f"  pip:      {'✓ 已安装' if self.pip_manager.pip_available else '✗ 未安装'}")
        print(f"  conda:    {'✓ 已安装' if self.conda_manager.conda_available else '✗ 未安装'}")
    
    def menu_pip(self):
        """PIP configuration menu."""
        while True:
            clear_screen()
            print(f"\n{Colors.BLUE}{'='*45}")
            print("          配置 pip 镜像源")
            print(f"{'='*45}{Colors.NC}\n")
            
            for key, (url, name) in PIP_MIRRORS.items():
                rec = " [推荐]" if key == '1' else ""
                print(f"  {key}) {name}{rec}")
            
            print(f"\n  6) 恢复默认源 (PyPI)")
            print(f"  7) 查看当前配置")
            print(f"  0) 返回主菜单")
            
            choice = input(f"\n请选择 [0-7]: ").strip()
            
            if choice in PIP_MIRRORS:
                url, name = PIP_MIRRORS[choice]
                self.pip_manager.set_source(url, name)
                self.pip_manager.show_current_config()
                pause()
            elif choice == '6':
                self.pip_manager.restore_default()
                pause()
            elif choice == '7':
                self.pip_manager.show_current_config()
                pause()
            elif choice == '0':
                break
            else:
                log_error("无效选择")
                pause()
    
    def menu_conda(self):
        """Conda configuration menu."""
        while True:
            clear_screen()
            print(f"\n{Colors.BLUE}{'='*45}")
            print("         配置 Conda 镜像源")
            print(f"{'='*45}{Colors.NC}\n")
            
            if not self.conda_manager.conda_available:
                log_error("Conda 未安装或不在 PATH 中")
                log_warn("请先安装 Anaconda 或 Miniconda")
                pause()
                return
            
            print("  1) Tsinghua 清华 [包含 pytorch/conda-forge]")
            print("  2) USTC 中科大 [包含 bioconda/conda-forge]")
            print(f"\n  3) 恢复默认源")
            print(f"  4) 查看当前配置")
            print(f"  0) 返回主菜单")
            
            choice = input(f"\n请选择 [0-4]: ").strip()
            
            if choice == '1':
                self.conda_manager.set_source('tsinghua')
                self.conda_manager.show_current_config()
                print(f"\n{Colors.YELLOW}提示: 如遇到问题，请运行 'conda clean -i'{Colors.NC}")
                pause()
            elif choice == '2':
                self.conda_manager.set_source('ustc')
                self.conda_manager.show_current_config()
                print(f"\n{Colors.YELLOW}提示: 如遇到问题，请运行 'conda clean -i'{Colors.NC}")
                pause()
            elif choice == '3':
                self.conda_manager.restore_default()
                pause()
            elif choice == '4':
                self.conda_manager.show_current_config()
                pause()
            elif choice == '0':
                break
            else:
                log_error("无效选择")
                pause()
    
    def menu_view_all(self):
        """View all current configurations."""
        clear_screen()
        print(f"\n{Colors.BLUE}{'='*45}")
        print("           当前配置总览")
        print(f"{'='*45}{Colors.NC}")
        
        self.show_system_info()
        self.pip_manager.show_current_config()
        
        if self.conda_manager.conda_available:
            self.conda_manager.show_current_config()
        
        print(f"\n{Colors.CYAN}配置文件位置:{Colors.NC}")
        print(f"  pip:   {self.path_config.pip_config_path}")
        print(f"  conda: {self.path_config.conda_config_path}")
        
        pause()
    
    def main_menu(self):
        """Main menu loop."""
        while True:
            clear_screen()
            print(f"\n{Colors.GREEN}{'='*50}")
            print("     Python 包管理器镜像源切换工具")
            print("     (Cross-Platform Source Switcher)")
            print(f"{'='*50}{Colors.NC}")
            
            self.show_system_info()
            
            print(f"\n{Colors.CYAN}功能菜单:{Colors.NC}")
            print("  1) 配置 pip 镜像源")
            print("  2) 配置 Conda 镜像源")
            print("  3) 查看当前所有配置")
            print("  0) 退出")
            
            choice = input(f"\n请选择 [0-3]: ").strip()
            
            if choice == '1':
                self.menu_pip()
            elif choice == '2':
                self.menu_conda()
            elif choice == '3':
                self.menu_view_all()
            elif choice == '0':
                log_info("再见!")
                break
            else:
                log_error("无效选择")
                pause()


# ==============================================================================
# Command Line Interface
# ==============================================================================

def print_help():
    """Print command line usage help."""
    help_text = """
Python Package Source Switcher
用法: python switch_source.py [选项]

选项:
  (无参数)              启动交互式菜单
  --pip <源>            设置 pip 源 (tsinghua/ustc/aliyun/tencent/douban/default)
  --conda <源>          设置 conda 源 (tsinghua/ustc/default)
  --show                显示当前配置
  --help, -h            显示此帮助信息

示例:
  python switch_source.py                    # 交互式菜单
  python switch_source.py --pip tsinghua     # 设置 pip 为清华源
  python switch_source.py --conda ustc       # 设置 conda 为中科大源
  python switch_source.py --show             # 显示当前配置
"""
    print(help_text)


def cli_mode():
    """Handle command line arguments."""
    args = sys.argv[1:]
    
    if not args:
        return False  # No args, use interactive mode
    
    path_config = PathConfig()
    pip_manager = PipSourceManager(path_config)
    conda_manager = CondaSourceManager(path_config)
    
    pip_source_map = {
        'tsinghua': ('https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple', 'Tsinghua'),
        'ustc': ('https://mirrors.ustc.edu.cn/pypi/simple', 'USTC'),
        'aliyun': ('https://mirrors.aliyun.com/pypi/simple/', 'Aliyun'),
        'tencent': ('https://mirrors.cloud.tencent.com/pypi/simple', 'Tencent'),
        'douban': ('https://pypi.douban.com/simple', 'Douban'),
    }
    
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg in ('--help', '-h'):
            print_help()
            return True
        
        elif arg == '--pip':
            if i + 1 >= len(args):
                log_error("--pip 需要指定源名称")
                return True
            source = args[i + 1].lower()
            if source == 'default':
                pip_manager.restore_default()
            elif source in pip_source_map:
                url, name = pip_source_map[source]
                pip_manager.set_source(url, name)
            else:
                log_error(f"未知的 pip 源: {source}")
                log_info(f"可用源: {', '.join(pip_source_map.keys())}, default")
            i += 2
        
        elif arg == '--conda':
            if i + 1 >= len(args):
                log_error("--conda 需要指定源名称")
                return True
            source = args[i + 1].lower()
            if source == 'default':
                conda_manager.restore_default()
            elif source in CONDA_CONFIGS:
                conda_manager.set_source(source)
            else:
                log_error(f"未知的 conda 源: {source}")
                log_info(f"可用源: {', '.join(CONDA_CONFIGS.keys())}, default")
            i += 2
        
        elif arg == '--show':
            pip_manager.show_current_config()
            if conda_manager.conda_available:
                conda_manager.show_current_config()
            i += 1
        
        else:
            log_error(f"未知参数: {arg}")
            print_help()
            return True
    
    return True


# ==============================================================================
# Entry Point
# ==============================================================================

def main():
    """Main entry point."""
    try:
        # Try CLI mode first
        if cli_mode():
            return
        
        # Interactive menu mode
        app = SourceSwitcher()
        app.main_menu()
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[中断] 用户取消操作{Colors.NC}")
        sys.exit(0)
    except Exception as e:
        log_error(f"发生错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

