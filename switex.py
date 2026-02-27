#!/usr/bin/env python3
"""
Switex — Switch + Text Keyboard Layout Converter
==========================================
Converts text typed in the wrong keyboard layout to the correct one.
Runs on Windows, macOS, and Linux. No GUI. No framework.

MODES
-----
1. CLI (pipe / args):
       echo "sghl" | switex                     # auto-detect
       echo "sghl" | switex -f en -t fa         # explicit
       switex -f en -t ru "ghbdtn"              # inline text
       switex --list                             # show language pairs

2. Clipboard mode (one-shot):
       switex --clipboard                       # convert clipboard contents
       switex --clipboard -f en -t fa           # explicit direction

3. Daemon (global hotkey):
       switex --daemon                          # Ctrl+Alt+Space
       switex --daemon --hotkey "<ctrl>+<alt>+z"
       pythonw switex.py --daemon --log C:\\switex.log

   While daemon runs:
   - Switch your keyboard to the target language (e.g. FA)
   - Select the mistyped text in any app
   - Press the hotkey
   - The app detects the language switch automatically and converts

REQUIREMENTS
------------
  Core (CLI):     Python 3.7+  — zero extra packages
  Daemon mode:    pip install pynput pyperclip
  Clipboard mode: pip install pyperclip

SUPPORTED PAIRS
---------------
  EN ↔ FA  (Persian/Farsi — Standard & Legacy layouts)
  EN ↔ AR  (Arabic)
  EN ↔ RU  (Russian)
  EN ↔ TR  (Turkish)
  EN ↔ HE  (Hebrew)

DAEMON SAFETY NOTES
-------------------
  The daemon uses pynput.GlobalHotKeys on all platforms.
  On Windows, if pynput is not available, it falls back to RegisterHotKey.
  The hotkey callback NEVER does clipboard/key work directly — it always
  dispatches to a worker thread so the OS hotkey handler returns instantly.
  This prevents keyboard lockups.
"""

import sys
import os
import argparse
import threading
import time

# =============================================================================
# CHARACTER MAPS
# =============================================================================

def _rev(d: dict) -> dict:
    """Reverse a char→char mapping, first-seen wins on collisions."""
    r = {}
    for k, v in d.items():
        if v not in r:
            r[v] = k
    return r


def _zip(src: str, dst: str) -> dict:
    return {s: d for s, d in zip(src, dst)}


# ── Persian Standard ──────────────────────────────────────────────────────────
_EN_FA_STD: dict = {
    '`': '\u200D',
    '1':'۱','2':'۲','3':'۳','4':'۴','5':'۵',
    '6':'۶','7':'۷','8':'۸','9':'۹','0':'۰',
    '-':'-', '=':'=',
    '~':'÷','!':'!','@':'٬','#':'٫','$':'﷼',
    '%':'٪','^':'×','&':'،','*':'*',
    '(':')',')':'(','_':'ـ','+':'+',
    'q':'ض','w':'ص','e':'ث','r':'ق','t':'ف',
    'y':'غ','u':'ع','i':'ه','o':'خ','p':'ح',
    '[':'ج',']':'چ',
    'Q':'ْ','W':'ٌ','E':'ٍ','R':'ً','T':'ُ',
    'Y':'ِ','U':'َ','I':'ّ','O':']','P':'[',
    '{':'}','}':'{',
    'a':'ش','s':'س','d':'ی','f':'ب','g':'ل',
    'h':'ا','j':'ت','k':'ن','l':'م',';':'ک',"'":'گ',
    'A':'ؤ','S':'ئ','D':'ي','F':'إ','G':'أ',
    'H':'آ','J':'ة','K':'»','L':'«',':':':','"':'؛',
    'z':'ظ','x':'ط','c':'ز','v':'ر','b':'ذ',
    'n':'د','m':'پ',',':'و','.':'.','/'  :'/',
    'Z':'ك','X':'ٓ','C':'ژ','V':'ٰ','B':'\u200C',
    'N':'ٔ','M':'ء','<':'>','>':'<','?':'؟',
    '\\'  :'\\','|':'|',' ':' ','\n':'\n','\t':'\t',
}

_EN_FA_LEG: dict = {**_EN_FA_STD, '\\'  :'ژ'}

# ── Arabic ────────────────────────────────────────────────────────────────────
_EN_AR: dict = {
    **_zip('1234567890-=', '١٢٣٤٥٦٧٨٩٠-='),
    **_zip('qwertyuiop[]\\'  , 'ضصثقفغعهخحجد\\'  ),
    **_zip("asdfghjkl;'",   'شسيبلاتنمكط'),
    **_zip('zxcvbnm,./',    'ئءؤرىةوز,.'),
    '`':'ذ', '~':'ّ', ' ':' ', '\n':'\n', '\t':'\t',
}

