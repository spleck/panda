#!/bin/bash
#
# MarsMode wrapper script
#
# This script provides a convenient interface for running and managing
# MarsMode operations.
#
# Usage: marsmode.sh [command] [options]
#

set -euo pipefail

# Configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly INSTALL_DIR="$(dirname "${SCRIPT_DIR}")"
readonly PANDA_DIR="${INSTALL_DIR}/../.."
readonly LINK_FILE="${INSTALL_DIR}/marsmode-active.link"
readonly PID_FILE="/tmp/marsmode.pid"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Default Python interpreter
PYTHON="${PANDA_DIR}/bin/python3"
[[ -x "${PYTHON}" ]] || PYTHON="$(which python3)"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_debug() { echo -e "${BLUE}[DEBUG]${NC} $*"; }

get_active_script() {
    if [[ -L "${LINK_FILE}" ]]; then
        readlink -f "${LINK_FILE}"
    else
        echo "${INSTALL_DIR}/marsmode/modes.py"
    fi
}

is_running() {
    if [[ -f "${PID_FILE}" ]]; then
        local pid
        pid=$(cat "${PID_FILE}")
        if kill -0 "${pid}" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# ============================================================================
# Commands
# ============================================================================

cmd_start() {
    local mode="${1:-advanced}"
    
    if is_running; then
        log_warn "MarsMode is already running (PID: $(cat "${PID_FILE}"))"
        return 1
    fi
    
    log_info "Starting MarsMode in '${mode}' mode..."
    
    # Run in background
    nohup "${PYTHON}" -m marsmode "${mode}" >/dev/null 2>&1 &
    local pid=$!
    
    echo "${pid}" > "${PID_FILE}"
    
    # Wait a moment to check if it started
    sleep 1
    if kill -0 "${pid}" 2>/dev/null; then
        log_info "MarsMode started (PID: ${pid})"
    else
        log_error "Failed to start MarsMode"
        rm -f "${PID_FILE}"
        return 1
    fi
}

cmd_stop() {
    if ! is_running; then
        log_warn "MarsMode is not running"
        return 1
    fi
    
    local pid
    pid=$(cat "${PID_FILE}")
    
    log_info "Stopping MarsMode (PID: ${pid})..."
    
    kill "${pid}" 2>/dev/null || true
    
    # Wait for process to stop
    for _ in {1..10}; do
        if ! kill -0 "${pid}" 2>/dev/null; then
            break
        fi
        sleep 0.5
    done
    
    rm -f "${PID_FILE}"
    log_info "MarsMode stopped"
}

cmd_restart() {
    cmd_stop || true
    sleep 1
    cmd_start "$@"
}

cmd_status() {
    if is_running; then
        local pid
        pid=$(cat "${PID_FILE}")
        log_info "MarsMode is running (PID: ${pid})"
        
        # Show process info
        ps -p "${pid}" -o pid,ppid,cmd 2>/dev/null || true
    else
        log_info "MarsMode is not running"
    fi
    
    # Also run Python status check
    "${PYTHON}" -m marsmode status
}

cmd_set() {
    local script="$1"
    
    if [[ -z "${script}" ]]; then
        log_error "No mode specified"
        echo "Usage: $0 set <mode>"
        echo "Available modes:"
        "${PYTHON}" -m marsmode list
        return 1
    fi
    
    # Validate mode
    if ! "${PYTHON}" -m marsmode list | grep -q "^  ${script}"; then
        log_error "Invalid mode: ${script}"
        echo "Available modes:"
        "${PYTHON}" -m marsmode list
        return 1
    fi
    
    # Remove old link
    if [[ -L "${LINK_FILE}" ]]; then
        log_info "Removing old mode link"
        rm -f "${LINK_FILE}"
    fi
    
    # Create new link
    ln -sf "${INSTALL_DIR}/marsmode/modes.py" "${LINK_FILE}"
    
    log_info "Mode set to: ${script}"
    
    # Restart if running
    if is_running; then
        log_info "Restarting with new mode..."
        cmd_restart "${script}"
    fi
}

cmd_run() {
    local mode="${1:-advanced}"
    
    log_info "Running MarsMode in '${mode}' mode (foreground)..."
    log_info "Press Ctrl+C to stop"
    echo
    
    "${PYTHON}" -m marsmode "${mode}" --verbose
}

cmd_list() {
    "${PYTHON}" -m marsmode list
}

cmd_log() {
    if [[ -f "/var/log/marsmode.log" ]]; then
        tail -f "/var/log/marsmode.log"
    elif command -v journalctl >/dev/null 2>&1; then
        sudo journalctl -u marsmode -f
    else
        log_error "No log available"
        return 1
    fi
}

cmd_help() {
    cat <<EOF
MarsMode Wrapper Script

Usage: $(basename "$0") <command> [options]

Commands:
    start [mode]     Start MarsMode in the background (default: advanced)
    stop             Stop MarsMode
    restart [mode]   Restart MarsMode
    status           Check MarsMode and Panda status
    set <mode>       Set the default mode
    run [mode]       Run MarsMode in the foreground
    list             List available modes
    log              View MarsMode logs
    help             Show this help message

Examples:
    $(basename "$0") start advanced
    $(basename "$0") set media-volume
    $(basename "$0") run --dry-run

Modes:
    media-volume-basic  Basic volume control with random timing
    media-volume        Volume synchronized to Tesla clock
    speed-basic         Basic speed control with random timing
    speed               Speed synchronized to Tesla clock
    media-back          Media back button for Streaming app
    advanced            Multi-mode with gesture controls

For more information, see:
    ${INSTALL_DIR}/README.md
EOF
}

# ============================================================================
# Main
# ============================================================================

main() {
    local command="${1:-help}"
    shift || true
    
    case "${command}" in
        start)
            cmd_start "$@"
            ;;
        stop)
            cmd_stop
            ;;
        restart)
            cmd_restart "$@"
            ;;
        status)
            cmd_status
            ;;
        set)
            cmd_set "$@"
            ;;
        run)
            cmd_run "$@"
            ;;
        list)
            cmd_list
            ;;
        log|logs)
            cmd_log
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            log_error "Unknown command: ${command}"
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
