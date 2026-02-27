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
import ctypes.wintypes as _wt

# ── Resolve paths relative to the .exe / script itself ───────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)

    def _load_bundled_switex():
        import importlib.util
        bundled = os.path.join(sys._MEIPASS, 'switex.py')
        spec = importlib.util.spec_from_file_location('switex', bundled)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['switex'] = mod
        return mod

    switex = _load_bundled_switex()
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, BASE_DIR)
    import switex

LOG_FILE  = os.path.join(BASE_DIR, 'switex.log')
HOTKEY    = '<ctrl>+<alt>+<space>'
APP_NAME  = 'Switex'
APP_AUMID = 'Switex.App'   # App User Model ID used for WinRT toast notifications

# Registry key for Windows startup
_STARTUP_REG_KEY  = r'Software\Microsoft\Windows\CurrentVersion\Run'
_STARTUP_REG_NAME = 'Switex'


# ── Windows startup helpers ───────────────────────────────────────────────────

def _get_exe_path() -> str:
    if getattr(sys, 'frozen', False):
        return sys.executable
    return os.path.abspath(__file__)


def is_startup_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY) as key:
            val, _ = winreg.QueryValueEx(key, _STARTUP_REG_NAME)
            return os.path.normcase(val.strip('"')) == os.path.normcase(_get_exe_path())
    except Exception:
        return False


def enable_startup() -> bool:
    try:
        import winreg
        exe = _get_exe_path()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY,
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _STARTUP_REG_NAME, 0, winreg.REG_SZ, f'"{exe}"')
        return True
    except Exception:
        return False


def disable_startup() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY,
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _STARTUP_REG_NAME)
        return True
    except Exception:
        return False


# ── Icon helpers ──────────────────────────────────────────────────────────────

def _resolve_ico_path() -> str | None:
    """Return path to switex.ico: beside the exe first, then _MEIPASS bundle."""
    p = os.path.join(BASE_DIR, 'switex.ico')
    if os.path.exists(p):
        return p
    if getattr(sys, 'frozen', False):
        p = os.path.join(sys._MEIPASS, 'switex.ico')
        if os.path.exists(p):
            return p
    return None


def _make_icon(running: bool):
    """Load switex.ico for the tray. Greyscale when stopped. Falls back to generated."""
    from PIL import Image
    ico_path = _resolve_ico_path()
    if ico_path:
        try:
            img = Image.open(ico_path).convert('RGBA')
            img = img.resize((64, 64), Image.LANCZOS)
            if not running:
                import PIL.ImageEnhance as _enh
                img = _enh.Color(img).enhance(0.0)
                img = _enh.Brightness(img).enhance(0.75)
            return img
        except Exception:
            pass
    return _make_icon_generated(running)


def _make_icon_generated(running: bool):
    """Fallback generated tray icon."""
    from PIL import Image, ImageDraw, ImageFont
    size = 64
    img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (40, 180, 40, 255) if running else (120, 120, 120, 255)
    draw.ellipse([2, 2, size - 2, size - 2], fill=color)
    try:
        font = ImageFont.truetype('arialbd.ttf', 36)
    except Exception:
        try:
            font = ImageFont.truetype('arial.ttf', 36)
        except Exception:
            font = ImageFont.load_default()
    text = 'S'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
              text, font=font, fill=(255, 255, 255, 255))
    return img


# ── AUMID registration + process identity ────────────────────────────────────

def _setup_app_identity() -> None:
    """
    Two steps are both required to make Windows show "Switex" (not "Switex.exe")
    and the correct custom icon in toast notifications:

    1. Registry entry under HKCU\Software\Classes\AppUserModelId\Switex.App
       Sets DisplayName and IconUri — Windows reads these when rendering the toast.

    2. SetCurrentProcessExplicitAppUserModelID — binds the running process to the
       AUMID so WinRT picks up the registry entry for this process.

    No admin rights needed (HKCU only).
    """
    # Step 1: registry
    try:
        import winreg
        ico_path = _resolve_ico_path() or ''
        key_path = rf'Software\Classes\AppUserModelId\{APP_AUMID}'
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path,
                                0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, 'DisplayName',         0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(key, 'IconUri',             0, winreg.REG_SZ, ico_path)
            winreg.SetValueEx(key, 'IconBackgroundColor', 0, winreg.REG_SZ, '00000000')
    except Exception:
        pass

    # Step 2: bind process to AUMID
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_AUMID)
    except Exception:
        pass