# ── Russian ───────────────────────────────────────────────────────────────────
_EN_RU: dict = {
    **_zip('qwertyuiop[]\\'  , 'йцукенгшщзхъ\\'  ),
    **_zip("asdfghjkl;'",   'фывапролджэ'),
    **_zip('zxcvbnm,./',    'ячсмитьбю.'),
    **_zip('QWERTYUIOP{}|', 'ЙЦУКЕНГШЩЗХЪ|'),
    **_zip('ASDFGHJKL:"',   'ФЫВАПРОЛДЖЭ'),
    **_zip('ZXCVBNM<>?',    'ЯЧСМИТЬБЮ,'),
    **_zip('1234567890-=',  '1234567890-='),
    ' ':' ', '\n':'\n', '\t':'\t',
}

# ── Turkish ───────────────────────────────────────────────────────────────────
_EN_TR: dict = {
    **_zip('abcdefghijklmnopqrstuvwxyz',
           'abcçdefgğhıijklmnoöprsştuüvyz'),
    **_zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',
           'ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ'),
    **_zip('1234567890-=', '1234567890-='),
    ' ':' ', '\n':'\n', '\t':'\t',
}

# ── Hebrew ────────────────────────────────────────────────────────────────────
_EN_HE: dict = {
    **_zip('qwertyuiop',  'קואבטיחיפ'),
    **_zip('asdfghjkl;',  'שדגכעיחלפ'),
    **_zip('zxcvbnm',     'זסבנהצמ'),
    **_zip('1234567890',  '1234567890'),
    ' ':' ', '\n':'\n', '\t':'\t',
}

_MAPS: dict = {
    ('en', 'fa'):     (_EN_FA_STD, _rev(_EN_FA_STD)),
    ('en', 'fa_leg'): (_EN_FA_LEG, _rev(_EN_FA_LEG)),
    ('en', 'ar'):     (_EN_AR,     _rev(_EN_AR)),
    ('en', 'ru'):     (_EN_RU,     _rev(_EN_RU)),
    ('en', 'tr'):     (_EN_TR,     _rev(_EN_TR)),
    ('en', 'he'):     (_EN_HE,     _rev(_EN_HE)),
}

# Tray app can set this to stop the listener cleanly
_active_listener = None

SUPPORTED_PAIRS = [
    ('en', 'fa'), ('fa', 'en'),
    ('en', 'ar'), ('ar', 'en'),
    ('en', 'ru'), ('ru', 'en'),
    ('en', 'tr'), ('tr', 'en'),
    ('en', 'he'), ('he', 'en'),
]

LANG_NAMES = {
    'en': 'English', 'fa': 'Persian/Farsi',
    'ar': 'Arabic',  'ru': 'Russian',
    'tr': 'Turkish', 'he': 'Hebrew',
}


# =============================================================================
# CONVERSION LOGIC
# =============================================================================

def _get_map(from_lang: str, to_lang: str) -> dict | None:
    f, t = from_lang.lower(), to_lang.lower()
    if (f, t) in _MAPS:
        return _MAPS[(f, t)][0]
    if (t, f) in _MAPS:
        return _MAPS[(t, f)][1]
    if (f, t) == ('fa_leg', 'en'):
        return _MAPS[('en', 'fa_leg')][1]
    return None


def _detect_persian_layout(text: str) -> str:
    if any('\u064B' <= c <= '\u0652' for c in text):
        return 'fa'
    if 'ژ' in text:
        return 'fa_leg'
    return 'fa'


def auto_detect_source(text: str) -> str:
    if not text.strip():
        return 'en'
    non_ascii = [c for c in text if ord(c) > 127]
    if non_ascii:
        counts = {'arabic_block': 0, 'ru': 0, 'he': 0}
        # Characters that only appear in Persian (not in Arabic)
        persian_exclusive = set('پچژگ')
        # Persian Kaf (ک U+06A9) and Persian Yeh (ی U+06CC) are Persian-only
        persian_exclusive.update('\u06A9\u06CC')
        # Characters that are strongly Arabic (not used in Persian)
        arabic_exclusive = set(
            '\u0643'   # ك Arabic Kaf  (Persian uses ک U+06A9 instead)
            '\u064A'   # ي Arabic Yeh  (Persian uses ی U+06CC instead)
            '\u0649'   # ى Alef Maqsura
        )
        for c in non_ascii:
            cp = ord(c)
            if 0x0600 <= cp <= 0x06FF:
                counts['arabic_block'] += 1
            elif 0x0400 <= cp <= 0x04FF:
                counts['ru'] += 1
            elif 0x0590 <= cp <= 0x05FF:
                counts['he'] += 1
        if counts['arabic_block'] > 0:
            has_persian = any(c in persian_exclusive for c in text)
            has_arabic  = any(c in arabic_exclusive for c in text)
            if has_arabic and not has_persian:
                return 'ar'
            # Default to Persian — far more common mismatch scenario,
            # and the shared characters (ئ، ؤ، إ، أ، آ …) appear in both
            return 'fa'
        if counts['ru'] > 0:
            return 'ru'
        if counts['he'] > 0:
            return 'he'
        return 'en'
    # All ASCII — the source is always 'en' when text contains only ASCII.
    # We cannot distinguish "typed in EN by mistake while FA was active" from
    # "genuine English text" using characters alone — that requires OS layout
    # state, which is handled by LanguageMonitor. Here we just return 'en'
    # so that convert_auto can apply its EN→FA default hint.
    return 'en'


