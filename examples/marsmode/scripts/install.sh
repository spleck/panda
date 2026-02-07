#!/bin/bash
#
# MarsMode Installer for Raspberry Pi OS
#
# This script installs MarsMode and all dependencies for use with
# the comma.ai Panda CAN interface on Tesla vehicles.
#
# Usage: ./install.sh [-v] [-h]
#   -v  Verbose mode
#   -h  Show help
#

set -euo pipefail

# Configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PANDA_DIR="${HOME}/panda"
readonly INSTALL_DIR="${PANDA_DIR}/examples/marsmode"
readonly VENV_DIR="${PANDA_DIR}"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

# Verbosity flag
VERBOSE=0

# ============================================================================
# Functions
# ============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

run_cmd() {
    if [[ ${VERBOSE} -eq 1 ]]; then
        "$@"
    else
        "$@" >/dev/null 2>&1
    fi
}

show_help() {
    cat <<EOF
MarsMode Installer for Raspberry Pi OS

This script installs MarsMode and all dependencies for use with
the comma.ai Panda CAN interface on Tesla vehicles.

Usage: $(basename "$0") [OPTIONS]

Options:
    -v, --verbose    Enable verbose output
    -h, --help       Show this help message

Examples:
    ./install.sh              # Standard installation
    ./install.sh -v           # Verbose installation

The installer will:
    1. Check for Raspberry Pi OS
    2. Install system dependencies
    3. Clone the Panda repository
    4. Set up Python virtual environment
    5. Install Python dependencies
    6. Configure udev rules for Panda
    7. Build and flash Panda firmware
    8. Set up systemd service for auto-start
    9. Configure boot settings for Pi 4 USB
EOF
}

check_pios() {
    echo -n "Checking for Raspberry Pi OS... "
    
    if [[ -f '/etc/apt/sources.list.d/raspi.list' ]]; then
        log_info "OK"
        return 0
    fi
    
    log_warn "NOT DETECTED"
    echo "- This installer is designed for Raspberry Pi OS."
    read -r -p "- Proceed anyway? [y/N] " response
    
    if [[ "${response}" =~ ^[Yy]$ ]]; then
        log_warn "Proceeding with override. Good luck!"
        return 0
    else
        log_error "Aborted. Please run on Raspberry Pi OS."
        exit 1
    fi
}

install_system_deps() {
    echo -n "Installing system dependencies... "
    
    local packages=(
        dfu-util
        gcc-arm-none-eabi
        python3-pip
        python3-venv
        libffi-dev
        git
        scons
        screen
    )
    
    run_cmd sudo apt-get update
    run_cmd sudo apt-get install -y "${packages[@]}"
    
    log_info "OK"
}

clone_panda_repo() {
    echo -n "Checking out Panda git repository... "
    
    if [[ -d "${PANDA_DIR}/.git" ]]; then
        log_info "SKIPPED (already exists)"
        return 0
    fi
    
    run_cmd git clone https://github.com/spleck/panda.git "${PANDA_DIR}"
    log_info "OK"
}

setup_venv() {
    echo -n "Setting up Python virtual environment... "
    
    if [[ -f "${VENV_DIR}/bin/python3" ]]; then
        log_info "SKIPPED (already exists)"
        return 0
    fi
    
    run_cmd python3 -m venv "${VENV_DIR}"
    log_info "OK"
}

install_python_deps() {
    echo -n "Installing Python dependencies... "
    
    # Activate venv
    # shellcheck source=/dev/null
    source "${VENV_DIR}/bin/activate"
    
    run_cmd pip install --upgrade pip
    run_cmd pip install -r "${PANDA_DIR}/requirements.txt"
    run_cmd pip install -e "${PANDA_DIR}"
    
    # Install MarsMode dependencies
    if [[ -f "${INSTALL_DIR}/requirements.txt" ]]; then
        run_cmd pip install -r "${INSTALL_DIR}/requirements.txt"
    fi
    
    log_info "OK"
}

setup_udev() {
    echo -n "Setting up udev rules... "
    
    local rules_file='/etc/udev/rules.d/11-panda.rules'
    
    if [[ -f "${rules_file}" ]]; then
        log_info "SKIPPED (already exists)"
        return 0
    fi
    
    sudo tee "${rules_file}" >/dev/null <<'EOF'
# comma.ai Panda udev rules
SUBSYSTEM=="usb", ATTRS{idVendor}=="bbaa", ATTRS{idProduct}=="ddcc", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="bbaa", ATTRS{idProduct}=="ddee", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="df11", MODE="0666"
EOF
    
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    
    log_info "OK"
}

build_firmware() {
    echo -n "Building Panda firmware... "
    
    # Activate venv
    # shellcheck source=/dev/null
    source "${VENV_DIR}/bin/activate"
    
    cd "${PANDA_DIR}/board"
    run_cmd scons -u
    
    log_info "OK"
}

flash_panda() {
    log_info "Entering Panda recovery mode..."
    
    cd "${PANDA_DIR}/board"
    
    if [[ ${VERBOSE} -eq 1 ]]; then
        ./recover.py
    else
        ./recover.py >/dev/null 2>&1 || true
    fi
    
    echo -n "Flashing Panda firmware... "
    
    if [[ ${VERBOSE} -eq 1 ]]; then
        ./flash.py
    else
        ./flash.py >/dev/null 2>&1
    fi
    
    log_info "OK"
}

setup_systemd() {
    echo -n "Setting up systemd service... "
    
    local service_file='/etc/systemd/system/marsmode.service'
    
    if [[ -f "${service_file}" ]]; then
        log_info "SKIPPED (already exists)"
        return 0
    fi
    
    sudo tee "${service_file}" >/dev/null <<EOF
[Unit]
Description=MarsMode - Tesla CAN bus automation
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=${VENV_DIR}/bin/python -m marsmode advanced
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable marsmode.service
    
    log_info "OK"
}

configure_boot() {
    echo -n "Configuring boot settings... "
    
    local config_file='/boot/firmware/config.txt'
    local setting='dtoverlay=dwc2,dr_mode=host'
    
    if [[ -f "${config_file}" ]]; then
        if ! grep -q "${setting}" "${config_file}" 2>/dev/null; then
            echo "${setting}" | sudo tee -a "${config_file}" >/dev/null
        fi
    fi
    
    log_info "OK"
}

# ============================================================================
# Main
# ============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -v|--verbose)
                VERBOSE=1
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Show banner
    cat <<EOF
----------------------------------------------------------------------

                   ** MarsMode Installer for PiOS! **

----------------------------------------------------------------------

EOF
    
    # Run installation steps
    check_pios
    install_system_deps
    clone_panda_repo
    setup_venv
    install_python_deps
    setup_udev
    build_firmware
    flash_panda
    setup_systemd
    configure_boot
    
    # Done
    cat <<EOF

----------------------------------------------------------------------

        ** MarsMode installation complete! **

  To start MarsMode now:
    sudo systemctl start marsmode

  To check status:
    sudo systemctl status marsmode

  To change mode:
    sudo systemctl edit marsmode
    # Change ExecStart line to desired mode

  Available modes:
    - media-volume-basic
    - media-volume
    - speed-basic  
    - speed
    - media-back
    - advanced

----------------------------------------------------------------------
EOF
}

main "$@"
