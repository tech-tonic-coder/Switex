# Switex

**Typed in the wrong keyboard layout? Convert it — without retyping.**

`Switex` converts text you accidentally typed in the wrong language directly inside any application, via a global hotkey. Select the mistyped text, press **Ctrl+Alt+Space**, and it's fixed instantly. It also works as a classic command-line pipe tool.

```
You typed:   sghl           →   سلام
You typed:   ghbdtn         →   привет
You typed:   ihpfv          →   שלום
```

> **License: [GNU General Public License v3.0 (GPL-3.0)](LICENSE)**
> Switex is free and open-source software. You are free to use, modify, and distribute it
> under the terms of the GPL-3.0 license. Any distributed modifications must also remain
> open-source under the same license. See [LICENSE](LICENSE) for full terms.

---

## ⬇️ Download

Go to the **[Releases](../../releases/latest)** page to download the ready-to-use files for your OS. No build step needed — just download and run.

### Windows
| File | What it is |
|------|-----------|
| `Switex.exe` | **All-in-one app** — includes Python and all dependencies. Double-click to launch. Shows a system tray icon with Start / Stop / Restart / Exit. No installation required. |

### macOS
| File | What it is |
|------|-----------|
| `switex.py` | Main script |
| `setup_macos.sh` | Setup & launcher — checks dependencies, permissions, and starts the daemon |

### Linux
| File | What it is |
|------|-----------|
| `switex.py` | Main script |
| `setup_linux.sh` | Setup & launcher — detects X11 vs Wayland, installs ydotool if needed, starts the daemon |

---

## 🪟 Windows — Switex.exe

Double-click `Switex.exe`. That's it.

- Starts automatically and lives in the **system tray** (bottom-right of your taskbar)
- **Right-click** the tray icon for the full menu:

| Menu item | Action |
|-----------|--------|
| ● Running / ○ Stopped | Current status (not clickable) |
| **Start** | Start the hotkey daemon |
| **Stop** | Stop the hotkey daemon |
| **Restart** | Restart the daemon |
| **Status** | Show a notification with current status |
| **Open Log** | Open `switex.log` in Notepad |
| **Exit** | Stop daemon and quit |

- No Python installation required — everything is bundled inside
- Only one instance can run at a time (protected by a Windows mutex)

---

## 🍎 macOS & 🐧 Linux — Setup Scripts

**You only need two files.** Download `switex.py` and your OS setup script from the [Releases](../../releases/latest) page, put them in the same folder, and run the script.

| Your OS | Run with |
|---------|----------|
| **macOS** | `bash setup_macos.sh` |
| **Linux** | `bash setup_linux.sh` |

The setup script will:
1. ✅ Check if Python 3.7+ is installed — guide you to install it if not
2. ✅ Check for required packages (`pynput`, `pyperclip`) — offer to install them
3. ✅ Detect your environment (X11 vs Wayland, Accessibility permission on macOS)
4. ✅ Warn about anything needing manual action, with exact steps
5. ✅ Start the daemon automatically

---

## How to Use (Daemon Mode)

1. Type something in the **wrong keyboard layout**
   *(e.g. you meant to write Persian but your keyboard was set to English)*
2. **Switch** your keyboard to the correct language (e.g. switch to FA)
3. **Select** the mistyped text
4. Press **`Ctrl+Alt+Space`**
5. The text is replaced with the correct version ✓

The daemon detects which layout you switched from/to — no flags needed.

---

## CLI Mode

No daemon, no extra packages — just Python. Works anywhere, including Wayland and SSH.

```bash
# Auto-detect and convert (defaults to EN→FA for ASCII input)
echo "sghl" | python switex.py

# Explicit direction
echo "sghl"   | python switex.py -f en -t fa    # → سلام
echo "ghbdtn" | python switex.py -f en -t ru    # → привет
echo "ihpfv"  | python switex.py -f en -t he    # → שלום

# Inline text
python switex.py -f en -t ar "lhpfhm"

# Convert clipboard (requires pyperclip)
python switex.py --clipboard -f en -t fa

# List all supported pairs
python switex.py --list
```

---

## Supported Languages

| Code | Language | Direction |
|------|----------|-----------|
| `en` | English | ↔ all below |
| `fa` | Persian / Farsi (Standard ISIRI 9147 + Legacy) | ↔ EN |
| `ar` | Arabic | ↔ EN |
| `ru` | Russian | ↔ EN |
| `tr` | Turkish | ↔ EN |
| `he` | Hebrew | ↔ EN |

All pairs are bidirectional. Persian auto-detects Standard vs. Legacy layout.

---

## All Options (CLI)

```
python switex.py [options] [text]

  text                  Text to convert (omit to read from stdin)
  -f, --from LANG       Source language code (default: auto-detect)
  -t, --to   LANG       Target language code (default: auto-detect)
  -c, --clipboard       Read from clipboard, paste converted text back
  -d, --daemon          Start hotkey daemon
      --hotkey HOTKEY   Hotkey string (default: <ctrl>+<alt>+<space>)
  -l, --list            List supported language pairs and exit
      --log FILE        Write log to FILE (useful for background mode)
```

Custom hotkey examples:
```bash
python switex.py --daemon --hotkey "<ctrl>+<alt>+k"
python switex.py --daemon --hotkey "<ctrl>+<alt>+z"
```

