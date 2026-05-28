#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Switex — Service Manager                                               ║
# ║  Usage:  bash switex.sh [command]                                       ║
# ║  Commands: start | stop | restart | status | log | help                 ║
# ╚══════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$DIR/switex.py"
LOGFILE="$DIR/switex.log"
PIDFILE="$DIR/switex.pid"
HOTKEY="<win>+<alt>+<space>"
MIN_PYTHON_MINOR=7

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'

info()    { echo -e "  ${GREEN}✓${RESET}  $*"; }
warn()    { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
error()   { echo -e "  ${RED}✗${RESET}  $*"; }
hint()    { echo -e "  ${DIM}→  $*${RESET}"; }

# ── Banner ────────────────────────────────────────────────────────────────────
_banner() {
    echo ""
    echo -e "${BOLD}${CYAN}  ╔══════════════════════════════════╗${RESET}"
    echo -e "${BOLD}${CYAN}  ║   Switex — Layout Converter      ║${RESET}"
    echo -e "${BOLD}${CYAN}  ╚══════════════════════════════════╝${RESET}"
    echo ""
}

# ── Detect Python ─────────────────────────────────────────────────────────────
_find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            ver=$("$cmd" --version 2>&1 | awk '{print $2}')
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [[ "$major" -ge 3 && "$minor" -ge "$MIN_PYTHON_MINOR" ]]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_CMD=""

# ── PID helpers ───────────────────────────────────────────────────────────────
_pid_running() {
    [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

_get_pid() {
    cat "$PIDFILE" 2>/dev/null || echo ""
}

_clean_pid() {
    rm -f "$PIDFILE"
}

# ─────────────────────────────────────────────────────────────────────────────
# PREFLIGHT — check switex.py, Python, and packages exist
# Returns 0 if all good, 1 if something is missing (with guidance printed)
# ─────────────────────────────────────────────────────────────────────────────
_preflight() {
    local ok=true

    # switex.py
    if [[ ! -f "$SCRIPT" ]]; then
        error "switex.py not found in: $DIR"
        hint  "Place switex.sh in the same folder as switex.py"
        ok=false
    fi

    # Python
    PYTHON_CMD=$(_find_python 2>/dev/null || true)
    if [[ -z "$PYTHON_CMD" ]]; then
        error "Python 3.${MIN_PYTHON_MINOR}+ not found."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            hint "brew install python   OR   https://www.python.org/downloads/macos/"
        else
            hint "sudo apt install python3   OR   https://www.python.org/downloads/"
        fi
        ok=false
    fi

    # pynput
    if [[ -n "$PYTHON_CMD" ]] && ! "$PYTHON_CMD" -c "import pynput" &>/dev/null; then
        warn "pynput not installed — daemon won't start."
        hint "$PYTHON_CMD -m pip install pynput"
        ok=false
    fi

    # pyperclip
    if [[ -n "$PYTHON_CMD" ]] && ! "$PYTHON_CMD" -c "import pyperclip" &>/dev/null; then
        warn "pyperclip not installed — daemon won't start."
        hint "$PYTHON_CMD -m pip install pyperclip"
        ok=false
    fi

    [[ "$ok" == "true" ]]
}

# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM NOTES  (shown once during start if relevant)
# ─────────────────────────────────────────────────────────────────────────────
_platform_notes() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # Check Accessibility
        if ! osascript -e 'tell application "System Events" to get name of first process' &>/dev/null 2>&1; then
            echo ""
            warn "Accessibility permission not granted — hotkey will register but never fire."
            hint "System Settings → Privacy & Security → Accessibility → add your Terminal → ON"
        fi

    elif [[ -n "${WAYLAND_DISPLAY:-}" || "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
        echo ""
        warn "Wayland detected — global hotkeys may be blocked."
        hint "Install ydotool: sudo apt install ydotool && sudo systemctl enable --now ydotoold"
        hint "Or use CLI mode: echo 'sghl' | $PYTHON_CMD \"$SCRIPT\" -f en -t fa"

    else
        # X11 — check xkblayout-state
        if ! command -v xkblayout-state &>/dev/null; then
            echo ""
            warn "xkblayout-state not found — layout detection falls back to setxkbmap (less accurate)."
            hint "sudo apt install xkblayout-state"
        fi
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

cmd_start() {
    _banner

    if _pid_running; then
        local pid
        pid=$(_get_pid)
        warn "Switex is already running  (PID $pid)"
        hint "Use 'bash switex.sh restart' to restart it."
        echo ""
        return 0
    fi

    echo -e "${BOLD}  Starting Switex daemon...${RESET}"

    if ! _preflight; then
        echo ""
        error "Cannot start — fix the issues above first."
        echo ""
        return 1
    fi

    _platform_notes

    # Clean up stale PID file
    _clean_pid

    # Launch daemon in background
    "$PYTHON_CMD" "$SCRIPT" --daemon --hotkey "$HOTKEY" --log "$LOGFILE" &
    local pid=$!
    echo "$pid" > "$PIDFILE"

    # Give it a moment to fail fast if something is wrong
    sleep 1

    if kill -0 "$pid" 2>/dev/null; then
        echo ""
        info "Switex daemon started  (PID $pid)"
        info "Hotkey: Ctrl+Alt+Space"
        info "Log:    $LOGFILE"
        echo ""
        echo -e "  ${BOLD}How to use:${RESET}"
        echo    "  1. Type text in the wrong keyboard layout"
        echo    "  2. Switch your keyboard to the target language"
        echo    "  3. Select the mistyped text"
        echo    "  4. Press  Ctrl+Alt+Space"
        echo    "  5. The text is converted automatically ✓"
        echo ""
    else
        _clean_pid
        echo ""
        error "Daemon failed to start."
        hint  "Check the log: bash switex.sh log"
        echo ""
        return 1
    fi
}

cmd_stop() {
    _banner
    echo -e "${BOLD}  Stopping Switex daemon...${RESET}"
    echo ""

    if ! _pid_running; then
        warn "Switex is not running."
        _clean_pid
        echo ""
        return 0
    fi

    local pid
    pid=$(_get_pid)

    # Send SIGTERM for a clean shutdown
    kill -TERM "$pid" 2>/dev/null || true

    # Wait up to 5 seconds for it to exit
    local waited=0
    while kill -0 "$pid" 2>/dev/null && [[ $waited -lt 10 ]]; do
        sleep 0.5
        (( waited++ )) || true
    done

    # Force-kill if still alive
    if kill -0 "$pid" 2>/dev/null; then
        kill -KILL "$pid" 2>/dev/null || true
        sleep 0.3
    fi

    _clean_pid
    info "Switex stopped  (was PID $pid)"
    echo ""
}

cmd_restart() {
    _banner
    echo -e "${BOLD}  Restarting Switex daemon...${RESET}"
    echo ""

    if _pid_running; then
        local pid
        pid=$(_get_pid)
        kill -TERM "$pid" 2>/dev/null || true
        local waited=0
        while kill -0 "$pid" 2>/dev/null && [[ $waited -lt 10 ]]; do
            sleep 0.5
            (( waited++ )) || true
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill -KILL "$pid" 2>/dev/null || true
        fi
        _clean_pid
        info "Old daemon stopped  (was PID $pid)"
    else
        warn "Daemon was not running — starting fresh."
    fi

    echo ""

    if ! _preflight; then
        echo ""
        error "Cannot start — fix the issues above first."
        echo ""
        return 1
    fi

    _platform_notes

    "$PYTHON_CMD" "$SCRIPT" --daemon --hotkey "$HOTKEY" --log "$LOGFILE" &
    local pid=$!
    echo "$pid" > "$PIDFILE"
    sleep 1

    if kill -0 "$pid" 2>/dev/null; then
        info "Switex restarted  (PID $pid)"
        info "Hotkey: Ctrl+Alt+Space"
        info "Log:    $LOGFILE"
        echo ""
    else
        _clean_pid
        error "Daemon failed to start after restart."
        hint  "Check the log: bash switex.sh log"
        echo ""
        return 1
    fi
}

cmd_status() {
    _banner
    echo -e "${BOLD}  Switex Status${RESET}"
    echo ""

    if _pid_running; then
        local pid
        pid=$(_get_pid)
        echo -e "  ${GREEN}● RUNNING${RESET}  (PID $pid)"
        echo    "  Hotkey : Ctrl+Alt+Space"
        echo    "  Script : $SCRIPT"
        echo    "  Log    : $LOGFILE"
        echo    "  PID    : $PIDFILE"

        # Show platform
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo    "  OS     : macOS"
        elif [[ -n "${WAYLAND_DISPLAY:-}" || "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
            echo    "  OS     : Linux / Wayland"
        else
            echo    "  OS     : Linux / X11"
        fi

        # Show last few log lines
        if [[ -f "$LOGFILE" ]]; then
            echo ""
            echo -e "  ${DIM}Last log entries:${RESET}"
            tail -5 "$LOGFILE" | sed 's/^/    /'
        fi

    else
        echo -e "  ${RED}○ STOPPED${RESET}"
        _clean_pid

        if [[ -f "$LOGFILE" ]]; then
            echo ""
            echo -e "  ${DIM}Last log entries:${RESET}"
            tail -5 "$LOGFILE" | sed 's/^/    /'
        fi
    fi

    echo ""

    # Dependency check summary
    echo -e "  ${DIM}Dependencies:${RESET}"

    PYTHON_CMD=$(_find_python 2>/dev/null || true)
    if [[ -n "$PYTHON_CMD" ]]; then
        local ver
        ver=$("$PYTHON_CMD" --version 2>&1 | awk '{print $2}')
        echo -e "    Python    ${GREEN}✓${RESET}  $ver  ($PYTHON_CMD)"
    else
        echo -e "    Python    ${RED}✗${RESET}  not found"
    fi

    if [[ -n "$PYTHON_CMD" ]] && "$PYTHON_CMD" -c "import pynput" &>/dev/null 2>&1; then
        echo -e "    pynput    ${GREEN}✓${RESET}"
    else
        echo -e "    pynput    ${RED}✗${RESET}  (pip install pynput)"
    fi

    if [[ -n "$PYTHON_CMD" ]] && "$PYTHON_CMD" -c "import pyperclip" &>/dev/null 2>&1; then
        echo -e "    pyperclip ${GREEN}✓${RESET}"
    else
        echo -e "    pyperclip ${RED}✗${RESET}  (pip install pyperclip)"
    fi

    if [[ "$OSTYPE" != "darwin"* ]]; then
        if command -v xkblayout-state &>/dev/null; then
            echo -e "    xkblayout ${GREEN}✓${RESET}"
        else
            echo -e "    xkblayout ${YELLOW}–${RESET}  not installed (optional, improves layout detection)"
        fi
    fi

    echo ""
}

cmd_log() {
    if [[ ! -f "$LOGFILE" ]]; then
        warn "No log file yet: $LOGFILE"
        hint "The log is created when the daemon starts."
        echo ""
        return 0
    fi

    # If 'follow' arg passed, tail -f; otherwise show full log with pager
    if [[ "${1:-}" == "-f" || "${1:-}" == "--follow" ]]; then
        echo -e "${BOLD}  Following $LOGFILE  (Ctrl+C to stop)${RESET}"
        echo ""
        tail -f "$LOGFILE"
    else
        echo -e "${BOLD}  Log: $LOGFILE${RESET}"
        echo ""
        # Use pager if available and output is a terminal
        if [[ -t 1 ]] && command -v less &>/dev/null; then
            less +G "$LOGFILE"
        else
            cat "$LOGFILE"
        fi
    fi
}

cmd_help() {
    _banner
    echo -e "${BOLD}  Usage:${RESET}  bash switex.sh [command]"
    echo ""
    echo -e "${BOLD}  Commands:${RESET}"
    echo    "    start      Start the Switex hotkey daemon"
    echo    "    stop       Stop the daemon"
    echo    "    restart    Stop then start the daemon"
    echo    "    status     Show running status and dependency check"
    echo    "    log        View the log file (add -f to follow live)"
    echo    "    help       Show this help message"
    echo ""
    echo -e "${BOLD}  CLI mode (no daemon):${RESET}"
    PYTHON_CMD=$(_find_python 2>/dev/null || echo "python3")
    echo    "    echo 'sghl'   | $PYTHON_CMD switex.py -f en -t fa"
    echo    "    echo 'ghbdtn' | $PYTHON_CMD switex.py -f en -t ru"
    echo    "    $PYTHON_CMD switex.py --list"
    echo ""
    echo -e "${BOLD}  Custom hotkey:${RESET}"
    echo    "    Edit HOTKEY= at the top of this script."
    echo    "    Example:  HOTKEY=\"<ctrl>+<alt>+k\""
    echo ""
    echo -e "${BOLD}  Supported languages:${RESET}"
    echo    "    EN ↔ FA  (Persian/Farsi)"
    echo    "    EN ↔ AR  (Arabic)"
    echo    "    EN ↔ RU  (Russian)"
    echo    "    EN ↔ TR  (Turkish)"
    echo    "    EN ↔ HE  (Hebrew)"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
COMMAND="${1:-help}"

case "$COMMAND" in
    start)          cmd_start ;;
    stop)           cmd_stop ;;
    restart)        cmd_restart ;;
    status)         cmd_status ;;
    log)            cmd_log "${2:-}" ;;
    help|--help|-h) cmd_help ;;
    *)
        echo ""
        error "Unknown command: '$COMMAND'"
        echo ""
        cmd_help
        exit 1
        ;;
esac
