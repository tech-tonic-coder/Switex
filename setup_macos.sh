#!/usr/bin/env bash
# Switex — macOS Setup & Launcher
# Run with:  bash setup_macos.sh

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$DIR/switex.py"
LOGFILE="$DIR/switex.log"
PIDFILE="$DIR/switex.pid"
MIN_PYTHON_MINOR=7
HOTKEY="<ctrl>+<alt>+<space>"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*"; }
section() { echo -e "\n${BOLD}${CYAN}$*${RESET}"; }
ask()     { echo -e "${BOLD}$*${RESET}"; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "========================================="
echo "  Switex — Keyboard Layout Converter"
echo "  macOS Setup & Launcher"
echo "========================================="
echo ""

# ── Check switex.py exists ─────────────────────────────────────────────────
if [[ ! -f "$SCRIPT" ]]; then
    error "switex.py not found in: $DIR"
    echo "  Make sure setup_macos.sh is in the same folder as switex.py"
    exit 1
fi
info "switex.py found."

# ── Check Python ──────────────────────────────────────────────────────────────
section "[CHECK] Looking for Python 3.${MIN_PYTHON_MINOR}+..."

PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | awk '{print $2}')
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [[ "$major" -ge 3 && "$minor" -ge "$MIN_PYTHON_MINOR" ]]; then
            PYTHON_CMD="$cmd"
            PYTHON_VER="$ver"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    error "Python 3.${MIN_PYTHON_MINOR}+ was not found."
    echo ""
    echo "  Install Python using one of these methods:"
    echo ""
    echo "  Option A — Homebrew (recommended):"
    echo "    /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "    brew install python"
    echo ""
    echo "  Option B — Official installer:"
    echo "    https://www.python.org/downloads/macos/"
    echo ""
    ask "Open the Python download page? (y/n): "
    read -r OPEN
    if [[ "$OPEN" =~ ^[Yy]$ ]]; then
        open "https://www.python.org/downloads/macos/"
    fi
    exit 1
fi
info "Python $PYTHON_VER found  ($PYTHON_CMD)"

# ── Check / install pyperclip ─────────────────────────────────────────────────
section "[CHECK] Checking for pyperclip..."

if ! "$PYTHON_CMD" -c "import pyperclip" &>/dev/null; then
    warn "pyperclip is not installed."
    echo ""
    ask "  Install pyperclip now? (y/n): "
    read -r INSTALL
    if [[ "$INSTALL" =~ ^[Yy]$ ]]; then
        echo "  Installing..."
        "$PYTHON_CMD" -m pip install pyperclip
        info "pyperclip installed."
    else
        warn "pyperclip is required for daemon and clipboard modes."
        echo "  Install later with:  pip3 install pyperclip"
        echo "  CLI mode (pipe/stdin) will still work without it."
    fi
else
    info "pyperclip is installed."
fi

# ── Check / install pynput ────────────────────────────────────────────────────
section "[CHECK] Checking for pynput..."

if ! "$PYTHON_CMD" -c "import pynput" &>/dev/null; then
    warn "pynput is not installed."
    echo ""
    ask "  Install pynput now? (y/n): "
    read -r INSTALL
    if [[ "$INSTALL" =~ ^[Yy]$ ]]; then
        echo "  Installing..."
        "$PYTHON_CMD" -m pip install pynput
        info "pynput installed."
    else
        warn "pynput is required for the global hotkey daemon."
        echo "  Install later with:  pip3 install pynput"
    fi
else
    info "pynput is installed."
fi

# ── macOS Platform Check ──────────────────────────────────────────────────────
section "Platform: macOS"
echo ""

# Detect macOS version
MACOS_VER=$(sw_vers -productVersion 2>/dev/null || echo "unknown")
info "macOS $MACOS_VER"

# ── Accessibility permission check ────────────────────────────────────────────
echo ""
echo -e "${BOLD}Checking Accessibility permission...${RESET}"
echo ""

# Use osascript to test if we have Accessibility access
HAVE_ACCESS=false
if osascript -e 'tell application "System Events" to get name of first process' &>/dev/null 2>&1; then
    HAVE_ACCESS=true
fi

if [[ "$HAVE_ACCESS" == "true" ]]; then
    info "Accessibility permission: GRANTED"
