"""
Switex — System Tray Application (Windows)
===========================================
Compatible with both PyInstaller and Nuitka compilers.
Handles UI/UX Tray icon, interactive submenus, real-time language hot-swapping,
Windows AUMID identity for Toast Notifications with Icons, and manages the daemon.
"""

import sys
import os
import threading
import queue
import time
import ctypes
import ctypes.wintypes as _wt
from config import LOCALIZED_STRINGS

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    if hasattr(sys, '_MEIPASS'):
        INTERNAL_DIR = sys._MEIPASS
    elif '__compiled__' in globals():
        INTERNAL_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else BASE_DIR
    else:
        INTERNAL_DIR = BASE_DIR
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    INTERNAL_DIR = BASE_DIR

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
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
    sys.path.insert(0, INTERNAL_DIR)
    import switex

LOG_FILE  = os.path.join(BASE_DIR, 'switex.log')
HOTKEY    = '<ctrl>+<shift>+<alt>+<space>'
APP_NAME  = 'Switex'
APP_AUMID = 'Switex.App'

_STARTUP_REG_KEY  = r'Software\Microsoft\Windows\CurrentVersion\Run'
_STARTUP_REG_NAME = 'Switex'

CURRENT_LANG = 'en'  

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
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _STARTUP_REG_NAME, 0, winreg.REG_SZ, f'"{exe}"')
        return True
    except Exception:
        return False

def disable_startup() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _STARTUP_REG_NAME)
        return True
    except Exception:
        return False

def _resolve_ico_path() -> str | None:
    paths = [
        os.path.join(INTERNAL_DIR, 'switex.ico'),
        os.path.join(BASE_DIR, 'switex.ico'),
    ]
    for p in paths:
        if os.path.exists(p):
            return os.path.abspath(p)
    return None

def _make_icon(running: bool):
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
    from PIL import Image, ImageDraw, ImageFont
    size = 64
    img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (34, 160, 54, 255) if running else (120, 120, 120, 255)
    draw.ellipse([2, 2, size - 2, size - 2], fill=color)
    try:
        font = ImageFont.truetype('arialbd.ttf', 36)
    except Exception:
        font = ImageFont.load_default()
    text = 'S'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), text, font=font, fill=(255, 255, 255, 255))
    return img

def _setup_app_identity() -> None:
    if not sys.platform.startswith('win'):
        return
    try:
        import winreg
        ico_path = _resolve_ico_path() or ''
        exe_path = _get_exe_path()  # ← اضافه کنید
        key_path = rf'Software\Classes\AppUserModelId\{APP_AUMID}'
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, 'DisplayName',         0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(key, 'IconUri',             0, winreg.REG_SZ, ico_path)
            winreg.SetValueEx(key, 'IconBackgroundColor', 0, winreg.REG_SZ, '00000000')
            winreg.SetValueEx(key, 'CustomActivator',     0, winreg.REG_SZ, exe_path)
    except Exception:
        pass

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_AUMID)
    except Exception:
        pass

_toaster = None

def _get_toaster():
    global _toaster
    if _toaster is None:
        try:
            from windows_toasts import InteractableWindowsToaster
            _toaster = InteractableWindowsToaster(APP_NAME, notifierAUMID=APP_AUMID)
        except Exception:
            _toaster = False
    return _toaster if _toaster else None

def _notify(icon, title_key: str, message_key: str, **kwargs) -> None:
    title = LOCALIZED_STRINGS[CURRENT_LANG].get(title_key, title_key)
    msg = LOCALIZED_STRINGS[CURRENT_LANG].get(message_key, message_key).format(**kwargs)
    
    try:
        from windows_toasts import Toast
        toaster = _get_toaster()
        if toaster is None:
            raise RuntimeError()
        t = Toast(text_fields=[title, msg])
        toaster.show_toast(t)
    except Exception:
        try:
            icon.notify(msg, title)
        except Exception:
            pass

_daemon_thread: threading.Thread | None = None

def _daemon_is_alive() -> bool:
    return _daemon_thread is not None and _daemon_thread.is_alive()

