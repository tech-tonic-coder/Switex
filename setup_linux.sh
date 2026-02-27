#!/usr/bin/env bash
# Switex — Linux Setup & Launcher
# Run with:  bash setup_linux.sh

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$DIR/switex.py"
LOGFILE="$DIR/switex.log"
PIDFILE="$DIR/switex.pid"
MIN_PYTHON_MINOR=7
HOTKEY="<ctrl>+<alt>+<space>"
USE_YDOTOOL=false
WAYLAND=false

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
echo "  Linux Setup & Launcher"
echo "========================================="
echo ""

# ── Check switex.py exists ─────────────────────────────────────────────────
if [[ ! -f "$SCRIPT" ]]; then
    error "switex.py not found in: $DIR"
    echo "  Make sure setup_linux.sh is in the same folder as switex.py"
    exit 1
fi
info "switex.py found."

# ── Detect package manager ────────────────────────────────────────────────────
PKG_MANAGER=""
PKG_INSTALL=""
if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
    PKG_INSTALL="sudo apt-get install -y"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
    PKG_INSTALL="sudo dnf install -y"
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    PKG_INSTALL="sudo pacman -S --noconfirm"
elif command -v zypper &>/dev/null; then
    PKG_MANAGER="zypper"
    PKG_INSTALL="sudo zypper install -y"
fi

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
    if [[ -n "$PKG_MANAGER" ]]; then
        ask "  Install Python 3 now using $PKG_MANAGER? (y/n): "
        read -r INSTALL
        if [[ "$INSTALL" =~ ^[Yy]$ ]]; then
            case "$PKG_MANAGER" in
                apt)    sudo apt-get update && sudo apt-get install -y python3 python3-pip ;;
                dnf)    sudo dnf install -y python3 python3-pip ;;
                pacman) sudo pacman -S --noconfirm python python-pip ;;
                zypper) sudo zypper install -y python3 python3-pip ;;
            esac
            PYTHON_CMD="python3"
            PYTHON_VER=$(python3 --version 2>&1 | awk '{print $2}')
            info "Python $PYTHON_VER installed."
        else
            echo "  Install manually: https://www.python.org/downloads/"
            exit 1
        fi
    else
        echo "  Install Python 3.7+ for your distribution:"
        echo "  https://www.python.org/downloads/"
        exit 1
    fi
else
    info "Python $PYTHON_VER found  ($PYTHON_CMD)"
fi

# ── Check / install pyperclip ─────────────────────────────────────────────────
section "[CHECK] Checking for pyperclip..."

if ! "$PYTHON_CMD" -c "import pyperclip" &>/dev/null; then
    warn "pyperclip is not installed."
    ask "  Install pyperclip now? (y/n): "
    read -r INSTALL
    if [[ "$INSTALL" =~ ^[Yy]$ ]]; then
        "$PYTHON_CMD" -m pip install pyperclip
        info "pyperclip installed."
    else
        warn "pyperclip required for daemon/clipboard. CLI mode works without it."
        echo "  Install later:  pip3 install pyperclip"
    fi
else
    info "pyperclip is installed."
fi

# ── Check / install pynput ────────────────────────────────────────────────────
section "[CHECK] Checking for pynput..."

if ! "$PYTHON_CMD" -c "import pynput" &>/dev/null; then
    warn "pynput is not installed."
    ask "  Install pynput now? (y/n): "
    read -r INSTALL
    if [[ "$INSTALL" =~ ^[Yy]$ ]]; then
        "$PYTHON_CMD" -m pip install pynput
        info "pynput installed."
    else
        warn "pynput required for the global hotkey daemon."
        echo "  Install later:  pip3 install pynput"
    fi
else
    info "pynput is installed."
fi

# ── Detect display server ─────────────────────────────────────────────────────
section "Platform: Linux — Detecting display server..."
echo ""

if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    WAYLAND=true
    info "Display server: Wayland  (WAYLAND_DISPLAY=$WAYLAND_DISPLAY)"