else
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${RED}║  ACCESSIBILITY PERMISSION REQUIRED                          ║${RESET}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
    echo "  The global hotkey and key simulation require Accessibility access."
    echo "  Without it, the hotkey will register but NEVER fire."
    echo ""
    echo "  HOW TO FIX:"
    echo "  1. Open:  System Settings → Privacy & Security → Accessibility"
    echo "  2. Click the '+' button"
    echo "  3. Add your Terminal app:"

    # Detect which terminal is being used
    TERMINAL_APP=""
    if [[ "$TERM_PROGRAM" == "iTerm.app" ]]; then
        TERMINAL_APP="iTerm"
        echo "     → iTerm2  (found in /Applications/iTerm.app)"
    elif [[ "$TERM_PROGRAM" == "Apple_Terminal" ]]; then
        TERMINAL_APP="Terminal"
        echo "     → Terminal  (found in /Applications/Utilities/Terminal.app)"
    elif [[ -n "${TERM_PROGRAM:-}" ]]; then
        echo "     → $TERM_PROGRAM"
    else
        echo "     → Your current terminal application"
    fi

    echo "  4. Toggle it ON"
    echo "  5. Re-run this script"
    echo ""
    ask "Open Accessibility settings now? (y/n): "
    read -r OPEN_ACC
    if [[ "$OPEN_ACC" =~ ^[Yy]$ ]]; then
        open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        echo ""
        echo "  Grant access, then re-run this script."
        ask "  Exit now so you can grant access? (y/n): "
        read -r DO_EXIT
        if [[ "$DO_EXIT" =~ ^[Yy]$ ]]; then
            echo "  Run  bash \"$0\"  after granting permission."
            exit 0
        fi
    fi
    echo ""
    warn "Proceeding without Accessibility permission."
    warn "The hotkey will register but WON'T fire until permission is granted."
    warn "CLI mode (pipe/stdin) works fine without it."
fi

# ── Hotkey conflict check ─────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Hotkey: Ctrl+Alt+Space${RESET}"
echo ""
echo "  Note: Ctrl+Alt+Space may conflict with some input method shortcuts."
echo "  If the hotkey doesn't respond, try an alternative:"
echo "    bash setup_macos.sh  (then edit HOTKEY= at the top of the script)"
echo "  Suggested alternatives:  <ctrl>+<alt>+k   <ctrl>+<alt>+z"
echo ""

# ── CLI notification ──────────────────────────────────────────────────────────
echo -e "${BOLD}CLI mode is also available — no daemon needed:${RESET}"
echo ""
echo "  echo \"sghl\" | $PYTHON_CMD \"$SCRIPT\" -f en -t fa"
echo "  $PYTHON_CMD \"$SCRIPT\" --list"
echo ""

# ── Check if already running ──────────────────────────────────────────────────
section "Starting daemon..."

if [[ -f "$PIDFILE" ]]; then
    OLD_PID=$(cat "$PIDFILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo ""
        echo "  Switex daemon is already running (PID $OLD_PID)"
        ask "  Restart it? (y/n): "
        read -r RESTART
        if [[ "$RESTART" =~ ^[Yy]$ ]]; then
            kill "$OLD_PID" 2>/dev/null || true
            rm -f "$PIDFILE"
            sleep 1
        else
            echo "  Leaving existing daemon running."
            echo ""
            exit 0
        fi
    else
        rm -f "$PIDFILE"
    fi
fi

# ── Start daemon ──────────────────────────────────────────────────────────────
"$PYTHON_CMD" "$SCRIPT" --daemon --hotkey "$HOTKEY" --log "$LOGFILE" &
DAEMON_PID=$!
echo "$DAEMON_PID" > "$PIDFILE"
sleep 1

if kill -0 "$DAEMON_PID" 2>/dev/null; then
    info "Switex daemon started (PID $DAEMON_PID)"
else
    error "Daemon failed to start. Check the log:"
    echo "  cat \"$LOGFILE\""
    rm -f "$PIDFILE"
    exit 1
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "========================================="
echo "  Switex is running!"
echo ""
echo "  HOW TO USE:"
echo "  1. Type text in the wrong layout"
echo "  2. Switch keyboard to the target language"
echo "  3. Select the mistyped text"
echo "  4. Press  Ctrl+Alt+Space"
echo "  5. Text is converted automatically"
echo ""
echo "  To stop:"
echo "    kill \$(cat \"$PIDFILE\")"
echo "    rm \"$PIDFILE\""
echo ""
echo "  Log:  $LOGFILE"
echo "========================================="
echo ""