def _run_daemon_thread():
    try:
        switex.run_daemon(HOTKEY)
    except Exception:
        pass

def start_daemon():
    global _daemon_thread
    if _daemon_is_alive():
        return False
    _daemon_thread = threading.Thread(target=_run_daemon_thread, daemon=True)
    _daemon_thread.start()
    time.sleep(0.2)
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
    if _daemon_thread:
        _daemon_thread.join(timeout=1.5)
    _daemon_thread = None

def on_start(icon, item):
    if not _daemon_is_alive():
        start_daemon()
        icon.icon = _make_icon(True)
        icon.title = f"{APP_NAME} — {LOCALIZED_STRINGS[CURRENT_LANG].get('status_running')}"
        _notify(icon, 'notif_start_title', 'notif_start_msg', hk='Ctrl+Shift+Alt+Space')
        _safe_refresh_menu(icon)

def on_stop(icon, item):
    if _daemon_is_alive():
        stop_daemon()
        icon.icon = _make_icon(False)
        icon.title = f"{APP_NAME} — {LOCALIZED_STRINGS[CURRENT_LANG].get('status_stopped')}"
        _notify(icon, 'notif_stop_title', 'notif_stop_msg')
        _safe_refresh_menu(icon)

def on_toggle_startup(icon, item):
    if is_startup_enabled():
        if disable_startup():
            _notify(icon, 'menu_startup', 'notif_startup_dis')
    else:
        if enable_startup():
            _notify(icon, 'menu_startup', 'notif_startup_en')
    _safe_refresh_menu(icon)

def on_open_log(icon, item):
    try:
        if os.path.exists(LOG_FILE):
            os.startfile(LOG_FILE)
    except Exception:
        pass

def on_exit(icon, item):
    stop_daemon()
    icon.stop()

def set_lang(lang_code):
    def _callback(icon, item):
        global CURRENT_LANG
        if CURRENT_LANG != lang_code:
            CURRENT_LANG = lang_code
            _notify(icon, 'notif_lang_title', 'notif_lang_msg')
            icon.title = f"{APP_NAME} — {(LOCALIZED_STRINGS[CURRENT_LANG].get('status_running') if _daemon_is_alive() else LOCALIZED_STRINGS[CURRENT_LANG].get('status_stopped'))}"
            _safe_refresh_menu(icon)
    return _callback

def _safe_refresh_menu(icon):
    icon.menu = _build_menu(icon)

def _get_txt(key: str) -> str:
    return LOCALIZED_STRINGS[CURRENT_LANG].get(key, key)