def convert(text: str, from_lang: str, to_lang: str) -> tuple:
    f = from_lang.lower()
    t = to_lang.lower()
    if f == 'fa':
        f = _detect_persian_layout(text)
    mapping = _get_map(f, t)
    if mapping is None:
        raise ValueError(
            f"No mapping for {from_lang.upper()} → {to_lang.upper()}. "
            f"Run --list to see supported pairs."
        )
    result = ''.join(mapping.get(c, c) for c in text)
    return result, f.replace('_leg', '').replace('_std', ''), t


def convert_auto(text: str, hint_to: str | None = None) -> tuple:
    src = auto_detect_source(text)
    if src == 'en':
        tgt = hint_to
        if not tgt:
            _log('note: ASCII input; cannot auto-detect target. Defaulting to EN→FA. Use -t LANG to specify.')
            tgt = 'fa'
    else:
        tgt = hint_to or 'en'
    return convert(text, src, tgt)


# =============================================================================
# LOGGING
# =============================================================================

_log_file: str | None = None


def _log(msg: str) -> None:
    print(f'[switex] {msg}', file=sys.stderr, flush=True)
    if _log_file:
        try:
            import datetime
            ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(_log_file, 'a', encoding='utf-8') as fh:
                fh.write(f'[{ts}] {msg}\n')
        except Exception:
            pass


def _die(msg: str) -> None:
    _log(msg)
    sys.exit(1)


# =============================================================================
# LANGUAGE MONITOR  — detects current & previous keyboard layout from the OS
# =============================================================================
#
# Windows:  GetKeyboardLayout on the foreground window thread (same technique
#           as the C# app). Maps the low-word LCID to a two-letter ISO code.
# macOS:    Reads the active input source via AppKit (NSTextInputContext) or
#           falls back to parsing `defaults read` on the HIToolbox plist.
# Linux:    Calls `xkblayout-state get %s` (X11) or parses `setxkbmap -query`.
#
# The monitor polls every 150 ms on a background daemon thread.
# It stores the two most recent *distinct* language codes so the hotkey
# handler always knows (previous → current) even if called a moment after
# the switch.