elif [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
    WAYLAND=true
    info "Display server: Wayland  (XDG_SESSION_TYPE=wayland)"
elif [[ -n "${DISPLAY:-}" ]]; then
    info "Display server: X11  (DISPLAY=$DISPLAY)"
else
    warn "Could not detect display server (no DISPLAY or WAYLAND_DISPLAY set)."
    echo "  Assuming X11. If you are on Wayland, set WAYLAND_DISPLAY and re-run."
fi

# ── X11: check xkblayout-state ────────────────────────────────────────────────
if [[ "$WAYLAND" == "false" ]]; then
    echo ""
    echo -e "${BOLD}Checking xkblayout-state (active layout detection)...${RESET}"

    if command -v xkblayout-state &>/dev/null; then
        info "xkblayout-state is installed."
    else
        warn "xkblayout-state is not installed."
        echo "  Without it, layout detection falls back to setxkbmap (less accurate)."
        echo "  setxkbmap only reads the default layout, not the currently active one."
        if [[ -n "$PKG_MANAGER" ]]; then
            ask "  Install xkblayout-state now? (y/n): "
            read -r INSTALL_XKB
            if [[ "$INSTALL_XKB" =~ ^[Yy]$ ]]; then
                case "$PKG_MANAGER" in
                    apt)
                        sudo apt-get update && sudo apt-get install -y xkblayout-state 2>/dev/null || {
                            warn "xkblayout-state not in apt repos. Trying to build from source..."
                            if command -v git &>/dev/null && command -v make &>/dev/null; then
                                TMP=$(mktemp -d)
                                git clone https://github.com/nonpop/xkblayout-state "$TMP/xkblayout-state" 2>/dev/null
                                make -C "$TMP/xkblayout-state"
                                sudo cp "$TMP/xkblayout-state/xkblayout-state" /usr/local/bin/
                                rm -rf "$TMP"
                                info "xkblayout-state built and installed."
                            else
                                warn "git/make not available. Skipping. Layout detection will use setxkbmap fallback."
                            fi
                        }
                        ;;
                    dnf)    sudo dnf install -y xkblayout-state 2>/dev/null || warn "Not available in dnf. Using setxkbmap fallback." ;;
                    pacman) sudo pacman -S --noconfirm xkblayout-state 2>/dev/null || warn "Not available in pacman. Using setxkbmap fallback." ;;
                esac
            else
                warn "Using setxkbmap fallback for layout detection."
            fi
        else
            echo "  Install manually: https://github.com/nonpop/xkblayout-state"
        fi
    fi

    # X11 hotkey and simulation: full support
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${GREEN}║  X11 detected — full hotkey and key simulation support  ✓   ║${RESET}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
    info "Hotkey daemon: SUPPORTED"
    info "Key simulation (Ctrl+C / Ctrl+V): SUPPORTED"
    info "Default hotkey: Ctrl+Alt+Space"
fi

