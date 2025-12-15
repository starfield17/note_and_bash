#!/bin/bash

# ==============================================================================
# Python Package Source Switcher (Linux Optimized)
# Supports: pip, conda
# Mirrors: Tsinghua, USTC, Tencent, Aliyun, Douban
# ==============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Config Files
CONDARC="$HOME/.condarc"
PIP_CONF="$HOME/.config/pip/pip.conf"

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()  { echo -e "${RED}[ERR] ${NC} $1"; }

check_requirements() {
    if ! command -v pip &> /dev/null; then
        log_warn "pip is not installed."
    fi
    if ! command -v conda &> /dev/null; then
        log_warn "conda is not installed."
    fi
}

backup_file() {
    local file=$1
    if [ -f "$file" ]; then
        cp "$file" "${file}.bak_$(date +%Y%m%d_%H%M%S)"
        log_info "Backed up $file"
    fi
}

# ------------------------------------------------------------------------------
# PIP Functions
# ------------------------------------------------------------------------------

set_pip_source() {
    local url=$1
    local name=$2

    if ! command -v pip &> /dev/null; then
        log_err "pip not found. Skipping."
        return
    fi

    log_info "Setting pip source to: $name"
    
    # pip install --upgrade pip &> /dev/null

    if [ "$url" == "default" ]; then
        pip config unset global.index-url
        log_info "Restored pip to default source."
    else
        pip config set global.index-url "$url"
        log_info "pip source updated."
    fi
    
    echo -e "${BLUE}Current pip config:${NC}"
    pip config list
}

menu_pip() {
    echo -e "\n${BLUE}=== Configure pip Source ===${NC}"
    echo "1) Tsinghua (China) [Recommended]"
    echo "2) USTC (China)"
    echo "3) Aliyun (China)"
    echo "4) Tencent (China)"
    echo "5) Douban (China)"
    echo "6) Restore Default"
    echo "0) Return to Main Menu"
    
    read -p "Enter choice [0-6]: " choice

    case $choice in
        1) set_pip_source "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple" "Tsinghua" ;;
        2) set_pip_source "https://mirrors.ustc.edu.cn/pypi/simple" "USTC" ;;
        3) set_pip_source "https://mirrors.aliyun.com/pypi/simple/" "Aliyun" ;;
        4) set_pip_source "http://mirrors.cloud.tencent.com/pypi/simple" "Tencent" ;;
        5) set_pip_source "http://pypi.douban.com/simple" "Douban" ;;
        6) set_pip_source "default" "Official" ;;
        0) return ;;
        *) log_err "Invalid choice" ;;
    esac
}

# ------------------------------------------------------------------------------
# Conda Functions
# ------------------------------------------------------------------------------

write_condarc_tsinghua() {
    backup_file "$CONDARC"
    cat > "$CONDARC" <<EOF
channels:
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
EOF
    log_info "Written Tsinghua configuration to $CONDARC"
}

write_condarc_ustc() {
    backup_file "$CONDARC"
    cat > "$CONDARC" <<EOF
channels:
  - nodefaults
show_channel_urls: true
custom_channels:
  conda-forge: https://mirrors.ustc.edu.cn/anaconda/cloud
  bioconda: https://mirrors.ustc.edu.cn/anaconda/cloud
  msys2: https://mirrors.ustc.edu.cn/anaconda/cloud
  pytorch: https://mirrors.ustc.edu.cn/anaconda/cloud
default_channels:
  - https://mirrors.ustc.edu.cn/anaconda/pkgs/main
  - https://mirrors.ustc.edu.cn/anaconda/pkgs/r
EOF
    log_info "Written USTC configuration to $CONDARC"
}

write_condarc_default() {
    backup_file "$CONDARC"
    conda config --remove-key channels
    conda config --remove-key default_channels
    conda config --remove-key custom_channels
    log_info "Restored Conda to official defaults."
}

menu_conda() {
    if ! command -v conda &> /dev/null; then
        log_err "Conda is not installed."
        return
    fi

    echo -e "\n${BLUE}=== Configure Conda Source ===${NC}"
    echo "1) Tsinghua (China) [Includes pytorch/conda-forge]"
    echo "2) USTC (China) [Includes bioconda/conda-forge]"
    echo "3) Restore Default (Official)"
    echo "0) Return to Main Menu"

    read -p "Enter choice [0-3]: " choice

    case $choice in
        1) write_condarc_tsinghua ;;
        2) write_condarc_ustc ;;
        3) write_condarc_default ;;
        0) return ;;
        *) log_err "Invalid choice" ;;
    esac
    
    echo -e "${BLUE}Current Conda config:${NC}"
    cat "$CONDARC"
    echo -e "${YELLOW}Note: Run 'conda clean -i' if you encounter errors after switching.${NC}"
}

# ------------------------------------------------------------------------------
# Main Loop
# ------------------------------------------------------------------------------

check_requirements

while true; do
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "   Linux Python Source Switcher Tool"
    echo -e "${GREEN}========================================${NC}"
    echo "1) Configure pip"
    echo "2) Configure conda"
    echo "0) Exit"
    
    read -p "Enter choice: " choice
    
    case $choice in
        1) menu_pip ;;
        2) menu_conda ;;
        0) 
            log_info "Exiting..."
            exit 0 
            ;;
        *) log_err "Invalid choice" ;;
    esac
done