class LanguageMonitor:
    """
    Polls the OS keyboard layout and tracks (previous_lang, current_lang).
    Both values are ISO 639-1 two-letter codes in lowercase: 'en', 'fa', etc.
    Falls back to None if detection is not supported on this platform.
    """

    # LCID low-word → ISO 639-1 (subset we care about)
    _LCID_MAP = {
        0x0409: 'en', 0x0809: 'en', 0x0C09: 'en', 0x1009: 'en',  # English variants
        0x0429: 'fa',  # Persian
        0x0401: 'ar', 0x0801: 'ar', 0x0C01: 'ar', 0x1001: 'ar',  # Arabic variants
        0x2801: 'ar', 0x3401: 'ar', 0x3801: 'ar', 0x3C01: 'ar',
        0x0419: 'ru',  # Russian
        0x041F: 'tr',  # Turkish
        0x040D: 'he',  # Hebrew
        0x040C: 'fr', 0x080C: 'fr',  # French
        0x0407: 'de',  # German
        0x0410: 'it',  # Italian
        0x0C0A: 'es', 0x040A: 'es',  # Spanish
        0x0416: 'pt', 0x0816: 'pt',  # Portuguese
        0x0422: 'uk',  # Ukrainian
        0x0415: 'pl',  # Polish
        0x0412: 'ko',  # Korean
        0x0411: 'ja',  # Japanese
        0x0804: 'zh', 0x0404: 'zh', 0x0C04: 'zh',  # Chinese
    }

    _POLL_INTERVAL = 0.15  # seconds

    def __init__(self):
        self.current:  str | None = None
        self.previous: str | None = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._supported: bool = True

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Start polling. Returns True if language detection is supported."""
        lang = self._get_os_lang()
        if lang is None:
            self._supported = False
            return False
        with self._lock:
            self.current  = lang
            self.previous = lang
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        return True

    def get(self) -> tuple:
        """Return (previous_lang, current_lang) as lowercase ISO codes."""
        with self._lock:
            return self.previous, self.current

    @property
    def supported(self) -> bool:
        return self._supported

    # ── Internal ──────────────────────────────────────────────────────────────

    def snapshot(self) -> tuple:
        """
        Capture (hwnd, lang) RIGHT NOW for the foreground window.
        hwnd is passed to the worker so it can read the layout of the
        correct window even after focus has shifted to pythonw.
        Returns (hwnd, lang) on Windows; (0, lang) on other platforms.
        """
        if sys.platform == 'win32':
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                lang = self._get_lang_for_hwnd(hwnd)
                return (hwnd, lang)
            except Exception:
                return (0, self._get_os_lang())
        return (0, self._get_os_lang())

    def lang_for_hwnd(self, hwnd: int) -> str | None:
        """Read keyboard layout for a specific window handle (Windows only)."""
        if sys.platform == 'win32' and hwnd:
            return self._get_lang_for_hwnd(hwnd)
        return self._get_os_lang()

    def _get_lang_for_hwnd(self, hwnd: int) -> str | None:
        """Windows: get keyboard layout for a given HWND."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            thread_id = user32.GetWindowThreadProcessId(hwnd, None)
            hkl  = user32.GetKeyboardLayout(thread_id)
            lcid = hkl & 0xFFFF
            if lcid in self._LCID_MAP:
                return self._LCID_MAP[lcid]
            buf = ctypes.create_unicode_buffer(9)
            ctypes.windll.kernel32.GetLocaleInfoW(lcid, 0x59, buf, 9)
            code = buf.value.lower()
            return code if code else None
        except Exception:
            return None

    def _poll_loop(self) -> None:
        while True:
            time.sleep(self._POLL_INTERVAL)
            try:
                lang = self._get_os_lang()
                if lang is None:
                    continue
                with self._lock:
                    if lang != self.current:
                        self.previous = self.current
                        self.current  = lang
            except Exception:
                pass

    def _get_os_lang(self) -> str | None:
        if sys.platform == 'win32':
            return self._get_lang_windows()
        elif sys.platform == 'darwin':
            return self._get_lang_macos()
        else:
            return self._get_lang_linux()

    # ── Windows ───────────────────────────────────────────────────────────────

    def _get_lang_windows(self) -> str | None:
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            return self._get_lang_for_hwnd(hwnd)
        except Exception:
            return None

    # ── macOS ─────────────────────────────────────────────────────────────────

    def _get_lang_macos(self) -> str | None:
        # Method 1: AppKit (most reliable, no subprocess)
        try:
            from AppKit import NSTextInputContext  # type: ignore
            src = NSTextInputContext.currentInputContext()
            if src:
                name = src.selectedKeyboardInputSource()
                # e.g. "com.apple.keylayout.Persian" → "fa"
                return self._parse_macos_source(name)
        except Exception:
            pass
        # Method 2: subprocess defaults read
        try:
            import subprocess, plistlib
            raw = subprocess.check_output(
                ['defaults', 'read', 'com.apple.HIToolbox', 'AppleCurrentKeyboardLayoutInputSourceID'],
                stderr=subprocess.DEVNULL, timeout=1
            ).decode().strip()
            return self._parse_macos_source(raw)
        except Exception:
            pass
        return None

    def _parse_macos_source(self, source_id: str) -> str | None:
        if not source_id:
            return None
        s = source_id.lower()
        _MAC_MAP = {
            'persian':   'fa', 'arabic':    'ar', 'russian':   'ru',
            'turkish':   'tr', 'hebrew':    'he', 'french':    'fr',
            'german':    'de', 'italian':   'it','spanish':   'es',
            'portuguese':'pt', 'ukrainian': 'uk', 'polish':    'pl',
            'korean':    'ko', 'japanese':  'ja', 'chinese':   'zh',
            'us':        'en', 'british':   'en', 'australian':'en',
        }
        for key, code in _MAC_MAP.items():
            if key in s:
                return code
        return None

    # ── Linux ─────────────────────────────────────────────────────────────────

    def _get_lang_linux(self) -> str | None:
        # Method 1: xkblayout-state (most reliable if installed)
        try:
            import subprocess
            out = subprocess.check_output(
                ['xkblayout-state', 'print', '%s'],
                stderr=subprocess.DEVNULL, timeout=1
            ).decode().strip().lower()
            return self._xkb_to_iso(out)
        except Exception:
            pass
        # Method 2: setxkbmap -query
        try:
            import subprocess
            out = subprocess.check_output(
                ['setxkbmap', '-query'],
                stderr=subprocess.DEVNULL, timeout=1
            ).decode()
            for line in out.splitlines():
                if line.startswith('layout:'):
                    layout = line.split(':', 1)[1].strip().split(',')[0].lower()
                    return self._xkb_to_iso(layout)
        except Exception:
            pass
        return None

    def _xkb_to_iso(self, xkb: str) -> str | None:
        _XKB_MAP = {
            'us': 'en', 'gb': 'en', 'au': 'en',
            'ir': 'fa', 'ara': 'ar', 'ru': 'ru',
            'tr': 'tr', 'il': 'he', 'fr': 'fr',
            'de': 'de', 'it': 'it', 'es': 'es',
            'pt': 'pt', 'ua': 'uk', 'pl': 'pl',
            'kr': 'ko', 'jp': 'ja', 'cn': 'zh',
        }
        return _XKB_MAP.get(xkb)


