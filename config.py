"""
Switex — Configuration & Localization Data
Contains all static character maps and UI localization dictionaries.
"""

def _rev(d: dict) -> dict:
    r = {}
    for k, v in d.items():
        if v not in r:
            r[v] = k
    return r

def _zip(src: str, dst: str) -> dict:
    return {s: d for s, d in zip(src, dst)}

# Persian Standard Map Configuration
_EN_FA_STD: dict = {
    '`': '\u200D', '1':'۱','2':'۲','3':'۳','4':'۴','5':'۵',
    '6':'۶','7':'۷','8':'۸','9':'۹','0':'۰', '-':'-', '=':'=',
    '~':'÷','!':'!','@':'٬','#':'٫','$':'﷼', '%':'٪','^':'×','&':'،','*':'*',
    '(' :')',')'  :'(','_':'ـ','+':'+',
    'q':'ض','w':'ص','e':'ث','r':'ق','t':'ف', 'y':'غ','u':'ع','i':'ه','o':'خ','p':'ح',
    '[':'ج',']':'چ',
    'Q':'ْ','W':'ٌ','E':'ٍ','R':'ً','T':'ُ', 'Y':'ِ','U':'َ','I':'ّ','O':']','P':'[',
    '{':'}','}':'{',
    'a':'ش','s':'س','d':'ی','f':'ب','g':'ل', 'h':'ا','j':'ت','k':'ن','l':'م',';':'ک',"'":'گ',
    'A':'ؤ','S':'ئ','D':'ي','F':'إ','G':'أ', 'H':'آ','J':'ة','K':'»','L':'«',':':':','"':'；',
    'z':'ظ','x':'ط','c':'ز','v':'ر','b':'ذ', 'n':'د','m':'پ',',':'و','.':'.','/':'/',
    'Z':'ك','X':'ٓ','C':'ژ','V':'ٰ','B':'\u200C', 'N':'ٔ','M':'ء','<':'>','>':'<','?':'؟',
    '\\'  :'\\','|':'|',' ':' ','\n':'\n','\t':'\t',
}

_EN_FA_LEG: dict = {**_EN_FA_STD, '\\'  :'ژ'}

_EN_AR: dict = {
    **_zip('1234567890-=', '١٢٣٤٥٦٧٨٩٠-='),
    **_zip('qwertyuiop[]\\'  , 'ضصثقفغعهخحجد\\'),
    **_zip("asdfghjkl;'",   'شسيبلاتنمكط'),
    **_zip('zxcvbnm,./',    'ئءؤرىةوز,.'),
    '`':'ذ', '~':'ّ', ' ':' ', '\n':'\n', '\t':'\t',
}

_EN_RU: dict = {
    **_zip('qwertyuiop[]\\'  , 'йцукенгшщзхъ\\'),
    **_zip("asdfghjkl;'",   'фывапролджэ'),
    **_zip('zxcvbnm,./',    'ячсмитьбю.'),
    **_zip('QWERTYUIOP{}|', 'ЙЦУКЕНГШЩЗХЪ|'),
    **_zip('ASDFGHJKL:"',   'ФЫВАПРОЛДЖЭ'),
    **_zip('ZXCVBNM<>?',    'ЯЧСМИТЬБЮ,'),
    **_zip('1234567890-=',  '1234567890-='),
    ' ':' ', '\n':'\n', '\t':'\t',
}

_EN_TR: dict = {
    **_zip('abcdefghijklmnopqrstuvwxyz', 'abcçdefgğhıijklmnoöprsştuüvyz'),
    **_zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ'),
    **_zip('1234567890-=', '1234567890-='),
    ' ':' ', '\n':'\n', '\t':'\t',
}

_EN_HE: dict = {
    **_zip('qwertyuiop',  'קואבטיحيפ'),
    **_zip('asdfghjkl;',  'שدגכעיחלפ'),
    **_zip('zxcvbnm',     'זسبنهצم'),
    **_zip('1234567890',  '1234567890'),
    ' ':' ', '\n':'\n', '\t':'\t',
}