# ── Notification ──────────────────────────────────────────────────────────────

_toaster = None   # cached so WinRT is only initialised once

def _get_toaster():
    global _toaster
    if _toaster is None:
        try:
            from windows_toasts import InteractableWindowsToaster
            _toaster = InteractableWindowsToaster(APP_NAME, notifierAUMID=APP_AUMID)
        except Exception:
            _toaster = False
    return _toaster if _toaster else None


def _notify(icon, title: str, message: str) -> None:
    """
    Send a Windows toast notification via WinRT (windows-toasts).
    Using InteractableWindowsToaster + our AUMID causes Windows to display:
      • "Switex" as the app name (not "Switex.exe")
      • our custom icon from the registry IconUri
    Falls back to pystray's built-in notify if windows-toasts is unavailable.
    """
    try:
        from windows_toasts import Toast
        toaster = _get_toaster()
        if toaster is None:
            raise RuntimeError('windows-toasts unavailable')
        t = Toast(text_fields=[title, message])
        toaster.show_toast(t)
    except Exception:
        try:
            icon.notify(message, title)
        except Exception:
            pass


# ── Daemon thread management ──────────────────────────────────────────────────
_daemon_thread: threading.Thread | None = None
_daemon_stop_event = threading.Event()
_status_queue: queue.Queue = queue.Queue()


def _daemon_is_alive() -> bool:
    return _daemon_thread is not None and _daemon_thread.is_alive()


def _run_daemon_thread():
    _daemon_stop_event.clear()
    try:
        switex._log_file = LOG_FILE
        switex.run_daemon(HOTKEY, None, None)
    except Exception as e:
        _status_queue.put(('error', str(e)))


def start_daemon():
    global _daemon_thread
    if _daemon_is_alive():
        return False
    _daemon_thread = threading.Thread(target=_run_daemon_thread, daemon=True)
    _daemon_thread.start()
    time.sleep(0.5)
    return _daemon_thread.is_alive()


def stop_daemon():
    global _daemon_thread
    if not _daemon_is_alive():
        return

    listener = getattr(switex, '_active_listener', None)
    if listener is not None:
        try:
            listener.stop()
            switex._active_listener = None
        except Exception:
            pass

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
    import pystray
    running       = _daemon_is_alive()
    startup_on    = is_startup_enabled()
    startup_label = 'Run at Startup  ✓' if startup_on else 'Run at Startup'

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

    def on_toggle_startup(icon, item):
        if is_startup_enabled():
            ok = disable_startup()
            _notify(icon, 'Startup Disabled',
                    'Switex will no longer start with Windows.' if ok
                    else 'Failed to remove startup entry.')
        else:
            ok = enable_startup()
            _notify(icon, 'Startup Enabled',
                    'Switex will now start automatically with Windows.' if ok
                    else 'Failed to add startup entry.')
        icon.menu = _build_menu(icon)

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
        pystray.MenuItem(f'{APP_NAME}  {status_label}', None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Start',   on_start,   enabled=not running),
        pystray.MenuItem('Stop',    on_stop,    enabled=running),
        pystray.MenuItem('Restart', on_restart, enabled=running),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Status',      on_status),
        pystray.MenuItem(startup_label, on_toggle_startup),
        pystray.MenuItem('Open Log',    on_open_log),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Exit', on_exit),
    )


def _check_already_running() -> bool:
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, 'SwitexTrayMutex')
    err   = ctypes.windll.kernel32.GetLastError()
    return err == 183


def main():
    import pystray

    if _check_already_running():
        ctypes.windll.user32.MessageBoxW(
            0,
            'Switex is already running in the system tray.\n\n'
            'Look for the  S  icon in your taskbar notification area.',
            'Switex',
            0x40
        )
        sys.exit(0)

    # Register AUMID so Windows uses our icon in toast notifications
    _setup_app_identity()

    start_daemon()
    running = _daemon_is_alive()

    icon = pystray.Icon(
        name=APP_NAME,
        icon=_make_icon(running),
        title=f'{APP_NAME} — {"Running" if running else "Stopped"}',
    )
    icon.menu = _build_menu(icon)

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