---

## Platform Details

### Windows — ✅ Full support
- Uses `GetKeyboardLayout` on the exact foreground window for accurate layout detection
- `Switex.exe` bundles everything — no Python or pip needed
- For developers: `build.bat` compiles `Switex.exe` from source using PyInstaller

### macOS — ✅ Full support (one manual step required)

Requires **Accessibility permission** for the hotkey and key simulation:

> System Settings → Privacy & Security → Accessibility → add your Terminal → toggle ON

The setup script checks this and opens the settings panel for you if needed.

- `Ctrl+Alt+Space` can conflict with some input methods — try `<ctrl>+<alt>+k` if needed

### Linux / X11 — ✅ Full support

- Hotkey and key simulation work natively
- Install `xkblayout-state` for accurate per-window layout detection:
  ```bash
  sudo apt install xkblayout-state
  ```
  Without it, falls back to `setxkbmap -query` which only reads the default layout.

### Linux / Wayland — ⚠️ Limited (workarounds available)

Wayland blocks cross-app keyboard simulation and global hotkeys by design.

**Option A — ydotool** *(recommended)*

Uses kernel-level `uinput` to bypass Wayland restrictions:

```bash
sudo apt install ydotool
sudo systemctl enable --now ydotoold
bash setup_linux.sh      # detects Wayland, walks through ydotool setup
```

**Option B — XWayland**

If the app you're typing in runs under XWayland:
```bash
DISPLAY=:0 python switex.py --daemon
```

**Option C — CLI only** *(always works on Wayland, no setup needed)*
```bash
echo "sghl" | python switex.py -f en -t fa
```

---

## Requirements

| Feature | Requires |
|---------|---------|
| `Switex.exe` (Windows) | Nothing — fully bundled |
| CLI mode | Python 3.7+ only |
| Daemon / hotkey (macOS & Linux) | Python 3.7+ · `pynput` · `pyperclip` |
| Clipboard mode | Python 3.7+ · `pyperclip` |

```bash
pip install pynput pyperclip
```

---

## How It Works

**Layout detection**
When the hotkey fires, the daemon captures the foreground window handle at that exact instant — before any focus shift. It reads the keyboard layout for that specific window via the OS API (`GetKeyboardLayout` on Windows, `NSTextInputContext` on macOS, `xkblayout-state` on Linux). The previously recorded layout is the source; the current layout is the target.

**Copy → Convert → Paste**
1. Hotkey fires → window handle + layout captured immediately
2. Modifier keys released (avoids interference with Ctrl+C)
3. Ctrl+C simulated → clipboard polled until it changes (up to 3s)
4. Each character mapped through the keyboard layout table
5. Result written to clipboard → Ctrl+V simulated
6. Original clipboard restored after 2 seconds

**Persian layout detection**
Standard (ISIRI 9147) and Legacy layouts are auto-detected from the characters present.

---

## Repository Files

```
switex/
├── switex.py             ← Core converter (all platforms, CLI + daemon)
├── switex_tray.py        ← Windows tray app (wraps switex.py)
├── build.bat             ← Compiles Switex.exe from source (Windows, dev only)
├── setup_macos.sh        ← macOS: check deps + launch daemon
├── setup_linux.sh        ← Linux: check deps + launch daemon (X11 & Wayland)
└── README.md
```

### What goes in each GitHub Release

| File | Windows | macOS | Linux |
|------|:-------:|:-----:|:-----:|
| `Switex.exe` | ✅ download & run | — | — |
| `switex.py` | — | ✅ required | ✅ required |
| `setup_macos.sh` | — | ✅ required | — |
| `setup_linux.sh` | — | — | ✅ required |

---

## Troubleshooting

**Hotkey fires but nothing happens**
→ Make sure text is *selected* before pressing the hotkey
→ macOS: Accessibility permission must be granted (System Settings → Privacy & Security)
→ Wayland: install ydotool and confirm ydotoold is running

**Always converts in the wrong direction (FA→EN instead of EN→FA)**
→ Switch to the *target* layout before pressing the hotkey — the app uses the layout you switched *to* as the target

**Language monitor always shows EN (Windows)**
→ Switch the layout of the typing window using Win+Space or the taskbar language switcher

**xkblayout-state not in apt (Ubuntu/Debian)**
→ The setup script offers to build it from source; or manually:
```bash
git clone https://github.com/nonpop/xkblayout-state
make -C xkblayout-state
sudo cp xkblayout-state/xkblayout-state /usr/local/bin/
```

---

## Contributing

To add a new language:
1. Add the character mapping dict in the `CHARACTER MAPS` section of `switex.py`
2. Add the pair to `SUPPORTED_PAIRS` and display name to `LANG_NAMES`
3. Open a pull request

All contributions must be compatible with GPL-3.0.

---

## License

**GNU General Public License v3.0**

Copyright © 2026 [tech-tonic-coder](https://github.com/tech-tonic-coder)

Switex is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version.

Switex is distributed in the hope that it will be useful, but **without any warranty** —
without even the implied warranty of merchantability or fitness for a particular purpose.
See the [GNU General Public License](LICENSE) for more details.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

---

*Because retyping is for machines.*
