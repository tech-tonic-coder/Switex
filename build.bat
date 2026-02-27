@echo off
setlocal EnableDelayedExpansion
set "DIR=%~dp0"
title Switex -- Build

:: Keep the window open on any unexpected exit
if "%~1"=="__child__" goto :main_start
cmd /k "%~f0" __child__
exit /b

:main_start
echo.
echo =========================================
echo   Switex - Build Switex.exe
echo =========================================
echo.
echo This will compile Switex into a single Switex.exe
echo that includes Python and all dependencies.
echo The final file will be in:  %DIR%dist\Switex.exe
echo.

:: ── Check Python ──────────────────────────────────────────────────────────────
echo [CHECK] Looking for Python 3.7+...
set "PYTHON="
for %%C in (python python3 py) do (
    if not defined PYTHON (
        %%C --version >nul 2>&1
        if not errorlevel 1 (
            for /f "tokens=2" %%V in ('%%C --version 2^>^&1') do (
                for /f "tokens=1,2 delims=." %%A in ("%%V") do (
                    if %%A GEQ 3 if %%B GEQ 7 set "PYTHON=%%C"
                )
            )
        )
    )
)

if not defined PYTHON (
    echo [ERROR] Python 3.7+ not found.
    echo         Install from https://www.python.org/downloads/
    pause & exit /b 1
)
echo [OK] Python found  (%PYTHON%)

:: ── Install/upgrade required packages ──────────────────────────────────────
echo.
echo [INSTALL] Installing required packages...
%PYTHON% -m pip install --upgrade pip >nul
%PYTHON% -m pip install pynput pyperclip pystray Pillow pyinstaller windows-toasts

if errorlevel 1 (
    echo.
    echo [ERROR] Package installation failed.
    echo         Try running this script as Administrator.
    pause & exit /b 1
)
echo [OK] All packages installed.

:: ── Resolve icon ──────────────────────────────────────────────────────────────
echo.
set "ICON_OPT="
set "ICON_DATA_OPT="
set "ICON_FILE=%DIR%switex.ico"

if exist "%ICON_FILE%" goto :icon_found
goto :icon_generate

:icon_found
echo [ICON] Found switex.ico -- using it for exe and tray.
set "ICON_OPT=--icon=%ICON_FILE%"
set "ICON_DATA_OPT=--add-data "%ICON_FILE%;.""
goto :icon_done

:icon_generate
echo [ICON] switex.ico not found -- generating default green-circle icon...

set "GEN_SCRIPT=%TEMP%\switex_gen_icon.py"
set "GEN_ICON=%DIR%switex_icon.ico"

(
echo from PIL import Image, ImageDraw, ImageFont
echo import sys
echo size = 256
echo img  = Image.new^('RGBA', ^(size, size^), ^(0, 0, 0, 0^)^)
echo draw = ImageDraw.Draw^(img^)
echo draw.ellipse^([4, 4, size-4, size-4], fill=^(34, 160, 54, 255^)^)
echo try:
echo     font = ImageFont.truetype^('arialbd.ttf', 160^)
echo except Exception:
echo     try:
echo         font = ImageFont.truetype^('arial.ttf', 160^)
echo     except Exception:
echo         font = ImageFont.load_default^(^)
echo text = 'S'
echo bbox = draw.textbbox^(^(0, 0^), text, font=font^)
echo tw = bbox[2] - bbox[0]
echo th = bbox[3] - bbox[1]
echo draw.text^(^(^(size - tw^) / 2 - bbox[0], ^(size - th^) / 2 - bbox[1]^), text, font=font, fill=^(255, 255, 255, 255^)^)
echo icon_path = sys.argv[1]
echo sizes = [16, 32, 48, 64, 128, 256]
echo frames = [img.resize^(^(s, s^), Image.LANCZOS^) for s in sizes]
echo frames[-1].save^(icon_path, format='ICO', sizes=[(s, s^) for s in sizes]^)
echo print^('Icon saved to: ' + icon_path^)
) > "%GEN_SCRIPT%"

%PYTHON% "%GEN_SCRIPT%" "%GEN_ICON%"
set "GEN_ERR=%ERRORLEVEL%"
del "%GEN_SCRIPT%" >nul 2>&1

if %GEN_ERR% neq 0 (
    echo [WARN] Icon generation failed. Building without a custom icon.
    set "ICON_OPT="
    set "ICON_DATA_OPT="
    goto :icon_done
)
echo [OK] Default icon generated.
set "ICON_OPT=--icon=%GEN_ICON%"

:icon_done

:: ── Run PyInstaller ───────────────────────────────────────────────────────────
echo.
echo [BUILD] Compiling Switex.exe with PyInstaller...
echo         This may take a minute...
echo.

%PYTHON% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name Switex ^
    --add-data "%DIR%switex.py;." ^
    %ICON_DATA_OPT% ^
    %ICON_OPT% ^
    --hidden-import pynput.keyboard ^
    --hidden-import pynput.mouse ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL._imaging ^
    --hidden-import pyperclip ^
    --hidden-import windows_toasts ^
    --hidden-import winrt.windows.ui.notifications ^
    --hidden-import winrt.windows.data.xml.dom ^
    --clean ^
    --noconfirm ^
    "%DIR%switex_tray.py"

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed.
    echo         Check the output above for details.
    pause & exit /b 1
)

:: ── Copy output ───────────────────────────────────────────────────────────────
echo.
if exist "%DIR%dist\Switex.exe" (
    copy /Y "%DIR%dist\Switex.exe" "%DIR%Switex.exe" >nul
    echo =========================================
    echo   BUILD SUCCESSFUL!
    echo.
    echo   Switex.exe is ready:
    echo   %DIR%Switex.exe
    echo.
    echo   Double-click Switex.exe to launch.
    echo   It will appear in your system tray.
    echo.
    echo   Right-click the tray icon for:
    echo     Start / Stop / Restart / Status
    echo     Run at Startup / Open Log / Exit
    echo =========================================
) else (
    echo [ERROR] Switex.exe not found in dist\ folder.
    echo         Build may have failed silently.
)

echo.
pause