MAPS: dict = {
    ('en', 'fa'):     _EN_FA_STD,
    ('en', 'fa_leg'): _EN_FA_LEG,
    ('en', 'ar'):     _EN_AR,
    ('en', 'ru'):     _EN_RU,
    ('en', 'tr'):     _EN_TR,
    ('en', 'he'):     _EN_HE,
}

def generate_reverse_maps() -> None:
    new_entries = {}
    for (f, t), mapping in MAPS.items():
        new_entries[(t, f)] = _rev(mapping)
    MAPS.update(new_entries)

generate_reverse_maps()

# =============================================================================
# LOCALIZATION DICTIONARY (UI/UX Texts)
# =============================================================================
LOCALIZED_STRINGS = {
    'en': {
        'status_running': '● Running',
        'status_stopped': '○ Stopped',
        'menu_start': 'Start',
        'menu_stop': 'Stop',
        'menu_startup': 'Run at Startup',
        'menu_lang': 'Language / زبان',
        'menu_guide': 'Auto-Detect Guide',
        'menu_shortcuts': 'Manual Layout Shortcuts',
        'menu_exit': 'Exit',
        'notif_start_title': 'Switex Active',
        'notif_start_msg': 'Hotkey {hk}: Select text -> Switch OS Layout -> Press Hotkey. For targeted language mapping, check "Manual Layout Shortcuts" menu.',
        'notif_stop_title': 'Switex Stopped',
        'notif_stop_msg': 'Conversion engine disabled.',
        'notif_startup_en': 'Added to Windows startup.',
        'notif_startup_dis': 'Removed from Windows startup.',
        'notif_error_title': 'System Error',
        'notif_error_msg': 'An error occurred. Please check the switex.log file.',
        'notif_lang_title': 'Language Changed',
        'notif_lang_msg': 'Application language has been set to English.',
        'log_init': 'Switex application process initialized.',
        'log_daemon_start': 'Switex core engine daemon started active.',
        'log_daemon_stop': 'Switex core engine daemon stopped by user request.',
        'log_startup_en': 'Windows startup execution enabled successfully.',
        'log_startup_dis': 'Windows startup execution disabled successfully.',
        'log_lang_change': 'Application language changed to English.',
    },
    'fa': {
        'status_running': '● در حال اجرا',
        'status_stopped': '○ متوقف شده',
        'menu_start': 'شروع',
        'menu_stop': 'توقف',
        'menu_startup': 'اجرا در شروع ویندوز',
        'menu_lang': 'Language / زبان',
        'menu_guide': 'راهنمای تشخیص خودکار',
        'menu_shortcuts': 'میانبرهای تغییر چیدمان دستی',
        'menu_exit': 'خروج',
        'notif_start_title': 'Switex فعال شد',
        'notif_start_msg': 'میانبر {hk}: متن را انتخاب کنید -> زبان کیبورد را تغییر دهید -> میانبر را بزنید. برای میانبر سایر زبان‌ها به منوی «میانبرهای تغییر چیدمان دستی» بروید.',
        'notif_stop_title': 'Switex متوقف شد',
        'notif_stop_msg': 'موتور تبدیل غیرفعال گردید.',
        'notif_startup_en': 'برنامه با موفقیت به بخش شروع خودکار ویندوز اضافه شد.',
        'notif_startup_dis': 'اجرای خودکار برنامه در شروع ویندوز لغو شد.',
        'notif_error_title': 'خطا در سیستم',
        'notif_error_msg': 'عملیات با خطا مواجه شد. لطفاً فایل switex.log را بررسی کنید.',
        'notif_lang_title': 'تغییر زبان',
        'notif_lang_msg': 'زبان برنامه به فارسی تغییر یافت.',
        'log_init': 'فرایند برنامه Switex مقداردهی اولیه شد.',
        'log_daemon_start': 'موتور پردازش پس‌زمینه Switex فعال گردید.',
        'log_daemon_stop': 'موتور پردازش پس‌زمینه بنا به درخواست کاربر متوقف شد.',
        'log_startup_en': 'قابلیت اجرای خودکار در شروع ویندوز فعال شد.',
        'log_startup_dis': 'قابلیت اجرای خودکار در شروع ویندوز غیرفعال شد.',
        'log_lang_change': 'زبان برنامه به فارسی تغییر داده شد.',
    }
}