# ── Wayland: check ydotool ────────────────────────────────────────────────────
if [[ "$WAYLAND" == "true" ]]; then
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${RED}║  Wayland detected — standard key simulation is BLOCKED      ║${RESET}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
    echo "  Wayland's security model blocks cross-application keyboard"
    echo "  simulation (used for copy/paste) and global hotkeys."
    echo ""
    echo "  OPTION A — ydotool (Wayland key simulation tool)"
    echo "  ─────────────────────────────────────────────────"
    echo "  ydotool uses a kernel-level input device (uinput) to simulate"
    echo "  keystrokes, bypassing Wayland's restrictions."
    echo ""

    if command -v ydotool &>/dev/null && command -v ydotoold &>/dev/null; then
        info "ydotool is already installed."
        USE_YDOTOOL=true
    else
        warn "ydotool is NOT installed."
        if [[ -n "$PKG_MANAGER" ]]; then
            ask "  Install ydotool now? (y/n): "
            read -r INSTALL_YDO
            if [[ "$INSTALL_YDO" =~ ^[Yy]$ ]]; then
                case "$PKG_MANAGER" in
                    apt)    sudo apt-get update && sudo apt-get install -y ydotool ;;
                    dnf)    sudo dnf install -y ydotool ;;
                    pacman) sudo pacman -S --noconfirm ydotool ;;
                    zypper) sudo zypper install -y ydotool ;;
                esac
                info "ydotool installed."
                USE_YDOTOOL=true
            fi
        else
            echo "  Install manually: https://github.com/ReimuNotMoe/ydotool"
            echo "  Or via your package manager."
        fi
    fi

    # Check ydotoold (daemon) is running
    if [[ "$USE_YDOTOOL" == "true" ]]; then
        echo ""
        echo -e "${BOLD}Checking ydotoold daemon...${RESET}"

        if systemctl is-active --quiet ydotoold 2>/dev/null; then
            info "ydotoold service: running"
        else
            warn "ydotoold service is not running."
            echo ""
            ask "  Enable and start ydotoold now? (y/n): "
            read -r START_YDO
            if [[ "$START_YDO" =~ ^[Yy]$ ]]; then
                sudo systemctl enable --now ydotoold
                info "ydotoold started."
            else
                echo ""
                echo "  Start manually:"
                echo "    sudo systemctl enable --now ydotoold"
                echo "  Or for current session only:"
                echo "    ydotoold &"
                warn "ydotool will not work until ydotoold is running."
            fi
        fi

        # Check uinput permission
        echo ""
        echo -e "${BOLD}Checking /dev/uinput permission...${RESET}"
        if [[ -r /dev/uinput && -w /dev/uinput ]]; then
            info "/dev/uinput: accessible"
        else
            warn "/dev/uinput is not accessible for your user."
            echo ""
            echo "  ydotool requires write access to /dev/uinput."
            echo "  HOW TO FIX (choose one):"
            echo ""
            echo "  Option 1 — Add yourself to the input group:"
            echo "    sudo usermod -aG input \$USER"
            echo "    (log out and back in for this to take effect)"
            echo ""
            echo "  Option 2 — Create a udev rule:"
            echo "    echo 'KERNEL==\"uinput\", MODE=\"0660\", GROUP=\"input\"' \\"
            echo "      | sudo tee /etc/udev/rules.d/60-ydotool.rules"
            echo "    sudo udevadm control --reload-rules"
            echo "    sudo udevadm trigger"
            echo ""
            ask "  Add current user to input group now? (y/n): "
            read -r ADD_GROUP
            if [[ "$ADD_GROUP" =~ ^[Yy]$ ]]; then
                sudo usermod -aG input "$USER"
                warn "Group change requires logout/login to take effect."
                echo "  After re-logging in, run this script again."
            fi
        fi
    fi

    echo ""
    echo "  OPTION B — XWayland fallback"
    echo "  ─────────────────────────────"
    echo "  If your app runs under XWayland, you can force switex to use X11:"
    echo "    DISPLAY=:0 $PYTHON_CMD \"$SCRIPT\" --daemon"
    echo ""
    echo "  OPTION C — CLI mode only (no hotkey needed)"
    echo "  ─────────────────────────────────────────────"
    echo "  CLI mode works on Wayland without any workaround:"
    echo "    echo \"sghl\" | $PYTHON_CMD \"$SCRIPT\" -f en -t fa"
    echo ""

    if [[ "$USE_YDOTOOL" == "false" ]]; then
        warn "ydotool not installed — daemon hotkey will not work on Wayland."
        echo "  CLI mode is still fully functional."
        echo ""
        ask "  Continue and start daemon anyway (it may work via XWayland)? (y/n): "
        read -r CONTINUE
        if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
            echo ""
            echo "  Exiting. Install ydotool and re-run, or use CLI mode."
            exit 0
        fi
    fi
fi

# ── CLI notification ──────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}CLI mode (always available):${RESET}"
echo "  echo \"sghl\" | $PYTHON_CMD \"$SCRIPT\" -f en -t fa"
echo "  $PYTHON_CMD \"$SCRIPT\" -f ru -t en \"ghbdtn\""
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
            exit 0
        fi
    else
        rm -f "$PIDFILE"
    fi
fi

# ── Start daemon ──────────────────────────────────────────────────────────────
# On Wayland with ydotool, set YDOTOOL_SOCKET if needed
if [[ "$WAYLAND" == "true" && "$USE_YDOTOOL" == "true" ]]; then
    export YDOTOOL_SOCKET="${YDOTOOL_SOCKET:-/tmp/.ydotool_socket}"
    warn "Running on Wayland with ydotool."
    echo "  Note: Switex uses pynput for hotkey detection."
    echo "  If the hotkey does not fire, try the XWayland method:"
    echo "    DISPLAY=:0 $PYTHON_CMD \"$SCRIPT\" --daemon"
fi

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