def _build_menu(tray_icon):
    import pystray
    running = _daemon_is_alive()
    startup_on = is_startup_enabled()
    
    startup_label = f"{_get_txt('menu_startup')}  ✓" if startup_on else _get_txt('menu_startup')
    status_label = _get_txt('status_running') if running else _get_txt('status_stopped')

    language_submenu = pystray.Menu(
        pystray.MenuItem(f"English {' ✓' if CURRENT_LANG == 'en' else ''}", set_lang('en')),
        pystray.MenuItem(f"فارسی {' ✓' if CURRENT_LANG == 'fa' else ''}", set_lang('fa'))
    )

    if CURRENT_LANG == 'fa':
        guide_submenu = pystray.Menu(
            pystray.MenuItem("۱. متن اشتباه تایپ‌شده (Mistyped) خود را انتخاب کنید.", None, enabled=False),
            pystray.MenuItem("۲. اگر می‌خواهید از میانبر عمومی (Ctrl+Shift+Alt+Space) استفاده کنید:", None, enabled=False),
            pystray.MenuItem("   - ابتدا زبان کیبورد سیستم را به زبان مقصد تغییر دهید.", None, enabled=False),
            pystray.MenuItem("   - در غیر این صورت (میانبرهای اختصاصی) نیازی به این مرحله نیست.", None, enabled=False),
            pystray.MenuItem("۳. در نهایت، میانبر مربوطه را بفشارید.", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("--- لیست میانبرها ---", None, enabled=False),
            pystray.MenuItem("عمومی: Ctrl + Shift + Alt + Space", None, enabled=False),
            pystray.MenuItem("اختصاصی: Ctrl + Shift + Alt + F  ->  فارسی (FA)", None, enabled=False),
            pystray.MenuItem("اختصاصی: Ctrl + Shift + Alt + E  ->  انگلیسی (EN)", None, enabled=False),
            pystray.MenuItem("اختصاصی: Ctrl + Shift + Alt + A  ->  عربی (AR)", None, enabled=False),
            pystray.MenuItem("اختصاصی: Ctrl + Shift + Alt + R  ->  روسی (RU)", None, enabled=False),
            pystray.MenuItem("اختصاصی: Ctrl + Shift + Alt + T  ->  ترکی (TR)", None, enabled=False),
            pystray.MenuItem("اختصاصی: Ctrl + Shift + Alt + H  ->  عبری (HE)", None, enabled=False),
        )
    else:
        guide_submenu = pystray.Menu(
            pystray.MenuItem("1. Select (Highlight) your mistyped text.", None, enabled=False),
            pystray.MenuItem("2. If you want to use the Global Shortcut (Ctrl+Shift+Alt+Space):", None, enabled=False),
            pystray.MenuItem("   - Change system keyboard layout to target language first.", None, enabled=False),
            pystray.MenuItem("   - Otherwise (Dedicated Shortcuts), skip this step.", None, enabled=False),
            pystray.MenuItem("3. Press the corresponding shortcut keys.", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("--- Shortcuts List ---", None, enabled=False),
            pystray.MenuItem("Global: Ctrl + Shift + Alt + Space", None, enabled=False),
            pystray.MenuItem("Dedicated: Ctrl + Shift + Alt + F  ->  Persian (FA)", None, enabled=False),
            pystray.MenuItem("Dedicated: Ctrl + Shift + Alt + E  ->  English (EN)", None, enabled=False),
            pystray.MenuItem("Dedicated: Ctrl + Shift + Alt + A  ->  Arabic (AR)", None, enabled=False),
            pystray.MenuItem("Dedicated: Ctrl + Shift + Alt + R  ->  Russian (RU)", None, enabled=False),
            pystray.MenuItem("Dedicated: Ctrl + Shift + Alt + T  ->  Turkish (TR)", None, enabled=False),
            pystray.MenuItem("Dedicated: Ctrl + Shift + Alt + H  ->  Hebrew (HE)", None, enabled=False),
        )

    return pystray.Menu(
        pystray.MenuItem(f"{APP_NAME}  {status_label}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_get_txt('menu_start'), on_start, enabled=not running),
        pystray.MenuItem(_get_txt('menu_stop'), on_stop, enabled=running),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(startup_label, on_toggle_startup),
        pystray.MenuItem(_get_txt('menu_lang'), language_submenu),
        pystray.MenuItem(_get_txt('menu_shortcuts'), guide_submenu),
        pystray.MenuItem('Open Log', on_open_log),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_get_txt('menu_exit'), on_exit),
    )

def _check_already_running() -> bool:
    if not sys.platform.startswith('win'):
        return False
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, 'SwitexTrayMutex')
    return ctypes.windll.kernel32.GetLastError() == 183

def main():
    import pystray
    if _check_already_running():
        if sys.platform.startswith('win'):
            ctypes.windll.user32.MessageBoxW(0, 'Switex is already running in the system tray.', 'Switex', 0x40)
        sys.exit(0)

    _setup_app_identity()
    start_daemon()
    running = _daemon_is_alive()

    icon = pystray.Icon(
        name=APP_NAME,
        icon=_make_icon(running),
        title=f"{APP_NAME} — {(_get_txt('status_running') if running else _get_txt('status_stopped'))}",
    )
    
    icon.menu = _build_menu(icon)

    def _on_ready(i):
        i.visible = True
        def _delayed_notify():
            time.sleep(0.8)
            if _daemon_is_alive():
                _notify(i, 'notif_start_title', 'notif_start_msg', hk='Ctrl+Shift+Alt+Space')
        threading.Thread(target=_delayed_notify, daemon=True).start()

    icon.run(setup=_on_ready)

if __name__ == '__main__':
    main()