# =============================================================================
# CLIPBOARD HELPERS
# =============================================================================

def _get_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or ''
    except ImportError:
        _die('Clipboard mode requires pyperclip.\n  pip install pyperclip')
    return ''


def _set_clipboard(text: str) -> None:
    try:
        import pyperclip
        pyperclip.copy(text)
    except ImportError:
        _die('Clipboard mode requires pyperclip.\n  pip install pyperclip')


# =============================================================================
# DAEMON — SAFE WORKER ARCHITECTURE
# =============================================================================
#
# KEY DESIGN PRINCIPLE:
# The hotkey callback MUST return immediately (< a few ms).
# All actual work (clipboard read/write, key simulation) happens in a
# separate worker thread. The callback only puts a signal in a queue.
# This prevents any keyboard lockup on any platform.

_DELAY_AFTER_COPY  = 0.35   # seconds to wait after simulating Ctrl+C
_DELAY_BEFORE_PASTE = 0.12  # seconds to wait before simulating Ctrl+V
_CLIPBOARD_TIMEOUT  = 3.0   # max seconds to wait for clipboard change
_CLIPBOARD_POLL     = 0.05  # polling interval


def _wait_clipboard_change(old_text: str, timeout: float = _CLIPBOARD_TIMEOUT) -> str:
    """Poll clipboard until it differs from old_text or timeout expires."""
    try:
        import pyperclip
    except ImportError:
        return old_text
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(_CLIPBOARD_POLL)
        try:
            current = pyperclip.paste() or ''
            if current != old_text:
                return current
        except Exception:
            pass
    return old_text


def _release_hotkey_keys() -> None:
    """
    Release Ctrl, Shift, Alt, and Space so they are not held down
    when we simulate Ctrl+C. If any modifier is still physically held,
    the OS may interpret our Ctrl+C as Ctrl+Shift+C or similar.
    """
    try:
        from pynput.keyboard import Controller, Key
        kb = Controller()
        for key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r,
                    Key.shift, Key.shift_l, Key.shift_r,
                    Key.alt, Key.alt_l, Key.alt_r, Key.space):
            try:
                kb.release(key)
            except Exception:
                pass
    except Exception:
        pass


def _simulate_copy() -> None:
    """Simulate Ctrl+C (or Cmd+C on macOS) using pynput."""
    try:
        from pynput.keyboard import Controller, Key
        kb = Controller()
        # Release any held hotkey keys first, then wait for the OS
        # to process the releases and return focus to the target window.
        _release_hotkey_keys()
        time.sleep(0.15)
        mod = Key.cmd if sys.platform == 'darwin' else Key.ctrl
        with kb.pressed(mod):
            kb.press('c')
            kb.release('c')
        time.sleep(_DELAY_AFTER_COPY)
    except Exception as e:
        _log(f'simulate_copy failed: {e}')


def _simulate_paste() -> None:
    """Simulate Ctrl+V (or Cmd+V on macOS) using pynput."""
    try:
        from pynput.keyboard import Controller, Key
        kb = Controller()
        mod = Key.cmd if sys.platform == 'darwin' else Key.ctrl
        with kb.pressed(mod):
            kb.press('v')
            kb.release('v')
        time.sleep(0.05)
    except Exception as e:
        _log(f'simulate_paste failed: {e}')


