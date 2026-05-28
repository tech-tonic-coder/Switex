@echo off
echo ===================================================
echo    Building Switex.exe using NUITKA (Ultra-Optimized)
echo ===================================================

echo [1/4] Installing absolute minimum requirements...
python -m pip install --upgrade pip
python -m pip install pynput pyperclip pystray nuitka Pillow comtypes windows-toasts

echo [2/4] Generating temporary assets...
python build_assets.py

echo [3/4] Compiling to highly compressed native binary...
python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-disable-console ^
    --windows-icon-from-ico=switex.ico ^
    --include-data-files=switex.ico=./switex.ico ^
    --include-module=config ^
    --include-package=pystray ^
    --include-package=PIL ^
    --include-package=comtypes ^
    --include-package=windows_toasts ^
    --nofollow-import-to=*.tests ^
    --nofollow-import-to=unittest ^
    --nofollow-import-to=tkinter ^
    --nofollow-import-to=email ^
    --nofollow-import-to=html ^
    --nofollow-import-to=http ^
    --nofollow-import-to=urllib ^
    --nofollow-import-to=xml ^
    --nofollow-import-to=xmlrpc ^
    --nofollow-import-to=logging.handlers ^
    --nofollow-import-to=doctest ^
    --nofollow-import-to=pydoc ^
    --nofollow-import-to=difflib ^
    --nofollow-import-to=calendar ^
    --nofollow-import-to=ftplib ^
    --nofollow-import-to=imaplib ^
    --nofollow-import-to=mailbox ^
    --nofollow-import-to=smtplib ^
    --nofollow-import-to=turtle ^
    --nofollow-import-to=turtledemo ^
    --nofollow-import-to=test ^
    --nofollow-import-to=PIL.ImageTk ^
    --nofollow-import-to=PIL.ImageQt ^
    --python-flag=no_site ^
    --output-dir=build_out ^
    --output-filename=Switex.exe ^
    switex_tray.py

echo [4/4] Cleaning workspace...
python build_assets.py --cleanup

echo Build finished successfully!
echo Check your 'build_out' directory for the optimized binary.
pause