"""
Switex — System Tray Application (Windows)
===========================================
Bundles switex.py into a single .exe via PyInstaller.
Right-click the tray icon to Start / Stop / Restart / Status / Exit.

Build with:  build.bat
"""

import sys
import os
import threading
import queue
import time
import ctypes
import subprocess

# ── Resolve paths relative to the .exe / script itself ───────────────────────
if getattr(sys, 'frozen', False):
    # Running as compiled .exe (PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
    # switex.py is bundled inside the PyInstaller archive — we extract it
    # to a temp location so it can be imported as a module.
    import tempfile, importlib, types

    def _load_bundled_switex():
        """Load switex module from PyInstaller bundle."""
        import importlib.util
        # PyInstaller puts bundled data in sys._MEIPASS
        bundled = os.path.join(sys._MEIPASS, 'switex.py')
        spec = importlib.util.spec_from_file_location('switex', bundled)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['switex'] = mod
        return mod

    switex = _load_bundled_switex()
else:
    # Running as plain .py script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, BASE_DIR)
    import switex

LOG_FILE  = os.path.join(BASE_DIR, 'switex.log')
HOTKEY    = '<ctrl>+<alt>+<space>'
APP_NAME  = 'Switex'

# ── Tray icon image (generated, no external file needed) ──────────────────────
def _make_icon(running: bool):
    """
    Generate a simple tray icon using Pillow.
    Green keyboard symbol = running, grey = stopped.
    """
    from PIL import Image, ImageDraw, ImageFont
    size = 64
    img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    color = (40, 180, 40, 255) if running else (120, 120, 120, 255)
    draw.ellipse([2, 2, size - 2, size - 2], fill=color)

    # "S" letter for Switex
    # Use default font — no external font file needed
    try:
        font = ImageFont.truetype('arialbd.ttf', 36)
    except Exception:
        try:
            font = ImageFont.truetype('arial.ttf', 36)
        except Exception:
            font = ImageFont.load_default()

    text = 'S'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
              text, font=font, fill=(255, 255, 255, 255))
    return img


# ── Daemon thread management ──────────────────────────────────────────────────
_daemon_thread: threading.Thread | None = None
_daemon_stop_event = threading.Event()
_status_queue: queue.Queue = queue.Queue()


def _daemon_is_alive() -> bool:
    return _daemon_thread is not None and _daemon_thread.is_alive()


def _run_daemon_thread():
    """Run switex daemon in a background thread."""
    _daemon_stop_event.clear()
    try:
        switex._log_file = LOG_FILE
        switex.run_daemon(HOTKEY, None, None)
    except Exception as e:
        _status_queue.put(('error', str(e)))


def start_daemon():
    global _daemon_thread
    if _daemon_is_alive():
        return False  # already running
    _daemon_thread = threading.Thread(target=_run_daemon_thread, daemon=True)
    _daemon_thread.start()
    time.sleep(0.5)
    return _daemon_thread.is_alive()


def stop_daemon():
    """Stop the daemon cleanly via pynput listener .stop() or KeyboardInterrupt."""
    global _daemon_thread
    if not _daemon_is_alive():
        return

    # Preferred: call pynput listener's own .stop() method
    listener = getattr(switex, '_active_listener', None)
    if listener is not None:
        try:
            listener.stop()
            switex._active_listener = None
        except Exception:
            pass

    # Fallback: raise KeyboardInterrupt in the daemon thread
    # (caught by the except KeyboardInterrupt in run_daemon)
    if _daemon_is_alive() and _daemon_thread and _daemon_thread.ident:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(_daemon_thread.ident),
            ctypes.py_object(KeyboardInterrupt)
        )

    if _daemon_thread:
        _daemon_thread.join(timeout=2.0)
    _daemon_thread = None


# ── Tray application ──────────────────────────────────────────────────────────
def _build_menu(tray_icon):
    """Build the right-click tray menu based on current state."""
    import pystray
    running = _daemon_is_alive()

    def on_start(icon, item):
        if not _daemon_is_alive():
            ok = start_daemon()
            icon.icon  = _make_icon(True)
            icon.title = f'{APP_NAME} — Running'
            _notify(icon, 'Switex Started',
                    f'Hotkey active: Ctrl+Alt+Space\nLog: {LOG_FILE}' if ok
                    else 'Failed to start. Check switex.log')
            icon.menu = _build_menu(icon)

    def on_stop(icon, item):
        if _daemon_is_alive():
            stop_daemon()
            icon.icon  = _make_icon(False)
            icon.title = f'{APP_NAME} — Stopped'
            _notify(icon, 'Switex Stopped', 'Hotkey daemon is no longer active.')
            icon.menu = _build_menu(icon)

    def on_restart(icon, item):
        stop_daemon()
        time.sleep(0.3)
        ok = start_daemon()
        icon.icon  = _make_icon(True)
        icon.title = f'{APP_NAME} — Running'
        _notify(icon, 'Switex Restarted',
                'Hotkey daemon restarted.' if ok else 'Restart failed. Check switex.log')
        icon.menu = _build_menu(icon)

    def on_status(icon, item):
        if _daemon_is_alive():
            _notify(icon, 'Switex — Running',
                    f'Hotkey: Ctrl+Alt+Space\nLog: {LOG_FILE}')
        else:
            _notify(icon, 'Switex — Stopped',
                    'Daemon is not running. Click Start to activate.')

    def on_open_log(icon, item):
        if os.path.exists(LOG_FILE):
            os.startfile(LOG_FILE)
        else:
            _notify(icon, 'No log file yet',
                    'Log file will be created when the daemon starts.')

    def on_exit(icon, item):
        stop_daemon()
        icon.stop()

    status_label = '● Running' if running else '○ Stopped'

    return pystray.Menu(
        pystray.MenuItem(f'{APP_NAME}  {status_label}',
                         None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Start',   on_start,   enabled=not running),
        pystray.MenuItem('Stop',    on_stop,    enabled=running),
        pystray.MenuItem('Restart', on_restart, enabled=running),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Status',   on_status),
        pystray.MenuItem('Open Log', on_open_log),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Exit', on_exit),
    )


def _notify(icon, title: str, message: str):
    """Show a Windows balloon notification."""
    try:
        icon.notify(message, title)
    except Exception:
        pass  # notifications not critical


def _check_already_running() -> bool:
    """Use a Windows named mutex to prevent multiple instances."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, 'SwitexTrayMutex')
    err   = ctypes.windll.kernel32.GetLastError()
    return err == 183  # ERROR_ALREADY_EXISTS


def main():
    import pystray

    # Single instance guard
    if _check_already_running():
        ctypes.windll.user32.MessageBoxW(
            0,
            'Switex is already running in the system tray.\n\n'
            'Look for the  S  icon in your taskbar notification area.',
            'Switex',
            0x40  # MB_ICONINFORMATION
        )
        sys.exit(0)

    # Auto-start daemon on launch
    start_daemon()
    running = _daemon_is_alive()

    icon = pystray.Icon(
        name=APP_NAME,
        icon=_make_icon(running),
        title=f'{APP_NAME} — {"Running" if running else "Stopped"}',
    )
    icon.menu = _build_menu(icon)

    # Show startup notification
    def _on_setup(icon):
        icon.visible = True
        if running:
            _notify(icon, 'Switex Started',
                    'Hotkey active: Ctrl+Alt+Space\n'
                    'Right-click the tray icon for options.')
        else:
            _notify(icon, 'Switex — Could Not Start',
                    'Check that pynput and pyperclip are installed.\n'
                    f'Log: {LOG_FILE}')

    icon.run(_on_setup)


if __name__ == '__main__':
    main()