def _worker_do_convert(from_lang, to_lang, pyperclip_module,
                       lang_monitor: LanguageMonitor | None = None,
                       fire_lang: str | None = None,
                       fire_hwnd: int = 0) -> None:
    """
    The actual work: copy → convert → paste.
    Always runs in a worker thread, never in the hotkey callback.

    Language resolution priority:
      1. Explicit -f / -t flags (always win)
      2. fire_lang = layout of the user's window at the exact hotkey-fire
         instant (captured before any focus shift), paired with the
         monitor's cached previous value
      3. Text-based auto-detect (last resort)

    On Windows, fire_hwnd lets us re-read the layout of the original window
    even after focus has moved — useful if fire_lang was missed.
    """
    resolved_from = from_lang
    resolved_to   = to_lang

    if (resolved_from is None or resolved_to is None) and lang_monitor and lang_monitor.supported:
        prev, _ = lang_monitor.get()

        # fire_lang: layout of the foreground window at hotkey-fire time.
        # On Windows with fire_hwnd, re-read it now to be sure.
        curr = fire_lang
        if fire_hwnd and sys.platform == 'win32':
            curr = lang_monitor.lang_for_hwnd(fire_hwnd) or curr

        if curr:
            if prev and prev != curr:
                # Clean switch: text typed in prev, switched to curr
                resolved_from = resolved_from or prev
                resolved_to   = resolved_to   or curr
                _log(f'OS layout: {prev.upper()} → {curr.upper()}')
            elif curr != 'en':
                # No switch or switch not detected, but active layout is non-EN.
                # Most likely: user typed in EN while this layout was active,
                # intending to type in this language. EN → curr.
                resolved_from = resolved_from or 'en'
                resolved_to   = resolved_to   or curr
                _log(f'OS layout: {curr.upper()} active → assuming EN → {curr.upper()}')
            else:
                # Active layout is EN — truly ambiguous, use text auto-detect.
                # But for ASCII text, EN→FA is the most common mistake,
                # so hint auto-detect toward FA if nothing else matches.
                _log(f'OS layout: EN active — using text auto-detect (hint: EN→FA)')

    # Save clipboard so we can restore it
    try:
        backup = pyperclip_module.paste() or ''
    except Exception:
        backup = ''

    # Simulate copy to get selected text
    _simulate_copy()
    selected = _wait_clipboard_change(backup)

    if selected == backup:
        _log('✗ clipboard did not change — make sure text is selected before pressing the hotkey')
        return

    if not selected.strip():
        _log('✗ clipboard empty — nothing was selected')
        return

    # Convert
    try:
        if resolved_from and resolved_to:
            result, f, t = convert(selected, resolved_from, resolved_to)
        else:
            result, f, t = convert_auto(selected, hint_to=resolved_to)
    except ValueError as e:
        _log(f'✗ {e}')
        try:
            pyperclip_module.copy(backup)
        except Exception:
            pass
        return

    if result == selected:
        _log(f'~ no change ({f.upper()}→{t.upper()}) — text may already be correct')
        try:
            pyperclip_module.copy(backup)
        except Exception:
            pass
        return

    # Paste
    try:
        pyperclip_module.copy(result)
    except Exception as e:
        _log(f'✗ failed to write clipboard: {e}')
        return

    time.sleep(_DELAY_BEFORE_PASTE)
    _simulate_paste()

    preview = result[:60].replace('\n', '↵')
    ellipsis = '…' if len(result) > 60 else ''
    _log(f'✓ {f.upper()}→{t.upper()}  "{preview}{ellipsis}"')

    # Restore original clipboard after 2 seconds
    def _restore():
        time.sleep(2.0)
        try:
            pyperclip_module.copy(backup)
        except Exception:
            pass
    threading.Thread(target=_restore, daemon=True).start()


