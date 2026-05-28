"""
switex - Universal Language Layout Switcher/Converter
Fully Cross-Platform (Windows, macOS, Linux).
Uses native WinEvent Hooks on Windows for 0% CPU event-driven layout tracking,
and falls back to dynamic OS layout queries on macOS/Linux for maximum compatibility.
Default fallback configuration is strictly tuned to English ('en') to maintain core autonomy.
"""

import sys
import os
import time
import threading
import logging
import subprocess
from config import MAPS

_active_listener = None

# Configure basic fallback logging safe for compiled environments
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# =============================================================================
# CROSS-PLATFORM KEYBOARD LAYOUT DETECTION & HISTORY TRACKING
# =============================================================================

_PREVIOUS_LAYOUT = 'en'
_CURRENT_LAYOUT = 'en'
_layout_lock = threading.Lock()

# Windows Hook Constants
EVENT_OBJECT_NAMECHANGE = 0x800C
WINEVENT_OUTOFCONTEXT  = 0x0000

def get_os_keyboard_layout() -> str:
    """Returns the currently active keyboard layout code for the active window."""
    platform = sys.platform
    if platform.startswith('win'):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            curr_window = user32.GetForegroundWindow()
            thread_id = user32.GetWindowThreadProcessId(curr_window, 0)
            layout_id = user32.GetKeyboardLayout(thread_id)
            primary_lang = layout_id & 0x3FF
            
            mapping = {
                0x09: 'en',  # LANG_ENGLISH
                0x29: 'fa',  # LANG_PERSIAN
                0x01: 'ar',  # LANG_ARABIC
                0x19: 'ru',  # LANG_RUSSIAN
                0x1F: 'tr',  # LANG_TURKISH
                0x0D: 'he',  # LANG_HEBREW
            }
            return mapping.get(primary_lang, 'en')
        except Exception as e:
            logging.error(f"Failed to get Windows keyboard layout: {e}")
            return 'en'
            
    elif platform == 'darwin':
        try:
            cmd = "defaults read ~/Library/Preferences/com.apple.HIToolbox.plist AppleSelectedInputSources | grep 'KeyboardLayout Name' | head -n1 | awk -F'= ' '{print $2}' | tr -d ' \";'"
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, _ = proc.communicate()
            layout_str = out.decode('utf-8').strip().lower()
            if 'persian' in layout_str or 'isiri' in layout_str: return 'fa'
            if 'arabic' in layout_str: return 'ar'
            if 'russian' in layout_str: return 'ru'
            if 'turkish' in layout_str: return 'tr'
            if 'hebrew' in layout_str: return 'he'
            return 'en'
        except Exception as e:
            logging.error(f"Failed to get macOS keyboard layout: {e}")
            return 'en'
            
    else:
        try:
            proc = subprocess.Popen(['xkb-switch', '-p'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, _ = proc.communicate()
            if proc.returncode == 0:
                layout_str = out.decode('utf-8').strip().lower()
                if 'ir' in layout_str or 'fa' in layout_str: return 'fa'
                if 'ar' in layout_str: return 'ar'
                if 'ru' in layout_str: return 'ru'
                if 'tr' in layout_str: return 'tr'
                if 'he' in layout_str: return 'he'
                return 'en'
                
            proc = subprocess.Popen(['setxkbmap', '-query'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, _ = proc.communicate()
            for line in out.decode('utf-8').split('\n'):
                if line.startswith('layout:'):
                    layouts = line.split(':')[1].strip().lower().split(',')
                    for l in layouts:
                        if l in ['ir', 'fa']: return 'fa'
                        if l == 'ar': return 'ar'
                        if l == 'ru': return 'ru'
                        if l == 'tr': return 'tr'
                        if l == 'he': return 'he'
                    return layouts[0] if layouts else 'en'
            return 'en'
        except Exception as e:
            logging.error(f"Failed to get Linux keyboard layout: {e}")
            return 'en'

def _init_event_trigger():
    """Initializes a native Windows Event Hook to track layout state transitions event-driven."""
    global _PREVIOUS_LAYOUT, _CURRENT_LAYOUT
    
    if not sys.platform.startswith('win'):
        return

    import ctypes
    from ctypes import wintypes

    initial = get_os_keyboard_layout()
    _CURRENT_LAYOUT = initial
    _PREVIOUS_LAYOUT = initial

    # Define WinEventProc Callback structure
    WinEventProcType = ctypes.WINFUNCTYPE(
        None,
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.HWND,
        wintypes.LONG,
        wintypes.LONG,
        wintypes.DWORD,
        wintypes.DWORD
    )

    def callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
        global _PREVIOUS_LAYOUT, _CURRENT_LAYOUT
        active_layout = get_os_keyboard_layout()
        
        if active_layout != _CURRENT_LAYOUT:
            with _layout_lock:
                _PREVIOUS_LAYOUT = _CURRENT_LAYOUT
                _CURRENT_LAYOUT = active_layout
                logging.info(f"Trigger Active - Layout Switched: {_PREVIOUS_LAYOUT} -> {_CURRENT_LAYOUT}")

    # Retain a global reference to prevent garbage collection of the function pointer
    global _wrapped_callback
    _wrapped_callback = WinEventProcType(callback)

    user32 = ctypes.windll.user32
    user32.SetWinEventHook(
        EVENT_OBJECT_NAMECHANGE,
        EVENT_OBJECT_NAMECHANGE,
        None,
        _wrapped_callback,
        0,
        0,
        WINEVENT_OUTOFCONTEXT
    )

    # Establish a lightweight message pump to process the asynchronous windows messages hook
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

# Only invoke the hardware event hook thread if running on Windows OS
if sys.platform.startswith('win'):
    threading.Thread(target=_init_event_trigger, daemon=True).start()

# =============================================================================
# CORE CONVERSION LOGIC
# =============================================================================

def convert(text: str, from_lang: str, to_lang: str):
    if from_lang == to_lang:
        return text, from_lang, to_lang
    mapping = MAPS.get((from_lang, to_lang))
    if not mapping:
        if from_lang != 'en' and to_lang != 'en':
            step1, _, _ = convert(text, from_lang, 'en')
            return convert(step1, 'en', to_lang)
        raise ValueError(f"No mapping found from '{from_lang}' to '{to_lang}'")
    return "".join(mapping.get(c, c) for c in text), from_lang, to_lang

def detect_lang(text: str) -> str:
    if not text: return 'en'
    fa_chars = "ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی"
    ru_chars = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    tr_chars = "çğıöşüİ"
    he_chars = "אבגדהוזחטיכלمنסעפצקרשת"

    counts = {'fa': 0, 'ru': 0, 'tr': 0, 'he': 0, 'en': 0}
    for c in text.lower():
        if c in fa_chars: counts['fa'] += 1
        elif c in ru_chars: counts['ru'] += 1
        elif c in he_chars: counts['he'] += 1
        elif 'a' <= c <= 'z': counts['en'] += 1
        elif c in tr_chars: counts['tr'] += 1

    max_lang = max(counts, key=counts.get)
    return max_lang if counts[max_lang] > 0 else 'en'

def convert_by_system_layout(text: str):
    """
    Windows: Uses hardware event triggers.
    macOS / Linux: Dynamic fallback query based on text analysis and real-time layout.
    Strictly defaults to 'en' (English) as the global fallback architecture.
    """
    # 1. Windows Path (Event-Driven Layout Switch Memory)
    if sys.platform.startswith('win'):
        with _layout_lock:
            from_lang = _PREVIOUS_LAYOUT
            to_lang = _CURRENT_LAYOUT
            
        if from_lang != to_lang:
            return convert(text, from_lang, to_lang)

    # 2. Cross-Platform Fallback Path (macOS, Linux, or Windows with no prior switch)
    target_layout = get_os_keyboard_layout()
    detected_source = detect_lang(text)
    
    # If source and target are identical (meaning user didn't switch layout or text is fully ambiguous),
    # we enforce 'en' (English) as the universal target layout, unless the source text itself is already English.
    if detected_source == target_layout:
        target_layout = 'fa' if detected_source == 'en' else 'en'
        
    return convert(text, detected_source, target_layout)

# =============================================================================
# OS IO SIMULATION
# =============================================================================

def _release_modifiers(kb) -> None:
    from pynput.keyboard import Key
    for key in [Key.ctrl, Key.shift, Key.alt, Key.cmd, Key.ctrl_l, Key.ctrl_r, Key.alt_l, Key.alt_r, Key.shift_l, Key.shift_r]:
        try: kb.release(key)
        except Exception: pass

def _simulate_copy() -> None:
    from pynput.keyboard import Controller, Key
    kb = Controller()
    _release_modifiers(kb)
    time.sleep(0.05)
    with kb.pressed(Key.ctrl):
        kb.press('c')
        kb.release('c')
    time.sleep(0.12)

def _simulate_paste() -> None:
    from pynput.keyboard import Controller, Key
    kb = Controller()
    _release_modifiers(kb)
    time.sleep(0.05)
    with kb.pressed(Key.ctrl):
        kb.press('v')
        kb.release('v')
    time.sleep(0.1)

def _delayed_restore_clipboard(backup_text: str, delay: float = 0.6) -> None:
    def _task():
        time.sleep(delay)
        import pyperclip
        try:
            pyperclip.copy(backup_text)
        except Exception as e:
            logging.error(f"Clipboard restoration deferred task failed: {e}")
    threading.Thread(target=_task, daemon=True).start()

# =============================================================================
# ENGINE DAEMON
# =============================================================================

def run_daemon(hotkey_str: str) -> None:
    import pyperclip
    from pynput import keyboard

    work_q = []
    work_lock = threading.Lock()

    def worker_loop():
        while True:
            with work_lock:
                if not work_q:
                    time.sleep(0.04)
                    continue
                action = work_q.pop(0)
            try: 
                action()
            except Exception as e:
                logging.error(f"Error executing queued action: {e}", exc_info=True)

    threading.Thread(target=worker_loop, daemon=True).start()

    def handle_conversion(convert_func):
        try:
            backup = pyperclip.paste() or ''
            _simulate_copy()
            
            start = time.monotonic()
            selected = backup
            while time.monotonic() - start < 0.4:
                selected = pyperclip.paste() or ''
                if selected != backup:
                    break
                time.sleep(0.04)

            if selected == backup or not selected.strip():
                pyperclip.copy(backup)
                return

            res, _, _ = convert_func(selected)
            pyperclip.copy(res)
            _simulate_paste()
            _delayed_restore_clipboard(backup)
        except Exception as e:
            logging.error(f"Layout transformation pipeline failed: {e}", exc_info=True)

    def with_lock_enqueue(action):
        with work_lock: work_q.append(action)

    hotkeys = {
        hotkey_str: lambda: with_lock_enqueue(lambda: handle_conversion(convert_by_system_layout)),
        '<ctrl>+<shift>+<alt>+f': lambda: with_lock_enqueue(lambda: handle_conversion(lambda t: convert(t, detect_lang(t), 'fa'))),
        '<ctrl>+<shift>+<alt>+e': lambda: with_lock_enqueue(lambda: handle_conversion(lambda t: convert(t, detect_lang(t), 'en'))),
        '<ctrl>+<shift>+<alt>+a': lambda: with_lock_enqueue(lambda: handle_conversion(lambda t: convert(t, detect_lang(t), 'ar'))),
        '<ctrl>+<shift>+<alt>+r': lambda: with_lock_enqueue(lambda: handle_conversion(lambda t: convert(t, detect_lang(t), 'ru'))),
        '<ctrl>+<shift>+<alt>+t': lambda: with_lock_enqueue(lambda: handle_conversion(lambda t: convert(t, detect_lang(t), 'tr'))),
        '<ctrl>+<shift>+<alt>+h': lambda: with_lock_enqueue(lambda: handle_conversion(lambda t: convert(t, detect_lang(t), 'he'))),
    }

    global _active_listener
    try:
        with keyboard.GlobalHotKeys(hotkeys) as h:
            _active_listener = h
            h.join()
    except Exception as e:
        logging.critical(f"GlobalHotKeys listener thread crashed: {e}", exc_info=True)
    finally:
        _active_listener = None