def run_daemon(hotkey_str: str, from_lang, to_lang) -> None:
    """
    Start the hotkey daemon.

    Uses pynput.GlobalHotKeys on all platforms. This is the safest approach:
      - pynput uses native OS hotkey APIs under the hood
      - The callback only enqueues work; all actual work runs in a thread pool
      - No manual hook installation, no risk of keyboard lockup

    Falls back to Windows RegisterHotKey only if pynput is not installed.
    """
    try:
        import pyperclip
    except ImportError:
        _die('Daemon mode requires pyperclip.\n  pip install pyperclip')

    # Start OS language monitor
    lang_monitor = LanguageMonitor()
    monitor_ok = lang_monitor.start()
    if monitor_ok:
        prev, curr = lang_monitor.get()
        _log(f'language monitor: active (current layout: {curr.upper() if curr else "?"})')
    else:
        _log('language monitor: not supported on this platform — using text auto-detect')
        lang_monitor = None

    _log(f'hotkey   : {hotkey_str}')
    if from_lang or to_lang:
        _log(f'direction: {(from_lang or "auto").upper()} → {(to_lang or "auto").upper()} (explicit)')
    else:
        _log(f'direction: auto (OS layout tracking)')
    _log('ready — press Ctrl+C in this terminal to stop\n')

    # ── pynput path (preferred, all platforms) ────────────────────────────────
    try:
        from pynput import keyboard as pynput_kb
    except ImportError:
        pynput_kb = None

    if pynput_kb is not None:
        import queue as _queue
        _work_q: _queue.Queue = _queue.Queue()
        _DEBOUNCE = 0.5
        _last_fire = [0.0]

        def _on_activate():
            # Runs in pynput's listener thread — must return fast.
            # Capture foreground hwnd + lang HERE, before any focus shift.
            now = time.monotonic()
            if now - _last_fire[0] < _DEBOUNCE:
                return
            _last_fire[0] = now
            # snapshot() returns (hwnd, lang) — both captured before focus shifts
            snap = lang_monitor.snapshot() if lang_monitor else (0, None)
            _work_q.put(snap)

        def _worker_loop():
            while True:
                snap = _work_q.get()   # blocks until signal
                try:
                    fire_hwnd = snap[0] if snap else 0
                    fire_lang = snap[1] if snap else None
                    _worker_do_convert(from_lang, to_lang, pyperclip,
                                       lang_monitor, fire_lang, fire_hwnd)
                except Exception as e:
                    _log(f'unexpected error: {e}')

        threading.Thread(target=_worker_loop, daemon=True).start()

        try:
            listener = pynput_kb.GlobalHotKeys({hotkey_str: _on_activate})
            listener.start()
            # Expose listener globally so external callers (e.g. tray app) can
            # call switex._active_listener.stop() to shut down cleanly.
            import switex as _self_mod
            _self_mod._active_listener = listener
            _log(f'method: pynput.GlobalHotKeys')
            while listener.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            _log(f'pynput GlobalHotKeys failed: {e}')
            _log('Try a different hotkey or install pynput: pip install pynput')
        finally:
            _log('stopped.')
        return

    # ── Windows-only RegisterHotKey fallback (no pynput) ──────────────────────
    if sys.platform != 'win32':
        _die(
            'Daemon mode requires pynput.\n'
            '  pip install pynput pyperclip\n\n'
            'On Linux you may also need:\n'
            '  sudo apt install python3-xlib\n'
            '  or run under XWayland if on Wayland'
        )

    _log('pynput not found — using Windows RegisterHotKey fallback')
    _run_daemon_win_register(hotkey_str, from_lang, to_lang, pyperclip, lang_monitor)


def _run_daemon_win_register(hotkey_str, from_lang, to_lang, pyperclip, lang_monitor) -> None:
    """
    Windows-only RegisterHotKey daemon (used only when pynput is absent).
    Safe: the message loop only enqueues work; a worker thread does everything.
    """
    import ctypes
    import ctypes.wintypes as wt
    import queue as _queue

    user32   = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    MOD_CONTROL  = 0x0002
    MOD_SHIFT    = 0x0004
    MOD_ALT      = 0x0001
    MOD_WIN      = 0x0008
    MOD_NOREPEAT = 0x4000
    WM_HOTKEY    = 0x0312

    _MOD_MAP = {
        'ctrl': MOD_CONTROL, 'control': MOD_CONTROL,
        'shift': MOD_SHIFT, 'alt': MOD_ALT,
        'win': MOD_WIN, 'cmd': MOD_WIN,
    }
    _VK_MAP = {
        'space': 0x20, 'enter': 0x0D, 'tab': 0x09,
        'esc': 0x1B, 'escape': 0x1B,
        'f1':0x70,'f2':0x71,'f3':0x72,'f4':0x73,
        'f5':0x74,'f6':0x75,'f7':0x76,'f8':0x77,
        'f9':0x78,'f10':0x79,'f11':0x7A,'f12':0x7B,
        'insert':0x2D,'delete':0x2E,'del':0x2E,
        'home':0x24,'end':0x23,'pageup':0x21,'pagedown':0x22,
        'up':0x26,'down':0x28,'left':0x25,'right':0x27,
    }

    parts = [p.strip().lower().strip('<>') for p in hotkey_str.split('+')]
    mods  = MOD_NOREPEAT
    vk    = 0
    for part in parts:
        if part in _MOD_MAP:
            mods |= _MOD_MAP[part]
        elif part in _VK_MAP:
            vk = _VK_MAP[part]
        elif len(part) == 1:
            vk = user32.VkKeyScanA(ctypes.c_char(part.encode('ascii'))) & 0xFF
        else:
            _die(f"Unknown hotkey token: '{part}'")
    if vk == 0:
        _die(f"No virtual key in hotkey: '{hotkey_str}'")

    HOTKEY_ID = 42
    if not user32.RegisterHotKey(None, HOTKEY_ID, mods, vk):
        err = kernel32.GetLastError()
        _die(
            f'RegisterHotKey failed (err={err}). '
            'The hotkey may be taken by another app or IME.\n'
            'Try a different hotkey or install pynput: pip install pynput'
        )

    _log(f'method: RegisterHotKey  mods=0x{mods:04X}  vk=0x{vk:02X}')

    _work_q: _queue.Queue = _queue.Queue()
    _DEBOUNCE = 0.5
    _last_fire = [0.0]

    def _worker_loop():
        while True:
            snap = _work_q.get()
            try:
                fire_hwnd = snap[0] if snap else 0
                fire_lang = snap[1] if snap else None
                _worker_do_convert(from_lang, to_lang, pyperclip,
                                   lang_monitor, fire_lang, fire_hwnd)
            except Exception as e:
                _log(f'unexpected error: {e}')

    threading.Thread(target=_worker_loop, daemon=True).start()

    class MSG(ctypes.Structure):
        _fields_ = [
            ('hwnd', wt.HWND), ('message', wt.UINT),
            ('wParam', wt.WPARAM), ('lParam', wt.LPARAM),
            ('time', wt.DWORD), ('pt', wt.POINT),
        ]

    msg = MSG()
    try:
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                now = time.monotonic()
                if now - _last_fire[0] >= _DEBOUNCE:
                    _last_fire[0] = now
                    # Capture (hwnd, lang) here, before any focus shift
                    snap = lang_monitor.snapshot() if lang_monitor else (0, None)
                    _work_q.put(snap)
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID)
        _log('stopped.')


# =============================================================================
# CLI
# =============================================================================

def print_supported_pairs() -> None:
    print('\nSupported language pairs:\n')
    seen = set()
    for f, t in SUPPORTED_PAIRS:
        pair = tuple(sorted([f, t]))
        if pair not in seen:
            seen.add(pair)
            fn = LANG_NAMES.get(f, f.upper())
            tn = LANG_NAMES.get(t, t.upper())
            print(f'  {f.upper():4} ↔ {t.upper():4}   ({fn} ↔ {tn})')
    print()


def _validate_lang(code: str, role: str) -> str:
    code = code.lower()
    valid = {f for f, _ in SUPPORTED_PAIRS} | {t for _, t in SUPPORTED_PAIRS}
    if code not in valid:
        _die(f"Unknown {role} language '{code}'. Run --list to see options.")
    return code


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='switex',
        description='Convert text typed in the wrong keyboard layout.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  echo "sghl" | switex                       # auto-detect → convert
  echo "sghl" | switex -f en -t fa           # explicit EN→FA
  switex -f ru -t en "ghbdtn"                # inline text
  cat file.txt | switex -f en -t ar          # from file
  switex --clipboard                         # convert clipboard
  switex --clipboard -f en -t ru             # clipboard, explicit direction
  switex --daemon                            # start hotkey daemon
  switex --daemon --hotkey "<ctrl>+<alt>+k"  # custom hotkey
  switex --list                              # show supported pairs
        """,
    )

    parser.add_argument('-f', '--from', dest='from_lang', metavar='LANG',
                        help='source language (default: auto-detect)')
    parser.add_argument('-t', '--to', dest='to_lang', metavar='LANG',
                        help='target language (default: auto-detect)')
    parser.add_argument('text', nargs='?', default=None,
                        help='text to convert (omit to read from stdin)')
    parser.add_argument('--clipboard', '-c', action='store_true',
                        help='read from clipboard, write converted text back')
    parser.add_argument('--daemon', '-d', action='store_true',
                        help='start hotkey daemon (requires pynput + pyperclip)')
    parser.add_argument('--hotkey', default='<ctrl>+<alt>+<space>',
                        metavar='HOTKEY',
                        help='hotkey for daemon mode (default: <ctrl>+<alt>+<space>)')
    parser.add_argument('--list', '-l', action='store_true',
                        help='list supported language pairs and exit')
    parser.add_argument('--log', metavar='FILE',
                        help='write log output to FILE (useful with pythonw.exe)')

    args = parser.parse_args()

    global _log_file
    if args.log:
        _log_file = args.log

    if args.list:
        print_supported_pairs()
        return

    from_lang = _validate_lang(args.from_lang, 'source') if args.from_lang else None
    to_lang   = _validate_lang(args.to_lang,   'target') if args.to_lang   else None

    if args.daemon:
        run_daemon(args.hotkey, from_lang, to_lang)
        return

    if args.clipboard:
        text = _get_clipboard()
        if not text.strip():
            _die('clipboard is empty.')
        if from_lang and to_lang:
            result, f, t = convert(text, from_lang, to_lang)
        else:
            result, f, t = convert_auto(text, hint_to=to_lang)
        _set_clipboard(result)
        _log(f'✓ {f.upper()}→{t.upper()} — converted text written to clipboard')
        return

    if args.text:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print('Enter text to convert (Ctrl+D / Ctrl+Z when done):', file=sys.stderr)
        text = sys.stdin.read()

    text = text.rstrip('\n')

    try:
        if from_lang and to_lang:
            result, f, t = convert(text, from_lang, to_lang)
        else:
            result, f, t = convert_auto(text, hint_to=to_lang)
    except ValueError as e:
        _die(str(e))
        return

    print(result)


if __name__ == '__main__':
    main()
